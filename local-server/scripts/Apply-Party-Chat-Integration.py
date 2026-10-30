"""Install only the reviewed native party routing sources with exact backups."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1] / 'party-chat-integration'
source = Path('C:/Files/Programs/Codex/Presence/working')
stage = root / 'working'
files = []
for name in ('root-manifest.json', 'native-chat-manifest.json'):
    data = json.loads((root / name).read_text(encoding='utf-8-sig'))
    if isinstance(data, dict):
        if Path(data['source_root']) != source or Path(data['staged_root']) != stage:
            raise RuntimeError('Unexpected source directory.')
        files.extend(data['files'])
    else:
        files.extend(data)
allowed = {
    'backend/tools/game_player.py', 'backend/tools/game_player_native.py',
    'backend/tools/game_player_modes/social/game_player_social.py',
    'backend/tests/test_game_player_native_loop_efficiency.py',
    'backend/tests/test_game_player_native_chat_routing.py',
    'backend/tests/test_game_player_party_chat_delivery.py',
    'docs/game-player-azerothcore.md',
}
if {item['path'] for item in files} != allowed or len(files) != len(allowed):
    raise RuntimeError('Unexpected deployment files.')

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None

for item in files:
    relative = Path(item['path'])
    if relative.is_absolute() or '..' in relative.parts:
        raise RuntimeError('Unexpected relative path.')
    if digest(source / relative) != item['sha256']:
        raise RuntimeError(f'Original changed; merge required: {relative}')
    if digest(stage / relative) != item['staged_sha256']:
        raise RuntimeError(f'Staged source changed; review required: {relative}')
backup = root / 'backups' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
backup.mkdir(parents=True, exist_ok=False)
(backup / 'applied.json').write_text(json.dumps(files, indent=2), encoding='utf-8')
for item in files:
    if item['sha256'] is not None:
        target = backup / item['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / item['path'], target)
for item in files:
    target = source / item['path']
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(stage / item['path'], target)
    if digest(target) != item['staged_sha256']:
        raise RuntimeError('Installed source verification failed.')
print(f'Installed and verified {len(files)} reviewed files. Originals: {backup}')
