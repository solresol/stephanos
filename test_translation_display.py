import copy
import unittest
from translation_display import evaluate_candidate, inherit_text_blocks

TARGET = dict(id=10, source_document='meineke', text_hash='same')
POLICY = dict(id=1, version=1, baseline_choices={}, recipes={3:dict(recipe_key='gabe_v3',prompt_md5='hash')}, rules=[
    dict(candidate_class='human_translation', rank=10, label='Human', source_requirement='aligned'),
    dict(candidate_class='translation_run', model_name='gpt-6.1-sol', recipe_key='gabe_v3',rank=20,label='6.1 v3',source_requirement='aligned'),
    dict(candidate_class='translation_run', model_name='gpt-5.5', recipe_key='gabe_v3',rank=23,label='5.5 v3',source_requirement='aligned'),
    dict(candidate_class='external_translation',delivery_id=1,rank=80,label='External',source_requirement='external_unverified'),
    dict(candidate_class='translation_run', model_name='gpt-5.4-mini',recipe_key='gabe_v3',rank=90,label='Mini',source_requirement='aligned')])

def run(**changes):
    return dict(dict(kind='translation_run',id=1,lemma_id=2,translation_text='City.', status='approved',source_text_version_id=10,
        source_document='meineke',source_hash='same',model='gpt-6.1-sol',profile_version_id=3,prompt_md5='hash',
        uses_guidance_context=True,guidance_freshness_state='current',public_eligible=True,assessment={}), **changes)

def human(**changes):
    return run(**dict(dict(kind='human_translation',stage='reviewed',model=''), **changes))

def external(**changes):
    return run(**dict(dict(kind='external_translation',source_text_version_id=None,source_document=None,source_hash=None,
        status='not_individually_verified',delivery_id=1,match_status='exact_meineke',cohort='unmarked_reported_claude'), **changes))

class DisplayTests(unittest.TestCase):
    def evaluate(self, c, target=TARGET, policy=POLICY):return evaluate_candidate(c,target,policy)
    def test_human_and_model_order(self):
        items=[run(model='gpt-5.5'),run(),human()]
        self.assertEqual([self.evaluate(c)['display_rank'] for c in items], [23,20,10])
    def test_preferred_mini_wins_but_never_bypasses_risk(self):
        c=run(model='gpt-5.4-mini',assessment=dict(decision='prefer',reason='Checked'))
        self.assertEqual(self.evaluate(c)['display_rank'],0)
        for flag in ('risk_blocked','revision_pending'):
            self.assertFalse(self.evaluate(dict(c,**{flag:True}))['publishable'])
    def test_historical_equivalent_source_and_changed_text(self):
        c=run(source_text_version_id=9)
        self.assertEqual(self.evaluate(c)['alignment'],'equivalent_text')
        self.assertFalse(self.evaluate(dict(c,source_hash='changed'))['publishable'])
    def test_legacy_human_allowance_scoped_to_frozen_source(self):
        c=human(source_text_version_id=None,source_document=None,source_hash=None)
        self.assertFalse(self.evaluate(c)['publishable'])
        c['assessment']=dict(decision='allow',target_document='meineke',target_hash='same',alignment_state='legacy_unlinked')
        self.assertTrue(self.evaluate(c)['publishable'])
        self.assertFalse(self.evaluate(c,dict(TARGET,text_hash='changed'))['publishable'])
    def test_initial_human_unknown_model_and_experimental_profile_blocked(self):
        for c in (human(stage='initial'),run(model='future-model'),run(profile_version_id=99),run(prompt_md5='changed')):
            self.assertFalse(self.evaluate(c)['publishable'])
    def test_guidance_must_be_verified_even_if_zero_rules_matched(self):
        self.assertTrue(self.evaluate(run())['publishable'])
        for state in ('','needs_review','outdated','potentially_outdated'):
            self.assertFalse(self.evaluate(run(guidance_freshness_state=state))['publishable'])
    def test_external_labels_and_ambiguity(self):
        e=self.evaluate(external())
        self.assertTrue(e['publishable']);self.assertEqual(e['status'],'not_individually_verified')
        self.assertIn('reported Claude',e['display_attribution'])
        self.assertIn('reported reuse',self.evaluate(external(cohort='reused_project_marker'))['display_attribution'])
        self.assertFalse(self.evaluate(external(match_status='ambiguous'))['publishable'])
        self.assertFalse(self.evaluate(external(),dict(TARGET,source_document='kiesling'))['publishable'])
    def test_exclusion_beats_preference_and_stable_ties(self):
        self.assertFalse(self.evaluate(run(assessment=dict(decision='exclude',reason='Wrong')))['publishable'])
        policy=copy.deepcopy(POLICY);policy['baseline_choices']={'2':{'kind':'translation_run','id':'9'}}
        choices=[self.evaluate(run(id=i),policy=policy) for i in (1,9,20)]
        self.assertEqual(sorted(choices,key=lambda c:c['sort_key'])[0]['id'],'9')
    def test_formatting_only_copy_cannot_bypass_open_revision(self):
        original = run(translation_text="Kapai. The *ethnonym* is Kapaios.", revision_pending=True)
        copied = external(translation_text="Kapai. The ethnonym is Kapaios.")
        distinct = external(id=9, translation_text="Kapai. The ethnic form is Kapaios.")
        inherit_text_blocks([original, copied, distinct])
        self.assertFalse(self.evaluate(copied)['publishable'])
        self.assertTrue(self.evaluate(distinct)['publishable'])

    def test_bad_first_candidate_does_not_hide_eligible_fallback(self):
        choices=[self.evaluate(run(id=1,revision_pending=True)),self.evaluate(run(id=2,model='gpt-5.5'))]
        self.assertEqual([c['id'] for c in choices if c['publishable']],['2'])

if __name__=='__main__':unittest.main()
