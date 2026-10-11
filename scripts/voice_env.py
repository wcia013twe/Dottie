"""Load allowlisted local credentials from the repository's private .env file."""
import os
from pathlib import Path
import shlex

VOICE_KEYS = {'ELEVENLABS_API_KEY', 'ELEVENLABS_VOICE_ID', 'ELEVENLABS_NAVIGATION_VOICE_ID', 'ELEVENLABS_STORY_VOICE_ID', 'ELEVENLABS_MODEL_ID'}
DATABRICKS_KEYS = {'DATABRICKS_HOST', 'DATABRICKS_TOKEN', 'DATABRICKS_AUTH_TYPE'}


def load_env(keys):
    path = Path(__file__).resolve().parents[1] / '.env'
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line.startswith('export '):
            line = line[7:]
        name, separator, value = line.partition('=')
        name = name.strip()
        if not separator or name not in keys:
            continue
        try:
            parts = shlex.split(value, comments=True)
        except ValueError:
            raise ValueError(f'Invalid quoting for {name} in .env') from None
        if len(parts) == 1:
            os.environ.setdefault(name, parts[0])


def load_voice_env():
    load_env(VOICE_KEYS)


def load_databricks_env():
    """Load only local Databricks unified-auth settings before starting the server."""
    load_env(DATABRICKS_KEYS)
