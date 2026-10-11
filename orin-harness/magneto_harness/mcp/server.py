"""Magneto harness MCP server.

Exposes the bounded observation, actuation and teacher tools over stdio. The
server owns the devices via a `DeviceExecutor`; the brain only ever asks for
one validated tool per turn. Start it with `python -m magneto_harness.mcp.server`.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from ..brain.tools import SPEC
from ..config import load_config
from ..devices import (
    make_cell_device,
    make_listening_device,
    make_speech_device,
    make_vision_device,
)
from ..devices.executor import DeviceExecutor
from ..paths import DEFAULT_CONFIG
from ..session.controller import SessionController


def build_server(config: dict[str, Any] | None = None, config_path: str | Path | None = None):
    config = config or load_config(config_path)
    base_dir = Path(config_path).parent if config_path else DEFAULT_CONFIG.parent

    executor = DeviceExecutor(
        make_cell_device(config),
        make_vision_device(config, base_dir),
        make_speech_device(config),
        make_listening_device(config),
    )
    controller = SessionController(config, executor)
    server = FastMCP("magneto-harness")

    def call(name: str, session_id: str, args: dict[str, Any]) -> dict[str, Any]:
        actor = SPEC[name]["actor"] if name in SPEC else "teacher"
        return controller.call(session_id, name, args, actor=actor)

    @server.tool()
    def create_session() -> dict[str, Any]:
        """Teacher: create a new session id to use with the other tools."""
        return {"session_id": controller.new_session_id()}

    @server.tool()
    def get_companion_state(session_id: str) -> dict[str, Any]:
        """Observation: the current phase, target, recent outcomes and device state."""
        return call("get_companion_state", session_id, {"session_id": session_id})

    @server.tool()
    def observe_scene(session_id: str, max_items: int = 10) -> dict[str, Any]:
        """Observation: latest camera detections at the cane tip (bounded)."""
        return call("observe_scene", session_id, {"session_id": session_id, "max_items": max_items})

    @server.tool()
    def read_cell(session_id: str) -> dict[str, Any]:
        """Observation: the pattern currently shown on the Braille cell."""
        return call("read_cell", session_id, {"session_id": session_id})

    @server.tool()
    def announce(session_id: str, revision: int, text: str) -> dict[str, Any]:
        """Actuation: speak a short phrase aloud."""
        return call("announce", session_id, {"session_id": session_id, "revision": revision, "text": text})

    @server.tool()
    def show_cell(session_id: str, revision: int, text: str) -> dict[str, Any]:
        """Actuation: show a letter or short text on the Braille cell."""
        return call("show_cell", session_id, {"session_id": session_id, "revision": revision, "text": text})

    @server.tool()
    def present_activity(
        session_id: str, revision: int, target: str, activity: str, prompt: str = ""
    ) -> dict[str, Any]:
        """Actuation: show the target and speak the prompt; begins listening for a response."""
        return call(
            "present_activity",
            session_id,
            {
                "session_id": session_id,
                "revision": revision,
                "target": target,
                "activity": activity,
                "prompt": prompt,
            },
        )

    @server.tool()
    def begin_listening(session_id: str, revision: int) -> dict[str, Any]:
        """Actuation: start continuous listening for a spoken response."""
        return call("begin_listening", session_id, {"session_id": session_id, "revision": revision})

    @server.tool()
    def end_listening(session_id: str, revision: int) -> dict[str, Any]:
        """Actuation: stop listening."""
        return call("end_listening", session_id, {"session_id": session_id, "revision": revision})

    @server.tool()
    def advance_target(session_id: str, revision: int) -> dict[str, Any]:
        """Actuation: move to the next target in the lesson and clear the cell."""
        return call("advance_target", session_id, {"session_id": session_id, "revision": revision})

    @server.tool()
    def recommend_continue(session_id: str, revision: int) -> dict[str, Any]:
        """Actuation: end the lesson for now and stop listening."""
        return call("recommend_continue", session_id, {"session_id": session_id, "revision": revision})

    @server.tool()
    def submit_response(session_id: str, transcript: str, source: str = "stt") -> dict[str, Any]:
        """Harness: record a heard/typed response and let the harness compare it to the target."""
        return call(
            "submit_response",
            session_id,
            {"session_id": session_id, "transcript": transcript, "source": source},
        )

    @server.tool()
    def poll_speech(session_id: str) -> dict[str, Any]:
        """Harness: drain transcripts the listener has produced since the last poll."""
        return call("poll_speech", session_id, {"session_id": session_id})

    @server.tool()
    def start_session(session_id: str, lesson_id: str | None = None) -> dict[str, Any]:
        """Teacher: begin a lesson (defaults to the configured lesson)."""
        return call("start_session", session_id, {"session_id": session_id, "lesson_id": lesson_id})

    @server.tool()
    def select_lesson(session_id: str, lesson_id: str) -> dict[str, Any]:
        """Teacher: choose a lesson from the configured catalog."""
        return call("select_lesson", session_id, {"session_id": session_id, "lesson_id": lesson_id})

    @server.tool()
    def stop_session(session_id: str) -> dict[str, Any]:
        """Teacher: stop the session and clear the cell."""
        return call("stop_session", session_id, {"session_id": session_id})

    @server.tool()
    def record_outcome(
        session_id: str,
        outcome: str,
        transcript: str = "",
        target: str | None = None,
        match: str | None = None,
        source: str = "teacher",
    ) -> dict[str, Any]:
        """Teacher: override the recorded outcome for the current target."""
        return call(
            "record_outcome",
            session_id,
            {
                "session_id": session_id,
                "outcome": outcome,
                "transcript": transcript,
                "target": target,
                "match": match,
                "source": source,
            },
        )

    return server, controller


def main() -> None:  # pragma: no cover - process entry
    import logging

    logging.getLogger("mcp").setLevel(logging.WARNING)
    config_path = os.environ.get("MAGNETO_HARNESS_CONFIG")
    server, _ = build_server(config_path=config_path)
    server.run(transport="stdio")


if __name__ == "__main__":  # pragma: no cover
    main()
