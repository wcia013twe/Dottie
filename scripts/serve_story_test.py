"""Isolated fictional Story UI walkthrough. Never selects/uploads real learner data.

Uses the normal UI, controller and live model. Run python3 scripts/serve_story_test.py.
Cloud follow-through is explicit: test_synthetic_cloud_flow.py --evidence REPORT.
"""
import json
import argparse
from functools import partial
from http.server import ThreadingHTTPServer
from threading import RLock
from urllib.parse import urlparse
from serve import Handler, WEB
import story_bridge
from learner_intelligence import ROOT, ProfileStore, reflect_story
from story_mode.personas import load_persona

OUTPUT=ROOT/'reports/storybook-session-test'
STORE=ProfileStore(ROOT/'.local/storybook-session-test')
LOCK=RLock()
CURRENT_SESSION=None
PERSONA=load_persona('alex-morgan')
# This override lives only in this separate test-server process. The ordinary server stays anonymous.
story_bridge.create_session=lambda: story_bridge.controller.create(synthetic_persona_id=PERSONA['id'])

def publish(state):
    with LOCK:
        result=reflect_story(state,STORE,synthetic=True)
        if result:
            learner=result['profile']['learner_id']
            record=STORE.read(learner)
            batch={'learner_id':learner,'display_name':PERSONA['display_name']+' · fictional test',
                   'synthetic':True,'events':record['events']}
            OUTPUT.mkdir(parents=True,exist_ok=True)
            (OUTPUT/'evidence.json').write_text(json.dumps(batch,indent=2)+'\n')

story_bridge.publish_story=publish

class TestHandler(Handler):
    def _json(self,status,value):
        global CURRENT_SESSION
        state=value.get('state',value) if isinstance(value,dict) else {}
        if status==200 and isinstance(state,dict) and state.get('session_id') and 'observations' in state:
            with LOCK:
                CURRENT_SESSION=state['session_id']
                OUTPUT.mkdir(parents=True,exist_ok=True)
                (OUTPUT/'telemetry.json').write_text(json.dumps({'synthetic':True,'state':state},indent=2)+'\n')
                sessions=OUTPUT/'sessions'
                sessions.mkdir(exist_ok=True)
                with (sessions/(state['session_id']+'.jsonl')).open('a') as log:
                    log.write(json.dumps({'synthetic':True,'state':state})+'\n')
        super()._json(status,value)

    def do_GET(self):
        path=urlparse(self.path).path
        if path=='/api/story/test-persona':
            return self._json(200,PERSONA)
        if path=='/api/story/test-telemetry':
            file=OUTPUT/'telemetry.json'
            return self._json(200,json.loads(file.read_text()) if file.exists() else {'synthetic':True})
        if path in ('/api/learner-profile','/api/learner-profile/status'):
            # No live refresh, active learner selection, or production publication.
            if path.endswith('/status'):
                return self._json(200,{'state':'synthetic_test','synthetic':True})
            from learner_intelligence import derive
            with LOCK:
                learner='synthetic-story-'+(CURRENT_SESSION or 'empty')
                record=STORE.read(learner)
            batch={'learner_id':learner,'display_name':PERSONA['display_name']+' · fictional test',
                   'events':record['events'] if record else []}
            cloud=ROOT/'reports/synthetic-cloud-flow/profile.json'
            profile=json.loads(cloud.read_text()) if cloud.exists() else None
            if not profile or not profile['learner_id'].startswith(batch['learner_id']+'-'):
                record=STORE.read(batch['learner_id'])
                profile=record['profile'] if record else derive(batch['learner_id'],batch['display_name'],batch['events'],True)
            return self._json(200,profile)
        super().do_GET()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8100)
    parser.add_argument('--identify-fixture',action='store_true',help='Controlled identification proposal; substitutes the model only in this test process')
    args=parser.parse_args()
    if args.identify_fixture:
        def identify(request,port):
            state=story_bridge.controller.get(request['session_id'])
            target=state['opportunity']['targets'][0]
            state=story_bridge.controller.call(state['session_id'],request['revision'],'propose_activity',
                {'activity':'identify','target':target,'kind':'letter','reason':'FICTIONAL TEST: controlled identification proposal.',
                 'prompt':'Which letter is shown?','hint':'Think of the first letter of the story object.'},actor='orchestrator')
            return {'state':state}
        story_bridge.orchestrate=identify
    print(f'ALEX MORGAN · FICTIONAL STORY TEST: http://127.0.0.1:{args.port}/learn/?profile=synthetic-test#stories',flush=True)
    ThreadingHTTPServer(('127.0.0.1',args.port),partial(TestHandler,directory=str(WEB))).serve_forever()
