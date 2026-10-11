"""Serve the static viewer and a local, same-origin Databricks decision bridge."""
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import argparse
import json
import threading
from voice_env import load_voice_env
from urllib.parse import urlparse

from decision_bridge import BridgeError, ContractError, request_decision
from learning_bridge import LearningError, create_profile, ingest_events, ingest_attempts
from story_bridge import handle as handle_story
from learner_bridge import handle as handle_learner
from system_status import handle as handle_system_status
from explore_bridge import handle as handle_explore
from nano_bridge import handle as handle_nano
from voice_bridge import handle as handle_voice
from story_narration import handle as handle_narration

WEB = Path(__file__).resolve().parents[1] / 'web'
_pending = threading.Lock()


class Handler(SimpleHTTPRequestHandler):
    def _json(self, status, value):
        body=json.dumps(value).encode()
        try:
            self.send_response(status)
            self.send_header('Content-Type','application/json')
            self.send_header('Cache-Control','no-store')
            self.send_header('Content-Length',str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass  # Navigation/cancellation must not turn a late result into another activity.

    def do_GET(self):
        if handle_nano(self): return
        if handle_learner(self): return
        super().do_GET()

    def do_POST(self):
        if handle_narration(self): return
        if handle_voice(self): return
        if handle_explore(self): return
        if handle_system_status(self): return
        if handle_story(self): return
        if self.path == '/api/learning/attempts':
            return self.do_learning_payload(ingest_attempts, 65536)
        if self.path == '/api/learning/events':
            return self.do_learning_events()
        if self.path == '/api/learning/profile':
            return self.do_learning_profile()
        if self.path != '/api/decision':
            return self._json(404,{'error':'Unknown API route.'})
        host=self.headers.get('Host','')
        if host not in (f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'):
            return self._json(403,{'error':'Local requests only.'})
        origin=self.headers.get('Origin')
        if origin and origin != 'http://'+host:
            return self._json(403,{'error':'Same-origin requests only.'})
        if self.headers.get_content_type() != 'application/json':
            return self._json(415,{'error':'Send application/json.'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0 < length <= 16384:
                return self._json(413,{'error':'Invalid request size.'})
            self.connection.settimeout(5)
            payload=json.loads(self.rfile.read(length))
        except (ValueError, TimeoutError, OSError):
            return self._json(400,{'error':'Invalid JSON request.'})
        if not _pending.acquire(blocking=False):
            return self._json(409,{'error':'A decision is already pending. Retry when it finishes.'})
        try:
            self._json(200,request_decision(payload))
        except ContractError as exc:
            self._json(400,{'error':str(exc)})
        except BridgeError as exc:
            self._json(exc.status,{'error':str(exc)})
        except Exception:
            self._json(502,{'error':'The decision service is unavailable. No activity was started.'})
        finally:
            _pending.release()

    def do_learning_events(self):
        return self.do_learning_payload(ingest_events, 65536)

    def do_learning_profile(self):
        return self.do_learning_payload(create_profile, 8192)

    def do_learning_payload(self, handler, limit):
        host=self.headers.get('Host','')
        if host not in (f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'):
            return self._json(403,{'error':'Local requests only.'})
        origin=self.headers.get('Origin')
        if origin and origin != 'http://'+host:
            return self._json(403,{'error':'Same-origin requests only.'})
        if self.headers.get_content_type() != 'application/json':
            return self._json(415,{'error':'Send application/json.'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0 < length <= limit:
                return self._json(413,{'error':'Invalid learning payload size.'})
            self.connection.settimeout(5)
            payload=json.loads(self.rfile.read(length))
            self._json(200,handler(payload))
        except (ValueError, TimeoutError, OSError):
            self._json(400,{'error':'Invalid learning payload.'})
        except LearningError as exc:
            self._json(exc.status,{'error':str(exc)})


def main():
    load_voice_env()
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=8080)
    args=parser.parse_args()
    print(f'Magneto: http://127.0.0.1:{args.port}/',flush=True)
    try:
        ThreadingHTTPServer(('127.0.0.1',args.port),partial(Handler,directory=str(WEB))).serve_forever()
    except KeyboardInterrupt:
        pass


if __name__=='__main__':
    main()
