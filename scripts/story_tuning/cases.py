"""Small synthetic regression pilot; labels come from the existing demo policy."""
from itertools import product
from uuid import uuid5, NAMESPACE_URL


def records(split):
    rows = []
    specs = [('monday_apple', ()), ('tuesday_pear', ()), ('wednesday_plum', ())]
    lengths = [1, 2] if split == 'train' else [3]
    for n in lengths:
        specs.extend(('wednesday_plum', r) for r in product(('correct','incorrect','help'), repeat=n))
    if split != 'train':
        specs = specs[3:]  # held-out response sequences, never used by GEPA
    for i, (passage, responses) in enumerate(specs):
        def uid(label): return str(uuid5(NAMESPACE_URL, f'magneto-story-{split}-{i}-{label}'))
        events = [dict(event_id=uid(f'event-{j}'), passage_id='tuesday_pear', target_letter='P', response=r)
                  for j, r in enumerate(responses)]
        action = 'continue' if passage == 'monday_apple' or (responses and responses[-1] == 'correct') else 'teach'
        evidence = ('A is familiar; P difficulty is irrelevant.' if passage == 'monday_apple' else
                    f'Latest P response is {responses[-1]}; most recent evidence wins.' if responses else
                    'P needs practice; no recent success was supplied.')
        rows.append({'inputs': {'request': dict(request_id=uid('request'),session_id=uid('session'),
                     passage_id=passage,events=events)},
                     'expectations': {'action':action,'evidence':evidence}})
    return rows
