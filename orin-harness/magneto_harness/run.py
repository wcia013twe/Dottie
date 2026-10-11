"""Run the Orin harness against the configured brain.

    python -m magneto_harness.run --lesson word_cab

Loads the harness config, picks the brain from `brain.mode`, then drives one
lesson over the MCP stdio server. Physical effects only happen when the real
devices are configured; otherwise this is a safe dry run.
"""

from __future__ import annotations

import argparse
import asyncio
import json

from .brain.client import make_brain
from .brain.orchestrator import run_lesson
from .config import load_config
from .paths import DEFAULT_CONFIG


async def _main(args: argparse.Namespace) -> dict:
    config = load_config(args.config)
    brain = make_brain(config)
    return await run_lesson(args.config or DEFAULT_CONFIG, brain, lesson_id=args.lesson, max_turns=args.max_turns)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one Magneto harness lesson")
    parser.add_argument("--config", help="harness config path (default: orin-harness/config.yaml)")
    parser.add_argument("--lesson", help="lesson id (default: configured lesson)")
    parser.add_argument("--max-turns", type=int, default=16)
    args = parser.parse_args()
    try:
        print(json.dumps(asyncio.run(_main(args)), indent=2, sort_keys=True))
    except Exception as exc:  # noqa: BLE001 - top-level CLI boundary
        print(json.dumps({"error": "harness run failed", "error_type": type(exc).__name__}))
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
