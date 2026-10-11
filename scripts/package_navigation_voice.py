"""Prepackage fixed UI prompts with the existing cached ElevenLabs speaker.

Run in the camera environment (requests/PyYAML), with ElevenLabs settings in the repository-root .env.
No credentials are written to the browser bundle.
"""
import json
import os
from pathlib import Path
import shutil
import sys
from voice_env import load_voice_env

ROOT = Path(__file__).resolve().parents[1]


def main():
    load_voice_env()
    key = os.environ.get('ELEVENLABS_API_KEY', '').strip()
    if not key:
        print('ELEVENLABS_API_KEY is not set. Navigation keeps using local browser speech; no audio was generated.')
        return 1
    sys.path.insert(0, str(ROOT / 'cane-vision'))
    import yaml
    from cane_vision.elevenlabs import ElevenLabsTTS, DEFAULT_VOICE, DEFAULT_MODEL
    config = yaml.safe_load((ROOT / 'orin-harness/config.yaml').read_text())
    settings = config.get('speech', {}).get('elevenlabs', {})
    destination = ROOT / 'web/learn/assets/navigation-voice'
    cache = ROOT / '.local/navigation-voice'
    tts = ElevenLabsTTS(key, voice_id=os.environ.get('ELEVENLABS_NAVIGATION_VOICE_ID') or os.environ.get('ELEVENLABS_VOICE_ID') or settings.get('voice_id', DEFAULT_VOICE), model_id=os.environ.get('ELEVENLABS_MODEL_ID') or settings.get('model_id', DEFAULT_MODEL), cache_dir=cache)
    phrases = json.loads((ROOT / 'web/learn/navigation-prompts.json').read_text())
    destination.mkdir(parents=True, exist_ok=True)
    try:
        generated = [(route, tts.audio(phrase)) for route, phrase in phrases.items()]
    except Exception:
        print('ElevenLabs packaging failed. Check key access, quota, and network. Existing packaged prompts remain available.')
        return 1
    for route, source in generated:
        shutil.copyfile(source, destination / f'{route}.wav')
    manifest = {'provider':'elevenlabs','voice_id':tts.voice_id,'model_id':tts.model_id,'phrases':phrases}
    temporary = destination / 'manifest.part'
    temporary.write_text(json.dumps(manifest, indent=2) + '\n')
    temporary.replace(destination / 'manifest.json')
    print(f'Packaged {len(phrases)} navigation prompts. They now play locally without a live ElevenLabs request.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
