"""Controller state machine: transitions, bounds, actors, and staleness."""

from __future__ import annotations

import unittest

from magneto_harness.config import load_config
from magneto_harness.devices.executor import NullExecutor
from magneto_harness.errors import ContractError
from magneto_harness.session.controller import SessionController


def make_controller(**session_overrides):
    config = load_config(None)
    config["session"].update(session_overrides)
    return SessionController(config, NullExecutor())


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.c = make_controller()
        self.sid = self.c.new_session_id()

    def start(self):
        return self.c.call(self.sid, "start_session", {"session_id": self.sid}, actor="teacher")

    def present(self, target="c", **extra):
        state = self.c.call(self.sid, "get_companion_state", {"session_id": self.sid})
        args = {"session_id": self.sid, "revision": state["revision"], "target": target, "activity": "identify"}
        args.update(extra)
        return self.c.call(self.sid, "present_activity", args, actor="brain")

    def test_start_then_present_then_correct_advances(self):
        self.start()
        state = self.present("c")
        self.assertEqual(state["phase"], "awaiting_response")
        self.assertEqual(state["target"], "c")
        self.assertEqual(state["activities_started"], 1)
        state = self.c.call(self.sid, "submit_response", {"transcript": "c"}, actor="harness")
        self.assertTrue(state["accepted"])
        self.assertEqual(state["phase"], "reviewing")
        self.assertEqual(state["index"], 1)
        self.assertEqual(state["target"], "a")
        self.assertEqual(state["recent_outcomes"][-1]["outcome"], "correct")

    def test_last_correct_completes(self):
        self.start()
        for transcript in ("c", "a", "b"):
            state = self.c.call(self.sid, "get_companion_state", {"session_id": self.sid})
            self.present(state["target"])
            state = self.c.call(self.sid, "submit_response", {"transcript": transcript}, actor="harness")
            self.assertTrue(state["accepted"])
        self.assertEqual(state["phase"], "complete")
        self.assertEqual(state["activities_started"], 3)

    def test_incorrect_keeps_target_and_marks_reviewing(self):
        self.start()
        self.present("c")
        state = self.c.call(self.sid, "submit_response", {"transcript": "z"}, actor="harness")
        self.assertEqual(state["recent_outcomes"][-1]["outcome"], "incorrect")
        self.assertEqual(state["phase"], "reviewing")
        self.assertEqual(state["target"], "c")

    def test_submit_outside_awaiting_is_ignored(self):
        self.start()
        state = self.c.call(self.sid, "submit_response", {"transcript": "c"}, actor="harness")
        self.assertFalse(state["accepted"])
        self.assertEqual(state["recent_outcomes"], [])

    def test_stale_revision_rejected(self):
        self.start()
        state = self.present("c")
        stale = state["revision"] - 1
        with self.assertRaises(ContractError):
            self.c.call(
                self.sid,
                "present_activity",
                {"session_id": self.sid, "revision": stale, "target": "a", "activity": "identify"},
                actor="brain",
            )

    def test_target_must_be_in_lesson(self):
        self.start()
        with self.assertRaises(ContractError):
            self.present("z")

    def test_prompt_length_enforced(self):
        self.start()
        with self.assertRaises(ContractError):
            self.present("c", prompt="x" * 500)

    def test_model_cannot_use_teacher_tools(self):
        with self.assertRaises(ContractError):
            self.c.call(self.sid, "start_session", {"session_id": self.sid}, actor="brain")

    def test_model_cannot_submit_or_grade(self):
        self.start()
        self.present("c")
        with self.assertRaises(ContractError):
            self.c.call(self.sid, "submit_response", {"transcript": "c"}, actor="brain")

    def test_activity_budget_enforced(self):
        c = make_controller(max_activities=1)
        sid = c.new_session_id()
        state = c.call(sid, "start_session", {"session_id": sid}, actor="teacher")
        c.call(sid, "present_activity", {"session_id": sid, "revision": state["revision"], "target": "c", "activity": "identify"}, actor="brain")
        state = c.call(sid, "get_companion_state", {"session_id": sid})
        with self.assertRaises(ContractError):
            c.call(sid, "present_activity", {"session_id": sid, "revision": state["revision"], "target": "c", "activity": "identify"}, actor="brain")

    def test_teacher_can_override_outcome(self):
        self.start()
        self.present("c")
        state = self.c.call(
            self.sid,
            "record_outcome",
            {"session_id": self.sid, "outcome": "help", "target": "c"},
            actor="teacher",
        )
        self.assertEqual(state["recent_outcomes"][-1]["outcome"], "help")

    def test_snapshot_has_companion_shape(self):
        self.start()
        snap = self.c.snapshot(self.sid, "0f0a2b4c-6d8e-4a1b-9c2d-3e4f5a6b7c8d")
        self.assertEqual(snap["request_id"], "0f0a2b4c-6d8e-4a1b-9c2d-3e4f5a6b7c8d")
        self.assertEqual(snap["session_id"], self.sid)
        for key in ("phase", "targets", "policy", "device", "recent_outcomes"):
            self.assertIn(key, snap)


if __name__ == "__main__":
    unittest.main()
