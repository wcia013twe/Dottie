# Magneto Orin harness

The Orin Nano harness owns every physical effect in the accessible-interaction
loop. It exposes a bounded set of MCP tools over stdio and executes at most one
validated tool per turn on behalf of the Databricks Personal Intelligence brain
(`databricks/magneto-companion`). The brain only selects; the harness validates,
executes and records.

Package: `magneto_harness`. Runner: [`config.yaml`](config.yaml).

## What it does

1. A teacher selects a lesson (`start_session`).
2. The harness sends a `companion-snapshot` to the brain.
3. The brain returns one `companion-tool-plan` (`{tool, arguments, reason}`).
4. The harness checks the plan against the current revision and lesson targets,
   then runs it over MCP (show on the Braille cell, speak, listen, observe).
5. Continuous listening feeds a transcript to `submit_response`; the harness
   compares it deterministically to the expected target and advances.

The brain never executes a tool and never grades a response. A stale or
mismatched plan is rejected before any physical action, and a retry never
repeats a physical action.

## Run

```bash
# from the repository root, with .venv-harness (see requirements.txt)
python -m magneto_harness.dry_run --lesson word_cab     # offline: sim + scripted + fixture brain
python -m magneto_harness.run --lesson word_cab          # real devices + configured brain
python -m magneto_harness.mcp.server                     # MCP stdio server only
```

`dry_run` needs no hardware, microphone, network or credentials. `run` uses the
`backend` and `brain` from `config.yaml`; set `backend: real` on the Orin.

## Config (`config.yaml`)

- `backend`: `sim` (simulated devices) or `real` (cane-vision hardware).
- `session.max_activities`, `session.advance_on_correct`: session bounds/policy.
- `lesson.catalog`, `lesson.prompts`: the only valid targets and prompt text.
- `bounds`: prompt/phrase/observation/outcome caps.
- `cell`, `camera`, `detector`, `cane`, `speech`: hardware sections, passed
  through to `cane_vision` (`serial_cell.make_cell`, `detector.Detector`,
  `elevenlabs.make_speaker`).
- `listening`: `scripted` (tests/dry run) or `scribe` (ElevenLabs Scribe), with
  an energy VAD (`vad: energy|webrtcvad|none`).
- `brain.mode`: `direct` (`Services.complete`), `agent` (`Services.invoke_agent`
  against `brain.agent_app`), or `fixture` (tests only).
- `grading.aliases`: spoken-letter aliases (`see` → `c`).

### Credentials (environment, never in config)

- `ELEVENLABS_API_KEY` — speech and Scribe listening.
- Databricks auth for `brain.mode: direct|agent`, via
  `databricks/platform/services.toml`.

## Tools

Observation:
- `get_companion_state(session_id)`
- `observe_scene(session_id, max_items=10)`
- `read_cell(session_id)`

Actuation (brain-selectable):
- `announce(session_id, revision, text)`
- `show_cell(session_id, revision, text)`
- `present_activity(session_id, revision, target, activity, prompt="")`
- `begin_listening(session_id, revision)` / `end_listening(session_id, revision)`
- `advance_target(session_id, revision)`
- `recommend_continue(session_id, revision)`

Harness automatic path (not brain-selectable):
- `submit_response(session_id, transcript, source="stt")`
- `poll_speech(session_id)`

Teacher only:
- `create_session()`, `start_session(session_id, lesson_id=None)`,
  `select_lesson(session_id, lesson_id)`, `stop_session(session_id)`,
  `record_outcome(session_id, outcome, ...)`

## Bring-up on the Orin Nano

1. Create the environment: `python3 -m venv .venv-harness && .venv-harness/bin/pip install -r orin-harness/requirements.txt` (and `cane-vision/requirements.txt`).
2. Flash `cell-firmware/` and confirm the cell: `python -m cane_vision.serial_cell "abc"`.
3. Set `backend: real`, the right `cell.port`/`camera.source`, and `listening.engine: scribe`; export `ELEVENLABS_API_KEY`.
4. Deploy the companion agent (see `databricks/magneto-companion/README.md`) and set `brain.mode: agent`.
5. Run `python -m magneto_harness.run --lesson word_cab` and confirm a device
   acknowledgement before treating the cell as ready.

## Checks

```bash
npm run check:harness     # unit + MCP integration tests, then the dry run
```

Passing checks exercise the simulated path and the contract; they do not prove
mechanical reliability or physical readiness.
