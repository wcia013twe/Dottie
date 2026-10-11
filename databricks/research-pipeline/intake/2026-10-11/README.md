# October 11 research intake

User-authorized additions from the recommended source list. The eight source metadata JSON files are exact input metadata for the existing `ingest` command. Publisher files remain in the reference volume; they are not copied into this repository. Ingestion is not human acceptance or recommendation approval. Actual source versions, completed runs, passage counts and retrieval checks are recorded in `results.json` when verified.

## Source map

| Source ID | Collection | Evidence category | Intended question | Interpretation boundary |
| --- | --- | --- | --- | --- |
| `braille-pedagogy-review` | teaching | Scoping review | What evidence exists for beginning braille instruction, and which original studies should we acquire next? | K–4 mainstream, English-first-language learners without additional disabilities; search through 2022; review citations are not independent replications |
| `ies-study-guide` | teaching | General learning practice guide | How can spacing, retrieval and study scheduling inform a candidate lesson strategy? | General learning evidence; transfer to braille and this individual requires review; retain recommendation-specific evidence ratings |
| `scanning-study` | teaching | Longitudinal observational study | Which measured aspects of finger scanning relate to braille reading performance? | Eight children in Japan; repeated lines are not additional participants; no inference of hand movement from response latency alone |
| `ueb-2024` | teaching | Normative code reference | Which UEB rule governs a symbol, contraction or transcription? | Not teaching-effectiveness evidence or a validated translator; inspect original glyphs; preserve publisher license and unmodified edition |
| `polly-guide` | industry | Vendor quick-start manual | What device, onboarding and educator workflows does Polly document? | Published edition may differ from current software; vendor documentation is not a controlled learning evaluation |
| `polly-menu` | industry | Vendor activity/menu reference | How does a comparable product organize braille activities? | Menu availability and activity names do not establish efficacy |
| `rnib-braille-200` | industry | User survey report | What learning barriers, uses and technology needs did responding UK braille users report? | Self-selected sample; denominators and questions matter; not all blind people or a causal intervention study |
| `aph-fy2025` | industry | Institutional annual report | What initiatives, deployments and operational figures does APH report? | Fiscal-period and self-report qualifications; not total market demand; preserve ambiguities and absent survey denominators |

Evidence categories above are curatorial documentation, not a new implemented search-filter field. Both collections use the same ingestion and review workflow. Source metadata includes interpretation notes, and extracted candidates still require source/context review.

## Acquisition and conversion

The previously suggested Polly guidebook URL returned HTTP 404. The current APH product page links to the 32-page Quick Start Guide stored under `media.aph.org`; that official document is used instead, together with the 67-page menu map.

RNIB publishes its report as DOCX. Preserve it unchanged as `original.docx` beside the ingested `source.pdf`. The PDF is a one-off rendering using bundled LibreOfficeDev 26.8.0.0.alpha0, not a general DOCX intake adapter. `conversion.json` records original and rendered SHA-256 values, converter version and citation semantics. All 25 rendered pages were visually inspected in contact sheets; all cell text from the original's 10 tables was found in the PDF text. Citations refer to physical pages of the archived rendering.

Other documents are unmodified publisher/repository PDFs. Their original checksums are retained by the pipeline. Unknown exact publication days remain null; do not invent a full date from a year or month. The UEB rulebook contains 408 PDF pages, within the current 500-page parser limit. Its first whole-document parse reached the SQL adapter's ten-minute timeout and left no eligible passages. The recovery uses Databricks' native `pageRange` option in non-overlapping 50-page sections against the unchanged original PDF. It requires all original page IDs 0–407, rejects partial parsing or incorrect page IDs, saves each range's parser/preparation artifacts, and writes passages in groups of 25 under a single completed processing run. All failed attempts remain in history. A page in the 201–250 section reported an execution-slot timeout; that section was re-parsed successfully before publication. A separate last-page probe returned page ID 407 with no parser errors, verifying that this workspace preserves original pagination. A later API read timeout occurred after pages 51–100 had finished remotely; that completed result was recovered by statement ID. The final recovery uses literal page-range maps and external SQL result links for large parser responses, reuses the verified completed sections, and validates the entire original page inventory. Preparation reads the saved parser JSON from the volume rather than passing multi-megabyte JSON as a SQL parameter (the warehouse enforces a 1 MiB combined parameter limit). Search preparation also emitted empty entries containing neither source text nor page citations. The recovery records and excludes only those empty entries; all substantive passages must pass the existing source-page validation. Raw preparation output and the recovery script remain run artifacts. This is an explicit intake recovery, not an automatic retry policy or a new general CLI option.

## Instructional frameworks to acquire next

**I-M-ABLE is recommended as an instructional-method reference.** APH describes continuous assessment of learner strengths and needs, personally meaningful vocabulary, student-created stories, phonics/contractions and fluency. These are relevant to story-mode planning. Preserve the intended learner population and separate method descriptions from independently evaluated outcomes. Do not turn a framework into an automatic judgment about a person's abilities or a fixed learning style.

- [Author's book at APH](https://www.aph.org/product/i-m-able-individualized-meaning-centered-approach-to-braille-literacy-education-epub/): sold as EPUB; the full text has not been acquired or loaded. A publisher description is not a substitute for the practice guide.
- [Author presentation at FIMC-VI](https://www.fimcvi.org/past-events/i-m-able-wormsley): public event description and linked handouts; the handout was not retrieved during this intake. No framework text has been inferred from inaccessible material.
- [CAST Universal Design for Learning](https://www.cast.org/resources/about-universal-design-for-learning/): useful next as a broader accessibility/design framework for engagement, representation, and action/expression. Not loaded in this batch and not braille-specific effectiveness evidence.

These are recommendations, not additional ingestion or purchase authorization. Loading a purchased framework requires the actual acquired file and an appropriate recorded processing basis. Neither the absence of that book nor pending framework review blocks the eight authorized sources above.

`retrieval-checks.json` contains one source-targeted query per new document. These checks establish index coverage and citation resolution, not relevance accuracy on unseen questions or educational quality.
