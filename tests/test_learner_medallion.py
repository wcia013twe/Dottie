"""Offline storage-boundary tests: quarantine, replay, immutable gold and failure recovery."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import learner_medallion as layers
import learner_cloud
import learner_bridge as bridge
from learner_intelligence import ProfileStore, digest
from learner_reflection import VERSION


class MemorySQL:
    def __init__(self):
        self.bronze={};self.quarantine={};self.gold={};self.silver={}
    def execute(self,sql,p=None):
        p=p or {}
        if sql.startswith(f'MERGE INTO {layers.BRONZE}'):
            self.bronze.setdefault(p['id'],p['payload']);return []
        if sql.startswith(f'SELECT payload FROM {layers.BRONZE}'):
            return [{'payload':self.bronze[p['id']]}] if p['id'] in self.bronze else []
        if sql.startswith(f'MERGE INTO {layers.QUARANTINE}'):
            self.quarantine.setdefault(p['id'],p['reason']);return []
        if sql.startswith(f'MERGE INTO {layers.GOLD}'):
            self.gold.setdefault((p['learner'],p['epoch']),p['profile']);return []
        if sql.startswith(f'SELECT profile FROM {layers.GOLD}'):
            value=self.gold.get((p['learner'],p['epoch']))
            return [{'profile':value}] if value else []
        raise AssertionError(sql)
    def insert_silver(self,event):
        if event['id'] in self.silver and self.silver[event['id']]!=event:raise layers.EventConflict('conflict')
        self.silver[event['id']]=deepcopy(event)
    def ingest(self,events):
        ids=layers.capture(self.execute,events)
        return layers.promote(self.execute,ids,self.insert_silver)


class MedallionTests(unittest.TestCase):
    def setUp(self):
        self.db=MemorySQL()
        self.batch=json.loads((Path(__file__).parent/'fixtures/learner-evidence.json').read_text())
        self.batch['synthetic']=False
        for event in self.batch['events']:event['synthetic']=False
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=ProfileStore(self.tmp.name)
    def profile(self):
        result=self.store.update(self.batch['learner_id'],self.batch['display_name'],self.batch['events'])
        return result['profile']
    def test_bronze_exact_payload_replay_and_silver_conflict(self):
        self.assertEqual(self.db.ingest(self.batch['events']),len(self.batch['events']))
        before=deepcopy(self.db.silver)
        self.db.ingest(self.batch['events']*2)
        self.assertEqual(self.db.silver,before)
        self.assertEqual(len(self.db.bronze),len(before))
        changed={**self.batch['events'][0],'outcome':'try_later'}
        with self.assertRaises(ValueError):self.db.ingest([changed])
        self.assertEqual(self.db.silver,before)
        self.assertEqual(self.db.quarantine[digest(changed)],'immutable_event_conflict')
        self.assertEqual(json.loads(self.db.bronze[digest(changed)]),changed)
    def test_invalid_contract_retained_and_quarantined_synthetic_never_lands(self):
        bad={**self.batch['events'][0],'category':'unsupported'}
        with self.assertRaises(ValueError):self.db.ingest([bad])
        self.assertEqual(self.db.quarantine[digest(bad)],'invalid_event_contract')
        self.assertFalse(self.db.silver)
        for flags in ({'synthetic':True},{'confirmed':False}):
            event={**self.batch['events'][0],**flags}
            with self.assertRaises(ValueError):self.db.ingest([event])
            self.assertNotIn(digest(event),self.db.bronze)
    def test_cloud_failure_remains_replayable_without_quarantine(self):
        ids=layers.capture(self.db.execute,self.batch['events'][:1])
        def unavailable(_):raise RuntimeError('warehouse unavailable')
        with self.assertRaises(RuntimeError):layers.promote(self.db.execute,ids,unavailable)
        self.assertFalse(self.db.quarantine)
        layers.promote(self.db.execute,ids,self.db.insert_silver)
        self.assertEqual(len(self.db.silver),1)
    def test_new_excluded_evidence_does_not_manufacture_gold_epoch(self):
        first=self.profile()
        event={**self.batch['events'][0],'id':'device-failure','outcome':'device_failure'}
        result=self.store.update(self.batch['learner_id'],self.batch['display_name'],[event])
        self.assertFalse(result['published'])
        self.assertEqual(result['profile'],first)
        self.assertNotEqual(result['checkpoint'],digest(first['evidence']))
    def test_gold_exact_readback_immutable_replay_and_metrics_gate(self):
        self.db.ingest(self.batch['events']);profile=self.profile()
        read=lambda learner:[e for e in self.db.silver.values() if e['learner_id']==learner]
        first=layers.publish(self.db.execute,profile,read)
        self.assertEqual(first['profile'],profile)
        self.assertEqual(layers.publish(self.db.execute,profile,read),first)
        self.assertEqual(len(self.db.gold),1)
        bad=deepcopy(profile);bad['stats'][0]['value']='999'
        with self.assertRaises(ValueError):layers.publish(self.db.execute,bad,read)
        bad=deepcopy(profile);bad['categories'][0]['finding']='Different prose'
        with self.assertRaises(ValueError):layers.publish(self.db.execute,bad,read)
        with self.assertRaises(ValueError):layers.publish(self.db.execute,profile,lambda _:[])
        with self.assertRaises(ValueError):layers.publish(self.db.execute,profile,lambda _:self.batch['events'][1:])
    def test_gold_rejects_cross_learner_and_synthetic(self):
        profile=self.profile()
        for key,value in [('learner_id','other'),('synthetic',True)]:
            bad=deepcopy(profile);bad['evidence'][0][key]=value
            with self.assertRaises(ValueError):layers.validate_gold(bad)
    def test_bridge_cloud_failure_retains_profile_and_retries_same_candidate(self):
        self.store.update(self.batch['learner_id'],self.batch['display_name'],self.batch['events'][:3])
        before=self.store.path(self.batch['learner_id']).read_bytes()
        calls=[]
        def reflect_run(command,**kwargs):
            request=json.loads(kwargs['input']);stage=ProfileStore(request['store'])
            def checked(profile):profile['derivation_version']=VERSION;profile['reflection']={'id':'audit','input_digest':'input','proposal_digest':'proposal'};return profile
            result=stage.update(request['batch']['learner_id'],request['batch']['display_name'],request['batch']['events'],reviewed_transform=checked)
            return SimpleNamespace(returncode=0,stdout=json.dumps(result))
        def cloud(operation,payload):
            calls.append(deepcopy(payload['profile']))
            if len(calls)==1:raise RuntimeError('Ambiguous cloud commit')
            return {'profile':payload['profile']}
        with patch.object(bridge,'STORE',self.store),patch.object(bridge.subprocess,'run',side_effect=reflect_run),patch.object(bridge,'cloud',side_effect=cloud):
            with self.assertRaises(RuntimeError):bridge.materialize({'learner_id':self.batch['learner_id'],'events':self.batch['events']})
            self.assertEqual(self.store.path(self.batch['learner_id']).read_bytes(),before)
            bridge.materialize({'learner_id':self.batch['learner_id'],'events':self.batch['events']})
        self.assertEqual(calls[0],calls[1])
        self.assertEqual(self.store.read(self.batch['learner_id'])['profile'],calls[1])
    def test_restore_gold_preserves_epoch_and_rejects_missing_silver(self):
        profile=self.profile();self.store.path(self.batch['learner_id']).unlink()
        with patch.object(bridge,'STORE',self.store):
            with self.assertRaises(ValueError):bridge.restore_gold({'learner_id':self.batch['learner_id'],'events':[],'gold_profile':profile})
            bridge.restore_gold({'learner_id':self.batch['learner_id'],'events':self.batch['events'],'gold_profile':profile})
        self.assertEqual(self.store.read(self.batch['learner_id'])['profile'],profile)

if __name__=='__main__':unittest.main()
