# Agent guide

- Keep this a simple local static viewer; avoid frameworks or cloud services unless requested.
- Run `python3 scripts/serve.py`; the site root is `web/`.
- Edit CAD sources in `cad/` and builders in `scripts/`. Rebuild with `npm run build:cad`; do not hand-edit generated meshes or 3MFs.
- Use millimeters. Keep printed parts separate from bought hardware, and identify provisional measurements and concept-only geometry.
- Servo/reset browser geometry comes from the same solid CAD export as its 3MFs. Preserve this shared source.
- Run `npm run check`, then check affected views and animations in the browser. Never imply that mesh checks prove mechanical reliability.
- Preserve browser-local saved designs, the localhost workflow, reference documents and third-party licenses.

## Shared component contracts

- Read [databricks/contracts/README.md](databricks/contracts/README.md) before changing a cross-component interface. It is the authoritative v1 baseline; schemas/examples live beside it.
- Preserve the deployed demo wire format. Research/retrieval contracts are specified but not yet connected. Do not treat planned interfaces as implemented services.
- Run `npm run check:contracts` from the repository root for contract changes. Update producer, consumer, examples and migration notes together for a new version.

## Orin harness and companion

- The Orin harness lives in `orin-harness/` (package `magneto_harness`). It exposes bounded MCP tools over stdio and owns all physical effects; the brain only selects one validated tool per turn. Run `npm run check:harness`.
- `magneto_harness/devices/` is the only place that touches hardware. Keep a simulated backend so `python -m magneto_harness.dry_run` stays hardware- and network-free.
- The Personal Intelligence brain is `databricks/magneto-companion/` (generate its `magneto_platform/` copy with `scripts/prepare_agent.py`; never hand-edit it). It must never execute a tool or grade a response. Run `npm run check:companion`; full tests need the agent's own `.venv` via `uv run pytest`.
- The harness and brain share one tool-plan prompt and validator; keep `databricks/magneto-companion/agent/plan.py` in step with `orin-harness/magneto_harness/brain/protocol.py`.
- Never assert physical readiness without a device acknowledgement, and never claim a transcript or a design is confirmed by a check.
