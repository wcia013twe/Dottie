# Learner research reflection

The localhost server runs the coordinator asynchronously after recording a learner outcome. The current server must be restarted to load this implementation. Databricks provides evidence storage, hybrid research retrieval, hosted inference, and MLflow judgments/audits. No new service, graph database, index, schedule, or job is provisioned.

## Flow and ownership

1. Preserve the authoritative Story snapshot locally before normalization.
2. Validate and deduplicate normalized outcome events. Order them into session episodes with original IDs, timestamps, task, target, condition, confirmation, and outcome. Keep separate attempts and failed-device/deferred outcomes. State explicitly that prompts, hint contents, retry links and session completion are not available in this format.
3. Search the existing teaching library using bounded category queries. Each result is rechecked against current Delta eligibility. Industry data remains independently searchable but does not justify teaching efficacy.
4. Propose up to three category prose changes, or no change. Every change needs observation IDs, passage IDs, exact source excerpts, direct/inferred basis, and applicability limits. Counts and comparison groups remain deterministic.
5. Validate references and verbatim excerpts in code. The native MLflow `learner_research_support_v2` judge assesses the actual support for the specific action. At most one repair is permitted. Neither a search result nor judge acceptance approves a research source for the live director.
6. Upload the complete audit before publishing a conditional local profile revision. Stale evidence, failed audit upload, invalid references, or rejection retains the previous publication. Replay of unchanged evidence skips model/search calls.
7. Genie optionally summarizes the derived profile. It cannot replace the judged categories. No automatic teaching action or next-session strategy consumption is implemented here.

## Find an audit in Databricks

Open experiment `/Shared/magneto-research` (ID `1306573313615572`). Reflection run names start with `research-reflection-2`. In the run's Artifacts, open `reflection/audit.json`:

- `inputs.episodes`: ordered observations and coverage limits.
- `inputs.research.queries`: queries and linked research search run IDs.
- `inputs.research.passages`: source titles/URIs, immutable versions, page locators, original passage text and metadata.
- `attempts`: original and repaired proposals and judgments, when applicable.
- `proposal.support`: observation → passage → exact excerpt → action rationale.
- `assessment`: support verdict, not a measured learner benefit.

`publication.json` records the published epoch. The profile's optional `reflection.id` is the MLflow run ID. Local immutable audits are also retained under `<profile-store>/reflections/`. Source-only changes do not trigger learner reprocessing automatically. An operational failure before retrieval completes may leave a failed parent/search run without a full reflection artifact.

## Implementation and limits

- `scripts/learner_episodes.py`: deterministic episode construction.
- `scripts/learner_reflection.py`: coordinator and native MLflow proposer/judge tracing.
- `scripts/learner_bridge.py`: asynchronous live trigger and pending evidence.
- `scripts/learner_intelligence.py`: numeric derivation and atomic conditional publication.
- `scripts/learner_genie.py`: summary-only adapter used by this path; legacy standalone interfaces remain for existing isolated tests.
- `databricks/contracts/learner-profile-v1/README.md`: additive migration and provenance contract.

The profile store remains local and single-writer. A session episode is an observation snapshot, not proof of session completion. This is an outcome-based MVP, not a reconstruction of full interaction telemetry. Model judgments can still be wrong; exact quotes improve traceability but do not establish applicability or educational effectiveness.

Verification: offline tests cover replay, stale evidence, rejected citations/excerpts, failed retrieval/audit upload, device-failure preservation, and Genie category isolation. Synthetic Databricks checks exercise actual search, model and audit connections; see the implementation receipt for final results. They do not validate learning outcomes. Restart the existing localhost server when ready to activate the new bridge code; running sessions are not interrupted by installation.

Excerpt matching normalizes PDF whitespace, typographic quotes, Unicode compatibility characters and in-word typesetting hyphens. It does not normalize words or paraphrases. Original source text and generated excerpts remain in the audit.

## Verified implementation receipt

Final synthetic run: `b07c18114e7b45fa99025f10bd0c6647` in `/Shared/magneto-research`. Two episodes retrieved three cited passages. After rejection and one repair, the final proposal contained zero changes: the retrieved passages did not justify the proposed specific adaptation. The baseline observations were published in an isolated temporary store. Remote audit readback matched the local audit, profile schema validation passed, and replay invoked no external service and published no new epoch. Genie was intentionally skipped for synthetic evidence. The running localhost server was not restarted, so activation remains pending a restart.

Local checks: 45 learner tests, `npm run check:contracts`, `npm run check`, and `git diff --check` passed. The synthetic receipt is `learner-research-reflection-proof.json` beside this file in the Databricks operations folder (repository copy under `reports/`). These checks establish the software flow, not educational effectiveness.
