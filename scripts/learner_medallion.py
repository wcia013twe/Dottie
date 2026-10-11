"""Learner storage layers. SQL is injected so replay/publication tests stay offline.

Bronze retains received confirmed-real event JSON, not microphone/camera data or
whole Story snapshots. Existing observations remain the authoritative silver API.
"""
import json
from learner_intelligence import ROOT, CATEGORIES, validate_event, derive, digest

BRONZE = 'workspace.magneto.learner_bronze_v1'
QUARANTINE = 'workspace.magneto.learner_quarantine_v1'
GOLD = 'workspace.magneto.learner_gold_v1'
LATEST = 'workspace.magneto.learner_gold_latest_v1'


class EventConflict(ValueError):
    """An immutable silver ID already identifies different content."""


def setup(execute):
    execute(f'''CREATE TABLE IF NOT EXISTS {BRONZE} (
        ingest_id STRING, event_id STRING, learner_id STRING, payload STRING,
        schema_version STRING, source STRING, ingested_at TIMESTAMP) USING DELTA''')
    execute(f'''CREATE TABLE IF NOT EXISTS {QUARANTINE} (
        ingest_id STRING, reason STRING, rejected_at TIMESTAMP) USING DELTA''')
    execute(f'''CREATE TABLE IF NOT EXISTS {GOLD} (
        learner_id STRING, epoch BIGINT, profile STRING, fingerprint STRING,
        evidence_digest STRING, derivation_version STRING, published_at TIMESTAMP)
        USING DELTA''')
    execute(f'''CREATE OR REPLACE VIEW {LATEST} AS
        SELECT * EXCEPT (rn) FROM (SELECT *, row_number() OVER (
        PARTITION BY learner_id ORDER BY epoch DESC) rn FROM {GOLD}) WHERE rn = 1''')


def capture(execute, events, *, source='confirmed-story-event-v1'):
    if not isinstance(events, list) or len(events) > 10000:
        raise ValueError('Expected a bounded event batch.')
    # Preserve the existing upload scope: synthetic/unconfirmed inputs never land
    # in production bronze, even when another field would fail silver validation.
    for event in events:
        if (not isinstance(event, dict) or event.get('synthetic') is not False
                or event.get('confirmed') is not True):
            raise ValueError('Only confirmed real observations may enter bronze.')
    identifiers = []
    for event in events:
        payload = json.dumps(event, sort_keys=True, allow_nan=False)
        if len(payload.encode()) > 65536:
            raise ValueError('Event payload exceeds bronze bound.')
        identifier = digest(event)
        execute(f'''MERGE INTO {BRONZE} t USING (SELECT :id ingest_id) s
            ON t.ingest_id=s.ingest_id WHEN NOT MATCHED THEN INSERT
            VALUES (:id,:event,:learner,:payload,'1.0',:source,current_timestamp())''',
            {'id': identifier, 'event': event.get('id') if isinstance(event.get('id'),str) else None,
             'learner': event.get('learner_id') if isinstance(event.get('learner_id'),str) else None,
             'payload': payload, 'source': source})
        stored = execute(f'SELECT payload FROM {BRONZE} WHERE ingest_id=:id', {'id': identifier})
        if len(stored) != 1 or stored[0]['payload'] != payload:
            raise ValueError('Bronze readback mismatch.')
        identifiers.append(identifier)
    return identifiers


def promote(execute, identifiers, silver_insert):
    failures = []
    for identifier in dict.fromkeys(identifiers):
        rows = execute(f'SELECT payload FROM {BRONZE} WHERE ingest_id=:id', {'id': identifier})
        if len(rows) != 1:
            raise ValueError('Missing or ambiguous bronze record.')
        try:
            event = json.loads(rows[0]['payload'])
            validate_event(event)
            if event['synthetic'] or not event['confirmed']:
                raise ValueError('Invalid production source flags.')
        except (ValueError, TypeError, KeyError):
            reason = 'invalid_event_contract'
        else:
            try:
                silver_insert(event)
                continue
            except EventConflict:
                reason = 'immutable_event_conflict'
        # Service failures propagate; they are retryable, not bad learner evidence.
        execute(f'''MERGE INTO {QUARANTINE} t USING (SELECT :id ingest_id) s
            ON t.ingest_id=s.ingest_id WHEN NOT MATCHED THEN INSERT
            VALUES (:id,:reason,current_timestamp())''', {'id': identifier, 'reason': reason})
        failures.append(identifier)
    if failures:
        raise ValueError('Bronze records quarantined; no profile update requested.')
    return len(set(identifiers))


def validate_gold(profile):
    import jsonschema
    schema = json.loads((ROOT/'databricks/contracts/learner-profile-v1/profile.schema.json').read_text())
    jsonschema.Draft202012Validator(schema).validate(profile)
    if profile['synthetic'] or profile['epoch'] < 1 or not profile['updated_at']:
        raise ValueError('Gold requires a published real epoch.')
    events = profile['evidence']
    seen = set()
    for event in events:
        validate_event(event)
        if (event['synthetic'] or not event['confirmed'] or
                event['learner_id'] != profile['learner_id'] or event['id'] in seen):
            raise ValueError('Gold evidence must be unique, confirmed and learner scoped.')
        seen.add(event['id'])
    baseline = derive(profile['learner_id'], profile['display_name'], events, False)
    if profile['stats'] != baseline['stats']:
        raise ValueError('Gold counts must match deterministic evidence.')
    cards = {card['id']: card for card in profile['categories']}
    if set(cards) != dict(CATEGORIES).keys():
        raise ValueError('Gold needs six distinct categories.')
    for expected in baseline['categories']:
        for key in ('metric', 'chart', 'evidence_ids', 'status'):
            if cards[expected['id']][key] != expected[key]:
                raise ValueError('Gold metrics/provenance must match deterministic evidence.')
    epochs = [update['epoch'] for update in profile['updates']]
    if epochs != list(range(1, profile['epoch'] + 1)):
        raise ValueError('Gold epoch history must be contiguous.')


def publish(execute, profile, silver_read):
    validate_gold(profile)
    silver = {event['id']: event for event in silver_read(profile['learner_id'])}
    if any(silver.get(event['id']) != event for event in profile['evidence']):
        raise ValueError('Gold evidence is missing or differs from silver.')
    payload = json.dumps(profile, sort_keys=True, allow_nan=False)
    values = {'learner': profile['learner_id'], 'epoch': str(profile['epoch']),
              'profile': payload, 'fingerprint': digest(profile),
              'evidence': digest(profile['evidence']), 'version': profile['derivation_version']}
    existing = execute(f'SELECT profile FROM {GOLD} WHERE learner_id=:learner AND epoch=:epoch', values)
    if existing:
        if len(existing) != 1 or existing[0]['profile'] != payload:
            raise ValueError('Conflicting immutable gold epoch.')
    else:
        execute(f'''MERGE INTO {GOLD} t USING (SELECT :learner learner_id, CAST(:epoch AS BIGINT) epoch) s
            ON t.learner_id=s.learner_id AND t.epoch=s.epoch WHEN NOT MATCHED THEN INSERT
            VALUES (:learner,CAST(:epoch AS BIGINT),:profile,:fingerprint,:evidence,:version,current_timestamp())''', values)
    rows = execute(f'SELECT profile FROM {GOLD} WHERE learner_id=:learner AND epoch=:epoch', values)
    if len(rows) != 1 or rows[0]['profile'] != payload:
        raise ValueError('Gold publication readback mismatch.')
    return {'profile': json.loads(rows[0]['profile']), 'table': GOLD}


def read_gold(execute, learner):
    if not learner:
        return None
    rows = execute(f'SELECT profile,fingerprint FROM {LATEST} WHERE learner_id=:learner', {'learner': learner})
    if not rows:
        return None
    if len(rows) != 1:
        raise ValueError('Ambiguous gold profile.')
    profile = json.loads(rows[0]['profile'])
    validate_gold(profile)
    if profile['learner_id'] != learner or digest(profile) != rows[0]['fingerprint']:
        raise ValueError('Gold identity/fingerprint mismatch.')
    return profile
