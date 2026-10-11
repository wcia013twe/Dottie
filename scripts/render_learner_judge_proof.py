"""Render actual MLflow judge results; no fabricated statuses or model outputs."""
from html import escape
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
r=json.loads((ROOT/'reports/learner-judge-proof.json').read_text())
host='https://dbc-129a8d44-1940.cloud.databricks.com'
experiment=f'{host}/ml/experiments/{r["experiment_id"]}'
e=lambda value:escape(str(value))
css=(ROOT/'web/system.css').read_text()
page=f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Magneto · Learner updater proof</title><style>{css}
main{{max-width:1000px}}.cases{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}}article{{min-width:0;padding:22px;background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow-wrap:anywhere}}article h2{{font-size:20px}}.accepted{{color:var(--connected)}}.rejected{{color:#bd4141}}.badge{{font-weight:700}}summary{{cursor:pointer}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}}@media(max-width:650px){{.cases{{grid-template-columns:1fr}}}}</style>
<main><p class="eyebrow">Magneto · Actual hosted-model calls · Fictional learner observations</p><h1>Evidence before profile updates</h1><p>Proof status: <strong>{e(r['status'])}</strong>. Software proof passed: <strong>{e(r.get('proof_passed','pending'))}</strong>.</p>
<p><a href="{experiment}/runs/{e(r['run_id'])}">Open the actual MLflow run</a> · <a href="{experiment}">Updater experiment</a></p>
<p>The hosted updater proposes profile text. A registered native MLflow judge checks evidence support. Code owns counts, provenance and versioned publication.</p><div class="cases">'''
for case in r['cases']:
    a=case['assessment'];accepted=a['accepted'];label='Accepted' if accepted else 'Rejected'
    page+=f'<article><p class="badge {"accepted" if accepted else "rejected"}">{label}</p><h2>{e(case["name"].replace("_"," "))}</h2>'
    for change in case['proposal']['changes']:
        page+=f'<p>{e(change["finding"])}</p><p><strong>Teaching action:</strong> {e(change["action"])}</p>'
    page+=f'<details><summary>Read the actual judge assessment</summary><p>{e(a["rationale"])}</p></details>'
    page+=f'<p><a href="{experiment}/traces/{e(case["trace_id"].rsplit("/",1)[-1])}">Inspect this gate trace</a></p></article>'
page+='</div><section class="detail"><h2>Publication evidence</h2>'
p=r.get('publication',{})
page+=f'<p>Published: {e(p.get("published","pending"))} · Epoch: {e(p.get("epoch","pending"))} · Replay created another epoch: {e(r.get("replay_published","pending"))} · Rejection preserved the prior store: {e(r.get("rejection_preserved_store","pending"))}</p>'
if p.get('profile'):
    page+=f'<details><summary>Inspect the published profile JSON</summary><pre>{e(json.dumps(p["profile"],indent=2))}</pre></details>'
page+=f'<p>Native MLflow evaluation agreement with these three declared regression expectations: {e(r.get("native_judge_case_agreement","pending"))}.</p>'
if r.get('evaluation_run_id'):
    page+=f'<p><a href="{experiment}/evaluation-runs?selectedRunUuid={e(r["evaluation_run_id"])}">Open native evaluation results</a></p>'
if r.get('attempts'):
    page+=f'<details><summary>Inspect all generation attempts ({len(r["attempts"])})</summary><pre>{e(json.dumps(r["attempts"],indent=2))}</pre></details>'
page+='</section><p class="footnote">This is an opt-in CLI with an isolated local profile store. The live page still uses the existing rules-based updater. The judge shares the Qwen endpoint with the updater and has not been aligned to teacher feedback. These synthetic checks demonstrate software behavior, not learning effectiveness.</p></main></html>'
output=ROOT/'.lavish/learner-judge-proof.html';output.parent.mkdir(exist_ok=True);output.write_text(page)
print(output)
