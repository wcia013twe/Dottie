"""Live profile feed. Real observations sync to UC; mocks are explicit, isolated previews."""
import json
import subprocess
import threading
import time
from urllib.parse import urlparse, parse_qs
from learner_intelligence import ROOT, STORE, ProfileStore, derive, digest

PENDING_STORE=ProfileStore(ROOT/'.local/learner-intelligence/pending-evidence')

POINTER=STORE.directory/'active-session.json'
try:ACTIVE=json.loads(POINTER.read_text())['learner_id']
except (OSError,ValueError,KeyError):ACTIVE=None
LOCK=threading.RLock()
STATUS={'state':'checking','connected':False,'source':'workspace.magneto.learner_observations_v1','event_count':0,'checked_at':None,'error':None,'genie':'checking'}
RUNNING=False;QUEUED=False;CHECKED=0

def cloud(operation,payload):
    result=subprocess.run([str(ROOT/'.venv-agent/bin/python'),str(ROOT/'scripts/learner_cloud.py'),operation],input=json.dumps(payload),text=True,capture_output=True,timeout=55)
    if result.returncode:raise RuntimeError('Databricks evidence sync failed. Local observations retained for retry.')
    return json.loads(result.stdout)

def select(learner):
    global ACTIVE
    ACTIVE=learner
    STORE.directory.mkdir(parents=True,exist_ok=True)
    tmp=POINTER.with_suffix('.tmp');tmp.write_text(json.dumps({'learner_id':learner}));tmp.replace(POINTER)

def materialize(data):
    learner=data['learner_id'] or 'unassigned'
    previous=STORE.read(learner)
    merged={e['id']:e for e in (previous or {}).get('events',[])}
    for e in data['events']:
        if e['id'] in merged and merged[e['id']]!=e:raise ValueError('Conflicting immutable evidence.')
        merged[e['id']]=e
    events=sorted(merged.values(),key=lambda e:(e['occurred_at'],e['id']))
    from learner_reflection import VERSION
    if previous and previous['checkpoint']==digest(events) and previous.get('reflection_version')==VERSION:
        return {'published':False,'profile':previous['profile']}
    if not events:
        return {'published':False,'profile':live_profile()}
    batch={'learner_id':learner,'display_name':'This learner','synthetic':False,'events':events}
    with LOCK:STATUS['genie']='analyzing'
    result=subprocess.run([str(ROOT/'.venv-agent/bin/python'),str(ROOT/'scripts/learner_reflection.py')],
        input=json.dumps({'batch':batch,'store':str(STORE.directory)}),
        text=True,capture_output=True,timeout=900)
    if result.returncode:raise RuntimeError('Research reflection failed; previous publication retained.')
    return json.loads(result.stdout)

def worker():
    global RUNNING,QUEUED,CHECKED
    while True:
        with LOCK:QUEUED=False;learner=ACTIVE
        try:
            record=(PENDING_STORE.read(learner) or STORE.read(learner)) if learner else None
            if record:cloud('ingest',{'events':[e for e in record['events'] if e['confirmed'] and not e['synthetic']]})
            data=cloud('read',{'learner_id':learner})
            with LOCK:STATUS.update(state='connected',connected=True,event_count=len(data['events']),checked_at=time.time(),error=None)
            try:
                materialize(data)
                with LOCK:
                    if data['learner_id'] and ACTIVE==learner:select(data['learner_id'])
                    STATUS['genie']='connected' if live_profile().get('analysis') else 'unavailable'
            except Exception:
                with LOCK:STATUS.update(genie='unavailable',error='Research reflection unavailable. Previous published understanding retained.')
        except Exception:
            with LOCK:STATUS.update(state='unavailable',connected=False,error='Databricks sync unavailable. Showing retained real evidence; mock preview remains separate.',checked_at=time.time())
        with LOCK:
            CHECKED=time.monotonic()
            if not QUEUED:RUNNING=False;return

def refresh(force=False):
    global RUNNING,QUEUED
    with LOCK:
        if RUNNING:
            if force:QUEUED=True
            return
        if not force and time.monotonic()-CHECKED<60:return
        RUNNING=True
        if not STATUS['connected']:STATUS['state']='syncing'
        threading.Thread(target=worker,daemon=True).start()

def publish_story(state):
    from learner_intelligence import reflect_story
    # Preserve the authoritative input before normalization drops unrelated fields.
    raw=PENDING_STORE.directory/'raw-story'
    raw.mkdir(parents=True,exist_ok=True)
    path=raw/(digest(state)+'.json')
    if not path.exists():
        tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(state,indent=2)+'\n');tmp.replace(path)
    result=reflect_story(state,store=PENDING_STORE)
    if result:
        with LOCK:select(result['profile']['learner_id'])
        refresh(force=True)
    return result

def live_profile():
    record=STORE.read(ACTIVE or 'unassigned')
    return record['profile'] if record else derive('unassigned','This learner',[],False)

def handle(handler):
    parsed=urlparse(handler.path)
    if parsed.path not in ('/api/learner-profile','/api/learner-profile/status'):return False
    host=handler.headers.get('Host','')
    if host not in (f'127.0.0.1:{handler.server.server_port}',f'localhost:{handler.server.server_port}'):
        handler._json(403,{'error':'Local requests only.'});return True
    try:
        if parsed.path.endswith('/status'):
            refresh()
            with LOCK:handler._json(200,dict(STATUS))
        elif parse_qs(parsed.query).get('mode')==['synthetic-test']:
            # Read the last validated test artifact only. No refresh, ingestion,
            # active-learner selection or live-store writes in this mode.
            test_root=ROOT/'reports/synthetic-cloud-flow'
            report=json.loads((test_root/'latest.json').read_text())
            profile=json.loads((test_root/'profile.json').read_text())
            if (report.get('status')!='passed' or profile.get('synthetic') is not True
                    or profile['learner_id']!=report['learner_id']
                    or any(e['synthetic'] is not True for e in profile['evidence'])):
                raise ValueError('No validated synthetic cloud profile available.')
            handler._json(200,profile)
        elif parse_qs(parsed.query).get('mode')==['mock']:
            handler._json(200,json.loads((ROOT/'web/learn/data/learner-profile-demo.json').read_text()))
        elif parsed.query:
            handler._json(400,{'error':'Unsupported profile mode.'})
        else:
            refresh()
            handler._json(200,live_profile())
    except Exception:handler._json(503,{'error':'Profile unavailable. Previous publication retained.'})
    return True
