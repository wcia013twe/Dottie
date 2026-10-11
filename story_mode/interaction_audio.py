"""Generate reusable prompt/hint audio off the browser's playback path."""
import json
import os
from pathlib import Path
from threading import Lock
from scripts.build_narration import build, load_local_env

ROOT = Path(__file__).resolve().parents[1]
LOCK = Lock()

def prepare_audio(plan):
    if plan['tool'] not in ('propose_activity','propose_word_emphasis'): return {}
    with LOCK:
        settings = {}
        load_local_env(ROOT / '.env', settings)
        voice = os.environ.get('ELEVENLABS_VOICE_ID') or settings.get('ELEVENLABS_VOICE_ID')
        key = os.environ.get('ELEVENLABS_API_KEY') or settings.get('ELEVENLABS_API_KEY')
        if not voice or not key: return {}
        script = json.loads((ROOT/'story_mode/narration/peter-rabbit-interactions.json').read_text())
        script.update(book_id='peter-rabbit-exercises', script_version='exercise-1')
        script['passages'] = [{'id':name, 'match_text':'exercise:'+name, 'text':plan['arguments'][name]}
                              for name in ('prompt','hint')]
        build(script, ROOT/'web/learn/narration', voice, api_key=key)
        manifest = json.loads((ROOT/'web/learn/narration/peter-rabbit-exercises/manifest.json').read_text())
        return {p['id']:'/learn/narration/peter-rabbit-exercises/'+p['audio'] for p in manifest['passages']}
