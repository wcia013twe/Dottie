"""API-only native Databricks App, using Agent Bricks' supported custom-server deployment.

Managed Runtime Store is unavailable on this workspace tier. This foreground endpoint intentionally
has no background runs, implicit memory or restart durability. Every request is self-contained.
"""
import asyncio
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


def main():
    uvicorn.run('runtime.main:app',host='0.0.0.0',port=int(os.getenv('DATABRICKS_APP_PORT',os.getenv('PORT','8000'))))


if __name__ == '__main__':
    main()
