"""Read-only learner reflection: evidence -> conditional, versioned profile. No hardware/model calls."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from threading import RLock

ROOT = Path(__file__).resolve().parents[1]
CATEGORIES = [('braille','Braille recognition'),('tactile','Tactile exploration'),('instructions','Understanding instructions'),('answering','Answering & asking for help'),('transfer','Retention & transfer'),('interests','Interests & participation')]
ACTIONS = {'braille':'Check an unfamiliar example without a naming hint.', 'tactile':'Ask the learner to show a comfortable starting point.', 'instructions':'Give one instruction at a time and check clarity.', 'answering':'Offer a response choice and ask which feels comfortable.', 'transfer':'Revisit the same target in a new context next session.', 'interests':'Offer two story topics and ask the learner to choose.'}
FIELDS = {'id','learner_id','session_id','occurred_at','category','target','task','condition','outcome','confirmed','synthetic','trace_id'}
OUTCOMES = {'independent','with_help','try_later','spoken','alternative','clear','repeated','device_failure'}

def now(): return datetime.now(timezone.utc).isoformat()
def digest(value): return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
def validate_event(e):
    if not isinstance(e,dict) or set(e)!=FIELDS: raise ValueError('Invalid evidence fields.')
    for k in FIELDS-{'confirmed','synthetic','trace_id'}:
        if not isinstance(e[k],str) or not 1<=len(e[k])<=240: raise ValueError('Invalid evidence text.')
    if e['category'] not in dict(CATEGORIES) or e['outcome'] not in OUTCOMES: raise ValueError('Unsupported evidence category/outcome.')
    if type(e['confirmed']) is not bool or type(e['synthetic']) is not bool: raise ValueError('Invalid confirmation/source flag.')
    if e['trace_id'] is not None and (not isinstance(e['trace_id'],str) or len(e['trace_id'])>500): raise ValueError('Invalid trace reference.')
    if datetime.fromisoformat(e['occurred_at'].replace('Z','+00:00')).tzinfo is None: raise ValueError('Evidence timestamps require a timezone.')
    if e['category']=='answering' and e['condition']!='speech and tactile alternatives available': raise ValueError('Preference evidence requires both response options.')
    allowed={'braille':{'independent','with_help','try_later'},'instructions':{'clear','repeated','try_later'},'answering':{'spoken','alternative','try_later'},'transfer':{'independent','with_help','try_later'},'tactile':{'try_later'},'interests':{'try_later'}}
    if e['outcome'] not in allowed[e['category']]|{'device_failure'}: raise ValueError('Outcome does not match teaching category.')

def derive(learner_id,name,events,synthetic):
    usable=[e for e in events if e['confirmed'] and e['outcome']!='device_failure']
    cards=[]
    for cid,title in CATEGORIES:
        rows=[e for e in usable if e['category']==cid and e['outcome']!='try_later']
        card={'id':cid,'title':title,'status':'Not enough observations','finding':f'We don’t yet have enough evidence about {title.lower()}.','action':ACTIONS[cid], 'reasoning':'No supported pattern established. Unconfirmed responses and device failures are excluded; deferred responses are not counted as incorrect.', 'evidence_ids':[], 'metric':None,'chart':None,'last_changed_at':None,'history':[]}
        # Compare only identical target, task and presentation/difficulty condition. Never pool unrelated tasks.
        groups={}
        for e in rows: groups.setdefault((e['target'],e['task'],e['condition']),[]).append(e)
        if groups:
            group=max(groups.values(),key=lambda g:max(e['occurred_at'] for e in g))
            sessions={}
            for e in sorted(group,key=lambda e:(e['occurred_at'],e['id'])): sessions.setdefault(e['session_id'],[]).append(e)
            ordered=list(sessions.values()); latest=ordered[-1]; success={'braille':'independent','instructions':'clear','answering':'spoken','transfer':'independent'}.get(cid)
            if success and len(latest)>=3:
                n=sum(e['outcome']==success for e in latest); total=len(latest); percent=round(n/total*100)
                card.update(status='Emerging preference' if cid=='answering' else 'Observed pattern', metric={'numerator':n,'denominator':total,'unit':'percent'}, evidence_ids=[e['id'] for e in group])
                target=latest[0]['target']; condition=latest[0]['condition']
                if cid=='braille':card['finding']=f'{name} identified {target} independently {percent}% of the time.'
                if cid=='instructions':card['finding']=f'{name} responded without a repeat on {percent}% of {condition} prompts.'
                if cid=='answering':
                    card['finding']=f'{name} chose spoken answers {percent}% of the time when both options were available.'
                    card['action']='Offer speech first, keep alternatives, and confirm the preference.'
                if cid=='transfer':card['finding']=f'{name} recognized {target} independently in {percent}% of these new-context opportunities.'
                card['reasoning']=f'{n} of {total} teacher-confirmed opportunities in the latest session, for {target}, {latest[0]["task"]}, under {condition}. This describes this task, not mastery or a diagnosis.'
                points=[{'session_id':s[0]['session_id'],'numerator':sum(e['outcome']==success for e in s),'denominator':len(s)} for s in ordered if len(s)>=3]
                if cid=='braille' and len(points)>=2 and 'unspecified' not in condition:
                    before=round(points[-2]['numerator']/points[-2]['denominator']*100)
                    if before!=percent:card['finding']+=f' Previously {before}% under comparable conditions.'
                    card['chart']={'type':'session_progress','points':points}
            elif cid=='transfer' and group:
                n=sum(e['outcome']=='independent' for e in group)
                finding=f'{name} recognized {group[0]["target"]} independently once in a new context.' if n==1 else f'{name} has {n} independent recognition observations in a new context.'
                if n==0:finding=f'{name} needed support identifying {group[0]["target"]} in a new context.'
                card.update(status='Early observation',finding=finding, evidence_ids=[e['id'] for e in group],reasoning='These are isolated new-context observations. Delayed retention has not been established.')
            elif rows:
                card['reasoning']=f'{len(group)} comparable observations available; at least three in a session are required before displaying a percentage.'
                card['evidence_ids']=[e['id'] for e in group]
        cards.append(card)
    recognition=[e for e in usable if e['category'] in ('braille','transfer')]
    current=cards[0]['metric']
    stats=[{'label':'Recognition targets practiced','value':str(len({e['target'] for e in recognition}))}, {'label':'Sessions with evidence','value':str(len({e['session_id'] for e in usable}))}, {'label':'Independent recognition · latest comparable session','value':f"{round(current['numerator']/current['denominator']*100)}%" if current else '—'}]
    return {'schema_version':'1.0','learner_id':learner_id,'display_name':name,'synthetic':synthetic,'epoch':0,'updated_at':None,'derivation_version':'rules-1','stats':stats,'categories':cards,'evidence':events,'updates':[]}

class ProfileStore:
    def __init__(self,directory): self.directory=Path(directory); self.lock=RLock()
    def path(self,learner):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',learner):raise ValueError('Invalid learner ID.')
        return self.directory/f'{learner}.json'
    def read(self,learner):
        p=self.path(learner)
        return json.loads(p.read_text()) if p.exists() else None
    def update(self,learner,name,incoming,*,synthetic=False,reviewed_transform=None):
        if not isinstance(name,str) or not 1<=len(name)<=80:raise ValueError('Invalid display name.')
        with self.lock:
            previous=self.read(learner)
            if previous and previous['profile']['synthetic']!=synthetic:raise ValueError('Cannot mix synthetic and real evidence.')
            merged={e['id']:e for e in (previous or {}).get('events',[])}
            for e in incoming:
                validate_event(e)
                if e['learner_id']!=learner or e['synthetic']!=synthetic:raise ValueError('Evidence belongs to another learner/source.')
                if e['id'] in merged and merged[e['id']]!=e:raise ValueError('Conflicting immutable event ID. Use a reviewed correction workflow.')
                merged[e['id']]=deepcopy(e)
            events=sorted(merged.values(),key=lambda e:(e['occurred_at'],e['id']))
            candidate=derive(learner,name,events,synthetic)
            if reviewed_transform is not None:
                # Optional judged producer; rejection raises before any store write.
                candidate=reviewed_transform(candidate)
            old=(previous or {}).get('profile')
            semantic=lambda c:{k:c[k] for k in ('status','finding','action','reasoning','metric','chart')}
            changed=[c['id'] for c in candidate['categories'] if not old or semantic(c)!=semantic(next(x for x in old['categories'] if x['id']==c['id']))]
            # Stats are meaningful evidence updates too. Provenance-only passes advance checkpoint, not epoch.
            publish=not old or bool(changed) or candidate['stats']!=old['stats'] or candidate.get('analysis',{}).get('summary')!=old.get('analysis',{}).get('summary')
            stamp=now()
            if publish:
                candidate['epoch']=(old['epoch'] if old else 0)+1; candidate['updated_at']=stamp
                candidate['updates']=(old['updates'] if old else [])+[{'epoch':candidate['epoch'],'at':stamp,'changed_categories':changed}]
                if candidate.get('analysis'):
                    candidate['updates'][-1]['source_url']=candidate['analysis']['source_url']
                for c in candidate['categories']:
                    prior=next((x for x in old['categories'] if x['id']==c['id']),None) if old else None
                    c['history']=deepcopy(prior['history']) if prior else []
                    c['last_changed_at']=prior['last_changed_at'] if prior else None
                    if c['id'] in changed:
                        c['last_changed_at']=stamp
                        c['history'].append({'epoch':candidate['epoch'],'at':stamp,'previous_finding':prior['finding'] if prior else None,'finding':c['finding'],'reasoning':c['reasoning'],'action':c['action'],'evidence_ids':c['evidence_ids']})
                profile=candidate
            else: profile=old  # Immutable publication; new processing evidence waits for a meaningful revision.
            record={'checkpoint':digest(events),'processed_at':stamp,'events':events,'profile':profile}
            if candidate.get('reflection'):
                record['reflection_version']=candidate['derivation_version']
                record['last_reflection']=candidate['reflection']
            self.directory.mkdir(parents=True,exist_ok=True)
            path=self.path(learner);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(record,indent=2)+'\n');tmp.replace(path)
            return {'published':publish,'changed_categories':changed,'profile':profile,'checkpoint':record['checkpoint']}

STORE=ProfileStore(ROOT/'.local/learner-intelligence')

def reflect_story(state,store=None,*,synthetic=False):
    """Only authoritative server snapshots; session identity never implies a persistent child identity."""
    if synthetic and (store is None or store.directory.resolve().is_relative_to(STORE.directory.resolve())):
        raise ValueError('Synthetic Story observations require an isolated store.')
    store=store or STORE
    learner=('synthetic-story-' if synthetic else 'story-')+state['session_id']; existing=store.read(learner); saved={e['id']:e for e in (existing or {}).get('events',[])}
    events=[]
    for o in state['observations']:
        if o['activity']!='identify':continue  # Introduction/matching is not identification.
        events.append(saved.get(o['id']) or {'id':o['id'],'learner_id':learner,'session_id':state['session_id'],'occurred_at':now(),'category':'braille','target':o['target'].upper(),'task':'identify','condition':'teacher-supplied tactile material; difficulty unspecified','outcome':o['outcome'],'confirmed':o['source']=='teacher','synthetic':synthetic,'trace_id':None})
    if not events:return None
    name=(state.get('synthetic_persona',{}).get('display_name','Story walkthrough')+' · fictional test') if synthetic else 'This learner'
    return store.update(learner,name,events,synthetic=synthetic)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('evidence');parser.add_argument('--store',default=str(ROOT/'.local/learner-intelligence'));parser.add_argument('--output')
    args=parser.parse_args();batch=json.loads(Path(args.evidence).read_text());result=ProfileStore(args.store).update(batch['learner_id'],batch['display_name'],batch['events'],synthetic=batch['synthetic'])
    if args.output:Path(args.output).write_text(json.dumps(result['profile'],indent=2)+'\n')
    print(json.dumps({'published':result['published'],'epoch':result['profile']['epoch'],'changed_categories':result['changed_categories'],'checkpoint':result['checkpoint']}))
