"""Small local selection policy; no retrieval, storage or device execution."""
from copy import deepcopy

MAX_RECENT_OBSERVATIONS = 4
DECISION_PHASES = {'reading', 'proposed', 'continue_proposed'}


def decision_context(state):
    """Project runtime state onto bounded, relevant evidence for this opportunity."""
    synthetic_followup = bool(state.get('synthetic_persona')) and state['phase'] == 'awaiting_confirmation'
    if (state['phase'] not in DECISION_PHASES and not synthetic_followup) or not state['opportunity']:
        raise ValueError('No teaching decision is available in this phase')
    targets = state['opportunity']['targets']
    observations = [o for o in state['observations']
                    if o['source'] == 'teacher' and o['target'] in targets]
    context = {key: deepcopy(state[key]) for key in (
        'session_id', 'revision', 'phase', 'opportunity', 'policy', 'activities_started')}
    context['observations'] = deepcopy(observations[-MAX_RECENT_OBSERVATIONS:])
    context['review_candidates'] = deepcopy([r for r in state.get('review_candidates',[]) if r['target'] in targets][:4])
    context['observations_omitted'] = len(observations) - len(context['observations'])
    if state.get('synthetic_persona'):
        context['synthetic_persona'] = deepcopy(state['synthetic_persona'])
        context['response'] = deepcopy(state.get('response'))
    return context


def allowed_tools(context):
    if context['activities_started'] >= context['policy']['max_activities']:
        return {'recommend_continue'}
    tools={'propose_activity', 'recommend_continue'}
    if context['policy'].get('word_emphasis_enabled') and any(len(t)>1 for t in context['opportunity']['targets']):tools.add('propose_word_emphasis')
    return tools


def rule_plan(context):
    if allowed_tools(context) == {'recommend_continue'}:
        return {'tool': 'recommend_continue', 'arguments': {
            'session_id': context['session_id'], 'revision': context['revision'],
            'reason': 'The session activity limit has been reached. Continue the story.'}}
    return None


def validate_plan(plan, context):
    """Reject malformed selections before transport; controller rechecks live state."""
    if not isinstance(plan, dict) or set(plan) != {'tool', 'arguments'}:
        raise ValueError('Invalid selection envelope')
    if not isinstance(plan['tool'], str) or plan['tool'] not in allowed_tools(context):
        raise ValueError('Unavailable teaching action')
    args = plan['arguments']
    fields = {'session_id', 'revision', 'reason'}
    if plan['tool'] in ('propose_activity','propose_word_emphasis'):
        fields |= {'activity', 'target', 'prompt', 'hint'}
    if not isinstance(args, dict) or set(args) != fields:
        raise ValueError('Invalid teaching action arguments')
    if (type(args['revision']) is not int or args['revision'] != context['revision']
            or args['session_id'] != context['session_id']):
        raise ValueError('Stale or mismatched selection')
    for field, limit in [('reason', 400), ('prompt', 240), ('hint', 240)]:
        if field in args and (not isinstance(args[field], str)
                              or not 1 <= len(args[field].strip()) <= limit):
            raise ValueError('Invalid teaching text')
    if plan['tool'] in ('propose_activity','propose_word_emphasis'):
        beta=plan['tool']=='propose_word_emphasis'
        if beta and len(args.get('target',''))<2:raise ValueError('Word emphasis requires an approved keyword')
        if args['activity'] not in (('emphasize',) if beta else ('introduce','identify','match')):
            raise ValueError('Unknown teaching activity')
        if args['target'] not in context['opportunity']['targets']:
            raise ValueError('Target outside this opportunity')
    return plan
