import copy
import json
from pathlib import Path
from types import SimpleNamespace as NS
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, FormatChecker
from learning.contract import validate_attempts, validate_batch, validate_profile
from learning.store import LearningStore, StorageUnavailable, RecordConflict, ConsentRequired
from runtime import main

BASE = Path(__file__).resolve().parents[2] / 'contracts'
EXAMPLE = json.loads((BASE / 'v3/examples/rabbit-session.json').read_text())
SCHEMA = Draft202012Validator(json.loads((BASE / 'v3/attempt-batch.schema.json').read_text()), format_checker=FormatChecker())


def batch():
    return copy.deepcopy(EXAMPLE)


def profile():
    return {'schema_version': '2.0', 'profile_id': EXAMPLE['profile_id'], 'consent': 'granted', 'preferences': {'audio_enabled': False}}


def legacy():
    return json.loads((BASE / 'v2/examples/interaction-event.json').read_text())


class SQL:
    """Fake external service, including successful transport with failed SQL status."""
    def __init__(self):
        self.records = {}
        self.calls = []
        self.consent = 'granted'
        self.failure = None
        self.truncated = False

    def execute_statement(self, **request):
        self.calls.append(request)
        state = self.failure or 'SUCCEEDED'
        rows = []
        values = {p.name: p.value for p in request['parameters']}
        query = request['statement']
        if state == 'SUCCEEDED':
            if query.startswith('SELECT consent'):
                rows = [[self.consent]] if self.consent else []
            elif query.startswith('MERGE') and 'p0_attempt_id' in values:
                for key in values:
                    if key.endswith('_attempt_id'):
                        prefix = key[:-len('attempt_id')]
                        record = {k[len(prefix):]: v for k, v in values.items() if k.startswith(prefix)}
                        self.records.setdefault(values[key], record)
            elif query.startswith('SELECT attempt_id,fingerprint'):
                rows = [[key, self.records[key]['fingerprint']] for key in values.values() if key in self.records]
            elif query.startswith('MERGE') and 'p0_event_id' in values:
                for key in values:
                    if key.endswith('_event_id'):
                        prefix = key[:-len('event_id')]
                        self.records.setdefault(values[key], {k[len(prefix):]: v for k, v in values.items() if k.startswith(prefix)})
            elif query.startswith('SELECT t.event_id'):
                for key in values:
                    if key.endswith('_event_id'):
                        prefix = key[:-len('event_id')]
                        record = {k[len(prefix):]: v for k, v in values.items() if k.startswith(prefix)}
                        if self.records.get(values[key]) == record:
                            rows.append([values[key]])
        return NS(status=NS(state=state), manifest=NS(truncated=self.truncated), result=NS(data_array=rows))


def store():
    sql = SQL()
    svc = NS(config=NS(learning_warehouse_id='test', catalog='workspace', schema='magneto'), client=NS(statement_execution=sql))
    return LearningStore(svc), sql


def test_valid_examples_and_catalog():
    SCHEMA.validate(batch())
    assert validate_attempts(batch()) == batch()
    assert validate_batch({'schema_version': '2.0', 'events': [legacy()]})
    assert validate_profile(profile())


@pytest.mark.parametrize('field,value', [
    ('transcript', 'unnecessary raw text'), ('observed_at', 'today'),
    ('activity_ref', 'made-up'), ('support', 'probably'),
    ('assessment', 'machine_confirmed'), ('result', 'mastered'),
    ('attempt_id', 'bad-id'),
])
def test_rejects_invalid_attempt_fields_in_schema_and_runtime(field, value):
    payload = batch()
    payload['attempts'][0][field] = value
    with pytest.raises(Exception):
        SCHEMA.validate(payload)
    with pytest.raises((ValueError, TypeError)):
        validate_attempts(payload)


@pytest.mark.parametrize('change', ['mixed-assessment', 'duplicate', 'too-many', 'empty', 'extra-envelope'])
def test_semantic_rejections(change):
    payload = batch()
    if change == 'mixed-assessment': payload['attempts'][0]['assessment'] = 'unconfirmed'
    if change == 'duplicate': payload['attempts'].append(payload['attempts'][0])
    if change == 'too-many': payload['attempts'] *= 20
    if change == 'empty': payload['attempts'] = []
    if change == 'extra-envelope': payload['story_text'] = 'not collected'
    with pytest.raises(ValueError):
        validate_attempts(payload)


def test_legacy_invalid_timestamp_and_version_rejected():
    event = legacy()
    for key, value in [('occurred_at', '2026-99-99T12:00:00Z'), ('schema_version', '3.0'), ('client_sequence', True)]:
        bad = {**event, key: value}
        with pytest.raises(ValueError):
            validate_batch({'schema_version': '2.0', 'events': [bad]})


def test_successful_retry_is_one_record_per_attempt_and_matching_ack():
    service, sql = store()
    first = service.ingest_attempts(batch())
    assert first == service.ingest_attempts(batch())
    assert len(sql.records) == len(batch()['attempts'])
    assert first['attempt_ids'] == [a['attempt_id'] for a in EXAMPLE['attempts']]
    assert all(r['wait_timeout'] == '5s' and r['on_wait_timeout'].value == 'CANCEL' for r in sql.calls)
    assert all(EXAMPLE['profile_id'] not in r['statement'] for r in sql.calls)


@pytest.mark.parametrize('state', ['PENDING', 'RUNNING', 'FAILED', 'CANCELED', 'CLOSED', None])
def test_non_success_never_acknowledged(state):
    service, sql = store()
    # Fail specifically on the MERGE, after a successful consent lookup.
    original = sql.execute_statement
    def execute(**request):
        if request['statement'].startswith('MERGE'):
            return NS(status=NS(state=state))
        return original(**request)
    sql.execute_statement = execute
    with pytest.raises(StorageUnavailable):
        service.ingest_attempts(batch())


def test_same_id_different_content_is_rejected():
    service, sql = store()
    service.ingest_attempts(batch())
    altered = batch()
    altered['attempts'][0]['support'] = 'none'
    with pytest.raises(RecordConflict):
        service.ingest_attempts(altered)
    assert len(sql.records) == len(batch()['attempts'])


def test_missing_and_revoked_profiles_block_writes():
    for consent in [None, 'revoked']:
        service, sql = store()
        sql.consent = consent
        with pytest.raises(ConsentRequired):
            service.ingest_attempts(batch())
        assert not any(r['statement'].startswith('MERGE') for r in sql.calls)


def test_truncated_readback_not_acknowledged():
    service, sql = store()
    original = sql.execute_statement
    def execute(**request):
        result = original(**request)
        if request['statement'].startswith('SELECT attempt_id'):
            result.manifest.truncated = True
        return result
    sql.execute_statement = execute
    with pytest.raises(StorageUnavailable):
        service.ingest_attempts(batch())


def test_legacy_retries_and_sql_nulls_are_preserved():
    service, sql = store()
    event = legacy()
    event['target'] = None
    event['outcome'] = None
    assert service.ingest_events([event]) == service.ingest_events([event])
    assert len(sql.records) == 1
    assert sql.records[event['event_id']]['target'] is None
    changed = {**event, 'outcome': 'incorrect'}
    with pytest.raises(RecordConflict):
        service.ingest_events([changed])


@pytest.mark.parametrize('status', ['FAILED', 'RUNNING', 'CANCELED'])
def test_profile_failure_never_reports_ready(status):
    service, sql = store()
    sql.failure = status
    with pytest.raises(StorageUnavailable):
        service.create_profile(profile())


@pytest.mark.parametrize('error,status', [
    (StorageUnavailable('secret sql'), 503), (RecordConflict('private record'), 409),
    (ConsentRequired('private consent'), 403),
])
def test_api_reports_retryable_storage_errors_separately_from_validation(monkeypatch, error, status):
    def fail(_): raise error
    monkeypatch.setattr(main.app.state, 'learning_store', NS(ingest_attempts=fail), raising=False)
    response = TestClient(main.app).post('/api/learning/attempts', json=batch(), headers={'x-profile-key': EXAMPLE['profile_id']})
    assert response.status_code == status
    assert 'attempt_ids' not in response.json()
    assert 'private' not in response.text and 'secret' not in response.text


def test_invalid_api_batch_never_reaches_store(monkeypatch):
    def forbidden(_): pytest.fail('Invalid payload reached store')
    monkeypatch.setattr(main.app.state, 'learning_store', NS(ingest_attempts=forbidden), raising=False)
    payload = batch()
    payload['attempts'][0]['transcript'] = 'not allowed'
    client = TestClient(main.app)
    assert client.post('/api/learning/attempts', json=payload, headers={'x-profile-key': EXAMPLE['profile_id']}).status_code == 400
    assert client.post('/api/learning/attempts', json=batch(), headers={'x-profile-key': str(uuid4())}).status_code == 400
    assert client.post('/api/learning/attempts', content='x'*65537).status_code == 413


def test_valid_api_batch_round_trip(monkeypatch):
    service, _ = store()
    monkeypatch.setattr(main.app.state, 'learning_store', service, raising=False)
    response = TestClient(main.app).post('/api/learning/attempts', json=batch(), headers={'x-profile-key': EXAMPLE['profile_id']})
    assert response.status_code == 200
    assert len(response.json()['attempt_ids']) == len(batch()['attempts'])
