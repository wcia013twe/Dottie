"""Unity Catalog evidence adapter. Only explicitly confirmed, non-synthetic observations are uploaded."""
import argparse
import json
from pathlib import Path
import sys
import time
import tomllib
from learner_intelligence import FIELDS, ROOT, validate_event

DDL = 'id STRING, learner_id STRING, session_id STRING, occurred_at STRING, category STRING, target STRING, task STRING, condition STRING, outcome STRING, confirmed BOOLEAN, synthetic BOOLEAN, trace_id STRING'
CONFIG=tomllib.loads((ROOT/'databricks/platform/learner-intelligence.toml').read_text())
TABLE=CONFIG['evidence_table']
if TABLE!='workspace.magneto.learner_observations_v1':raise ValueError('Unapproved evidence table.')

def query(w,statement,params=None):
    from databricks.sdk.service.sql import StatementParameterListItem
    result=w.statement_execution.execute_statement(statement=statement,warehouse_id=CONFIG['warehouse_id'],wait_timeout='10s',row_limit=10001,parameters=[StatementParameterListItem(name=k,value=v,type='STRING') for k,v in (params or {}).items()])
    deadline=time.monotonic()+35
    while str(result.status.state.value) in ('PENDING','RUNNING'):
        if time.monotonic()>deadline:raise TimeoutError('Warehouse read/write pending. Local evidence retained for retry.')
        time.sleep(1);result=w.statement_execution.get_statement(result.statement_id)
    if result.status.state.value!='SUCCEEDED':raise RuntimeError('Databricks query failed. Check warehouse/table access.')
    if result.manifest and result.manifest.truncated:raise ValueError('Evidence result truncated; no partial profile published.')
    if result.manifest and (result.manifest.total_row_count or 0)>10000:raise ValueError('Evidence requires pagination; no partial profile published.')
    if not result.result:return []
    if result.result.next_chunk_index is not None:raise ValueError('Evidence requires pagination; no partial profile published.')
    columns=[c.name for c in result.manifest.schema.columns]
    return [dict(zip(columns,row)) for row in result.result.data_array or []]

def setup(w):
    query(w,f"CREATE TABLE IF NOT EXISTS {TABLE} ({DDL}) USING DELTA COMMENT 'Confirmed learner observations. Independent recognition counts teacher-confirmed identify responses independent versus with_help within identical target/task/condition; exclude deferred and device failures. No mastery inference. MLflow trace_id is provenance only.'")

def ingest(w,events):
    for e in events:
        validate_event(e)
        if e['synthetic'] or not e['confirmed']:raise ValueError('Only confirmed real observations may enter the live table.')
    for e in events:
        payload=json.dumps(e,sort_keys=True)
        existing=query(w,f'SELECT * FROM {TABLE} WHERE id = :event_id',{'event_id':e['id']})
        if existing:
            if decode(existing[0])!=e:raise ValueError('Conflicting immutable cloud event. No overwrite performed.')
            continue
        struct='STRUCT<'+DDL.replace(' STRING',':STRING').replace(' BOOLEAN',':BOOLEAN')+'>'
        query(w,f"MERGE INTO {TABLE} t USING (SELECT parsed.* FROM (SELECT from_json(:payload, '{struct}') parsed)) s ON t.id=s.id WHEN NOT MATCHED THEN INSERT *",{'payload':payload})
    return {'uploaded':len(events),'table':TABLE}

def decode(row):
    for k in ('confirmed','synthetic'):
        if row[k] not in ('true','false',True,False):raise ValueError('Invalid cloud flag.')
        row[k]=row[k] in ('true',True)
    validate_event(row)
    return row

def read(w,learner=None):
    if not learner:
        latest=query(w,f'SELECT learner_id FROM {TABLE} WHERE confirmed = true AND synthetic = false ORDER BY occurred_at DESC, id DESC LIMIT 1')
        if not latest:return {'learner_id':None,'events':[],'table':TABLE}
        learner=latest[0]['learner_id']
    rows=query(w,f'SELECT * FROM {TABLE} WHERE learner_id = :learner AND synthetic = false ORDER BY occurred_at, id',{'learner':learner})
    return {'learner_id':learner,'events':[decode(row) for row in rows],'table':TABLE}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('operation',choices=['setup','ingest','read']);args=parser.parse_args()
    from databricks.sdk import WorkspaceClient
    w=WorkspaceClient(profile=CONFIG['profile'])
    if w.config.host.rstrip('/')!='https://dbc-129a8d44-1940.cloud.databricks.com':raise ValueError('Workspace mismatch.')
    if args.operation=='setup':setup(w);result={'ready':True,'table':TABLE}
    elif args.operation=='ingest':result=ingest(w,json.load(sys.stdin)['events'])
    else:result=read(w,json.load(sys.stdin).get('learner_id'))
    print(json.dumps(result))
if __name__=='__main__':
    try:main()
    except Exception as e:
        print(json.dumps({'error':str(e) if isinstance(e,(ValueError,RuntimeError,TimeoutError)) else 'Databricks evidence access failed.'}));sys.exit(1)
