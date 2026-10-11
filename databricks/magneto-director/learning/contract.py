"""Shared, dependency-free validation for localhost and cloud boundaries."""
from datetime import datetime
import json
import re
from pathlib import Path
from uuid import UUID

CATALOG = json.loads(Path(__file__).with_name('activity-catalog.json').read_text())
EVENT_TYPES = {'activity_started', 'activity_completed', 'response_recorded', 'activity_skipped', 'device_unavailable'}
OUTCOMES = {'correct', 'incorrect', 'help', 'skipped', 'unavailable', None}
RESULTS = {'correct', 'incorrect', 'help_requested', 'unconfirmed'}
SUPPORT = {'none', 'hint', 'modeled_answer', 'unknown'}


def _shape(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys.split()):
        raise ValueError('Unexpected fields')


def _uuid(value):
    if not isinstance(value, str) or str(UUID(value)) != value:
        raise ValueError('Canonical UUID required')


def _time(value, *, utc=False):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})', value):
        raise ValueError('Timestamp required')
    if utc and not value.endswith('Z'):
        raise ValueError('UTC timestamp required')
    datetime.fromisoformat(value.replace('Z', '+00:00'))


def validate_batch(payload):
    """Accept v2 without upgrading its observations or interpreting assistance."""
    _shape(payload, 'schema_version events')
    if payload['schema_version'] != '2.0' or not isinstance(payload['events'], list) or not 1 <= len(payload['events']) <= 50:
        raise ValueError('Expected 1–50 v2 events')
    profile = None
    seen = set()
    for event in payload['events']:
        _shape(event, 'schema_version event_id profile_id session_id occurred_at event_type activity_id target outcome client_sequence metadata')
        for key in ('event_id', 'profile_id', 'session_id'):
            _uuid(event[key])
        profile = profile or event['profile_id']
        if event['profile_id'] != profile or event['schema_version'] != '2.0' or event['event_id'] in seen:
            raise ValueError('Mixed profile/version or duplicate event')
        seen.add(event['event_id'])
        _time(event['occurred_at'])
        if event['event_type'] not in EVENT_TYPES or event['outcome'] not in OUTCOMES:
            raise ValueError('Invalid event type or outcome')
        if not isinstance(event['activity_id'], str) or not 1 <= len(event['activity_id']) <= 120:
            raise ValueError('Invalid activity')
        if event['target'] is not None and (not isinstance(event['target'], str) or len(event['target']) > 120):
            raise ValueError('Invalid target')
        if type(event['client_sequence']) is not int or event['client_sequence'] < 0:
            raise ValueError('Invalid sequence')
        if event['metadata'] != {'source': 'browser'}:
            raise ValueError('Invalid metadata')
    return payload


def validate_attempts(payload):
    _shape(payload, 'schema_version profile_id session_id attempts')
    if payload['schema_version'] != '3.0':
        raise ValueError('Expected attempts v3')
    _uuid(payload['profile_id'])
    _uuid(payload['session_id'])
    attempts = payload['attempts']
    if not isinstance(attempts, list) or not 1 <= len(attempts) <= 50:
        raise ValueError('Expected 1–50 attempts')
    seen = set()
    for attempt in attempts:
        _shape(attempt, 'attempt_id observed_at activity_ref result support assessment')
        _uuid(attempt['attempt_id'])
        if attempt['attempt_id'] in seen:
            raise ValueError('Duplicate attempt')
        seen.add(attempt['attempt_id'])
        _time(attempt['observed_at'], utc=True)
        if attempt['activity_ref'] not in CATALOG:
            raise ValueError('Unknown activity reference')
        if attempt['result'] not in RESULTS or attempt['support'] not in SUPPORT:
            raise ValueError('Invalid result or support')
        if attempt['assessment'] not in ('teacher_confirmed', 'unconfirmed'):
            raise ValueError('Invalid assessment')
        if (attempt['assessment'] == 'unconfirmed') != (attempt['result'] == 'unconfirmed'):
            raise ValueError('Unconfirmed responses cannot claim a confirmed result')
    return payload


def validate_profile(profile):
    _shape(profile, 'schema_version profile_id consent preferences')
    if profile['schema_version'] != '2.0' or profile['consent'] not in ('granted', 'revoked'):
        raise ValueError('Invalid profile version or consent')
    _uuid(profile['profile_id'])
    _shape(profile['preferences'], 'audio_enabled')
    if type(profile['preferences']['audio_enabled']) is not bool:
        raise ValueError('Invalid audio preference')
    return profile
