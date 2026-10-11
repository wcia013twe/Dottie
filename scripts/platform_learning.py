"""Private subprocess adapter for authenticated learning-event ingestion."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'databricks/platform'))
from magneto_platform import ServiceConfig, Services


def main():
    try:
        payload = json.load(sys.stdin)
        services = Services(ServiceConfig.load(ROOT / 'databricks/platform/services.toml'))
        if 'profile' in payload:
            profile = payload['profile']
            result = services.create_learning_profile(profile, timeout_s=30)
        elif payload.get('schema_version') == '3.0':
            result = services.ingest_learning_attempts(payload, timeout_s=30)
        else:
            profile_id = payload['events'][0]['profile_id']
            result = services.ingest_learning_events(payload, profile_id=profile_id, timeout_s=30)
        print(json.dumps(result))
        return 0
    except Exception as exc:
        print(json.dumps({'error_type': type(exc).__name__}))
        return 1


if __name__ == '__main__':
    sys.exit(main())
