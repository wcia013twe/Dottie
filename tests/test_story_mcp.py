"""Real MCP stdio integration with an injected model fixture; no inference or learner data."""
import asyncio
from functools import partial
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import threading
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from serve import Handler
from story_bridge import controller, MCP_KEY
from story_mode.orchestrator import run

class ProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(ROOT/'web')))
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        os.environ['MAGNETO_STORY_URL']=f'http://127.0.0.1:{cls.server.server_port}'
        os.environ['MAGNETO_STORY_KEY']=MCP_KEY
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.thread.join()
    def setUp(self):
        self.s=controller.create();self.s=controller.call(self.s['session_id'],0,'set_context',{'passage_id':'rabbit'},actor='teacher')
    def test_model_selection_executes_through_mcp(self):
        def fixture(messages):
            data=json.loads(messages[-1]['content'])
            self.assertIn('propose_activity',[t['name'] for t in data['available_mcp_tools']])
            self.assertEqual(data['context']['opportunity']['targets'],['r','rabbit'])
            return json.dumps({'tool':'propose_activity','arguments':{'session_id':self.s['session_id'],'revision':self.s['revision'],
                'activity':'identify','target':'r','prompt':'What letter do you feel?','hint':'Feel the three left dots and the middle right dot.',
                'reason':'Try a brief recognition activity with the rabbit prop.'}})
        result=asyncio.run(run(self.s,fixture))
        self.assertEqual(result['state']['phase'],'proposed')
        self.assertEqual(result['state']['trace'][-1]['actor'],'orchestrator')
        self.assertEqual(result['orchestrator']['transport'],'MCP stdio')
        self.assertFalse(result['state']['device']['ready'])
    def test_teacher_observation_reaches_next_model_context(self):
        def act(name,args=None,actor='teacher'):
            self.s=controller.call(self.s['session_id'],self.s['revision'],name,args,actor=actor)
        act('propose_activity',{'activity':'identify','target':'r','prompt':'What letter do you feel?',
            'hint':'Explore the right middle dot.','reason':'Synthetic integration-test activity.'},'orchestrator')
        act('approve_activity');act('prepare_braille');act('confirm_tactile');act('speak_prompt')
        act('record_observation',{'outcome':'with_help'})
        act('set_context',{'passage_id':'lettuce'})
        def fixture(messages):
            context=json.loads(messages[-1]['content'])['context']
            self.assertEqual(context['observations'][-1]['outcome'],'with_help')
            self.assertEqual(context['observations'][-1]['target'],'r')
            return json.dumps({'tool':'propose_activity','arguments':{'session_id':self.s['session_id'],
                'revision':self.s['revision'],'activity':'identify','target':'r','prompt':'Feel this letter. Can you name it?',
                'hint':'There are three dots on the left and one in the middle on the right.',
                'reason':'Revisit r with radish after teacher-recorded support with rabbit.'}})
        result=asyncio.run(run(self.s,fixture))
        self.assertEqual(result['state']['proposal']['target'],'r')
        self.assertEqual(len(result['state']['observations']),1)

    def test_navigation_during_model_call_rejects_late_tool(self):
        def late(messages):
            controller.call(self.s['session_id'],self.s['revision'],'set_context',{'passage_id':'gate'},actor='teacher')
            return json.dumps({'tool':'recommend_continue','arguments':{'session_id':self.s['session_id'],'revision':self.s['revision'],'reason':'Stale'}})
        with self.assertRaises(Exception):asyncio.run(run(self.s,late))
        self.assertEqual(controller.get(self.s['session_id'])['passage_id'],'gate')
        self.assertIsNone(controller.get(self.s['session_id'])['proposal'])
    def test_model_cannot_select_teacher_tool(self):
        def invalid(messages):return json.dumps({'tool':'record_observation','arguments':{}})
        with self.assertRaises(Exception):asyncio.run(run(self.s,invalid))
        self.assertEqual(controller.get(self.s['session_id'])['observations'],[])

    def test_synthetic_persona_and_reply_reach_model_without_grading(self):
        self.s=controller.create(synthetic_persona_id='alex-morgan')
        def act(name,args=None,actor='teacher'):
            self.s=controller.call(self.s['session_id'],self.s['revision'],name,args,actor=actor)
        act('set_context',{'passage_id':'rabbit'})
        act('propose_activity',{'activity':'introduce','target':'r','prompt':'This letter is r.',
            'hint':'Feel one dot at a time.','reason':'Fictional beginner test.'},'orchestrator')
        act('approve_activity');act('prepare_braille');act('confirm_tactile');act('speak_prompt')
        act('submit_response',{'text':'Are a letter and a word basically the same?'})
        def fixture(messages):
            context=json.loads(messages[-1]['content'])['context']
            self.assertEqual(context['synthetic_persona']['id'],'alex-morgan')
            self.assertFalse(context['response']['confirmed'])
            self.assertEqual(context['observations'],[])
            return json.dumps({'tool':'propose_activity','arguments':{'session_id':self.s['session_id'],
                'revision':self.s['revision'],'activity':'introduce','target':'r',
                'prompt':'A letter is one symbol. A word uses letters. This is the letter r.',
                'hint':'Explore one letter first.','reason':'Clarify the fictional learner’s question using one approved letter.'}})
        result=asyncio.run(run(self.s,fixture))
        self.assertEqual(result['state']['phase'],'proposed')
        self.assertEqual(result['state']['observations'],[])
        self.assertFalse(result['state']['device']['ready'])

if __name__=='__main__':unittest.main()
