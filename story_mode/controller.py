"""Authoritative in-memory session controller. No physical hardware or microphone adapter yet."""
from copy import deepcopy
from threading import RLock
from uuid import uuid4
from datetime import datetime, timezone
from story_mode.review import validate_history, summarize

import json
from pathlib import Path

CHECKPOINT_MAP = json.loads((Path(__file__).resolve().parents[1]/'web/learn/books/peter-rabbit-checkpoints.json').read_text())
CATALOG = {c['id']: {k:v for k,v in c.items() if k != 'id'} for c in CHECKPOINT_MAP['checkpoints']}

DOTS = dict(zip('abcdefghijklmnopqrstuvwxyz', [[1],[1,2],[1,4],[1,4,5],[1,5],[1,2,4],[1,2,4,5],[1,2,5],[2,4],[2,4,5],[1,3],[1,2,3],[1,3,4],[1,3,4,5],[1,3,5],[1,2,3,4],[1,2,3,4,5],[1,2,3,5],[2,3,4],[2,3,4,5],[1,3,6],[1,2,3,6],[2,4,5,6],[1,3,4,6],[1,3,4,5,6],[1,3,5,6]]))

class StoryError(ValueError):
    pass

class Controller:
    def __init__(self):
        self.sessions = {}
        self.lock = RLock()

    def create(self, history=None, *, synthetic_persona_id=None):
        # Only the isolated server selects a repository-owned persona; HTTP clients cannot supply prose.
        persona=None
        if synthetic_persona_id is not None:
            from story_mode.personas import load_persona
            persona=load_persona(synthetic_persona_id)
        with self.lock:
            history=deepcopy(validate_history([] if history is None else history,{t for c in CATALOG.values() for t in c['targets']}))
            # Ephemeral anonymous session; never load a child's identity or browser shelf.
            if len(self.sessions) >= 100:
                raise StoryError('Too many sessions. Restart the local server to clear expired sessions.')
            sid = str(uuid4())
            self.sessions[sid] = {'session_id':sid, 'revision':0, 'passage_id':None,
                'phase':'reading', 'proposal':None, 'response':None, 'observations':[], 'trace':[],
                'device':{'connected':False, 'ready':False, 'mode':'teacher-supplied tactile Braille'},
                'policy':{'word_emphasis_enabled':True, 'teacher_approval':True, 'max_activities':6, 'braille_code':'UEB', 'translation':'uncontracted lowercase letters'},
                'activities_started':0, 'interaction_revision':0, 'learner_history':history}
            if persona is not None:
                self.sessions[sid]['synthetic_persona']=persona
            return self.get(sid)

    def get(self, sid):
        with self.lock:
            if sid not in self.sessions: raise StoryError('Session expired. Reopen the teacher panel.')
            state = deepcopy(self.sessions[sid])
            state['review_candidates']=summarize(state.get('learner_history',[])+state['observations'])
            state['opportunity'] = deepcopy(CATALOG.get(state['passage_id']))
            return state

    def start_device_activity(self, sid, revision, send):
        """One validated target, atomic revision check, then acknowledged actuation."""
        with self.lock:
            state=self.get(sid)
            if type(revision) is not int or revision!=state['revision']:
                raise StoryError('Stale activity rejected before sending a device command.')
            if state.get('device_released') or state['phase']!='proposed' or not state.get('proposal'):
                raise StoryError('No active proposal to send to the device.')
            proposal=state['proposal']
            if proposal['target'] not in CATALOG[state['passage_id']]['targets'] or state['activities_started']>=state['policy']['max_activities']:
                raise StoryError('Activity target or budget is invalid.')
            result=send('show',proposal['target'])
            state['device']=result
            if result.get('cell_ack') is True and result.get('connected') is True:
                state['activities_started']+=1
                state['braille']={'code':'UEB','mode':'uncontracted lowercase','cells':[{'letter':c,'dots':DOTS[c]} for c in proposal['target']],
                    'physical_ready':True,'source':'device acknowledgement'}
                state['tactile_source']='device acknowledged target; mechanical operation unverified'
                state['phase']='waiting_response'
                state['speech']={'id':str(uuid4()),'text':proposal['prompt'],'kind':'prompt'}
            state['revision']+=1
            state['interaction_revision']+=1
            state['trace']=(state['trace']+[{'tool':'start_device_activity','actor':'runtime','revision':state['revision']}])[-40:]
            self.sessions[sid]=state
            return self.get(sid)

    def release_device(self, sid, send):
        with self.lock:
            state=self.get(sid)
            if state['device'].get('state') not in (None,'not_configured'):
                state['device']=send('clear')
                if state['device'].get('cell_ack') is not True:
                    state['revision']+=1;self.sessions[sid]=state
                    return self.get(sid)
            state.update(device_released=True,phase='reading',proposal=None,response=None)
            state['interaction_revision']+=1
            state.pop('braille',None)
            state['revision']+=1
            self.sessions[sid]=state
            return self.get(sid)

    def call(self, sid, revision, name, args=None, *, actor='orchestrator'):
        with self.lock:
            if sid not in self.sessions: raise StoryError('Session expired.')
            original=self.sessions[sid]
            if type(revision) is not int or revision != original['revision']: raise StoryError('Stale action rejected. Refresh the story context.')
            s=deepcopy(original); args=args or {}
            def phase(*allowed):
                if s['phase'] not in allowed: raise StoryError('Action is not allowed in the current phase.')
            def teacher():
                if actor != 'teacher': raise StoryError('Only the teacher can confirm this action.')
            def text(field, limit):
                value=args.get(field)
                if not isinstance(value,str) or not 1 <= len(value.strip()) <= limit: raise StoryError(f'Invalid {field}.')
                return value.strip()
            if name == 'set_context':
                teacher()
                passage=args.get('passage_id')
                if passage is not None and passage not in CATALOG: raise StoryError('Unknown story passage.')
                s.update(passage_id=passage, phase='reading', proposal=None, response=None, device_released=False)
            elif name == 'set_word_emphasis':
                teacher();phase('reading','proposed','continue_proposed')
                if type(args.get('enabled')) is not bool:raise StoryError('Word emphasis setting must be boolean.')
                s['policy']['word_emphasis_enabled']=args['enabled']
                s.update(phase='reading',proposal=None,response=None)
            elif name in ('propose_activity','propose_word_emphasis'):
                phase('reading','proposed','continue_proposed',*(['awaiting_confirmation'] if s.get('synthetic_persona') else []))
                opportunity=CATALOG.get(s['passage_id'])
                target=args.get('target')
                if not opportunity or target not in opportunity['targets']: raise StoryError('Target is outside the approved passage.')
                if s['activities_started'] >= s['policy']['max_activities']: raise StoryError('Session activity limit reached.')
                beta=name=='propose_word_emphasis'
                if beta and (not s['policy']['word_emphasis_enabled'] or not isinstance(target,str) or len(target)<2):raise StoryError('Word emphasis is unavailable for this target.')
                if args.get('activity') not in (('emphasize',) if beta else ('introduce','identify','match')): raise StoryError('Unknown activity.')
                s['proposal']={'activity':args['activity'], 'target':target, 'kind':'letter' if len(target)==1 else 'word',
                    'reason':text('reason',400), 'prompt':text('prompt',240), 'hint':text('hint',240)}
                s['phase']='proposed'
                s['response']=None
            elif name == 'recommend_continue':
                phase('reading','proposed','continue_proposed',*(['awaiting_confirmation'] if s.get('synthetic_persona') else []))
                s['proposal']={'reason':text('reason',400)};s['phase']='continue_proposed'
            elif name == 'approve_activity':
                teacher();phase('proposed');s['phase']='awaiting_tactile';s['activities_started']+=1
            elif name in ('prepare_braille','prepare_word_sequence'):
                phase('awaiting_tactile')
                if name=='prepare_word_sequence' and (not s['policy']['word_emphasis_enabled'] or s['proposal']['activity']!='emphasize'):raise StoryError('No approved word activity.')
                s['braille']={'code':'UEB','mode':'uncontracted lowercase', 'cells':[{'letter':c,'dots':DOTS[c]} for c in s['proposal']['target']],
                              'physical_ready':False, 'source':'deterministic preview; teacher supplies tactile material'}
                if name=='prepare_word_sequence':
                    s['braille']['sequence']={'word':s['proposal']['target'],'hold_ms':1500,'gap_ms':300,'command':'SPELL '+s['proposal']['target'],'execution':'preview_only'}
            elif name == 'confirm_tactile':
                teacher();phase('awaiting_tactile')
                if 'braille' not in s: raise StoryError('Prepare the Braille preview first.')
                s['phase']='ready';s['tactile_source']='teacher confirmed material offered; not a hardware acknowledgement'
            elif name == 'speak_prompt':
                phase('ready','waiting_response')
                s['phase']='waiting_response';s['speech']={'id':str(uuid4()),'text':s['proposal']['prompt'],'kind':'prompt'}
            elif name == 'give_hint':
                phase('waiting_response')
                s['hint_used']=True;s['speech']={'id':str(uuid4()),'text':s['proposal']['hint'],'kind':'hint'}
            elif name == 'submit_response':
                phase('waiting_response');s['response']={'text':text('text',300), 'source':'unconfirmed transcript', 'confirmed':False}
                s['phase']='awaiting_confirmation'
            elif name == 'record_observation':
                teacher();phase('waiting_response','awaiting_confirmation')
                outcome=args.get('outcome')
                if outcome not in ('independent','with_help','try_later'): raise StoryError('Invalid observation.')
                if outcome == 'independent' and s.get('hint_used'): raise StoryError('A hint was used. Record with help or try later.')
                s['observations'].append({'id':str(uuid4()), 'passage_id':s['passage_id'], 'target':s['proposal']['target'],
                    'observed_at':datetime.now(timezone.utc).isoformat(), 'activity':s['proposal']['activity'], 'outcome':outcome, 'source':'teacher', 'hint_used':s.get('hint_used',False)})
                s['phase']='complete'
            elif name == 'resume_story':
                teacher();s.update(phase='reading',proposal=None,response=None)
            else: raise StoryError('Unknown Story Mode tool.')
            if name in ('set_context','resume_story','propose_activity','propose_word_emphasis','set_word_emphasis'):
                for field in ('braille','speech','hint_used','tactile_source'):s.pop(field,None)
            if name != 'set_context': s['interaction_revision'] = s.get('interaction_revision', 0) + 1
            s['revision']+=1
            s['trace']=(s['trace']+[{'tool':name,'actor':actor,'revision':s['revision']}])[-40:]
            self.sessions[sid]=s
            return self.get(sid)
