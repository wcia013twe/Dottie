"""Manual read-only smoke entry point; metadata access does not prove processing."""
import argparse
import json

from magneto_research.config import ResearchConfig
from magneto_research.connections import check_services, connect


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--profile', help='Local CLI profile; omit in a Databricks job')
    args = parser.parse_args(argv)
    try:
        config = ResearchConfig.load(args.config)
        report = check_services(config, connect(config, profile=args.profile))
    except Exception as exc:
        report = {'setup': {'status': 'failed', 'error_type': type(exc).__name__}}
    print(json.dumps(report, indent=2))
    return int(any(item['status'] == 'failed' for item in report.values()))


def run():
    """Propagate failures even when a job invokes the entry point as a function."""
    status = main()
    if status:
        raise SystemExit(status)


if __name__ == '__main__':
    run()
