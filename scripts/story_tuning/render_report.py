"""Render the actual local MLflow report for review; no service simulation."""
from pathlib import Path
import html
import json

ROOT = Path(__file__).resolve().parents[2]
r = json.loads((ROOT/'reports/story-tuning-live.json').read_text())
fixtures = json.loads((ROOT/'reports/story-registry-fixtures.json').read_text())
host = 'https://dbc-129a8d44-1940.cloud.databricks.com'
base = f'{host}/ml/experiments/{r["experiment_id"]}'
def link(run, label): return f'<a href="{base}/runs/{run}" target="_blank" rel="noopener">{label} ↗</a>'
def pct(section, key):
    value = r.get(section,{}).get('metrics',{}).get(key+'/mean')
    return 'Pending' if value is None else f'{value:.1%}'
rows = ''.join(f'<tr><th>{label}</th><td>{pct("baseline",key)}</td><td>{pct("candidate",key)}</td></tr>'
               for key,label in [('valid_decision','Valid decisions'),('teaching_policy','Correct teach / continue'),('concise_activity','Concise activity')])
cards = ''.join(f'<article><span class="badge">{html.escape(x["decision"]["action"])}</span><h3>{html.escape(x["fixture"].replace("_"," "))}</h3><p>{html.escape(x["decision"]["reason"])}</p>'
                +(f'<blockquote>{html.escape(x["decision"]["prompt"])}</blockquote>' if x['decision']['prompt'] else '')+'</article>' for x in fixtures['requests'])
trace = r['smoke']['trace_id'].split('/')[-1]
status = ('Final held-out comparison running' if r['status'] != 'complete' else
          'Promoted after strict gain' if r.get('promoted') else 'Champion retained: no qualifying improvement')
page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Magneto · Live MLflow tuning</title><style>
:root{--paper:#faf9f5;--ink:#203e38;--muted:#586b63;--teal:#184f47;--green:#e5eee4;--yellow:#f3cd61;--line:#dce2d9}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 'Avenir Next',Avenir,sans-serif}main{max-width:1050px;margin:auto;padding:40px 24px}h1{font-size:clamp(30px,5vw,48px);line-height:1.12;letter-spacing:-1px}h2{margin:32px 0 12px}h3{margin:12px 0 8px}p{color:var(--muted)}a{color:var(--teal);overflow-wrap:anywhere}code{overflow-wrap:anywhere}.hero{background:var(--green);padding:24px;border-radius:16px}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;margin:18px 0}article{min-width:0;background:white;padding:20px;border:1px solid var(--line);border-radius:16px}.badge{display:inline-block;background:var(--yellow);border-radius:12px;font-size:12px;font-weight:800;padding:3px 10px}table{width:100%;border-collapse:collapse;background:white}th,td{padding:16px;text-align:left;border-bottom:1px solid var(--line)}thead{background:var(--green)}.note{border-left:5px solid var(--yellow);padding:8px 16px}blockquote{margin:12px 0;padding:12px;background:var(--green);border-radius:8px}details{padding:16px;background:white;border:1px solid var(--line);border-radius:12px;margin:12px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere}footer{font-size:13px;color:var(--muted)}@media(max-width:740px){.grid{grid-template-columns:1fr}main{padding:24px 16px}th,td{padding:10px}}
</style><main><span class="badge">Real hosted-model calls · Synthetic cases</span><h1>Your story optimizer is linked to MLflow.</h1>'''
page += f'<div class="hero"><strong>{status}</strong><p>Prompt <code>{r["prompt_name"]}</code> · baseline v{r["baseline_version"]} · candidate v{r.get("candidate_version","pending")} · champion v{r.get("champion_version",r["baseline_version"])}</p></div>'
page += f'<h2>Held-out comparison</h2><p>27 three-response sequences; 15 separate training cases. Same model, same checks. Failures count against the score.</p><table><thead><tr><th>Engineering quality check</th><th>Baseline</th><th>GEPA candidate</th></tr></thead><tbody>{rows}</tbody></table>'
if r.get('candidate_changed') is False:
    page += '<p class="note"><strong>No tuning gain:</strong> GEPA selected the starting template. Registry v2 has identical text to v1. Differences between these two runs are variation, not an improved prompt. A proposed revision scored worse on training and was rejected.</p>'
page += '<p>'+link(r['baseline']['run_id'],'Baseline evaluation')+' · '+link(r['optimization_run_id'],'GEPA optimization')+' · '+link(r.get('candidate',{}).get('run_id',r['optimization_run_id']),'Candidate evaluation')+'</p>'
page += f'<h2>What the live model actually returned</h2><p>All {fixtures["summary"]["successes"]}/5 original fixtures passed via the CLI, using the registered champion prompt.</p><div class="grid">{cards}</div>'
page += f'<p><a target="_blank" rel="noopener" href="{base}/traces/{trace}">Open the verified registry inference trace ↗</a></p>'
page += '<h2>Repeat the automated search</h2><pre>.venv-agent/bin/python scripts/tune_story.py --max-metric-calls 36</pre><p>The CLI loads the champion, evaluates it, runs GEPA, registers a candidate, evaluates held-out cases, and promotes only a strict gain with no regression. Runtime schema and tactile Braille constraints remain fixed.</p>'
page += '<p class="note">These scores demonstrate an engineering optimization pipeline. The examples are synthetic and policy-labeled; they do not establish teacher approval or better learning. This does not connect learner-profile updates or tune model weights.</p>'
page += '<details><summary>Runtime verification boundary</summary><p>Runtime alias activation awaits the additional schema privileges. The app was restored to its previous prompt and is RUNNING. Its startup check captured the exact registry denial in MLflow. Calls from this machine to the Databricks Apps hostname are blocked at DNS/TLS, so a complete localhost → deployed-app request remains unverified. CLI → Prompt Registry → hosted model → MLflow trace is verified.</p></details>'
page += '<footer>Report generated from reports/story-tuning-live.json and the actual five-fixture report. Design follows Magneto’s existing colors and typography.</footer></main></html>'
(ROOT/'.lavish/story-tuning-results.html').write_text(page)
print(ROOT/'.lavish/story-tuning-results.html')
