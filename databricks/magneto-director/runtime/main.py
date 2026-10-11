"""API-only native Databricks App, using Agent Bricks' supported custom-server deployment.

Managed Runtime Store is unavailable on this workspace tier. This foreground endpoint intentionally
has no background runs, implicit memory or restart durability. Every request is self-contained.
"""
import asyncio
import json
from contextlib import asynccontextmanager
import os
from pathlib import Path
from types import SimpleNamespace

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
import uvicorn

from agent.agent import configure
from agent.decision import ContractError, resolve_prompt, validate_snapshot
from runtime.adapter import invoke
from learning.store import LearningStore, StorageUnavailable, RecordConflict, ConsentRequired
from learning.contract import validate_batch, validate_attempts, validate_profile

load_dotenv(dotenv_path=Path(__file__).parent.parent / '.env', override=False)


@asynccontextmanager
async def lifespan(app):
    configure()
    # Fail startup if the serving identity cannot read the configured champion.
    # A green app status must not hide a broken registry connection.
    if os.getenv('MAGNETO_PROMPT_URI'):
        import mlflow
        def check_prompt():
            try:
                return mlflow.trace(name='story_prompt_registry_startup')(resolve_prompt)()
            finally:
                mlflow.flush_trace_async_logging()
        await asyncio.to_thread(check_prompt)
    from magneto_platform import ServiceConfig, Services
    services = Services(ServiceConfig.load(Path(__file__).resolve().parents[1] / 'services.toml'))
    app.state.learning_store = LearningStore(services) if services.config.learning_warehouse_id else None
    if app.state.learning_store:
        await asyncio.to_thread(app.state.learning_store.ensure_tables)
    yield


app = FastAPI(title='Magneto learning director', lifespan=lifespan)


@app.get('/health')
def health():
    return {'status':'ok','service':'magneto-director','mode':'foreground-stateless'}


@app.post('/api/invocations')
async def invocations(request: Request):
    if int(request.headers.get('content-length', '0')) > 32768:
        raise HTTPException(413, 'Request too large')
    try:
        body=await request.json()
        if not isinstance(body,dict) or set(body) != {'id','session_id','input'}:
            raise ContractError('Expected id, session_id and input')
        snapshot=validate_snapshot(body['input'])
        if body['id'] != snapshot['request_id'] or body['session_id'] != snapshot['session_id']:
            raise ContractError('Invocation IDs do not match snapshot')
    except (ValueError, TypeError) as exc:
        raise HTTPException(400,'Invalid Magneto snapshot') from exc
    async def emit(event):
        pass  # No streaming transport or physical effects in this milestone.
    context=SimpleNamespace(invocation_id=body['id'],session_id=body['session_id'],emit=emit)
    try:
        output=await asyncio.wait_for(invoke(snapshot,context), timeout=14)
        return {'id':body['id'],'status':'completed','output':output}
    except TimeoutError as exc:
        raise HTTPException(504,'Decision timed out') from exc
    except Exception as exc:
        # Detailed errors stay in the server trace, never in the caller's response.
        raise HTTPException(502,'Decision could not be completed') from exc


async def _learning_write(request, validator, method, *, profile_payload=False):
    store = getattr(app.state, 'learning_store', None)
    if store is None:
        raise HTTPException(503, 'Learning storage is not configured')
    try:
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > (8192 if profile_payload else 65536):
                raise HTTPException(413, 'Learning payload too large')
        payload = validator(json.loads(raw))
        profile_id = payload.get('profile_id') or payload['events'][0]['profile_id']
        if request.headers.get('x-profile-key') != profile_id:
            raise ValueError('Profile header does not match payload')
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(400, 'Invalid learning payload') from exc
    try:
        value = payload['events'] if method == 'ingest_events' else payload
        return await asyncio.to_thread(getattr(store, method), value)
    except ConsentRequired as exc:
        raise HTTPException(403, 'Learning uploads are not enabled for this profile') from exc
    except RecordConflict as exc:
        raise HTTPException(409, 'Record ID conflict; original record retained') from exc
    except Exception as exc:
        raise HTTPException(503, 'Learning storage has not confirmed this upload; retry later') from exc


@app.post('/api/learning/events')
async def learning_events(request: Request):
    return await _learning_write(request, validate_batch, 'ingest_events')


@app.post('/api/learning/attempts')
async def learning_attempts(request: Request):
    return await _learning_write(request, validate_attempts, 'ingest_attempts')


@app.post('/api/learning/profile')
async def learning_profile(request: Request):
    return await _learning_write(request, validate_profile, 'create_profile', profile_payload=True)


def main():
    uvicorn.run('runtime.main:app',host='0.0.0.0',port=int(os.getenv('DATABRICKS_APP_PORT',os.getenv('PORT','8000'))))


if __name__ == '__main__':
    main()
