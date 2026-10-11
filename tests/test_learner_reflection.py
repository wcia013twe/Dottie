"""Offline integration tests: real coordinator, isolated stores, substituted cloud services."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from learner_episodes import episodes
from learner_reflection import reflect, validate_proposal, quote_text
from learner_intelligence import ProfileStore
from learner_judged_updater import baseline_for

class ReflectionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=ProfileStore(self.temp.name)
        self.batch=json.loads((Path(__file__).parent/'fixtures/learner-evidence.json').read_text())
        self.research=lambda _: {'queries':[], 'passages':[{'id':'p1','text':'Synthetic scoped evidence.'}]}
        self.proposal={'changes':[{'id':'braille','finding':'Scoped observation.',
            'reasoning':'Confirmed observations for B/D only.', 'action':'Try an unfamiliar B/D example.'}],
            'support':[{'category':'braille','event_ids':[self.batch['events'][0]['id']],
                        'passage_ids':['p1'],'excerpts':[{'passage_id':'p1','quote':'Synthetic scoped evidence.'}],'basis':'inferred','applicability':'Limited evidence; test this suggestion.'}]}
    def run_reflection(self, **kw):
        return reflect(self.batch,self.store,kw.get('research',self.research),
            kw.get('propose',lambda _:deepcopy(self.proposal)),
            kw.get('assess',lambda *_:{'accepted':True}),uuid4().hex,kw.get('summarize'))
    def test_episode_dedup_conflict_order_and_missing_context(self):
        rows=deepcopy(self.batch['events'][:3]);rows[0]['outcome']='device_failure'
        rows[1]['confirmed']=False
        result=episodes(list(reversed(rows))+[rows[0]])
        self.assertEqual(result[0]['steps'],rows)
        self.assertIn('not recorded',result[0]['coverage'])
        self.assertEqual(result,episodes(rows))
        changed={**rows[0],'outcome':'independent'}
        with self.assertRaises(ValueError):episodes(rows+[changed])
    def test_timezone_order_is_chronological(self):
        rows=deepcopy(self.batch['events'][:2])
        rows[0]['occurred_at']='2026-10-10T13:00:00+02:00'
        rows[1]['occurred_at']='2026-10-10T12:00:00+00:00'
        self.assertEqual(episodes(rows)[0]['event_ids'],[e['id'] for e in rows])
    def test_publication_audit_replay_and_authoritative_counts(self):
        baseline=baseline_for(self.batch,self.store)
        first=self.run_reflection()
        self.assertTrue(first['published'])
        self.assertEqual(first['profile']['categories'][0]['metric'],baseline['categories'][0]['metric'])
        audit=json.loads((self.store.directory/'reflections'/f'{first["audit_id"]}.json').read_text())
        self.assertEqual(audit['proposal']['support'][0]['passage_ids'],['p1'])
        self.assertEqual(audit['inputs']['episodes'],episodes(self.batch['events']))
        def forbidden(*_):raise AssertionError('Replay called cloud')
        self.assertFalse(self.run_reflection(research=forbidden)['published'])
    def test_rejected_and_invalid_citations_preserve_profile(self):
        self.run_reflection();before=self.store.path(self.batch['learner_id']).read_bytes()
        self.batch['events'].append({**self.batch['events'][0],'id':'new-event'})
        with self.assertRaises(ValueError):self.run_reflection(assess=lambda *_:{'accepted':False})
        self.assertEqual(before,self.store.path(self.batch['learner_id']).read_bytes())
        self.proposal['support'][0]['passage_ids']=['invented']
        with self.assertRaises(ValueError):self.run_reflection()
        self.assertEqual(before,self.store.path(self.batch['learner_id']).read_bytes())
        self.assertEqual(len(list((self.store.directory/'reflections').glob('*.json'))),3)
    def test_pdf_quote_normalization_only_changes_typography(self):
        self.assertEqual(quote_text('“stu-dents” reading\nbraille'),quote_text('"students" reading braille'))
        self.assertNotEqual(quote_text('students did not improve'),quote_text('students improved'))

    def test_fabricated_quote_is_rejected_before_judge(self):
        self.proposal['support'][0]['excerpts'][0]['quote']='This exact recommendation does not occur in the paper.'
        def forbidden(*_):raise AssertionError('Invalid quote reached judge')
        with self.assertRaises(ValueError):self.run_reflection(assess=forbidden)
        self.assertIsNone(self.store.read(self.batch['learner_id']))

    def test_audit_upload_failure_prevents_publication(self):
        def fail(_):raise RuntimeError('Audit storage unavailable')
        with self.assertRaises(RuntimeError):
            reflect(self.batch,self.store,self.research,lambda _:self.proposal,
                    lambda *_:{'accepted':True},uuid4().hex,audit_sink=fail)
        self.assertIsNone(self.store.read(self.batch['learner_id']))

    def test_empty_search_has_explicit_no_change(self):
        def forbidden(*_):raise AssertionError('No passages must not propose actions')
        result=self.run_reflection(research=lambda _: {'queries':[],'passages':[]},propose=forbidden)
        audit=json.loads((self.store.directory/'reflections'/f'{result["audit_id"]}.json').read_text())
        self.assertEqual(audit['proposal'],{'changes':[],'support':[]})
    def test_failed_search_does_not_publish(self):
        def fail(*_):raise RuntimeError('search unavailable')
        with self.assertRaises(RuntimeError):self.run_reflection(research=fail)
        self.assertIsNone(self.store.read(self.batch['learner_id']))
    def test_stale_evidence_rejected(self):
        def racing_assess(*_):
            self.store.update(self.batch['learner_id'],self.batch['display_name'],
                self.batch['events']+[{**self.batch['events'][0],'id':'concurrent'}],synthetic=True)
            return {'accepted':True}
        with self.assertRaises(ValueError):self.run_reflection(assess=racing_assess)
        self.assertNotIn('reflection',self.store.read(self.batch['learner_id'])['profile'])
    def test_genie_cannot_overwrite_judged_categories(self):
        self.batch['synthetic']=False
        for event in self.batch['events']:event['synthetic']=False
        def summary(candidate):
            candidate['categories'][0]['action']='Unjudged action'
            candidate['analysis']={'summary':'Observed evidence only.', 'source_url':'https://example.org/summary'}
            return candidate
        result=self.run_reflection(summarize=summary)
        self.assertEqual(result['profile']['categories'][0]['action'],self.proposal['changes'][0]['action'])

if __name__=='__main__':unittest.main()
