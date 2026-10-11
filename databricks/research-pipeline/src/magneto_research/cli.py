"""Explicit operational commands; smoke remains a separate metadata-only entry point."""
import argparse
from contextlib import redirect_stdout
import json
import sys
from pathlib import Path

from .config import ResearchConfig
from .connections import connect
from .pipeline import Pipeline
from .storage import Warehouse, initialize


def _main(argv=None, output=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--profile')
    sub = parser.add_subparsers(dest='command', required=True)
    tracking = sub.add_parser('connect-experiment', help='Verify updater tracking independently of SQL processing')
    tracking.add_argument('--create', action='store_true', help='Create experiment or bind its UC trace location')
    tracking.add_argument('--verify-write', action='store_true', help='Write and read one synthetic trace')
    sub.add_parser('init', help='Create research tables/views in the existing schema')
    ingest = sub.add_parser('ingest')
    ingest.add_argument('--file', required=True)
    ingest.add_argument('--metadata', required=True)
    for name, help_text in [('process', 'Parse and prepare one source version'),
                            ('extract', 'Extract candidate findings from one passage'),
                            ('export-guidance', 'Export one currently approved teaching recommendation'),
                            ('judge', 'Assess one recommendation without approving it')]:
        p = sub.add_parser(name, help=help_text)
        p.add_argument('id')
        if name == 'judge':
            p.add_argument('--kind', choices=['finding', 'recommendation'], default='recommendation')
    p = sub.add_parser('draft')
    p.add_argument('--file', required=True)
    p = sub.add_parser('review', help='Record an explicit human decision under the authenticated identity')
    p.add_argument('kind', choices=['source', 'finding', 'recommendation'])
    p.add_argument('id')
    p.add_argument('action', choices=['active', 'withdrawn', 'accepted', 'rejected', 'approved'])
    p.add_argument('--rationale', required=True)
    p = sub.add_parser('audit')
    p.add_argument('kind', choices=['source', 'passage', 'finding', 'recommendation'])
    p.add_argument('id')
    p = sub.add_parser('list')
    p.add_argument('kind', choices=['sources', 'chunks', 'findings', 'recommendations', 'reviews', 'runs'])
    sub.add_parser('publish')
    sub.add_parser('create-index')
    p = sub.add_parser('search')
    p.add_argument('query')
    p.add_argument('--collection', choices=['teaching', 'industry'], required=True)
    p.add_argument('--tier', choices=['library', 'reviewed', 'approved'], default='reviewed')
    p.add_argument('--limit', type=int, default=5)
    args = parser.parse_args(argv)
    try:
        config = ResearchConfig.load(args.config)
        client = connect(config, profile=args.profile)
        experiment_id = None
        if config.experiment_name or args.command == 'connect-experiment':
            from .tracking import configure_tracking, verify_connection
            experiment_id = configure_tracking(config, client, args.profile,
                create=args.command == 'connect-experiment' and args.create)
        if args.command == 'connect-experiment':
            result = (verify_connection(config, experiment_id) if args.verify_write else
                      {'status': 'connected', 'experiment_id': experiment_id,
                       'experiment_name': config.experiment_name, 'trace_schema': config.schema_name})
            print(json.dumps(result, indent=2), file=output)
            return 0
        db = Warehouse(client, config)
        pipeline = Pipeline(config, client, db, client.current_user.me().user_name, experiment_id)
        cmd = args.command
        if cmd == 'init':
            initialize(db, config)
            result = {'status': 'research_tables_initialized'}
        elif cmd == 'ingest':
            result = pipeline.ingest(args.file, json.loads(Path(args.metadata).read_text()))
        elif cmd == 'process': result = pipeline.process(args.id)
        elif cmd == 'extract': result = pipeline.extract(args.id)
        elif cmd == 'draft': result = pipeline.draft(json.loads(Path(args.file).read_text()))
        elif cmd == 'review': result = pipeline.review(args.kind, args.id, args.action, args.rationale)
        elif cmd == 'audit': result = pipeline.audit(args.kind, args.id)
        elif cmd == 'export-guidance': result = pipeline.export(args.id)
        elif cmd == 'publish': result = pipeline.publish()
        elif cmd == 'create-index': result = pipeline.create_index()
        elif cmd == 'search': result = pipeline.search(args.query, args.collection, args.tier, args.limit)
        elif cmd == 'list':
            result = db.execute(f'SELECT * FROM {config.table(args.kind)} LIMIT 100')
        elif cmd == 'judge':
            from .judge import judge_recommendation
            result = judge_recommendation(pipeline, args.id, args.profile, args.kind)
        print(json.dumps(result, indent=2, ensure_ascii=False), file=output)
        return 0
    except Exception as exc:
        # SQL failures include a statement ID for private workspace diagnostics, not source content.
        message = str(exc) if type(exc) in (ValueError, RuntimeError, TimeoutError) else 'Inspect workspace logs'
        print(json.dumps({'status': 'failed', 'error_type': type(exc).__name__, 'message': message}), file=output)
        return 1


def main(argv=None):
    # SDK/MLflow progress belongs on stderr; stdout is one machine-readable JSON result.
    output = sys.stdout
    with redirect_stdout(sys.stderr):
        return _main(argv, output)


def run():
    status = main()
    if status:
        raise SystemExit(status)


if __name__ == '__main__':
    run()
