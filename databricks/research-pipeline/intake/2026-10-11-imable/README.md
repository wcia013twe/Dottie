# I-M-ABLE author article intake — October 11, 2026

User-authorized intake of Diane P. Wormsley's **The Right to Literacy: Braille literacy for learners with cognitive impairments and additional disabilities**, JSPEVI Volume 9 (2016), printed pages 45–50. The article identifies itself as a paper presented at the WBU–ICEVI General Assembly, Orlando, August 2016.

Official source: https://www.spevi.net/wp-content/uploads/2015/07/JSPEVI-Vol-9-2016-1.pdf#page=46

## Original and processing scope

Preserve the complete publisher journal PDF unchanged at the registered source's volume path, with SHA-256. Only physical PDF pages **46–51**, corresponding to printed pages **45–50**, are parsed/prepared and indexed. The six pages were rendered and visually inspected, including the article title, ending, references and attribution. Other journal articles and its separate I-M-ABLE book review are outside this intake.

An explicit one-time operation uses the native `ai_parse_document` `pageRange` option, validates the exact original page IDs 45–50 (zero-based), then uses the existing preparation and passage validation functions. Its script and selected-page mapping are preserved as a run artifact. Original PDF pagination is retained in search citations. This does not add a generic page-selection CLI feature. **Do not run the whole-document `process` command for this source version**: it would process unrelated articles in the journal. Reuse the recorded scoped procedure for a deliberate retry.

## Interpretation and use

Classify this as an **author/practitioner account with illustrative learner cases**. It provides a source for the origins of I-M-ABLE, meaningful vocabulary, personal stories and literacy access, but does not replace the full practice guide or establish causal effectiveness. Preserve the author's explicit uncertainty about alternative explanations for observed progress. Case-specific numbers must retain the learner, time window and anecdotal context; do not interpret them as population estimates, expected gains or controlled study results.

The source metadata records these boundaries. Categories here are curatorial documentation, not a new implemented search-filter field. No finding extraction, human acceptance, recommendation approval or learner-profile update is authorized by this intake.

The full APH I-M-ABLE practice guide remains unacquired. The earlier FIMC-VI handout access failure remains true, but does not describe availability of this newly located author article.

## Verification and console documentation

`results.json` records the source version, processing/publication runs, counts, and source-targeted retrieval check when completed. This check establishes source coverage and citation resolution, not educational validity or general retrieval quality.

Databricks workspace folder: `/Shared/magneto-research-operations/`; this note is published as `imable-intake.md` and the results as `imable-intake-results.json`.

## Completed intake

Added four cited passages from the six article pages. Index synchronization reached 414 entries; the source-targeted retrieval check passed. The library now contains 12 source records and 414 eligible passages, with zero reviews. Processing run: `86fb2680-7d3e-4a53-b460-cc9442b5c9be`; publication run: `05eca50c-7d2f-4567-b35a-4682054bd62c`; retrieval run: `ae1abd31-575b-4255-b362-83c1ac2fd90c`. Repository `npm run check` and `git diff --check` passed. No pipeline code or deployment configuration changed.
