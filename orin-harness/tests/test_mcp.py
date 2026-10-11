"""Real MCP stdio integration with the simulated backend and fixture brain."""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

import yaml

from magneto_harness.brain.client import FixtureBrain
from magneto_harness.brain.orchestrator import connect, run_lesson, unpack
from magneto_harness.config import load_config
from magneto_harness.dry_run import demo_plan


def write_config(directory: Path, hear: list[str]) -> Path:
    config = load_config(None)
    config["backend"] = "sim"
    config["listening"] = {**config["listening"], "enabled": True, "engine": "scripted", "scripted": hear}
    config["brain"] = {**config["brain"], "mode": "fixture"}
    path = directory / "config.yaml"
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return path


class McpIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._dir = tempfile.TemporaryDirectory(prefix="magneto-harness-test-")
        cls.config_path = write_config(Path(cls._dir.name), ["c", "a", "b"])

    @classmethod
    def tearDownClass(cls):
        cls._dir.cleanup()

    def test_tool_roundtrip(self):
        async def scenario():
            async with connect(self.config_path) as client:
                created = unpack(await client.call_tool("create_session", {}))
                sid = created["session_id"]
                state = unpack(await client.call_tool("start_session", {"session_id": sid, "lesson_id": "word_cab"}))
                self.assertEqual(state["phase"], "idle")
                state = unpack(
                    await client.call_tool(
                        "present_activity",
                        {"session_id": sid, "revision": state["revision"], "target": "c", "activity": "identify", "prompt": "Say it."},
                    )
                )
                self.assertEqual(state["phase"], "awaiting_response")
                pending = unpack(await client.call_tool("poll_speech", {"session_id": sid}))
                self.assertEqual([t["transcript"] for t in pending["transcripts"]], ["c"])
                state = unpack(await client.call_tool("submit_response", {"session_id": sid, "transcript": "c"}))
                self.assertTrue(state["accepted"])
                self.assertEqual(state["recent_outcomes"][-1]["outcome"], "correct")

        asyncio.run(scenario())

    def test_stale_revision_is_rejected_over_mcp(self):
        async def scenario():
            async with connect(self.config_path) as client:
                sid = unpack(await client.call_tool("create_session", {}))["session_id"]
                await client.call_tool("start_session", {"session_id": sid, "lesson_id": "word_cab"})
                result = await client.call_tool(
                    "present_activity",
                    {"session_id": sid, "revision": 99, "target": "c", "activity": "identify"},
                )
                self.assertTrue(result.isError)

        asyncio.run(scenario())

    def test_full_lesson_with_fixture_brain(self):
        result = asyncio.run(run_lesson(self.config_path, FixtureBrain(decide=demo_plan), lesson_id="word_cab", max_turns=12))
        self.assertTrue(result["done"])
        self.assertEqual(result["state"]["phase"], "complete")
        self.assertEqual([o["outcome"] for o in result["state"]["recent_outcomes"]], ["correct", "correct", "correct"])


if __name__ == "__main__":
    unittest.main()
