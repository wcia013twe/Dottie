"""Explicit updater experiment setup and bounded operational tracing.

Smoke checks never import this module. Operational commands run in a dedicated
process; they must not inherit the live director's experiment or active run.
"""
from contextlib import contextmanager
import os
import time

DIRECTOR_EXPERIMENT_ID = '948045133158359'


def resolve_experiment(config, client):
    if not config.experiment_name:
        raise ValueError('Configure a separate updater experiment')
    experiment = client.experiments.get_by_name(config.experiment_name).experiment
    if not experiment or not experiment.experiment_id or experiment.lifecycle_stage == 'deleted':
        raise ValueError('Updater experiment does not exist or is deleted')
    if experiment.experiment_id == DIRECTOR_EXPERIMENT_ID:
        raise ValueError('Updater must not use the director experiment')
    return experiment


def configure_tracking(config, client, profile=None, *, create=False):
    import mlflow
    from mlflow.entities.trace_location import UnityCatalog
    from databricks.sdk.errors import NotFound
    from .connections import verify_workspace
    verify_workspace(config, client)
    if not config.experiment_name or not config.warehouse_id:
        raise ValueError('Configure updater experiment_name and warehouse_id')
    if mlflow.active_run():
        raise ValueError('Updater requires a dedicated process without an active MLflow run')
    # Read existing shared resources; do not create namespaces or grants.
    client.schemas.get(config.schema_name)
    client.warehouses.get(config.warehouse_id)
    if profile:
        os.environ['DATABRICKS_CONFIG_PROFILE'] = profile
    os.environ['MLFLOW_TRACING_SQL_WAREHOUSE_ID'] = config.warehouse_id
    mlflow.set_tracking_uri(f'databricks://{profile}' if profile else 'databricks')
    try:
        experiment = resolve_experiment(config, client)
    except NotFound:
        if not create:
            raise ValueError('Updater experiment missing; run connect-experiment --create') from None
        identifier = mlflow.create_experiment(config.experiment_name,
            trace_location=UnityCatalog(catalog_name=config.catalog, schema_name=config.schema))
    else:
        identifier = experiment.experiment_id
    resolved = mlflow.get_experiment(identifier)
    location = resolved.trace_location
    if location is None and create:
        resolved = mlflow.set_experiment(experiment_id=identifier,
            trace_location=UnityCatalog(catalog_name=config.catalog, schema_name=config.schema))
        location = resolved.trace_location
    if (not isinstance(location, UnityCatalog) or location.catalog_name != config.catalog
            or location.schema_name != config.schema):
        raise ValueError('Updater experiment must be bound to the configured UC schema; '
                         'use connect-experiment --create for an unbound experiment')
    mlflow.set_experiment(experiment_id=identifier)
    return identifier


@contextmanager
def tracked_operation(experiment_id, operation, research_run_id, subject_id):
    if not experiment_id:
        yield {}
        return
    import mlflow
    from mlflow.entities import MlflowExperimentLocation
    with mlflow.start_run(experiment_id=experiment_id,
                          run_name=f'updater-{operation}-{research_run_id}',
                          tags={'magneto.role': 'passive_updater',
                                'research_run_id': research_run_id, 'operation': operation}) as run:
        with mlflow.start_span(name=f'updater.{operation}', run_id=run.info.run_id,
                trace_destination=MlflowExperimentLocation(experiment_id)) as span:
            span.set_inputs({'subject_id': subject_id, 'research_run_id': research_run_id})
            identifiers = {'mlflow_run_id': run.info.run_id, 'trace_id': span.trace_id,
                           'experiment_id': experiment_id}
            try:
                yield identifiers
            except Exception as exc:
                span.set_outputs({'status': 'failed', 'error_type': type(exc).__name__})
                raise
            else:
                span.set_outputs({'status': 'completed', **identifiers})


def verify_connection(config, experiment_id):
    """Synthetic write/read probe: no model, source ingestion, or learner data."""
    import mlflow
    from uuid import uuid4
    started = int(time.time() * 1000)
    with tracked_operation(experiment_id, 'connection_check', str(uuid4()), 'synthetic') as ids:
        pass
    # Persist identifiers before readback: the caller enforces a process deadline.
    import json
    print(json.dumps({'status': 'trace_written_pending_readback', **ids}), flush=True)
    mlflow.flush_trace_async_logging()
    trace = mlflow.get_trace(ids['trace_id'])
    if trace is None or not trace.data.spans:
        raise RuntimeError('Updater trace readback did not return spans')
    return {'status': 'verified', 'synthetic': True, 'started_at_ms': started, **ids,
            'url': f'{config.workspace_host}/ml/experiments/{experiment_id}/traces/'
                   f'{ids["trace_id"].rsplit("/", 1)[-1]}'}
