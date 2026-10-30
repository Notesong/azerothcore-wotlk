"""Install the reviewed native efficiency delta with exact-hash backups."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1] / 'efficiency-integration'
source = Path('C:/Files/Programs/Codex/Presence/working')
stage = root / 'working'
files = []
for name in ('root-manifest.json', 'native-context-manifest.json',
             'native-planning-manifest.json', 'usage-controls-manifest.json'):
    data = json.loads((root / name).read_text(encoding='utf-8'))
    if isinstance(data, dict):
        if Path(data['source_root']) != source or Path(data['staged_root']) != stage:
            raise RuntimeError('Unexpected source directory.')
        files.extend(data['files'])
    else:
        files.extend(data)
allowed = {
    'backend/tools/game_player.py',
    'backend/tools/game_player_native_usage.py',
    'backend/tools/game_player_native_context.py',
    'backend/tools/game_player_native_planning.py',
    'backend/tests/test_game_player_native_efficiency.py',
    'backend/tests/test_game_player_native.py',
    'backend/tests/test_game_player_native_conversation.py',
    'backend/tests/test_game_player_native_context.py',
    'backend/tests/test_game_player_native_planning.py',
    'backend/tests/test_game_player_native_loop_efficiency.py',
    'backend/tests/test_game_player_native_usage_runtime.py',
    'backend/app/game_player_runtime_service.py',
    'backend/app/routes_runtime.py',
    'frontend/src/components/AzerothCoreGamePlayerPanel.jsx',
    'frontend/src/components/AzerothCoreGamePlayerPanel.test.jsx',
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
        relative = Path(item['path'])
        target = backup / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / relative, target)
for item in files:
    relative = Path(item['path'])
    target = source / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(stage / relative, target)
    if digest(target) != item['staged_sha256']:
        raise RuntimeError(f'Installed source verification failed: {relative}')
print(f'Installed and verified {len(files)} reviewed files. Backups: {backup}')
