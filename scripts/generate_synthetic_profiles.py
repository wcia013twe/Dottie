"""Generate isolated fictional evidence and profiles; no cloud or live-store writes.

Run with the contract environment:
  databricks/magneto-director/.venv/bin/python scripts/generate_synthetic_profiles.py
"""
import argparse
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile

from jsonschema import Draft202012Validator
from learner_intelligence import CATEGORIES, ProfileStore, ROOT, validate_event

DEFAULT_OUTPUT = ROOT / 'reports/synthetic-learner-profiles'


def event(learner, session, category, index, outcome, *, condition=None, confirmed=True):
    day = int(session[-1])
    targets = {'braille': 'B/D', 'tactile': 'comfortable starting point',
               'instructions': 'spoken instruction', 'answering': 'response choice',
               'transfer': 'R', 'interests': 'story topic choice'}
    tasks = {'braille': 'identify', 'tactile': 'explore', 'instructions': 'follow_prompt',
             'answering': 'choose_response', 'transfer': 'identify_new_context',
             'interests': 'choose_topic'}
    conditions = {'braille': 'same tactile presentation; recognition difficulty one',
                  'tactile': 'teacher offers comfortable starting point',
                  'instructions': 'single-step',
                  'answering': 'speech and tactile alternatives available',
                  'transfer': 'new story, same tactile presentation',
                  'interests': 'two story topics offered'}
    return {'id': f'{learner}-{session}-{category}-{index}', 'learner_id': learner,
            'session_id': session,
            'occurred_at': (datetime(2026, 10, day, 14, tzinfo=timezone.utc) +
                            timedelta(seconds=index)).isoformat(),
            'category': category, 'target': targets[category], 'task': tasks[category],
            'condition': condition or conditions[category], 'outcome': outcome,
            'confirmed': confirmed, 'synthetic': True, 'trace_id': None}


def batches():
    learner = 'synthetic-river'
    rows = []
    for session, outcomes in [('session-1', ['independent']*2 + ['with_help']*3),
                              ('session-2', ['independent']*4 + ['with_help']),
                              ('session-3', ['independent']*3 + ['with_help']*2)]:
        groups = {'braille': outcomes,
                  'instructions': ['clear']*4 + ['repeated'],
                  'answering': ['spoken']*3 + ['alternative']*2,
                  'tactile': ['try_later'], 'interests': ['try_later']}
        if session == 'session-2':
            groups['transfer'] = ['independent']  # No percentage from one observation.
        for category, values in groups.items():
            for index, outcome in enumerate(values):
                rows.append(event(learner, session, category, index, outcome))
    # Keep deferred, failed and unconfirmed records but exclude them from percentages.
    rows += [event(learner, 'session-3', 'braille', 20, 'try_later'),
             event(learner, 'session-3', 'braille', 21, 'device_failure'),
             event(learner, 'session-3', 'braille', 22, 'independent', confirmed=False)]
    main = {'learner_id': learner, 'display_name': 'River (fictional)',
            'synthetic': True, 'events': rows}
    sparse_id = 'synthetic-sky'
    sparse = {'learner_id': sparse_id, 'display_name': 'Sky (fictional)',
              'synthetic': True, 'events': [event(sparse_id, 'session-1', 'braille', 0,
                                               'with_help')]}
    changed = deepcopy(main)
    changed['events'] += [event(learner, 'session-3', 'braille', 30, 'independent',
                               condition='different tactile presentation; difficulty two')]
    return {'river': main, 'sky-insufficient': sparse, 'river-changed-condition': changed}


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def generate(output):
    output = output.resolve()
    if output == ROOT or output == ROOT / 'reports' or output == ROOT / 'web':
        raise ValueError('Choose a dedicated fixture directory.')
    if output == ROOT / '.local' or ROOT / '.local' in output.parents:
        raise ValueError('Fixture generator must not write application stores under .local.')
    output.mkdir(parents=True, exist_ok=True)
    schema_dir = ROOT / 'databricks/contracts/learner-profile-v1'
    event_validator = Draft202012Validator(json.loads((schema_dir / 'evidence-event.schema.json').read_text()))
    profile_validator = Draft202012Validator(json.loads((schema_dir / 'profile.schema.json').read_text()))
    data = batches()
    steps = []
    with tempfile.TemporaryDirectory(prefix='magneto-synthetic-profile-') as directory:
        store = ProfileStore(Path(directory) / 'river')
        main = data['river']
        for number in (1, 2, 3):
            events = [e for e in main['events'] if int(e['session_id'][-1]) <= number]
            result = store.update(main['learner_id'], main['display_name'], events, synthetic=True)
            profile_validator.validate(result['profile'])
            write(output / f'river-epoch-{number}.profile.json', result['profile'])
            card = result['profile']['categories'][0]
            assert card['metric'] == {'numerator': (2, 4, 3)[number-1], 'denominator': 5, 'unit': 'percent'}
            assert result['profile']['epoch'] == number
            assert result['profile']['synthetic'] is True
            steps.append({'step': f'session-{number}', 'epoch': number, 'published': result['published'],
                          'braille_metric': card['metric']})
        before = deepcopy(store.read(main['learner_id']))
        replay = store.update(main['learner_id'], main['display_name'], main['events'], synthetic=True)
        assert replay['published'] is False and replay['profile'] == before['profile']
        steps.append({'step': 'identical-replay', 'epoch': replay['profile']['epoch'], 'published': False})
        for label, incoming in [('conflicting-event', [dict(main['events'][0], outcome='with_help')]),
                                ('different-learner', data['sky-insufficient']['events']),
                                ('real-source-mix', [dict(main['events'][0], synthetic=False)])]:
            try:
                store.update(main['learner_id'], main['display_name'], incoming, synthetic=True)
            except ValueError:
                assert store.read(main['learner_id'])['profile'] == replay['profile']
                steps.append({'step': label, 'rejected': True, 'profile_preserved': True})
            else:
                raise AssertionError(f'{label} must fail')
        for label, batch in data.items():
            for row in batch['events']:
                event_validator.validate(row)
                validate_event(row)
                assert row['synthetic'] is True and row['trace_id'] is None
            write(output / f'{label}.evidence.json', batch)
            isolated = ProfileStore(Path(directory) / label / 'fresh')
            profile = isolated.update(batch['learner_id'], batch['display_name'], batch['events'], synthetic=True)['profile']
            profile_validator.validate(profile)
            assert [c['id'] for c in profile['categories']] == [c[0] for c in CATEGORIES]
            assert profile['categories'][1]['metric'] is None
            assert profile['categories'][5]['metric'] is None
            if label == 'sky-insufficient':
                assert all(c['metric'] is None for c in profile['categories'])
            if label == 'river-changed-condition':
                assert profile['categories'][0]['metric'] is None and profile['categories'][0]['chart'] is None
            if label == 'river':
                assert profile['categories'][4]['metric'] is None
                assert profile['categories'][4]['status'] == 'Early observation'
            write(output / f'{label}.profile.json', profile)
    report = {'synthetic': True, 'verified': True, 'cloud_calls': False,
              'producer': 'scripts/learner_intelligence.py:ProfileStore',
              'steps': steps, 'scenarios': {k: len(v['events']) for k, v in data.items()},
              'limits': ['No real learner, cloud write, Genie call, MLflow join or physical action.',
                         'Tactile and interests remain unknown: v1 only accepts deferred/failure outcomes there.',
                         'Help is a supported recognition outcome; v1 does not record who requested help.',
                         'Changed presentation/difficulty is not pooled into a previous recognition trend.',
                         'Fixture confirmation flags describe fictional observations, not real teacher approval.']}
    write(output / 'verification.json', report)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=DEFAULT_OUTPUT)
    generate(parser.parse_args().output_dir)
