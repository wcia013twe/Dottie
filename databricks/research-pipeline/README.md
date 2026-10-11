# Magneto research intelligence

Paper-first evidence storage and AI search on Databricks, with equal teaching and industry workflows. This package owns research preparation; live teaching and learner profiles remain outside it. See [the implementation design](docs/mvp-design.md), [architecture](docs/architecture.md), and [shared v1 contracts](../contracts/README.md).

## What is implemented

- Explicit PDF intake with immutable source versions, SHA-256, attribution, rights basis, acquisition date, and optional expiry.
- Databricks `ai_parse_document` 2.0 and `ai_prep_search` (Beta), retaining parser/preparation artifacts and page-linked original passages separately from enriched embedding text.
- Source-bounded `ai_extract` 2.0 candidates; exact supporting quotes are checked before storage. Human acceptance and recommendation approval are distinct.
- Delta review history, source withdrawal, dependent-record eligibility, and current-status revalidation after AI Search retrieval.
- A shared research search table/index with collection and evidence-tier filters. Approved teaching guidance can be exported through the unchanged v1 contract; this is not the live director's retrieval service.
- Advisory MLflow evidence judging; no assessment can approve records or establish individual learning gains.
- Databricks-native operations: Catalog Explorer for evidence, a read-only operations notebook for review queues, Jobs for processing, and MLflow for traces. See [the console guide](docs/console-guide.md). Intake, review, publication, and auditing remain explicit CLI operations.

## Local checks

From the repository root:

```bash
PYTHONPATH=databricks/research-pipeline/src .venv-agent/bin/python -m unittest discover -s databricks/research-pipeline/tests -v
npm run check:contracts
npm run check
```

Tests and `magneto_research.smoke` never ingest sources, invoke models, schedule work, or upload learner data. Operational commands below do use cloud services. Install the package (and its `judge` extra for LLM judging) into Python 3.11+ or use the existing `.venv-agent`.

## Run operations

Use this prefix from the repository root, followed by one command:

```bash
PYTHONPATH=databricks/research-pipeline/src .venv-agent/bin/python -m magneto_research.cli --config databricks/research-pipeline/config/operations.toml --profile magneto --help
```

| Command | Effect |
| --- | --- |
| `init` | Create only research tables/views in the existing schema |
| `ingest --file paper.pdf --metadata source.json` | Register and upload an explicitly selected PDF; examples contain real source metadata, not bundled PDFs |
| `process SOURCE_VERSION` | Parse and prepare one registered document; calls managed AI Functions |
| `list chunks` / `list findings` | Inspect up to 100 records; use SQL for larger review queues |
| `extract CHUNK_ID` | Propose findings from one passage; leaves them unreviewed |
| `audit passage CHUNK_ID` / `audit finding FINDING_ID` | Resolve original source and processing history |
| `judge FINDING_ID --kind finding` | Advisory evidence check with MLflow; no approval |
| `review finding FINDING_ID accepted --rationale "..."` | Record the operator's explicit acceptance after checking source and context |
| `draft --file implication.json` | Save an implication supported by accepted findings from one collection |
| `judge RECOMMENDATION_ID` | Assess that implication before human approval |
| `review recommendation ID approved --rationale "..."` | Record explicit operator approval |
| `review source SOURCE_VERSION withdrawn --rationale "..."` | Immediately exclude dependent records from adapter results |
| `create-index` | Create a managed embedding index on an existing STANDARD search endpoint |
| `publish` | Refresh the shared search table and request triggered index synchronization |
| `search "question" --collection teaching --tier library` | Search original passages; `reviewed` finds accepted findings, `approved` finds approved implications |
| `export-guidance ID` | Export eligible, single-source teaching guidance matching v1 |

Recommendation JSON contains `text`, `finding_ids`, `rationale`, `limitations`, `target_letters`, and `difficulty_tags`. Industry implications use empty teaching arrays. Multi-source implications remain searchable internally but cannot be squeezed into v1's single citation. Corrections create new findings/recommendations; reject obsolete records rather than overwriting them. Ingesting a new edition does not automatically withdraw the previous edition: explicitly withdraw it when appropriate.

The CLI records the authenticated operator, not a user-supplied actor string. Do not run review commands on behalf of a human without their review decision. Ordinary access controls still apply: administrators can modify tables, and this is not a tamper-proof compliance ledger.

## Deployment and operation

`config/operations.toml` records the verified workspace, existing SQL warehouse and volume, plus research-owned endpoint/index/experiment names. No credentials are stored. `init` never creates catalogs, schemas, volumes, grants, or shared infrastructure.

```bash
cd databricks/research-pipeline
databricks bundle validate -t dev --profile magneto
databricks bundle deploy -t dev --profile magneto
databricks bundle run -t dev --profile magneto research_process --params source_version=REGISTERED_VERSION
```

The manual job parses/prepares one document. It does not extract findings, approve anything, or automatically publish. No schedule and no automatic retries. Direct CLI calls and job runs are separate verification paths. Run one mutation at a time; concurrent external writers are not supported in this MVP. An interrupted run stays incomplete and its derived passages/findings are ineligible; retry explicitly with a new run.

Use [the console guide](docs/console-guide.md) and `notebooks/research_operations.sql` to navigate and inspect the knowledge base inside Databricks. No local research UI or HTTP search bridge is maintained.

## Availability and limits

`ai_prep_search` is Beta. A supported region and SQL compute are required. The parser supports at most 500 pages / 100 MB; this intake deliberately supports PDFs first. HTML, CSV, XLSX, automatic discovery, schedules, and learner-data ingestion are not implemented. Generated extraction/preparation content requires review. Exact-substring checks establish quote presence, not scientific validity.

The domain library can contain unreviewed source passages. Those are clearly labeled and isolated from reviewed findings and approved implications. Search similarity is not evidence strength. No generic graph, custom embedding server, or separate learner database is added. Search overfetches candidates and revalidates current status, so it may return fewer than the requested limit while an index is stale.

See [verification.md](docs/verification.md) for actual cloud results and outstanding checks; configuration and local tests alone do not prove deployed behavior.

## Connect the updater experiment

The updater uses `/Shared/magneto-research`, separate from the live orchestrator's
`/Shared/agentbricks_traces/magneto-director-uc`. It reuses the existing
`workspace.magneto` schema and warehouse `a5e11b7fe2c6dbbc`. Setup may create the
updater experiment and its own UC trace tables; it never provisions shared
namespaces or grants, and never rebinds an experiment pointing to another schema.
Existing legacy traces are not migrated by binding the new destination.

From the repository root, authenticate and explicitly connect:

```bash
databricks auth login --profile magneto
PYTHONPATH=databricks/research-pipeline/src .venv-agent/bin/python -m magneto_research.cli --config databricks/research-pipeline/config/operations.toml --profile magneto connect-experiment --create --verify-write
```

The connection probe writes one synthetic run and trace, then reads it back;
it does not invoke a model, upload learner data, ingest sources, or create research
tables. Bound its readback to 60 seconds when running through an agent. A pending
trace ID is printed before readback so a timeout need not repeat the write.
A `verified` result confirms this probe only, not successful research processing.

Subsequent operational CLI commands require the configured experiment and its UC
binding to exist; they never create it implicitly. Ingestion, parsing/preparation,
extraction, judging, publication, and search are traced through their existing
operation contexts. The evidence judge reuses its parent updater run. Draft and
human review records remain explicit audit writes; model assessment never grants
approval. Install the package's `judge` extra to run model-based evidence judges.
Smoke remains read-only and checks the configured experiment without tracing.
