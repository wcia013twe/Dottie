# Orin harness + companion: what comes next

Status: built and checked locally. Not deployed, not run on hardware, not committed.

## Verified locally

- `npm run check:contracts` — 9 schemas, 11 examples, negative cases, no cloud calls.
- `npm run check:harness` — 31 passed, plus the simulated dry run reaching `phase: complete`.
- `npm run check:companion` — 7 dependency-free plan tests passed.
- `npm run check` — passes.

These exercise the simulated path and the contracts. They do not prove hardware
behaviour, model quality, or deployment correctness.

## Next steps

### 1. Commit the work
Nothing is committed. Review `git status`, then commit the new contracts,
`orin-harness/`, `databricks/magneto-companion/`, and the `package.json` /
`AGENTS.md` / `scripts/` edits together.

### 2. Provision the companion app (needs Databricks access)
- Create a Databricks App for the companion and a tracing experiment. Until then
  the generated `databricks/magneto-companion/services.toml` still points at the
  director's `agent_app` and experiment; the harness overrides `agent_app` at
  invoke time, but the app's own tracing would share the director's experiment.
- Set `agent_app` for the companion in `databricks/platform/services.toml` (or a
  companion-specific config) if a dedicated app is required.
- Deploy: `python3 scripts/prepare_agent.py` then the Agent Bricks CLI command in
  `databricks/magneto-companion/README.md`.
- Re-export `requirements.txt` from `uv.lock` after any dependency change.

### 3. Finish companion tests
`databricks/magneto-companion/tests/test_runtime.py` and `uv.lock` need the
companion's own environment:

```bash
cd databricks/magneto-companion && uv sync && uv run pytest
```

If `databricks_agentkit` / LangGraph are not yet resolved by `uv`, pin them in
`pyproject.toml` first.

### 4. Hardware bring-up on the Orin Nano
- Flash `cell-firmware/` and confirm the cell responds (`python -m cane_vision.serial_cell "abc"`).
- Set `backend: real`, correct `cell.port` / `camera.source`, `listening.engine: scribe`.
- Export `ELEVENLABS_API_KEY`.
- Verify a device acknowledgement before treating the cell as ready — passing
  checks and dry runs are not a physical-readiness signal.

### 5. Wire the real brain path
- Point `brain.mode: agent` at the deployed companion and confirm one full turn:
  snapshot → validated plan → physical action → transcript → deterministic grade.
- Confirm revision-staleness rejection actually blocks a replayed plan end to end.

### 6. Optional hardening
- Install `webrtcvad` if energy VAD proves too noisy (`listening.vad: webrtcvad`).
- Consider a dedicated tracing experiment per agent so director and companion
  traces stay separable.

## Known gaps / caveats

- The `check:contracts` fallback to `.venv-harness` assumes that venv exists; the
  director's own `.venv` is still the intended tool there.
- `test_runtime.py` has never been executed (missing runtime deps here).
- No real microphone, camera, servo, or Databricks call has been exercised.
