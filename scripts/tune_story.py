#!/usr/bin/env python3
"""MLflow-native dataset/scorer/evaluation workflow, adapted from its evaluation template.

CLI: .venv-agent/bin/python scripts/tune_story.py [--max-metric-calls 36]
Uses the existing updater experiment; no training, GPU hosting, or learner-data upload.
"""
from pathlib import Path
import argparse
import json
import os
import signal
import sys
import faulthandler
from dataclasses import replace

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'databricks/magneto-director'), str(ROOT/'databricks/platform')]
os.environ.setdefault('MLFLOW_GENAI_EVAL_MAX_WORKERS', '3')
os.environ.setdefault('MLFLOW_DISABLE_AGENT_HINT', '1')
import mlflow
from magneto_platform import ServiceConfig, Services
from agent.decision import SYSTEM_PROMPT, decide, make_snapshot, ContractError
from story_tuning.cases import records
from story_tuning.quality import SCORERS, promotion_allowed

PROMPT = 'workspace.magneto.story_orchestrator'
REPORT = ROOT/'reports/story-tuning-live.json'


def setup():
    c = ServiceConfig.load(ROOT/'databricks/platform/services.toml')
    s = Services(replace(c, experiment_name='/Shared/magneto-research', trace_table_prefix='1306573313615572'))
    # Resolve local OAuth once, then share it in memory with evaluation workers.
    # Concurrent keychain reads from worker processes can intermittently fail.
    token = s.client.config.authenticate()['Authorization'].removeprefix('Bearer ')
    os.environ['DATABRICKS_HOST'] = c.workspace_host
    os.environ['DATABRICKS_TOKEN'] = token
    os.environ['DATABRICKS_AUTH_TYPE'] = 'pat'
    eid = s.configure_tracing()
    mlflow.set_registry_uri('databricks-uc')
    return s, str(eid)


def predictor(uri):
    @mlflow.trace(name='story_prompt_decision')
    def predict(request):
        # Failures remain visible to quality checks; serving still raises ContractError.
        try:
            return decide(make_snapshot(request), prompt_uri=uri)
        except (ContractError, RuntimeError) as exc:
            return {'error_type': type(exc).__name__, 'error': str(exc)}
    return predict


def dataset(name, eid, split):
    from mlflow.genai.datasets import search_datasets, create_dataset, get_dataset
    found = [d for d in search_datasets(experiment_ids=[eid]) if d.name == name]
    # Search results use metadata wrappers in MLflow 3.17; reload the UC-backed dataset.
    ds = get_dataset(name) if found else create_dataset(name=name, experiment_id=eid)
    ds.merge_records(records(split))
    return ds


def evaluate(name, data, predict, scorers):
    with mlflow.start_run(run_name=name, tags={'role':'story_prompt_evaluation','synthetic':'true'}) as run:
        result = mlflow.genai.evaluate(data=data.to_df(), predict_fn=predict, scorers=scorers)
        mlflow.log_dict(json.loads(result.result_df.to_json(orient='records')), 'story_case_results.json')
        return {'run_id':run.info.run_id, 'metrics':result.metrics}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--max-metric-calls', type=int, default=36)
    parser.add_argument('--smoke-only', action='store_true')
    parser.add_argument('--resume', action='store_true', help='Reuse the verified smoke and baseline after an interrupted optimizer')
    args = parser.parse_args()
    services, eid = setup()
    report = json.loads(REPORT.read_text()) if args.resume else {'experiment_id':eid,'prompt_name':PROMPT,'synthetic':True,
              'model':services.config.model_endpoint,'status':'started'}
    def save(): REPORT.write_text(json.dumps(report, indent=2, default=str)+'\n')
    save()
    current = mlflow.genai.load_prompt(f'prompts:/{PROMPT}@champion', allow_missing=True)
    if current is None:
        current = mlflow.genai.register_prompt(PROMPT, SYSTEM_PROMPT,
                    commit_message='Existing demo teaching policy; synthetic regression baseline.',
                    tags={'synthetic':'true','role':'story_orchestrator'})
        mlflow.genai.set_prompt_alias(PROMPT,'champion',current.version)
    if args.resume and (report.get('baseline_version') != current.version or report.get('experiment_id') != eid
                        or 'baseline' not in report or not report.get('smoke', {}).get('verified_spans')):
        raise RuntimeError('Resume checkpoint must contain a verified baseline for the current champion / experiment')
    report['baseline_version'] = current.version
    uri = f'prompts:/{PROMPT}/{current.version}'
    predict = predictor(uri)
    if not args.resume:
        with mlflow.start_run(run_name='story-registry-smoke', tags={'synthetic':'true','role':'story_prompt_smoke'}) as run:
            output = predict(records('train')[0]['inputs']['request'])
            trace_id = mlflow.get_last_active_trace_id()
            report['smoke']={'run_id':run.info.run_id,'trace_id':trace_id,'output':output}
        save()
    # Enforce total wall-clock deadline for the one prerequisite readback.
    def timeout(*_): raise TimeoutError('Trace readback exceeded 60 seconds')
    if not args.resume:
        signal.signal(signal.SIGALRM, timeout); signal.alarm(60)
        try:
            mlflow.flush_trace_async_logging()
            trace = mlflow.get_trace(trace_id)
            assert trace and trace.data.spans
            report['smoke']['verified_spans'] = [s.name for s in trace.data.spans]
        finally:
            signal.alarm(0)
        if 'decision' not in output: raise RuntimeError('Smoke prediction failed')
    report['status']='trace_verified'; save()
    print('Verified registry prediction and trace',report['smoke']['trace_id'],flush=True)
    if args.smoke_only: return
    from mlflow.genai.scorers import list_scorers
    existing = {s.name:s for s in list_scorers(experiment_id=eid)}
    suite = [existing[s.name] if s.name in existing else s.register(experiment_id=eid) for s in SCORERS]
    train = dataset('workspace.magneto.story_policy_synthetic_train_v1',eid,'train')
    heldout = dataset('workspace.magneto.story_policy_synthetic_heldout_v1',eid,'heldout')
    report['datasets']={'train':train.dataset_id,'heldout':heldout.dataset_id,
                        'train_count':len(train.to_df()),'heldout_count':len(heldout.to_df())}
    save()
    if not args.resume:
        report['baseline'] = evaluate('story-baseline-heldout',heldout,predict,suite); save()
    # Ephemeral OAuth is used by LiteLLM only; never written to a file or printed.
    headers = services.client.config.authenticate()
    os.environ['DATABRICKS_API_KEY'] = headers['Authorization'].removeprefix('Bearer ')
    os.environ['DATABRICKS_API_BASE'] = services.config.workspace_host + '/serving-endpoints'
    import litellm
    litellm.DatabricksConfig(max_tokens=1200, temperature=0)
    litellm.request_timeout = 60
    litellm.num_retries = 0
    faulthandler.dump_traceback_later(300, repeat=True)
    from mlflow.genai.optimize import GepaPromptOptimizer
    with mlflow.start_run(run_name='story-gepa-optimization', tags={'synthetic':'true','role':'story_prompt_optimization'}) as run:
        report['optimization_run_id']=run.info.run_id; save()
        result = mlflow.genai.optimize_prompts(predict_fn=predict,
            train_data=train.to_df(),prompt_uris=[uri],scorers=suite,
            optimizer=GepaPromptOptimizer(reflection_model=f'databricks:/{services.config.model_endpoint}',
                max_metric_calls=args.max_metric_calls,
                display_progress_bar=True,
                gepa_kwargs={'skip_perfect_score':False, 'seed':42}), enable_tracking=True)
        report['optimizer']={'name':result.optimizer_name,'initial_score':result.initial_eval_score,
            'final_score':result.final_eval_score,'initial_by_scorer':result.initial_eval_score_per_scorer,
            'final_by_scorer':result.final_eval_score_per_scorer}
        candidate=result.optimized_prompts[0]
    faulthandler.cancel_dump_traceback_later()
    report['candidate_version']=candidate.version
    report['candidate_changed']=candidate.template != current.template
    mlflow.genai.set_prompt_alias(PROMPT,'candidate',candidate.version); save()
    report['candidate'] = evaluate('story-candidate-heldout',heldout,predictor(candidate.uri),suite)
    promote = report['candidate_changed'] and promotion_allowed(report['baseline']['metrics'],report['candidate']['metrics'])
    report['promoted']=bool(promote)
    if promote:
        mlflow.genai.set_prompt_alias(PROMPT,'previous',current.version)
        mlflow.genai.set_prompt_alias(PROMPT,'champion',candidate.version)
    report['champion_version']=candidate.version if promote else current.version
    report['status']='complete'; save()
    mlflow.MlflowClient().log_dict(report['optimization_run_id'], report, 'story_tuning_report.json')
    print(json.dumps(report,indent=2,default=str))

if __name__ == '__main__': main()
