"""Configuration adapter only. All transport and hardware lives in harness devices/."""
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'orin-harness'))
from magneto_harness.devices.nano_story import LocalStoryCell, NanoStoryCell

USB=LocalStoryCell()
NANO=NanoStoryCell()


def settings():
    path=ROOT/'.local/device-connections.json'
    try:data=json.loads(path.read_text()) if path.exists() else {}
    except (OSError,ValueError):return {}
    if not isinstance(data,dict):return {}
    for key,env in [('nano_ssh','MAGNETO_NANO_SSH'),('nano_repository','MAGNETO_NANO_REPOSITORY'),('cell_port','MAGNETO_STORY_CELL_PORT'),('story_cell_transport','MAGNETO_STORY_CELL_TRANSPORT')]:
        if os.environ.get(env):data[key]=os.environ[env]
    return data


def send(operation,target=''):
    config=settings()
    if config.get('story_cell_transport')=='usb':return USB.send(config,operation,target)
    if config.get('story_cell_transport')=='ssh':return NANO.send(config,operation,target)
    return {'connected':False,'ready':False,'state':'not_configured','message':'Braille connection not configured. Choose USB on this host or a Nano connection.'}
