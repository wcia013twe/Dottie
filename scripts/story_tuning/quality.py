"""Engineering policy checks, not learning-outcome or teacher-approval claims."""
from mlflow.entities import Feedback
from mlflow.genai.scorers import scorer

@scorer
def valid_decision(outputs):
    ok = isinstance(outputs, dict) and 'decision' in outputs
    return Feedback(value=ok, rationale='Validated runtime decision.' if ok else 'Runtime contract or model call failed.')

@scorer
def teaching_policy(outputs, expectations):
    actual = outputs.get('decision', {}).get('action')
    expected = expectations['action']
    return Feedback(value=actual == expected, rationale=f'Expected {expected}; got {actual}. {expectations["evidence"]}')

@scorer
def concise_activity(outputs):
    d = outputs.get('decision', {})
    ok = bool(d) and len(d.get('reason', '')) < 200 and (d.get('prompt') is None or len(d['prompt']) < 160)
    return Feedback(value=ok, rationale='Reason must be under 200 characters; activity under 160.')

SCORERS = [valid_decision, teaching_policy, concise_activity]


def promotion_allowed(baseline, candidate):
    """Only promote a strict improvement with perfect validation and policy checks."""
    keys = [f'{s.name}/mean' for s in SCORERS]
    if any(k not in baseline or k not in candidate for k in keys):
        return False
    return bool(candidate[keys[0]] == 1 and candidate[keys[1]] == 1
            and all(candidate[k] >= baseline[k] for k in keys)
            and any(candidate[k] > baseline[k] for k in keys))
