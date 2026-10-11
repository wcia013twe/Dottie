"""Same-origin ElevenLabs narration using the existing private voice settings and local cache."""
import hashlib
import json
import os
from pathlib import Path
import re
from threading import BoundedSemaphore
from urllib.request import Request,urlopen
from voice_env import load_voice_env

ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'.local/story-narration'
BUSY=BoundedSemaphore(1)

def validate(payload):
    if not isinstance(payload,dict) or set(payload)!={'text'}:raise ValueError('Send narration text only.')
    text=payload['text']
    if not isinstance(text,str) or not 1<=len(text.strip())<=3500 or '\x00' in text:raise ValueError('Invalid narration text.')
    return text.strip()

def audio(text):
    load_voice_env()
    manifest=json.loads((ROOT/'web/learn/assets/navigation-voice/manifest.json').read_text())
    voice=os.environ.get('ELEVENLABS_VOICE_ID') or manifest['voice_id']
    model=os.environ.get('ELEVENLABS_MODEL_ID') or manifest['model_id']
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',voice):raise ValueError('Invalid configured voice.')
    key=hashlib.sha256(json.dumps([voice,model,text]).encode()).hexdigest()
    path=CACHE/(key+'.wav')
    if path.exists():return path.read_bytes()
    api_key=os.environ.get('ELEVENLABS_API_KEY','').strip()
    if not api_key:raise RuntimeError('ElevenLabs key unavailable.')
    request=Request(f'https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=wav_22050',
        data=json.dumps({'text':text,'model_id':model}).encode(),
        headers={'Content-Type':'application/json','Accept':'audio/wav','xi-api-key':api_key})
    with urlopen(request,timeout=25) as response:data=response.read(12000000)
    if data[:4]!=b'RIFF' or data[8:12]!=b'WAVE':raise ValueError('Invalid narration audio.')
    CACHE.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp');tmp.write_bytes(data);tmp.replace(path)
    return data

def handle(handler):
    if handler.path!='/api/story-narration':return False
    host=handler.headers.get('Host','')
    if host not in (f'127.0.0.1:{handler.server.server_port}',f'localhost:{handler.server.server_port}') or handler.headers.get('Origin')!='http://'+host:
        handler._json(403,{'error':'Same-origin local requests only.'});return True
    try:
        if handler.headers.get_content_type()!='application/json':raise ValueError('Expected JSON.')
        size=int(handler.headers.get('Content-Length','0'))
        if not 0<size<=16000:raise ValueError('Invalid request size.')
        handler.connection.settimeout(5)
        text=validate(json.loads(handler.rfile.read(size)))
        if not BUSY.acquire(blocking=False):
            handler._json(503,{'error':'Narration is preparing. Please retry.'});return True
        try:data=audio(text)
        finally:BUSY.release()
        handler.send_response(200);handler.send_header('Content-Type','audio/wav')
        handler.send_header('Cache-Control','no-store');handler.send_header('Content-Length',str(len(data)))
        handler.end_headers();handler.wfile.write(data)
    except (ValueError,TypeError):handler._json(400,{'error':'Invalid story narration request.'})
    except (BrokenPipeError,ConnectionResetError):pass
    except Exception:handler._json(503,{'error':'ElevenLabs narration unavailable. Check voice access, quota and connection, then retry.'})
    return True
