# Magneto: one live decision

The browser sends a complete synthetic session snapshot through the localhost Python bridge to a native Databricks App. A single-node LangGraph makes one model call and validates `continue` or `teach`. No local lesson policy overrides the model's action. Only approved teacher passage summaries are transmitted; imported books are not uploaded.

## Shared wiring

`../platform/services.toml` and `../platform/magneto_platform/` are the source of truth for workspace resources and authenticated transport. The localhost bridge uses `Services.invoke_agent`; the deployed decision function uses `Services.complete`. Before deployment, `scripts/prepare_agent.py` copies the shared package and config into this standalone deployment directory. Do not edit the generated `magneto_platform/` copy or `services.toml` here.

The shared resources are `workspace.magneto`, the empty `references` volume, the existing `agent-bricks-magneto-director` app, and `/Shared/agentbricks_traces/magneto-director-uc`. Reference uploads are explicit opt-in platform operations and are not part of the decision loop. The model can be overridden with `MAGNETO_MODEL`.

## Local demo

From the repository root, authenticate and run:

```bash
databricks auth login --host https://dbc-129a8d44-1940.cloud.databricks.com --profile magneto
python3 scripts/serve.py
```

Open `http://127.0.0.1:8080/learn/#stories` and select the live Caterpillar demo. If an older server is already running, restart it or use `--port 8090`. Python's static server process delegates authenticated calls to `.venv-agent/bin/python`; credentials never enter browser JavaScript.

The adapter environment needs `databricks-sdk` and `requests`. The deployment CLI is pinned to `databricks-agentbricks==0.5.0`; install it into `.venv-agent`. The agent's own Python 3.12 dependencies are pinned in `uv.lock` and exported in `requirements.txt`.

```bash
python3 scripts/reasoning_cli.py --fixture plum_incorrect
python3 scripts/reasoning_cli.py --benchmark 30 --output reports/reasoning-benchmark.json
npm run check:reasoning
npm run check
```

Use the agent virtual environment for `scripts/reasoning_cli.py --direct` when calling the model without deployment. Deployed calls work with system Python through the isolated adapter subprocess.

## Deploy

```bash
python3 scripts/prepare_agent.py
PATH="$PWD/.venv-agent/bin:$PATH" .venv-agent/bin/agentbricks --profile magneto deploy magneto-director --source databricks/magneto-director
```

The Agent Bricks CLI excludes `uv.lock` from its upload, so Apps installs the exported `requirements.txt` and starts `python -m runtime.main`. Re-export requirements with `uv export --frozen --no-dev --no-hashes --no-emit-project --format requirements-txt --output-file requirements.txt` after dependency changes.

This workspace rejected managed Runtime Store provisioning with `Scale-to-zero must be enabled for this workspace tier`. The supported `server = "custom"` deployment runs a foreground FastAPI endpoint natively in Databricks Apps instead. This is a workspace-tier configuration constraint, not evidence of exhausted model usage. There is no Lakebase store, background invocation, streaming, replay, or durable invocation deduplication. A restart loses in-flight work; the browser retries with a fresh request ID and complete snapshot.

## Contract and safeguards

`POST /api/invocations` accepts `{id, session_id, input}`; `input` is a complete canonical snapshot. It returns `{id, status: "completed", output}`. Databricks Apps authenticates callers; local profile credentials and the app service identity stay server-side.

Decision fields: `action`, `passage_id`, `target_letter`, `prompt`, `reason`, `based_on_event_id`. The reason is a concise evidence summary. Model output never replaces the story. Invalid output is rejected before activity execution. Browser requests expire at 15 seconds; the bridge has a 14-second subprocess deadline. A timeout is an explicit error, with Retry and Continue without activity. Navigation/restart invalidates late responses.

Connected sessions use only `magneto-connected-demo-v1`. Existing books, reading positions, progress, and CAD storage are untouched. On-screen Braille is explicitly simulated. ElevenLabs, physical serial acknowledgements, camera inspection, research ingestion, and a persistent learner database remain deferred.

## Verified MLflow tracing

The app uses the shared Unity Catalog-backed experiment
`/Shared/agentbricks_traces/magneto-director-uc` (ID `948045133158359`). Its four OTEL
tables live in `workspace.magneto` with prefix `948045133158359`. The existing app
identity has explicitly approved SELECT/MODIFY access to those tables and CAN_EDIT
on the experiment. Startup validates the bound trace destination before serving.

The original experiment `948045133158207` is preserved. Its regional artifact
storage endpoint refused connections from the App. Databricks does not allow adding
UC trace storage to an experiment that already contains traces, so the replacement
experiment was necessary. No network protections were changed.

A deployed decision was read back with three complete spans: root decision,
LangGraph graph, and decision node. Inputs, outputs, model, request ID and elapsed
time matched the live response. See `reports/mlflow-agent-trace.json` and
`reports/mlflow-debug.md` from the repository root.

To verify one new synthetic invocation using the configured SQL warehouse:

```bash
databricks/magneto-director/.venv/bin/python scripts/verify_tracing.py
# If asynchronous ingestion is not visible yet, read the saved request without a new call:
databricks/magneto-director/.venv/bin/python scripts/verify_tracing.py --readback-only
```

Readback is bounded to 60 seconds per invocation of the verifier. The local SQL
helper explicitly uses profile `magneto`; deployed writes use the app identity.
The existing SQL warehouse is used for setup/readback; no learner database was added.

## Prompt optimization pilot

See [story prompt optimization](../docs/story-prompt-optimization.md) for the registry-backed CLI evaluation / GEPA workflow. Runtime registry loading is opt-in via `MAGNETO_PROMPT_URI`; the serving app keeps its previous prompt until the beta registry privileges are approved. Schema and tactile Braille constraints are outside the tunable policy.

## Approved research context (local implementation; live activation pending)

`agent/research.py` implements the v1 retrieval request/result boundary. With `MAGNETO_RESEARCH_ENABLED=1`, `decide` queries only teaching/approved AI Search candidates and rechecks them against current `research_eligible_recommendations` and `research_eligible_findings` in the SQL warehouse. It excludes stale hits, other target letters and multi-source recommendations that cannot satisfy v1's single citation. It never accepts library passages as approved advice or writes review decisions.

The model receives the canonical snapshot plus a separate approved-guidance evidence message. Citations and guidance IDs are recorded on the active director MLflow span as `research.approved_guidance`; they describe evidence supplied, not causal reliance or educational effectiveness. Model output and browser payloads keep the existing wire format. Empty retrieval is a successful `matches: []`; configured lookup failure stops the decision explicitly. The existing overall invocation deadline still applies.

`python3 scripts/prepare_agent.py --target magneto-director` packages authoritative retrieval schemas and research resource references as generated deployment files. Optional `MAGNETO_RESEARCH_CONFIG` selects a different config file. Do not edit generated `agent/research_contracts/` or `research.toml`. The serving identity needs index-query and warehouse access plus SELECT on the research eligibility dependencies. No grants or cloud deployment were changed by this local implementation. `app.yaml` does not enable the feature.

Reproduce local proof: `PYTHONPATH=databricks/magneto-director databricks/magneto-director/.venv/bin/python -m pytest databricks/magneto-director/tests/test_research.py -q`. Tests use explicitly synthetic research and a controlled model substitute; they prove adapter-to-model wiring and rejection gates, not hosted inference or teaching improvement. Existing research has no approved teaching recommendations in the latest inherited verification, so live retrieval may correctly return no matches until actual review/approval occurs. No synthetic fixture is published.

Local verification: 46 director tests passed, shared contract checks and repository `npm run check` passed. The System map connection is amber, with activation pending; labels and animation were browser-verified. Inspect `reports/research-director-local-proof.json` at the repository root for the captured synthetic guidance/citation, model messages, audit record and validated decision. `uv` was unavailable on PATH; tests ran in the director's existing virtual environment.
## Optional learning-history uploads

PR #7 extends this app with v2 legacy events/profiles and v3 lean attempts. See
[the contract and migration notes](../contracts/v3/README.md). This is durable observation storage;
the decision graph continues to use its supplied v1 snapshot and does not read the tables.
The browser keeps one profile across session restarts, asks for upload opt-in, and records
support separately from the teacher's response. Existing books and local progress stay separate.

With learning_warehouse_id empty, learning routes return 503 and queues remain local.
When configured for an explicit deployment, startup creates missing learning tables. SQL values
are parameterized; only successful statements and matching event/attempt readback produce
acknowledgements. The SDK wait is bounded to 5 seconds with cancellation on timeout.
See the [Statement Execution API](https://docs.databricks.com/api/statement-execution/v1/statement-execution).
No raw transcripts, media, device commands or model reasoning are accepted in v3.
The check:learning script covers contract rejection, storage failures, idempotent retries and the browser outbox.
