"""Continuous listening: microphone -> voice-activity segments -> STT.

The default production engine is ElevenLabs Scribe (`scribe_v2`). Segments come
from a lightweight energy VAD so the Orin needs no extra native dependency; a
`webrtcvad` option is available when installed. Tests and dry runs use the
scripted engine, which yields preset transcripts without a microphone.

Transcripts are unconfirmed: they are evidence for the harness's deterministic
comparison, never a grade.
"""

from __future__ import annotations

import io
import os
import queue
import threading
import time
import wave
from typing import Any, Callable

STT_URL = "https://api.elevenlabs.io/v1/speech-to-text"


def _now_ms() -> int:
    return int(time.monotonic() * 1000)


class NullListener:
    """Listening disabled: no device, no transcripts."""

    def __init__(self) -> None:
        self._running = False

    @property
    def running(self) -> bool:
        return False

    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None

    def drain(self) -> list[dict[str, Any]]:
        return []


class ScriptedListener:
    """Emits preset transcripts on start (dry run and tests).

    Each transcript is released only after the previous one has been drained,
    so the harness is always in the matching phase when a response arrives.
    """

    def __init__(self, transcripts: list[str], delay_s: float = 0.0):
        self._transcripts = list(transcripts)
        self._delay_s = delay_s
        self._queue: queue.Queue[dict[str, Any]] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._consumed = threading.Event()

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._consumed.set()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        for text in self._transcripts:
            if not self._consumed.wait(timeout=60.0):
                return
            self._consumed.clear()
            if self._stop.wait(self._delay_s):
                return
            self._queue.put(
                {"transcript": text, "confidence": 1.0, "duration_s": 0.0, "received_at_ms": _now_ms()}
            )

    def stop(self) -> None:
        self._stop.set()
        self._consumed.set()
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None

    def drain(self) -> list[dict[str, Any]]:
        out = []
        while True:
            try:
                out.append(self._queue.get_nowait())
            except queue.Empty:
                break
        if out:
            self._consumed.set()
        return out


class ScribeSTT:
    """ElevenLabs speech-to-text client. `http_post` is injectable for tests."""

    def __init__(
        self,
        api_key: str,
        model_id: str = "scribe_v2",
        language: str = "eng",
        timeout_s: float = 8.0,
        http_post: Callable[..., Any] | None = None,
    ):
        if http_post is None:
            import requests

            http_post = requests.post
        self._post = http_post
        self.api_key = api_key
        self.model_id = model_id
        self.language = language
        self.timeout_s = timeout_s

    def transcribe(self, wav_bytes: bytes) -> dict[str, Any]:
        files = {"file": ("audio.wav", wav_bytes, "audio/wav")}
        data = {"model_id": self.model_id, "language_code": self.language}
        headers = {"xi-api-key": self.api_key}
        resp = self._post(STT_URL, files=files, data=data, headers=headers, timeout=self.timeout_s)
        resp.raise_for_status()
        payload = resp.json()
        return {
            "transcript": str(payload.get("text", "")).strip(),
            "confidence": float(payload.get("language_probability", 1.0)),
        }


class VadScribeListener:
    """Microphone capture with an energy VAD, transcribed by Scribe."""

    def __init__(self, listening_cfg: dict[str, Any], stt: ScribeSTT):
        self._cfg = listening_cfg
        self._stt = stt
        self._sample_rate = int(listening_cfg.get("sample_rate", 16000))
        self._frame_ms = int(listening_cfg.get("frame_ms", 30))
        self._threshold = float(listening_cfg.get("energy_threshold", 500))
        self._min_segment_s = float(listening_cfg.get("min_segment_s", 0.25))
        self._max_segment_s = float(listening_cfg.get("max_segment_s", 6.0))
        self._silence_ms = float(listening_cfg.get("silence_ms", 800))
        self._queue: queue.Queue[dict[str, Any]] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._capture, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    def drain(self) -> list[dict[str, Any]]:
        out = []
        while True:
            try:
                out.append(self._queue.get_nowait())
            except queue.Empty:
                return out

    def _capture(self) -> None:  # pragma: no cover - requires audio hardware
        import sounddevice as sd

        frames_per_buffer = int(self._sample_rate * self._frame_ms / 1000)
        buffer: list[bytes] = []
        speaking = False
        silence_acc = 0.0

        def finalize() -> None:
            nonlocal buffer, speaking, silence_acc
            if buffer:
                duration_s = len(buffer) * self._frame_ms / 1000.0
                if self._min_segment_s <= duration_s <= self._max_segment_s:
                    wav_bytes = _encode_wav(b"".join(buffer), self._sample_rate)
                    try:
                        result = self._stt.transcribe(wav_bytes)
                        result["duration_s"] = round(duration_s, 3)
                        result["received_at_ms"] = _now_ms()
                        self._queue.put(result)
                    except Exception as exc:
                        print(f"[listen] transcription failed: {exc}", flush=True)
            buffer, speaking, silence_acc = [], False, 0.0

        with sd.RawInputStream(
            samplerate=self._sample_rate, channels=1, dtype="int16", blocksize=frames_per_buffer
        ) as stream:
            while not self._stop.is_set():
                data, _ = stream.read(frames_per_buffer)
                rms = _rms(data)
                if rms >= self._threshold:
                    speaking = True
                    silence_acc = 0.0
                    buffer.append(bytes(data))
                elif speaking:
                    buffer.append(bytes(data))
                    silence_acc += self._frame_ms
                    if silence_acc >= self._silence_ms:
                        finalize()
                if buffer and len(buffer) * self._frame_ms / 1000.0 >= self._max_segment_s:
                    finalize()


def _rms(data: Any) -> float:
    import array

    samples = array.array("h")
    samples.frombytes(bytes(data))
    if not samples:
        return 0.0
    return (sum(s * s for s in samples) / len(samples)) ** 0.5


def _encode_wav(pcm: bytes, sample_rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm)
    return buf.getvalue()


def _scribe_from_env(listening_cfg: dict[str, Any]) -> ScribeSTT:
    stt_cfg = listening_cfg.get("stt", {})
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        raise RuntimeError("ELEVENLABS_API_KEY is required for the scribe listening engine")
    return ScribeSTT(
        api_key,
        model_id=stt_cfg.get("model_id", "scribe_v2"),
        language=stt_cfg.get("language", "eng"),
        timeout_s=stt_cfg.get("timeout_s", 8.0),
    )


def make_listening_device(config: dict[str, Any], backend: str):
    listening = config.get("listening", {})
    if not listening.get("enabled"):
        return NullListener()

    engine = listening.get("engine", "scripted")
    if backend != "real" or engine == "scripted":
        return ScriptedListener(
            listening.get("scripted", []), delay_s=float(listening.get("scripted_delay_s", 0.0))
        )

    return VadScribeListener(listening, _scribe_from_env(listening))
