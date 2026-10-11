"""Ephemeral plans, separate from authoritative lesson state."""
from copy import deepcopy
from uuid import uuid4
from story_mode.controller import StoryError
from story_mode.selection import decision_context, validate_plan


class Preparation:
    def __init__(self, controller):
        self.controller = controller
        self.entries = {}

    def begin(self, sid, revision):
        with self.controller.lock:
            state = self.controller.get(sid)
            if type(revision) is not int or state['revision'] != revision:
                raise StoryError('Story changed. Prepare the current passage again.')
            decision_context(state)
            previous = self.entries.get(sid)
            if previous and previous['revision'] == revision:
                if previous['status'] == 'ready':
                    return deepcopy(previous), False
                raise StoryError('This passage is already being prepared.')
            entry = {'preparation_id': str(uuid4()), 'revision': revision, 'status': 'preparing'}
            self.entries[sid] = entry
            return deepcopy(entry), True

    def finish(self, sid, ticket, plan, diagnostics):
        with self.controller.lock:
            current = self.entries.get(sid)
            state = self.controller.get(sid)
            if current != ticket or state['revision'] != ticket['revision']:
                self.fail(sid, ticket)
                raise StoryError('Prepared decision expired because the story changed.')
            validate_plan(plan, decision_context(state))
            current.update(status='ready', plan=deepcopy(plan), diagnostics=deepcopy(diagnostics))
            return deepcopy(current)

    def fail(self, sid, ticket):
        with self.controller.lock:
            if self.entries.get(sid) == ticket:
                self.entries.pop(sid, None)

    def apply(self, sid, revision, preparation_id):
        with self.controller.lock:
            entry = self.entries.get(sid)
            if (not entry or entry['status'] != 'ready'
                    or entry['preparation_id'] != preparation_id or entry['revision'] != revision):
                raise StoryError('No matching prepared decision. Prepare this passage again.')
            state = self.controller.get(sid)
            if type(revision) is not int or state['revision'] != revision:
                self.entries.pop(sid, None)
                raise StoryError('Prepared decision expired because the story changed.')
            plan = validate_plan(entry['plan'], decision_context(state))
            args = {k: v for k, v in plan['arguments'].items() if k not in ('session_id', 'revision')}
            # Same authoritative tool dispatcher as the MCP bridge. No new process or inference.
            result = self.controller.call(sid, revision, plan['tool'], args, actor='orchestrator')
            self.entries.pop(sid, None)
            return {'state': result, 'orchestrator': {
                'mode': 'prepared', 'tool_called': plan['tool'],
                'transport': 'local MCP tool dispatcher', 'preparation': entry['diagnostics']}}
