# Magneto: one companion plan

The Orin harness sends a complete companion snapshot plus the current MCP tool schemas to a native
Databricks App. A single-node LangGraph makes one model call and validates exactly one bounded tool plan.
The agent never executes a tool and never grades a response; the harness performs the physical action and
records the deterministic outcome.

## Shared wiring

`../platform/services.toml` and `../platform/magneto_platform/` are the source of truth for workspace
resources and authenticated transport. The harness uses `Services.complete` (direct mode) or
`Services.invoke_agent` (agent mode, overriding `agent_app` to `agent-bricks-magneto-companion`). Before
deployment, `scripts/prepare_agent.py` copies the shared package and config into this standalone
deployment directory. Do not edit the generated `magneto_platform/` copy or `services.toml` here.

Until a dedicated app and tracing experiment are provisioned for the companion, this deployment shares the
existing workspace resources. Provisioning is an explicit platform operation and is not part of this
repository's automated checks; no cloud calls are made by the checks.

## Local checks

The companion agent is validated without deployment or credentials:

```bash
# from databricks/magneto-companion, with its own .venv (uv sync)
uv run pytest
```

The harness side is validated from the repository root:

```bash
npm run check:harness
```

## Deploy

```bash
python3 scripts/prepare_agent.py
PATH="$PWD/.venv-agent/bin:$PATH" .venv-agent/bin/agentbricks --profile magneto deploy magneto-companion --source databricks/magneto-companion
```

The Agent Bricks CLI excludes `uv.lock` from its upload, so Apps installs the exported
`requirements.txt` and starts `python -m runtime.main`. Re-export requirements after dependency changes.

## Contract and safeguards

`POST /api/invocations` accepts `{id, session_id, input}` and returns `{id, status: "completed", output}`.
`output.plan` is `{tool, arguments, reason}`. The plan's `tool` must be one the harness exposed, and
`arguments.session_id`/`arguments.revision` must match the snapshot, or the harness rejects it before any
physical action. The reason is a one-sentence evidence summary, not hidden reasoning.
