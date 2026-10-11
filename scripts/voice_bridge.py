"""Local-only token broker. The permanent ElevenLabs key never reaches the browser."""
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

TOKEN_URL = 'https://api.elevenlabs.io/v1/single-use-token/realtime_scribe'


def create_token():
    key = os.environ.get('ELEVENLABS_API_KEY', '').strip()
    if not key:
        return 503, {'error': 'Voice needs ELEVENLABS_API_KEY in the repository-root .env or server environment. Set it and restart the server.'}
    try:
        request = Request(TOKEN_URL, data=b'', headers={'xi-api-key': key}, method='POST')
        with urlopen(request, timeout=10) as response:
            result = json.loads(response.read(16384))
        if not isinstance(result, dict):
            raise ValueError('Invalid token response')
        token = result.get('token')
        if not isinstance(token, str) or not token or len(token) > 8192:
            raise ValueError('Invalid token response')
        return 200, {'token': token}
    except HTTPError as error:
        if error.code in (401, 403):
            return 502, {'error': 'ElevenLabs rejected the server key. Check its speech-to-text access.'}
        if error.code in (402, 429):
            return 502, {'error': 'ElevenLabs voice usage is unavailable. Check quota and retry later.'}
        return 502, {'error': 'ElevenLabs voice is temporarily unavailable.'}
    except (URLError, TimeoutError, OSError, ValueError):
        return 502, {'error': 'Could not connect to ElevenLabs voice. Please try again.'}


def handle(handler):
    if handler.path != '/api/voice-token':
        return False
    host = handler.headers.get('Host', '')
    if host not in (f'127.0.0.1:{handler.server.server_port}', f'localhost:{handler.server.server_port}'):
        handler._json(403, {'error': 'Local requests only.'})
    elif handler.headers.get('Origin') != 'http://' + host:
        handler._json(403, {'error': 'Same-origin browser requests only.'})
    elif handler.headers.get_content_type() != 'application/json':
        handler._json(415, {'error': 'Send application/json.'})
    else:
        handler._json(*create_token())
    return True
