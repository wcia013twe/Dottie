# Verified source intake — October 11, 2026

Added **8 documents / 630 PDF pages / 395 passages**. The library now has **10 registered documents / 409 eligible passages**. All eight source-targeted retrieval checks passed after index synchronization.

The additions are four teaching references and four industry documents. They remain source-library material, not approved teaching advice. No new findings were extracted or approved during this intake.

| Source | Collection | New passages |
| --- | --- | --- |
| aph-fy2025 | industry | 4 |
| polly-guide | industry | 9 |
| polly-menu | industry | 32 |
| rnib-braille-200 | industry | 12 |
| braille-pedagogy-review | teaching | 13 |
| ies-study-guide | teaching | 44 |
| scanning-study | teaching | 16 |
| ueb-2024 | teaching | 265 |

RNIB’s original DOCX, rendered PDF and conversion record are preserved together; both cloud-file checksums were verified. UEB’s whole-document parse timed out; completed page-range results were recovered and the final run validated all original page IDs 0–407 before publication. Failed runs remain auditable.

See `source-collection.md` in this workspace folder for interpretation boundaries and I-M-ABLE/UDL acquisition recommendations. Exact source versions, processing runs, search runs and citation checks are in `source-intake-results.json`.

Final publication run: `13905926-a90b-4f84-89e7-8b9e05669313`.

Verification: 40 research tests, repository `npm run check`, and `git diff --check` passed. The actual ingestion and search checks ran against the existing Databricks warehouse/index. No additional namespace, endpoint, grant, schedule, or local research UI was created.
