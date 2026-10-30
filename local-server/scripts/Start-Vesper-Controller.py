"""Start the saved Presence Full runtime through its authenticated local API."""
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
backend = Path('C:/Files/Programs/Codex/Presence/working/backend')
sys.path.insert(0, str(backend))
os.environ.setdefault('PRESENCE_DISABLE_SCHEDULER', '1')
from app.runtime_security import runtime_control_token
import requests

headers = {'X-Presence-Runtime-Request': '1'}
token = runtime_control_token()
if token:
    headers['X-Presence-Runtime-Token'] = token
response = requests.post('http://127.0.0.1:8000/runtime/game-player/start', json={}, headers=headers, timeout=30)
if not response.ok:
    raise RuntimeError(f'Presence start request failed (HTTP {response.status_code}); no authentication values printed.')
state = response.json()
print({key: state.get(key) for key in ('status', 'running', 'paused', 'pid', 'game_backend', 'last_error')})
