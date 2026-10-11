"""Optional read-only MLflow evidence lookup. Never turns model output into a learner grade."""
import argparse
import json
import os
import tomllib
from pathlib import Path
import re

def search_request(search,experiment_id,request_id):
    if not re.fullmatch(r'[0-9a-f-]{36}',request_id):raise ValueError('Expected canonical request UUID.')
    traces=search(locations=[experiment_id],max_results=2,return_type='list',include_spans=True,
                  filter_string=f"trace.client_request_id = '{request_id}'")
    if len(traces)!=1:raise ValueError('Expected exactly one matching trace; do not guess the join.')
    t=traces[0]
    if t.info.client_request_id!=request_id:raise ValueError('Trace request identity mismatch.')
    return {'request_id':request_id,'trace_id':t.info.trace_id,'span_names':[s.name for s in t.data.spans],
            'boundary':'Decision provenance only. Join to separately confirmed learner events before reflection.'}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--experiment',required=True);parser.add_argument('--request',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args()
    import mlflow
    config=tomllib.loads((Path(__file__).resolve().parents[1]/'databricks/platform/services.toml').read_text())
    os.environ['DATABRICKS_CONFIG_PROFILE']=config['profile']
    os.environ['MLFLOW_TRACING_SQL_WAREHOUSE_ID']=config['trace_warehouse_id']
    mlflow.set_tracking_uri('databricks://'+config['profile'])
    result=search_request(mlflow.search_traces,args.experiment,args.request)
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'verified':True,'trace_id':result['trace_id']}))
if __name__=='__main__':main()
