"""Same-origin browser camera frames -> isolated local recognition worker."""
import atexit
import base64
import json
import os
from pathlib import Path
import select
import subprocess
import threading

ROOT = Path(__file__).resolve().parents[1]
MAX_BODY = 1500000
_lock = threading.Lock()
_worker = None


def close_worker():
    global _worker
    if _worker is not None:
        _worker.kill()
        _worker.wait()
        _worker.stdin.close()
        _worker.stdout.close()
        _worker = None


atexit.register(close_worker)


def validate(payload):
    if not isinstance(payload, dict) or set(payload) != {'jpeg'} or not isinstance(payload['jpeg'], str):
        raise ValueError('Send a JPEG camera frame.')
    try:
        raw = base64.b64decode(payload['jpeg'], validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError('Invalid camera frame encoding.') from exc
    if not 4 <= len(raw) <= 1000000 or not raw.startswith(b'\xff\xd8'):
        raise ValueError('Send a JPEG camera frame smaller than 1 MB.')
    return payload


def observe(payload):
    global _worker
    python = Path(os.environ.get('MAGNETO_CAMERA_PYTHON', str(ROOT / '.venv-camera/bin/python')))
    if not python.is_file():
        raise RuntimeError('Camera recognition needs setup. See docs/explore-camera.md.')
    if _worker is None or _worker.poll() is not None:
        close_worker()
        _worker = subprocess.Popen([str(python), '-u', str(ROOT / 'scripts/explore_worker.py')],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        _worker.stdin.write(json.dumps(payload) + '\n')
        _worker.stdin.flush()
        if not select.select([_worker.stdout], [], [], 45)[0]:
            raise RuntimeError('Recognition timed out. Try again.')
        line = _worker.stdout.readline()
        if not line:
            raise RuntimeError('Camera recognition stopped. Try again.')
        return json.loads(line)
    except Exception:
        close_worker()
        raise


def handle(handler):
    if handler.path != '/api/explore-observe':
        return False
    host = handler.headers.get('Host', '')
    origin = handler.headers.get('Origin')
    if host not in (f'127.0.0.1:{handler.server.server_port}', f'localhost:{handler.server.server_port}') or (origin and origin != 'http://' + host):
        handler._json(403, {'error': 'Same-origin localhost requests only.'})
        return True
    if handler.headers.get_content_type() != 'application/json':
        handler._json(415, {'error': 'Send application/json.'})
        return True
    try:
        length = int(handler.headers.get('Content-Length', '0'))
        if not 0 < length <= MAX_BODY:
            handler._json(413, {'error': 'Camera frame is too large.'})
            return True
        handler.connection.settimeout(5)
        payload = validate(json.loads(handler.rfile.read(length)))
    except (ValueError, TimeoutError, OSError):
        handler._json(400, {'error': 'Invalid JPEG camera request.'})
        return True
    if not _lock.acquire(blocking=False):
        handler._json(409, {'error': 'Recognition is busy. Try again shortly.'})
        return True
    try:
        result = observe(payload)
        handler._json(503 if 'error' in result else 200, result)
    except Exception as exc:
        handler._json(503, {'error': str(exc) if isinstance(exc, RuntimeError) else 'Camera recognition is unavailable. Try again.'})
    finally:
        _lock.release()
    return True
