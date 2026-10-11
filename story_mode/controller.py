"""Authoritative in-memory session controller. No physical hardware or microphone adapter yet."""
from copy import deepcopy
from threading import RLock
from uuid import uuid4

CATALOG = {
    'rabbit': {'summary': 'Meet Peter and the other little rabbits.', 'prop': 'rabbit model', 'targets': ['r', 'rabbit']},
    'lettuce': {'summary': 'Peter eats lettuces, French beans and radishes.', 'prop': 'lettuce leaf or radish model', 'targets': ['l', 'lettuce', 'r', 'radish']},
    'gate': {'summary': 'Peter squeezes under the garden gate.', 'prop': 'tactile gate model', 'targets': ['g', 'gate']},
}
DOTS = dict(zip('abcdefghijklmnopqrstuvwxyz', [[1],[1,2],[1,4],[1,4,5],[1,5],[1,2,4],[1,2,4,5],[1,2,5],[2,4],[2,4,5],[1,3],[1,2,3],[1,3,4],[1,3,4,5],[1,3,5],[1,2,3,4],[1,2,3,4,5],[1,2,3,5],[2,3,4],[2,3,4,5],[1,3,6],[1,2,3,6],[2,4,5,6],[1,3,4,6],[1,3,4,5,6],[1,3,5,6]]))

class StoryError(ValueError):
    pass

class Controller:
    def __init__(self):
        self.sessions = {}
        self.lock = RLock()

    def create(self, *, synthetic_persona_id=None):
        # Only the isolated server selects a repository-owned persona; HTTP clients cannot supply prose.
        persona=None
        if synthetic_persona_id is not None:
            from story_mode.personas import load_persona
            persona=load_persona(synthetic_persona_id)
        with self.lock:
            # Ephemeral anonymous session; never load a child's identity or browser shelf.
            if len(self.sessions) >= 100:
                raise StoryError('Too many sessions. Restart the local server to clear expired sessions.')
            sid = str(uuid4())
            self.sessions[sid] = {'session_id':sid, 'revision':0, 'passage_id':None,
                'phase':'reading', 'proposal':None, 'response':None, 'observations':[], 'trace':[],
                'device':{'connected':False, 'ready':False, 'mode':'teacher-supplied tactile Braille'},
                'policy':{'teacher_approval':True, 'max_activities':6, 'braille_code':'UEB', 'translation':'uncontracted lowercase letters'},
                'activities_started':0}
            if persona is not None:
                self.sessions[sid]['synthetic_persona']=persona
            return self.get(sid)

    def get(self, sid):
        with self.lock:
            if sid not in self.sessions: raise StoryError('Session expired. Reopen the teacher panel.')
            state = deepcopy(self.sessions[sid])
            state['opportunity'] = deepcopy(CATALOG.get(state['passage_id']))
            return state

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
                s.update(passage_id=passage, phase='reading', proposal=None, response=None)
            elif name == 'propose_activity':
                phase('reading','proposed','continue_proposed',*(['awaiting_confirmation'] if s.get('synthetic_persona') else []))
                opportunity=CATALOG.get(s['passage_id'])
                target=args.get('target')
                if not opportunity or target not in opportunity['targets']: raise StoryError('Target is outside the approved passage.')
                if s['activities_started'] >= s['policy']['max_activities']: raise StoryError('Session activity limit reached.')
                if args.get('activity') not in ('introduce','identify','match'): raise StoryError('Unknown activity.')
                s['proposal']={'activity':args['activity'], 'target':target, 'kind':'letter' if len(target)==1 else 'word',
                    'reason':text('reason',400), 'prompt':text('prompt',240), 'hint':text('hint',240)}
                s['phase']='proposed'
                s['response']=None
            elif name == 'recommend_continue':
                phase('reading','proposed','continue_proposed',*(['awaiting_confirmation'] if s.get('synthetic_persona') else []))
                s['proposal']={'reason':text('reason',400)};s['phase']='continue_proposed'
            elif name == 'approve_activity':
                teacher();phase('proposed');s['phase']='awaiting_tactile';s['activities_started']+=1
            elif name == 'prepare_braille':
                phase('awaiting_tactile')
                s['braille']={'code':'UEB','mode':'uncontracted lowercase', 'cells':[{'letter':c,'dots':DOTS[c]} for c in s['proposal']['target']],
                              'physical_ready':False, 'source':'deterministic preview; teacher supplies tactile material'}
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
                    'activity':s['proposal']['activity'], 'outcome':outcome, 'source':'teacher', 'hint_used':s.get('hint_used',False)})
                s['phase']='complete'
            elif name == 'resume_story':
                teacher();s.update(phase='reading',proposal=None,response=None)
            else: raise StoryError('Unknown Story Mode tool.')
            if name in ('set_context','resume_story','propose_activity'):
                for field in ('braille','speech','hint_used','tactile_source'):s.pop(field,None)
            s['revision']+=1
            s['trace']=(s['trace']+[{'tool':name,'actor':actor,'revision':s['revision']}])[-40:]
            self.sessions[sid]=s
            return self.get(sid)
