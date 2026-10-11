"""Load only ElevenLabs settings from the repository's private .env file."""
import os
from pathlib import Path
import shlex

KEYS = {'ELEVENLABS_API_KEY', 'ELEVENLABS_VOICE_ID', 'ELEVENLABS_MODEL_ID'}


def load_voice_env():
    path = Path(__file__).resolve().parents[1] / '.env'
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line.startswith('export '):
            line = line[7:]
        name, separator, value = line.partition('=')
        name = name.strip()
        if not separator or name not in KEYS:
            continue
        try:
            parts = shlex.split(value, comments=True)
        except ValueError:
            raise ValueError(f'Invalid quoting for {name} in .env') from None
        if len(parts) == 1:
            os.environ.setdefault(name, parts[0])
