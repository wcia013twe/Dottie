"""Listening devices: scripted sequencing and the Scribe STT client."""

from __future__ import annotations

import time
import unittest

from magneto_harness.devices.listening import ScribeSTT, ScriptedListener


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class ScriptedListenerTests(unittest.TestCase):
    def test_releases_one_at_a_time(self):
        listener = ScriptedListener(["c", "a", "b"])
        listener.start()
        try:
            first = listener.drain()
            self.assertEqual([t["transcript"] for t in first], ["c"])
            deadline = time.time() + 2
            second = []
            while time.time() < deadline and not second:
                second = listener.drain()
                time.sleep(0.01)
            self.assertEqual([t["transcript"] for t in second], ["a"])
        finally:
            listener.stop()

    def test_stop_before_start_is_safe(self):
        ScriptedListener([]).stop()


class ScribeSTTTests(unittest.TestCase):
    def test_transcribe_posts_multipart_and_parses_text(self):
        captured = {}

        def fake_post(url, files=None, data=None, headers=None, timeout=None):
            captured.update(url=url, files=files, data=data, headers=headers, timeout=timeout)
            return _Resp({"text": "  c  ", "language_probability": 0.9})

        stt = ScribeSTT("secret-key", http_post=fake_post)
        result = stt.transcribe(b"RIFF....")
        self.assertEqual(result["transcript"], "c")
        self.assertAlmostEqual(result["confidence"], 0.9)
        self.assertEqual(captured["data"]["model_id"], "scribe_v2")
        self.assertEqual(captured["headers"]["xi-api-key"], "secret-key")
        self.assertIn("file", captured["files"])


if __name__ == "__main__":
    unittest.main()
