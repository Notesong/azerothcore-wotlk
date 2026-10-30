"""Save the user's close-follow preference and install the reviewed adapter change."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1] / 'close-follow-integration'
source = Path('C:/Files/Programs/Codex/Presence/working')
files = json.loads((root / 'manifest.json').read_text(encoding='utf-8-sig'))
allowed = {'backend/tools/game_player_native.py', 'backend/tools/game_player.py',
    'backend/tests/test_game_player_native_follow_spacing.py', 'docs/game-player-azerothcore.md'}
if {item['path'] for item in files} != allowed or len(files) != len(allowed):
    raise RuntimeError('Unexpected source files.')

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None

for item in files:
    if digest(source / item['path']) != item['sha256']:
        raise RuntimeError('Installed source changed; merge required.')
    if digest(root / 'working' / item['path']) != item['staged_sha256']:
        raise RuntimeError('Staged source changed; review required.')
config_entry = json.loads((root / 'config-baseline.json').read_text(encoding='utf-8-sig'))
if config_entry['path'] != 'local/game_player.config.json':
    raise RuntimeError('Unexpected config path.')
config_path = source / config_entry['path']
if digest(config_path) != config_entry['sha256']:
    raise RuntimeError('Saved settings changed; merge required.')
old = json.loads(config_path.read_text(encoding='utf-8-sig'))
if not isinstance(old.get('session_state'), dict):
    raise RuntimeError('Expected existing session state.')
updated = {**old, 'session_state': {**old['session_state'], 'native_follow_distance': 1}}
assert {key: value for key, value in updated.items() if key != 'session_state'} == {
    key: value for key, value in old.items() if key != 'session_state'}
backup = root / 'backups' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
backup.mkdir(parents=True, exist_ok=False)
(backup / 'applied.json').write_text(json.dumps({'files': files, 'config': config_entry}, indent=2), encoding='utf-8')
for item in [*files, config_entry]:
    if item['sha256'] is not None:
        target = backup / item['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / item['path'], target)
for item in files:
    target = source / item['path']
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(root / 'working' / item['path'], target)
    if digest(target) != item['staged_sha256']:
        raise RuntimeError('Installed hash mismatch.')
temporary = config_path.with_name(config_path.name + '.close-follow.tmp')
temporary.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
temporary.replace(config_path)
assert json.loads(config_path.read_text(encoding='utf-8')) == updated
print(f'Installed close-follow preference: 1 yard. Originals: {backup}')
