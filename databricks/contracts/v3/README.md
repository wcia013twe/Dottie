# Learning attempts v3

Status: implemented upload boundary; no deployment or history-to-planner integration implied.

## Milestone 1: collect and deliver learning telemetry

PR #7 establishes the ingestion foundation: capture selected learning outcomes, retain stable student and attempt IDs, queue bounded batches, validate them, and acknowledge successful lakehouse writes. It is the first part of returning learning telemetry to the lakehouse. Local checks validate this code path; live lakehouse delivery still needs deployment and end-to-end verification.

The remaining milestones are:

1. Configure and deploy storage, then verify a synthetic session reaches the intended lakehouse tables.
2. Connect the Peter Rabbit coach and Orin harness to the same lean contract, keeping raw device telemetry outside learning attempts.
3. Build analysis and a Personal Intelligence tab showing evidence-linked student facts and learned behaviors with teacher review and correction.
4. Feed selected student history and, when connected, research context into teaching decisions and apply supported story adjustments through MCP.

The current SQL readback verifies uploads; it does not supply student history to the teaching planner. The adaptive teaching loop remains a later milestone.

## Record scope

One record describes one observed attempt. Student identity, session identity and schema version travel once per batch. The server restores them on each Delta row. New attempts use stable UUIDs; upload retries reuse those IDs. Session restarts retain the selected browser profile and create a new session ID.

`activity-catalog.json` is immutable by activity reference: changing a target, task, or story context requires a new reference version. Catalog entries contain context once; attempts contain only result, support, assessment and observation time. Unknown activity references and extra fields are rejected. No transcript, raw media, model explanation, timing metric, or device command is accepted.

`support: unknown` means support was not recorded; it must never be counted as independent success. Only `assessment: teacher_confirmed`, `result: correct`, `support: none` counts as an observed independent success. `unconfirmed` assessment requires `unconfirmed` result. Device errors and skipped opportunities stay outside learning attempts. These observations do not establish mastery or causal effects of support.

## Migration from v2

Deploy the consumer with both `/api/learning/events` (v2) and `/api/learning/attempts` (v3) before updating the browser. Existing v2 schemas and queued v2 events remain intact. The browser drains legacy events separately in bounded batches for the explicitly enabled profile (v3 batches also group by session); new responses use v3. Never infer support or assessment from old `correct` events, or merge old profile IDs automatically. Old events remain in `interaction_events_v2`; new observations use `learning_attempts_v3`.

Profiles retain the v2 profile contract. Local saved demo sessions without a profile are restored without discarding their progress. An explicit teacher control enables uploads for this browser profile. Disabling uploads stops subsequent batches; it does not delete records already stored. The MVP has one browser profile, not a multi-student selector.

The outbox keeps records until a matching acknowledgement arrives. Databricks returns IDs only after a successful SQL write and readback; pending, failed, canceled and timed-out statements produce a retryable service error. An identical retry is acknowledged; reusing an ID with different content is rejected. This is single-app serialized ingestion, not a claim of database-enforced UUID uniqueness across independent writers.

Confirmed preferences remain profile data. Browser-local Peter Rabbit practice summaries now influence the planner; cloud readback and teacher correction workflows remain future work. The existing v1 director decision and snapshot are unchanged.

## Enablement and analysis

Run python3 scripts/prepare_agent.py to package shared adapters and generate both catalog copies.
Set the existing SQL warehouse in platform/services.toml only when intentionally enabling storage;
the deployed app's identity needs access to the learning tables. On startup, configured learning storage
creates missing v2/v3 tables. No deployment, grants, table creation or uploads occur in local checks.

Run npm run check:learning, npm run check:contracts, and the existing reasoning/story checks.
The connected Caterpillar demo and Peter Rabbit coach produce opt-in v3 uploads. The rabbit batch
is a synthetic validated example; the Orin harness remains separate.

Useful analysis starts with counts by catalog target/task, support and confirmation, across sessions.
Join immutable activity references to the catalog rather than parsing their text. Keep attempted
recognition separate from instruction and unconfirmed responses. Do not compare unlike tasks or
interpret a within-session improvement as proof that a hint caused learning. Each attempt ID occurs
once in analysis; idempotent ingestion is essential. The opaque profile ID is a routing identity,
not independent authentication; the endpoint remains protected by Databricks App authentication.

## Peter Rabbit interaction producer

The local Peter Rabbit coach now emits v3 attempts for educator-confirmed independent/assisted
completion when uploads are enabled. Existing references retain their meanings; new immutable
references cover introduce/identify/match across all authored checkpoint targets. `try_later`
is not an incorrect attempt and stays out of telemetry. Assisted completion without a recorded
hint uses unknown support. Introduction records remain distinguishable by catalog task and must
not be counted as recognition mastery. Original observation IDs and UTC timestamps are retained.

Deploy the regenerated consumer catalog before enabling new references in a cloud environment.
The wire schema is unchanged. Personal Intelligence currently retains bounded browser-local
story history for review scheduling; reading lakehouse history into the planner is not implemented.

Word emphasis adds immutable `emphasize-<word>@1` references with task `emphasize`.
These represent keyword exposure and must not be aggregated as recognition or matching success.
The existing attempt envelope is unchanged; deploy the catalog/enum extension before new producers.
