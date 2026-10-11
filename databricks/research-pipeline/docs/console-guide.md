# Research operations in Databricks

Use the Databricks console as the home for this knowledge base. Teaching and industry share the same storage and workflow, separated by `collection`. No separate collection website is maintained.

## Start here

- [Open the operations notebook](https://dbc-129a8d44-1940.cloud.databricks.com/editor/notebooks/368792836365572). Workspace path: `/Shared/magneto-research-operations/Research operations`. Its source is `databricks/research-pipeline/notebooks/research_operations.sql`. All executable cells are read-only SQL; attach the existing warehouse `a5e11b7fe2c6dbbc` to inspect current records. It does not ingest, invoke models, approve, or publish.
- Catalog Explorer: open `workspace` → `magneto`; research-owned tables and views begin with `research_`.
- Original files: Catalog Explorer → `workspace.magneto.references` → `research`. Each source record's `volume_path` points to its PDF. Each run's `details` records its artifacts and tracking links; failed runs retain these under `initial`.
- [Processing job](https://dbc-129a8d44-1940.cloud.databricks.com/jobs/966696100501459): supply an already registered `source_version`. Runs parsing/preparation only.
- [Read-only smoke job](https://dbc-129a8d44-1940.cloud.databricks.com/jobs/1116672964506265): checks resource metadata, without inference or ingestion.
- MLflow: experiment `/Shared/magneto-research`, ID `1306573313615572`. Keep research traces separate from the director experiment.
- AI Search: endpoint `magneto-research`, index `workspace.magneto.research_index`. Its source table is `research_search_documents`; synchronization is explicitly triggered by `publish`.

## Source collections

The October 11 intake is documented alongside this guide in the workspace folder: `source-collection.md` describes source uses and limitations, `source-intake-receipt.md` summarizes verification, and `source-intake-results.json` records source versions, processing runs and retrieval citations. Repository equivalents are under `intake/2026-10-11/`. Follow-up: CAST UDL 3.0’s one-page organizer is stored, processed and retrieval-verified after a managed retry recovered from free serverless capacity errors. That follow-up brought the library to 11 documents and 410 passages. See `framework-intake.md` and `framework-intake-results.json` in this workspace folder (repository: `intake/2026-10-11-frameworks/`). The subsequent verified I-M-ABLE intake added four cited passages, bringing the library to 12 source records and 414 passages. It processes Wormsley’s freely published 2016 author article (six original journal pages). See `imable-intake.md` and `imable-intake-results.json` for its scope and verified status. The full practice guide remains unacquired; the earlier handout still returned HTTP 403.

## Data dictionary

All names below have the prefix `workspace.magneto.research_`.

| Table | Purpose and links |
| --- | --- |
| `sources` | Immutable source-version `id`, stable `source_id`, collection, attribution, source URL, checksum, original PDF path and metadata |
| `chunks` | Original passage `text`, physical PDF page `locator`, separate embedding text; `source_version` → sources, `run_id` → runs |
| `findings` | Extracted statement, original quote, context and limitations in JSON `body`; `chunk_id` → chunks, `run_id` → runs. Presence does not mean acceptance |
| `recommendations` | Implication and rationale in JSON `body`; `body.finding_ids` → findings. Presence does not mean approval |
| `reviews` | Append-only operator decisions, rationale and timestamp; `subject_id` identifies a source version, finding or recommendation |
| `runs` | Started/completed/failed operation, subject, actor and JSON `details` with artifact directory and MLflow references |
| `search_documents` | Rebuildable search projection with collection, tier and kind; not the authoritative evidence or audit history |

Use `research_latest_reviews` to inspect the latest decision. Use `research_eligible_chunks`, `research_eligible_findings`, `research_eligible_recommendations` and `research_eligible_documents` for current usable evidence. These exclude incomplete processing and invalid dependencies. Raw tables deliberately retain rejected, withdrawn and historical records.

`library` means eligible original passages, which can be unreviewed. `reviewed` means accepted findings. `approved` means approved implications with currently accepted supporting findings. Search similarity and an LLM judge's positive assessment are not approval.

## Operator workflow

From the repository root, use this CLI prefix followed by an operation (replace `--help`):

```bash
PYTHONPATH=databricks/research-pipeline/src .venv-agent/bin/python -m magneto_research.cli --config databricks/research-pipeline/config/operations.toml --profile magneto --help
```

The full command reference is in repository file `databricks/research-pipeline/README.md`.

1. Select a PDF and prepare source metadata including collection, publisher, URL and rights basis; `ingest` registers and uploads it. Uploading a PDF through the console alone does not register it.
2. `process` the returned source version, or run the processing job with that version. Inspect sources, passages and failures in the notebook.
3. `extract` selected passage IDs. Inspect candidate statements beside their original passages and PDF pages. `judge` provides an optional advisory evidence check.
4. After an actual review decision, explicitly accept/reject a finding with a rationale. Draft implications from accepted findings, then review those separately. Do not directly edit Delta rows to bypass these operations.
5. `publish` refreshes the search projection and requests index sync. `search` retrieves by collection and evidence tier and rechecks current eligibility. The index console alone is not the eligibility-enforcing retrieval interface.
6. `audit` resolves the full evidence trail. Withdraw obsolete source versions explicitly; corrections and new editions retain old history and require fresh review.

There are no scheduled imports or refreshes. Serialize mutations. PDF intake and text findings are implemented; typed numeric extraction, HTML/spreadsheet intake, learner updates and live director integration remain future work.

## Maintaining the console notebook

The checked-in SQL notebook is the source of truth. Publish updates with:

```bash
databricks workspace mkdirs /Shared/magneto-research-operations --profile magneto
databricks workspace import '/Shared/magneto-research-operations/Research operations' --file databricks/research-pipeline/notebooks/research_operations.sql --format SOURCE --language SQL --overwrite --profile magneto
```

Also upload this guide with `databricks workspace import '/Shared/magneto-research-operations/console-guide.md' --file databricks/research-pipeline/docs/console-guide.md --format RAW --overwrite --profile magneto`.

This installs documentation and read-only queries; it does not execute the notebook. Consult repository file `databricks/research-pipeline/docs/verification.md` for what has actually been tested.
