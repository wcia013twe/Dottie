"""Speech device: speak a bounded phrase through the configured voice.

Thin wrapper over `cane_vision.elevenlabs.make_speaker`, which uses ElevenLabs
when `ELEVENLABS_API_KEY` is set and falls back to a local engine otherwise.
"""

from __future__ import annotations

from typing import Any


class SimulatedSpeechDevice:
    def __init__(self) -> None:
        self.said: list[str] = []

    def say(self, text: str) -> dict[str, Any]:
        self.said.append(text)
        return {"spoken": True, "engine": "simulated"}

    def stop(self) -> None:
        return None


class RealSpeechDevice:
    def __init__(self, speaker: Any):
        self._speaker = speaker

    def say(self, text: str) -> dict[str, Any]:
        self._speaker.say(text)
        return {"spoken": True, "engine": getattr(self._speaker, "engine", "unknown")}

    def stop(self) -> None:
        self._speaker.stop()


def make_speech_device(config: dict[str, Any], backend: str):
    if backend != "real":
        return SimulatedSpeechDevice()
    from cane_vision.elevenlabs import make_speaker

    return RealSpeechDevice(make_speaker(config.get("speech", {})))
