"""Terminal responses must end a real MCP turn before another brain call."""
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock

import yaml

from magneto_harness.brain.orchestrator import connect, _call, run_turn
from magneto_harness.config import load_config


class TerminalResponseTests(unittest.IsolatedAsyncioTestCase):
    async def test_final_scripted_response_does_not_call_brain(self):
        config = load_config()
        config["backend"] = "sim"
        config["lesson"]["catalog"]["terminal_test"] = {
            "activity": "identify", "targets": ["c"]}
        config["listening"].update(enabled=True, engine="scripted", scripted=["c"])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            path.write_text(yaml.safe_dump(config))
            async with connect(path) as client:
                created = await _call(client, "create_session", {})
                sid = created["session_id"]
                state = await _call(client, "start_session", {
                    "session_id": sid, "lesson_id": "terminal_test"})
                await _call(client, "present_activity", {
                    "session_id": sid, "revision": state["revision"],
                    "target": "c", "activity": "identify", "prompt": "Feel and identify."})
                brain = Mock()
                result = await run_turn(client, brain, sid)
                self.assertTrue(result["done"])
                self.assertEqual(result["state"]["phase"], "complete")
                self.assertIsNone(result["tool_called"])
                brain.decide.assert_not_called()
