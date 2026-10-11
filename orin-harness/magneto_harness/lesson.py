"""Lesson catalog and prompt rendering.

Only the configured lesson catalog defines valid targets. The brain never
invents targets: every target it presents must come from here, and the prompt
text it supplies is bounded by `bounds.max_prompt_chars` before use.
"""

from __future__ import annotations

from typing import Any

from .errors import LessonNotFoundError

ACTIVITIES = ("introduce", "identify", "match", "spell")


def resolve_lesson(config: dict[str, Any], lesson_id: str | None = None) -> dict[str, Any]:
    catalog = config["lesson"].get("catalog") or {}
    chosen = lesson_id or config["lesson"].get("default")
    if not chosen:
        raise LessonNotFoundError("no lesson id given and no default configured")
    spec = catalog.get(chosen)
    if not spec:
        raise LessonNotFoundError(f"unknown lesson {chosen!r}")
    targets = list(spec["targets"])
    return {
        "lesson_id": chosen,
        "activity": spec.get("activity", "identify"),
        "targets": targets,
    }


def render_prompt(config: dict[str, Any], activity: str, target: str) -> str:
    templates = config["lesson"].get("prompts") or {}
    template = templates.get(activity) or templates.get("identify") or "{target}"
    return template.format(target=target)
