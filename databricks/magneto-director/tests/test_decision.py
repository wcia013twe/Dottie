import copy
import json
from pathlib import Path

import pytest

from agent.decision import ContractError, decide, make_snapshot, validate_decision, validate_snapshot

FIXTURES = Path(__file__).parents[1] / 'fixtures'


def fixture(name='plum_incorrect'):
    return json.loads((FIXTURES / f'{name}.json').read_text())['snapshot']


def output(s, action='teach'):
    return dict(action=action, passage_id=s['passage_id'], target_letter='P' if action=='teach' else None,
                prompt='Feel the letter and identify it.' if action=='teach' else None,
                reason='The latest response supports this activity.',
                based_on_event_id=s['events'][-1]['event_id'] if s['events'] else None)


@pytest.mark.parametrize('name', ['apple','pear','plum_incorrect','plum_correct','plum_help'])
def test_fixtures_valid(name):
    assert validate_snapshot(fixture(name)) == fixture(name)


def test_one_call_and_no_outcome_override():
    s = fixture()
    calls=[]
    def completion(model, messages):
        calls.append((model, messages))
        return json.dumps(output(s, 'continue'))
    result = decide(s, completion=completion)
    assert len(calls)==1
    assert result['decision']['action']=='continue'  # Policy quality is evaluated, never hardcoded.
    assert json.loads(calls[0][1][1]['content']) == s
    assert result['request_id'] == s['request_id']


@pytest.mark.parametrize('key,value', [('action','inspect'),('passage_id','monday_apple'),
    ('target_letter','A'),('prompt',''),('reason',''),('based_on_event_id',None)])
def test_reject_bad_output(key,value):
    s=fixture(); d=output(s); d[key]=value
    with pytest.raises(ContractError): validate_decision(d,s)


def test_reject_extra_fields_and_continue_activity():
    s=fixture(); d=output(s); d['story_text']='replacement'
    with pytest.raises(ContractError): validate_decision(d,s)
    d=output(s); d['action']='continue'
    with pytest.raises(ContractError): validate_decision(d,s)


def test_malformed_model_no_retry():
    calls=[]
    def completion(*args): calls.append(1); return 'not json'
    with pytest.raises(ContractError): decide(fixture(),completion=completion)
    assert len(calls)==1


def test_no_implicit_context():
    s=fixture(); s['learner_history']['A']='upload private history'
    with pytest.raises(ContractError): validate_snapshot(s)


def test_duplicate_event_rejected():
    s=fixture(); s['events']*=2
    with pytest.raises(ContractError): validate_snapshot(s)


def test_future_events_rejected():
    s=fixture(); s['events'][0]['passage_id']='wednesday_plum'
    with pytest.raises(ContractError): validate_snapshot(s)


@pytest.mark.asyncio
async def test_runtime_session_and_request_checks(monkeypatch):
    from runtime import adapter
    from types import SimpleNamespace
    s=fixture(); emitted=[]
    async def emit(v): emitted.append(v)
    async def run(v, session_id):
        assert session_id==s['session_id']
        return {'decision':output(v)}
    monkeypatch.setattr(adapter,'run_agent',run)
    context=SimpleNamespace(invocation_id=s['request_id'],session_id=s['session_id'],emit=emit)
    assert (await adapter.invoke(s,context))['decision']['action']=='teach'
    assert len(emitted)==1
    context.invocation_id='wrong'
    with pytest.raises(ValueError): await adapter.invoke(s,context)


def test_model_uses_shared_platform_and_endpoint_override(monkeypatch):
    import magneto_platform
    from agent.decision import model_completion
    calls=[]
    class SharedAdapter:
        def __init__(self, config):
            assert config.model_endpoint == 'test-override'
            assert config.agent_app == 'agent-bricks-magneto-director'
        def complete(self, messages, **kwargs):
            calls.append((messages,kwargs))
            return {'choices':[{'message':{'content':'{}'}}]}
    monkeypatch.setattr(magneto_platform,'Services',SharedAdapter)
    assert model_completion('test-override',[{'role':'user','content':'test'}])=='{}'
    assert len(calls)==1
    assert calls[0][1]['response_format']['json_schema']['strict'] is True


def test_registry_prompt_and_immutable_boundary(monkeypatch):
    import agent.decision as module
    s = fixture(); calls = []
    monkeypatch.setattr(module, 'resolve_prompt', lambda uri: 'Candidate teaching policy')
    def completion(model, messages):
        calls.append(messages)
        return json.dumps(output(s))
    decide(s, completion=completion, prompt_uri='prompts:/workspace.magneto.story_orchestrator/1')
    assert calls[0][0]['content'].startswith('Candidate teaching policy')
    assert module.PROTOCOL_PROMPT in calls[0][0]['content']


def test_registry_failure_does_not_call_model(monkeypatch):
    import agent.decision as module
    def broken(uri): raise RuntimeError('Registry unavailable')
    monkeypatch.setattr(module, 'resolve_prompt', broken)
    def completion(*args): pytest.fail('Must not infer with a silently substituted policy')
    with pytest.raises(RuntimeError, match='Registry unavailable'):
        decide(fixture(), completion=completion, prompt_uri='configured')


@pytest.mark.asyncio
async def test_startup_checks_registry_access(monkeypatch):
    from runtime import main
    import mlflow
    monkeypatch.setattr(mlflow, 'trace', lambda **kwargs: lambda fn: fn)
    monkeypatch.setattr(mlflow, 'flush_trace_async_logging', lambda: None)
    monkeypatch.setenv('MAGNETO_PROMPT_URI', 'prompts:/workspace.magneto.story_orchestrator@champion')
    monkeypatch.setattr(main, 'configure', lambda: None)
    def unavailable(): raise RuntimeError('Registry denied')
    monkeypatch.setattr(main, 'resolve_prompt', unavailable)
    with pytest.raises(RuntimeError, match='Registry denied'):
        async with main.lifespan(main.app):
            pytest.fail('App must not become ready with a broken registry')
