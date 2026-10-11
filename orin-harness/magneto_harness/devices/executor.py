"""Binds the four devices and performs one harness action.

The executor is the only place that touches hardware. It returns raw execution
flags; the controller turns those into a `companion-outcome`. A `NullExecutor`
is used by unit tests that only exercise controller logic.
"""

from __future__ import annotations

from typing import Any

from cane_vision.braille import LETTERS

from ..errors import ContractError

EXECUTING_TOOLS = {
    "announce",
    "show_cell",
    "present_activity",
    "begin_listening",
    "end_listening",
    "advance_target",
    "observe_scene",
    "read_cell",
    "poll_speech",
    "stop_session",
}


class NullExecutor:
    def run(self, name: str, args: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        return {}

    def device_state(self) -> dict[str, Any]:
        return {
            "cell_connected": False,
            "cell_ready": True,
            "listening": False,
            "camera_available": False,
        }

    def close(self) -> None:
        return None


class DeviceExecutor:
    def __init__(self, cell, vision, speech, listening):
        self.cell = cell
        self.vision = vision
        self.speech = speech
        self.listening = listening
        self._camera_available = False

    def device_state(self) -> dict[str, Any]:
        cell_state = self.cell.state()
        return {
            "cell_connected": bool(cell_state.get("connected")),
            "cell_ready": bool(cell_state.get("ready", True)),
            "listening": bool(self.listening.running),
            "camera_available": self._camera_available,
        }

    def _show_target(self, target: str) -> dict[str, Any]:
        if len(target) == 1 and target.lower() in LETTERS:
            return self.cell.hold(LETTERS[target.lower()], target.lower())
        return self.cell.show_text(target)

    def run(self, name: str, args: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        if name == "announce":
            spoken = self.speech.say(args["text"])
            return {"spoken": spoken["spoken"], "engine": spoken.get("engine")}

        if name == "show_cell":
            result = self._show_target(args["text"])
            return {"shown": result["shown"], "cell_ack": result["cell_ack"]}

        if name == "present_activity":
            shown = self._show_target(args["target"])
            spoken = self.speech.say(args["prompt"])
            self.listening.start()
            return {
                "shown": shown["shown"],
                "cell_ack": shown["cell_ack"],
                "spoken": spoken["spoken"],
                "engine": spoken.get("engine"),
                "listening": self.listening.running,
            }

        if name == "begin_listening":
            self.listening.start()
            return {"listening": self.listening.running}

        if name == "end_listening":
            self.listening.stop()
            return {"listening": False}

        if name == "advance_target":
            result = self.cell.clear()
            return {"shown": result["shown"], "cell_ack": result["cell_ack"]}

        if name == "observe_scene":
            result = self.vision.observe(args["max_items"])
            self._camera_available = bool(result.get("camera_available"))
            return result

        if name == "read_cell":
            return self.cell.state()

        if name == "poll_speech":
            return {"transcripts": self.listening.drain()}

        if name == "stop_session":
            self.listening.stop()
            self.speech.stop()
            result = self.cell.clear()
            return {"shown": result["shown"], "cell_ack": result["cell_ack"], "listening": False}

        raise ContractError(f"no executor action for tool {name!r}")

    def close(self) -> None:
        for device in (self.listening, self.vision, self.speech, self.cell):
            close = getattr(device, "close", None)
            if close:
                close()
