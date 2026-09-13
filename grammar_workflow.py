#!/usr/bin/env python3
"""Relational grammar storage, immutable human revisions and review snapshots.

JSON is accepted as a transport file only; no new parse JSON is stored in SQL.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sqlite3
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from psycopg2.extras import RealDictCursor

CONFIDENCES = {'high', 'medium', 'low', 'manual', 'unknown'}
UPOS = set('ADJ ADP ADV AUX CCONJ DET INTJ NOUN NUM PART PRON PROPN PUNCT SCONJ SYM VERB X'.split())
FEATURE_NAME = re.compile(r'^[A-Za-z][A-Za-z0-9_]*$')
PUNCTUATION = ',.;··:!?“”„"«»()[]{}'


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def clean(text):
    return unicodedata.normalize('NFC', ' '.join(text.split()))


def word_forms(text):
    return [form for word in clean(text).split() if (form := word.strip(PUNCTUATION))]


def parse_features(raw):
    if not raw or raw == '_':
        return {}
    result = {}
    for pair in raw.split('|'):
        name, separator, value = pair.partition('=')
        if not separator or not FEATURE_NAME.fullmatch(name) or not value or name in result:
            raise ValueError('Features must be unique Name=Value pairs separated by |')
        result[name] = value
    return result


def normalize_tokens(tokens):
    result = []
    for index, source in enumerate(tokens, 1):
        token = dict(source)
        token['id'] = str(token.get('id', token.get('token_id', index)))
        token['head'] = str(token.get('head', token.get('head_token_id', '')))
        token['feats'] = token.get('feats') or parse_features(token.get('feats_raw', ''))
        for key in ('form', 'lemma', 'upos', 'xpos', 'deprel', 'note'):
            token[key] = str(token.get(key) or '')
        token['role'] = token.get('role', token.get('grammatical_role', '')) or ''
        token['confidence'] = token.get('confidence') or 'unknown'
        result.append(token)
    return result


def validate_parse(text, tokens):
    tokens = normalize_tokens(tokens)
    if [clean(t['form']) for t in tokens] != word_forms(text):
        raise ValueError('Word tokens must cover the source text in order without changes or omissions')
    ids = [t['id'] for t in tokens]
    if ids != [str(i) for i in range(1, len(tokens) + 1)]:
        raise ValueError('Token IDs must be consecutive integers starting at 1')
    if sum(t['head'] == '0' for t in tokens) != 1:
        raise ValueError('A parse must have exactly one root')
    heads = {t['id']: t['head'] for t in tokens}
    for t in tokens:
        if not t['lemma'].strip() or t['upos'] not in UPOS or not t['deprel'].strip():
            raise ValueError('Every token needs a lemma, recognised part of speech and dependency relation')
        if t['confidence'] not in CONFIDENCES:
            raise ValueError('Invalid confidence')
        if (t['head'] == '0') != (t['deprel'] == 'root'):
            raise ValueError('Only the root token may have head 0 and relation root')
        if not isinstance(t['feats'], dict):
            raise ValueError('Morphology must be feature/value pairs')
        for key, value in t['feats'].items():
            if not FEATURE_NAME.fullmatch(key) or not str(value) or any(x in str(value) for x in '|\n\t'):
                raise ValueError('Invalid morphology feature')
        visited = set()
        node = t['id']
        while node != '0':
            if node in visited or node not in heads:
                raise ValueError('Dependency heads must exist and form an acyclic tree')
            visited.add(node)
            node = heads[node]
    return tokens


def register_model(cur, provider, model, observed_at=None, display_name=None):
    observed_at = observed_at or datetime.now(timezone.utc)
    cur.execute('''INSERT INTO grammar_models(provider,model_slug,display_name,model_release_id,first_observed_at)
        VALUES (%s,%s,%s,(SELECT id FROM llm_model_releases WHERE provider=%s AND model_slug=%s),%s)
        ON CONFLICT(provider,model_slug) DO UPDATE SET
            first_observed_at=LEAST(grammar_models.first_observed_at,EXCLUDED.first_observed_at),
            model_release_id=COALESCE(EXCLUDED.model_release_id,grammar_models.model_release_id)
        RETURNING id''', (provider, model, display_name or model, provider, model, observed_at))
    return cur.fetchone()['id']


def create_run(cur, key, model, *, provider='openai', manual=False, actor='', notes='', observed_at=None, prompt_version='grammar_worked_v1'):
    model_id = None if manual else register_model(cur, provider, model, observed_at)
    cur.execute('''INSERT INTO sentence_grammar_runs
        (run_id,parser_kind,model,grammar_model_id,prompt_version,parser_version,annotation_scheme,status,created_by,notes,started_at,completed_at)
        VALUES (%s,%s,%s,%s,%s,'grammar_workflow.py:v1','Greek morphology / UD-like','completed',%s,%s,COALESCE(%s,now()),now())
        ON CONFLICT(run_id) DO NOTHING RETURNING id''',
        (key, 'manual' if manual else 'llm', model, model_id, prompt_version, actor, notes, observed_at))
    row = cur.fetchone()
    if row:
        return row['id']
    cur.execute('SELECT id,model,parser_kind,prompt_version FROM sentence_grammar_runs WHERE run_id=%s', (key,))
    existing = cur.fetchone()
    if (existing['model'], existing['parser_kind'], existing['prompt_version']) != (model, 'manual' if manual else 'llm', prompt_version):
        raise ValueError('Existing run key has different model or prompt metadata; use a new run key')
    return existing['id']


def store_analysis(cur, *, sentence_id, run_id, payload, key=None, parent_id=None,
                   variant_number=1, variant_label='', manual=False, usage=None,
                   attempt_number=1, attempt_kind='initial'):
    cur.execute('SELECT text FROM lemma_sentences WHERE id=%s FOR SHARE', (sentence_id,))
    source = cur.fetchone()
    if not source:
        raise ValueError('Unknown grammar passage')
    tokens = validate_parse(source['text'], payload['tokens'])
    if key:
        cur.execute('SELECT id,sentence_id,sentence_note,title,literal_translation FROM sentence_grammar_analyses WHERE analysis_key=%s', (key,))
        previous = cur.fetchone()
        if previous:
            old_tokens = normalize_tokens(load_tokens(cur, previous['id']))
            fields = ('id','form','lemma','upos','xpos','head','deprel','feats','role','note','confidence')
            same_tokens = [{k:t[k] for k in fields} for t in old_tokens] == [{k:t[k] for k in fields} for t in tokens]
            if previous['sentence_id'] != sentence_id or not same_tokens or any(previous[k] != payload.get(k,'') for k in ('sentence_note','title','literal_translation')):
                raise ValueError('Existing parse key contains different content; use a new run key or variant')
            return previous['id']
    usage = usage or {}
    cur.execute('''INSERT INTO sentence_grammar_analyses
        (sentence_id,grammar_run_id,analysis_key,parent_analysis_id,variant_number,variant_label,
         title,literal_translation,sentence_note,status,token_count,attempt_number,attempt_kind,input_tokens,output_tokens)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
        (sentence_id, run_id, key, parent_id, variant_number, variant_label,
         payload.get('title',''), payload.get('literal_translation',''), payload.get('sentence_note',''),
         'manual' if manual else 'completed', len(tokens), attempt_number, 'manual' if manual else attempt_kind,
         usage.get('input_tokens',0), usage.get('output_tokens',0)))
    analysis_id = cur.fetchone()['id']
    for order, t in enumerate(tokens, 1):
        cur.execute('''INSERT INTO sentence_grammar_tokens
            (analysis_id,token_order,token_id,form,lemma,upos,xpos,head_token_id,deprel,confidence,note,grammatical_role)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
            (analysis_id,order,t['id'],t['form'],t['lemma'],t['upos'],t['xpos'],t['head'],t['deprel'],t['confidence'],t['note'],t['role']))
        token_id = cur.fetchone()['id']
        for name, value in sorted(t['feats'].items()):
            cur.execute('INSERT INTO sentence_grammar_token_features VALUES (%s,%s,%s)', (token_id,name,str(value)))
    for kind, field in [('observation','observations'),('uncertainty','uncertainties'),('context','context_notes')]:
        for order, note in enumerate(payload.get(field, []), 1):
            cur.execute('INSERT INTO sentence_grammar_notes(analysis_id,note_kind,note_order,note_text) VALUES (%s,%s,%s,%s)',
                        (analysis_id,kind,order,str(note)))
    for order, ref in enumerate(payload.get('references', []), 1):
        if not str(ref.get('url','')).startswith(('https://','http://')):
            raise ValueError('Reference links must be HTTP or HTTPS')
        cur.execute('INSERT INTO sentence_grammar_notes(analysis_id,note_kind,note_order,note_text,reference_url) VALUES (%s,%s,%s,%s,%s)',
                    (analysis_id,'reference',order,ref['title'],ref['url']))
    cur.execute('UPDATE sentence_grammar_analyses SET structure_validated=TRUE WHERE id=%s', (analysis_id,))
    cur.execute('''UPDATE sentence_grammar_runs SET
        processed_count=(SELECT count(*) FROM sentence_grammar_analyses WHERE grammar_run_id=%s AND structure_validated),
        token_count=(SELECT COALESCE(sum(token_count),0) FROM sentence_grammar_analyses WHERE grammar_run_id=%s AND structure_validated)
        WHERE id=%s''', (run_id,run_id,run_id))
    return analysis_id


def source_span(source, excerpt):
    words = list(re.finditer(r'\S+', source))
    needle = clean(excerpt).split()
    candidates = []
    for start in range(len(words) - len(needle) + 1):
        segment = words[start:start+len(needle)]
        if [unicodedata.normalize('NFC', m.group()) for m in segment] == needle:
            candidates.append((segment[0].start(), segment[-1].end()))
    if len(candidates) != 1:
        raise ValueError('Excerpt must match one unambiguous span in its source version')
    return candidates[0]


def ensure_passage(cur, lemma_id, excerpt):
    cur.execute('''SELECT id,text_body FROM lemma_source_text_versions
        WHERE lemma_id=%s AND is_current AND is_public_greek
        ORDER BY CASE source_document WHEN 'meineke' THEN 0 ELSE 1 END,id DESC''', (lemma_id,))
    for source in cur.fetchall():
        try:
            start,end = source_span(source['text_body'],excerpt)
        except ValueError:
            continue
        source_id = source['id']
        break
    else:
        raise ValueError(f'No matching current public Greek source for lemma {lemma_id}')
    # The excerpt hash is part of segmentation_version so multiple bounded
    # passages in the same entry never overwrite one another.
    version = 'selected-v1:' + digest(clean(excerpt))
    cur.execute('''INSERT INTO lemma_sentence_sets
        (lemma_id,text_kind,source_text_version_id,segmentation_method,segmentation_model,
         segmentation_version,text_sha256,sentence_count,created_by,notes)
        VALUES (%s,'source_greek',%s,'selected_passage','human_selection',%s,%s,1,'grammar_workflow.py',
        'Selected continuous source span; sentence.text uses NFC and collapsed whitespace; offsets refer to original source text.')
        ON CONFLICT DO NOTHING RETURNING id''', (lemma_id,source_id,version,digest(source['text_body'])))
    row=cur.fetchone()
    if row:
        set_id=row['id']
    else:
        cur.execute('SELECT id FROM lemma_sentence_sets WHERE lemma_id=%s AND source_text_version_id=%s AND segmentation_version=%s', (lemma_id,source_id,version))
        set_id=cur.fetchone()['id']
    cur.execute('''INSERT INTO lemma_sentences(sentence_set_id,sentence_number,text,char_start,char_end,token_count,text_sha256)
        VALUES (%s,1,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING id''',
        (set_id,clean(excerpt),start,end,len(word_forms(excerpt)),digest(clean(excerpt))))
    row=cur.fetchone()
    if row:
        return row['id']
    cur.execute('SELECT id,text FROM lemma_sentences WHERE sentence_set_id=%s AND sentence_number=1', (set_id,))
    row=cur.fetchone()
    if row['text'] != clean(excerpt):
        raise ValueError('Existing passage text differs; create a new source version')
    return row['id']


def import_pilot(cur, path, model, provider):
    raw=path.read_text()
    payload=json.loads(raw)
    file_hash=digest(raw)
    run_id=create_run(cur,'golden-100-pilot:'+file_hash,model,provider=provider,
        actor=payload.get('author','Codex'), notes=payload.get('evaluation_note',''),
        observed_at=datetime.now(timezone.utc))
    if model == 'codex-gpt-6':
        cur.execute("UPDATE grammar_models SET display_name='Codex (GPT-6)', notes='Current Codex task, identified as GPT-6 by its system context. Exact model variant and release date were not recorded; first_observed_at is the import time.' WHERE provider=%s AND model_slug=%s", (provider,model))
    for order,note in enumerate(payload.get('conventions',[]),1):
        cur.execute('INSERT INTO sentence_grammar_run_notes VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING', (run_id,order,'convention',note))
    results=[]
    for p in payload['passages']:
        membership=p['source']['database_membership']
        cur.execute('SELECT a.id,r.greek_text FROM assembled_lemmas a JOIN kappa_review_rows r ON r.id=%s WHERE a.id=%s AND a.entry_number=r.source_row_id',
                    (membership['kappa_review_row_id'],membership['lemma_id']))
        row=cur.fetchone()
        if not row or clean(p['text']) not in clean(row['greek_text']):
            raise ValueError('Pilot provenance does not match the database review row')
        sid=ensure_passage(cur,membership['lemma_id'],p['text'])
        variants=[('Primary analysis',p)]
        for alternative in p.get('alternative_dependencies',[]):
            variant=copy.deepcopy(p)
            for change in alternative['changes']:
                t=next(t for t in variant['tokens'] if t['id']==change['token_id'])
                t.update(head=change['head'],deprel=change['deprel'])
                t['note']='Alternative attachment: '+alternative['description']
            variant['context_notes']=[alternative['description']]
            variants.append((alternative['description'],variant))
        parent_id=None
        for number,(label,variant) in enumerate(variants,1):
            key=f'pilot:{file_hash}:{p["entry_number"]}:{number}'
            aid=store_analysis(cur,sentence_id=sid,run_id=run_id,payload=variant,key=key,
                               variant_number=number,variant_label=label,parent_id=parent_id)
            parent_id=parent_id or aid
            cur.execute('''INSERT INTO sentence_grammar_import_sources
                (analysis_id,file_path,file_sha256,source_file_path,source_file_sha256,kappa_review_row_id,source_jsonl_line,excerpt_sha256)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING''',
                (aid,str(path),file_hash,payload['source_file'],payload['source_sha256'],membership['kappa_review_row_id'],p['source']['jsonl_line'],digest(p['text'])))
            results.append((sid,aid,number))
    return results


def load_tokens(cur, analysis_id):
    cur.execute('''SELECT token_id AS id,form,lemma,upos,xpos,head_token_id AS head,deprel,confidence,note,grammatical_role AS role,
        id AS row_id FROM sentence_grammar_tokens WHERE analysis_id=%s ORDER BY token_order''', (analysis_id,))
    tokens=[dict(r) for r in cur.fetchall()]
    for t in tokens:
        cur.execute('SELECT feature_name,feature_value FROM sentence_grammar_token_features WHERE token_row_id=%s ORDER BY feature_name', (t.pop('row_id'),))
        t['feats']={r['feature_name']:r['feature_value'] for r in cur.fetchall()}
    return tokens


def backfill_validation(cur):
    cur.execute('SELECT id,passage_text FROM grammar_analysis_catalog WHERE NOT structure_validated AND status IN (\'completed\',\'manual\')')
    rows=cur.fetchall(); valid=0
    for row in rows:
        try:
            validate_parse(row['passage_text'],load_tokens(cur,row['id']))
        except ValueError:
            continue
        cur.execute('UPDATE sentence_grammar_analyses SET structure_validated=TRUE WHERE id=%s', (row['id'],))
        valid+=1
    return valid,len(rows)-valid


def import_review_actions(cur, path):
    if not path.exists():
        raise FileNotFoundError(path)
    cur.execute("SELECT pg_advisory_xact_lock(hashtext('grammar_review_import'))")
    with sqlite3.connect(f'file:{path}?mode=ro',uri=True) as edge:
        edge.row_factory=sqlite3.Row
        if not edge.execute("SELECT 1 FROM sqlite_master WHERE name='grammar_review_actions'").fetchone():
            return 0
        actions=edge.execute('SELECT * FROM grammar_review_actions ORDER BY id').fetchall()
        imported=0
        for action in actions:
            cur.execute('SELECT id FROM sentence_grammar_review_events WHERE event_key=%s', (action['event_key'],))
            if cur.fetchone():
                continue
            cur.execute('SELECT * FROM grammar_analysis_catalog WHERE analysis_key=%s', (action['target_key'],))
            parent=cur.fetchone()
            if not parent:
                raise ValueError(f'Unknown review target {action["target_key"]}; refresh snapshot before importing')
            if action['passage_sha256'] != digest(parent['passage_text']):
                raise ValueError('Review refers to a different source passage')
            aid=parent['id']
            if action['action'] in ('correct','bless'):
                tokens=[]
                for raw in edge.execute('SELECT * FROM grammar_review_action_tokens WHERE event_key=? ORDER BY token_order',(action['event_key'],)):
                    token=dict(raw)
                    token['id']=str(token['token_order'])
                    token['head']=token['head_token_id']
                    token['role']=token['grammatical_role']
                    token['feats']={f['feature_name']:f['feature_value'] for f in edge.execute('SELECT feature_name,feature_value FROM grammar_review_action_features WHERE event_key=? AND token_order=?',(action['event_key'],token['token_order']))}
                    tokens.append(token)
                run_id=create_run(cur,'human:'+action['event_key'],'human',manual=True,actor=action['reviewer'],notes=action['review_note'],observed_at=action['created_at'])
                cur.execute('SELECT note_kind,note_text,reference_url FROM sentence_grammar_notes WHERE analysis_id=%s ORDER BY note_kind,note_order',(aid,))
                notes=cur.fetchall()
                payload={'tokens':tokens,'sentence_note':action['sentence_note'],'title':parent['title'],'literal_translation':action['literal_translation'],
                         'observations':[], 'uncertainties':[], 'references':[], 'context_notes':[]}
                for n in notes:
                    if n['note_kind']=='reference': payload['references'].append({'title':n['note_text'],'url':n['reference_url']})
                    else: payload[{'observation':'observations','uncertainty':'uncertainties','context':'context_notes'}[n['note_kind']]].append(n['note_text'])
                aid=store_analysis(cur,sentence_id=parent['sentence_id'],run_id=run_id,payload=payload,
                    key='human:'+action['event_key'],parent_id=parent['id'],manual=True,variant_label='Human revision')
            decisions={'correct':'draft','bless':'blessed','reject':'rejected','restore':'unreviewed','unbless':'draft'}
            if action['action'] not in decisions:
                raise ValueError('Unknown grammar review action')
            cur.execute('''INSERT INTO sentence_grammar_review_events(event_key,analysis_id,decision,reviewer,review_note,reviewed_at)
                VALUES (%s,%s,%s,%s,%s,%s)''', (action['event_key'],aid,decisions[action['action']],action['reviewer'],action['review_note'],action['created_at']))
            for issue in edge.execute('SELECT token_id,issue_text FROM grammar_review_action_issues WHERE event_key=?',(action['event_key'],)):
                cur.execute('''INSERT INTO sentence_grammar_feedback_items(sentence_id,analysis_id,target_token_id,feedback_source,issue_text,created_by)
                    VALUES (%s,%s,%s,'human',%s,%s)''', (parent['sentence_id'],parent['id'],issue['token_id'],issue['issue_text'],action['reviewer']))
            imported+=1
        return imported


def export_snapshot(cur, path):
    """Export typed tables atomically; never replace the separate action journal."""
    queries={
        'grammar_analyses':'SELECT * FROM grammar_analysis_catalog ORDER BY lemma_id,sentence_id,id',
        'grammar_tokens':'''SELECT analysis_id,token_order,token_id,form,COALESCE(lemma,'') AS lemma,COALESCE(upos,'') AS upos,
            COALESCE(xpos,'') AS xpos,COALESCE(head_token_id,'') AS head_token_id,COALESCE(deprel,'') AS deprel,
            confidence,note,grammatical_role,id AS row_id FROM sentence_grammar_tokens ORDER BY analysis_id,token_order''',
        'grammar_features':'SELECT token_row_id,feature_name,feature_value FROM sentence_grammar_token_features',
        'grammar_notes':'SELECT analysis_id,note_kind,note_order,note_text,reference_url FROM sentence_grammar_notes',
        'grammar_imported_events':'''SELECT e.event_key,a.analysis_key FROM sentence_grammar_review_events e
            JOIN sentence_grammar_analyses a ON a.id=e.analysis_id''',
    }
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.new')
    temporary.unlink(missing_ok=True)
    with sqlite3.connect(temporary) as dest:
        for table,query in queries.items():
            cur.execute(query)
            columns=[d.name for d in cur.description]
            rows=cur.fetchall()
            integer_names={'id','analysis_id','sentence_id','lemma_id','source_text_version_id','parent_analysis_id','grammar_run_id','variant_number','attempt_number','token_order','row_id','token_row_id','note_order','structure_validated','is_public_greek','source_is_current','model_release_known'}
            dest.execute(f'CREATE TABLE {table} ('+', '.join(f'{c} '+('INTEGER' if c in integer_names else 'TEXT') for c in columns)+')')
            def value(v):
                if isinstance(v,bool): return int(v)
                if isinstance(v,datetime): return v.astimezone(timezone.utc).isoformat(timespec='microseconds')
                if hasattr(v,'isoformat'): return v.isoformat()
                return v
            dest.executemany(f'INSERT INTO {table} VALUES ('+','.join('?' for _ in columns)+')', ([value(row[c]) for c in columns] for row in rows))
        dest.executescript('''CREATE UNIQUE INDEX grammar_key_idx ON grammar_analyses(analysis_key);
            CREATE INDEX grammar_lemma_idx ON grammar_analyses(lemma_id,sentence_id);
            CREATE INDEX grammar_tokens_analysis_idx ON grammar_tokens(analysis_id,token_order);
            CREATE INDEX grammar_features_token_idx ON grammar_features(token_row_id);
            CREATE UNIQUE INDEX grammar_imported_events_key_idx ON grammar_imported_events(event_key);''')
        assert dest.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    temporary.replace(path)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('import-pilot'); p.add_argument('input',type=Path)
    p.add_argument('--model',required=True); p.add_argument('--provider',default='openai')
    p.add_argument('--dry-run',action='store_true')
    p=sub.add_parser('import-parse'); p.add_argument('input',type=Path)
    p.add_argument('--sentence-id',type=int,required=True); p.add_argument('--model',required=True)
    p.add_argument('--provider',default='openai'); p.add_argument('--run-key',required=True)
    p.add_argument('--variant-number',type=int,default=1); p.add_argument('--dry-run',action='store_true')
    p.add_argument('--prompt-version',default='external_import_v1')
    p=sub.add_parser('import-reviews'); p.add_argument('--input',type=Path,default=Path.home()/'stephanos/review_data/reviews.db')
    p.add_argument('--dry-run',action='store_true')
    p=sub.add_parser('export'); p.add_argument('--output',type=Path,default=Path('grammar_data.sqlite'))
    sub.add_parser('validate-legacy')
    args=parser.parse_args()
    from db import get_connection
    with get_connection(dict_cursor=True) as conn:
        if args.command=='export': conn.set_session(readonly=True,isolation_level='REPEATABLE READ')
        with conn.cursor() as cur:
            if args.command=='import-pilot': print(import_pilot(cur,args.input,args.model,args.provider))
            elif args.command=='import-parse':
                run_id=create_run(cur,args.run_key,args.model,provider=args.provider,prompt_version=args.prompt_version)
                payload=json.loads(args.input.read_text())
                print(store_analysis(cur,sentence_id=args.sentence_id,run_id=run_id,payload=payload,
                    key=f'{args.run_key}:{args.sentence_id}:{args.variant_number}',variant_number=args.variant_number))
            elif args.command=='import-reviews': print('Grammar review actions imported:',import_review_actions(cur,args.input))
            elif args.command=='validate-legacy': print('Validated / still require correction:',backfill_validation(cur))
            elif args.command=='export': export_snapshot(cur,args.output); print(args.output)
        if getattr(args,'dry_run',False): conn.rollback(); print('Dry run: transaction rolled back')

if __name__=='__main__':
    main()
