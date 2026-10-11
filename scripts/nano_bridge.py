"""Bounded localhost check of a server-configured Jetson SSH target."""
import json
import os
from pathlib import Path
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'orin-harness'))
from magneto_harness.devices.nano_status import probe

_pending = threading.Lock()


def target():
    value = os.environ.get('MAGNETO_NANO_SSH')
    if value:
        return value
    path = ROOT / '.local/device-connections.json'
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text()).get('nano_ssh')
    except (ValueError, OSError, AttributeError):
        return '!invalid!'


def handle(handler):
    if handler.path != '/api/nano-status':
        return False
    host = handler.headers.get('Host', '')
    if host not in (f'127.0.0.1:{handler.server.server_port}', f'localhost:{handler.server.server_port}') or handler.headers.get('Origin') not in (None, 'http://' + host):
        handler._json(403, {'error': 'Same-origin localhost requests only.'})
        return True
    if not _pending.acquire(blocking=False):
        handler._json(409, {'error': 'Nano check is already running.'})
        return True
    try:
        handler._json(200, probe(target()))
    finally:
        _pending.release()
    return True
