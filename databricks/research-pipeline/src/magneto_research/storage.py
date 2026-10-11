"""Small SQL adapter; Databricks owns execution, Delta storage and search indexing."""
import json
import time
from databricks.sdk.service.sql import StatementParameterListItem


class Warehouse:
    def __init__(self, client, config):
        if not config.warehouse_id:
            raise ValueError('Configure an existing serverless SQL warehouse_id')
        self.client, self.config = client, config

    def execute(self, statement, params=None, timeout=600):
        api = self.client.statement_execution
        response = api.execute_statement(
            statement, self.config.warehouse_id, wait_timeout='10s',
            parameters=[StatementParameterListItem(name=k, value=v if v is None else str(v))
                        for k, v in (params or {}).items()])
        deadline = time.monotonic() + timeout
        while response.status.state.value in {'PENDING', 'RUNNING'}:
            if time.monotonic() >= deadline:
                api.cancel_execution(response.statement_id)
                raise TimeoutError(f'SQL timed out: {response.statement_id}')
            time.sleep(1)
            response = api.get_statement(response.statement_id)
        if response.status.state.value != 'SUCCEEDED':
            code = getattr(response.status.error, 'error_code', 'UNKNOWN')
            raise RuntimeError(f'SQL failed ({code}); inspect statement {response.statement_id}')
        if response.manifest and response.manifest.truncated:
            raise RuntimeError('SQL response truncated; narrow the request')
        if not response.result:
            return []
        names = [c.name for c in response.manifest.schema.columns]
        result, rows = response.result, []
        while result:
            rows.extend(dict(zip(names, row)) for row in (result.data_array or []))
            if result.next_chunk_index is None:
                break
            result = api.get_statement_result_chunk_n(response.statement_id, result.next_chunk_index)
        return rows


def initialize(db, config):
    """Only research-owned tables/views. No schemas, volumes, grants or endpoints."""
    t = config.table
    definitions = {
        'sources': 'id STRING, source_id STRING, collection STRING, title STRING, uri STRING, '
                   'sha256 STRING, volume_path STRING, metadata STRING, valid_until DATE, '
                   'created_at TIMESTAMP, actor STRING',
        'chunks': 'id STRING, source_version STRING, run_id STRING, text STRING, '
                  'embedding_text STRING, locator STRING, pages STRING',
        'findings': 'id STRING, chunk_id STRING, run_id STRING, body STRING',
        'recommendations': 'id STRING, collection STRING, body STRING, created_at TIMESTAMP, actor STRING',
        'reviews': 'id STRING, subject_id STRING, action STRING, rationale STRING, '
                   'created_at TIMESTAMP, actor STRING',
        'runs': 'id STRING, subject_id STRING, operation STRING, status STRING, '
                'details STRING, created_at TIMESTAMP, actor STRING',
        'search_documents': 'id STRING, collection STRING, tier STRING, kind STRING, '
                            'embedding_text STRING',
    }
    for name, columns in definitions.items():
        db.execute(f"CREATE TABLE IF NOT EXISTS {t(name)} ({columns}) USING DELTA "
                   "TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')")
    db.execute(f'''CREATE OR REPLACE VIEW {t('latest_reviews')} AS
        SELECT * EXCEPT (rn) FROM (
          SELECT *, row_number() OVER (PARTITION BY subject_id ORDER BY created_at DESC, id DESC) rn
          FROM {t('reviews')}) WHERE rn = 1''')
    # A source remains ineligible after reactivation until its findings are reviewed again.
    db.execute(f'''CREATE OR REPLACE VIEW {t('eligible_chunks')} AS
        SELECT c.*, s.collection, s.title, s.uri, s.source_id, s.metadata,
               coalesce(r.created_at, s.created_at) source_reviewed_at
        FROM {t('chunks')} c JOIN {t('sources')} s ON c.source_version = s.id
        JOIN {t('runs')} run ON c.run_id = run.id AND run.status = 'completed'
        LEFT JOIN {t('latest_reviews')} r ON s.id = r.subject_id
        WHERE coalesce(r.action, 'active') = 'active'
          AND (s.valid_until IS NULL OR s.valid_until >= current_date())''')
    db.execute(f'''CREATE OR REPLACE VIEW {t('eligible_findings')} AS
        SELECT f.*, c.collection, c.source_version, c.text, c.locator, c.title, c.uri,
               c.source_id, c.metadata, r.created_at reviewed_at
        FROM {t('findings')} f JOIN {t('eligible_chunks')} c ON f.chunk_id = c.id
        JOIN {t('runs')} run ON f.run_id = run.id AND run.status = 'completed'
        JOIN {t('latest_reviews')} r ON f.id = r.subject_id AND r.action = 'accepted'
        WHERE r.created_at >= c.source_reviewed_at''')
    db.execute(f'''CREATE OR REPLACE VIEW {t('eligible_recommendations')} AS
        WITH dependencies AS (
          SELECT rec.id, explode(from_json(get_json_object(rec.body, '$.finding_ids'),
                 'ARRAY<STRING>')) finding_id FROM {t('recommendations')} rec
        ), valid AS (
          SELECT d.id, count(*) total, count(f.id) available, max(f.reviewed_at) latest_finding_review
          FROM dependencies d LEFT JOIN {t('eligible_findings')} f ON d.finding_id = f.id
          GROUP BY d.id
        ) SELECT rec.* FROM {t('recommendations')} rec
          JOIN valid v ON rec.id = v.id AND v.total = v.available AND v.total > 0
          JOIN {t('latest_reviews')} r ON rec.id = r.subject_id AND r.action = 'approved'
          WHERE r.created_at >= v.latest_finding_review''')
    db.execute(f'''CREATE OR REPLACE VIEW {t('eligible_documents')} AS
        SELECT id, collection, 'library' tier, 'passage' kind, embedding_text
        FROM {t('eligible_chunks')}
        UNION ALL SELECT id, collection, 'reviewed' tier, 'finding' kind,
          concat(title, '\\n', get_json_object(body, '$.statement'), '\\n',
                 get_json_object(body, '$.context'), '\\n', get_json_object(body, '$.limitations'))
        FROM {t('eligible_findings')}
        UNION ALL SELECT id, collection, 'approved' tier, 'recommendation' kind,
          concat(get_json_object(body, '$.text'), '\\n', get_json_object(body, '$.rationale'),
                 '\\n', get_json_object(body, '$.limitations'))
        FROM {t('eligible_recommendations')}''')


def refresh_search(db, config):
    t = config.table
    db.execute(f'''MERGE INTO {t('search_documents')} target
        USING {t('eligible_documents')} source ON target.id = source.id
        WHEN MATCHED THEN UPDATE SET * WHEN NOT MATCHED THEN INSERT *
        WHEN NOT MATCHED BY SOURCE THEN DELETE''')


def insert(db, config, table, row):
    # Columns come exclusively from package-owned callers, not model output.
    columns = ', '.join(row)
    values = ', '.join(':' + name for name in row)
    db.execute(f'INSERT INTO {config.table(table)} ({columns}) VALUES ({values})', row)


def get_one(db, config, table, identifier):
    rows = db.execute(f'SELECT * FROM {config.table(table)} WHERE id = :id', {'id': identifier})
    if len(rows) != 1:
        raise ValueError(f'Expected one {table} record; found {len(rows)}')
    return rows[0]
