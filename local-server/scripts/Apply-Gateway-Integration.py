"""Deploy only reviewed gateway files, refusing to overwrite newer user edits."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1] / 'gateway-integration'
manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
destination = Path(manifest['source_root'])
stage = Path(manifest['staged_root'])
if destination != Path('C:/Files/Programs/Codex/ChatGPT-Scratchpad') or stage != root / 'working':
    raise RuntimeError('Unexpected gateway destination.')

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None

for item in manifest['files']:
    relative = Path(item['path'])
    if relative.is_absolute() or '..' in relative.parts:
        raise RuntimeError('Unexpected manifest path.')
    if digest(destination / relative) != item['sha256']:
        raise RuntimeError(f'Original changed; merge required: {relative}')
    if digest(stage / relative) != item['staged_sha256']:
        raise RuntimeError(f'Stage changed; review required: {relative}')
backup = root / 'backups' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
for item in manifest['files']:
    relative = Path(item['path'])
    if item['sha256'] is not None:
        target = backup / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(destination / relative, target)
    target = destination / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(stage / relative, target)
backup.mkdir(parents=True, exist_ok=True)
(backup / 'applied.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print(f'Applied {len(manifest["files"])} gateway files. Originals backed up to {backup}')
