"""Offline dry run: simulated devices, scripted hearing, fixture brain.

    python -m magneto_harness.dry_run --lesson word_cab

Exercises the full harness path (MCP server, controller, graders) without any
camera, Arduino, microphone, network or Databricks credentials. The fixture
brain demonstrates the intended loop: present a target, hear the response,
advance, and finish.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any

import yaml

from .brain.client import FixtureBrain
from .brain.orchestrator import run_lesson
from .config import load_config


def demo_plan(snapshot: dict[str, Any]) -> dict[str, Any]:
    """A minimal stand-in for the brain: present the current target, else finish."""
    session_id = snapshot["session_id"]
    revision = snapshot["revision"]
    if snapshot["phase"] in ("idle", "reviewing"):
        target = snapshot.get("target") or snapshot["targets"][0]
        return {
            "tool": "present_activity",
            "arguments": {
                "session_id": session_id,
                "revision": revision,
                "target": target,
                "activity": snapshot.get("activity") or "identify",
                "prompt": "Feel the letter on the cell, then say it out loud.",
            },
            "reason": "Present the current target for identification.",
        }
    return {
        "tool": "recommend_continue",
        "arguments": {"session_id": session_id, "revision": revision},
        "reason": "The lesson has no further activities.",
    }


def _write_temp_config(args: argparse.Namespace) -> Path:
    config = load_config(args.config)
    config["backend"] = "sim"
    listening = dict(config.get("listening", {}))
    listening.update({"enabled": True, "engine": "scripted", "scripted": list(args.hear)})
    config["listening"] = listening
    config["brain"] = {**config.get("brain", {}), "mode": "fixture"}
    directory = Path(tempfile.mkdtemp(prefix="magneto-harness-"))
    path = directory / "config.yaml"
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return path


async def _main(args: argparse.Namespace) -> dict[str, Any]:
    config_path = _write_temp_config(args)
    brain = FixtureBrain(decide=demo_plan)
    return await run_lesson(config_path, brain, lesson_id=args.lesson, max_turns=args.max_turns)


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline dry run of the Magneto harness")
    parser.add_argument("--config", help="base config path (default: orin-harness/config.yaml)")
    parser.add_argument("--lesson", default="word_cab")
    parser.add_argument("--hear", nargs="*", default=["c", "a", "b"], help="scripted spoken responses")
    parser.add_argument("--max-turns", type=int, default=16)
    args = parser.parse_args()
    try:
        print(json.dumps(asyncio.run(_main(args)), indent=2, sort_keys=True))
    except Exception as exc:  # noqa: BLE001 - top-level CLI boundary
        print(json.dumps({"error": "dry run failed", "error_type": type(exc).__name__}))
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
