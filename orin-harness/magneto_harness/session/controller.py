"""Session state machine for the Orin harness.

The controller is the only authority on session state. Every tool call passes
through `call`, which checks the actor's permissions, the revision (so a stale
plan can never replay a physical action), and the configured bounds before any
device action runs. It returns a companion-snapshot-shaped state dict.

`submit_response` is the automatic path: the harness records what was heard,
grades it deterministically, and updates the target. The brain never grades.
"""

from __future__ import annotations

import threading
import time
import uuid
from typing import Any

from ..devices.executor import EXECUTING_TOOLS, NullExecutor
from ..errors import ContractError, LessonNotFoundError
from ..grading import grade, grade_config
from ..lesson import ACTIVITIES, render_prompt, resolve_lesson

PHASES = ("idle", "awaiting_response", "reviewing", "complete", "stopped")

MODEL_TOOLS = {
    "get_companion_state",
    "observe_scene",
    "read_cell",
    "announce",
    "show_cell",
    "present_activity",
    "begin_listening",
    "end_listening",
    "advance_target",
    "recommend_continue",
}
HARNESS_TOOLS = MODEL_TOOLS | {"submit_response", "poll_speech"}
TEACHER_TOOLS = HARNESS_TOOLS | {"start_session", "select_lesson", "stop_session", "record_outcome"}

READ_ONLY = {"get_companion_state", "read_cell", "poll_speech", "observe_scene"}
MUTATING = {
    "announce",
    "show_cell",
    "present_activity",
    "begin_listening",
    "end_listening",
    "advance_target",
    "recommend_continue",
    "start_session",
    "select_lesson",
    "stop_session",
    "submit_response",
    "record_outcome",
}


def _now_ms() -> int:
    return int(time.monotonic() * 1000)


class SessionController:
    def __init__(self, config: dict[str, Any], executor: Any | None = None):
        self.config = config
        self.bounds = config["bounds"]
        self.session_cfg = config["session"]
        self.executor = executor or NullExecutor()
        self._sessions: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

    # -- allowed actors -----------------------------------------------------

    @staticmethod
    def _allowed(actor: str, name: str) -> bool:
        if actor == "brain":
            return name in MODEL_TOOLS
        if actor == "harness":
            return name in HARNESS_TOOLS
        if actor == "teacher":
            return name in TEACHER_TOOLS
        return False

    # -- sessions -----------------------------------------------------------

    def ensure_session(self, session_id: str) -> dict[str, Any]:
        if session_id not in self._sessions:
            self._sessions[session_id] = {
                "session_id": session_id,
                "revision": 0,
                "phase": "idle",
                "lesson_id": None,
                "targets": [],
                "index": 0,
                "target": None,
                "activity": None,
                "prompt": None,
                "activities_started": 0,
                "last_response": None,
                "last_presentation": None,
                "outcomes": [],
                "observations": [],
                "trace": [],
                "created_at_ms": _now_ms(),
            }
        return self._sessions[session_id]

    def new_session_id(self) -> str:
        return str(uuid.uuid4())

    def sessions(self) -> list[str]:
        return list(self._sessions)

    # -- tool dispatch ------------------------------------------------------

    def call(self, session_id: str, name: str, args: dict[str, Any] | None = None, actor: str = "brain") -> dict[str, Any]:
        args = dict(args or {})
        with self._lock:
            state = self.ensure_session(session_id)
            if not self._allowed(actor, name):
                raise ContractError(f"actor {actor!r} may not call {name!r}")

            if name in MUTATING:
                if actor == "brain" and "revision" not in args:
                    raise ContractError(f"{name} requires a revision")
                if "revision" in args and int(args["revision"]) != state["revision"]:
                    raise ContractError(
                        f"stale revision {args['revision']} for {name}; current is {state['revision']}"
                    )

            handler = getattr(self, f"_do_{name}", None)
            if handler is None:
                raise ContractError(f"unknown tool {name!r}")
            result = handler(state, args)

            if name in MUTATING and name != "submit_response":
                state["revision"] += 1
            state["trace"].append({"t": _now_ms(), "tool": name, "actor": actor})
            if len(state["trace"]) > self.session_cfg.get("max_trace", 40):
                state["trace"] = state["trace"][-self.session_cfg["max_trace"] :]

            view = self.state_view(state)
            if isinstance(result, dict) and "__accepted__" in result:
                view["accepted"] = bool(result["__accepted__"])
            elif isinstance(result, dict):
                view.update(result)
            return view

    # -- handlers -----------------------------------------------------------

    def _do_get_companion_state(self, state: dict[str, Any], args: dict[str, Any]) -> None:
        return None

    def _do_poll_speech(self, state: dict[str, Any], args: dict[str, Any]) -> dict[str, Any]:
        return self._exec(state, "poll_speech", {})

    def _do_observe_scene(self, state: dict[str, Any], args: dict[str, Any]) -> None:
        max_items = min(int(args.get("max_items", self.bounds["max_observe_items"])), self.bounds["max_observe_items"])
        execution = self._exec(state, "observe_scene", {"max_items": max_items})
        for det in execution.get("detections", [])[: self.bounds["max_observations"]]:
            state["observations"].append({"t": _now_ms(), **det})
        state["observations"] = state["observations"][-self.bounds["max_observations"] :]

    def _do_read_cell(self, state: dict[str, Any], args: dict[str, Any]) -> dict[str, Any]:
        return self._exec(state, "read_cell", {})

    def _do_announce(self, state: dict[str, Any], args: dict[str, Any]) -> None:
        text = self._bounded(args, "text", self.bounds["max_phrase_chars"], required=True)
        self._exec(state, "announce", {"text": text})

    def _do_show_cell(self, state: dict[str, Any], args: dict[str, Any]) -> None:
        text = self._bounded(args, "text", self.bounds["max_cell_text_chars"], required=True)
        self._exec(state, "show_cell", {"text": text})

    def _do_present_activity(self, state: dict[str, Any], args: dict[str, Any]) -> None:
        if state["phase"] == "complete":
            raise ContractError("the lesson is complete; no further activities")
        if state["phase"] == "stopped":
            raise ContractError("session is stopped")
        if not state["targets"]:
            raise ContractError("no lesson selected; call start_session first")
        if state["activities_started"] >= self.session_cfg["max_activities"]:
            raise ContractError("activity budget exhausted")
        target = str(args.get("target", "")).lower()
        if target not in state["targets"]:
            raise ContractError(f"target {target!r} is not in this lesson")
        activity = args.get("activity", state["activity"])
        if activity not in ACTIVITIES:
            raise ContractError(f"invalid activity {activity!r}")
        default_prompt = render_prompt(self.config, activity, target)
        prompt = self._bounded(args, "prompt", self.bounds["max_prompt_chars"], default=default_prompt)
        execution = self._exec(state, "present_activity", {"target": target, "activity": activity, "prompt": prompt})
        state["target"] = target
        state["activity"] = activity
        state["prompt"] = prompt
        state["last_presentation"] = {**execution, "t": _now_ms()}
        state["last_response"] = None
        state["activities_started"] += 1
        state["phase"] = "awaiting_response"

    def _do_begin_listening(self, state: dict[str, Any], args: dict[str, Any]) -> None:
        self._exec(state, "begin_listening", {})

    def _do_end_listening(self, state: dict[str, Any], args: dict[str, Any]) -> None:
        self._exec(state, "end_listening", {})

    def _do_advance_target(self, state: dict[str, Any], args: dict[str, Any]) -> None:
        if state["targets"] and state["index"] < len(state["targets"]) - 1:
            state["index"] += 1
        state["target"] = state["targets"][state["index"]] if state["targets"] else None
        state["last_response"] = None
        state["phase"] = "idle"
        self._exec(state, "advance_target", {})

    def _do_recommend_continue(self, state: dict[str, Any], args: dict[str, Any]) -> None:
        self._exec(state, "end_listening", {})
        state["phase"] = "complete"

    def _do_stop_session(self, state: dict[str, Any], args: dict[str, Any]) -> None:
        self._exec(state, "stop_session", {})
        state["phase"] = "stopped"

    def _do_start_session(self, state: dict[str, Any], args: dict[str, Any]) -> None:
        self._select_lesson(state, args.get("lesson_id"))

    def _do_select_lesson(self, state: dict[str, Any], args: dict[str, Any]) -> None:
        self._select_lesson(state, args.get("lesson_id"))

    def _do_submit_response(self, state: dict[str, Any], args: dict[str, Any]) -> dict[str, Any]:
        if state["phase"] != "awaiting_response":
            return {"__accepted__": False}
        transcript = str(args.get("transcript", ""))[:300]
        source = args.get("source", "stt")
        if source not in ("stt", "typed", "teacher"):
            raise ContractError(f"invalid source {source!r}")
        match, outcome = grade(transcript, state["target"], grade_config(self.config))
        response = {
            "transcript": transcript,
            "expected": state["target"],
            "match": match,
            "outcome": outcome,
            "source": source,
            "received_at_ms": _now_ms(),
        }
        state["last_response"] = response
        self._record(state, response, state.get("last_presentation") or {})
        self._after_response(state)
        state["revision"] += 1
        return {"__accepted__": True}

    def _do_record_outcome(self, state: dict[str, Any], args: dict[str, Any]) -> None:
        outcome = args.get("outcome")
        if outcome not in ("correct", "incorrect", "help", "unrecognized"):
            raise ContractError(f"invalid outcome {outcome!r}")
        match = args.get("match", {"correct": "exact"}.get(outcome, "none"))
        response = {
            "transcript": str(args.get("transcript", ""))[:300],
            "expected": str(args.get("target", state["target"] or "")),
            "match": match,
            "outcome": outcome,
            "source": args.get("source", "teacher"),
            "received_at_ms": _now_ms(),
        }
        state["last_response"] = response
        self._record(state, response, state.get("last_presentation") or {})
        self._after_response(state)

    # -- helpers ------------------------------------------------------------

    def _select_lesson(self, state: dict[str, Any], lesson_id: str | None) -> None:
        try:
            lesson = resolve_lesson(self.config, lesson_id)
        except LessonNotFoundError:
            raise
        self._exec(state, "stop_session", {})
        state.update(
            lesson_id=lesson["lesson_id"],
            targets=lesson["targets"],
            index=0,
            target=lesson["targets"][0],
            activity=lesson["activity"],
            prompt=render_prompt(self.config, lesson["activity"], lesson["targets"][0]),
            activities_started=0,
            last_response=None,
            last_presentation=None,
            outcomes=[],
            observations=[],
            phase="idle",
        )

    def _after_response(self, state: dict[str, Any]) -> None:
        response = state["last_response"]
        if response["outcome"] == "correct" and self.session_cfg.get("advance_on_correct", True):
            if state["index"] < len(state["targets"]) - 1:
                state["index"] += 1
                state["target"] = state["targets"][state["index"]]
                state["phase"] = "reviewing"
            else:
                self._exec(state, "end_listening", {})
                state["phase"] = "complete"
        elif state["phase"] == "awaiting_response":
            state["phase"] = "reviewing"

    def _record(self, state: dict[str, Any], response: dict[str, Any], execution: dict[str, Any]) -> None:
        entry = {**response, "execution": execution}
        state["outcomes"].append(entry)
        if len(state["outcomes"]) > self.bounds["max_outcomes"]:
            state["outcomes"] = state["outcomes"][-self.bounds["max_outcomes"] :]

    def _exec(self, state: dict[str, Any], name: str, args: dict[str, Any]) -> dict[str, Any]:
        if name not in EXECUTING_TOOLS:
            return {}
        return self.executor.run(name, args, state) or {}

    def _bounded(self, args: dict[str, Any], key: str, limit: int, required: bool = False, default: str | None = None) -> str:
        if key not in args or args[key] in (None, ""):
            if required:
                raise ContractError(f"{key} is required")
            return default or ""
        text = str(args[key])
        if len(text) > limit:
            raise ContractError(f"{key} exceeds {limit} characters")
        return text

    # -- views --------------------------------------------------------------

    def state_view(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "session_id": state["session_id"],
            "revision": state["revision"],
            "phase": state["phase"],
            "lesson_id": state["lesson_id"],
            "targets": list(state["targets"]),
            "index": state["index"],
            "target": state["target"],
            "activity": state["activity"],
            "prompt": state["prompt"],
            "activities_started": state["activities_started"],
            "policy": {
                "max_activities": self.session_cfg["max_activities"],
                "advance_on_correct": bool(self.session_cfg.get("advance_on_correct", True)),
            },
            "device": self.executor.device_state(),
            "last_response": state["last_response"],
            "recent_outcomes": [
                {k: v for k, v in o.items() if k != "execution"} for o in state["outcomes"]
            ],
            "recent_observations": state["observations"],
        }

    def snapshot(self, session_id: str, request_id: str) -> dict[str, Any]:
        with self._lock:
            state = self.ensure_session(session_id)
            return {"request_id": request_id, **self.state_view(state)}
