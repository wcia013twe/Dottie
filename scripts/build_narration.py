"""Build local, passage-aligned narration with ElevenLabs. Python standard library only."""
import argparse
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import shlex
import tempfile
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler
import wave

ROOT = Path(__file__).resolve().parents[1]
FORMAT = 'pcm_24000'
RATE = 24000
SAFE_ID = re.compile(r'^[a-zA-Z0-9_-]{1,100}$')


def validate(script):
    fields = {'schema_version', 'book_id', 'script_version', 'model_id', 'voice_settings', 'passages'}
    if not isinstance(script, dict) or set(script) != fields or script['schema_version'] != '1.0':
        raise ValueError('Expected narration script schema 1.0.')
    for name in ('book_id', 'script_version', 'model_id'):
        if not isinstance(script[name], str) or not SAFE_ID.fullmatch(script[name]):
            raise ValueError(f'Invalid {name}.')
    settings = script['voice_settings']
    if not isinstance(settings, dict) or set(settings) - {'stability', 'similarity_boost', 'style', 'use_speaker_boost'}:
        raise ValueError('Unknown voice setting.')
    for key, value in settings.items():
        if key == 'use_speaker_boost':
            if type(value) is not bool: raise ValueError('Speaker boost must be boolean.')
        elif type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError('Voice settings must be between zero and one.')
    if not isinstance(script['passages'], list) or not 1 <= len(script['passages']) <= 1000:
        raise ValueError('Expected 1–1000 passages.')
    ids, matches = set(), set()
    for passage in script['passages']:
        if not isinstance(passage, dict) or set(passage) != {'id', 'match_text', 'text'}:
            raise ValueError('Each passage needs id, match_text and text.')
        if not isinstance(passage['id'], str) or not SAFE_ID.fullmatch(passage['id']) or passage['id'] in ids:
            raise ValueError('Passage IDs must be unique safe identifiers.')
        for key in ('text', 'match_text'):
            if not isinstance(passage[key], str) or not 1 <= len(passage[key].strip()) <= 4000:
                raise ValueError('Passage text must contain 1–4000 characters; split longer passages.')
        match = ' '.join(passage['match_text'].split()).lower()
        if match in matches: raise ValueError('Passage match text must be unique.')
        ids.add(passage['id']); matches.add(match)
    return script


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): return None


def synthesize(voice_id, payload, api_key):
    if not api_key: raise ValueError('Set ELEVENLABS_API_KEY to generate missing audio.')
    request = Request(f'https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format={FORMAT}',
        data=json.dumps(payload).encode(), headers={'xi-api-key': api_key,
        'Content-Type': 'application/json', 'Accept': 'audio/pcm'})
    try:
        with build_opener(NoRedirect).open(request, timeout=90) as response:
            if response.headers.get_content_type() not in ('audio/pcm', 'audio/x-pcm', 'audio/raw', 'application/octet-stream'):
                raise ValueError('ElevenLabs returned an unexpected audio type.')
            pcm = response.read(64 * 1024 * 1024 + 1)
    except HTTPError as exc:
        code=exc.code; exc.close()
        raise ValueError(f'ElevenLabs HTTP {code}; check credentials, voice access or quota. No automatic retry.') from None
    except (URLError, TimeoutError):
        raise ValueError('ElevenLabs connection failed. Rerun to retry missing passages.') from None
    if not pcm or len(pcm) % 2 or len(pcm) > 64 * 1024 * 1024:
        raise ValueError('Invalid or oversized PCM audio.')
    return pcm


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as out:
            name = out.name; out.write(data)
        os.replace(name, path)
    finally:
        if name and os.path.exists(name): os.unlink(name)


def duration(path):
    try:
        with wave.open(str(path), 'rb') as audio:
            if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) != (1, 2, RATE): return None
            frames=audio.getnframes()
            if frames <= 0 or len(audio.readframes(frames)) != frames * 2: return None
            return round(frames / RATE, 6)
    except (OSError, EOFError, wave.Error): return None


def build(script, output_root, voice_id, *, api_key=None, dry_run=False, convert=synthesize):
    validate(script)
    if not isinstance(voice_id, str) or not SAFE_ID.fullmatch(voice_id):
        raise ValueError('Set ELEVENLABS_VOICE_ID or pass --voice-id.')
    folder = Path(output_root) / script['book_id']
    manifest = {key: script[key] for key in ('schema_version', 'book_id', 'script_version', 'model_id', 'voice_settings')}
    manifest.update(voice_id=voice_id, source_format=FORMAT, format='wav', passages=[])
    generated = reused = 0
    for passage in script['passages']:
        payload = {'text': passage['text'], 'model_id': script['model_id'], 'voice_settings': script['voice_settings']}
        digest = hashlib.sha256(json.dumps({'voice_id':voice_id, 'format':FORMAT, **payload}, sort_keys=True).encode()).hexdigest()
        name = f"{passage['id']}-{digest}.wav"
        path = folder / name
        seconds = duration(path)
        if seconds is None:
            generated += 1
            if not dry_run:
                pcm = convert(voice_id, payload, api_key)
                if not isinstance(pcm, bytes) or not pcm or len(pcm) % 2: raise ValueError('Invalid PCM audio.')
                buffer = io.BytesIO()
                with wave.open(buffer, 'wb') as audio:
                    audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(RATE); audio.writeframes(pcm)
                atomic_write(path, buffer.getvalue())
                seconds = duration(path)
        else: reused += 1
        manifest['passages'].append({**passage, 'audio': name, 'duration_seconds': seconds, 'cache_key': digest})
    if not dry_run:
        atomic_write(folder / 'manifest.json', (json.dumps(manifest, indent=2)+'\n').encode())
    return {'generate': generated, 'reuse': reused, 'dry_run': dry_run, 'manifest': str(folder / 'manifest.json')}


def load_local_env(path, environ=None):
    """Read only narration settings. Never execute shell code or expand variables."""
    environ = os.environ if environ is None else environ
    if not path.exists(): return
    pending = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if line.startswith('export '): line = line[7:].lstrip()
        key, separator, value = line.partition('=')
        key = key.strip()
        if not separator or key not in ('ELEVENLABS_API_KEY', 'ELEVENLABS_VOICE_ID'): continue
        try:
            parts = shlex.split(value, comments=True, posix=True)
        except ValueError:
            raise ValueError('Invalid quoted ElevenLabs setting in .env.') from None
        if len(parts) > 1: raise ValueError('Quote ElevenLabs settings containing spaces in .env.')
        pending[key] = parts[0] if parts else ''
    for key, value in pending.items(): environ.setdefault(key, value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('script', type=Path)
    parser.add_argument('--output-root', type=Path, default=ROOT/'web/learn/narration')
    parser.add_argument('--voice-id')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    try:
        load_local_env(ROOT / '.env')
        result=build(json.loads(args.script.read_text()), args.output_root, args.voice_id or os.environ.get('ELEVENLABS_VOICE_ID'),
            api_key=os.environ.get('ELEVENLABS_API_KEY'), dry_run=args.dry_run)
    except (ValueError, OSError) as exc:
        parser.exit(1, f'{exc}\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__': main()
