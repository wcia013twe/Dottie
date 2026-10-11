from contextlib import contextmanager
import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from magneto_research.config import ResearchConfig
from magneto_research.pipeline import Pipeline
from magneto_research.tracking import configure_tracking, resolve_experiment


class TrackingTests(unittest.TestCase):
    def setUp(self):
        self.config = ResearchConfig('https://example.com', 'workspace', 'magneto', 'references',
                                     experiment_name='/Shared/magneto-research', warehouse_id='w')
        self.client = Mock()
        self.client.config.host = self.config.workspace_host
        self.client.experiments.get_by_name.return_value.experiment = SimpleNamespace(
            experiment_id='updater', lifecycle_stage='active')

    def test_director_id_is_rejected_even_under_a_different_name(self):
        self.client.experiments.get_by_name.return_value.experiment.experiment_id = '948045133158359'
        with self.assertRaisesRegex(ValueError, 'director'):
            resolve_experiment(self.config, self.client)

    def test_wrong_uc_destination_fails_without_rebinding(self):
        from mlflow.entities.trace_location import UnityCatalog
        with patch('mlflow.active_run', return_value=None), patch('mlflow.set_tracking_uri'), \
             patch('mlflow.get_experiment', return_value=SimpleNamespace(
                 trace_location=UnityCatalog(catalog_name='other', schema_name='schema'))), \
             patch('mlflow.set_experiment') as select:
            with self.assertRaisesRegex(ValueError, 'configured UC schema'):
                configure_tracking(self.config, self.client, create=True)
            select.assert_not_called()

    def test_missing_experiment_does_not_implicitly_create(self):
        from databricks.sdk.errors import NotFound
        self.client.experiments.get_by_name.side_effect = NotFound('missing')
        with patch('mlflow.active_run', return_value=None), patch('mlflow.set_tracking_uri'), \
             patch('mlflow.create_experiment') as create:
            with self.assertRaisesRegex(ValueError, 'connect-experiment'):
                configure_tracking(self.config, self.client)
            create.assert_not_called()

    def test_tracking_ids_are_kept_when_processing_fails(self):
        @contextmanager
        def tracking(*args):
            yield {'mlflow_run_id': 'mlrun', 'trace_id': 'trace', 'experiment_id': 'updater'}
        db = Mock()
        pipeline = Pipeline(self.config, self.client, db, 'reviewer', 'updater')
        with patch('magneto_research.tracking.tracked_operation', tracking), \
             patch.object(pipeline, 'put') as put:
            with self.assertRaisesRegex(RuntimeError, 'processing failed'):
                with pipeline.run('extract', 'chunk'):
                    raise RuntimeError('processing failed')
        details = json.loads(put.call_args.args[1]['details'])
        self.assertEqual(details['mlflow_run_id'], 'mlrun')
        failure = db.execute.call_args.args[1]
        self.assertEqual(failure['status'], 'failed')
        self.assertEqual(json.loads(failure['details'])['initial']['trace_id'], 'trace')

    def test_dedicated_process_required(self):
        with patch('mlflow.active_run', return_value=object()):
            with self.assertRaisesRegex(ValueError, 'dedicated process'):
                configure_tracking(self.config, self.client)
        self.client.schemas.get.assert_not_called()


if __name__ == '__main__':
    unittest.main()
