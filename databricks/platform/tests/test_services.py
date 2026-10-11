import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from databricks.sdk.errors import NotFound, PermissionDenied, ResourceAlreadyExists
from magneto_platform import ServiceConfig, Services


class ServicesTest(unittest.TestCase):
    def setUp(self):
        self.config = ServiceConfig.load(Path(__file__).resolve().parents[1] / 'services.toml')
        self.client = MagicMock()
        self.client.config.host = self.config.workspace_host
        self.client.config.authenticate.return_value = {'Authorization': 'Bearer test-secret'}
        self.http = MagicMock()
        self.http.post.return_value.status_code = 200
        self.http.post.return_value.json.return_value = {'output': {'arbitrary': True}}
        self.services = Services(self.config, client=self.client, http=self.http)

    def test_existing_resources_are_not_recreated(self):
        report = self.services.provision()
        self.assertEqual(report['schema'], 'existing')
        self.client.schemas.create.assert_not_called()
        self.client.volumes.create.assert_not_called()
        self.client.experiments.create_experiment.assert_not_called()
        self.client.apps.create.assert_not_called()

    def test_missing_resources_are_created_then_read(self):
        self.client.schemas.get.side_effect = [NotFound('missing'), SimpleNamespace(full_name='workspace.magneto')]
        self.services.provision()
        self.client.schemas.create.assert_called_once()
        self.assertEqual(self.client.schemas.get.call_count, 2)

    def test_creation_race_reuses_winner(self):
        get, create = MagicMock(), MagicMock()
        get.side_effect = [NotFound('missing'), 'winner']
        create.side_effect = ResourceAlreadyExists('race')
        self.assertEqual(Services._ensure(get, create), ('winner', 'ready'))

    def test_permission_failure_is_not_treated_as_missing(self):
        self.client.schemas.get.side_effect = PermissionDenied('private detail')
        with self.assertRaises(PermissionDenied):
            self.services.provision()
        self.client.schemas.create.assert_not_called()

    def test_wrong_workspace_is_rejected(self):
        self.client.config.host = 'https://different.example.com'
        with self.assertRaises(ValueError):
            Services(self.config, client=self.client)

    def test_local_pat_uses_unified_auth_environment(self):
        import os
        client = MagicMock()
        client.config.host = self.config.workspace_host
        with patch.dict(os.environ, {'DATABRICKS_HOST': self.config.workspace_host,
                                     'DATABRICKS_TOKEN': 'test-token'}, clear=True), \
             patch('magneto_platform.services.WorkspaceClient', return_value=client) as workspace_client:
            Services(self.config)
        workspace_client.assert_called_once_with()

    def test_reference_paths_stay_in_volume(self):
        for path in ('', '../secret', '/etc/passwd', 'a/../b', 'a//b', 'a/./b', 'a\\b'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.services.reference_path(path)
        self.assertEqual(self.services.reference_path('paper.pdf'), self.config.volume_path + '/paper.pdf')

    def test_upload_is_explicit_and_non_overwriting(self):
        self.services.upload_reference('paper.txt', b'example reference')
        args, kwargs = self.client.files.upload.call_args
        self.assertEqual(args[1].getvalue(), b'example reference')
        self.assertFalse(kwargs['overwrite'])

    def test_single_model_call_preserves_generic_contract(self):
        messages = [{'role': 'user', 'content': 'test'}]
        result = self.services.complete(messages)
        self.assertEqual(result, {'output': {'arbitrary': True}})
        self.http.post.assert_called_once()
        kwargs = self.http.post.call_args.kwargs
        self.assertEqual(kwargs['json']['messages'], messages)
        self.assertFalse(kwargs['allow_redirects'])

    def test_invocation_retains_request_and_session_ids(self):
        self.client.apps.get.return_value.url = 'https://example.databricksapps.com'
        session, request = str(uuid4()), str(uuid4())
        self.services.invoke_agent({'future_contract': 1}, session_id=session, request_id=request)
        kwargs = self.http.post.call_args.kwargs
        self.assertEqual(kwargs['json'], {'id': request, 'session_id': session, 'input': {'future_contract': 1}})
        self.assertEqual(kwargs['headers']['X-Routing-Key'], session)

    def test_unsafe_agent_url_is_rejected(self):
        self.client.apps.get.return_value.url = 'http://example.com'
        with self.assertRaises(ValueError):
            self.services.invoke_agent({}, session_id=str(uuid4()), request_id=str(uuid4()))
        self.http.post.assert_not_called()

    def test_upstream_body_not_exposed_on_error(self):
        self.http.post.return_value.status_code = 403
        self.http.post.return_value.text = 'test-secret'
        with self.assertRaisesRegex(RuntimeError, '^Databricks returned HTTP 403$'):
            self.services.complete([])
        self.http.post.assert_called_once()

    def test_wire_adds_narrow_permissions_without_updating_app(self):
        self.client.apps.get.return_value.service_principal_client_id = 'test-principal'
        self.services.wire_app_permissions()
        self.assertEqual(self.client.grants.update.call_count, 7)
        table_calls = [c for c in self.client.grants.update.call_args_list if c.args[0]=='table']
        self.assertEqual(len(table_calls), 4)
        for call in table_calls:
            self.assertTrue(call.args[1].startswith('workspace.magneto.948045133158359_otel_'))
            self.assertEqual({p.value for p in call.kwargs['changes'][0].add}, {'SELECT','MODIFY'})
        for call in self.client.grants.update.call_args_list:
            self.assertIsNone(call.kwargs['changes'][0].remove)
        self.client.apps.update.assert_not_called()
        self.client.apps.deploy.assert_not_called()
        self.client.serving_endpoints.update_permissions.assert_called_once()
        self.client.experiments.update_permissions.assert_called_once()

    def test_system_model_has_no_endpoint_acl(self):
        endpoint = self.client.serving_endpoints.get.return_value
        endpoint.id = None
        endpoint.config.served_entities = [SimpleNamespace(foundation_model=object())]
        result = self.services.wire_app_permissions()
        self.assertIn('existing workspace policy', result['model_access'])
        self.client.serving_endpoints.update_permissions.assert_not_called()
        self.client.experiments.update_permissions.assert_called_once()

    def test_tracing_pins_sql_profile_and_verifies_uc_destination(self):
        import os
        from unittest.mock import patch
        from mlflow.entities.trace_location import UnityCatalog
        expected=UnityCatalog(catalog_name=self.config.catalog,schema_name=self.config.schema,
                              table_prefix=self.config.trace_table_prefix)
        with patch.dict(os.environ,{},clear=True), \
             patch('mlflow.set_tracking_uri') as tracking, \
             patch('mlflow.set_experiment',return_value=SimpleNamespace(trace_location=expected)):
            self.services.configure_tracing()
            tracking.assert_called_once_with('databricks://magneto')
            self.assertEqual(os.environ['DATABRICKS_CONFIG_PROFILE'],'magneto')
            self.assertEqual(os.environ['MLFLOW_TRACING_SQL_WAREHOUSE_ID'],self.config.trace_warehouse_id)

    def test_tracing_refuses_legacy_destination_when_uc_configured(self):
        import os
        from unittest.mock import patch
        with patch.dict(os.environ,{},clear=True), \
             patch('mlflow.set_tracking_uri'), \
             patch('mlflow.set_experiment',return_value=SimpleNamespace(trace_location=None)):
            with self.assertRaisesRegex(ValueError,'does not match'):
                self.services.configure_tracing()


if __name__ == '__main__':
    unittest.main()
