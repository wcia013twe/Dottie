from contextlib import redirect_stdout
import io
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from magneto_research.config import ResearchConfig
from magneto_research.connections import check_services
from magneto_research.smoke import main, run


class SmokeTests(unittest.TestCase):
    def setUp(self):
        self.config = ResearchConfig('https://example.com', 'workspace', 'magneto', 'references')
        self.client = SimpleNamespace(config=SimpleNamespace(host='https://example.com'),
                                      catalogs=Mock(spec=['get']), schemas=Mock(spec=['get']),
                                      volumes=Mock(spec=['read']))

    def test_required_reads_and_optional_services(self):
        report = check_services(self.config, self.client)
        self.assertEqual(report['source_volume']['status'], 'reachable')
        self.assertEqual(report['mlflow']['status'], 'not_configured')
        self.assertEqual(report['ai_search']['status'], 'not_configured')
        self.client.volumes.read.assert_called_once_with('workspace.magneto.references')

    def test_workspace_mismatch_prevents_reads(self):
        self.client.config.host = 'https://other.example.com'
        with self.assertRaises(ValueError):
            check_services(self.config, self.client)
        self.client.catalogs.get.assert_not_called()

    def test_failure_redacts_messages_and_checks_other_services(self):
        self.client.catalogs.get.side_effect = RuntimeError('private-secret')
        report = check_services(self.config, self.client)
        self.assertEqual(report['catalog']['status'], 'failed')
        self.assertNotIn('private-secret', str(report))
        self.assertEqual(report['schema']['status'], 'reachable')

    def test_explicit_optional_resources_are_checked(self):
        config = ResearchConfig('https://example.com', 'workspace', 'magneto', 'references',
                                '/Shared/research', 'workspace.magneto.research')
        self.client.experiments = Mock(spec=['get_by_name'])
        self.client.vector_search_indexes = Mock(spec=['get_index'])
        self.client.vector_search_indexes.get_index.side_effect = RuntimeError('not ready')
        report = check_services(config, self.client)
        self.assertEqual(report['mlflow']['status'], 'reachable')
        self.assertEqual(report['ai_search']['status'], 'failed')

    def test_cli_auth_failure_exits_nonzero_without_credentials(self):
        output = io.StringIO()
        with patch('magneto_research.smoke.ResearchConfig.load', return_value=self.config), \
             patch('magneto_research.smoke.connect', side_effect=RuntimeError('private-secret')), \
             redirect_stdout(output):
            result = main(['--config', 'unused', '--profile', 'magneto'])
        self.assertEqual(result, 1)
        self.assertNotIn('private-secret', output.getvalue())

    def test_job_entry_point_propagates_failure(self):
        with patch('magneto_research.smoke.main', return_value=1):
            with self.assertRaises(SystemExit) as failure:
                run()
        self.assertEqual(failure.exception.code, 1)

    def test_successful_wheel_task_returns_normally(self):
        with patch('magneto_research.smoke.main', return_value=0):
            self.assertIsNone(run())
