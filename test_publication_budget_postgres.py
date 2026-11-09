"""Opt-in private PostgreSQL budget regression tests. Never accepts a live DSN.

Run with STEPHANOS_TEST_POSTGRES=1. The fixture creates a private temporary
Unix-socket-only cluster and stops/removes it after testing.
"""
import json,os,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta
from types import SimpleNamespace
import psycopg2
import publication_budget as b

@unittest.skipUnless(os.environ.get("STEPHANOS_TEST_POSTGRES") == "1", "set STEPHANOS_TEST_POSTGRES=1 for an isolated local cluster")
class PublicationBudgetPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix='stephanos-review-pg-'); cls.root=cls.tmp.name
        bins = sorted(Path("/usr/lib/postgresql").glob("*/bin/initdb"), reverse=True)
        if not bins or os.geteuid() == 0:
            raise unittest.SkipTest("Local non-root initdb required")
        cls.pg = str(bins[0].parent) + "/"
        cls.price_patch = patch.object(b, "PRICE_EXPIRES", datetime.now(b.TIMEZONE) + timedelta(days=365))
        cls.price_patch.start()
        subprocess.run([cls.pg+'initdb','-D',cls.root+'/data','-A','trust','--no-locale'],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,check=True)
        subprocess.run([cls.pg+'pg_ctl','-D',cls.root+'/data','-l',cls.root+'/server.log','-o',f"-k {cls.root} -p 65479 -h ''",'-w','start'],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,check=True)
        cls.conn=psycopg2.connect(host=cls.root,port=65479,dbname='postgres',user=os.environ['USER'])
        cls.conn.autocommit=True
        with cls.conn.cursor() as c:
            c.execute('''CREATE TABLE openai_batch_jobs(id int primary key,status text,openai_batch_id text);
CREATE TABLE openai_batch_items(id serial primary key,batch_job_id int,custom_id text unique,purpose text,local_id int,metadata jsonb,response_json jsonb,status text default 'submitted',created_at timestamptz default now(),updated_at timestamptz default now());
CREATE TABLE translation_prompt_profiles(id int primary key,name text);
CREATE TABLE translation_runs(profile_id int,completed_at timestamptz,request_id int,run_index int,request_payload_json jsonb,model text default 'gpt-6.1-sol');
CREATE TABLE translation_run_requests(id int primary key,requested_runs int,created_by text);''')
    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        subprocess.run([cls.pg+'pg_ctl','-D',cls.root+'/data','-m','fast','-w','stop'],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,check=True)
        cls.tmp.cleanup()
        cls.price_patch.stop()
    def setUp(self):
        with self.conn.cursor() as c:
            c.execute("TRUNCATE openai_batch_items,openai_batch_jobs,translation_prompt_profiles,translation_runs,translation_run_requests RESTART IDENTITY; INSERT INTO translation_run_requests SELECT id,1,'enqueue_translation_runs.py' FROM generate_series(1,5000) AS id; INSERT INTO openai_batch_jobs VALUES(1,'creating',NULL); INSERT INTO translation_prompt_profiles VALUES(1,'gpt-5.5')")
        self.now=datetime.now(b.TIMEZONE)
        client=SimpleNamespace(base_url='https://api.openai.com/v1/',responses=SimpleNamespace(input_tokens=SimpleNamespace(count=lambda **_:SimpleNamespace(input_tokens=32768))))
        self.body,self.quote=b.quote_request(client,dict(model=b.MODEL,instructions='translate',input=[dict(role='user',content='test')],tools=[dict(type='function',name='submit_translation')]),now=self.now)
    def connection(self):
        return psycopg2.connect(host=self.root,port=65479,dbname='postgres',user=os.environ['USER'])
    def attempt(self,i,request_id=None):
        conn=self.connection()
        try:
            with conn.cursor() as cur:
                result=b.reserve_item(cur,job_id=1,custom_id=f'custom-{i}',request_id=request_id or i,metadata={'profile_id':1,'run_index':1,'model':b.MODEL},quote=self.quote,body=self.body)
                conn.commit(); return result
        except b.BudgetBlocked as e:
            conn.rollback(); return str(e)
        finally:conn.close()
    def seed(self,amount,start,end):
        entry=dict(scheme=b.SCHEME,reserved_micro_usd=amount,reserved_at=start.isoformat(),closed_at=end.isoformat() if end else None)
        with self.conn.cursor() as c:c.execute("INSERT INTO openai_batch_items(batch_job_id,custom_id,purpose,local_id,metadata) VALUES(1,'seed','translation',99999,%s::jsonb)",(json.dumps({'publication_budget':entry}),))
    def test_atomic_daily_cap_concurrency(self):
        with ThreadPoolExecutor(max_workers=30) as pool:results=list(pool.map(self.attempt,range(1,31)))
        admitted=[x for x in results if isinstance(x,dict)]
        self.assertEqual(len(admitted),19,results)
        with self.conn.cursor() as c:
            totals=b.period_totals(b.read_entries(c,self.now+timedelta(minutes=1)),self.now+timedelta(minutes=1))
        self.assertEqual(totals,(972800,972800))
    def test_atomic_month_cap_concurrency(self):
        if self.now.day == 1:
            self.skipTest("Prior-day same-month fixture requires day2 or later")
        self.seed(29050000,self.now-timedelta(days=2),self.now-timedelta(days=1))
        with ThreadPoolExecutor(max_workers=30) as pool:results=list(pool.map(self.attempt,range(1,31)))
        self.assertEqual(sum(isinstance(x,dict) for x in results),18,results)
    def test_duplicate_request_serialized(self):
        with ThreadPoolExecutor(max_workers=20) as pool:results=list(pool.map(lambda i:self.attempt(i,request_id=1234),range(1,21)))
        self.assertEqual(sum(isinstance(x,dict) for x in results),1,results)
    def test_pending_prior_month_carries_and_closed_day_stays(self):
        self.seed(960000,self.now.replace(day=1)-timedelta(days=1),None)
        self.assertIsInstance(self.attempt(1),str)
        with self.conn.cursor() as c:
            b.close_reservations(c,1)
            entries=b.read_entries(c,self.now+timedelta(minutes=1))
            self.assertEqual(b.period_totals(entries,self.now+timedelta(minutes=1)),(960000,960000))
            tomorrow=(self.now+timedelta(days=1)).replace(hour=1)
            self.assertEqual(b.period_totals(entries,tomorrow),(0,960000 if tomorrow.month == self.now.month else 0))
    def test_sync_after_expired_prior_month_blocks(self):
        old=self.now.replace(day=1)-timedelta(days=1)
        with self.conn.cursor() as c:
            c.execute("UPDATE openai_batch_jobs SET status='expired',openai_batch_id='batch-old'")
            c.execute("INSERT INTO openai_batch_items(batch_job_id,custom_id,purpose,local_id,metadata,status,created_at,updated_at) VALUES(1,'old','translation',12,'{\"profile_id\":1,\"run_index\":1,\"model\":\"gpt-6.1-sol\"}','expired',%s,%s)",(old,old))
            c.execute("INSERT INTO translation_runs VALUES(1,%s,12,1,'{\"transport\":\"sync\"}')",(self.now,))
            with self.assertRaisesRegex(b.BudgetBlocked,'standard publication'):b.read_entries(c,self.now)
    def test_unknown_legacy_and_bad_quote_fail_closed(self):
        with self.conn.cursor() as c:
            c.execute("INSERT INTO openai_batch_items(batch_job_id,custom_id,purpose,local_id,metadata) VALUES(1,'old','translation',12,'{\"profile_id\":1,\"run_index\":1,\"model\":\"gpt-6.1-sol\"}')")
            with self.assertRaisesRegex(b.BudgetBlocked,'Unresolved legacy'):b.read_entries(c,self.now)
        with self.conn.cursor() as c:c.execute('TRUNCATE openai_batch_items')
        self.quote['reserved_micro_usd']=1
        self.assertIn('does not match',self.attempt(1))
    def test_rollback_is_not_reserved_and_commit_survives_restart(self):
        conn=self.connection()
        with conn.cursor() as c:b.reserve_item(c,job_id=1,custom_id='rollback',request_id=1,metadata={},quote=self.quote,body=self.body)
        conn.rollback();conn.close()
        self.assertIsInstance(self.attempt(1),dict)
        self.conn.close()
        subprocess.run([self.pg+'pg_ctl','-D',self.root+'/data','-m','fast','-w','restart'],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,check=True)
        type(self).conn=self.connection();self.conn.autocommit=True
        with self.conn.cursor() as c:
            c.execute('SELECT COUNT(*) FROM openai_batch_items');self.assertEqual(c.fetchone()[0],1)
    def test_missing_legacy_model_is_not_zero_spend(self):
        with self.conn.cursor() as c:
            c.execute("INSERT INTO openai_batch_items(batch_job_id,custom_id,purpose,local_id,metadata) VALUES(1,'missing-model','translation',12,%s::jsonb)",(json.dumps(dict(profile_id=1,run_index=1)),))
            with self.assertRaises(b.BudgetBlocked):b.read_entries(c,self.now)
    def test_marker_underscores_are_literal(self):
        with self.conn.cursor() as c:
            c.execute("UPDATE translation_run_requests SET created_by='humanXeval:test' WHERE id=12")
            c.execute("INSERT INTO openai_batch_items(batch_job_id,custom_id,purpose,local_id,metadata) VALUES(1,'marker','translation',12,%s::jsonb)",(json.dumps(dict(profile_id=1,run_index=1,model=b.MODEL)),))
            self.assertTrue(b.is_normal_publication('gpt-5.5',b.MODEL,1,'humanXeval:test'))
            with self.assertRaises(b.BudgetBlocked):b.read_entries(c,self.now)
    def test_unknown_legacy_profile_classification_blocks(self):
        with self.conn.cursor() as c:
            c.execute("INSERT INTO openai_batch_items(batch_job_id,custom_id,purpose,local_id,metadata) VALUES(1,'missing-profile','translation',12,%s::jsonb)",(json.dumps(dict(run_index=1,model=b.MODEL)),))
            with self.assertRaisesRegex(b.BudgetBlocked,'Unknown legacy publication classification'):b.read_entries(c,self.now)
    def test_exact_profile_human_experiment_excluded_from_legacy(self):
        with self.conn.cursor() as c:
            c.execute("UPDATE translation_run_requests SET created_by='human-eval:test' WHERE id=12")
            c.execute("INSERT INTO openai_batch_items(batch_job_id,custom_id,purpose,local_id,metadata) VALUES(1,'experiment','translation',12,%s::jsonb)",(json.dumps(dict(profile_id=1,run_index=1,model=b.MODEL)),))
            c.execute("INSERT INTO translation_runs VALUES(1,%s,12,1,'{\"transport\":\"sync\"}')",(self.now,))
            self.assertEqual(b.read_entries(c,self.now),[])
    def test_completed_prior_month_no_current_charge(self):
        old=self.now.replace(day=1)-timedelta(days=1)
        self.seed(29999999,old-timedelta(days=1),old)
        with self.conn.cursor() as c:self.assertEqual(b.period_totals(b.read_entries(c,self.now),self.now),(0,0))

if __name__=='__main__':unittest.main(verbosity=2)
