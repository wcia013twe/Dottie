-- Databricks notebook source
-- MAGIC %md
-- MAGIC # Research knowledge base — operations
-- MAGIC Teaching and industry have equal processing and review capabilities. This notebook contains **read-only SQL**. Attach the existing SQL warehouse `a5e11b7fe2c6dbbc`; running cells reads evidence without invoking AI models or approving anything.
-- MAGIC
-- MAGIC **Navigation:** Catalog Explorer → `workspace.magneto` → `research_*`. Originals and AI artifacts: volume `workspace.magneto.references`, folder `research`. MLflow experiment: `/Shared/magneto-research` (ID `1306573313615572`). Search endpoint: `magneto-research`; index: `workspace.magneto.research_index`.
-- MAGIC
-- MAGIC [Process a registered PDF](https://dbc-129a8d44-1940.cloud.databricks.com/jobs/966696100501459) · [Metadata smoke check](https://dbc-129a8d44-1940.cloud.databricks.com/jobs/1116672964506265)
-- MAGIC
-- MAGIC **Workflow:** CLI `ingest` → `process` (or processing job) → `extract` → explicit finding review → `draft` implication → explicit implication review → `publish` → `search`. `judge` is advisory. Uploading files alone does not register them. No automatic schedules or learner updates exist.
-- MAGIC
-- MAGIC CLI from repository root: `PYTHONPATH=databricks/research-pipeline/src .venv-agent/bin/python -m magneto_research.cli --config databricks/research-pipeline/config/operations.toml --profile magneto --help`. Full instructions: `databricks/research-pipeline/README.md` and `docs/console-guide.md`.

-- COMMAND ----------
-- MAGIC %md
-- MAGIC ## Current searchable evidence
-- MAGIC `library`: original passages; `reviewed`: accepted findings; `approved`: approved implications. Missing tiers mean no eligible records. Raw table counts include historical and unreviewed evidence.

-- COMMAND ----------
SELECT collection, tier, kind, count(*) AS eligible_records
FROM workspace.magneto.research_eligible_documents
GROUP BY collection, tier, kind ORDER BY collection, tier;

-- COMMAND ----------
-- MAGIC %md
-- MAGIC ## Source inventory
-- MAGIC `id` is the immutable source version accepted by the processing job. Use `volume_path` to inspect the original PDF. A new edition does not automatically withdraw the old one.

-- COMMAND ----------
SELECT s.id, s.source_id, s.collection, s.title, s.uri, s.volume_path,
       s.sha256, s.metadata, s.valid_until, coalesce(r.action, 'active') AS source_status
FROM workspace.magneto.research_sources s
LEFT JOIN workspace.magneto.research_latest_reviews r ON s.id = r.subject_id
ORDER BY s.created_at DESC LIMIT 100;

-- COMMAND ----------
-- MAGIC %md
-- MAGIC ## Findings and review queue
-- MAGIC This includes candidates requiring first review or renewed review. `currently_eligible` is authoritative for use; a historical accepted decision may no longer be sufficient. Inspect context and the original PDF before a decision. Exact quote presence does not establish scientific quality. Numbers are still stored in finding text; no typed numeric extraction exists.

-- COMMAND ----------
SELECT f.id AS finding_id, s.collection, s.title, c.locator,
       get_json_object(f.body, '$.statement') AS statement,
       get_json_object(f.body, '$.quote') AS quote,
       get_json_object(f.body, '$.context') AS context,
       get_json_object(f.body, '$.limitations') AS limitations,
       c.text AS original_passage, coalesce(r.action, 'needs_review') AS latest_decision,
       e.id IS NOT NULL AS currently_eligible, run.status AS extraction_status
FROM workspace.magneto.research_findings f
JOIN workspace.magneto.research_chunks c ON f.chunk_id = c.id
JOIN workspace.magneto.research_sources s ON c.source_version = s.id
JOIN workspace.magneto.research_runs run ON f.run_id = run.id
LEFT JOIN workspace.magneto.research_latest_reviews r ON f.id = r.subject_id
LEFT JOIN workspace.magneto.research_eligible_findings e ON f.id = e.id
ORDER BY currently_eligible, s.collection, f.id LIMIT 100;

-- COMMAND ----------
-- MAGIC %md
-- MAGIC ## Approved implications
-- MAGIC Every supporting finding must remain eligible. No rows is a valid result before human approval. These records are not automatically connected to the live teaching agent.

-- COMMAND ----------
SELECT id, collection, get_json_object(body, '$.text') AS implication,
       get_json_object(body, '$.finding_ids') AS supporting_finding_ids,
       get_json_object(body, '$.rationale') AS rationale,
       get_json_object(body, '$.limitations') AS limitations
FROM workspace.magneto.research_eligible_recommendations LIMIT 100;

-- COMMAND ----------
-- MAGIC %md
-- MAGIC ## Recent operations and failures
-- MAGIC Run details contain MLflow references and saved artifact paths; failed-run metadata is nested under `initial`. An incomplete operation is not eligible. Retry explicitly after diagnosis; do not approve or rewrite run status to bypass failure.

-- COMMAND ----------
SELECT id, subject_id, operation, status, created_at, actor, details
FROM workspace.magneto.research_runs ORDER BY created_at DESC LIMIT 100;

-- COMMAND ----------
-- MAGIC %md
-- MAGIC ## Review history and audit links
-- MAGIC `recommendations.body.finding_ids` → `findings.chunk_id` → `chunks.source_version` → `sources.id`. Processing links use `run_id`; review links use `subject_id`. Use CLI `audit recommendation ID`, `audit finding ID`, or `audit passage ID` for a complete record. Perform acceptance, rejection and withdrawal through explicit CLI review commands with a rationale. Do not directly edit records here.

-- COMMAND ----------
SELECT subject_id, action, rationale, created_at, actor
FROM workspace.magneto.research_reviews ORDER BY created_at DESC LIMIT 100;
