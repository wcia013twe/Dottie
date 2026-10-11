"""Trusted SSH transport for validated Story targets. Physical effects remain in devices/."""
import json
import select
import shlex
import subprocess
import threading
from pathlib import PurePosixPath
from uuid import uuid4

from .nano_status import TARGET, probe


class NanoStoryCell:
    def __init__(self):
        self.process=None
        self.key=None
        self.lock=threading.Lock()

    def send(self, settings, operation, target=''):
        with self.lock:
            from .story_cell import validate
            try:validate({'command_id':str(uuid4()),'operation':operation,'target':target})
            except (ValueError,TypeError):return {'connected':False,'ready':False,'state':'invalid','message':'Invalid Braille request.'}
            host=settings.get('nano_ssh')
            root=settings.get('nano_repository')
            if not host or not root:
                return {'connected':False,'ready':False,'state':'not_configured','message':'Set the Nano SSH address and repository path to send Braille.'}
            if not isinstance(host,str) or not TARGET.fullmatch(host) or not isinstance(root,str) or not root.startswith('/') or '..' in PurePosixPath(root).parts or '\n' in root:
                return {'connected':False,'ready':False,'state':'invalid','message':'Nano connection settings are invalid.'}
            key=(host,root)
            try:
                if self.process is None or self.process.poll() is not None or self.key!=key:
                    self.close()
                    if probe(host)['state']!='connected':raise RuntimeError('identity')
                    command='cd '+shlex.quote(root)+' && PYTHONPATH=orin-harness exec .venv-harness/bin/python -m magneto_harness.devices.story_cell'
                    self.process=subprocess.Popen(['ssh','-T','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=3','-o','ClearAllForwardings=yes','-o','ControlMaster=no','-o','ControlPath=none',host,command],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,bufsize=1)
                    self.key=key
                command_id=str(uuid4())
                self.process.stdin.write(json.dumps({'command_id':command_id,'operation':operation,'target':target})+'\n');self.process.stdin.flush()
                if not select.select([self.process.stdout],[],[],12)[0]:raise TimeoutError('receipt')
                result=json.loads(self.process.stdout.readline())
                if result.get('command_id')!=command_id or result.get('cell_ack') is not True:raise RuntimeError('receipt')
                return {'connected':True,'ready':True,'state':'acknowledged','message':'Nano cell acknowledged '+('clear' if operation=='clear' else target.upper()),**result}
            except Exception:
                self.close()
                return {'connected':False,'ready':False,'state':'unavailable','message':'Nano cell did not acknowledge. Check SSH, the receiver environment, and the serial cell. No automatic replay.'}

    def close(self):
        if self.process:
            try:self.process.stdin.close()
            except (OSError,AttributeError):pass
            try:self.process.wait(timeout=1)
            except subprocess.TimeoutExpired:self.process.terminate()
        self.process=None;self.key=None


class LocalStoryCell:
    """USB serial on the machine running the story server (including the Nano)."""
    def __init__(self):
        self.cell=None
        self.port=None
        self.lock=threading.Lock()

    def send(self, settings, operation, target=''):
        from .story_cell import AcknowledgedCell
        with self.lock:
            from .story_cell import validate
            try:validate({'command_id':str(uuid4()),'operation':operation,'target':target})
            except (ValueError,TypeError):return {'connected':False,'ready':False,'state':'invalid','message':'Invalid Braille request.'}
            port=settings.get('cell_port')
            if not port:
                return {'connected':False,'ready':False,'state':'not_configured','message':'Connect the USB Braille controller and configure its serial port.'}
            try:
                if self.cell is None or self.port!=port:
                    if self.cell:self.cell.close()
                    self.cell=AcknowledgedCell(port);self.port=port
                result=self.cell.execute({'command_id':str(uuid4()),'operation':operation,'target':target})
                return {'connected':True,'ready':True,'state':'acknowledged','message':'USB cell acknowledged '+('clear' if operation=='clear' else target.upper()),**result}
            except Exception:
                if self.cell:
                    try:self.cell.close()
                    except Exception:pass
                self.cell=None
                return {'connected':False,'ready':False,'state':'unavailable','message':'USB cell did not acknowledge. Check its port, firmware and power. No automatic replay.'}
