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
import voice_navigation


class VoiceBridgeTests(unittest.TestCase):
    def test_model_navigation_is_bounded_and_reader_controls_depend_on_context(self):
        payload={'text':'I would love a book','route':'home','story_reader':False}
        voice_navigation.validate_request(payload)
        self.assertEqual(voice_navigation.validate_action({'action':'stories'},payload),{'type':'navigate','route':'stories'})
        for result in ({'action':'https://outside.example'},{'action':'stories','extra':'bad'},{'action':'next_page'},{'action':'grade_answer'}):
            with self.assertRaises(ValueError):voice_navigation.validate_action(result,payload)
        payload['story_reader']=True
        self.assertEqual(voice_navigation.validate_action({'action':'next_page'},payload),{'type':'control','name':'next page'})
        for bad in ({**payload,'text':''},{**payload,'route':'outside'},{**payload,'story_reader':1},{**payload,'profile':'private'}):
            with self.assertRaises(ValueError):voice_navigation.validate_request(bad)

    def test_model_failure_is_explicit_and_never_echoes_process_details(self):
        from types import SimpleNamespace
        with patch.object(voice_navigation.subprocess,'run',return_value=SimpleNamespace(returncode=1,stdout='private transcript',stderr='secret')):
            status,result=voice_navigation.interpret({'text':'a book please','route':'home','story_reader':False})
        self.assertEqual(status,503);self.assertNotIn('secret',str(result));self.assertNotIn('private transcript',str(result))

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
        for path in ('/api/voice-token','/api/voice-intent'):
            handler=SimpleNamespace(path=path,headers=headers,server=SimpleNamespace(server_port=8097),_json=lambda *args:results.append(args))
            with patch.object(voice_bridge,'create_token') as create,patch.object(voice_navigation,'interpret') as interpret:
                self.assertTrue(voice_bridge.handle(handler));create.assert_not_called();interpret.assert_not_called()
        self.assertEqual(results[0][0],403)

    def test_missing_transcription_permission_is_actionable_without_echoing_body(self):
        body=json.dumps({'detail':{'status':'missing_permissions','message':'secret missing speech_to_text'}}).encode()
        with patch.dict(os.environ, {'ELEVENLABS_API_KEY':'secret'}), patch.object(voice_bridge, 'urlopen', side_effect=HTTPError('url',401,'unauthorized',{},io.BytesIO(body))):
            status,result=voice_bridge.create_token()
        self.assertEqual(status,502)
        self.assertIn('Speech to Text permission',result['error'])
        self.assertNotIn('secret',str(result))
