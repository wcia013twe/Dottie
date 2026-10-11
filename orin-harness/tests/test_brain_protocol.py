"""Brain protocol: response_format construction and plan validation."""

from __future__ import annotations

import unittest

from magneto_harness.brain.protocol import response_format, validate_plan
from magneto_harness.errors import ContractError

SNAPSHOT = {
    "request_id": "0f0a2b4c-6d8e-4a1b-9c2d-3e4f5a6b7c8d",
    "session_id": "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d",
    "revision": 3,
    "phase": "reviewing",
    "targets": ["c", "a", "b"],
    "target": "c",
    "activity": "identify",
}

SCHEMAS = [
    {
        "name": "present_activity",
        "description": "present",
        "inputSchema": {"type": "object", "properties": {"session_id": {"type": "string"}}},
    },
    {
        "name": "record_outcome",
        "description": "teacher",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


class ProtocolTests(unittest.TestCase):
    def test_response_format_only_includes_allowed_tools(self):
        fmt = response_format(SCHEMAS)
        options = fmt["json_schema"]["schema"]["oneOf"]
        names = [opt["properties"]["tool"]["const"] for opt in options]
        self.assertEqual(names, ["present_activity"])

    def test_valid_plan(self):
        plan = {
            "tool": "present_activity",
            "arguments": {
                "session_id": SNAPSHOT["session_id"],
                "revision": 3,
                "target": "c",
                "activity": "identify",
                "prompt": "Feel it and say it.",
            },
            "reason": "Present the current target.",
        }
        self.assertEqual(validate_plan(plan, SNAPSHOT), plan)

    def test_rejects_unknown_tool(self):
        with self.assertRaises(ContractError):
            validate_plan({"tool": "record_outcome", "arguments": {}, "reason": "x"}, SNAPSHOT)

    def test_rejects_stale_revision(self):
        plan = {
            "tool": "present_activity",
            "arguments": {"session_id": SNAPSHOT["session_id"], "revision": 1, "target": "c", "activity": "identify"},
            "reason": "stale",
        }
        with self.assertRaises(ContractError):
            validate_plan(plan, SNAPSHOT)

    def test_rejects_target_outside_lesson(self):
        plan = {
            "tool": "present_activity",
            "arguments": {"session_id": SNAPSHOT["session_id"], "revision": 3, "target": "z", "activity": "identify"},
            "reason": "bad target",
        }
        with self.assertRaises(ContractError):
            validate_plan(plan, SNAPSHOT)

    def test_rejects_wrong_keys(self):
        with self.assertRaises(ContractError):
            validate_plan({"tool": "present_activity", "arguments": {}}, SNAPSHOT)


if __name__ == "__main__":
    unittest.main()
