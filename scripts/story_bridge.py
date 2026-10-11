"""Local HTTP adapter for the shared Story Mode controller and MCP orchestrator."""
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
from time import perf_counter

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from learner_bridge import publish_story
from story_mode.controller import Controller, StoryError
from story_mode.preparation import Preparation
from story_mode.lookahead import Lookahead
from story_mode.interaction_audio import prepare_audio
from threading import Thread

controller=Controller()
create_session=controller.create
preparations=Preparation(controller)
lookahead=Lookahead(controller)
MCP_KEY=secrets.token_urlsafe(32)
MODEL_TOOLS={'propose_word_emphasis','prepare_word_sequence','propose_activity','recommend_continue','prepare_braille','speak_prompt','give_hint','submit_response'}
TEACHER_ACTIONS={'set_word_emphasis','prepare_word_sequence','set_context','approve_activity','prepare_braille','confirm_tactile','speak_prompt','give_hint','submit_response','record_observation','resume_story'}


def handle(handler):
    """Return True for handled routes. Request bodies and errors never expose credentials."""
    if not handler.path.startswith('/api/story/'): return False
    host=handler.headers.get('Host','')
    if host not in (f'127.0.0.1:{handler.server.server_port}',f'localhost:{handler.server.server_port}'):
        handler._json(403,{'error':'Local requests only.'});return True
    mcp=handler.path=='/api/story/mcp'
    if mcp:
        if not secrets.compare_digest(handler.headers.get('X-Story-Key',''),MCP_KEY):
            handler._json(403,{'error':'MCP bridge authentication required.'});return True
    elif handler.headers.get('Origin')!='http://'+host:
        handler._json(403,{'error':'Same-origin teacher UI required.'});return True
    try:
        if handler.headers.get_content_type()!='application/json':raise StoryError('Expected JSON.')
        size=int(handler.headers.get('Content-Length','0'))
        if not 0<size<=16384:raise StoryError('Invalid request size.')
        handler.connection.settimeout(45)
        body=json.loads(handler.rfile.read(size))
        if not isinstance(body,dict):raise StoryError('Expected object.')
        path=handler.path
        if path=='/api/story/session':
            result=create_session(body.get('history',[]))
        elif path=='/api/story/lookahead':
            ticket, needed=lookahead.begin(body['session_id'],body['revision'],body['target'])
            if needed:
                def work():
                    try:
                        request={'session_id':body['session_id'],'revision':body['revision'],'lookahead_target':body['target']}
                        result=orchestrate(request,handler.server.server_port,prepare_only=True)
                        try: audio=prepare_audio(result['plan'])
                        except Exception: audio={}  # Keep the reviewed text usable if synthesis is unavailable.
                        lookahead.finish(body['session_id'],ticket,result['plan'],audio)
                    except Exception: lookahead.fail(body['session_id'],ticket)
                Thread(target=work,daemon=True).start()
            result={k:ticket[k] for k in ('preparation_id','target','status')}
            if ticket.get('plan'):result['preview']=ticket['plan']
        elif path=='/api/story/lookahead-status':
            with controller.lock:
                ticket=lookahead.entries.get(body['session_id'])
                if not ticket or ticket['preparation_id']!=body['preparation_id']:raise StoryError('Look-ahead expired or failed.')
                result={k:ticket[k] for k in ('preparation_id','target','status')}
                if ticket.get('plan'):result['preview']=ticket['plan']
        elif path=='/api/story/apply-lookahead':
            result=lookahead.apply(body['session_id'],body['revision'],body['preparation_id'])
        elif path=='/api/story/prepare':
            result=prepare(body,handler.server.server_port)
        elif path=='/api/story/apply-prepared':
            started=perf_counter()
            result=preparations.apply(body['session_id'],body['revision'],body['preparation_id'])
            result['orchestrator']['apply_ms']=round((perf_counter()-started)*1000,2)
        elif path=='/api/story/orchestrate':
            result=orchestrate(body,handler.server.server_port)
        elif path in ('/api/story/action','/api/story/mcp'):
            name=body['name'];sid=body['session_id']
            if name=='get_story_context':result=controller.get(sid)
            else:
                if name not in (MODEL_TOOLS if mcp else TEACHER_ACTIONS):raise StoryError('Action unavailable to this caller.')
                if not isinstance(body.get('arguments',{}),dict):raise StoryError('Invalid tool arguments.')
                result=controller.call(sid,body['revision'],name,body.get('arguments',{}),actor='orchestrator' if mcp else 'teacher')
        else:
            handler._json(404,{'error':'Unknown Story Mode route.'});return True
        # Reflection is read-only and cannot fail or replay an already saved teaching action.
        if path in ('/api/story/action','/api/story/mcp') and body.get('name')=='record_observation':
            try: publish_story(result)
            except Exception: print('Learner reflection failed; previous publication retained.',flush=True)  # Never replay an already recorded action.
        handler._json(200,result)
    except (StoryError,ValueError,KeyError,TypeError) as exc:
        handler._json(400,{'error':str(exc) if isinstance(exc,StoryError) else 'Invalid Story Mode request.'})
    except (subprocess.TimeoutExpired,TimeoutError):
        handler._json(504,{'error':'Story orchestrator timed out. Refresh context before retrying.'})
    except Exception:
        handler._json(503,{'error':'Story Mode is unavailable. Check the local server and isolated environment.'})
    return True


def prepare(request, port):
    sid=request['session_id']
    ticket, needed=preparations.begin(sid, request['revision'])
    if needed:
        try:
            result=orchestrate(request, port, prepare_only=True)
            ticket=preparations.finish(sid, ticket, result['plan'], result['orchestrator'])
        except Exception:
            preparations.fail(sid, ticket)
            raise
    return {key:ticket[key] for key in ('preparation_id','revision','status')}


def orchestrate(request,port, *, prepare_only=False):
    state=controller.get(request['session_id'])
    phases=('reading','proposed','continue_proposed')+ (('awaiting_confirmation',) if state.get('synthetic_persona') else ())
    if request['revision']!=state['revision'] or state['phase'] not in phases:
        raise StoryError('Refresh context before requesting another decision.')
    if state['opportunity'] is None and not (prepare_only and request.get('lookahead_target')):raise StoryError('No approved teaching opportunity on this spread.')
    python=ROOT/'.venv-story/bin/python'
    if not python.exists():raise StoryError('Install story_mode/requirements.txt in .venv-story first.')
    started=perf_counter()
    result=subprocess.run([str(python),str(ROOT/'story_mode/orchestrator.py')],
        input=json.dumps({'session_id':state['session_id'],'revision':state['revision'],'prepare_only':prepare_only, **({'lookahead_target':request['lookahead_target']} if request.get('lookahead_target') else {})}),
        text=True,capture_output=True,timeout=35,
        env={**os.environ,'MAGNETO_STORY_URL':f'http://127.0.0.1:{port}','MAGNETO_STORY_KEY':MCP_KEY})
    if result.returncode:raise StoryError('The model or MCP connection failed. No fallback teaching decision was substituted.')
    response=json.loads(result.stdout)
    response['orchestrator']['timings_ms']['bridge_total_ms']=round((perf_counter()-started)*1000,2)
    return response
