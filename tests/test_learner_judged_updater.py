"""Publication invariants, independent of hosted model judgments."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from learner_intelligence import ProfileStore,digest
from learner_judged_updater import baseline_for,apply_changes,publish

class JudgedPublicationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=ProfileStore(self.tmp.name)
        self.batch=json.loads((ROOT/'tests/fixtures/learner-evidence.json').read_text())
        self.baseline=baseline_for(self.batch,self.store)
        self.proposal={'changes':[{'id':'braille','finding':'Scoped B/D observation.',
            'reasoning':'Teacher-confirmed observations only.','action':'Check an unfamiliar B/D example.'}]}
        self.approval={'accepted':True,'baseline_digest':digest(self.baseline),'proposal_digest':digest(self.proposal)}

    def test_rejection_retains_prior_bytes(self):
        publish(self.batch,self.proposal,self.approval,self.store)
        path=self.store.path(self.batch['learner_id']);before=path.read_bytes()
        with self.assertRaises(ValueError):publish(self.batch,self.proposal,{'accepted':False},self.store)
        self.assertEqual(before,path.read_bytes())

    def test_transform_failure_is_atomic(self):
        publish(self.batch,self.proposal,self.approval,self.store)
        path=self.store.path(self.batch['learner_id']);before=path.read_bytes()
        def unavailable(_):raise RuntimeError('Judge unavailable')
        with self.assertRaises(RuntimeError):
            self.store.update(self.batch['learner_id'],self.batch['display_name'],self.batch['events'],
                              synthetic=True,reviewed_transform=unavailable)
        self.assertEqual(before,path.read_bytes())

    def test_replay_does_not_publish_and_preserves_counts(self):
        first=publish(self.batch,self.proposal,self.approval,self.store)
        replay=publish(self.batch,self.proposal,self.approval,self.store)
        self.assertTrue(first['published']);self.assertFalse(replay['published'])
        self.assertEqual(first['profile']['categories'][0]['metric'],{'numerator':4,'denominator':5,'unit':'percent'})
        self.assertEqual(first['profile']['evidence'],self.baseline['evidence'])

    def test_changed_proposal_or_evidence_requires_new_judgment(self):
        altered=deepcopy(self.proposal);altered['changes'][0]['finding']='Tampered.'
        with self.assertRaises(ValueError):publish(self.batch,altered,self.approval,self.store)
        changed=deepcopy(self.batch);changed['events'][0]['outcome']='with_help'
        with self.assertRaises(ValueError):publish(changed,self.proposal,self.approval,self.store)
        self.assertIsNone(self.store.read(self.batch['learner_id']))

    def test_unknown_category_and_numeric_changes_rejected(self):
        altered=deepcopy(self.proposal);altered['changes'][0]['metric']={'numerator':100}
        with self.assertRaises(ValueError):apply_changes(self.baseline,altered)
        altered=deepcopy(self.proposal);altered['changes'][0]['id']='interests'
        with self.assertRaises(ValueError):apply_changes(self.baseline,altered)

    def test_no_change_no_epoch_and_mixed_identity_rejected(self):
        empty={'changes':[]};approval={**self.approval,'proposal_digest':digest(empty)}
        first=publish(self.batch,empty,approval,self.store)
        second=publish(self.batch,empty,approval,self.store)
        self.assertEqual(first['profile']['epoch'],1);self.assertFalse(second['published'])
        changed=deepcopy(self.batch);changed['events'][0]['learner_id']='another'
        with self.assertRaises(ValueError):baseline_for(changed,self.store)

if __name__=='__main__':unittest.main()
