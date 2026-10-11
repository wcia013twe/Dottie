# Verification — October 11, 2026

## I-M-ABLE author article verified

Loaded Diane P. Wormsley’s freely published 2016 “The Right to Literacy” article only: original PDF pages 46–51 (printed pages 45–50). Preserved the complete unmodified journal PDF; scoped native parsing validated original page IDs 45–50 and created four passages. Index reached 414 entries and source-targeted teaching/library retrieval passed with original page citations. Totals: 12 source records, 414 eligible passages, zero reviews. The full practice guide remains unacquired. Exact source version and processing/publication/retrieval runs: [intake](../intake/2026-10-11-imable/README.md) and [results](../intake/2026-10-11-imable/results.json), also published as `imable-intake.md` and `imable-intake-results.json` in the operations workspace folder. Repository `npm run check` and `git diff --check` passed; no shared contract, pipeline code or deployment change.

## Framework follow-up

CAST UDL 3.0 numbered graphic organizer was registered and processed as a teaching framework (one page, one eligible passage). Source and run details: [framework intake](../intake/2026-10-11-frameworks/README.md) and [results](../intake/2026-10-11-frameworks/results.json). Publication refreshed the search table and requested sync. Initial managed retries reported exhausted free serverless compute capacity; the existing retry recovered, the index reached 410 entries and source-targeted retrieval passed with the CAST source and page 1 citation (search run `17a848b5-ed9a-469a-95cf-17521b3b136d`). Current totals are 11 sources and 410 passages. No other workload was stopped and no new findings or approvals were created. I-M-ABLE remains unacquired because the public handout returned HTTP 403. Repository `npm run check` passed; no pipeline code or deployment configuration changed. Earlier verified batches below remain historical.

## Curated intake verified

Loaded eight additional documents, equally split between teaching and industry: braille pedagogy review, IES study guide, finger-scanning study, UEB 2024 rulebook, Polly quick-start guide and menu map, RNIB Braille 200 report, and APH FY2025 annual report. They added 630 PDF pages and 395 eligible passages. The full library now contains 10 source versions and 409 eligible passages (five documents per collection).

Final publication run `13905926-a90b-4f84-89e7-8b9e05669313` completed and requested index sync. The index reached 409 rows; all eight source-targeted retrieval checks found the intended source in the top five with resolved original-page citations. These are coverage checks, not an educational or retrieval-quality benchmark. RNIB original DOCX and rendered PDF hashes were verified in cloud storage. UEB recovery run `7ea2fe60-7807-4091-aa3f-f06d0d9351b3` validated all 408 original page IDs and saved 265 passages after native range parsing, external-result recovery, stored-file preparation and exclusion of explicitly logged empty entries. Failed attempts remain auditable; the standard CLI still processes whole PDFs.

No new findings were extracted or reviewed during this intake. Verified review counts remain zero reviews, zero accepted findings and zero approved recommendations. I-M-ABLE and CAST UDL are recommended next but have not been acquired or loaded.

Exact sources, processing runs, checks and limits: [intake receipt](../intake/2026-10-11/receipt.md), [results](../intake/2026-10-11/results.json), and [source catalog](../intake/2026-10-11/README.md). These are also published in `/Shared/magneto-research-operations/` as `source-intake-receipt.md`, `source-intake-results.json`, and `source-collection.md`. Local validation: 40 research tests and `npm run check` passed. No deployment configuration or shared contracts changed in this intake.

## Console-only operations update

At the user’s request, removed the local research page, JavaScript, HTTP bridge and its five dedicated tests. Research storage, search, CLI, jobs and review logic are preserved. The earlier browser results below are historical verification, not a maintained interface.

Published the read-only SQL notebook `/Shared/magneto-research-operations/Research operations` (object `368792836365572`) and `console-guide.md` alongside it. All six SQL cells executed successfully against the existing warehouse: 2 collection/tier count rows, 2 sources, 4 findings, 0 approved implications, 15 recent runs and 0 reviews. This verifies the SQL through Statement Execution, not an interactive notebook run.

Current checks: 40 research tests, `npm run check`, and `git diff --check` passed. Restarted the localhost server without the research handler; browser verified the retired URL returns 404 and the existing parts viewer still loads. The 45-test count below includes the now-removed bridge tests.

See [the console guide](console-guide.md) for the resource map, data dictionary, evidence tiers and operating workflow.

## Original implementation checks

- Research unit tests: 40 passing (including tracking isolation, provenance and failed/stale retrieval).
- Local research bridge tests: 5 passing (literal command arguments, request validation, cross-origin rejection, explicit failures).
- `node --check web/research.js`, repository `npm run check`, and `npm run check:contracts` passed. Contract check validated 9 schemas and 11 examples; no shared payload changes.
- Authenticated `databricks bundle validate -t dev --profile magneto` passed.

## Workspace changes and observed results

Existing workspace: `https://dbc-129a8d44-1940.cloud.databricks.com`. Reused `workspace.magneto`, `references`, and serverless warehouse `a5e11b7fe2c6dbbc`. CLI access works outside the local sandbox; the sandbox-only credential failure did not mean the user was logged out.

Created seven research tables, five eligibility/review views, a STANDARD endpoint `magneto-research`, and Delta-sync index `workspace.magneto.research_index`. Embeddings use existing `databricks-qwen3-embedding-0-6b`. No catalog, schema, volume or grants were created. The index became ready with 14 rows after initial provisioning; a sync attempt before readiness failed explicitly.

Research experiment `/Shared/magneto-research` (`1306573313615572`) is separate from the director. Its Unity Catalog trace destination was bound and a synthetic connection trace was written/read successfully. Subsequent operations record research run and trace links.

| Source | Source version | Observed result |
| --- | --- | --- |
| IES foundational-reading guide summary | `d980f9bfda7168daec909175bc787925d7e5e37f9595474a46843b1fdc270a4a` | Registered PDF; managed parsing/preparation completed; 8 original passages |
| NLS News, April–June 2026 | `8dc8d9cbb18f9838be8208cbce6689f72fd1edd12688edd9c8b5005c82b0256b` | Registered PDF; managed parsing/preparation completed; 6 original passages |

Teaching extraction run `4c5915be-f609-4ece-b83e-1b82e40bfd62` produced 3 candidate findings and rejected 1 unsupported/unresolvable quote. Industry extraction run `6041101b-d6c3-4b07-84ad-079a804f6db5` produced 1 candidate and rejected 7. These are engineering verification samples, not extraction-accuracy benchmarks. All four candidates remain unreviewed. No review or teaching-approval events were created.

An advisory Qwen evidence judge completed for one candidate: research run `a684979a-7662-475f-b599-cc25f52e56c7`, MLflow run `fb191728b36444e49dd994a97818f6d3`, trace `trace:/workspace.magneto.1306573313615572/7e2a166603fe3d5c8e2cb87a6dc31fb5`. Its true assessment did not change approval status.

Live testing found and fixed a managed extraction schema-format mismatch, PDF whitespace/quotation normalization, and a Databricks wheel-task `SystemExit(0)` failure. Resolved citations are saved as original source substrings; unresolved candidates are recorded as rejections rather than silently published. Failed attempts remain in run history.

## Deployment

The package wheel and two manual jobs were deployed:

- [Research processing](https://dbc-129a8d44-1940.cloud.databricks.com/jobs/966696100501459): parse/prepare a supplied registered source version; no schedule, automatic approval, or publication.
- [Research smoke](https://dbc-129a8d44-1940.cloud.databricks.com/jobs/1116672964506265): metadata only. Corrected run `991989333835890` completed SUCCESS. Earlier run `910374184785387` reached all configured resources but was marked failed due to the now-fixed success exit behavior.

PDF processing was executed through the CLI against the SQL warehouse; the deployed processing job has not separately been run. Source originals and AI outputs reside in the reference volume, not in the repository.

## Final search and browser checks

- Teaching library search returned 5 cited passages in the localhost browser; final batched-read run `c6017525-42db-4847-80cb-7ad103896ed3`.
- Industry library search returned 2 NLS passages with original source and page references; run `f28961f3-bdfe-4579-9d74-1efe148fbeca`.
- Reviewed teaching search returned an explicit successful empty result, as all findings are unapproved; run `c32f1dc1-e9c6-449a-962b-d5b90ab70149`.
- Publication run `b89c3a86-c12f-4490-aa10-7d0c84252996` refreshed the search table and successfully requested sync once the index was ready.
- Browser collection filters, the real search request, full-passage/evidence disclosures, and 375 px responsive layout were checked. No horizontal overflow. Screenshot: `reports/research-intelligence-live.png`.
- Library retrieval now batches current-status and citation reads into one SQL query, avoiding a database round trip per result. Full historical audit remains available through the CLI. No latency benchmark is claimed.

Source-withdrawal exclusion, recommendation review/export gates and failure handling have local tests; no human scientific approval was fabricated for cloud demonstration. The deployed processing job itself remains unexecuted, while the same processing implementation ran successfully via the CLI. No live teaching integration, learner-profile updates, learner uploads, scientific acceptance, or intervention-effectiveness validation is claimed.
