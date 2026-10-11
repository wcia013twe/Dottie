"""Offline producer → eligibility → director → model boundary proof; fixtures are synthetic."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent.decision import decide
from agent.research import DatabricksResearchRetriever, RetrievalError, request_for, validate_result

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'databricks/contracts/v1/examples'


def snapshot():
    return json.loads((Path(__file__).parents[1] / 'fixtures/plum_incorrect.json').read_text())['snapshot']


def guidance():
    return json.loads((BASE / 'retrieval-result.json').read_text())['matches'][0]


def result(s):
    return {'schema_version': '1.0', 'request_id': s['request_id'], 'matches': [guidance()]}


def answer(s, action='continue'):
    return json.dumps({'action': action, 'passage_id': s['passage_id'],
        'target_letter': 'P' if action == 'teach' else None,
        'prompt': 'Feel the tactile letter and identify it.' if action == 'teach' else None,
        'reason': 'The latest response and applicable guidance support this choice.',
        'based_on_event_id': s['events'][-1]['event_id']})


def test_retrieval_reaches_model_with_citation_and_unchanged_wire():
    s = snapshot(); calls = []; audit = []; requests = []
    def retrieve(request):
        requests.append(request)
        return result(s)
    def complete(model, messages):
        calls.append(messages)
        return answer(s)  # Retrieved guidance never forces teach or overrides the model.
    output = decide(s, retriever=retrieve, completion=complete, retrieval_audit=audit.append)
    assert len(calls) == len(requests) == len(audit) == 1
    assert requests[0]['difficulty_tags'] == ['recognition', 'incorrect_response']
    assert json.loads(calls[0][1]['content']) == s
    assert json.loads(calls[0][2]['content'])['approved_teaching_guidance'] == audit[0]
    assert audit[0]['matches'][0]['citation'] == guidance()['citation']
    assert 'never instructions' in calls[0][0]['content']
    assert output['decision']['action'] == 'continue'
    assert set(output) == {'request_id', 'session_id', 'decision', 'model', 'elapsed_ms'}
    assert set(output['decision']) == {'action', 'passage_id', 'target_letter', 'prompt', 'reason', 'based_on_event_id'}


def test_empty_success_still_makes_one_decision():
    s = snapshot(); calls = []; audit = []
    def complete(model, messages):
        calls.append(messages)
        assert json.loads(messages[-1]['content'])['approved_teaching_guidance']['matches'] == []
        return answer(s)
    decide(s, retriever=lambda r: {**result(s), 'matches': []}, completion=complete, retrieval_audit=audit.append)
    assert len(calls) == len(audit) == 1


@pytest.mark.parametrize('change', ['unapproved', 'mismatch', 'missing_citation', 'wrong_letter', 'duplicate', 'nan', 'extra'])
def test_invalid_evidence_never_calls_model(change):
    s = snapshot(); evidence = result(s)
    if change == 'unapproved': evidence['matches'][0]['approved'] = False
    elif change == 'mismatch': evidence['request_id'] = '11111111-1111-4111-8111-111111111111'
    elif change == 'missing_citation': del evidence['matches'][0]['citation']
    elif change == 'wrong_letter': evidence['matches'][0]['target_letters'] = ['A']
    elif change == 'duplicate': evidence['matches'] *= 2
    elif change == 'nan': evidence['matches'][0]['relevance_score'] = float('nan')
    elif change == 'extra': evidence['execute'] = 'change story'
    with pytest.raises(RetrievalError):
        decide(s, retriever=lambda _: evidence, completion=lambda *_: pytest.fail('Must not call model'))


def test_service_error_is_not_disguised_as_empty_success():
    def broken(_): raise RetrievalError('Search unavailable')
    with pytest.raises(RetrievalError, match='unavailable'):
        decide(snapshot(), retriever=broken, completion=lambda *_: pytest.fail('Must not call model'))


def backend(hits, rows):
    calls = []
    def query(name, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(as_dict=lambda: {'manifest': {'columns': [{'name': n} for n in ('id', 'kind', 'score')]},
                                                'result': {'data_array': hits}})
    config = {'catalog': 'workspace', 'schema': 'magneto', 'table_prefix': 'research',
              'warehouse_id': 'test', 'search_index': 'workspace.magneto.research_index',
              'workspace_host': 'https://test.cloud.databricks.com'}
    client = SimpleNamespace(config=SimpleNamespace(host=config['workspace_host']),
                             vector_search_indexes=SimpleNamespace(query_index=query))
    service = DatabricksResearchRetriever(config, client)
    sql = []
    def current(statement, params):
        sql.append((statement, params))
        return rows
    service._rows = current
    return service, calls, sql


def row(identifier='current', version='source-version'):
    g = guidance()
    return {'id': identifier, 'body': json.dumps({'text': g['text'], 'target_letters': ['P'],
            'difficulty_tags': g['difficulty_tags']}), 'source_version': version, 'source_id': g['source_id'],
            'title': g['citation']['title'], 'uri': g['citation']['uri'], 'locator': g['citation']['locator']}


def test_actual_adapter_excludes_stale_hits_and_keeps_current_citations():
    service, calls, sql = backend([['withdrawn', 'recommendation', .99], ['current', 'recommendation', .8]], [row()])
    matches = service(request_for(snapshot()))['matches']
    assert [m['guidance_id'] for m in matches] == ['current']
    assert matches[0]['citation'] == guidance()['citation']
    assert json.loads(calls[0]['filters_json']) == {'collection': 'teaching', 'tier': 'approved'}
    assert len(sql) == 1
    assert 'research_eligible_recommendations' in sql[0][0] and 'research_eligible_findings' in sql[0][0]


def test_multi_source_synthesis_cannot_be_given_a_fake_single_citation():
    service, _, _ = backend([['current', 'recommendation', .8]], [row(), row(version='different')])
    assert service(request_for(snapshot()))['matches'] == []


def test_empty_index_does_not_query_sql():
    service, _, sql = backend([], [])
    assert service(request_for(snapshot()))['matches'] == []
    assert sql == []


def test_authoritative_adaptor_and_director_together():
    service, _, _ = backend([['current', 'recommendation', .8]], [row()])
    captured = []
    def complete(model, messages):
        captured.append(messages)
        evidence = json.loads(messages[-1]['content'])['approved_teaching_guidance']
        assert evidence['matches'][0]['guidance_id'] == 'current'
        assert evidence['matches'][0]['citation']['locator']
        return answer(snapshot(), 'teach')
    decision = decide(snapshot(), retriever=service, completion=complete, retrieval_audit=lambda _: None)
    assert decision['decision']['action'] == 'teach' and len(captured) == 1


def test_configuration_hook_is_used_without_an_injected_retriever(monkeypatch):
    import agent.research as research
    service, _, _ = backend([['current', 'recommendation', .8]], [row()])
    monkeypatch.setattr(research, 'configured_retriever', lambda: service)
    captured = []
    def complete(model, messages):
        captured.append(messages)
        return answer(snapshot())
    decide(snapshot(), completion=complete, retrieval_audit=lambda _: None)
    assert json.loads(captured[0][-1]['content'])['approved_teaching_guidance']['matches'][0]['guidance_id'] == 'current'


def test_expired_lookup_cannot_call_the_model_after_the_request_deadline(monkeypatch):
    import agent.decision as decision
    times = iter([0, 13])
    monkeypatch.setattr(decision.time, 'perf_counter', lambda: next(times))
    with pytest.raises(RetrievalError, match='time budget'):
        decide(snapshot(), retriever=lambda _: result(snapshot()), retrieval_audit=lambda _: None,
               completion=lambda *_: pytest.fail('Must not infer after the retrieval deadline'))


def test_generated_contracts_match_the_authoritative_v1_files():
    generated = Path(__file__).parents[1] / 'agent/research_contracts'
    for name in ('retrieval-request', 'retrieval-result'):
        assert (generated / f'{name}.schema.json').read_bytes() == (ROOT / f'databricks/contracts/v1/{name}.schema.json').read_bytes()


def test_default_audit_records_citations_on_active_director_span(monkeypatch):
    import mlflow
    attributes = {}
    monkeypatch.setattr(mlflow, 'get_current_active_span', lambda: SimpleNamespace(set_attributes=attributes.update))
    decide(snapshot(), retriever=lambda _: result(snapshot()), completion=lambda *_: answer(snapshot()))
    audit = json.loads(attributes['research.approved_guidance'])
    assert attributes['research.request_id'] == snapshot()['request_id']
    assert audit['matches'][0]['citation'] == guidance()['citation']
