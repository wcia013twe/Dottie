"""One speculative exercise per session, never an authoritative future state."""
from copy import deepcopy
from uuid import uuid4
from story_mode.controller import CATALOG, StoryError
from story_mode.selection import decision_context, validate_plan


def project(state, target):
    if target not in CATALOG or state['phase'] != 'reading':
        raise StoryError('Look-ahead requires reading and a curated opportunity.')
    state = deepcopy(state)
    state.update(passage_id=target, opportunity=deepcopy(CATALOG[target]))
    return state


def evidence(state):
    return deepcopy({**{k: state[k] for k in ('observations', 'activities_started', 'policy')},
                     'learner_history':state.get('learner_history',[]), 'review_candidates':state.get('review_candidates',[]),
                     'interaction_revision':state.get('interaction_revision',0)})


class Lookahead:
    def __init__(self, controller):
        self.controller, self.entries = controller, {}

    def begin(self, sid, revision, target):
        with self.controller.lock:
            state = self.controller.get(sid)
            if type(revision) is not int or revision != state['revision']:
                raise StoryError('Refresh the reading context.')
            projected = project(state, target)
            old = self.entries.get(sid)
            if old and old['status'] == 'preparing':
                raise StoryError('Look-ahead is already preparing.')
            if old and old['target'] == target and old['evidence'] == evidence(state):
                if old['status'] == 'ready': return deepcopy(old), False
                raise StoryError('Look-ahead is already preparing.')
            ticket = dict(preparation_id=str(uuid4()), target=target, status='preparing',
                          evidence=evidence(state), projected=projected)
            self.entries[sid] = ticket
            return deepcopy(ticket), True

    def fail(self, sid, ticket):
        with self.controller.lock:
            if self.entries.get(sid, {}).get('preparation_id') == ticket['preparation_id']:
                self.entries.pop(sid, None)

    def finish(self, sid, ticket, plan, audio):
        with self.controller.lock:
            state = self.controller.get(sid)
            if (self.entries.get(sid) != ticket or state['phase'] != 'reading'
                    or evidence(state) != ticket['evidence']):
                self.fail(sid, ticket)
                raise StoryError('Look-ahead expired.')
            validate_plan(plan, decision_context(ticket['projected']))
            entry = self.entries[sid]
            entry.update(status='ready', plan=deepcopy(plan), audio=audio)
            return deepcopy(entry)

    def apply(self, sid, revision, handle):
        with self.controller.lock:
            state = self.controller.get(sid)
            entry = self.entries.get(sid)
            if (not entry or entry['status'] != 'ready' or entry['preparation_id'] != handle
                    or type(revision) is not int or state['revision'] != revision
                    or state['phase'] != 'reading' or state['passage_id'] != entry['target']
                    or evidence(state) != entry['evidence']):
                raise StoryError('Look-ahead no longer matches this page and learning state.')
            plan = deepcopy(entry['plan'])
            plan['arguments']['revision'] = revision
            validate_plan(plan, decision_context(state))
            args = {k:v for k,v in plan['arguments'].items() if k not in ('session_id','revision')}
            result = self.controller.call(sid, revision, plan['tool'], args, actor='orchestrator')
            self.entries.pop(sid, None)
            return {'state':result, 'interaction_audio':entry['audio'],
                    'orchestrator':{'mode':'lookahead', 'tool_called':plan['tool']}}
