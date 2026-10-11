import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from runtime import main

FIXTURE = json.loads((Path(__file__).parents[1] / 'fixtures/companion_snapshot.json').read_text())
SNAPSHOT = FIXTURE['snapshot']


def envelope(input_value=None):
    return {'id': SNAPSHOT['request_id'], 'session_id': SNAPSHOT['session_id'], 'input': input_value or FIXTURE}


@pytest.mark.parametrize(
    'payload',
    [
        {},
        {**envelope(), 'id': 'wrong'},
        {**envelope(), 'background': True},
        {'id': SNAPSHOT['request_id'], 'session_id': SNAPSHOT['session_id'], 'input': {'snapshot': SNAPSHOT}},
    ],
)
def test_invalid_invocation_never_reaches_model(monkeypatch, payload):
    async def forbidden(*args):
        pytest.fail('Invalid request reached agent')

    monkeypatch.setattr(main, 'invoke', forbidden)
    assert TestClient(main.app).post('/api/invocations', json=payload).status_code == 400


def test_completed_envelope(monkeypatch):
    async def fake(value, context):
        assert value == FIXTURE
        return {'plan': {'tool': 'recommend_continue', 'arguments': {}, 'reason': 'done'}}

    monkeypatch.setattr(main, 'invoke', fake)
    response = TestClient(main.app).post('/api/invocations', json=envelope())
    assert response.status_code == 200
    assert response.json() == {
        'id': SNAPSHOT['request_id'],
        'status': 'completed',
        'output': {'plan': {'tool': 'recommend_continue', 'arguments': {}, 'reason': 'done'}},
    }


@pytest.mark.parametrize('error,status', [(TimeoutError('internal timeout'), 504), (ValueError('secret context'), 502)])
def test_failures_do_not_leak_or_become_plans(monkeypatch, error, status):
    async def fail(*args):
        raise error

    monkeypatch.setattr(main, 'invoke', fail)
    response = TestClient(main.app).post('/api/invocations', json=envelope())
    assert response.status_code == status
    assert 'secret' not in response.text
    assert 'output' not in response.json()
