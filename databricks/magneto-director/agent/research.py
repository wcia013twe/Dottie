"""Read-only approved research retrieval; never approve, publish, or alter learner data."""
from __future__ import annotations

from collections import defaultdict
import json
import logging
import math
import os
from pathlib import Path
import re
import time
import tomllib


class RetrievalError(RuntimeError):
    """Lookup failure is distinct from a successful empty result."""


def _validator(name):
    from jsonschema import Draft202012Validator, FormatChecker
    directory = Path(__file__).with_name('research_contracts')
    if not directory.exists():
        directory = Path(__file__).resolve().parents[2] / 'contracts/v1'
    return Draft202012Validator(json.loads((directory / f'{name}.schema.json').read_text()),
                               format_checker=FormatChecker())


def request_for(snapshot):
    letter = snapshot['current_passage']['letter']
    events = [e for e in snapshot['events'] if e['target_letter'] == letter]
    tags = ['recognition']
    response = events[-1]['response'] if events else None
    if response == 'incorrect':
        tags.append('incorrect_response')
    elif response == 'help':
        tags.append('help_requested')
    request = {'schema_version': '1.0', 'request_id': snapshot['request_id'],
               'target_letter': letter, 'difficulty_tags': tags, 'limit': 3,
               'query': f"Brief tactile braille {letter} recognition using the current "
                        f"{snapshot['current_passage']['word']} opportunity; "
                        f"latest target-letter response: {response or 'none'}."}
    _validator('retrieval-request').validate(request)
    return request


def validate_result(result, request):
    try:
        _validator('retrieval-result').validate(result)
        if result['request_id'] != request['request_id']:
            raise ValueError('Mismatched retrieval request')
        seen, previous = set(), math.inf
        if len(result['matches']) > request['limit']:
            raise ValueError('Too many guidance matches')
        for match in result['matches']:
            score = match['relevance_score']
            if isinstance(score, bool) or not math.isfinite(score) or score > previous:
                raise ValueError('Invalid relevance ordering')
            if match['guidance_id'] in seen:
                raise ValueError('Duplicate guidance')
            if request['target_letter'] not in match['target_letters']:
                raise ValueError('Guidance does not apply to the current letter')
            if not set(request['difficulty_tags']) & set(match['difficulty_tags']):
                raise ValueError('Guidance does not apply to the practice context')
            seen.add(match['guidance_id']); previous = score
        return result
    except Exception as exc:
        raise RetrievalError('Invalid approved research response') from exc


class DatabricksResearchRetriever:
    """AI Search candidates rechecked against current Delta eligibility, in one SQL read."""
    def __init__(self, config, client):
        self.client, self.config = client, config
        names = [config['catalog'], config['schema'], config['table_prefix']]
        index = config['search_index']
        if any(not re.fullmatch('[a-z][a-z0-9_]*', n) for n in names):
            raise ValueError('Invalid research identifiers')
        if (not re.fullmatch('[a-z][a-z0-9_]*\\.[a-z][a-z0-9_]*\\.[a-z][a-z0-9_]*', index)
                or not index.startswith('.'.join(names[:2]) + '.')):
            raise ValueError('Invalid research index')
        if client.config.host.rstrip('/') != config['workspace_host'].rstrip('/'):
            raise ValueError('Research workspace differs from authenticated workspace')
        self.prefix = '.'.join(names[:2]) + '.' + names[2] + '_'

    def _rows(self, statement, params):
        from databricks.sdk.service.sql import StatementParameterListItem
        api = self.client.statement_execution
        response = api.execute_statement(statement, self.config['warehouse_id'], wait_timeout='0s',
            parameters=[StatementParameterListItem(name=k, value=v) for k, v in params.items()])
        deadline = time.monotonic() + 4
        while response.status.state.value in {'PENDING', 'RUNNING'}:
            if time.monotonic() >= deadline:
                api.cancel_execution(response.statement_id)
                raise RetrievalError('Research eligibility query timed out')
            time.sleep(.1)
            response = api.get_statement(response.statement_id)
        if response.status.state.value != 'SUCCEEDED' or not response.manifest or response.manifest.truncated:
            raise RetrievalError('Research eligibility query failed or was truncated')
        if not response.result:
            raise RetrievalError('Research eligibility query returned no result envelope')
        columns = [c.name for c in response.manifest.schema.columns]
        rows, result = [], response.result
        while result:
            for row in result.data_array or []:
                if len(row) != len(columns):
                    raise RetrievalError('Malformed SQL result row')
                rows.append(dict(zip(columns, row)))
            if result.next_chunk_index is None:
                break
            result = api.get_statement_result_chunk_n(response.statement_id, result.next_chunk_index)
        return rows

    def __call__(self, request):
        _validator('retrieval-request').validate(request)
        try:
            response = self.client.vector_search_indexes.query_index(
                self.config['search_index'], columns=['id', 'kind'], query_text=request['query'],
                query_type='HYBRID', filters_json=json.dumps({'collection': 'teaching', 'tier': 'approved'}),
                num_results=request['limit'] * 4).as_dict()
            columns = [c['name'] for c in response['manifest']['columns']]
            if not {'id', 'kind', 'score'} <= set(columns):
                raise RetrievalError('Malformed research search response')
            ranked = {}
            for values in response['result'].get('data_array', []):
                if len(values) != len(columns):
                    raise RetrievalError('Malformed research search row')
                hit = dict(zip(columns, values)); score = float(hit['score'])
                if hit['kind'] != 'recommendation' or not math.isfinite(score):
                    raise RetrievalError('Unexpected research search candidate')
                ranked[hit['id']] = max(score, ranked.get(hit['id'], -math.inf))
            groups = defaultdict(list)
            if ranked:
                # Both views revalidate human approval, source withdrawal/expiry and dependencies.
                rows = self._rows(f'''SELECT r.id, r.body, f.source_version, f.source_id,
                    f.title, f.uri, f.locator FROM {self.prefix}eligible_recommendations r
                    JOIN {self.prefix}eligible_findings f
                    ON array_contains(from_json(get_json_object(r.body, '$.finding_ids'),
                        'ARRAY<STRING>'), f.id)
                    WHERE r.collection = 'teaching'
                    AND array_contains(from_json(:ids, 'ARRAY<STRING>'), r.id)''',
                    {'ids': json.dumps(list(ranked))})
                for row in rows:
                    groups[row['id']].append(row)
            matches = []
            for identifier, score in sorted(ranked.items(), key=lambda x: x[1], reverse=True):
                rows = groups.get(identifier, [])
                if not rows:  # A stale index hit can never bypass the current eligibility views.
                    continue
                if len({row['source_version'] for row in rows}) != 1:
                    continue  # v1 has one source; do not invent a citation for multi-source synthesis.
                row = rows[0]; body = json.loads(row['body'])
                if request['target_letter'] not in body['target_letters']:
                    continue
                if not set(request['difficulty_tags']) & set(body['difficulty_tags']):
                    continue
                matches.append({'schema_version': '1.0', 'guidance_id': identifier,
                    'text': body['text'], 'target_letters': body['target_letters'],
                    'difficulty_tags': body['difficulty_tags'], 'source_id': row['source_id'],
                    'citation': {'title': row['title'], 'uri': row['uri'],
                                 'locator': '; '.join(sorted({r['locator'] for r in rows}))},
                    'approved': True, 'relevance_score': score})
                if len(matches) == request['limit']:
                    break
            return validate_result({'schema_version': '1.0', 'request_id': request['request_id'],
                                    'matches': matches}, request)
        except RetrievalError:
            raise
        except Exception as exc:
            raise RetrievalError('Approved teaching research lookup failed') from exc


def configured_retriever():
    enabled = os.getenv('MAGNETO_RESEARCH_ENABLED', '0')
    if enabled not in {'0', '1'}:
        raise RetrievalError('MAGNETO_RESEARCH_ENABLED must be 0 or 1')
    if enabled == '0':
        return None
    from magneto_platform import ServiceConfig, Services
    root = Path(__file__).resolve().parents[1]
    with open(os.getenv('MAGNETO_RESEARCH_CONFIG', str(root / 'research.toml')), 'rb') as source:
        config = tomllib.load(source)
    services = Services(ServiceConfig.load(os.getenv('MAGNETO_SERVICES_CONFIG', str(root / 'services.toml'))))
    return DatabricksResearchRetriever(config, services.client)


def record_retrieval(result):
    """Record evidence supplied to the model, not an assertion that it caused the decision."""
    import mlflow
    span = mlflow.get_current_active_span()
    if span is not None:
        span.set_attributes({'research.request_id': result['request_id'],
                             'research.approved_guidance': json.dumps(result)})
    else:
        logging.getLogger(__name__).info('Approved teaching retrieval: %s', json.dumps(result))
