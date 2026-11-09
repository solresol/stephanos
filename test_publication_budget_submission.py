import json,unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
from contextlib import ExitStack
import translate_lemmas as t
import publication_budget as b

def row(profile='gpt-5.5',created='enqueue_translation_runs.py',approved_only=False):
    return (1,2,1,created,b.MODEL,None,None,'responses','medium',1,profile,1,1,'Translate',False,approved_only,1,'Greek','meineke','Lemma',1,False,approved_only,False)
def args():
    return SimpleNamespace(request_limit=50,run_limit=50,daily_token_limit=100000,no_guidance_context=True,allow_incomplete_guidance=False,allow_human_evaluation_translations=False,no_source_passage_context=True,publication_budget=True)

class Integration(unittest.TestCase):
    def test_unknown_submission_holds_reservations_and_never_requeues(self):
        conn=Mock();cur=Mock();cur.fetchall.return_value=[(1,)]
        client=SimpleNamespace(base_url='https://api.openai.com/v1/',responses=SimpleNamespace(input_tokens=SimpleNamespace(count=lambda **_:SimpleNamespace(input_tokens=100))))
        history=[]
        conn.commit.side_effect=lambda:history.append('commit')
        def reserve(*a,**k):history.append('reserve')
        def submit(*a,**k):
            self.assertIn('commit',history[history.index('reserve')+1:]);raise TimeoutError('unknown')
        with ExitStack() as stack:
            for name,ret in [('create_batch_job',1),('has_human_translation',False),('cancel_non_public_source_request',False),('completed_run_count',0),('max_run_index',0)]:stack.enter_context(patch.object(t,name,return_value=ret))
            pending=stack.enter_context(patch.object(t,'mark_request_pending'))
            stack.enter_context(patch.object(t,'mark_request_running'))
            stack.enter_context(patch.object(t,'mark_batch_job_error'))
            stack.enter_context(patch.object(t.publication_budget,'reserve_item',side_effect=reserve))
            stack.enter_context(patch.object(t,'submit_batch',side_effect=submit))
            with self.assertRaises(TimeoutError):t.submit_translation_batch(conn,cur,client,requests=[row()],args=args(),tokens_today=0,guidance_provenance_enabled=False)
            pending.assert_not_called()
    def test_budget_lane_does_not_cancel_experiment(self):
        with ExitStack() as stack:
            stack.enter_context(patch.object(t,'create_batch_job',return_value=1))
            done=stack.enter_context(patch.object(t,'mark_request_done'))
            stack.enter_context(patch.object(t,'mark_batch_job_error'))
            pending=stack.enter_context(patch.object(t,'mark_request_pending'))
            request=row(profile='gpt-5.5_v4_reasoning',created='human-eval:test',approved_only=True)
            result=t.submit_translation_batch(Mock(),Mock(),Mock(),requests=[request],args=args(),tokens_today=0,guidance_provenance_enabled=False)
            done.assert_not_called();pending.assert_not_called();self.assertIsNone(result)
    def test_incomplete_response_never_published_but_tokens_retained(self):
        metadata=dict(request_id=1,lemma_id=2,profile_id=1,profile_version_id=1,source_text_version_id=1,run_index=1,requested_runs=1,source_document='meineke',api_mode='responses',model=b.MODEL,profile_version_number=1,publication_budget=dict(input_tokens=100,max_output_tokens=2048),request_payload={})
        item=dict(status='submitted',metadata=metadata)
        body=dict(status='incomplete',incomplete_details=dict(reason='max_output_tokens'),usage=dict(input_tokens=100,output_tokens=10,total_tokens=110),output=[dict(type='function_call',name='submit_translation',arguments=json.dumps({'translation':'Partial valid JSON'}))])
        payload=dict(custom_id='x',response=dict(status_code=200,body=body))
        client=Mock();client.batches.retrieve.return_value=SimpleNamespace(status='completed',output_file_id='file-1',error_file_id=None)
        conn=Mock();cur=Mock();cur.fetchone.return_value=(1,)
        with ExitStack() as stack:
            for name,ret in [('get_batch_job',(1,2,3,4,'batch-id')),('get_batch_items',{'x':item}),('file_content_text',json.dumps(payload)),('write_batch_output','/tmp/fake'),('completed_run_count',0)]:stack.enter_context(patch.object(t,name,return_value=ret))
            for name in ['update_batch_status','mark_batch_item','mark_request_done','mark_request_pending']:stack.enter_context(patch.object(t,name))
            insert=stack.enter_context(patch.object(t,'insert_run',return_value=7))
            publish=stack.enter_context(patch.object(t,'project_legacy_translation'))
            close=stack.enter_context(patch.object(t.publication_budget,'close_reservations'))
            result=t.collect_translation_batch(conn,cur,client,job_id=1)
            publish.assert_not_called();self.assertEqual(insert.call_args.kwargs['status'],'failed');self.assertEqual(insert.call_args.kwargs['tokens_used'],110);self.assertEqual(result,(0,1,0));close.assert_called_once()
if __name__=='__main__':unittest.main(verbosity=2)
