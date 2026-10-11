"""Validate base-contract examples and compatibility with the deployed demo validators."""
import copy
import json
from pathlib import Path
import sys
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'databricks/contracts/v1'
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
