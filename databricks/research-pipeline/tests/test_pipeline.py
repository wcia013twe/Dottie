import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from magneto_research.config import ResearchConfig
from magneto_research.pipeline import Pipeline
from magneto_research.storage import Warehouse


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.config = ResearchConfig('https://example.com', 'workspace', 'magneto', 'references',
            search_index='workspace.magneto.research_index', warehouse_id='warehouse')
        self.client, self.db = Mock(), Mock()
        self.p = Pipeline(self.config, self.client, self.db, 'test-reviewer')

    def response(self, hits):
        return {'manifest': {'columns': [{'name': n} for n in ['id', 'kind', 'score']]},
                'result': {'data_array': hits}}

    def test_stale_index_cannot_serve_withdrawn_evidence(self):
        self.client.vector_search_indexes.query_index.return_value.as_dict.return_value = self.response([
            ['withdrawn', 'finding', .99], ['current', 'finding', .8]])
        def execute(sql, params=None):
            if 'SELECT id, kind' in sql:
                return [{'id': 'current', 'kind': 'finding'}]
            return []
        self.db.execute.side_effect = execute
        with patch.object(self.p, 'audit', return_value={'id': 'current'}):
            result = self.p.search('task', 'teaching')
        self.assertEqual(result['matches'], [{'score': .8, 'record': {'id': 'current'}}])
        kwargs = self.client.vector_search_indexes.query_index.call_args.kwargs
        self.assertEqual(json.loads(kwargs['filters_json']), {'collection': 'teaching', 'tier': 'reviewed'})

    def test_lookup_failure_is_not_an_empty_result(self):
        self.client.vector_search_indexes.query_index.side_effect = RuntimeError('outage')
        with self.assertRaises(RuntimeError): self.p.search('task', 'industry')
        self.assertTrue(any(call.args[1].get('status') == 'failed'
                            for call in self.db.execute.call_args_list if len(call.args) > 1))

    def test_library_citations_are_fetched_in_one_current_status_read(self):
        self.client.vector_search_indexes.query_index.return_value.as_dict.return_value = self.response([
            ['withdrawn', 'passage', .99], ['current', 'passage', .8]])
        def execute(sql, params=None):
            if 'SELECT c.id' in sql:
                return [{'id': 'current', 'text': 'Original passage', 'locator': 'PDF page(s) 1',
                         'source': json.dumps({'id': 'version', 'title': 'Original source'}),
                         'produced_by': json.dumps({'id': 'parse-run'})}]
            return []
        self.db.execute.side_effect = execute
        with patch.object(self.p, 'audit') as audit:
            result = self.p.search('task', 'teaching', tier='library')
        audit.assert_not_called()
        self.assertEqual(len(result['matches']), 1)
        self.assertEqual(result['matches'][0]['record']['source']['id'], 'version')
        reads = [c for c in self.db.execute.call_args_list if 'SELECT c.id' in c.args[0]]
        self.assertEqual(len(reads), 1)
        self.assertEqual(json.loads(reads[0].args[1]['ids']), ['withdrawn', 'current'])

    def test_nonfinite_scores_fail(self):
        self.client.vector_search_indexes.query_index.return_value.as_dict.return_value = self.response([
            ['current', 'finding', float('nan')]])
        with self.assertRaises((ValueError, RuntimeError)): self.p.search('task', 'teaching')

    def test_recommendation_cannot_use_unaccepted_finding(self):
        body = {'text': 'Try A', 'finding_ids': ['unreviewed'], 'rationale': 'Reason',
                'limitations': 'Limited', 'target_letters': [], 'difficulty_tags': []}
        with patch.object(self.p, 'get', side_effect=ValueError('Not eligible')), \
             patch.object(self.p, 'put') as put:
            with self.assertRaises(ValueError): self.p.draft(body)
            put.assert_not_called()

    def test_failed_extraction_leaves_no_reviewable_findings(self):
        chunk = {'text': 'Real source text'}
        self.db.execute.return_value = [{'output': json.dumps({'error_message': 'failed'})}]
        with patch.object(self.p, 'get', return_value=chunk), patch.object(self.p, 'put') as put:
            with self.assertRaises(ValueError): self.p.extract('chunk')
        self.assertEqual([c.args[0] for c in put.call_args_list], ['runs'])

    def test_partial_candidate_rejection_is_explicit_and_cannot_save_bad_quotes(self):
        good = {'statement': 'A reported result', 'quote': 'real source',
                'context': 'Context not reported', 'limitations': 'No comparator'}
        bad = {**good, 'quote': 'invented claim'}
        self.db.execute.return_value = [{'output': json.dumps({'response': {'findings': [good, bad]}})}]
        with patch.object(self.p, 'get', return_value={'text': 'Some real source text'}), \
             patch.object(self.p, 'put') as put, patch.object(self.p, 'artifact') as artifact:
            result = self.p.extract('chunk')
        stored = [c.args[1] for c in put.call_args_list if c.args[0] == 'findings']
        self.assertEqual(len(stored), 1)
        self.assertEqual(json.loads(stored[0]['body'])['quote'], 'real source')
        self.assertEqual(result['rejected_candidates'], 1)
        self.assertEqual(result['review_status'], 'needs_review')
        self.assertEqual(artifact.call_args_list[-1].args[1], 'validation')

    def test_null_extraction_is_an_explicit_failure(self):
        self.db.execute.return_value = [{'output': 'null'}]
        with patch.object(self.p, 'get', return_value={'text': 'source'}):
            with self.assertRaises(ValueError): self.p.extract('chunk')

    def test_review_action_is_bound_to_record_kind(self):
        with self.assertRaises(ValueError): self.p.review('finding', 'id', 'approved', 'reason')
        self.db.execute.assert_not_called()

    def test_export_requires_current_eligibility(self):
        with patch.object(self.p, 'get', side_effect=ValueError('Withdrawn')) as get:
            with self.assertRaises(ValueError): self.p.export('rec')
            get.assert_called_once_with('eligible_recommendations', 'rec')

    def test_search_validates_before_remote_call(self):
        for limit in (0, True, 21):
            with self.assertRaises(ValueError): self.p.search('q', 'teaching', limit=limit)
        self.client.vector_search_indexes.query_index.assert_not_called()


class WarehouseTests(unittest.TestCase):
    def test_parameters_are_bound_not_interpolated(self):
        config = ResearchConfig('https://example.com', 'a', 'b', 'c', warehouse_id='w')
        client = Mock()
        client.statement_execution.execute_statement.return_value = SimpleNamespace(
            status=SimpleNamespace(state=SimpleNamespace(value='SUCCEEDED')), manifest=None, result=None)
        warehouse = Warehouse(client, config)
        warehouse.execute('SELECT :text', {'text': "x'; DROP TABLE sources; --"})
        call = client.statement_execution.execute_statement.call_args
        self.assertEqual(call.args[0], 'SELECT :text')
        self.assertEqual(call.kwargs['parameters'][0].value, "x'; DROP TABLE sources; --")

    def test_truncated_sql_results_fail_closed(self):
        config = ResearchConfig('https://example.com', 'a', 'b', 'c', warehouse_id='w')
        client = Mock()
        client.statement_execution.execute_statement.return_value = SimpleNamespace(
            status=SimpleNamespace(state=SimpleNamespace(value='SUCCEEDED')),
            manifest=SimpleNamespace(truncated=True))
        with self.assertRaises(RuntimeError): Warehouse(client, config).execute('SELECT 1')


if __name__ == '__main__': unittest.main()
