"""Offline validation/publication tests; no Databricks calls or evidence uploads."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from learner_intelligence import ProfileStore, derive
from learner_genie import apply_proposal, apply_summary, generate, parse_proposal
import learner_bridge as bridge

SOURCE={'conversation_id':'test','response_id':'test','source_url':'https://dbc-129a8d44-1940.cloud.databricks.com/one/chat/threads/test'}
def proposal(baseline):
    return {'summary':'Confirmed task evidence is available for review.' if baseline['evidence'] else 'No confirmed learner evidence is available yet.','categories':[
        {'id':c['id'],'finding':c['finding'],'action':c['action'],
         'reasoning':'Use the recorded evidence for this task; no broader pattern is established.',
         'evidence_ids':c['evidence_ids']} for c in baseline['categories']]}

class GenieTests(unittest.TestCase):
    def test_fenced_proposal_with_transport_narration_and_ambiguity(self):
        self.assertEqual(parse_proposal('Read-only check completed.\n```json\n{"summary":"example"}\n```'),{'summary':'example'})
        with self.assertRaises(ValueError):
            parse_proposal('```json\n{}\n```\n```json\n{}\n```')

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=ProfileStore(self.temp.name)
        self.baseline=derive('unassigned','This learner',[],False)
    def candidate(self,baseline):return apply_proposal(baseline,proposal(baseline),SOURCE)
    def test_empty_profile_has_genie_provenance_without_progress(self):
        candidate=self.candidate(self.baseline)
        self.assertEqual(candidate['stats'],self.baseline['stats'])
        self.assertTrue(all(c['metric'] is None for c in candidate['categories']))
        self.assertEqual(candidate['analysis']['source_url'],SOURCE['source_url'])
    def test_reject_fabricated_references_and_percentages(self):
        for key,value in [('evidence_ids',['invented']),('finding','Recognition improved to 80%.')]:
            p=proposal(self.baseline);p['categories'][0][key]=value
            with self.assertRaises(ValueError):apply_proposal(self.baseline,p,SOURCE)
    def test_reject_missing_categories_and_html(self):
        p=proposal(self.baseline);p['categories'].pop()
        with self.assertRaises(ValueError):apply_proposal(self.baseline,p,SOURCE)
        p=proposal(self.baseline);p['categories'][0]['action']='<script>bad</script>'
        with self.assertRaises(ValueError):apply_proposal(self.baseline,p,SOURCE)
    def test_mock_never_calls_genie(self):
        b=copy.deepcopy(self.baseline);b['synthetic']=True
        with self.assertRaises(ValueError):generate(b)
    def test_summary_only_cannot_edit_categories(self):
        result=apply_summary(self.baseline,{'summary':'No confirmed observations yet.'},SOURCE)
        self.assertEqual(result['categories'],self.baseline['categories'])
        self.assertEqual(result['derivation_version'],self.baseline['derivation_version'])
        with self.assertRaises(ValueError):
            apply_summary(self.baseline,{'summary':'New action','categories':[]},SOURCE)

    def test_empty_evidence_does_not_call_models(self):
        with patch.object(bridge,'STORE',self.store),patch.object(bridge.subprocess,'run') as call:
            result=bridge.materialize({'learner_id':None,'events':[]})
        self.assertFalse(result['published']);call.assert_not_called()

    def test_failed_reflection_preserves_previous_publication(self):
        batch=json.loads((Path(__file__).resolve().parents[1]/'tests/fixtures/learner-evidence.json').read_text())
        events=[{**e,'synthetic':False} for e in batch['events']]
        self.store.update(batch['learner_id'],'This learner',events)
        before=self.store.path(batch['learner_id']).read_bytes()
        with patch.object(bridge,'STORE',self.store),patch.object(bridge.subprocess,'run',return_value=Mock(returncode=1)):
            with self.assertRaises(RuntimeError):bridge.materialize({'learner_id':batch['learner_id'],'events':events})
        self.assertEqual(before,self.store.path(batch['learner_id']).read_bytes())

    def test_pending_story_does_not_publish_rule_profile(self):
        pending=ProfileStore(Path(self.temp.name)/'pending')
        state={'session_id':'test','observations':[{'id':'event','activity':'identify','target':'b','outcome':'independent','source':'teacher'}]}
        with patch.object(bridge,'PENDING_STORE',pending),patch.object(bridge,'STORE',self.store),patch.object(bridge,'select'),patch.object(bridge,'refresh'):
            bridge.publish_story(state)
        self.assertIsNone(self.store.read('story-test'))
        self.assertEqual(len(pending.read('story-test')['events']),1)
    def test_fenced_json_is_data(self):
        p=proposal(self.baseline)
        self.assertEqual(parse_proposal('```json\n'+json.dumps(p)+'\n```'),p)

if __name__=='__main__':unittest.main()
