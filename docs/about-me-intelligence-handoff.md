# About me: learner intelligence and update epochs

## Accepted product direction

About me leads with the learner character and shorthand stats, then exactly six differently colored, expandable category summaries: Braille recognition; tactile exploration; understanding instructions; answering & asking for help; retention & transfer; interests & participation. Start all six collapsed. The collapsed state shows the category, a plain-language status, one concise finding and a short teaching next step. Use percentages where supported, without fractions in the summary; retain counts, denominators and comparison conditions in expanded evidence. Do not invent percentages for insufficient observations or isolated transfer examples. Charts, analysis, evidence and local fact editing appear inside the relevant category; the B/D chart belongs inside Braille recognition. No spider chart or composite ability score. The instructor does not need MLflow internals. Every insight must be **reasoning backed, useful, actionable, concise, and traceable**. Findings may describe improvement, a stable preference, mixed evidence, a difficulty or insufficient observations. Review all categories each epoch but do not force a new insight for each. Lead with what is known about this learner, not a log of agent interactions. Explain evidence briefly and suggest one specific teaching action. Keep supporting records expandable.

Current UI: `web/learn/intelligence.js`; styles: `web/learn/app.css`. Sample Wes stats, chart, insights and learned preferences are deliberately fictional and labeled. Sample evidence IDs are local illustration labels, not real MLflow trace IDs. Do not publish or store fixtures as genuine learner records. Preserve separately stored user/teacher facts and existing browser learning data.

## What is implemented versus planned

The story coach records teacher outcomes in an anonymous in-memory session. `scripts/story_bridge.py` now triggers local reflection after confirmed identification observations; `scripts/learner_intelligence.py` stores normalized evidence, a processing checkpoint and conditional profile epochs under ignored `.local/learner-intelligence/`. `GET /api/learner-profile` serves the active anonymous session profile or an empty real profile before any evidence exists; the labeled fixture is available only through the temporary mock-preview button. The browser now renders this JSON, including rationale, source evidence and category revision history. The fixture profile is produced by the same rules from synthetic events. Anonymous sessions are not merged into persistent learner identities. The active anonymous session selection is now persisted locally; confirmed events also sync to Unity Catalog. The browser captures the last successful coach snapshot for this visit. The demo has browser-local results with synthetic starting context. The companion in `databricks/magneto-companion/agent/agent.py` is stateless, traces tool-plan invocations, and has no learner-memory tools. Finishing a book saves reading position; it does not trigger a profile update. Local rule-based reflection and conditional epochs now feed About me. The optional `scripts/learner_trace_search.py` performs read-only request-ID lookup; readback was verified against an existing synthetic MLflow trace, but no cloud trace-to-learner join feeds the page yet. The Unity Catalog evidence table and local sync are now live. Genie One MCP access and a real-table query were verified on October 11 without changing authentication or grants (reports/genie-mcp-verification.json). The earlier 403 cleared; its cause is unknown. Genie is not integrated into this feed, and cloud update jobs remain unconnected. Do not describe those as live.

## Future conversion from MLflow and learning records

Build a separate, read-only reflection/materialization step that joins decision trace evidence with actual teacher-confirmed learner outcomes. Model intentions, tool selections, transcripts and trace completion are not learner progress. The bounded action planner must continue to select one validated tool, never execute tools or grade responses.

A proposed **update epoch** is one versioned learner-intelligence publication, not a model training epoch and not every individual model/tool call. After an explicitly ended or paused learning session, save the session evidence first, then request an intelligence update. A partial session can have an epoch. Book completion is neither required nor proof of learning. Preserve the last successful profile if a run fails; indicate pending/failed/stale/updated and last updated time. A successful update with no new evidence says so, rather than fabricating progress.

Before implementing, agree a new reflection/profile contract through `databricks/contracts/README.md`. This document is product context, NOT an authoritative schema or deployed service. Preserve v1 demo and companion tool-plan wire formats. Update producer, consumer, examples and migration notes together and run `npm run check:contracts` for new contracts.

Planned provenance needs:
- Stable learner, session and event identities; occurrence timestamps; source and teacher confirmation; story, target, activity and task difficulty; response, actual support/hint and who requested it; available answer options and chosen option when collecting preferences.
- Trace/span IDs, invocation request IDs and links to decision evidence plus separately recorded subsequent outcomes. MLflow traces alone do not supply all these learner observations.
- Epoch ID/revision, learner ID, source session/event/trace IDs, evidence cutoff/window, previous successful epoch, generated time, model/prompt/derivation versions, status and review/correction history.
- Each insight/fact: stable ID, concise finding, type (observation, emerging pattern, hypothesis, student-stated preference, teacher-confirmed fact), supporting evidence, scope, uncertainty, next action and lifecycle (active, revised, dismissed, superseded). Avoid invented numeric confidence.

Generate at most a few meaningful findings per epoch. Permit 'no new pattern established.' Teacher corrections should regenerate a revised epoch and retain provenance. Retry the same session revision idempotently; never duplicate a journey entry or replay physical actions. Do not silently blend different learners, synthetic demos, unconfirmed transcripts or device failures into progress.

## Trend and insight semantics

Chart comparable targets and tasks across sessions. Show independent/supported/deferred counts and denominators; keep introduction separate from identification, letter recognition separate from word recognition. No attempts means a gap, not zero ability. Presentation/device failures are separate from learner responses. The current three-session chart has only independent and supported sample responses; a real pipeline must retain deferred outcomes and explain exclusions. Quick stats must share a stated window and derive from the same evidence as the chart.

For B/D differentiation, compare assistance and difficulty, then propose checking unfamiliar examples; don't assert mastery from a few matches. For audio prompts, collect explicit repeat requests and prompt conditions before inferring that shorter prompts help. Do not label a student as having an audio comprehension deficit. For spoken-answer preferences, observe choices only when alternatives were actually available and invite student confirmation. Preferences are revisable, not ability judgments. Confidence, motivation or persistence require explicit student reports or carefully described observations, never just slower answers or teacher-directed repetition.

## Validation expected of the next agent

Use fixture cases for insufficient evidence, changed task/support, missing responses, device failure, stale/replayed epochs, corrected observations, revoked facts, cloud failure and multiple learners. Verify traceability and that no new evidence never becomes a progress claim. Keep the current local workflow and saved browser designs. UI changes require `npm run check` and browser verification; companion/harness changes require their prescribed checks as well.


## Current runnable workflow and proof

- Run `python3 scripts/prove_learner_intelligence.py`: first session publishes epoch 1 at 40%, new comparable evidence publishes epoch 2 at 80%, identical background pass does not publish. Output: `reports/learner-intelligence-proof.json`.
- Run `npm run check:intelligence` (standard library tests; the schema test uses the contract environment), `npm run check:contracts`, and `npm run check:story`.
- A normalized evidence batch can be processed with `python3 scripts/learner_intelligence.py tests/fixtures/learner-evidence.json --store /tmp/magneto-demo-profile --output /tmp/magneto-demo-profile.json`. Keep fixture outputs separate from real records.
- `scripts/learner_trace_search.py --experiment EXPERIMENT_ID --request REQUEST_UUID --output /tmp/trace-reference.json` runs in the existing `.venv-agent` and queries exactly one decision request. It returns provenance, never an inferred learner outcome. Missing/ambiguous matches fail explicitly.
- Published changes compare findings, status, action, counts and optional comparable-session charts, plus quick stats. Provenance-only or identical passes advance the processing checkpoint without incrementing the epoch. Minimum three comparable observations per session is an MVP display threshold, not proof of mastery.
- The existing Story Mode controller is unchanged: the instructor records outcomes; the reflection never executes a physical tool or grades a transcript. Only identification observations currently have an automatic adapter. Other categories need explicitly collected, normalized observations; otherwise they remain unknown.

## Genie direction (access verified; feed integration pending)

Use Genie One MCP as the governed evidence-query layer once confirmed learner observations are stored in Unity Catalog and approved definitions exist for independent recognition, assistance, prompt clarity and response choice. Define denominators, exclusions, task/presentation comparability, source confirmation and learner scope before querying. MLflow traces provide decision provenance; they are not a substitute for learner outcome records.

Suggested flow: confirmed session evidence -> governed tables/definitions -> Genie question and complete SQL results/citations -> validated profile materialization -> conditional publication -> About me JSON. Retain this additive contract, history and deterministic numeric checks. Do not render Genie's natural-language output or generated SQL as arbitrary page HTML. Genie MCP Apps show inline views in supporting clients; they do not automatically embed into this static viewer. Fetch the complete result where needed because conversational responses can be truncated.

Official integration reference: https://docs.databricks.com/aws/en/agents/mcp-tools/genie-mcp . Genie One uses `system.ai.genie_one_mcp` through Unity Gateway. Workspace configuration, authentication, access policy and approved ontology remain prerequisites; this task did not create them.


## Live evidence feed and mock isolation (October 11)

Created and verified `workspace.magneto.learner_observations_v1` through the existing warehouse. Current readback contains zero confirmed learner outcomes; existing workspace tables contain research, traces and labeled synthetic evaluation sets, not a persistent learner record. Never claim those synthetic histories are real students. Existing historical learner data elsewhere needs an explicit source and learner identity.

`learner_bridge.py` runs a local background sync on confirmed Story Mode identification observations and while the live page is viewed (at most once per minute). It uploads only confirmed/non-synthetic events, reads the selected learner’s governed rows and materializes conditional epochs. No inference pass alone increments an epoch. Failed sync keeps local observations and the last profile for retry. The page polls for updated publications without replacing unchanged expanded content. This is a live local application service, not a separately scheduled cloud job; the local server must remain running.

Genie One initialization previously returned HTTP 403, but a subsequent retry succeeded with the same `magneto` profile and `all-apis offline_access` scopes. Service discovery, tool discovery, `genie_ask`, polling and structured SQL result retrieval succeeded. The real table returned total_rows=0 and confirmed_real_rows=0; see `reports/genie-mcp-verification.json`. Existing effective USE CATALOG, USE SCHEMA and EXECUTE grants were sufficient. No OAuth scopes, grants or policies were changed; the earlier failure cause is not established. Zero curated Genie spaces do not block Genie One. The live evidence route still uses SQL, not Genie; status is `available_not_integrated`. Do not say Genie generates this feed today.

The temporary “Render mock preview” button requests `?mode=mock`, uses module-local view state only, and never publishes an epoch or sends fixture events to Databricks. “Return to live data” and browser reload restore live mode. Empty live data never falls back to fixtures. Tests patch cloud sync in controller fixtures so tests never upload synthetic controller sessions as real observations.

## Opt-in MLflow-judged updater

Run `.venv-agent/bin/python scripts/learner_judged_updater.py --proof` for a live hosted-model proposal, native MLflow custom judge, native GenAI evaluation, accepted isolated profile publication, rejected overclaims and idempotent replay. Inspect `reports/learner-judge-proof.json` for actual results; synthetic cases do not demonstrate educational effectiveness.

For a normalized evidence file, run `.venv-agent/bin/python scripts/learner_judged_updater.py --evidence FILE --store DIRECTORY`. This sends the batch to the hosted model and records it in MLflow. Code keeps metrics/provenance authoritative; the model proposes prose only, with a fail-closed judge gate. One rejected generation may be repaired using gate feedback; all attempts are retained. No Genie or model-weight training is involved. Unchanged evidence batches skip the LLM and preserve the epoch. The default isolated store does not alter live About me selection or the automatic rules-based Story Mode updater.

The registered judge is an initial rubric, not teacher-calibrated or aligned. Its model currently shares the Qwen endpoint with the updater. Independent reviewers, broader cases and human feedback remain future work.

## Genie live profile integration (October 11)

`scripts/learner_genie.py` now calls Genie One MCP for all six summary finding/action/reasoning fields plus a concise overall summary. Even the real empty state is authored by Genie. SQL still reads/writes the confirmed evidence table; code owns category status, metrics, comparison groups and charts. The producer requests a read-only table check, preserves evidence IDs, rejects unsupported numeric claims/markup and validates the source link. This structural/numeric gate is not scientific validation or proof that every suggested action is optimal.

`scripts/learner_bridge.py` automatically materializes this result into the live `ProfileStore`. New Story Mode evidence is buffered in a separate pending-evidence store; it does not prematurely publish a rules-only profile. A completed, valid Genie analysis is required before publication. Empty real data uses the explicit `unassigned` profile; no mock fallback. Failed reads, Genie calls, validation or publication retain the prior profile and retry later. A digest cache and unchanged-checkpoint guard avoid new Genie requests for every background pass. Conditional epochs compare findings, actions, rationale, summary, metrics and stats; source-only changes do not publish.

Profile JSON gains optional `analysis` (conversation/response IDs, source URL, evidence digest, overall summary); epoch records retain their own optional Genie `source_url`. The UI escapes prose, allowlists source links and renders the six summaries consistently. Source records are saved under ignored `.local/learner-intelligence/genie-analysis/`; no credentials enter browser JSON. This is the existing localhost server workflow, not a deployed cloud scheduler. Earlier sections describing Genie as unintegrated are historical and superseded by this section.

## Saved Story session audit (October 11)

`reports/storybook-session-test/audit.json` records a browser walkthrough of Peter Rabbit with isolated fictional outcomes. Reading position survived reload; teacher-coach tool telemetry updated through confirmation. A live model introduction was correctly excluded from recognition evidence. A separately labeled controlled identification proposal produced a saved synthetic observation, exact isolated SQL readback, validated Genie publication, unchanged replay and an About me profile that survived reload. This is not a real learner run, an automatic test-server cloud trigger, or proof of the full architecture.

The audit fixed Genie JSON parsing when one fenced proposal follows transport narration; ambiguous multiple fences still fail, and profile validation remains authoritative. The test server never selects or syncs production learner data. Production still queues updates per confirmed identification, not at book close, and reopening the reader creates a new anonymous coach session. The shelf's separate mock activities do not feed this queue. Stable learner/session restoration, explicit finalization, other category adapters and MLflow outcome joins remain outstanding.

## Learner medallion storage (October 11)

The existing research-backed, MLflow-judged worker now publishes through additive
bronze/silver/gold storage. See [medallion stages](../databricks/docs/medallion-stages.md)
for table roles, upload scope, historical migration and replay commands. The original
learner event and read-only profile contracts are unchanged. New confirmed-real
normalized payloads land in bronze before validation; invalid records are retained
with quarantine reasons. Silver remains `learner_observations_v1`. Immutable gold
profile epochs require schema/metric/provenance checks and exact SQL readback before
the staged local profile becomes visible. Latest gold readback can restore the local
cache; failed publication keeps the prior profile and identical retry candidate.
The local worker remains necessary. Synthetic tests do not enter these tables,
empty evidence does not manufacture an epoch, and planner readback, MLflow outcome
joins, reviewed correction handling and a cloud scheduler remain unconnected.
