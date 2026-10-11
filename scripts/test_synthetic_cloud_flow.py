"""Explicit fictional evidence -> isolated UC table -> Genie -> isolated profile test.

Run with .venv-agent/bin/python. Never writes or selects live learner records.
"""
import json
import argparse
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone

from learner_intelligence import ROOT, ProfileStore, derive, validate_event
from learner_cloud import DDL, query, decode
from learner_genie import HOST, generate_synthetic_test

TABLE = 'workspace.magneto.synthetic_learner_e2e_v1'
OUTPUT = ROOT/'reports/synthetic-cloud-flow'


def validate_batch(batch):
    if batch.get('synthetic') is not True or not batch['events'] or not batch['learner_id'].startswith('synthetic-'):
        raise ValueError('Expected fictional learner identity.')
    ids = set()
    for event in batch['events']:
        validate_event(event)
        if event['synthetic'] is not True or event['learner_id'] != batch['learner_id']:
            raise ValueError('Real or mixed learner evidence prohibited.')
        if event['trace_id'] is not None or event['id'] in ids:
            raise ValueError('Fixture trace references and duplicate IDs prohibited.')
        ids.add(event['id'])


def main(resume=None,evidence=None):
    if resume is not None and (len(resume)!=12 or any(c not in '0123456789abcdef' for c in resume)):
        raise ValueError('Expected a saved hexadecimal test run ID.')
    if resume and evidence is None:
        evidence=json.loads((OUTPUT/f'{resume}.json').read_text()).get('input_evidence')
    batch = json.loads(Path(evidence or ROOT/'reports/synthetic-learner-profiles/river.evidence.json').read_text())
    # One complete session is enough to exercise nonempty percentages without
    # claiming that a synthetic result is a real learning outcome.
    if not evidence:
        batch['events'] = [e for e in batch['events'] if e['session_id'] == 'session-1']
    run = resume or uuid4().hex[:12]
    learner = batch['learner_id']+'-'+run
    batch['learner_id'] = learner
    for event in batch['events']:
        event.update(learner_id=learner, id=event['id']+'-'+run)
    validate_batch(batch)  # Reject before authentication or any cloud operation.
    OUTPUT.mkdir(parents=True, exist_ok=True)
    report = {'run_id':run, 'synthetic':True, 'table':TABLE, 'learner_id':learner,
              'started_at':datetime.now(timezone.utc).isoformat(), 'stages':{},
              'full_suite_complete':False, 'live_learner_table_written':False,
              'input_evidence':str(Path(evidence).resolve()) if evidence else None}
    journal = OUTPUT/f'{run}.json'
    if resume:
        report=json.loads(journal.read_text())
        if report['learner_id']!=learner or report['table']!=TABLE or report['synthetic'] is not True:
            raise ValueError('Saved run isolation mismatch.')
        for key in ('status','error_type','validation_error'):report.pop(key,None)

    def record(stage, value):
        report['stages'][stage] = value
        journal.write_text(json.dumps(report, indent=2)+'\n')
        print(stage+': '+json.dumps(value), flush=True)

    try:
        from databricks.sdk import WorkspaceClient
        w = WorkspaceClient(profile='magneto')
        if w.config.host.rstrip('/') != HOST:
            raise ValueError('Workspace mismatch.')
        query(w, f"CREATE TABLE IF NOT EXISTS {TABLE} ({DDL}) USING DELTA COMMENT 'FICTIONAL SOFTWARE TEST ONLY. Never real learner observations.'")
        struct = 'STRUCT<'+DDL.replace(' STRING', ':STRING').replace(' BOOLEAN', ':BOOLEAN')+'>'
        if not report['stages'].get('sql_write',{}).get('passed'):
            # Read first: a process may have ended after committing SQL but before
            # recording its checkpoint. Never repeat an uncertain insert.
            existing=query(w, f'SELECT * FROM {TABLE} WHERE learner_id=:learner', {'learner':learner})
            if not existing:
                query(w, f"INSERT INTO {TABLE} SELECT parsed.* FROM (SELECT explode(from_json(:payload, 'ARRAY<{struct}>')) parsed)",
                      {'payload':json.dumps(batch['events'])})
            record('sql_write', {'passed':True, 'event_count':len(batch['events'])})
        rows = query(w, f'SELECT * FROM {TABLE} WHERE learner_id=:learner AND synthetic=true ORDER BY occurred_at,id', {'learner':learner})
        actual = [decode(row) for row in rows]
        expected = sorted(batch['events'], key=lambda e:(e['occurred_at'], e['id']))
        if actual != expected:
            raise ValueError('SQL round-trip evidence mismatch.')
        record('sql_readback', {'passed':True, 'exact_match':True, 'event_count':len(actual)})
        baseline = derive(learner, batch['display_name'], actual, True)
        candidate = generate_synthetic_test(baseline)
        record('genie', {'passed':True, 'analysis':candidate['analysis']})
        store = ProfileStore(ROOT/'.local/synthetic-learner-e2e/profile-store')
        def reviewed(current):
            if current != baseline:
                raise ValueError('Publication baseline changed.')
            return candidate
        result = store.update(learner, baseline['display_name'], actual,
                              synthetic=True, reviewed_transform=reviewed)
        profile = result['profile']
        from jsonschema import Draft202012Validator
        schema = json.loads((ROOT/'databricks/contracts/learner-profile-v1/profile.schema.json').read_text())
        Draft202012Validator(schema).validate(profile)
        if profile['synthetic'] is not True or any(c['metric']!=baseline['categories'][i]['metric'] for i,c in enumerate(profile['categories'])) or profile['stats']!=baseline['stats']:
            raise ValueError('Synthetic identity or authoritative counts changed.')
        profile_path = OUTPUT/'profile.json'
        profile_path.write_text(json.dumps(profile, indent=2)+'\n')
        replay = store.update(learner, baseline['display_name'], actual,
                             synthetic=True, reviewed_transform=reviewed)
        if replay['published'] or replay['profile'] != profile:
            raise ValueError('Identical replay published a new profile.')
        record('profile_publication', {'passed':True, 'epoch':profile['epoch'],
               'replay_published':False, 'profile_path':str(profile_path), 'schema_valid':True})
        report['status'] = 'passed'
    except Exception as exc:
        report.update(status='failed', error_type=type(exc).__name__)
        # SDK exception strings may include credentials; persist only bounded local diagnostics.
        if isinstance(exc, ValueError):
            report['validation_error'] = str(exc)
        print(json.dumps({'status':'failed', 'error_type':type(exc).__name__}), flush=True)
    finally:
        journal.write_text(json.dumps(report, indent=2)+'\n')
        (OUTPUT/'latest.json').write_text(json.dumps(report, indent=2)+'\n')
    return 0 if report['status']=='passed' else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resume', help='Resume a saved run without repeating an uncertain SQL write')
    parser.add_argument('--evidence', help='Explicit saved fictional evidence batch; all source guards apply')
    args=parser.parse_args()
    raise SystemExit(main(args.resume,args.evidence))
