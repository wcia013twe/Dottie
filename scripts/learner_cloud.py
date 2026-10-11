"""Unity Catalog evidence adapter. Only explicitly confirmed, non-synthetic observations are uploaded."""
import argparse
import json
from pathlib import Path
import sys
import time
import tomllib
from learner_intelligence import ROOT, validate_event
import learner_medallion as layers

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

def insert_silver(w,e):
    validate_event(e)
    if e['synthetic'] or not e['confirmed']:raise ValueError('Only confirmed real observations may enter silver.')
    payload=json.dumps(e,sort_keys=True)
    existing=query(w,f'SELECT * FROM {TABLE} WHERE id = :event_id',{'event_id':e['id']})
    if existing:
        if len(existing)!=1 or decode(existing[0])!=e:raise layers.EventConflict('Conflicting immutable cloud event. No overwrite performed.')
        return
    struct='STRUCT<'+DDL.replace(' STRING',':STRING').replace(' BOOLEAN',':BOOLEAN')+'>'
    query(w,f"MERGE INTO {TABLE} t USING (SELECT parsed.* FROM (SELECT from_json(:payload, '{struct}') parsed)) s ON t.id=s.id WHEN NOT MATCHED THEN INSERT *",{'payload':payload})
    stored=query(w,f'SELECT * FROM {TABLE} WHERE id = :event_id',{'event_id':e['id']})
    if len(stored)!=1 or decode(stored[0])!=e:raise RuntimeError('Silver readback mismatch; retry required.')

def ingest(w,events):
    execute=lambda sql,params=None:query(w,sql,params)
    identifiers=layers.capture(execute,events)
    count=layers.promote(execute,identifiers,lambda event:insert_silver(w,event))
    return {'uploaded':count,'table':TABLE,'bronze_table':layers.BRONZE}

def replay(w,learner):
    if not learner:raise ValueError('Replay requires one explicit learner.')
    rows=query(w,f'SELECT ingest_id FROM {layers.BRONZE} WHERE learner_id=:learner ORDER BY ingested_at,ingest_id',{'learner':learner})
    count=layers.promote(lambda sql,params=None:query(w,sql,params),[row['ingest_id'] for row in rows],lambda event:insert_silver(w,event))
    return {'replayed':count,'table':TABLE}

def publish_gold(w,profile):
    return layers.publish(lambda sql,params=None:query(w,sql,params),profile,lambda learner:read(w,learner)['events'])

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
    parser=argparse.ArgumentParser();parser.add_argument('operation',choices=['setup','ingest','read','replay','publish-gold','read-gold','backfill']);args=parser.parse_args()
    from databricks.sdk import WorkspaceClient
    w=WorkspaceClient(profile=CONFIG['profile'])
    if w.config.host.rstrip('/')!='https://dbc-129a8d44-1940.cloud.databricks.com':raise ValueError('Workspace mismatch.')
    execute=lambda sql,params=None:query(w,sql,params)
    if args.operation=='setup':
        setup(w);layers.setup(execute)
        result={'ready':True,'silver':TABLE,'bronze':layers.BRONZE,'gold':layers.GOLD}
    else:
        payload=json.load(sys.stdin)
        if args.operation=='ingest':result=ingest(w,payload['events'])
        elif args.operation=='replay':result=replay(w,payload.get('learner_id'))
        elif args.operation=='publish-gold':result=publish_gold(w,payload['profile'])
        elif args.operation=='read-gold':result={'profile':layers.read_gold(execute,payload.get('learner_id'))}
        elif args.operation=='backfill':
            # Historical silver is not mislabeled as an original received payload.
            rows=query(w,f'SELECT * FROM {TABLE} ORDER BY occurred_at,id')
            ids=layers.capture(execute,[decode(row) for row in rows],source='historical-silver-backfill-v1')
            result={'backfilled':len(ids),'source':'historical-silver-backfill-v1'}
        else:
            result=read(w,payload.get('learner_id'))
            result['gold_profile']=layers.read_gold(execute,result['learner_id'])
    print(json.dumps(result))
if __name__=='__main__':
    try:main()
    except Exception as e:
        print(json.dumps({'error':str(e) if isinstance(e,(ValueError,RuntimeError,TimeoutError)) else 'Databricks evidence access failed.'}));sys.exit(1)
