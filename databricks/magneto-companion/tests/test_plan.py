import json
from pathlib import Path

import pytest

from agent.plan import ContractError, decide, response_format, validate_plan

FIXTURE = json.loads((Path(__file__).parents[1] / 'fixtures/companion_snapshot.json').read_text())
SNAPSHOT = FIXTURE['snapshot']
TOOLS = FIXTURE['available_mcp_tools']


def valid_plan():
    return {
        'tool': 'present_activity',
        'arguments': {
            'session_id': SNAPSHOT['session_id'],
            'revision': SNAPSHOT['revision'],
            'target': 'c',
            'activity': 'identify',
            'prompt': 'Feel the letter and say it.',
        },
        'reason': 'Present the current target.',
    }


def test_response_format_pins_discovered_tools():
    schema = response_format(TOOLS)['json_schema']['schema']
    names = [option['properties']['tool']['const'] for option in schema['oneOf']]
    assert names == ['present_activity', 'recommend_continue']


def test_decide_returns_validated_plan():
    result = decide(SNAPSHOT, TOOLS, completion=lambda *args: json.dumps(valid_plan()))
    assert result['plan']['tool'] == 'present_activity'
    assert result['plan']['arguments']['target'] == 'c'
    assert result['session_id'] == SNAPSHOT['session_id']


@pytest.mark.parametrize(
    'plan',
    [
        {'tool': 'record_outcome', 'arguments': {}, 'reason': 'x'},
        {**valid_plan(), 'arguments': {**valid_plan()['arguments'], 'revision': 99}},
        {**valid_plan(), 'arguments': {**valid_plan()['arguments'], 'target': 'z'}},
        {**valid_plan(), 'arguments': {**valid_plan()['arguments'], 'session_id': 'other'}},
    ],
)
def test_validate_plan_rejects_bad_plans(plan):
    with pytest.raises(ContractError):
        validate_plan(plan, SNAPSHOT)


def test_decide_rejects_non_json():
    with pytest.raises(ContractError):
        decide(SNAPSHOT, TOOLS, completion=lambda *args: 'not json')
