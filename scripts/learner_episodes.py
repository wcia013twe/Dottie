"""Deterministic, lossless episode views over normalized outcome evidence."""
from copy import deepcopy
from datetime import datetime
from learner_intelligence import digest, validate_event

VERSION = 'interaction-episodes-1'


def episodes(events):
    """One ordered session view; repeated attempts are never collapsed by content."""
    unique = {}
    identity = set()
    for event in events:
        validate_event(event)
        identity.add((event['learner_id'], event['synthetic']))
        if len(identity) > 1:
            raise ValueError('Mixed learner/source episodes')
        if event['id'] in unique and unique[event['id']] != event:
            raise ValueError('Conflicting immutable event')
        unique[event['id']] = deepcopy(event)
    ordered = sorted(unique.values(), key=lambda e: (
        datetime.fromisoformat(e['occurred_at'].replace('Z', '+00:00')), e['id']))
    sessions = {}
    for event in ordered:
        sessions.setdefault(event['session_id'], []).append(event)
    result = []
    for session, rows in sessions.items():
        result.append({
            'version': VERSION,
            'id': digest({'version': VERSION, 'events': rows}),
            'learner_id': rows[0]['learner_id'], 'session_id': session,
            'synthetic': rows[0]['synthetic'],
            'started_at': rows[0]['occurred_at'], 'last_observed_at': rows[-1]['occurred_at'],
            'event_ids': [e['id'] for e in rows],
            'steps': rows,
            'coverage': 'Recorded outcomes only; prompts, hint contents, retry links and session completion are not recorded. Same-time events have unknown relative order.',
        })
    return result


def research_queries(items):
    """Bounded category queries; no learner identity or raw trace text in search logs."""
    topics = {
        'braille': 'braille literacy instruction independent letter recognition tactile discrimination assistance',
        'tactile': 'braille tactile exploration instruction support',
        'instructions': 'accessible instruction repetition task comprehension scaffolding',
        'answering': 'accessible learning response options learner choice asking for help',
        'transfer': 'braille literacy retrieval practice transfer delayed retention',
        'interests': 'braille literacy meaningful motivating learner selected content',
    }
    observed = {e['category'] for item in items for e in item['steps']
                if e['confirmed'] and e['outcome'] not in ('device_failure', 'try_later')}
    return [{'category': c, 'query': topics[c]} for c in topics if c in observed]
