"""Versioned public translation selection, independent of generation/review status."""
from __future__ import annotations

import time

_POLICIES: dict = {}
ASSESSMENT_COLUMNS = {
    'translation_run': 'translation_run_id',
    'human_translation': 'human_translation_id',
    'external_translation': 'external_translation_entry_id',
}


def clear_cache(cur=None):
    if cur is None:
        _POLICIES.clear()
    else:
        _POLICIES.pop(getattr(cur, 'connection', cur), None)


def rows_as_dicts(cur):
    names = [col[0] for col in cur.description]
    return [dict(zip(names, row)) for row in cur.fetchall()]


def load_policy(cur, policy_id=None):
    connection = getattr(cur, 'connection', cur)
    cached = _POLICIES.get(connection)
    if policy_id is None and cached and time.monotonic() - cached[0] < 30:
        return cached[1]
    cur.execute("SELECT to_regclass('public.translation_display_policies') IS NOT NULL")
    if not cur.fetchone()[0]:
        policy = None
    else:
        condition = 'id = %s' if policy_id is not None else "state = 'active' AND purpose = 'scholarly'"
        cur.execute(f'SELECT * FROM translation_display_policies WHERE {condition}', (policy_id,) if policy_id is not None else ())
        rows = rows_as_dicts(cur)
        policy = rows[0] if rows else None
        if policy:
            cur.execute('SELECT * FROM translation_display_preferences WHERE policy_id = %s ORDER BY rank', (policy['id'],))
            policy['rules'] = rows_as_dicts(cur)
            cur.execute('SELECT * FROM translation_display_profile_recipes WHERE policy_id = %s', (policy['id'],))
            policy['recipes'] = {row['profile_version_id']: row for row in rows_as_dicts(cur)}
    if policy_id is None:
        if len(_POLICIES) > 8:
            _POLICIES.clear()
        _POLICIES[connection] = (time.monotonic(), policy)
    return policy


def target_source(cur, lemma_id):
    from source_documents import source_document_priority_sql, public_source_document_list_sql
    cur.execute(f"""
        SELECT s.id, s.lemma_id, s.source_document, s.text_hash, s.text_body
        FROM lemma_source_text_versions s JOIN assembled_lemmas a ON a.id = s.lemma_id
        WHERE s.lemma_id = %s AND s.is_current AND s.is_public_greek
          AND s.source_document IN ({public_source_document_list_sql()})
          AND NOT COALESCE(a.quarantined, false) AND btrim(s.text_body) <> ''
        ORDER BY {source_document_priority_sql('s.source_document')}, s.id DESC LIMIT 1
    """, (lemma_id,))
    rows = rows_as_dicts(cur)
    return rows[0] if rows else None


def fetch_candidates(cur, lemma_id):
    cur.execute("""
        SELECT c.*, s.source_document, s.text_hash AS source_hash,
               COALESCE(f.state, '') AS guidance_freshness_state,
               EXISTS (SELECT 1 FROM translation_risk_flags r WHERE r.lemma_id = c.lemma_id
                       AND r.variant_kind = c.kind AND r.variant_id = c.id::text AND r.is_blocked) AS risk_blocked,
               EXISTS (SELECT 1 FROM scholarly_translation_revision_requests rr
                       WHERE c.kind = 'translation_run' AND rr.translation_run_id = c.id
                         AND rr.status_code IN ('pending', 'queued')) AS revision_pending
        FROM translation_display_candidates c
        LEFT JOIN lemma_source_text_versions s ON s.id = c.source_text_version_id
        LEFT JOIN translation_guidance_freshness f ON c.kind = 'translation_run' AND f.run_id = c.id
        WHERE c.lemma_id = %s ORDER BY c.kind, c.id
    """, (lemma_id,))
    candidates = rows_as_dicts(cur)
    cur.execute("""
        SELECT a.*, s.source_document AS target_document, s.text_hash AS target_hash
        FROM translation_display_assessments a
        LEFT JOIN lemma_source_text_versions s ON s.id = a.target_source_version_id
        WHERE a.lemma_id = %s AND a.purpose = 'scholarly' AND a.is_current
    """, (lemma_id,))
    assessments = {}
    for assessment in rows_as_dicts(cur):
        for kind, column in ASSESSMENT_COLUMNS.items():
            if assessment[column] is not None:
                assessments[(kind, assessment[column])] = assessment
    for candidate in candidates:
        candidate['assessment'] = assessments.get((candidate['kind'], candidate['id']), {})
    return candidates


def attribution(candidate):
    kind = candidate['kind']
    if kind == 'human_translation':
        return 'Human translation — ' + candidate.get('stage', 'reviewed')
    if kind == 'external_translation':
        provenance = candidate.get('provenance') or {}
        credit = provenance.get('source_credit') or 'Brady Kiesling'
        if candidate.get('cohort') == 'reused_project_marker':
            origin = 'reported reuse of an earlier Stephanos project translation'
        else:
            origin = 'reported Claude Fable 5.5 translation'
        return (f'External translation supplied by Brady Kiesling; {origin}. '
                f'Credit: {credit}. Not individually verified; exact Greek input not supplied.')
    recipe = 'Gabe v3' if candidate.get('recipe_key') == 'gabe_v3' else 'earlier prompt'
    return f"AI translation — {candidate.get('model', '')}; {recipe}"


def evaluate_candidate(candidate, target, policy):
    """Pure eligibility/ranking function; an editorial preference never clears a block."""
    c = dict(candidate)
    c.update(exists=True, id=str(c['id']), publishable=False)
    assessment = c.get('assessment') or {}
    decision = assessment.get('decision', '')

    def reject(reason):
        c['block_reason'] = reason
        return c

    if not target:
        return reject('No current public Greek source for this lemma')
    if decision == 'exclude':
        return reject('Editorial exclusion: ' + assessment.get('reason', ''))
    if not (c.get('translation_text') or '').strip():
        return reject('Empty translation')
    if c.get('risk_blocked'):
        return reject('Translation blocked by source/risk review')
    if c.get('revision_pending'):
        return reject('Unresolved scholarly revision request for this translation')
    kind = c['kind']
    if kind in ('translation_run', 'human_translation') and c.get('status') != 'approved':
        return reject('Translation status is ' + str(c.get('status')))
    if c.get('public_eligible') is False or c.get('public_block_reason'):
        return reject(c.get('public_block_reason') or 'Translation is excluded from public use')
    if kind == 'human_translation' and c.get('stage') not in ('reviewed', 'final'):
        return reject('Human translation has not reached reviewed/final stage')
    c['recipe_key'] = None
    if kind == 'translation_run':
        recipe = policy['recipes'].get(c.get('profile_version_id'))
        if not recipe or recipe['prompt_md5'] != c.get('prompt_md5'):
            return reject('Prompt/profile is not registered for scholarly default display')
        c['recipe_key'] = recipe['recipe_key']
        freshness = c.get('guidance_freshness_state')
        if freshness in ('potentially_outdated', 'outdated', 'needs_review'):
            return reject('Guidance freshness is ' + freshness)
        if c['recipe_key'] == 'gabe_v3' and (not c.get('uses_guidance_context') or freshness != 'current'):
            return reject('Gabe v3 guidance coverage has not been verified')

    assessment_matches = (assessment.get('target_document') == target['source_document']
                          and assessment.get('target_hash') == target['text_hash'])
    aligned = (c.get('source_document') == target['source_document']
               and c.get('source_hash') == target['text_hash'])
    if aligned:
        alignment = 'exact' if c.get('source_text_version_id') == target['id'] else 'equivalent_text'
    elif assessment_matches and assessment.get('alignment_state') == 'confirmed':
        alignment = 'editor_confirmed'
    elif (kind == 'human_translation' and c.get('source_text_version_id') is None
          and assessment_matches and assessment.get('alignment_state') == 'legacy_unlinked'):
        alignment = 'legacy_reviewed_source_unlinked'
    elif (kind == 'external_translation' and c.get('match_status') in ('exact_meineke', 'exact_meineke_and_billerbeck')
          and target['source_document'] == 'meineke'):
        alignment = 'external_input_unverified'
    else:
        return reject('Translation source is not aligned with the displayed Greek')
    if kind == 'external_translation' and c.get('status') != 'not_individually_verified':
        return reject('Unrecognized external review status')

    rules = [r for r in policy['rules'] if r['candidate_class'] == kind
             and (r.get('model_name') is None or r['model_name'] == c.get('model'))
             and (r.get('recipe_key') is None or r['recipe_key'] == c['recipe_key'])
             and (r.get('delivery_id') is None or r['delivery_id'] == c.get('delivery_id'))
             and (alignment != 'external_input_unverified' or r['source_requirement'] == 'external_unverified')]
    if not rules:
        return reject('No display preference rule permits this model/recipe/delivery')
    rule = min(rules, key=lambda r: r['rank'])
    # An endorsement scoped to a source must be rechecked after a material source change.
    editorial = decision in ('prefer', 'endorse') and (assessment_matches or assessment.get('target_source_version_id') is None)
    rank = (0 if decision == 'prefer' else 1) if editorial else rule['rank']
    stage_rank = 0 if c.get('stage') == 'final' else 1
    baseline = (policy.get('baseline_choices') or {}).get(str(c['lemma_id'])) or {}
    baseline_tie = 0 if (baseline.get('kind'), str(baseline.get('id'))) == (kind, c['id']) else 1
    c.update(publishable=True, block_reason='', alignment=alignment,
             is_primary=True, display_rank=rank,
             sort_key=(rank, stage_rank if kind == 'human_translation' else 0, baseline_tie, int(c['id']), kind),
             display_policy_id=policy['id'], display_policy_version=policy['version'],
             display_reason=(f"Editorial {decision}: {assessment.get('reason')}" if editorial else rule['label']),
             source_text_version_id=str(c.get('source_text_version_id') or ''),
             display_target_source_id=str(target['id']))
    c['display_attribution'] = attribution(c)
    return c


def explain(cur, *, lemma_id, policy=None):
    policy = policy or load_policy(cur)
    if not policy:
        return None
    target = target_source(cur, lemma_id)
    evaluated = [evaluate_candidate(c, target, policy) for c in fetch_candidates(cur, lemma_id)]
    eligible = sorted((c for c in evaluated if c['publishable']), key=lambda c: c['sort_key'])
    return {'lemma_id': lemma_id, 'policy_id': policy['id'], 'policy_version': policy['version'],
            'selected': eligible[0] if eligible else None, 'eligible': eligible,
            'excluded': [{'kind': c['kind'], 'id': c['id'], 'reason': c['block_reason']}
                         for c in evaluated if not c['publishable']]}


def presented(cur, *, lemma_id, ux_mode='single', policy=None):
    result = explain(cur, lemma_id=lemma_id, policy=policy)
    if result is None:
        return None  # Distinct from an active policy choosing no translation.
    if not result['selected']:
        return []
    chosen = result['selected']
    if ux_mode == 'single':
        return [chosen]
    return [chosen, *[dict(c, is_primary=False) for c in result['eligible'][1:] if c['display_rank'] <= 1]]


def assess(cur, *, lemma_id, kind, variant_id, decision, reviewer, reason,
           target_source_version_id=None, alignment_state='unverified'):
    """Record an explicit editorial action with history; caller owns the transaction."""
    column = ASSESSMENT_COLUMNS[kind]
    cur.execute('SELECT id FROM assembled_lemmas WHERE id = %s FOR UPDATE', (lemma_id,))
    cur.execute(f"SELECT id FROM translation_display_assessments WHERE {column} = %s AND purpose = 'scholarly' AND is_current", (int(variant_id),))
    row = cur.fetchone()
    supersedes = row[0] if row else None
    cur.execute(f"UPDATE translation_display_assessments SET is_current = false WHERE {column} = %s AND purpose = 'scholarly' AND is_current", (int(variant_id),))
    if decision == 'prefer':
        # Former preferred candidates remain endorsed; preserve their alignment evidence.
        cur.execute("SELECT * FROM translation_display_assessments WHERE lemma_id = %s AND purpose = 'scholarly' AND is_current AND decision = 'prefer'", (lemma_id,))
        for old in rows_as_dicts(cur):
            old_kind = next(k for k, col in ASSESSMENT_COLUMNS.items() if old[col] is not None)
            assess(cur, lemma_id=lemma_id, kind=old_kind, variant_id=old[ASSESSMENT_COLUMNS[old_kind]],
                   decision='endorse', reviewer=reviewer, reason='Superseded preference: ' + reason,
                   target_source_version_id=old['target_source_version_id'], alignment_state=old['alignment_state'])
    cur.execute(f"""
        INSERT INTO translation_display_assessments
            (lemma_id, {column}, decision, reviewer, reason, target_source_version_id, alignment_state, supersedes_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
    """, (lemma_id, int(variant_id), decision, reviewer, reason, target_source_version_id, alignment_state, supersedes))
    clear_cache(cur)
    return cur.fetchone()[0]


def editorial_action(cur, *, lemma_id, action, kind='', variant_id='', reviewer, reason=''):
    """Apply review UI actions to the active display policy; return False for legacy mode."""
    policy = load_policy(cur)
    if not policy:
        return False
    candidates = fetch_candidates(cur, lemma_id)
    target = target_source(cur, lemma_id)
    selected = [c for c in candidates if c['kind'] == kind and str(c['id']) == str(variant_id)]
    if action in ('add', 'set_primary'):
        if not selected or not evaluate_candidate(selected[0], target, policy)['publishable']:
            raise ValueError('Candidate is not eligible under the active display policy')
    elif action == 'clear_primary':
        selected = [c for c in candidates if c['assessment'].get('decision') == 'prefer']
    elif action == 'clear_all':
        selected = [c for c in candidates if evaluate_candidate(c, target, policy)['publishable']]
    elif action != 'remove':
        raise ValueError('Unknown editorial action: ' + action)
    decision = {'add':'endorse', 'set_primary':'prefer', 'remove':'exclude',
                'clear_primary':'endorse', 'clear_all':'exclude'}[action]
    for c in selected:
        old = c.get('assessment') or {}
        assess(cur, lemma_id=lemma_id, kind=c['kind'], variant_id=c['id'], decision=decision,
               reviewer=reviewer, reason=reason or ('Review action: ' + action),
               target_source_version_id=old.get('target_source_version_id') or (target['id'] if target else None),
               alignment_state=old.get('alignment_state', 'unverified'))
    return True
