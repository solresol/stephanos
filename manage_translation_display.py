#!/usr/bin/env python3
"""Seed, audit, activate, roll back and explain the public translation policy."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import canonical_variants
import translation_display as display

FRONTIER_MODELS = [
    'gpt-6.1-sol', 'gpt-6-sol', 'gpt-5.6-sol', 'gpt-5.5', 'gpt-5.4',
    'gpt-5.3-chat-latest', 'gpt-5.2-2025-12-11', 'gpt-5.2',
    'gpt-5.1-2025-11-13', 'gpt-5-2025-08-07', 'gpt-4.1-2025-04-14',
    'gpt-4o-2024-11-20', 'gpt-4o-2024-08-06', 'gpt-4o-2024-05-13',
    'gpt-4-turbo-2024-04-09',
]
MINI_MODELS = ['gpt-5.4-mini', 'gpt-6-luna', 'gpt-5.6-luna']
PROFILE_NAMES = set(FRONTIER_MODELS + MINI_MODELS + ['gpt-5', 'gpt-5.1', 'gpt-5.2'])


def compact(choice):
    if not choice:
        return None
    keys = ('kind', 'id', 'model', 'profile_version', 'display_reason', 'display_attribution',
            'alignment', 'display_target_source_id', 'display_policy_id')
    result = {key: choice.get(key) for key in keys}
    result['text_sha256'] = hashlib.sha256(choice['translation_text'].encode()).hexdigest()
    return result


def seed(cur):
    cur.execute("SELECT id FROM translation_display_policies WHERE name = 'scholarly_default' AND version = 1")
    existing = cur.fetchone()
    if existing:
        return existing[0]
    cur.execute("SELECT id FROM assembled_lemmas WHERE NOT COALESCE(quarantined, false) ORDER BY id")
    ids = [row[0] for row in cur.fetchall()]
    baseline = {}
    for lemma_id in ids:
        choices = canonical_variants.select_presented_variants_legacy(cur, lemma_id=lemma_id, ux_mode='single')
        if choices:
            baseline[str(lemma_id)] = {'kind': choices[0]['kind'], 'id': str(choices[0]['id'])}
    cur.execute("""INSERT INTO translation_display_policies
        (name,version,baseline_choices,created_by,notes) VALUES
        ('scholarly_default',1,%s::jsonb,'gregb via Codex',%s) RETURNING id""",
        (json.dumps(baseline), 'User approved 8 October 2026. Preserve approved humans; labelled Brady delivery 1 fallback; actual model and verified recipe ranking.'))
    policy_id = cur.fetchone()[0]
    for model in FRONTIER_MODELS + MINI_MODELS:
        cur.execute("INSERT INTO translation_models VALUES (%s,'openai',%s) ON CONFLICT (model_name) DO NOTHING",
                    (model, 'mini' if model in MINI_MODELS else 'frontier'))

    def rule(rank, kind, label, model=None, recipe=None, delivery=None):
        cur.execute("""INSERT INTO translation_display_preferences
            (policy_id,rank,candidate_class,model_name,recipe_key,delivery_id,source_requirement,label)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""", (policy_id,rank,kind,model,recipe,delivery,
                'external_unverified' if kind == 'external_translation' else 'aligned',label))
    rule(10, 'human_translation', 'Approved human translation')
    for i, model in enumerate(FRONTIER_MODELS):
        rule(20+i, 'translation_run', f'Gabe v3 using {model}', model, 'gabe_v3')
        rule(60+i, 'translation_run', f'Earlier scholarly prompt using {model}', model, 'earlier')
    rule(80, 'external_translation', 'Credited Brady delivery: exact lemma link, unverified Greek input', delivery=1)
    for i, model in enumerate(MINI_MODELS):
        rule(90+i*2, 'translation_run', f'Gabe v3 using {model}', model, 'gabe_v3')
        rule(91+i*2, 'translation_run', f'Earlier scholarly prompt using {model}', model, 'earlier')
    cur.execute("""SELECT md5(pv.prompt_text) FROM translation_prompt_profiles p
                   JOIN translation_prompt_profile_versions pv ON pv.profile_id=p.id
                   WHERE p.name='gpt-5.5' AND pv.version=3""")
    gabe_hash = cur.fetchone()[0]
    cur.execute("""SELECT pv.id, md5(pv.prompt_text), pv.uses_guidance_context
                   FROM translation_prompt_profiles p JOIN translation_prompt_profile_versions pv ON pv.profile_id=p.id
                   WHERE p.name = ANY(%s) AND p.style_kind='literal'""", (sorted(PROFILE_NAMES),))
    for version_id, prompt_hash, guided in cur.fetchall():
        recipe = 'gabe_v3' if guided and prompt_hash == gabe_hash else 'earlier'
        cur.execute('INSERT INTO translation_display_profile_recipes VALUES (%s,%s,%s,%s)',
                    (policy_id,version_id,recipe,prompt_hash))

    # A frozen allowance for already-approved humans; it does not relabel their unknown source.
    cur.execute("SELECT id,lemma_id FROM human_translations WHERE status='approved' AND stage IN ('reviewed','final') AND source_text_version_id IS NULL")
    for human_id, lemma_id in cur.fetchall():
        target = display.target_source(cur, lemma_id)
        if target:
            display.assess(cur, lemma_id=lemma_id, kind='human_translation', variant_id=human_id,
                           decision='allow', reviewer='migration:existing-approved-humans',
                           reason='Preserve existing approved human translation; exact source link remains unknown.',
                           target_source_version_id=target['id'], alignment_state='legacy_unlinked')
    cur.execute("""SELECT lemma_id,variant_kind,variant_id,updated_by FROM lemma_canonical_variants
        WHERE is_active AND variant_kind='human_translation' AND is_primary
          AND updated_by IN ('gabriel','greta','codex','codex_user_authorized_human_publication_2026-09-20')""")
    for lemma_id, kind, variant_id, reviewer in cur.fetchall():
        target = display.target_source(cur, lemma_id)
        cur.execute('SELECT source_text_version_id FROM human_translations WHERE id=%s', (int(variant_id),))
        unlinked = cur.fetchone()[0] is None
        display.assess(cur, lemma_id=lemma_id, kind=kind, variant_id=variant_id,
                       decision='prefer', reviewer=reviewer,
                       reason='Preserve explicit existing human canonical preference.',
                       target_source_version_id=target['id'] if target else None,
                       alignment_state='legacy_unlinked' if unlinked and target else 'unverified')
    display.clear_cache(cur)
    return policy_id


def audit(cur, policy_id):
    policy = display.load_policy(cur, policy_id)
    if not policy:
        raise RuntimeError(f'No display policy {policy_id}')
    cur.execute("SELECT id,lemma FROM assembled_lemmas WHERE NOT COALESCE(quarantined,false) ORDER BY id")
    lemmas = cur.fetchall()
    counts = Counter(); changes = []; lost = []; human_changes = []; selected = []
    for lemma_id, headword in lemmas:
        old_list = canonical_variants.select_presented_variants_legacy(cur, lemma_id=lemma_id, ux_mode='single')
        old = old_list[0] if old_list else None
        result = display.explain(cur, lemma_id=lemma_id, policy=policy)
        new = result['selected']
        counts[(new['kind']+':'+(new.get('model') or '')) if new else 'none'] += 1
        record = {'lemma_id':lemma_id,'lemma':headword,'old':compact(old),'new':compact(new)}
        selected.append(record)
        if compact(old) != compact(new):
            identity_changed = (old or {}).get('kind') != (new or {}).get('kind') or str((old or {}).get('id')) != str((new or {}).get('id'))
            if identity_changed:
                record['excluded'] = result['excluded']; changes.append(record)
                if old and not new: lost.append(record)
                if old and old['kind']=='human_translation': human_changes.append(record)
    return {'generated_at':datetime.now(timezone.utc).isoformat(),'policy_id':policy_id,
            'counts':dict(counts),'lemmas':len(lemmas),'changed':len(changes),
            'lost':lost,'human_changes':human_changes,'changes':changes,'selections':selected}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['seed','audit','activate','deactivate','explain','assess'])
    parser.add_argument('--policy-id', type=int)
    parser.add_argument('--lemma-id', type=int)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--apply', action='store_true', help='Commit seed/activation/assessment; otherwise roll back')
    parser.add_argument('--kind', choices=list(display.ASSESSMENT_COLUMNS))
    parser.add_argument('--variant-id', type=int)
    parser.add_argument('--decision', choices=['allow','endorse','prefer','exclude'])
    parser.add_argument('--reviewer')
    parser.add_argument('--reason')
    parser.add_argument('--target-source-id', type=int)
    parser.add_argument('--alignment', choices=['unverified','confirmed','legacy_unlinked'], default='unverified')
    args = parser.parse_args()
    from db import get_connection
    with get_connection() as conn:
        if args.command in ('audit','explain'):
            conn.set_session(readonly=True)
        cur=conn.cursor()
        if args.command == 'seed':
            result={'policy_id':seed(cur), 'committed':args.apply}
        elif args.command in ('audit','activate'):
            if not args.policy_id:parser.error('--policy-id required')
            result=audit(cur,args.policy_id)
            if args.command=='activate':
                if result['lost'] or result['human_changes']:
                    raise RuntimeError('Activation refused: review translations lost or changed human selections in the audit first.')
                cur.execute("UPDATE translation_display_policies SET state='retired' WHERE purpose='scholarly' AND state='active'")
                cur.execute("UPDATE translation_display_policies SET state='active',activated_at=now() WHERE id=%s",(args.policy_id,))
        elif args.command=='deactivate':
            cur.execute("UPDATE translation_display_policies SET state='retired' WHERE purpose='scholarly' AND state='active'")
            result={'legacy_selection_restored':args.apply}
        elif args.command=='assess':
            if not all((args.lemma_id,args.kind,args.variant_id,args.decision,args.reviewer,args.reason)):
                parser.error('assess requires lemma/kind/variant/decision/reviewer/reason')
            candidates = display.fetch_candidates(cur, args.lemma_id)
            candidate = next((c for c in candidates if c['kind'] == args.kind and c['id'] == args.variant_id), None)
            if not candidate: raise ValueError('Candidate does not belong to this lemma')
            old = candidate.get('assessment') or {}
            target = display.target_source(cur, args.lemma_id)
            source_id = args.target_source_id or old.get('target_source_version_id') or (target['id'] if target else None)
            alignment = args.alignment if args.target_source_id else old.get('alignment_state', args.alignment)
            result={'assessment_id':display.assess(cur,lemma_id=args.lemma_id,kind=args.kind,
                variant_id=args.variant_id,decision=args.decision,reviewer=args.reviewer,reason=args.reason,
                target_source_version_id=source_id,alignment_state=alignment)}
            if args.decision in ('prefer','endorse'):
                choice = canonical_variants.resolve_variant(cur, lemma_id=args.lemma_id, variant_kind=args.kind, variant_id=str(args.variant_id))
                if not choice.get('publishable'):
                    raise ValueError(choice.get('block_reason', 'Candidate is not eligible'))

        else:
            if not args.lemma_id:parser.error('--lemma-id required')
            result=display.explain(cur,lemma_id=args.lemma_id,policy=display.load_policy(cur,args.policy_id))
        if args.output:
            args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str)+'\n')
        if args.command in ('audit','activate'):
            print(json.dumps({k:v for k,v in result.items() if k not in ('changes','selections','lost','human_changes')},ensure_ascii=False))
            print(f"Lost: {len(result['lost'])}; changed humans: {len(result['human_changes'])}")
        else:
            print(json.dumps(result,ensure_ascii=False,indent=2,default=str))
        if not args.apply:
            conn.rollback()


if __name__=='__main__':
    main()
