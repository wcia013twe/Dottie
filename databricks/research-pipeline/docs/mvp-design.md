# Research and industry intelligence MVP

Status: implemented, deployed, and verified for source ingestion, parsing/preparation, extraction, advisory judging, and cited library search on October 11, 2026. This replaces the earlier open-model/file-ledger proposal with the user-approved Databricks-managed design. See [README](../README.md) for commands and [verification](verification.md) for observed results.

## Product purpose

Build an extensible domain knowledge base that can explain which source passage supports a finding and which reviewed findings support an implication. Teaching research and industry intelligence receive equal intake, processing, review, search and maintenance capabilities. Personalization can later retrieve approved evidence to inform bounded changes to pacing, scaffolding or practice. The research layer does not itself infer a learner profile or change teaching.

## Chosen architecture

Keep original PDFs in the existing reference volume, structured metadata and evidence in Delta, and the search index derived from readable evidence records. Use Databricks `ai_parse_document`, `ai_prep_search` (Beta), `ai_extract`, managed embedding endpoints, AI Search, and MLflow tracing/judges. Use ordinary links and SQL joins. A graph is deferred until measured questions require multi-hop reasoning that this baseline cannot answer.

Original source text is separate from enriched embedding text. A retrieved claim always resolves to a saved source version and physical PDF page references. An LLM assessment is advisory; it does not confer human approval or prove a learner benefited.

## Scope implemented

1. Explicit PDF registration with title, stable source ID, collection, publisher, URI, rights basis, acquired/publication dates, optional expiry, SHA-256 and immutable original path.
2. Managed parsing and search preparation with persisted raw function outputs, fail-closed partial parsing and page validation.
3. Managed extraction into candidate findings: reported statement, exact quote, context and limitations. A fabricated quote fails validation; all accepted claims still need source review.
4. Distinct acceptance of findings and approval of implications; authenticated actor, rationale, exact immutable ID and timestamp retained.
5. Searchable library passages, reviewed findings and approved implications, filtered by teaching/industry collection. Source withdrawal invalidates dependent eligibility, including when the index is stale.
6. MLflow-backed judging and trace links; exact prompts and managed-function metadata retained. Underlying managed-model revisions may not be exposed and must not be invented.
7. Databricks-native evidence inspection and a read-only operations notebook, plus CLI search/audit/review/publish/export operations.

## Initial real sources

The IES foundational-reading practice-guide summary establishes the teaching ingestion path. It is general print-reading guidance and must not be presented as a braille-user study. NLS News, April–June 2026, establishes the industry path as dated institutional reporting. Intake metadata is checked in under `examples/`; source PDFs remain in the reference volume. Neither source is automatically approved as an intervention.

Expand with actual braille-user studies, standards, device manuals and institutional reports selected for concrete questions. Keep study/population/task/comparator and reporting-period/unit/denominator qualifications in each finding's context. Missing context stays explicitly unreported. No fixed corpus quota, synthetic claim count, or arbitrary promised accuracy/review-time improvement is imposed.

## Evidence and updates

Preserve originals for citation inspection, re-parsing and change detection. Distinguish a paper from the study/cohort it reports; related publications are not independent replications. Correction creates new evidence IDs and requires review. Withdrawal excludes dependent recommendations from current retrieval. Reinstatement requires fresh downstream review. Old versions remain auditable.

Publication uses a Delta MERGE and an explicit triggered index sync. Query-time eligibility checks prevent a stale index from serving withdrawn records. An outage remains an error; a successful search without an eligible match returns an empty list. Serial operator mutations are the initial concurrency boundary.

## Teaching contract

Approved recommendations can export precisely the existing v1 guidance fields. They must have justified uppercase target letters, permitted difficulty tags and a complete single-source citation. General findings and multi-source implications remain internal until a defensible v1 representation exists. Industry results never enter that teaching export. The live director's request/response schema remains unchanged.

## Validation and deferred work

Local tests cover exact quotes, page references, partial model output, unreviewed evidence, stale-index filtering, source eligibility, contract projection, SQL parameter binding, service failures and tracking isolation. Live verification must separately establish parse/preparation/extraction/search and MLflow behavior using real sources.

Evaluate future retrieval changes with representative questions in both collections and checked source citations. Track context relevance, citation correctness and reviewer effort before claiming improvements. Judge agreement is not learner-outcome evidence.

Deferred: participant datasets, CSV/XLSX analytics, HTML intake, automatic crawling/schedules, a knowledge graph, custom model hosting/fine-tuning, learner telemetry ingestion, personal-profile updates, adaptive interventions and live teaching integration. These are separate changes, not services implied by this implementation.
