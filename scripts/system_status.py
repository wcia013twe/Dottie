"""Read-only Databricks metadata probe for the local system map."""
import json
from pathlib import Path
import subprocess
import threading

ROOT = Path(__file__).resolve().parents[1]
KEYS = ('catalog', 'schema', 'references', 'director', 'companion', 'model',
        'director_traces', 'research_traces', 'warehouse', 'search_endpoint',
        'search_index', 'embeddings', 'learner_bronze', 'learner_evidence', 'learner_gold')
_pending = threading.Lock()


def probe():
    result = subprocess.run([str(ROOT / '.venv-agent/bin/python'),
                             str(ROOT / 'scripts/system_probe.py')],
                            capture_output=True, text=True, timeout=45)
    if result.returncode:
        raise RuntimeError('Metadata probe could not start. Check the local Databricks environment and login.')
    payload = json.loads(result.stdout)
    # Only bounded status values reach the browser; never upstream bodies or errors.
    return {key: {'status': payload.get(key, {}).get('status')
                  if payload.get(key, {}).get('status') in ('reachable', 'unavailable')
                  else 'unavailable'} for key in KEYS}


def handle(handler):
    if handler.path != '/api/system-status':
        return False
    host = handler.headers.get('Host', '')
    if host not in (f'127.0.0.1:{handler.server.server_port}', f'localhost:{handler.server.server_port}'):
        handler._json(403, {'error': 'Local requests only.'})
        return True
    if handler.headers.get('Origin') not in (None, 'http://' + host):
        handler._json(403, {'error': 'Same-origin requests only.'})
        return True
    try:
        length = int(handler.headers.get('Content-Length', '0'))
        if handler.headers.get_content_type() != 'application/json' or not 0 < length <= 64:
            raise ValueError()
        handler.connection.settimeout(5)
        if json.loads(handler.rfile.read(length)) != {}:
            raise ValueError()
    except (ValueError, OSError):
        handler._json(400, {'error': 'Send an empty JSON object.'})
        return True
    if not _pending.acquire(blocking=False):
        handler._json(409, {'error': 'A metadata check is already running.'})
        return True
    try:
        handler._json(200, {'resources': probe()})
    except subprocess.TimeoutExpired:
        handler._json(504, {'error': 'Metadata check timed out. Access remains unchecked.'})
    except Exception:
        handler._json(503, {'error': 'Metadata check unavailable. Check the local Databricks environment and login.'})
    finally:
        _pending.release()
    return True
