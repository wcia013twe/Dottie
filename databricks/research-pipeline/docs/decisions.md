# Decision register

| Decision | Status | Consequence |
| --- | --- | --- |
| Operations interface | Databricks console requested October 11, 2026 | Local research UI and HTTP bridge removed; console guide and read-only notebook maintained alongside CLI |
| Separate research package and deployment | Confirmed | Do not alter the live director for research-only changes |
| Reuse existing catalog/schema/reference volume | Confirmed | Research bundle does not provision shared containers |
| Separate document extraction and dataset analysis | Confirmed | Do not force all inputs through document processing |
| Smoke checks are read-only metadata checks | Implemented | No ingestion, inference, trace writes or index queries |
| Manual research jobs | Deployed October 11, 2026 | Metadata smoke and explicit source processing; no schedules; see verification report |
| Instructional frameworks | CAST organizer and Wormsley 2016 author article processed and retrieval-verified; full I-M-ABLE guide not acquired | Keep framework/author accounts distinct from controlled evidence; scoped journal intake preserves original pagination |
| Curated source intake | Eight additions verified October 11, 2026 | Four teaching and four industry documents; 10 total sources / 409 passages; exact provenance and checks in intake receipt |
| Source selection and update policy | Explicit paper-first intake implemented | Versioned public PDFs; manual refresh/withdrawal; no automatic internet ingestion |
| Shared guidance record | Unchanged [v1](../../contracts/README.md); internal export implemented | Only currently approved eligible teaching recommendations; no live consumer wiring |
| Analytical questions and methods | Undefined | No dataset analysis logic |
| Updater experiment connection | Connected and synthetic trace readback verified October 11, 2026 | `/Shared/magneto-research`; explicit creation/UC binding, operational run/trace tracking, advisory evidence judge; no director experiment reuse |
| AI Search publication/retrieval contract | v1 unchanged; internal research search implemented | Research index has library/reviewed/approved tiers and both collections; serving readiness tracked separately |
| Research-to-director context contract | Retrieval boundary defined; snapshot extension deferred | No live-agent integration; coordinate a version change before adding fields |
| Teaching and industry scope | Equal MVP scope requested October 11, 2026 | Both collections receive intake, extraction, review, publication, search, and evaluation; industry findings stay outside teaching contracts |
| MVP implementation design | Implemented in [mvp-design.md](mvp-design.md) | Managed parsing, preparation, extraction, embeddings and search; Delta evidence records; no generic graph or custom model host |

Update this register when a decision is supplied or behavior is verified. A configuration example, successful local test or SDK metadata response does not establish successful cloud processing.
