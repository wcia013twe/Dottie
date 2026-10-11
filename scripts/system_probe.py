"""Metadata only: no inference, SQL statements, uploads, deployment or tracing writes."""
import json
from pathlib import Path
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'databricks/platform'))
from magneto_platform import ServiceConfig, Services


def main():
    config = ServiceConfig.load(ROOT / 'databricks/platform/services.toml')
    services = Services(config)
    client = services.client
    research = tomllib.loads((ROOT / 'databricks/research-pipeline/config/operations.toml').read_text())
    if research['workspace_host'].rstrip('/') != config.workspace_host.rstrip('/'):
        raise ValueError('Research workspace mismatch')
    checks = {
        'catalog': lambda: client.catalogs.get(config.catalog),
        'schema': lambda: client.schemas.get(config.schema_name),
        'references': lambda: client.volumes.read(config.volume_name),
        'director': lambda: client.apps.get(config.agent_app),
        'companion': lambda: client.apps.get('agent-bricks-magneto-companion'),
        'model': lambda: client.serving_endpoints.get(config.model_endpoint),
        'director_traces': lambda: client.experiments.get_by_name(config.experiment_name),
        'research_traces': lambda: client.experiments.get_by_name(research['experiment_name']),
        'warehouse': lambda: client.warehouses.get(research['warehouse_id']),
        'search_endpoint': lambda: client.vector_search_endpoints.get_endpoint(research['search_endpoint']),
        'search_index': lambda: client.vector_search_indexes.get_index(research['search_index']),
        'embeddings': lambda: client.serving_endpoints.get(research['embedding_endpoint']),
    }
    result = {}
    for key, check in checks.items():
        try:
            value = check()
            result[key] = {'status': 'reachable' if value is not None else 'unavailable'}
        except Exception:
            result[key] = {'status': 'unavailable'}
    print(json.dumps(result))


if __name__ == '__main__':
    main()
