# Voice navigation v1

Additive, local `POST /api/voice-intent` contract. It does not change the deployed director, learner, Story Mode or hardware payloads. The version is in this directory; no version field is sent.

The browser producer (`web/learn/voice-understanding.js`) sends only an unknown navigation transcript (1–500 characters), current allowlisted route and whether a book is open. Activity answers bypass this classifier. The same-origin local broker (`scripts/voice_bridge.py`) calls `scripts/voice_navigation.py` in the existing Story Python environment; that adapter uses the existing authenticated Databricks foundation model, a strict action schema and independent validation.

Success is a model-source envelope containing one allowlisted intent. Reader controls require `story_reader: true` in both producer and consumer validation. No arbitrary URL, DOM selector, grading action or hardware action is accepted. Multiple or unclear requests return fixed clarification speech. Errors use an HTTP error status and `{error: string}`; unavailability is not an unknown successful interpretation.

The browser validates the returned intent again and checks microphone generation, cancellation and the original page/session context before executing the existing UI action. A route change or Stop listening cancels pending work. The model only interprets; it never executes.

Migration: existing local shortcuts continue without a model request. Restart the localhost server and reload the browser to enable the additive endpoint. Existing story answers and saved local designs remain under their existing contracts.

Validation: `npm run check:voice` and `npm run check:contracts`. Examples are synthetic navigation requests, not learner evidence.
