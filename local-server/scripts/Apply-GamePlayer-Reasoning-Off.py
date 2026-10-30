"""Install explicit reasoning-off requests and update only the active effort keys."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1] / 'reasoning-off-integration'
source = Path('C:/Files/Programs/Codex/Presence/working')
stage = root / 'working'
files = []
for name in ('root-manifest.json', 'social-reasoning-manifest.json'):
    data = json.loads((root / name).read_text(encoding='utf-8-sig'))
    if isinstance(data, dict):
        if Path(data['source_root']) != source or Path(data['staged_root']) != stage:
            raise RuntimeError('Unexpected source directory.')
        files.extend(data['files'])
    else:
        files.extend(data)
allowed = {
    'backend/tools/game_player.py',
    'backend/tools/game_player_modes/social/game_player_social.py',
    'backend/tests/test_game_player_contract.py',
    'backend/tests/test_game_player_reasoning_off.py',
    'backend/tests/test_game_player_social_reasoning_off.py',
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
config_entry = json.loads((root / 'config-baseline.json').read_text(encoding='utf-8-sig'))
if config_entry['path'] != 'local/game_player.config.json':
    raise RuntimeError('Unexpected configuration path.')
config_path = source / config_entry['path']
if digest(config_path) != config_entry['sha256']:
    raise RuntimeError('Saved settings changed; merge before applying.')
old_config = json.loads(config_path.read_text(encoding='utf-8-sig'))
if (old_config.get('game_backend') != 'azerothcore' or old_config.get('model') != 'gpt-6-luna'
        or old_config.get('social_model') != 'gpt-5.6-sol'):
    raise RuntimeError('Models changed; verify support before disabling reasoning.')
new_config = {**old_config, 'reasoning_effort': 'none', 'social_reasoning_effort': 'none'}
changed_keys = {key for key in set(old_config) | set(new_config) if old_config.get(key) != new_config.get(key)}
if not changed_keys <= {'reasoning_effort', 'social_reasoning_effort'}:
    raise RuntimeError('Unexpected configuration changes.')
backup = root / 'backups' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
backup.mkdir(parents=True, exist_ok=False)
(backup / 'applied.json').write_text(json.dumps({'files': files, 'config': config_entry,
    'changed_config_keys': sorted(changed_keys)}, indent=2), encoding='utf-8')
for item in [*files, config_entry]:
    if item['sha256'] is not None:
        target = backup / item['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / item['path'], target)
for item in files:
    target = source / item['path']
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(stage / item['path'], target)
    if digest(target) != item['staged_sha256']:
        raise RuntimeError('Installed source hash mismatch.')
temporary = config_path.with_name(config_path.name + '.reasoning-off.tmp')
temporary.write_text(json.dumps(new_config, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
temporary.replace(config_path)
if json.loads(config_path.read_text(encoding='utf-8')) != new_config:
    raise RuntimeError('Installed configuration verification failed.')
print(f'Installed {len(files)} reviewed files; both active reasoning settings are none.')
print(f'Changed configuration keys: {", ".join(sorted(changed_keys)) or "already correct"}.')
print(f'Originals: {backup}')
