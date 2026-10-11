# Magneto medallion stages

The stages describe data quality and consumption boundaries in the existing
`workspace.magneto` namespace. No deployed browser, director, harness or learner
profile payload changes, renamed evidence tables, new framework, streaming service,
or grant changes are required.

## Learner flow

1. `learner_bronze_v1` retains the received confirmed-real **event JSON** before
   contract validation. It records an immutable payload digest, event/learner IDs,
   schema version, source and ingestion timestamp. It does not upload whole Story
   snapshots, unconfirmed transcripts, audio or camera frames. This preserves the
   existing confirmed-event upload scope; it does not introduce new consent or
   identity inference. Synthetic uploads are rejected before production storage.
2. `learner_observations_v1` remains the silver evidence API. Validation and
   immutable-ID deduplication read bronze payloads before insertion, and exact SQL
   readback checks insertion. `learner_quarantine_v1` records invalid-contract and
   immutable-ID conflict reasons against bronze digests. Failed cloud execution
   remains retryable rather than becoming a learner failure or quarantined event.
3. `learner_gold_v1` retains immutable `(learner_id, epoch)` profile JSON, its
   fingerprint, evidence digest, derivation version and publication timestamp.
   The existing six-category schema is enforced; metrics, chart data, category
   status and evidence IDs must match deterministic derivation and evidence must
   match silver. `learner_gold_latest_v1` selects the latest epoch per learner.

The local bridge reads silver, retrieves eligible research library passages,
validates exact excerpts, and gates category proposals with the native MLflow
judge. Genie can supply an optional overall summary; it cannot overwrite judged
categories. Library passages are not approved guidance. The worker stages profile
updates under ignored `.local/learner-intelligence/gold-pending/`, including their
reflection audits, and publishes gold before replacing the visible local profile.
Exact gold readback is required. Failed or ambiguous cloud publication retains both
the old visible profile and the candidate for an identical retry. The latest cloud
profile restores a missing/older local cache without inventing a new epoch.

An unchanged reflection checkpoint republishes the existing gold epoch idempotently;
no new epoch is created. Provenance-only processing keeps the prior immutable
profile. Empty evidence remains unknown and does not manufacture a gold epoch.
Existing browser facts, saved reader state and mock previews remain separate.
The localhost server is still required; no scheduled cloud reflection job or
cloud-memory planner integration has been deployed. Use one local writer; these
MERGEs and readback checks are not multi-table transactions or distributed locks.

## Operations and migration

Use the existing `.venv-agent` and `magneto` SDK profile:

```sh
.venv-agent/bin/python scripts/learner_cloud.py setup
printf '{}' | .venv-agent/bin/python scripts/learner_cloud.py backfill
printf '{"learner_id":"story-SESSION_ID"}' | .venv-agent/bin/python scripts/learner_cloud.py replay
printf '{"learner_id":"story-SESSION_ID"}' | .venv-agent/bin/python scripts/learner_cloud.py read
```

`setup` creates the additive tables/view alongside the unchanged silver table.
`backfill` retains existing silver events in bronze with the explicit source
`historical-silver-backfill-v1`; these are historical normalized events, not
reconstructed original inputs. New intake uses `confirmed-story-event-v1`.
`replay` requires an explicit learner, reads retained bronze and performs the same
validation/deduplication without model calls, profile epochs or physical actions.
A quarantined payload causes replay to fail explicitly; it never overwrites the
original silver event. Reviewed corrections remain a separate future workflow.
Existing local judged epochs migrate to gold on their next successful sync.

The additive SQL storage layout is internal. The established learner-profile-v1
and normalized event producer/consumer contracts and examples are unchanged.
Synthetic cloud proofs keep their existing separate table and profile store and
do not exercise production medallion tables.

## Research flow

The existing research pipeline already provides logical stages:

- Bronze: immutable original bytes in `references`, `research_sources`, and
  per-run parser/extractor artifacts supporting replay and audit.
- Silver: `research_chunks`, candidate findings and eligibility views preserving
  citations and rejecting incomplete/expired/withdrawn evidence. Accepted findings
  have explicit human review; extraction success does not grant acceptance.
- Gold: approved, eligible recommendations and v1 guidance exports.

`research_search_documents` is a serving projection spanning library, reviewed
and approved tiers; it is not a gold-only table. Keep those filters explicit.
`research_reviews` and `research_runs` support all stages rather than representing
additional layers. No research rows are automatically promoted or approved by
this change. Existing recorded intake has zero reviews/eligible recommendations;
the approved pathway is implemented, but genuine approved publication is pending.

## Validation

Run `npm run check:intelligence`, `npm run check:contracts`, `npm run check` and
`python3 -m unittest discover -s tests -p test_system_status.py`. Offline storage
boundary tests cover retained invalid input, synthetic isolation, immutable
conflicts, replay, exact gold readback, deterministic metrics, multiple learners,
cloud failure and recovery. Inspect `/system.html` on the local server, including
bronze/silver/gold details and animation. Metadata probes use table metadata only;
they do not prove SQL writes, judged publication or educational effectiveness.

## Recorded verification — October 11, 2026

Live table/view setup and SQL count reads passed using the existing warehouse.
Bronze, silver, quarantine, gold and latest-gold each contain zero rows; historical
backfill therefore migrated zero events. Missing-learner gold readback returned
null. No fixture was inserted into production. See
[`learner-medallion-verification.json`](../../reports/learner-medallion-verification.json).
The System map’s new connection details, rendered edges and animation were
checked in Chrome. A genuine learner publication through the full flow remains
unverified until confirmed real evidence is available.
