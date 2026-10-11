"""Bounded, acknowledged Delta writes. No model calls or inferred learner facts."""
from hashlib import sha256
import json
import re
from threading import RLock

from databricks.sdk.service.sql import StatementParameterListItem, ExecuteStatementRequestOnWaitTimeout
from learning.contract import validate_attempts, validate_batch, validate_profile


class StorageUnavailable(RuntimeError):
    pass


class RecordConflict(ValueError):
    pass


class ConsentRequired(ValueError):
    pass


class LearningStore:
    def __init__(self, services):
        config = services.config
        if not config.learning_warehouse_id:
            raise StorageUnavailable('Learning storage is not configured')
        if any(not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name) for name in (config.catalog, config.schema)):
            raise ValueError('Invalid learning namespace')
        self.services = services
        self.warehouse = config.learning_warehouse_id
        self.catalog, self.schema = config.catalog, config.schema
        prefix = f'{self.catalog}.{self.schema}'
        self.events = f'{prefix}.interaction_events_v2'
        self.profiles = f'{prefix}.profiles_v2'
        self.attempts = f'{prefix}.learning_attempts_v3'
        self.lock = RLock()  # Single-app writer; independent writers need external coordination.

    def execute(self, statement, values=None):
        parameters = [StatementParameterListItem(name=k, value=None if v is None else str(v))
                      for k, v in (values or {}).items()]
        try:
            response = self.services.client.statement_execution.execute_statement(
                warehouse_id=self.warehouse, statement=statement, catalog=self.catalog,
                schema=self.schema, parameters=parameters, wait_timeout='5s',
                on_wait_timeout=ExecuteStatementRequestOnWaitTimeout.CANCEL)
        except Exception as exc:
            raise StorageUnavailable('Learning storage request failed') from exc
        state = getattr(getattr(response, 'status', None), 'state', None)
        if getattr(state, 'value', state) != 'SUCCEEDED':
            raise StorageUnavailable('Learning storage has not confirmed success')
        return response

    def ensure_tables(self):
        self.execute(f'''CREATE TABLE IF NOT EXISTS {self.events} (
            event_id STRING, profile_id STRING, session_id STRING, occurred_at TIMESTAMP,
            event_type STRING, activity_id STRING, target STRING, outcome STRING,
            client_sequence BIGINT, metadata STRING, ingested_at TIMESTAMP) USING DELTA''')
        self.execute(f'''CREATE TABLE IF NOT EXISTS {self.profiles} (
            profile_id STRING, consent STRING, preferences STRING,
            created_at TIMESTAMP, updated_at TIMESTAMP) USING DELTA''')
        self.execute(f'''CREATE TABLE IF NOT EXISTS {self.attempts} (
            attempt_id STRING, profile_id STRING, session_id STRING, observed_at TIMESTAMP,
            activity_ref STRING, result STRING, support STRING, assessment STRING,
            fingerprint STRING, ingested_at TIMESTAMP) USING DELTA''')

    @staticmethod
    def _rows(response):
        if getattr(getattr(response, 'manifest', None), 'truncated', False):
            raise StorageUnavailable('Learning readback was truncated')
        return getattr(getattr(response, 'result', None), 'data_array', None) or []

    def _consent(self, profile_id):
        rows = self._rows(self.execute(f'SELECT consent FROM {self.profiles} WHERE profile_id=:profile_id',
                                      {'profile_id': profile_id}))
        if len(rows) != 1 or rows[0][0] != 'granted':
            raise ConsentRequired('Enable learning uploads for this profile first')

    def ingest_attempts(self, payload):
        validate_attempts(payload)
        with self.lock:
            self._consent(payload['profile_id'])
            columns = ['attempt_id', 'profile_id', 'session_id', 'observed_at', 'activity_ref', 'result', 'support', 'assessment', 'fingerprint']
            rows, values, fingerprints = [], {}, {}
            for i, attempt in enumerate(payload['attempts']):
                record = {**attempt, 'profile_id': payload['profile_id'], 'session_id': payload['session_id']}
                record['fingerprint'] = sha256(json.dumps(record, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
                fingerprints[attempt['attempt_id']] = record['fingerprint']
                rows.append('(' + ','.join(f':p{i}_{key}' for key in columns) + ')')
                values.update({f'p{i}_{key}': record[key] for key in columns})
            source = f"SELECT * FROM VALUES {','.join(rows)} AS s({','.join(columns)})"
            expressions = [f'CAST(s.{key} AS TIMESTAMP)' if key == 'observed_at' else f's.{key}' for key in columns]
            self.execute(f'''MERGE INTO {self.attempts} t USING ({source}) s ON t.attempt_id=s.attempt_id
                WHEN NOT MATCHED THEN INSERT ({','.join(columns)},ingested_at)
                VALUES ({','.join(expressions)},current_timestamp())''', values)
            ids = {f'id{i}': key for i, key in enumerate(fingerprints)}
            stored = self._rows(self.execute(f"SELECT attempt_id,fingerprint FROM {self.attempts} WHERE attempt_id IN ({','.join(':'+k for k in ids)})", ids))
            if len(stored) != len(fingerprints) or {row[0]: row[1] for row in stored} != fingerprints:
                raise RecordConflict('Attempt ID has different content or readback is incomplete')
            return {'schema_version': '3.0', 'profile_id': payload['profile_id'], 'session_id': payload['session_id'],
                    'attempt_ids': list(fingerprints)}

    def ingest_events(self, events):
        validate_batch({'schema_version': '2.0', 'events': events})
        with self.lock:
            self._consent(events[0]['profile_id'])
            columns = ['event_id', 'profile_id', 'session_id', 'occurred_at', 'event_type', 'activity_id', 'target', 'outcome', 'client_sequence', 'metadata']
            values, rows = {}, []
            for i, event in enumerate(events):
                rows.append('(' + ','.join(f':p{i}_{key}' for key in columns) + ')')
                values.update({f'p{i}_{key}': json.dumps(event[key], separators=(',', ':')) if key == 'metadata' else event[key] for key in columns})
            source = f"SELECT * FROM VALUES {','.join(rows)} AS s({','.join(columns)})"
            expressions = [f'CAST(s.{key} AS TIMESTAMP)' if key == 'occurred_at' else f'CAST(s.{key} AS BIGINT)' if key == 'client_sequence' else f's.{key}' for key in columns]
            self.execute(f'''MERGE INTO {self.events} t USING ({source}) s ON t.event_id=s.event_id
                WHEN NOT MATCHED THEN INSERT ({','.join(columns)},ingested_at)
                VALUES ({','.join(expressions)},current_timestamp())''', values)
            equal = ' AND '.join(f"t.{key} <=> {expr}" for key, expr in zip(columns, expressions))
            readback = self._rows(self.execute(f'SELECT t.event_id FROM {self.events} t JOIN ({source}) s ON t.event_id=s.event_id WHERE {equal}', values))
            ids = [event['event_id'] for event in events]
            if len(readback) != len(ids) or {row[0] for row in readback} != set(ids):
                raise RecordConflict('Event ID has different content or readback is incomplete')
            return {'event_ids': ids}

    def create_profile(self, profile):
        validate_profile(profile)
        with self.lock:
            values = {'profile_id': profile['profile_id'], 'consent': profile['consent'],
                      'preferences': json.dumps(profile['preferences'], separators=(',', ':'))}
            self.execute(f'''MERGE INTO {self.profiles} t USING (SELECT :profile_id profile_id,
                :consent consent, :preferences preferences) s ON t.profile_id=s.profile_id
                WHEN MATCHED THEN UPDATE SET consent=s.consent, preferences=s.preferences, updated_at=current_timestamp()
                WHEN NOT MATCHED THEN INSERT (profile_id,consent,preferences,created_at,updated_at)
                VALUES (s.profile_id,s.consent,s.preferences,current_timestamp(),current_timestamp())''', values)
            return {'profile_id': profile['profile_id'], 'status': 'ready', 'consent': profile['consent']}
