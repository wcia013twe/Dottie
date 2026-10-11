# Agent guide

- Keep this a simple local static viewer; avoid frameworks or cloud services unless requested.
- Run `python3 scripts/serve.py`; the site root is `web/`.
- Edit CAD sources in `cad/` and builders in `scripts/`. Rebuild with `npm run build:cad`; do not hand-edit generated meshes or 3MFs.
- Use millimeters. Keep printed parts separate from bought hardware, and identify provisional measurements and concept-only geometry.
- Servo/reset browser geometry comes from the same solid CAD export as its 3MFs. Preserve this shared source.
- Run `npm run check`, then check affected views and animations in the browser. Never imply that mesh checks prove mechanical reliability.
- Preserve browser-local saved designs, the localhost workflow, reference documents and third-party licenses.

## System connection map

- Treat the live **System** map at `/system.html` as the source of truth for tracking component and Databricks service connections. Read [web/system.js](web/system.js) for its connection inventory and implementation references; [web/system.html](web/system.html) and [web/system.css](web/system.css) present it.
- Whenever wiring, service configuration, deployment status, or an integration boundary changes, update the map in the same task. Reconcile each connection against its producer, consumer, configuration and available verification evidence; do not leave completed integrations labeled planned or mark planned connections as implemented.
- Keep connected code paths green, optional/configuration-dependent paths amber, and unconnected paths dashed gray. Green means implemented wiring, not proof of current access, successful end-to-end execution or physical readiness. Keep metadata access results separate from integration evidence.
- Keep the read-only **Check Databricks access** probe in `scripts/system_probe.py` and its localhost bridge in `scripts/system_status.py` aligned with the mapped resources. Preserve the existing contract authority below; the map tracks connections and does not redefine payload schemas.
- After changing the map, run `npm run check` and verify the affected connections, labels and animation in the browser.

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

## About me learner intelligence

- Before changing learner insights, trends, facts, or post-session updates, read `docs/about-me-intelligence-handoff.md`. It records the accepted five criteria and the planned MLflow evidence conversion and update-epoch behavior.
- About me now has a Genie MCP prose-to-profile workflow with deterministic metrics and conditional epochs. Its demo evidence is fictional; Real confirmed Story Mode events now sync to a Unity Catalog table through SQL. MLflow trace-to-learner joins and a separately scheduled cloud update job remain unconnected. Genie MCP now writes the six live summaries from real evidence, including empty evidence; SQL still owns evidence reads/writes and code validates counts. Mock data is only an explicit, isolated preview. Preserve those distinctions and existing local facts.

## Model improvement planning

- Before implementing Hugging Face weight tuning, automated prompt optimization, or a custom model serving endpoint, read [the MVP workflow](databricks/docs/learner-adaptation-and-huggingface-tuning-mvp.md). Keep learner-profile update epochs distinct from model training epochs and preserve the harness validator.
