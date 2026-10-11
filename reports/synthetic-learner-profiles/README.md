# Fictional learner test pack

All records in this directory are synthetic. `confirmed: true` describes a
fictional instructor observation within the scenario, not approval by a real
teacher. `trace_id: null` means no MLflow trace is linked. These files are not
live learner records and must never be uploaded to the real observations table.

Regenerate and verify from the repository root:

```sh
databricks/magneto-director/.venv/bin/python scripts/generate_synthetic_profiles.py
npm run check:contracts
npm run check:intelligence
```

The generator uses the existing `ProfileStore` producer and validates every
event and output profile against the authoritative learner-profile-v1 schemas.
Its temporary stores are deleted after verification. It never calls cloud
services, changes the live store, selects a learner in About me, or replaces the
existing mock preview. A custom `--output-dir` must remain outside `.local`.

| Evidence batch | Scenario | Expected behavior |
| --- | --- | --- |
| `river.evidence.json` | 55 events over three fictional sessions | Comparable B/D recognition changes 40% → 80% → 60%; three conditional epochs. Supported responses, repeats and response alternatives are retained. |
| `sky-insufficient.evidence.json` | One supported observation for a different learner | No percentages or trend; six category cards remain available. |
| `river-changed-condition.evidence.json` | River plus one newer observation under different presentation/difficulty | No pooled recognition percentage or chart for the latest insufficient comparison group. |

Corresponding `.profile.json` files are fresh final snapshots. The
`river-epoch-1.profile.json` through `river-epoch-3.profile.json` files preserve
successive publications and history. `verification.json` records assertions
for unchanged replay, immutable-ID conflicts, another learner, and mixed real
versus synthetic source rejection. Identical replay retains epoch 3 and publishes
nothing.

To exercise the producer with your own **isolated** persistent test store:

```sh
python3 scripts/learner_intelligence.py \
  reports/synthetic-learner-profiles/river.evidence.json \
  --store /tmp/magneto-synthetic-river-store \
  --output /tmp/magneto-synthetic-river.profile.json
```

The Braille chart denominator is five valid confirmed responses per session;
deferred responses, device failures and unconfirmed observations do not enter
that denominator. Transfer has one observation and no percentage. Tactile and
interests contain deferred observations and correctly remain unknown: v1 has
no supported outcomes to derive a positive finding in those categories. A
`with_help` outcome describes assistance, not who requested it.

This pack verifies local evidence/profile behavior. It does not establish
educational effectiveness, physical readiness, live SQL/Genie behavior,
MLflow-to-learner joins, or planner profile consumption. A cloud synthetic run
needs a separate explicitly synthetic table and adapter; production ingestion
continues to reject these rows.
