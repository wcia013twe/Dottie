# Magneto runtime contract

This API-only LangGraph workload uses Agent Bricks custom-server deployment on Databricks Apps. Its single graph node calls
`agent.decision.decide` once. Inputs are complete, validated demo snapshots, not conversation messages.
The manifest intentionally binds no managed memory or graph-session store. The managed Runtime Store creation was rejected by this workspace tier (scale-to-zero required).
The custom foreground API has no durable invocation replay; application decisions never read prior output.

The top-level invocation UUID equals snapshot.request_id; session_id must match the snapshot too.
The invoke adapter returns a validated result. Transport uses the same id/session_id/input envelope
and id/status/output response, but does not support background runs or streaming. Clients must never
execute stale results. Retries use fresh IDs and never repeat a physical action.

Call configure_tracing at startup and wrap graph execution in start_trace, with inputs, output,
model and elapsed time. Use the app service identity for model access and the local OAuth profile
only for local development. Secrets must not be committed or returned to the browser.

Keep app.yaml and the pinned lockfile installable. Do not add tools, conversational memory, or a
chat UI without extending the approved application contract and tests.

Approved research context is now an optional server-side dependency of the single decision node.
When MAGNETO_RESEARCH_ENABLED=1, agent/research.py implements the existing v1 retrieval boundary,
rechecks current Delta eligibility and supplies a separate approved-evidence message to the model.
Canonical snapshot and decision transport schemas are unchanged; model-selected tools are not added.
The active decision span records evidence supplied and its citations. Lookup failures are explicit;
empty successful results carry matches: []. This code is locally tested, not activated in app.yaml
or verified in a deployed invocation. A model assessment cannot approve source findings/guidance.
