# Synthetic Story persona v1 (additive, test-only)

Producer: `story_mode/personas.py` loads the repository-owned example `story_mode/personas/alex-morgan.json`.
The isolated `scripts/serve_story_test.py` selects it when creating sessions. HTTP session bodies cannot select a persona or supply arbitrary prose.
Consumer: Story MCP `get_story_context`, `story_mode/orchestrator.py` and `web/learn/story-coach.js` receive the optional `synthetic_persona` snapshot field. `/api/story/test-persona` on the isolated server serves the seed for inspection.

All fields in `persona.schema.json` are required; `synthetic` must be true. These are fictional starting assumptions, not evidence events. Never insert the seed into the real observation table, infer a diagnosis or fabricate outcomes. Confirmed test identification outcomes use the existing evidence schema with `synthetic:true` and an isolated local store; cloud publication remains the explicit synthetic SQL-to-Genie CLI.

Only persona-bearing test sessions allow `awaiting_confirmation` → `proposed` / `continue_proposed` through the existing bounded tools. This permits a model follow-up to an unconfirmed test reply without grading it. New activity proposals clear the old reply and preview and still require teacher approval and tactile confirmation. Revision, target and activity-budget guards remain in force. Test snapshots retain the old reply in per-session JSONL logs. Ordinary anonymous sessions retain their original transitions.

Migration: opt-in test-server extension, version 1.0. Legacy demo/director/companion payloads and profile/evidence schemas are unchanged. No cloud persona table, stable learner identity, automatic learner simulation or cross-session coach restoration is added.
