"""Validate base-contract examples and compatibility with the deployed demo validators."""
import copy
import json
from pathlib import Path
import sys
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'databricks/contracts/v1'
V2=ROOT/'databricks/contracts/v2'
sys.path.insert(0,str(ROOT/'databricks/magneto-director'))
from agent.decision import make_snapshot, validate_snapshot, validate_decision, DECISION_SCHEMA

def read(path): return json.loads(path.read_text())
validators={}
for path in BASE.glob('*.schema.json'):
    schema=read(path)
    Draft202012Validator.check_schema(schema)
    validators[path.name.removesuffix('.schema.json')]=Draft202012Validator(schema,format_checker=FormatChecker())

examples={'guidance':'guidance','retrieval-request':'retrieval-request','retrieval-result':'retrieval-result',
          'retrieval-empty':'retrieval-result','browser-request':'browser-request','session-snapshot':'session-snapshot',
          'decision-teach':'decision','decision-continue':'decision',
          'companion-snapshot':'companion-snapshot','companion-tool-plan':'companion-tool-plan',
          'companion-outcome':'companion-outcome'}
for name,contract in examples.items(): validators[contract].validate(read(BASE/'examples'/f'{name}.json'))
snapshot=read(BASE/'examples/session-snapshot.json')
assert make_snapshot(read(BASE/'examples/browser-request.json'))==snapshot
validate_snapshot(snapshot)
for action in ('teach','continue'): validate_decision(read(BASE/'examples'/f'decision-{action}.json'),snapshot)
assert set(validators['decision'].schema['required'])==set(DECISION_SCHEMA['required'])
for fixture in (ROOT/'databricks/magneto-director/fixtures').glob('*.json'):
    value=read(fixture)['snapshot'];validators['session-snapshot'].validate(value);validate_snapshot(value)

def rejects(contract,value):
    try: validators[contract].validate(value)
    except ValidationError: return
    raise AssertionError(f'{contract} accepted invalid example')
result=read(BASE/'examples/retrieval-result.json')
bad=copy.deepcopy(result);bad['matches'][0]['approved']=False;rejects('retrieval-result',bad)
bad=copy.deepcopy(result);del bad['matches'][0]['citation'];rejects('retrieval-result',bad)
bad=copy.deepcopy(result);bad['schema_version']='2.0';rejects('retrieval-result',bad)
bad=read(BASE/'examples/decision-continue.json');bad['prompt']='Unexpected activity';rejects('decision',bad)
bad=copy.deepcopy(snapshot);bad['schema_version']='1.0';rejects('session-snapshot',bad)
bad=read(BASE/'examples/companion-tool-plan.json');bad['tool']='move_servos';rejects('companion-tool-plan',bad)
bad=read(BASE/'examples/companion-tool-plan.json');bad['arguments']={'session_id':bad['arguments']['session_id']};rejects('companion-tool-plan',bad)
bad=read(BASE/'examples/companion-outcome.json');bad['match']='maybe';rejects('companion-outcome',bad)
bad=read(BASE/'examples/companion-snapshot.json');del bad['device'];rejects('companion-snapshot',bad)
print(f'Validated {len(validators)} schemas, {len(examples)} examples, live demo fixtures and negative cases. No cloud calls.')

for name in ("profile", "evidence-event", "feed-status"):
    folder=ROOT/"databricks/contracts/learner-profile-v1"
    schema=read(folder/f"{name}.schema.json")
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema,format_checker=FormatChecker()).validate(read(folder/f"{name}.example.json"))
print("Validated additive learner profile/evidence contracts. Legacy v1 unchanged.")
Draft202012Validator(read(folder/'profile.schema.json'),format_checker=FormatChecker()).validate(read(folder/'genie-profile.example.json'))
print("Validated Genie profile provenance example.")

Draft202012Validator(read(folder/'profile.schema.json'),format_checker=FormatChecker()).validate(read(folder/'research-profile.example.json'))
print('Validated research reflection provenance example.')

# Optional fictional Story seed: kept separate from learner outcome/profile contracts.
persona_schema=read(ROOT/'databricks/contracts/synthetic-story-persona-v1/persona.schema.json')
Draft202012Validator.check_schema(persona_schema)
persona_validator=Draft202012Validator(persona_schema)
persona=read(ROOT/'story_mode/personas/alex-morgan.json')
persona_validator.validate(persona)
bad=copy.deepcopy(persona);bad['synthetic']=False
try:persona_validator.validate(bad)
except ValidationError:pass
else:raise AssertionError('Real records cannot use the synthetic persona contract')
print('Validated isolated synthetic Story persona contract and source example.')
v2_validators={}
for path in V2.glob('*.schema.json'):
    schema=read(path)
    Draft202012Validator.check_schema(schema)
    v2_validators[path.name.removesuffix('.schema.json')]=Draft202012Validator(schema,format_checker=FormatChecker())
v2_validators['interaction-event'].validate(read(V2/'examples/interaction-event.json'))
v2_validators['profile'].validate(read(V2/'examples/profile.json'))

from learning.contract import validate_attempts, validate_batch, validate_profile
v3 = ROOT / 'databricks/contracts/v3'
schema = read(v3 / 'attempt-batch.schema.json')
Draft202012Validator.check_schema(schema)
v3_validator = Draft202012Validator(schema, format_checker=FormatChecker())
rabbit = read(v3 / 'examples/rabbit-session.json')
v3_validator.validate(rabbit)
validate_attempts(rabbit)
validate_batch({'schema_version': '2.0', 'events': [read(V2 / 'examples/interaction-event.json')]})
validate_profile(read(V2 / 'examples/profile.json'))
assert read(v3 / 'activity-catalog.json') == read(ROOT / 'databricks/magneto-director/learning/activity-catalog.json')
assert set(schema['properties']['attempts']['items']['properties']['activity_ref']['enum']) == set(read(v3 / 'activity-catalog.json'))
generated = (ROOT / 'web/learn/activity-catalog.js').read_text().split('export const ACTIVITY_CATALOG = ',1)[1].strip().removesuffix(';')
assert json.loads(generated) == read(v3 / 'activity-catalog.json')
for mutate in (
    lambda p: p['attempts'][0].update(transcript='not accepted'),
    lambda p: p['attempts'][0].update(assessment='unconfirmed'),
    lambda p: p['attempts'][0].update(activity_ref='unknown'),
):
    bad=copy.deepcopy(rabbit);mutate(bad)
    try: v3_validator.validate(bad)
    except ValidationError: pass
    else: raise AssertionError('v3 schema accepted invalid input')
    try: validate_attempts(bad)
    except (ValueError, TypeError): pass
    else: raise AssertionError('v3 runtime accepted invalid input')
print(f'Validated {len(validators)+len(v2_validators)+1} schemas, {len(examples)+3} examples, generated catalogs, live demo fixtures and negative cases. No cloud calls.')

# Additive local hardware messages; neither interface changes deployed demo payloads.
cell_folder=ROOT/'databricks/contracts/story-cell-v1'
for name in ('request','receipt'):
    schema=read(cell_folder/f'{name}.schema.json')
    Draft202012Validator.check_schema(schema)
    validator=Draft202012Validator(schema,format_checker=FormatChecker())
    validator.validate(read(cell_folder/f'{name}.example.json'))
    bad=read(cell_folder/f'{name}.example.json')
    if name=='request':bad['target']='rabbit;CLEAR'
    else:bad['cell_ack']=False
    try:validator.validate(bad)
    except ValidationError:pass
    else:raise AssertionError('Invalid cell message accepted')
print('Validated additive Story cell request and successful receipt contracts.')

# Additive navigation classification: existing model, no new execution authority.
sys.path.insert(0,str(ROOT/'scripts'))
from voice_navigation import validate_request as validate_navigation_request, validate_action as validate_navigation_action
nav_folder=ROOT/'databricks/contracts/voice-navigation-v1'
for name in ('request','response'):
    schema=read(nav_folder/f'{name}.schema.json')
    Draft202012Validator.check_schema(schema)
    validator=Draft202012Validator(schema)
    example=read(nav_folder/f'{name}.example.json')
    validator.validate(example)
    if name=='request':validate_navigation_request(example)
    else:assert validate_navigation_action({'action':'stories'},read(nav_folder/'request.example.json'))==example['intent']
    bad=copy.deepcopy(example)
    if name=='request':bad['route']='outside'
    else:bad['intent']['route']='https://outside.example'
    try:validator.validate(bad)
    except ValidationError:pass
    else:raise AssertionError('Navigation schema accepted arbitrary destination')
print('Validated additive navigation request and bounded model intent contracts.')
