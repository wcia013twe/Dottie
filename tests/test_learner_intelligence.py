import copy
import io
from email.message import Message
from types import SimpleNamespace
from unittest.mock import Mock, patch
import json
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from learner_intelligence import ProfileStore, derive
from story_mode.controller import Controller

BATCH=json.loads((ROOT/'tests/fixtures/learner-evidence.json').read_text())
class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.store=ProfileStore(self.temp.name)
    def update(self,events):return self.store.update('demo-wes','Wes',events,synthetic=True)
    def card(self,result,cid='braille'):return next(c for c in result['profile']['categories'] if c['id']==cid)
    def test_change_and_replay(self):
        first=[e for e in BATCH['events'] if e['session_id']=='sample-1']
        a=self.update(first);b=self.update(BATCH['events']);c=self.update(BATCH['events'])
        self.assertEqual([a['profile']['epoch'],b['profile']['epoch'],c['profile']['epoch']],[1,2,2])
        self.assertFalse(c['published']);self.assertEqual(c['profile'],b['profile'])
        self.assertEqual(self.card(a)['metric']['numerator'],2)
        self.assertEqual(self.card(b)['metric']['numerator'],4)
        self.assertIn('Previously 40%',self.card(b)['finding'])
        self.assertEqual(len(self.card(b)['history']),2)
        self.assertEqual(len(self.card(b)['chart']['points']),2)
    def test_unconfirmed_device_failure_no_epoch(self):
        a=self.update(BATCH['events']);extra=copy.deepcopy(BATCH['events'][0]);extra.update(id='unconfirmed',confirmed=False)
        b=self.update([extra]);self.assertFalse(b['published']);self.assertNotEqual(a['checkpoint'],b['checkpoint'])
        extra.update(id='failure',confirmed=True,outcome='device_failure');c=self.update([extra]);self.assertFalse(c['published'])
    def test_insufficient_evidence(self):
        a=self.update(BATCH['events'][:2]);self.assertIsNone(self.card(a)['metric']);self.assertIsNone(self.card(a)['chart'])
    def test_different_conditions_never_make_trend(self):
        events=copy.deepcopy([e for e in BATCH['events'] if e['category']=='braille'])
        for e in events:
            if e['session_id']=='sample-2':e['condition']='different material and easier task'
        self.assertIsNone(self.card(self.update(events))['chart'])
    def test_source_identity_and_conflicting_ids(self):
        self.update(BATCH['events']);bad=copy.deepcopy(BATCH['events'][0]);bad['outcome']='with_help'
        with self.assertRaises(ValueError):self.update([bad])
        bad['learner_id']='someone-else'
        with self.assertRaises(ValueError):self.update([bad])
        bad['learner_id']='demo-wes';bad['synthetic']=False
        with self.assertRaises(ValueError):self.update([bad])
    def test_write_failure_retains_publication(self):
        a=self.update(BATCH['events']);bad=copy.deepcopy(BATCH['events'][0]);bad['id']='new';bad['category']='unknown'
        with self.assertRaises(ValueError):self.update([bad])
        self.assertEqual(self.store.read('demo-wes')['profile'],a['profile'])
    def test_real_story_adapter(self):
        import learner_intelligence as module
        original=module.STORE;module.STORE=self.store;self.addCleanup(setattr,module,'STORE',original)
        controller=Controller();state=controller.create()
        def call(name,args=None):
            nonlocal state
            state=controller.call(state['session_id'],state['revision'],name,args,actor='teacher')
        for outcome in ('independent','with_help','independent'):
            call('set_context',{'passage_id':'rabbit'})
            call('propose_activity',{'target':'r','activity':'identify','reason':'Test opportunity','prompt':'Identify R','hint':'The letter is R'})
            call('approve_activity');call('prepare_braille');call('confirm_tactile');call('speak_prompt')
            if outcome=='with_help':call('give_hint')
            call('record_observation',{'outcome':outcome})
            result=module.reflect_story(state)
        self.assertFalse(result['profile']['synthetic'])
        self.assertEqual(self.card(result)['metric'],{'numerator':2,'denominator':3,'unit':'percent'})
        self.assertFalse(module.reflect_story(state)['published'])
        self.assertTrue(all(e['trace_id'] is None for e in result['profile']['evidence']))
    def test_http_action_automatically_publishes(self):
        import learner_intelligence as module
        import story_bridge
        import learner_bridge
        for field,value in [('STORE',self.store),('PENDING_STORE',self.store),('POINTER',Path(self.temp.name)/'active-session.json'),('ACTIVE',None),('refresh',Mock())]:
            original_value=getattr(learner_bridge,field);setattr(learner_bridge,field,value);self.addCleanup(setattr,learner_bridge,field,original_value)
        original=module.STORE;module.STORE=self.store;self.addCleanup(setattr,module,'STORE',original)
        controller=Controller();previous=story_bridge.controller;story_bridge.controller=controller;self.addCleanup(setattr,story_bridge,'controller',previous)
        state=controller.create()
        for name,args in [('set_context',{'passage_id':'rabbit'}),('propose_activity',{'target':'r','activity':'identify','reason':'Test','prompt':'Identify R','hint':'R'}),('approve_activity',{}),('prepare_braille',{}),('confirm_tactile',{}),('speak_prompt',{})]:
            state=controller.call(state['session_id'],state['revision'],name,args,actor='teacher')
        body=json.dumps({'session_id':state['session_id'],'revision':state['revision'],'name':'record_observation','arguments':{'outcome':'independent'}}).encode()
        headers=Message();headers['Host']='127.0.0.1:8092';headers['Origin']='http://127.0.0.1:8092';headers['Content-Type']='application/json';headers['Content-Length']=str(len(body))
        handler=SimpleNamespace(path='/api/story/action',headers=headers,server=SimpleNamespace(server_port=8092),connection=Mock(),rfile=io.BytesIO(body),_json=Mock())
        self.assertTrue(story_bridge.handle(handler));self.assertEqual(handler._json.call_args.args[0],200)
        self.assertEqual(len(self.store.read('story-'+state['session_id'])['events']),1)
    def test_mlflow_read_join_does_not_grade(self):
        from learner_trace_search import search_request
        request='5a54f64d-f516-4edb-a7b3-ddd622fdab28'
        trace=SimpleNamespace(info=SimpleNamespace(client_request_id=request,trace_id='trace-example'),data=SimpleNamespace(spans=[SimpleNamespace(name='decision')]))
        search=Mock(return_value=[trace]);result=search_request(search,'experiment',request)
        self.assertEqual(result['trace_id'],'trace-example');self.assertNotIn('outcome',result)
        search.return_value=[]
        with self.assertRaises(ValueError):search_request(search,'experiment',request)
    def test_live_default_and_mock_isolation(self):
        import learner_bridge
        for field,value in [('STORE',self.store),('ACTIVE',None),('refresh',Mock())]:
            original_value=getattr(learner_bridge,field);setattr(learner_bridge,field,value);self.addCleanup(setattr,learner_bridge,field,original_value)
        handler=SimpleNamespace(path='/api/learner-profile',headers={'Host':'127.0.0.1:8092'},server=SimpleNamespace(server_port=8092),_json=Mock())
        learner_bridge.handle(handler);live=handler._json.call_args.args[1]
        self.assertFalse(live['synthetic']);self.assertEqual(live['epoch'],0);self.assertEqual(live['evidence'],[])
        handler.path+='?mode=mock';learner_bridge.handle(handler);mock=handler._json.call_args.args[1]
        self.assertTrue(mock['synthetic']);self.assertEqual(list(Path(self.temp.name).glob('*.json')),[])
    def test_cloud_rejects_mock_before_any_write(self):
        import learner_cloud
        with patch.object(learner_cloud,'query') as query:
            with self.assertRaises(ValueError):learner_cloud.ingest(Mock(),BATCH['events'])
            query.assert_not_called()
    def test_schema(self):
        try:from jsonschema import Draft202012Validator
        except ImportError:self.skipTest('jsonschema in contract environment')
        schema=json.loads((ROOT/'databricks/contracts/learner-profile-v1/profile.schema.json').read_text())
        Draft202012Validator.check_schema(schema);Draft202012Validator(schema).validate(self.update(BATCH['events'])['profile'])
        Draft202012Validator(schema).validate(derive('unassigned','This learner',[],False))
if __name__=='__main__':unittest.main()
