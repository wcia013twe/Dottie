"""Reproducible fixture proof; never writes real learner data or calls cloud services."""
import json
from pathlib import Path
import tempfile
from learner_intelligence import ProfileStore, ROOT
batch=json.loads((ROOT/'tests/fixtures/learner-evidence.json').read_text())
with tempfile.TemporaryDirectory() as directory:
    store=ProfileStore(directory)
    results=[]
    for label,events in [('first_session',[e for e in batch['events'] if e['session_id']=='sample-1']),('new_session',batch['events']),('repeat_background_pass',batch['events'])]:
        result=store.update(batch['learner_id'],batch['display_name'],events,synthetic=True)
        card=next(c for c in result['profile']['categories'] if c['id']=='braille')
        results.append({'step':label,'published':result['published'],'epoch':result['profile']['epoch'],'finding':card['finding'],'metric':card['metric'],'history_entries':len(card['history'])})
    assert [r['epoch'] for r in results]==[1,2,2]
    assert [r['published'] for r in results]==[True,True,False]
    report={'synthetic':True,'verified':True,'cloud_calls':False,'steps':results}
    (ROOT/'reports/learner-intelligence-proof.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
