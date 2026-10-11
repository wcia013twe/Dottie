# Interaction audio audit and look-ahead

## Tool-by-tool mapping

| Call | Accepted-state requirement | Audio wiring | Continuation behavior |
| --- | --- | --- | --- |
| `get_story_context` (MCP) | Existing session | None; read-only | None |
| `propose_activity` (MCP) | Approved current target, reading/proposed/continue phase, activity budget, current revision | No immediate audio. Look-ahead generates and caches prompt + hint from the validated proposal. | Educator reviews proposal. |
| `recommend_continue` (MCP) | Decision phase and current revision | No immediate audio; a prepared recommendation has one Continue story button. | One Continue story click resumes. |
| `prepare_braille` (MCP and educator adapter) | Approved activity, awaiting tactile material | None: visual preview does not establish physical readiness. | Single Start activity click confirms tactile readiness and runs the gated sequence. |
| `speak_prompt` (MCP and educator adapter) | Ready or waiting response | Educator adapter plays cached exercise `prompt`; browser speech fallback if unavailable. | Stay in exercise. |
| `give_hint` (MCP and educator adapter) | Waiting response | Educator adapter plays cached exercise `hint`, not a generic hint substitution. | Stay; controller marks subsequent outcome assisted. |
| `submit_response` (MCP) | Waiting response | None: unconfirmed transcript is not correctness. | Await educator confirmation. |
| `approve_activity` (educator only) | Proposed | None; deterministic Braille preparation follows. | Await tactile material. |
| `confirm_tactile` (educator only) | Awaiting tactile, prepared preview | The single Start activity sequence invokes Speak prompt automatically. | Prompt plays; wait for response. |
| `record_observation(independent)` (educator only) | Waiting/confirmation, no hint used | `success-independent`, only after accepted response. | Play feedback, then advance to the next story page automatically. |
| `record_observation(with_help)` (educator only) | Waiting/confirmation | `success-assisted`, only after acceptance. | Play feedback, then advance to the next story page automatically. |
| `record_observation(try_later)` (educator only) | Waiting/confirmation | `skip`, never `retry`. | Play feedback, then advance to the next story page automatically. |
| `resume_story` (educator only) | Current revision | `return-to-story` for continuation, or `skip` for an abandoned activity; close panel. | After feedback finishes, advance one page and autoplay that page narration. Interruption cancels auto-advance. |
| `set_context` (reader adapter) | Current revision | Stop interaction speech, clear exercise audio association. | Recompute current + next two spread window. |

Speech side effects are in the educator browser adapter. An arbitrary external MCP call updates
controller state but does not push speech to an already-open browser: a general event subscriber
is not implemented. No microphone scoring, physical device commands, mastery inference, or
lakehouse writes are introduced.

Unused pack clips: `retry` needs an explicit confirmed-incorrect-attempt event (not currently
supported); `offer-help` is redundant with the actual generated hint; `invite` is redundant with
the generated in-story prompt; `patient-wait` has no explicit encouragement control. None is
triggered by elapsed time or silence. Invalid/rejected actions play no feedback.

## Two-page look-ahead

The reader supplies the current spread plus the next two spreads (across chapter boundaries).
The first curated opportunity is selected, with the current page taking priority. At most one
pending exercise per session is retained. There is no arbitrary future story generation.

1. `POST /api/story/lookahead` accepts `{session_id, revision, target}` and returns
   `{preparation_id, target, status}` immediately. Only curated target passage IDs are accepted.
2. A background worker reads real session context over MCP, projects the curated opportunity
   without moving the live page, and asks for one validated propose/continue plan. Only four
   relevant teacher observations reach the model, as before.
3. A proposed exercise generates prompt and hint WAVs using the local ElevenLabs settings.
   Content/voice/settings hashes reuse existing audio. Continue decisions generate no speech.
   Missing credentials or synthesis failure leaves the text decision usable with browser speech.
4. `POST /api/story/lookahead-status` polls the session-bound handle. Browser polling is bounded
   to four minutes and stops on navigation outside the candidate window or disposal. An already
   running provider request may finish; it never plays audio by itself.
5. At the target page, **Start activity · tactile ready** (or **Continue story**) calls `POST /api/story/apply-lookahead` with
   `{session_id, revision, preparation_id}`. The server checks exact current revision, target,
   reading phase, observations, activity count, policy and interaction revision. Plain page
   movement may rebase the plan; any intervening activity/educator action invalidates it.
6. The validated plan executes once through the shared controller. Its `interaction_audio`
   maps prompt/hint to immutable local files. The Start button explicitly confirms tactile material is ready, then sequences approval, Braille preparation, tactile confirmation and prompt playback through their existing gates. Outcomes play feedback and resume automatically.

Reading never waits for this worker and there is no automatic interruption. Starting a prepared exercise needs one click; recording an outcome needs one click, with no separate resume step. If an educator asks
before preparation completes, the existing current-page preparation path remains available;
it may perform a fresh model call and use browser speech. Preparation can fail explicitly;
there is no invented fallback teaching decision.

The local additions do not change deployed Databricks v1 decision or v3 telemetry contracts.
Saved learner knowledge, scheduled repetition, MLflow linking and retrieval remain separate
integration work. The existing proposal reason is displayed directly in the educator panel.

## Validation

Unit coverage checks rebase on arrival, wrong target, stale revision, changed evidence,
intervening educator action, single-use handles, one in-flight job and late results. MCP tests
check future context projection without mutating the real page. Feedback mapping tests ensure
transcripts cannot trigger success and try-later cannot trigger incorrect feedback. Live browser
verification exercised cached prompt, hint and assisted-success playback on the gate opportunity.

## Authored checkpoints and stable page anchors

`web/learn/books/peter-rabbit-checkpoints.json` is the shared authored map read by the browser
and Python controller. Each checkpoint has a stable ID, page ID, allowed targets, required
materials, story summary and `after_narration` pause boundary. All checkpoints are optional:
the agent continues to choose propose versus continue, with no mandatory exercise added.

Page IDs bind to original EPUB illustration IDs, not displayed page numbers or wording.
The importer preserves source image IDs as escaped metadata; the bundled-book adapter attaches
stable page IDs after validating the edition. Missing/duplicate anchors fail explicitly so an
edited edition cannot silently move an exercise to the wrong page. Generic imported books do
not gain this checkpoint map. Narration matching and saved reading positions are unchanged.

Migration: existing checkpoint IDs `rabbit`, `gate`, `lettuce` and narration page IDs are retained.
No deployed Databricks interface changes. Story copy edits no longer alter checkpoint selection.
The pause boundary is authored guidance; educator initiation still controls starting an exercise.

## Personal Intelligence and review policy

The story reader retains at most 40 confirmed Peter Rabbit observations per existing browser
profile in `magneto-story-practice-v1:<profile UUID>`. On opening a book it sends this bounded
history to the local session endpoint; the server validates fields, IDs, targets, dates and
support consistency. It does not query the lakehouse or migrate old unconfirmed/undated history.
Accepted outcomes are saved before the next decision, including when a late response arrives
after page navigation. Browser storage failure is shown in the practice-history panel.

The deterministic policy groups target AND activity, deduplicates observations by ID, and shows
up to five recent observations per group. Try-later is excluded from difficulty evidence.
Introductions count as exposure, not recognition. After assisted practice or an introduction,
review is suggested one day later. Consecutive independent recognition/matching observations
use intervals of 1, 3, 7, then 14 days. These are initial heuristics, not validated optimal intervals
or mastery thresholds. Review dates and evidence are visible under Personal Intelligence in
the educator panel. Only four relevant candidates at most reach the model at each checkpoint.
Due reviews and recent assistance influence selection; continuing the story remains allowed.
Updated evidence invalidates speculative plans. Live decisions use local cached evidence.

With existing profile upload consent enabled, independent/assisted completed outcomes also enter
the v3 attempt outbox, using the observation ID and original observation timestamp. Independent
maps to correct/none; assisted maps to correct/hint when known, otherwise correct/unknown.
Try-later and unconfirmed transcripts do not upload as attempts. No retrospective upload of local
history is performed on opt-in. The immutable activity catalog now covers every supported
checkpoint/target/activity combination without changing existing references or payload schemas.
The cloud consumer needs the regenerated catalog deployed before new references are accepted;
failed acknowledgements keep attempts queued. Deployment and cloud-history readback are not
part of this local layer. No uploads are enabled automatically.

## Word emphasis

Enabled by default for each new story session. The educator can disable it under Word activities;
models cannot change that setting. `propose_word_emphasis` accepts only activity `emphasize` and an approved
multi-letter keyword at the current checkpoint. Prompt and hint use the same look-ahead audio
cache. It counts toward the existing activity budget and requires educator approval.

`prepare_word_sequence` runs after approval and returns ordered deterministic Braille cells,
1,500 ms letter hold, 300 ms gap, and the intended `SPELL <keyword>` command. This is a preview
payload, not a serial write, calibrated device timing or readiness acknowledgement. Repeated
letters remain separate frames. The educator Start action selects this preparation tool for
word-emphasis proposals and retains the existing tactile-material confirmation.

The panel shows the ordered letters and timing. No timed single-cell animation or physical
playback is implemented here. The existing SerialCell/firmware sequencer can be connected later;
no new firmware protocol is required for timed spelling. Learner-paced stepping remains separate.

Disabling word emphasis clears the proposal and invalidates cached plans through policy/revision checks.
Exposure telemetry uses immutable `emphasize-<word>@1` references and task `emphasize` rather
than identify/match. Review scheduling treats it as exposure, not recognition mastery. Deploy
the updated cloud catalog before uploading these new references. No end-user uploads are enabled
by the word-activity setting.

Release migration: the local session policy is now `word_emphasis_enabled` and the educator action
is `set_word_emphasis`. Restart the local server and reload the reader together. MCP proposal and
sequence tool signatures, activity references and telemetry meanings are unchanged.

## Live question stops

The chapter progress bar shows an upcoming question marker only for a ready `propose_activity` plan or
an active introduce/identify/match interaction. Draft/failed plans, continue recommendations,
word-exposure-only proposals and unselected authored checkpoints do not show question markers.
Markers refresh on preparation/status changes, outcomes and navigation; stale/out-of-window
plans disappear. The current one-plan/two-page look-ahead means at most one upcoming marker.
At the end of page narration, an already-prepared question opens the educator panel and stops
automatic page turning; the existing educator Start action remains required. A late plan still
updates the marker, without forcing an interruption in new narration.

Recorded teacher outcomes remain on the timeline as Solved, Solved with help, or Skipped.
The latest accepted question outcome per checkpoint is restored from the active profile’s
retained practice history (up to 40 observations); word exposure does not count as a question.
A planned revisit adds a gold outline while keeping the previous result visible.
