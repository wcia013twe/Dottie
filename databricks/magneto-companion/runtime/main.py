"""API-only native Databricks App for the Magneto Personal Intelligence companion.

Stateless and self-contained: every request carries a full companion snapshot
and the current MCP tool schemas. There are no background runs, no memory, and
no physical effects.
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
from agent.plan import ContractError, validate_snapshot
from runtime.adapter import invoke

load_dotenv(dotenv_path=Path(__file__).parent.parent / '.env', override=False)


@asynccontextmanager
async def lifespan(app):
    configure()
    yield


app = FastAPI(title='Magneto Personal Intelligence companion', lifespan=lifespan)


@app.get('/health')
def health():
    return {'status': 'ok', 'service': 'magneto-companion', 'mode': 'foreground-stateless'}


@app.post('/api/invocations')
async def invocations(request: Request):
    if int(request.headers.get('content-length', '0')) > 65536:
        raise HTTPException(413, 'Request too large')
    try:
        body = await request.json()
        if not isinstance(body, dict) or set(body) != {'id', 'session_id', 'input'}:
            raise ContractError('Expected id, session_id and input')
        snapshot = validate_snapshot(body['input']['snapshot'])
        if body['input'].get('available_mcp_tools') is None:
            raise ContractError('Expected available_mcp_tools')
        if body['id'] != snapshot['request_id'] or body['session_id'] != snapshot['session_id']:
            raise ContractError('Invocation IDs do not match snapshot')
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(400, 'Invalid Magneto companion snapshot') from exc

    async def emit(event):
        pass  # No streaming transport or physical effects in this milestone.

    context = SimpleNamespace(invocation_id=body['id'], session_id=body['session_id'], emit=emit)
    try:
        output = await asyncio.wait_for(invoke(body['input'], context), timeout=14)
        return {'id': body['id'], 'status': 'completed', 'output': output}
    except TimeoutError as exc:
        raise HTTPException(504, 'Companion plan timed out') from exc
    except Exception as exc:
        raise HTTPException(502, 'Companion plan could not be completed') from exc


def main():
    uvicorn.run('runtime.main:app', host='0.0.0.0',
                port=int(os.getenv('DATABRICKS_APP_PORT', os.getenv('PORT', '8000'))))


if __name__ == '__main__':
    main()
