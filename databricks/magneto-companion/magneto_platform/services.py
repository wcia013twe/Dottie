"""Resources and transport only; learning-data contracts belong to the application."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import io
import os
from pathlib import Path, PurePosixPath
import re
import tomllib
from urllib.parse import quote, urlparse
from uuid import UUID

from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import AlreadyExists, NotFound, ResourceAlreadyExists
from databricks.sdk.service import catalog, ml, serving
import requests


@dataclass(frozen=True)
class ServiceConfig:
    profile: str
    workspace_host: str
    catalog: str
    schema: str
    reference_volume: str
    model_endpoint: str
    experiment_name: str
    agent_app: str
    trace_table_prefix: str | None = None
    trace_warehouse_id: str | None = None
    learning_warehouse_id: str | None = None

    @classmethod
    def load(cls, path):
        with open(path, 'rb') as file:
            config = cls(**tomllib.load(file))
        for value in (config.catalog, config.schema, config.reference_volume):
            if not re.fullmatch(r'[a-z][a-z0-9_]*', value):
                raise ValueError('Catalog, schema and volume must be simple lowercase identifiers')
        host = urlparse(config.workspace_host)
        if host.scheme != 'https' or not host.hostname or host.path not in ('', '/') or host.query or host.fragment or host.username or host.password:
            raise ValueError('workspace_host must be an HTTPS origin')
        if not config.experiment_name.startswith('/'):
            raise ValueError('experiment_name must be an absolute workspace path')
        if config.trace_table_prefix is not None and not re.fullmatch(r'[a-zA-Z0-9_]+', config.trace_table_prefix):
            raise ValueError('Trace table prefix must be a simple identifier')
        return config

    @property
    def schema_name(self):
        return f'{self.catalog}.{self.schema}'

    @property
    def volume_name(self):
        return f'{self.schema_name}.{self.reference_volume}'

    @property
    def volume_path(self):
        return f'/Volumes/{self.catalog}/{self.schema}/{self.reference_volume}'


class Services:
    def __init__(self, config: ServiceConfig, *, client=None, http=None):
        self.config = config
        # Deployed Apps resolve their injected service identity. Local use selects the profile.
        self.client = client if client is not None else WorkspaceClient(
            **({} if os.getenv('DATABRICKS_APP_NAME') else {'profile': config.profile}))
        if self.client.config.host.rstrip('/') != config.workspace_host.rstrip('/'):
            raise ValueError('Authenticated workspace does not match services.toml')
        self.http = http or requests.Session()

    @staticmethod
    def _ensure(get, create):
        try:
            return get(), 'existing'
        except NotFound:
            try:
                create()
            except (AlreadyExists, ResourceAlreadyExists):
                # Another provisioning process won the race. Never replace its resource.
                pass
            return get(), 'ready'

    def provision(self):
        """Create missing containers only. No tables, uploads, deployments, or deletes."""
        w, c = self.client, self.config
        w.catalogs.get(c.catalog)  # Reuse existing managed catalog; never change ownership.
        report = {}
        _, report['schema'] = self._ensure(
            lambda: w.schemas.get(c.schema_name),
            lambda: w.schemas.create(c.schema, c.catalog, comment='Magneto research and learning data; application tables deferred.'))
        _, report['references'] = self._ensure(
            lambda: w.volumes.read(c.volume_name),
            lambda: w.volumes.create(c.catalog, c.schema, c.reference_volume,
                                    catalog.VolumeType.MANAGED, comment='Magneto explicitly uploaded source references.'))
        parent = str(PurePosixPath(c.experiment_name).parent)
        w.workspace.mkdirs(parent)
        exp, report['experiment'] = self._ensure(
            lambda: w.experiments.get_by_name(c.experiment_name),
            lambda: w.experiments.create_experiment(c.experiment_name))
        report['experiment_id'] = exp.experiment.experiment_id
        report['volume_path'] = c.volume_path
        return report

    def status(self):
        """Read-only. Checks resource access without running an inference or uploading data."""
        w, c = self.client, self.config
        checks = {
            'schema': lambda: {'name': w.schemas.get(c.schema_name).full_name},
            'references': lambda: {'name': w.volumes.read(c.volume_name).full_name, 'path': c.volume_path},
            'model': lambda: self._model_status(),
            'tracing': lambda: {'experiment_id': w.experiments.get_by_name(c.experiment_name).experiment.experiment_id},
            'agent': lambda: self._app_status(),
        }
        report = {}
        for name, check in checks.items():
            try:
                report[name] = {'status': 'reachable', **check()}
            except NotFound:
                report[name] = {'status': 'not_provisioned'}
            except Exception as exc:
                # SDK messages can include sensitive request context. Report type only.
                report[name] = {'status': 'error', 'error_type': type(exc).__name__}
        return report

    def _model_status(self):
        endpoint = self.client.serving_endpoints.get(self.config.model_endpoint)
        return {'endpoint': endpoint.name, 'state': endpoint.state.as_dict() if endpoint.state else {}}

    def _app_status(self):
        app = self.client.apps.get(self.config.agent_app)
        return {'name': app.name, 'url': app.url,
                'compute': app.compute_status.as_dict() if app.compute_status else {},
                'app': app.app_status.as_dict() if app.app_status else {}}

    def wire_app_permissions(self):
        """Add narrow access to the existing app identity; never create/update/deploy the app."""
        w, c = self.client, self.config
        app = w.apps.get(c.agent_app)
        principal = app.service_principal_client_id
        if not principal:
            raise ValueError('App service identity is not available yet')
        for kind, name, privileges in (
            ('catalog', c.catalog, [catalog.Privilege.USE_CATALOG]),
            ('schema', c.schema_name, [catalog.Privilege.USE_SCHEMA]),
            ('volume', c.volume_name, [catalog.Privilege.READ_VOLUME]),
        ):
            w.grants.update(kind, name, changes=[catalog.PermissionsChange(principal=principal, add=privileges)])
        endpoint = w.serving_endpoints.get(c.model_endpoint)
        if endpoint.id:
            w.serving_endpoints.update_permissions(endpoint.id, access_control_list=[
                serving.ServingEndpointAccessControlRequest(service_principal_name=principal,
                                                           permission_level=serving.ServingEndpointPermissionLevel.CAN_QUERY)])
            model_access = 'CAN_QUERY added'
        elif endpoint.config and any(entity.foundation_model for entity in endpoint.config.served_entities or []):
            # System pay-per-token models have no endpoint ACL ID. Their access follows
            # workspace/model governance; do not send a bogus ID or change account policy.
            model_access = 'system foundation model: existing workspace policy; no endpoint ACL to modify'
        else:
            raise ValueError('Cannot resolve model access: endpoint has no ACL ID or foundation model')
        exp = w.experiments.get_by_name(c.experiment_name).experiment
        w.experiments.update_permissions(exp.experiment_id, access_control_list=[
            ml.ExperimentAccessControlRequest(service_principal_name=principal,
                                              permission_level=ml.ExperimentPermissionLevel.CAN_EDIT)])
        if c.trace_table_prefix:
            for suffix in ('otel_spans', 'otel_logs', 'otel_metrics', 'otel_annotations'):
                w.grants.update('table', f'{c.schema_name}.{c.trace_table_prefix}_{suffix}', changes=[
                    catalog.PermissionsChange(principal=principal,
                                              add=[catalog.Privilege.SELECT, catalog.Privilege.MODIFY])])
        return {'app': app.name, 'principal': principal, 'grants': 'added',
                'reference_access': 'read-only', 'model_access': model_access, 'trace_access': 'edit'}

    def _post(self, url, payload, *, timeout_s, headers=None):
        # URLs originate only from trusted config / workspace app metadata, never caller input.
        response = self.http.post(url, json=payload,
                                  headers={**self.client.config.authenticate(), **(headers or {})},
                                  timeout=(3, timeout_s), allow_redirects=False)
        if not 200 <= response.status_code < 300:
            raise RuntimeError(f'Databricks returned HTTP {response.status_code}')
        return response.json()

    def complete(self, messages, *, response_format=None, max_tokens=350, timeout_s=12):
        """One model request, no retries. Caller owns prompts and output validation."""
        payload = {'messages': messages, 'max_tokens': max_tokens, 'temperature': 0}
        if response_format is not None:
            payload['response_format'] = response_format
        return self._post(f'{self.config.workspace_host}/serving-endpoints/{quote(self.config.model_endpoint, safe="")}/invocations',
                          payload, timeout_s=timeout_s)

    def invoke_agent(self, payload, *, session_id, request_id, timeout_s=12):
        """Opaque application input through the Agent Bricks invocation envelope."""
        for value in (session_id, request_id):
            if str(UUID(value)) != value:
                raise ValueError('Session and request IDs must be canonical UUIDs')
        app = self.client.apps.get(self.config.agent_app)
        address = urlparse(app.url or '')
        if address.scheme != 'https' or not address.hostname or address.username or address.password:
            raise ValueError('App does not have a valid HTTPS URL yet')
        return self._post(app.url.rstrip('/') + '/api/invocations',
                          {'id': request_id, 'session_id': session_id, 'input': payload},
                          timeout_s=timeout_s, headers={'X-Routing-Key': session_id})

    def ingest_learning_events(self, payload, *, profile_id, timeout_s=12):
        """Send validated browser events to the learning endpoint without exposing credentials."""
        if str(UUID(profile_id)) != profile_id:
            raise ValueError('Profile ID must be a canonical UUID')
        app = self.client.apps.get(self.config.agent_app)
        address = urlparse(app.url or '')
        if address.scheme != 'https' or not address.hostname or address.username or address.password:
            raise ValueError('App does not have a valid HTTPS URL yet')
        return self._post(app.url.rstrip('/') + '/api/learning/events', payload,
                          timeout_s=timeout_s, headers={'X-Profile-Key': profile_id})

    def ingest_learning_attempts(self, payload, *, timeout_s=30):
        profile_id = payload['profile_id']
        if str(UUID(profile_id)) != profile_id:
            raise ValueError('Profile ID must be a canonical UUID')
        app = self.client.apps.get(self.config.agent_app)
        address = urlparse(app.url or '')
        if address.scheme != 'https' or not address.hostname or address.username or address.password:
            raise ValueError('App does not have a valid HTTPS URL yet')
        return self._post(app.url.rstrip('/') + '/api/learning/attempts', payload,
                          timeout_s=timeout_s, headers={'X-Profile-Key': profile_id})

    def create_learning_profile(self, profile, *, timeout_s=12):
        profile_id = profile.get('profile_id') if isinstance(profile, dict) else None
        if not isinstance(profile_id, str) or str(UUID(profile_id)) != profile_id:
            raise ValueError('Profile ID must be a canonical UUID')
        app = self.client.apps.get(self.config.agent_app)
        address = urlparse(app.url or '')
        if address.scheme != 'https' or not address.hostname or address.username or address.password:
            raise ValueError('App does not have a valid HTTPS URL yet')
        return self._post(app.url.rstrip('/') + '/api/learning/profile', profile,
                          timeout_s=timeout_s, headers={'X-Profile-Key': profile_id})

    def reference_path(self, relative_path):
        path = PurePosixPath(relative_path)
        if not relative_path or path.is_absolute() or any(part in ('', '.', '..') for part in relative_path.split('/')) or '\\' in relative_path:
            raise ValueError('Reference path must be relative, without traversal')
        return self.config.volume_path + '/' + path.as_posix()

    def upload_reference(self, relative_path, contents: bytes):
        """Explicit upload only; existing files are never overwritten."""
        path = self.reference_path(relative_path)
        self.client.files.upload(path, io.BytesIO(contents), overwrite=False)
        return path

    def list_references(self):
        return [entry.as_dict() for entry in self.client.files.list_directory_contents(self.config.volume_path)]

    def configure_tracing(self):
        """Opt-in MLflow initialization. Skip if the agent runtime already configures tracing."""
        import mlflow
        uri = 'databricks' if os.getenv('DATABRICKS_APP_NAME') else f'databricks://{self.config.profile}'
        if not os.getenv('DATABRICKS_APP_NAME'):
            # MLflow's SQL warehouse helper constructs its own SDK client.
            os.environ['DATABRICKS_CONFIG_PROFILE'] = self.config.profile
        if self.config.trace_warehouse_id:
            os.environ['MLFLOW_TRACING_SQL_WAREHOUSE_ID'] = self.config.trace_warehouse_id
        mlflow.set_tracking_uri(uri)
        experiment = self.client.experiments.get_by_name(self.config.experiment_name).experiment
        resolved = mlflow.set_experiment(experiment_id=experiment.experiment_id)
        if self.config.trace_table_prefix:
            from mlflow.entities.trace_location import UnityCatalog
            expected = UnityCatalog(catalog_name=self.config.catalog, schema_name=self.config.schema,
                                    table_prefix=self.config.trace_table_prefix)
            if resolved.trace_location != expected:
                raise ValueError('MLflow experiment does not match configured UC trace tables')
        return experiment.experiment_id

    def resolved_settings(self):
        """Non-secret settings for consumers; does not modify the agent's deployment files."""
        settings = asdict(self.config)
        settings.update(volume_path=self.config.volume_path, schema_name=self.config.schema_name)
        return settings
