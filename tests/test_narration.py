import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('narration',ROOT/'scripts/build_narration.py')
narration=importlib.util.module_from_spec(spec);spec.loader.exec_module(narration)

class NarrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.script=json.loads((ROOT/'story_mode/narration/peter-rabbit.example.json').read_text())
        self.calls=[]
    def convert(self,voice,payload,key):
        self.calls.append((voice,payload));return b'\0\0'*24000
    def build(self,**kwargs):return narration.build(self.script,self.tmp.name,'test-voice',convert=self.convert,**kwargs)
    def test_full_peter_script_matches_extractor_and_has_unique_pages(self):
        spec=importlib.util.spec_from_file_location('prepare_peter',ROOT/'scripts/prepare_peter_narration.py')
        prepare=importlib.util.module_from_spec(spec);spec.loader.exec_module(prepare)
        script=prepare.prepare()
        self.assertEqual(script,json.loads((ROOT/'story_mode/narration/peter-rabbit.json').read_text()))
        narration.validate(script)
        self.assertEqual([p['id'] for p in script['passages']],['title-opening',*[f'page-{n:02d}' for n in range(3,30)]])
        for passage in script['passages'][1:]:
            self.assertEqual(sum(passage['match_text'].lower() in p['text'].lower() for p in script['passages']),1)
        self.assertIn('Flopsy,',script['passages'][1]['text'])
        self.assertTrue(script['passages'][-1]['text'].endswith('blackberries for supper.'))

    def test_local_env_quotes_comments_and_shell_precedence(self):
        path=Path(self.tmp.name)/'.env'
        path.write_text('# local settings\nexport ELEVENLABS_API_KEY="local-key" # comment\nELEVENLABS_VOICE_ID=voice123\nOTHER_KEY=ignored\n')
        env={'ELEVENLABS_API_KEY':'shell-key'}
        narration.load_local_env(path,env)
        self.assertEqual(env,{'ELEVENLABS_API_KEY':'shell-key','ELEVENLABS_VOICE_ID':'voice123'})
    def test_env_is_literal_and_bad_values_do_not_leak(self):
        path=Path(self.tmp.name)/'.env'
        path.write_text("ELEVENLABS_API_KEY='$(command)'\n")
        env={};narration.load_local_env(path,env)
        self.assertEqual(env['ELEVENLABS_API_KEY'],'$(command)')
        path.write_text('ELEVENLABS_API_KEY="private-invalid-value\n')
        with self.assertRaises(ValueError) as caught:narration.load_local_env(path,{})
        self.assertNotIn('private-invalid-value',str(caught.exception))
    def test_missing_env_file_is_optional(self):
        env={};narration.load_local_env(Path(self.tmp.name)/'missing',env)
        self.assertEqual(env,{})

    def test_reuses_audio_and_regenerates_only_changed_text(self):
        first=self.build();self.assertEqual(first['generate'],2)
        manifest=json.loads(Path(first['manifest']).read_text())
        self.assertEqual(manifest['passages'][0]['duration_seconds'],1)
        self.script['script_version']='sample-2'
        self.assertEqual(self.build()['reuse'],2)
        self.script['passages'][0]['text']+=' A new sentence.'
        self.assertEqual(self.build()['generate'],1);self.assertEqual(len(self.calls),3)
    def test_voice_settings_invalidate_audio(self):
        self.build();self.script['voice_settings']['stability']=0.7
        self.assertEqual(self.build()['generate'],2)
    def test_failure_keeps_previous_manifest_and_resumes_completed_files(self):
        first=self.build();path=Path(first['manifest']);old=path.read_bytes()
        self.script['passages'][0]['text']+=' Changed.'
        self.script['passages'][1]['text']+=' Changed.'
        count=0
        def partial(*args):
            nonlocal count
            count+=1
            if count==2:raise ValueError('Synthetic API failure')
            return self.convert(*args)
        with self.assertRaises(ValueError):narration.build(self.script,self.tmp.name,'test-voice',convert=partial)
        self.assertEqual(path.read_bytes(),old)
        self.assertEqual(self.build()['generate'],1)
    def test_invalid_script_fails_before_network_and_dry_run_writes_nothing(self):
        self.assertEqual(self.build(dry_run=True)['generate'],2)
        self.assertEqual(list(Path(self.tmp.name).iterdir()),[]);self.assertEqual(self.calls,[])
        self.script['passages'][1]['id']=self.script['passages'][0]['id']
        with self.assertRaises(ValueError):self.build()
        self.assertEqual(self.calls,[])
    def test_missing_key_and_bad_pcm_do_not_publish_manifest(self):
        with self.assertRaises(ValueError):narration.build(self.script,self.tmp.name,'test-voice')
        with self.assertRaises(ValueError):narration.build(self.script,self.tmp.name,'test-voice',convert=lambda *args:b'odd')
        self.assertFalse((Path(self.tmp.name)/self.script['book_id']/'manifest.json').exists())
    def test_api_request_has_expected_format_and_auth_only_in_header(self):
        from email.message import Message
        from unittest.mock import MagicMock
        response=MagicMock();response.headers=Message();response.headers['Content-Type']='audio/pcm'
        response.read.return_value=b'\0\0'*24
        response.__enter__.return_value=response
        opener=MagicMock();opener.open.return_value=response
        payload={'text':'Synthetic narration','model_id':'eleven_multilingual_v2','voice_settings':{}}
        with patch.object(narration,'build_opener',return_value=opener):
            narration.synthesize('voice123',payload,'test-key')
        req=opener.open.call_args.args[0]
        self.assertEqual(req.full_url,'https://api.elevenlabs.io/v1/text-to-speech/voice123?output_format=pcm_24000')
        self.assertEqual(req.get_header('Xi-api-key'),'test-key')
        self.assertEqual(json.loads(req.data),payload)
        self.assertNotIn('test-key',req.data.decode())

    def test_corrupt_audio_is_regenerated(self):
        result=self.build();manifest=json.loads(Path(result['manifest']).read_text())
        (Path(result['manifest']).parent/manifest['passages'][0]['audio']).write_bytes(b'broken')
        self.assertEqual(self.build()['generate'],1)

if __name__=='__main__':unittest.main()
