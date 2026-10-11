"""Canonical catalog of MCP tools and their argument requirements.

The MCP server definitions are the source of truth for the wire schemas; this
catalog is used by plan validation and by documentation, and keeps the
harness's notion of "required argument" in one place.
"""

from __future__ import annotations

SPEC: dict[str, dict] = {
    # observation
    "get_companion_state": {"required": ["session_id"], "mutating": False, "actor": "brain"},
    "observe_scene": {"required": ["session_id"], "mutating": False, "actor": "brain"},
    "read_cell": {"required": ["session_id"], "mutating": False, "actor": "brain"},
    # actuation
    "announce": {"required": ["session_id", "revision", "text"], "mutating": True, "actor": "brain"},
    "show_cell": {"required": ["session_id", "revision", "text"], "mutating": True, "actor": "brain"},
    "present_activity": {
        "required": ["session_id", "revision", "target", "activity"],
        "mutating": True,
        "actor": "brain",
    },
    "begin_listening": {"required": ["session_id", "revision"], "mutating": True, "actor": "brain"},
    "end_listening": {"required": ["session_id", "revision"], "mutating": True, "actor": "brain"},
    "advance_target": {"required": ["session_id", "revision"], "mutating": True, "actor": "brain"},
    "recommend_continue": {"required": ["session_id", "revision"], "mutating": True, "actor": "brain"},
    # harness automatic path
    "submit_response": {"required": ["session_id"], "mutating": True, "actor": "harness"},
    "poll_speech": {"required": ["session_id"], "mutating": False, "actor": "harness"},
    # teacher only
    "create_session": {"required": [], "mutating": True, "actor": "teacher"},
    "start_session": {"required": ["session_id"], "mutating": True, "actor": "teacher"},
    "select_lesson": {"required": ["session_id", "lesson_id"], "mutating": True, "actor": "teacher"},
    "stop_session": {"required": ["session_id"], "mutating": True, "actor": "teacher"},
    "record_outcome": {"required": ["session_id", "outcome"], "mutating": True, "actor": "teacher"},
}
