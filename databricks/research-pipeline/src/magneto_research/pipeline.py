"""Explicit paper-first operations. Model output never performs a review action."""
from contextlib import contextmanager
from datetime import datetime, timezone
import io
import json
import math
from pathlib import Path
from uuid import uuid4

from .evidence import (COLLECTIONS, EXTRACTION_INSTRUCTIONS, EXTRACTION_SCHEMA,
                       EXTRACTION_VERSION, digest, encoded, extracted_findings,
                       guidance_v1, prepared_chunks, recommendation, require_text, source_metadata)
from .storage import get_one, insert, refresh_search


def now():
    return datetime.now(timezone.utc).isoformat()


class Pipeline:
    def __init__(self, config, client, db, actor, experiment_id=None):
        if config.experiment_name and not experiment_id:
            raise ValueError('Configure updater tracking before operational processing')
        self.config, self.client, self.db = config, client, db
        self.actor = require_text(actor, 'authenticated actor')
        self.experiment_id = experiment_id

    def get(self, table, identifier):
        return get_one(self.db, self.config, table, identifier)

    def put(self, table, row):
        insert(self.db, self.config, table, row)

    def artifact(self, run_id, filename, value):
        path = f'{self.config.volume_path}/runs/{run_id}/{filename}.json'
        self.client.files.upload(path, io.BytesIO(encoded(value).encode()), overwrite=False)
        return path

    @contextmanager
    def run(self, operation, subject_id, details=None):
        run_id = str(uuid4())
        details = {**(details or {}), 'artifact_directory': f'{self.config.volume_path}/runs/{run_id}'}
        from .tracking import tracked_operation
        with tracked_operation(self.experiment_id, operation, run_id, subject_id) as tracking:
            details.update(tracking)
            self.put('runs', {'id': run_id, 'subject_id': subject_id, 'operation': operation,
                             'status': 'started', 'details': encoded(details),
                             'created_at': now(), 'actor': self.actor})
            try:
                yield run_id
            except Exception as exc:
                self.db.execute(f'UPDATE {self.config.table("runs")} SET status = :status, '
                                'details = :details WHERE id = :id',
                                {'status': 'failed', 'details': encoded({'error_type': type(exc).__name__,
                                 'initial': details or {}}), 'id': run_id})
                raise
            else:
                self.db.execute(f'UPDATE {self.config.table("runs")} SET status = :status WHERE id = :id',
                                {'status': 'completed', 'id': run_id})

    def ingest(self, path, metadata):
        metadata = source_metadata(metadata)
        path = Path(path)
        if path.suffix.lower() != '.pdf':
            raise ValueError('Initial intake supports PDF sources; preserve HTML/tables as separate follow-on work')
        if path.stat().st_size > 100 * 1024 * 1024:
            raise ValueError('PDF exceeds the managed parser 100 MB limit')
        raw = path.read_bytes()
        if not raw.startswith(b'%PDF-'):
            raise ValueError('Input is not a PDF')
        sha = digest(raw)
        version = digest({'sha256': sha, 'metadata': metadata})
        existing = self.db.execute(f'SELECT id FROM {self.config.table("sources")} WHERE id = :id',
                                   {'id': version})
        if existing:
            return {'source_version': version, 'status': 'already_registered'}
        target = f'{self.config.volume_path}/sources/{version}/source.pdf'
        with self.run('ingest', version, {'sha256': sha}):
            # Content-addressed path: safe recovery after upload succeeded but registry write failed.
            from databricks.sdk.errors import ResourceAlreadyExists
            try:
                self.client.files.upload(target, io.BytesIO(raw), overwrite=False)
            except ResourceAlreadyExists:
                downloaded = self.client.files.download(target).contents.read()
                if digest(downloaded) != sha:
                    raise ValueError('Existing immutable source has a different checksum')
            self.put('sources', {'id': version, 'source_id': metadata['source_id'],
                     'collection': metadata['collection'], 'title': metadata['title'],
                     'uri': metadata['uri'], 'sha256': sha, 'volume_path': target,
                     'metadata': encoded(metadata), 'valid_until': metadata['valid_until'],
                     'created_at': now(), 'actor': self.actor})
        return {'source_version': version, 'status': 'registered'}

    def process(self, source_version):
        source = self.get('sources', source_version)
        with self.run('parse_and_prepare', source_version,
                      {'parser_schema': '2.0', 'prep': 'ai_prep_search', 'sha256': source['sha256']}) as run_id:
            rows = self.db.execute('SELECT sha2(content, 256) sha256, '
                "to_json(ai_parse_document(content, map('version', '2.0', 'descriptionElementTypes', ''))) output "
                "FROM read_files(:path, format => 'binaryFile')", {'path': source['volume_path']})
            if len(rows) != 1 or rows[0]['sha256'] != source['sha256']:
                raise ValueError('Original source checksum changed')
            parsed = json.loads(rows[0]['output'])
            self.artifact(run_id, 'parsed', parsed)
            if parsed.get('error_status'):
                raise ValueError('Partial parsing; inspect saved parsed artifact')
            rows = self.db.execute('SELECT to_json(ai_prep_search(parse_json(:parsed))) output',
                                   {'parsed': encoded(parsed)})
            prepared = json.loads(rows[0]['output'])
            self.artifact(run_id, 'prepared', prepared)
            chunks = prepared_chunks(parsed, prepared)
            for position, chunk in enumerate(chunks):
                self.put('chunks', {'id': digest([run_id, position]), 'source_version': source_version,
                         'run_id': run_id, 'text': chunk['text'], 'embedding_text': chunk['embedding_text'],
                         'locator': chunk['locator'], 'pages': encoded(chunk['page_ids'])})
        return {'run_id': run_id, 'passages': len(chunks), 'status': 'completed'}

    def extract(self, chunk_id):
        chunk = self.get('eligible_chunks', chunk_id)
        with self.run('extract', chunk_id, {'prompt_version': EXTRACTION_VERSION,
                      'prompt_sha256': digest(EXTRACTION_INSTRUCTIONS), 'function_schema': '2.0',
                      'model': 'Databricks-managed; underlying revision not exposed'}) as run_id:
            rows = self.db.execute("SELECT to_json(ai_extract(:text, :schema, map('version', '2.0', "
                "'instructions', :instructions))) output", {'text': chunk['text'],
                'schema': encoded(EXTRACTION_SCHEMA), 'instructions': EXTRACTION_INSTRUCTIONS})
            result = json.loads(rows[0]['output'])
            self.artifact(run_id, 'extraction', result)
            response = result.get('response') if isinstance(result, dict) else None
            candidates = response.get('findings') if isinstance(response, dict) else None
            if not isinstance(result, dict) or result.get('error_message') or not isinstance(candidates, list):
                raise ValueError('Extraction failed or returned malformed findings')
            findings, rejected = [], []
            for n, candidate in enumerate(candidates):
                try:
                    findings.extend(extracted_findings({'response': {'findings': [candidate]}}, chunk['text']))
                except (ValueError, TypeError) as exc:
                    rejected.append({'candidate_position': n, 'reason': str(exc)})
            self.artifact(run_id, 'validation', {'accepted_candidates': len(findings), 'rejected': rejected})
            if candidates and not findings:
                raise ValueError('No candidate quote resolved to the source; inspect validation artifact')
            ids = []
            for n, finding in enumerate(findings):
                identifier = digest([run_id, n])
                self.put('findings', {'id': identifier, 'chunk_id': chunk_id,
                                     'run_id': run_id, 'body': encoded(finding)})
                ids.append(identifier)
        return {'run_id': run_id, 'finding_ids': ids, 'review_status': 'needs_review',
                'rejected_candidates': len(rejected)}

    def draft(self, body):
        body = recommendation(body)
        findings = [self.get('eligible_findings', i) for i in body['finding_ids']]
        collections = {f['collection'] for f in findings}
        if len(collections) != 1:
            raise ValueError('Recommendations cannot mix teaching and industry evidence')
        collection = collections.pop()
        if collection == 'industry' and (body['target_letters'] or body['difficulty_tags']):
            raise ValueError('Industry implications cannot carry teaching tags')
        identifier = str(uuid4())
        self.put('recommendations', {'id': identifier, 'collection': collection, 'body': encoded(body),
                                     'created_at': now(), 'actor': self.actor})
        return {'recommendation_id': identifier, 'review_status': 'draft'}

    def review(self, kind, identifier, action, rationale):
        allowed = {'source': ('sources', {'active', 'withdrawn'}),
                   'finding': ('findings', {'accepted', 'rejected'}),
                   'recommendation': ('recommendations', {'approved', 'rejected'})}
        if kind not in allowed or action not in allowed[kind][1]:
            raise ValueError('Invalid review action')
        require_text(rationale, 'review rationale')
        row = self.get(allowed[kind][0], identifier)
        if kind == 'finding' and action == 'accepted':
            chunk = self.get('eligible_chunks', row['chunk_id'])
            if self.get('runs', row['run_id'])['status'] != 'completed':
                raise ValueError('Cannot accept output from an incomplete run')
            extracted_findings({'response': {'findings': [json.loads(row['body'])]}}, chunk['text'])
        if kind == 'recommendation' and action == 'approved':
            body = recommendation(json.loads(row['body']))
            for finding_id in body['finding_ids']:
                self.get('eligible_findings', finding_id)
        event_id = str(uuid4())
        self.put('reviews', {'id': event_id, 'subject_id': identifier, 'action': action,
                            'rationale': rationale, 'created_at': now(), 'actor': self.actor})
        return {'review_id': event_id, 'action': action}

    def audit(self, kind, identifier):
        if kind == 'recommendation':
            row = self.get('recommendations', identifier)
            row['body'] = json.loads(row['body'])
            row['evidence'] = [self.audit('finding', i) for i in row['body']['finding_ids']]
        elif kind == 'finding':
            row = self.get('findings', identifier)
            row['body'] = json.loads(row['body'])
            row['evidence'] = self.audit('passage', row['chunk_id'])
        elif kind == 'passage':
            row = self.get('chunks', identifier)
            row['source'] = self.get('sources', row['source_version'])
        elif kind == 'source':
            row = self.get('sources', identifier)
        else:
            raise ValueError('Unknown audit record kind')
        row['reviews'] = self.db.execute(f'SELECT * FROM {self.config.table("reviews")} '
            'WHERE subject_id = :id ORDER BY created_at, id', {'id': identifier})
        row['runs'] = self.db.execute(f'SELECT * FROM {self.config.table("runs")} '
            'WHERE subject_id = :id ORDER BY created_at, id', {'id': identifier})
        if 'run_id' in row:
            row['produced_by'] = self.get('runs', row['run_id'])
        return row

    def export(self, identifier):
        row = self.get('eligible_recommendations', identifier)
        row['body'] = json.loads(row['body'])
        findings = [self.get('eligible_findings', i) for i in row['body']['finding_ids']]
        sources = {f['source_version']: json.loads(f['metadata']) for f in findings}
        return guidance_v1(row, list(sources.values()), [f['locator'] for f in findings])

    def publish(self):
        with self.run('publish', 'domain_library') as run_id:
            refresh_search(self.db, self.config)
            if self.config.search_index:
                self.client.vector_search_indexes.sync_index(self.config.search_index)
        return {'run_id': run_id, 'status': 'table_refreshed', 'index_status':
                'sync_requested' if self.config.search_index else 'not_configured'}

    def search(self, query, collection, tier='reviewed', limit=5):
        require_text(query, 'query')
        if collection not in COLLECTIONS or tier not in {'library', 'reviewed', 'approved'}:
            raise ValueError('Invalid collection or tier')
        if type(limit) is not int or not 1 <= limit <= 20:
            raise ValueError('limit must be between 1 and 20')
        if not self.config.search_index:
            raise ValueError('Configure a research AI Search index')
        with self.run('search', collection, {'query': query, 'tier': tier, 'limit': limit}) as run_id:
            response = self.client.vector_search_indexes.query_index(
                self.config.search_index, columns=['id', 'kind'], query_text=query,
                query_type='HYBRID', filters_json=encoded({'collection': collection, 'tier': tier}),
                num_results=min(200, limit * 4)).as_dict()
            self.artifact(run_id, 'retrieval', response)
            if 'result' not in response or 'manifest' not in response:
                raise RuntimeError('Malformed search response')
            names = [c['name'] for c in response['manifest']['columns']]
            if not {'id', 'kind', 'score'} <= set(names):
                raise RuntimeError('Search response is missing required columns')
            ranked = []
            for values in response['result'].get('data_array', []):
                hit = dict(zip(names, values))
                score = float(hit['score'])
                if not math.isfinite(score):
                    raise RuntimeError('Nonfinite search score')
                ranked.append({**hit, 'score': score})
            ranked.sort(key=lambda h: h['score'], reverse=True)
            params = {'ids': encoded([h['id'] for h in ranked]), 'collection': collection, 'tier': tier}
            # One current-status SQL read for the whole candidate set, not a query per hit.
            if tier == 'library':
                rows = self.db.execute(f'''SELECT c.id, c.source_version, c.run_id, c.text,
                    c.locator, c.pages, to_json(struct(s.*)) source, to_json(struct(r.*)) produced_by
                    FROM {self.config.table('eligible_chunks')} c
                    JOIN {self.config.table('sources')} s ON c.source_version = s.id
                    JOIN {self.config.table('runs')} r ON c.run_id = r.id
                    WHERE c.collection = :collection
                    AND array_contains(from_json(:ids, 'ARRAY<STRING>'), c.id)''',
                    {'ids': params['ids'], 'collection': collection})
                current = {r['id']: {**r, 'source': json.loads(r['source']),
                            'produced_by': json.loads(r['produced_by'])} for r in rows}
            else:
                rows = self.db.execute(f'SELECT id, kind FROM {self.config.table("eligible_documents")} '
                    "WHERE array_contains(from_json(:ids, 'ARRAY<STRING>'), id) "
                    'AND collection = :collection AND tier = :tier', params)
                current = {r['id']: r for r in rows}
            matches, seen = [], set()
            for hit in ranked:
                if hit['id'] in seen:
                    continue
                # Authoritative Delta eligibility beats stale copies in a syncing index.
                if hit['id'] not in current:
                    continue
                seen.add(hit['id'])
                record = current[hit['id']] if tier == 'library' else self.audit(current[hit['id']]['kind'], hit['id'])
                matches.append({'score': hit['score'], 'record': record})
                if len(matches) >= limit:
                    break
            self.artifact(run_id, 'returned_evidence', matches)
        return {'run_id': run_id, 'collection': collection, 'tier': tier, 'matches': matches}

    def create_index(self):
        from databricks.sdk.service.vectorsearch import (
            DeltaSyncVectorIndexSpecRequest, EmbeddingSourceColumn, PipelineType, VectorIndexType)
        c = self.config
        if not all([c.search_index, c.search_endpoint, c.embedding_endpoint]):
            raise ValueError('Configure index, existing STANDARD endpoint and embedding endpoint')
        endpoint = self.client.vector_search_endpoints.get_endpoint(c.search_endpoint)
        if endpoint.endpoint_type.value != 'STANDARD':
            raise ValueError('This adapter uses STANDARD endpoint filter syntax')
        self.client.vector_search_indexes.create_index(
            c.search_index, c.search_endpoint, 'id', VectorIndexType.DELTA_SYNC,
            delta_sync_index_spec=DeltaSyncVectorIndexSpecRequest(
                source_table=c.table('search_documents'), pipeline_type=PipelineType.TRIGGERED,
                embedding_source_columns=[EmbeddingSourceColumn(
                    name='embedding_text', embedding_model_endpoint_name=c.embedding_endpoint)]))
        return {'index': c.search_index, 'status': 'creation_requested'}
