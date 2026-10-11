import io
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import voice_bridge


class VoiceBridgeTests(unittest.TestCase):
    def test_missing_key_is_explicit(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(voice_bridge.create_token()[0], 503)

    def test_only_temporary_token_is_returned(self):
        with patch.dict(os.environ, {'ELEVENLABS_API_KEY':'permanent-test-secret'}), patch.object(voice_bridge, 'urlopen') as request:
            request.return_value.__enter__.return_value.read.return_value = b'{"token":"temporary","extra":"private"}'
            status, result = voice_bridge.create_token()
            self.assertEqual((status,result),(200,{'token':'temporary'}))
            self.assertNotIn('permanent-test-secret', json.dumps(result))

    def test_upstream_error_never_echoes_secret_body(self):
        with patch.dict(os.environ, {'ELEVENLABS_API_KEY':'secret'}), patch.object(voice_bridge, 'urlopen', side_effect=HTTPError('url',401,'secret',{},io.BytesIO(b'secret'))):
            status, result=voice_bridge.create_token()
            self.assertEqual(status,502); self.assertNotIn('secret',str(result))

    def test_cross_origin_never_requests_token(self):
        from email.message import Message
        from types import SimpleNamespace
        headers=Message();headers['Host']='localhost:8097';headers['Origin']='https://external.example';headers['Content-Type']='application/json'
        results=[]
        handler=SimpleNamespace(path='/api/voice-token',headers=headers,server=SimpleNamespace(server_port=8097),_json=lambda *args:results.append(args))
        with patch.object(voice_bridge,'create_token') as create:
            self.assertTrue(voice_bridge.handle(handler));create.assert_not_called()
        self.assertEqual(results[0][0],403)
