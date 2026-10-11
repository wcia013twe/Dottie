"""CLI: status is read-only; provision and wire-app are explicit, additive mutations."""
import argparse
import json
from pathlib import Path
import sys

from .services import ServiceConfig, Services


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['status', 'provision', 'wire-app', 'settings'])
    parser.add_argument('--config', type=Path, default=Path(__file__).resolve().parents[1] / 'services.toml')
    args = parser.parse_args()
    try:
        services = Services(ServiceConfig.load(args.config))
        method = {'status': services.status, 'provision': services.provision,
                  'wire-app': services.wire_app_permissions, 'settings': services.resolved_settings}[args.command]
        result = method()
        print(json.dumps(result, indent=2))
        if args.command == 'status' and any(item['status'] == 'error' for item in result.values()):
            return 1
        return 0
    except Exception as exc:
        print(json.dumps({'status': 'failed', 'error_type': type(exc).__name__}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
