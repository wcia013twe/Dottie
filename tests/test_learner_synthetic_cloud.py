"""Isolation guards for the explicit cloud fixture path; no cloud requests."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import learner_genie
import learner_bridge
from learner_intelligence import derive, reflect_story, ProfileStore, STORE
from test_synthetic_cloud_flow import validate_batch


class SyntheticCloudTests(unittest.TestCase):
    def test_story_walkthrough_is_saved_synthetic_and_replay_is_idempotent(self):
        state={'session_id':'walkthrough','observations':[{'id':'observation-1','activity':'identify','target':'r','source':'teacher','outcome':'independent'}]}
        with self.assertRaises(ValueError): reflect_story(state,synthetic=True)
        with self.assertRaises(ValueError): reflect_story(state,STORE,synthetic=True)
        with self.assertRaises(ValueError): reflect_story(state,ProfileStore(STORE.directory/'pending-evidence'),synthetic=True)
        with tempfile.TemporaryDirectory() as directory:
            store=ProfileStore(directory)
            first=reflect_story(state,store,synthetic=True)
            second=reflect_story(state,store,synthetic=True)
            self.assertTrue(first['profile']['synthetic'])
            self.assertTrue(first['profile']['learner_id'].startswith('synthetic-story-'))
            self.assertFalse(second['published'])
            saved=store.read(first['profile']['learner_id'])
            self.assertEqual(len(saved['events']),1)
            self.assertTrue(saved['events'][0]['synthetic'])

    def setUp(self):
        self.batch = json.loads((ROOT/'reports/synthetic-learner-profiles/river.evidence.json').read_text())
        self.baseline = derive(self.batch['learner_id'], 'Fictional River', self.batch['events'], True)

    def test_production_genie_still_rejects_synthetic(self):
        with patch.object(learner_genie, '_generate') as request:
            with self.assertRaises(ValueError):
                learner_genie.generate(self.baseline)
            request.assert_not_called()

    def test_test_path_rejects_real_and_mixed_evidence_before_request(self):
        for kind in ('profile', 'event', 'identity'):
            bad = copy.deepcopy(self.baseline)
            if kind == 'profile': bad['synthetic'] = False
            if kind == 'event': bad['evidence'][0]['synthetic'] = False
            if kind == 'identity': bad['evidence'][0]['learner_id'] = 'other-learner'
            with patch.object(learner_genie, '_generate') as request:
                with self.assertRaises(ValueError): learner_genie.generate_synthetic_test(bad)
                request.assert_not_called()

    def test_upload_rejects_real_events_duplicates_and_fabricated_traces(self):
        for kind in ('real', 'duplicate', 'trace'):
            bad = copy.deepcopy(self.batch)
            if kind == 'real': bad['events'][0]['synthetic'] = False
            if kind == 'duplicate': bad['events'].append(copy.deepcopy(bad['events'][0]))
            if kind == 'trace': bad['events'][0]['trace_id'] = 'fictional-cloud-trace'
            with self.assertRaises(ValueError): validate_batch(bad)

    def test_genie_test_prompt_and_cache_exclude_live_source(self):
        with patch.object(learner_genie, '_generate', return_value=self.baseline) as request:
            learner_genie.generate_synthetic_test(self.baseline)
            _, prompt, cache = request.call_args.args
            self.assertNotIn('workspace.magneto.learner_observations_v1', prompt)
            self.assertIn('workspace.magneto.synthetic_learner_e2e_v1', prompt)
            self.assertIn('fictional', prompt)
            self.assertEqual(cache, ROOT/'.local/synthetic-learner-e2e/genie-analysis')

    def test_test_profile_endpoint_never_refreshes_live_store(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            out=root/'reports/synthetic-cloud-flow'
            out.mkdir(parents=True)
            (out/'profile.json').write_text(json.dumps(self.baseline))
            (out/'latest.json').write_text(json.dumps({'status':'passed','learner_id':self.baseline['learner_id']}))
            from unittest.mock import Mock
            handler=SimpleNamespace(path='/api/learner-profile?mode=synthetic-test',
                headers={'Host':'127.0.0.1:8099'},server=SimpleNamespace(server_port=8099),_json=Mock())
            with patch.object(learner_bridge,'ROOT',root), patch.object(learner_bridge,'refresh') as refresh:
                self.assertTrue(learner_bridge.handle(handler))
                self.assertEqual(handler._json.call_args.args,(200,self.baseline))
                refresh.assert_not_called()
                (out/'latest.json').write_text(json.dumps({'status':'failed','learner_id':self.baseline['learner_id']}))
                learner_bridge.handle(handler)
                self.assertEqual(handler._json.call_args.args[0],503)
                refresh.assert_not_called()
