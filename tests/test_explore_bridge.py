"""Camera ingress limits and origin policy must hold before running YOLO."""
import base64
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from email.message import Message
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import explore_bridge as bridge

JPEG = base64.b64encode(b'\xff\xd8test').decode()

class Handler:
    path = '/api/explore-observe'
    def __init__(self, payload=None, origin='http://localhost:8102'):
        body = json.dumps(payload if payload is not None else {'jpeg': JPEG}).encode()
        self.headers = Message()
        for key, value in {'Host':'localhost:8102', 'Origin':origin, 'Content-Type':'application/json', 'Content-Length':str(len(body))}.items():
            self.headers[key] = value
        self.rfile = io.BytesIO(body)
        self.connection = SimpleNamespace(settimeout=lambda timeout: None)
        self.server = SimpleNamespace(server_port=8102)
    def _json(self, status, value):
        self.status, self.value = status, value

class CameraBridgeTests(unittest.TestCase):
    def test_invalid_frames_are_rejected(self):
        for payload in [{}, {'jpeg': '???'}, {'jpeg': base64.b64encode(b'not jpeg').decode()}, {'jpeg': JPEG, 'extra': True}, {'jpeg': 10}]:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                bridge.validate(payload)

    @patch.object(bridge, 'observe')
    def test_cross_origin_never_runs_recognition(self, observe):
        handler = Handler(origin='https://other.example')
        self.assertTrue(bridge.handle(handler))
        self.assertEqual(handler.status, 403)
        observe.assert_not_called()

    @patch.object(bridge, 'observe')
    def test_oversized_body_never_runs_recognition(self, observe):
        handler = Handler()
        handler.headers.replace_header('Content-Length', str(bridge.MAX_BODY+1))
        bridge.handle(handler)
        self.assertEqual(handler.status, 413)
        observe.assert_not_called()

    @patch.object(bridge, 'observe', return_value={'detections': [], 'width':640, 'height':480, 'physical_ready':False})
    def test_empty_detection_is_success_not_device_ready(self, observe):
        handler = Handler()
        bridge.handle(handler)
        self.assertEqual(handler.status, 200)
        self.assertEqual(handler.value['detections'], [])
        self.assertFalse(handler.value['physical_ready'])

    @patch.object(bridge, 'observe', return_value={'error':'Model missing'})
    def test_model_error_is_not_an_empty_success(self, observe):
        handler = Handler()
        bridge.handle(handler)
        self.assertEqual(handler.status, 503)
        self.assertIn('error', handler.value)

    @patch.object(bridge, 'observe')
    def test_busy_request_never_duplicates_work(self, observe):
        handler = Handler()
        bridge._lock.acquire()
        try:
            bridge.handle(handler)
        finally:
            bridge._lock.release()
        self.assertEqual(handler.status, 409)
        observe.assert_not_called()
