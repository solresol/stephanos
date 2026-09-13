"""Grammar regression tests; database fixtures always roll back."""
import copy
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from grammar_workflow import (
    create_run, digest, ensure_passage, export_snapshot, import_review_actions,
    load_tokens, parse_features, source_span, store_analysis, validate_parse,
)

PILOT = Path(__file__).parent/'paper/notes/2026-09-09-golden-100-grammar-pilot.json'


class GrammarValidationTests(unittest.TestCase):
    def setUp(self):
        self.p=json.loads(PILOT.read_text())['passages'][3]

    def test_pilot_and_alternative_cover_exact_source(self):
        for passage in json.loads(PILOT.read_text())['passages']:
            validate_parse(passage['text'],passage['tokens'])
            for alternative in passage.get('alternative_dependencies',[]):
                tokens=copy.deepcopy(passage['tokens'])
                for change in alternative['changes']:
                    tokens[int(change['token_id'])-1].update(head=change['head'],deprel=change['deprel'])
                validate_parse(passage['text'],tokens)

    def test_cycle_and_omission_rejected(self):
        tokens=copy.deepcopy(self.p['tokens']);tokens[2]['head']='4';tokens[3]['head']='3'
        with self.assertRaises(ValueError):validate_parse(self.p['text'],tokens)
        with self.assertRaises(ValueError):validate_parse(self.p['text'],self.p['tokens'][:-1])

    def test_duplicate_features_and_missing_heads_rejected(self):
        with self.assertRaises(ValueError):parse_features('Case=Acc|Case=Nom')
        tokens=copy.deepcopy(self.p['tokens']);tokens[3]['head']='999'
        with self.assertRaises(ValueError):validate_parse(self.p['text'],tokens)

    def test_source_span_retains_raw_offsets_and_normalises_unicode(self):
        source='before\n  τὸ  γένος.  after'
        start,end=source_span(source,'τὸ γένος.')
        self.assertEqual(source[start:end],'τὸ  γένος.')
        with self.assertRaises(ValueError):source_span('τὸ τὸ','τὸ')


@unittest.skipUnless(os.environ.get('GRAMMAR_DB_TEST')=='1','Set GRAMMAR_DB_TEST=1 for rollback-only integration tests')
class GrammarDatabaseTests(unittest.TestCase):
    def setUp(self):
        from db import get_connection
        self.conn=get_connection(dict_cursor=True);self.cur=self.conn.cursor()
        self.p=json.loads(PILOT.read_text())['passages'][3]
        self.prefix='test-grammar:'+uuid4().hex
        self.sid=self.isolated_passage()

    def isolated_passage(self):
        base=ensure_passage(self.cur,self.p['source']['database_membership']['lemma_id'],self.p['text'])
        self.cur.execute('SELECT ss.* FROM lemma_sentence_sets ss JOIN lemma_sentences s ON s.sentence_set_id=ss.id WHERE s.id=%s',(base,))
        row=self.cur.fetchone()
        self.cur.execute("INSERT INTO lemma_sentence_sets(lemma_id,text_kind,source_text_version_id,segmentation_method,segmentation_version,text_sha256,sentence_count) VALUES (%s,'source_greek',%s,'test_grammar',%s,%s,1) RETURNING id",(row['lemma_id'],row['source_text_version_id'],self.prefix,row['text_sha256']))
        set_id=self.cur.fetchone()['id']
        self.cur.execute('INSERT INTO lemma_sentences(sentence_set_id,sentence_number,text,token_count) VALUES (%s,1,%s,%s) RETURNING id',(set_id,self.p['text'],len(self.p['tokens'])))
        return self.cur.fetchone()['id']

    def tearDown(self):
        self.conn.rollback();self.cur.close();self.conn.close()

    def add(self,label,model='gpt-5.5',manual=False,when='2026-09-09T00:00:00Z',parent=None,variant=1,run=None):
        run=run or create_run(self.cur,self.prefix+label,model,manual=manual,actor='test reviewer',observed_at=when)
        aid=store_analysis(self.cur,sentence_id=self.sid,run_id=run,payload=self.p,key=self.prefix+label,parent_id=parent,manual=manual,variant_number=variant)
        return aid

    def select(self):
        self.cur.execute('SELECT id FROM effective_sentence_grammar WHERE sentence_id=%s',(self.sid,))
        row=self.cur.fetchone();return row['id'] if row else None

    def event(self,aid,decision):
        self.cur.execute('INSERT INTO sentence_grammar_review_events(event_key,analysis_id,decision,reviewer) VALUES (%s,%s,%s,%s)',(uuid4().hex,aid,decision,'test reviewer'))

    def test_release_order_then_latest_attempt_and_human_precedence(self):
        newer=self.add('newer',when='2026-09-09T00:00:00Z')
        old=self.add('old','gpt-5.4',when='2026-09-10T00:00:00Z')
        self.assertEqual(self.select(),newer)
        newest_attempt=self.add('newest',when='2026-09-11T00:00:00Z')
        self.assertEqual(self.select(),newest_attempt)
        self.event(newest_attempt,'rejected');self.assertEqual(self.select(),newer)
        human=self.add('human','human',manual=True,parent=newer,when='2026-09-01T00:00:00Z')
        self.assertEqual(self.select(),newer)
        self.event(human,'blessed');self.assertEqual(self.select(),human)
        self.event(human,'draft');self.assertEqual(self.select(),newer)
        self.event(newer,'rejected');self.assertEqual(self.select(),old)

    def test_alternatives_coexist_and_primary_is_default(self):
        run=create_run(self.cur,self.prefix+'variants','gpt-5.5',observed_at='2026-09-11T00:00:00Z')
        primary=self.add('primary',run=run)
        alternative=self.add('alternative',run=run,variant=2,parent=primary)
        self.assertEqual(self.select(),primary)
        self.event(primary,'rejected');self.assertEqual(self.select(),alternative)

    def test_human_blessing_and_parent_source_guard(self):
        machine=self.add('machine')
        with self.assertRaises(Exception):self.event(machine,'blessed')
        self.conn.rollback()
        self.sid=self.isolated_passage()
        second=json.loads(PILOT.read_text())['passages'][0]
        other=ensure_passage(self.cur,second['source']['database_membership']['lemma_id'],second['text'])
        machine=self.add('machine-again')
        run=create_run(self.cur,self.prefix+'cross','human',manual=True)
        with self.assertRaises(Exception):store_analysis(self.cur,sentence_id=other,run_id=run,payload=second,parent_id=machine,manual=True)

    def test_idempotent_key_cannot_hide_changed_content(self):
        aid=self.add('same')
        self.assertEqual(self.add('same'),aid)
        self.p['sentence_note']='Changed content'
        with self.assertRaises(ValueError):self.add('same')
        with self.assertRaises(ValueError):create_run(self.cur,self.prefix+'same','gpt-5.4')

    def test_relational_roundtrip_without_parse_json(self):
        aid=self.add('roundtrip')
        tokens=load_tokens(self.cur,aid)
        self.assertEqual(tokens[0]['feats'],self.p['tokens'][0]['feats'])
        self.assertEqual(tokens[0]['role'],self.p['tokens'][0]['role'])
        self.cur.execute('SELECT response_json,prompt_context_json FROM sentence_grammar_analyses WHERE id=%s',(aid,))
        self.assertEqual(dict(self.cur.fetchone()),{'response_json':{},'prompt_context_json':{}})
        self.cur.execute('SELECT count(*) FROM sentence_grammar_tokens WHERE analysis_id=%s AND (feats<>\'{}\'::jsonb OR deps<>\'[]\'::jsonb OR misc<>\'{}\'::jsonb)',(aid,))
        self.assertEqual(self.cur.fetchone()['count'],0)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'snapshot.sqlite';export_snapshot(self.cur,path)
            with sqlite3.connect(path) as db:
                self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
                self.assertEqual(db.execute('SELECT count(*) FROM grammar_tokens WHERE analysis_id=?',(aid,)).fetchone()[0],len(tokens))

    def test_existing_experiment_uses_relational_writer(self):
        from run_sentence_grammar_experiment import ExperimentSentence, create_grammar_run, insert_analysis
        run=create_grammar_run(self.cur,batch_id=self.prefix,model='gpt-5.5',reasoning_effort='high',attempt_kind='initial',notes='Rollback-only fixture')
        sentence=ExperimentSentence(self.sid,0,2062,'Κάθαια',None,0,1,self.p['text'],len(self.p['tokens']))
        aid=insert_analysis(self.cur,sentence=sentence,grammar_run_id=run,parse_payload=self.p,
                            usage={'input_tokens':100,'output_tokens':200},parent_analysis_id=None,
                            attempt_number=1,attempt_kind='initial',prompt_context={'test':'fixture'},context_items=[])
        self.assertEqual(load_tokens(self.cur,aid)[0]['feats'],self.p['tokens'][0]['feats'])
        self.cur.execute('SELECT response_json,prompt_context_json,structure_validated FROM sentence_grammar_analyses WHERE id=%s',(aid,))
        self.assertEqual(dict(self.cur.fetchone()),{'response_json':{},'prompt_context_json':{},'structure_validated':True})
        self.cur.execute('SELECT count(*) FROM sentence_grammar_run_notes WHERE grammar_run_id=%s',(run,))
        self.assertEqual(self.cur.fetchone()['count'],3)

    def test_review_journal_import_is_idempotent_and_correctable_before_sync(self):
        aid=self.add('review-base');key=self.prefix+'review-base'
        event=uuid4().hex;second=uuid4().hex
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'reviews.db'
            with sqlite3.connect(path) as edge:
                edge.executescript((Path(__file__).parent/'review_cgi/grammar_review_schema.sql').read_text())
                edge.execute('INSERT INTO grammar_review_actions(event_key,target_key,passage_sha256,action,reviewer,review_note,sentence_note,literal_translation,created_at) VALUES (?,?,?,?,?,?,?,?,?)',(event,key,digest(self.p['text']),'bless','test reviewer','reviewed','Corrected structure','corrected translation','2026-09-09T12:00:00Z'))
                for t in self.p['tokens']:
                    edge.execute('INSERT INTO grammar_review_action_tokens VALUES (?,?,?,?,?,?,?,?,?,?,?)',(event,int(t['id']),t['form'],t['lemma'],t['upos'],t['xpos'],t['head'],t['deprel'],'manual',t['note'],t['role']))
                    for k,v in t['feats'].items():edge.execute('INSERT INTO grammar_review_action_features VALUES (?,?,?,?)',(event,int(t['id']),k,v))
                edge.execute('INSERT INTO grammar_review_actions(event_key,target_key,passage_sha256,action,reviewer,created_at) VALUES (?,?,?,?,?,?)',(second,'human:'+event,digest(self.p['text']),'unbless','test reviewer','2026-09-09T13:00:00Z'))
            self.assertEqual(import_review_actions(self.cur,path),2)
            self.assertEqual(import_review_actions(self.cur,path),0)
            self.assertEqual(self.select(),aid)
            self.cur.execute('SELECT parent_analysis_id,sentence_note FROM sentence_grammar_analyses WHERE analysis_key=%s',('human:'+event,))
            row=self.cur.fetchone();self.assertEqual(row['parent_analysis_id'],aid);self.assertEqual(row['sentence_note'],'Corrected structure')

if __name__=='__main__':unittest.main()
