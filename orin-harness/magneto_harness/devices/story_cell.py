"""Bounded Story cell receiver on the Nano. No model, grading, or console fallback."""
import json
import re
import select
import sys
import time
from uuid import UUID

from .. import paths  # wire cane_vision imports
from cane_vision.braille import LETTERS


def validate(request):
    if not isinstance(request, dict) or set(request) != {'command_id','operation','target'}:
        raise ValueError('Invalid cell request')
    if str(UUID(request['command_id'])) != request['command_id']:
        raise ValueError('Invalid command identity')
    if request['operation'] not in ('show','clear'):
        raise ValueError('Unknown cell operation')
    target = request['target']
    if not isinstance(target,str) or (request['operation']=='show' and not re.fullmatch('[a-z]{1,16}',target)) or (request['operation']=='clear' and target!=''):
        raise ValueError('Invalid cell target')
    return request


class AcknowledgedCell:
    def __init__(self, port, baud=115200):
        import serial
        # Fail if another harness owns the serial port. Never fall back to a preview.
        self.serial = serial.Serial(port,baud,timeout=.1,exclusive=True)
        try:
            self.serial.reset_input_buffer()
            # Opening an Uno resets it; wait for boot before sending anything.
            # Already-running boards may have emitted READY before we opened.
            try:
                self.expect(lambda line:line.startswith('READY magneto-cell '),2.5)
            except TimeoutError:
                pass
            self.write('PING')
            self.expect(lambda line:line.startswith('PONG magneto-cell '),2)
            self.expect(lambda line:line=='OK',2)
            self.write('TIMING 1500 300 1000')
            self.expect(lambda line:line=='OK',2)
        except Exception:
            self.serial.close()
            raise

    def write(self, command):
        self.serial.write((command+'\n').encode('ascii'))
        self.serial.flush()

    def expect(self, matches, timeout):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            line=self.serial.readline().decode('ascii','replace').strip()
            if line.startswith('ERR'):raise RuntimeError('Cell rejected the command')
            if matches(line):return line
        raise TimeoutError('No matching device acknowledgement')

    def execute(self, request):
        validate(request)
        target=request['target']
        mask=0 if request['operation']=='clear' else LETTERS[target[0]]
        command='CLEAR' if request['operation']=='clear' else ('DOTS '+''.join(str(i+1) for i in range(6) if mask&(1<<i)) if len(target)==1 else 'SPELL '+target)
        self.serial.reset_input_buffer()
        self.write(command)
        # OK precedes CELL for this command; an old matching mask is not an acknowledgement.
        self.expect(lambda line:line=='OK',2)
        receipt=self.expect(lambda line: bool(re.fullmatch(r'CELL [0-9A-Fa-f]{2} .',line)) and int(line.split()[1],16)==mask,2)
        return {'command_id':request['command_id'],'cell_ack':True,'command':command,'receipt':receipt,
                'sequence_started':len(target)>1,'sequence_complete':False}

    def close(self):
        try:self.write('CLEAR')
        finally:self.serial.close()


def main():
    import argparse
    import os
    parser=argparse.ArgumentParser(description='Bounded physical Story cell receiver')
    parser.add_argument('--check',action='store_true',help='Check dependencies and port access without opening or actuating the cell')
    args=parser.parse_args()
    from ..config import load_config
    from cane_vision.serial_cell import find_port
    config=load_config()
    port=config['cell']['port']
    if port=='auto':port=find_port()
    if not port or port in ('none','console'):raise RuntimeError('No physical cell configured')
    if args.check:
        accessible=os.path.exists(port) and os.access(port,os.R_OK|os.W_OK)
        print(json.dumps({'port':port,'port_accessible':accessible,'physical_ready':False,
                          'message':'Port access only; no device command or acknowledgement.'}),flush=True)
        if not accessible:raise SystemExit(1)
        return
    cell=AcknowledgedCell(port,config['cell']['baud'])
    cache={}
    try:
        while True:
            # Clear held dots and stop the receiver when the local bridge disappears or goes idle.
            if not select.select([sys.stdin],[],[],30)[0]:break
            line=sys.stdin.readline()
            if not line:break
            request=validate(json.loads(line))
            key=request['command_id']
            if key in cache:
                prior,result=cache[key]
                if prior!=request:raise ValueError('Conflicting command identity')
            else:
                try:result=cell.execute(request)
                except Exception:result={'command_id':key,'cell_ack':False,'error':'Cell acknowledgement unavailable; command may have been sent.'}
                cache[key]=(request,result)
                if len(cache)>100:break  # bounded receiver lifetime, no identity eviction/replay
            print(json.dumps(result),flush=True)
    finally:cell.close()


if __name__=='__main__':main()
