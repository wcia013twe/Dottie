# Magneto runtime contract (companion)

This API-only LangGraph workload uses Agent Bricks custom-server deployment on Databricks Apps. Its single
graph node calls `agent.plan.decide` once. Inputs are complete, validated companion snapshots plus the
current MCP tool schemas, not conversation messages.

The manifest intentionally binds no managed memory or graph-session store. The deployment has no durable
invocation replay; a plan never reads prior output. A replay can repeat inference but must never repeat a
physical action — the harness, not this agent, performs and deduplicates physical effects.

Input envelope: `{id, session_id, input}` where `input = {snapshot, available_mcp_tools}`. `id` equals
`snapshot.request_id`; `session_id` must match the snapshot too. Response envelope:
`{id, status: "completed", output}` where `output = {plan, model, elapsed_ms}` and `plan` is
`{tool, arguments, reason}`. Clients must never execute a stale plan: the harness checks
`arguments.revision` against its current revision before acting.

The agent only selects among the discovered tools that are in its allowed set. It never executes, never
grades, and never names learner mastery. The system prompt and validation must stay in step with
`orin-harness/magneto_harness/brain/protocol.py`.

Call `configure_tracing` at startup and wrap graph execution in `start_trace` with inputs, output, model
and elapsed time. Use the app service identity for model access and the local OAuth profile only for local
development. Secrets must not be committed or returned to the caller.

Keep `app.yaml` and the pinned lockfile installable. Do not add tools, conversational memory, or a chat UI
without extending the approved companion contract and tests.
