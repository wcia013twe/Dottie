"""Validate bounded learning uploads before authenticated transport."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'databricks/magneto-director'))
from learning import contract


class LearningError(RuntimeError):
    def __init__(self, message, status=502):
        super().__init__(message)
        self.status = status


def _validate(validator, value):
    try:
        return validator(value)
    except (ValueError, TypeError, KeyError) as exc:
        raise LearningError('Invalid learning payload.', 400) from exc


def validate_batch(payload):
    return _validate(contract.validate_batch, payload)


def validate_attempts(payload):
    return _validate(contract.validate_attempts, payload)


def validate_profile(profile):
    return _validate(contract.validate_profile, profile)


def _invoke(payload, timeout):
    interpreter = ROOT / '.venv-agent/bin/python'
    if not interpreter.exists():
        raise LearningError('Databricks adapter dependencies are missing.', 503)
    try:
        response = subprocess.run([str(interpreter), str(ROOT / 'scripts/platform_learning.py')],
                                  input=json.dumps(payload), text=True, capture_output=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError) as exc:
        raise LearningError('Learning upload is unavailable; records remain queued.', 503) from exc
    if response.returncode:
        raise LearningError('Learning upload failed; records remain queued.', 503)
    try:
        result = json.loads(response.stdout)
        if not isinstance(result, dict):
            raise ValueError()
        return result
    except (ValueError, TypeError) as exc:
        raise LearningError('Learning service returned an invalid response.') from exc


def _ack(result, key, sent_ids):
    ids = result.get(key)
    if not isinstance(ids, list) or not ids or any(not isinstance(v, str) for v in ids) or len(ids) != len(set(ids)) or not set(ids) <= sent_ids:
        raise LearningError('Learning service returned an invalid acknowledgement.')
    return result


def ingest_events(payload, *, timeout=35):
    validate_batch(payload)
    return _ack(_invoke(payload, timeout), 'event_ids', {e['event_id'] for e in payload['events']})


def ingest_attempts(payload, *, timeout=35):
    validate_attempts(payload)
    result = _invoke(payload, timeout)
    if any(result.get(k) != payload[k] for k in ('schema_version', 'profile_id', 'session_id')):
        raise LearningError('Learning acknowledgement belongs to another session.')
    return _ack(result, 'attempt_ids', {a['attempt_id'] for a in payload['attempts']})


def create_profile(profile, *, timeout=35):
    validate_profile(profile)
    result = _invoke({'profile': profile}, timeout)
    if result.get('profile_id') != profile['profile_id'] or result.get('consent') != profile['consent']:
        raise LearningError('Profile service returned an invalid acknowledgement.')
    return result
