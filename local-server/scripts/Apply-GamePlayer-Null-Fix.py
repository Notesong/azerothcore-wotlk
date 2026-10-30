"""Install the two-file loading-state fix with verified originals and backups."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1] / 'null-status-fix'
destination = Path('C:/Files/Programs/Codex/Presence/working')
entries = json.loads((root / 'manifest.json').read_text(encoding='utf-8-sig'))
allowed = {
    'frontend/src/components/AzerothCoreGamePlayerPanel.jsx',
    'frontend/src/components/AzerothCoreGamePlayerPanel.test.jsx',
}
if {item['path'] for item in entries} != allowed or len(entries) != 2:
    raise RuntimeError('Unexpected deployment files.')

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

for item in entries:
    if digest(destination / item['path']) != item['sha256']:
        raise RuntimeError('Installed file changed; merge before applying.')
    if digest(root / Path(item['path']).name) != item['staged_sha256']:
        raise RuntimeError('Staged file changed; review before applying.')
backup = root / 'backups' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
backup.mkdir(parents=True, exist_ok=False)
(backup / 'applied.json').write_text(json.dumps(entries, indent=2), encoding='utf-8')
for item in entries:
    shutil.copy2(destination / item['path'], backup / Path(item['path']).name)
for item in entries:
    target = destination / item['path']
    shutil.copy2(root / Path(item['path']).name, target)
    if digest(target) != item['staged_sha256']:
        raise RuntimeError('Installed hash mismatch.')
print(f'Installed and verified loading-state fix. Originals: {backup}')
