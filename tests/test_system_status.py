import json
from pathlib import Path
import subprocess
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from functools import partial
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import system_status
import serve


class SystemStatusTests(unittest.TestCase):
    def test_only_allowlisted_statuses_are_exposed(self):
        raw = {'model': {'status': 'reachable', 'token': 'secret'},
               'director': {'status': 'secret'}, 'other': {'status': 'reachable'}}
        with patch.object(system_status.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout=json.dumps(raw))):
            result = system_status.probe()
        self.assertEqual(result['model'], {'status': 'reachable'})
        self.assertEqual(result['director'], {'status': 'unavailable'})
        self.assertNotIn('secret', json.dumps(result))
        self.assertNotIn('other', result)

    def test_upstream_stderr_is_not_exposed(self):
        with patch.object(system_status.subprocess, 'run', return_value=SimpleNamespace(returncode=1, stdout='', stderr='secret')):
            with self.assertRaises(RuntimeError) as caught:
                system_status.probe()
        self.assertNotIn('secret', str(caught.exception))

    def test_http_origin_deadline_and_busy_boundaries(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), partial(serve.Handler, directory=str(serve.WEB)))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def post(origin=None):
            headers = {'Content-Type': 'application/json'}
            if origin: headers['Origin'] = origin
            try:
                with urlopen(Request(f'http://127.0.0.1:{server.server_port}/api/system-status', data=b'{}', headers=headers), timeout=2) as response:
                    return response.status, json.load(response)
            except HTTPError as error:
                with error: return error.code, json.load(error)
        try:
            with patch.object(system_status, 'probe', return_value={'model': {'status': 'reachable'}}) as probe:
                self.assertEqual(post('https://other.example')[0], 403)
                probe.assert_not_called()
                self.assertEqual(post()[1]['resources']['model']['status'], 'reachable')
            with patch.object(system_status, 'probe', side_effect=subprocess.TimeoutExpired('probe', 45)):
                self.assertEqual(post()[0], 504)
            system_status._pending.acquire()
            try: self.assertEqual(post()[0], 409)
            finally: system_status._pending.release()
        finally:
            server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__':
    unittest.main()
