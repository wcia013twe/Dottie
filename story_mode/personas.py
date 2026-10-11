"""Repository-owned fictional personas, available only to the isolated Story test server."""
import json
from pathlib import Path

def load_persona(persona_id):
    if persona_id != 'alex-morgan':
        raise ValueError('Unknown synthetic persona.')
    return json.loads((Path(__file__).parent/'personas/alex-morgan.json').read_text())
