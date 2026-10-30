"""Apply only reviewed native UI files after validating all originals and staging."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1] / 'native-ui-integration'
destination = Path('C:/Files/Programs/Codex/Presence/working')
stage = root / 'working'
frontend = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
if Path(frontend['source_root']) != destination or Path(frontend['staged_root']) != stage:
    raise RuntimeError('Unexpected source or staging directory.')
files = list(frontend['files'])
files.extend(json.loads((root / 'parent-manifest.json').read_text(encoding='utf-8')))
for entry in json.loads((root / 'backend-sourcehashes.json').read_text(encoding='utf-8')):
    relative = Path(entry['relative_path'])
    if Path(entry['destination_path']) != destination / relative or Path(entry['staged_path']) != stage / relative:
        raise RuntimeError('Unexpected backend path.')
    files.append({'path': relative.as_posix(), 'sha256': entry['source_sha256'],
                  'staged_sha256': entry['staged_sha256']})
if len(files) != 12 or len({Path(item['path']) for item in files}) != len(files):
    raise RuntimeError('Expected twelve distinct reviewed files.')

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None

for item in files:
    relative = Path(item['path'])
    if relative.is_absolute() or '..' in relative.parts:
        raise RuntimeError('Unexpected relative path.')
    if digest(destination / relative) != item['sha256']:
        raise RuntimeError(f'Original changed; merge required: {relative}')
    if digest(stage / relative) != item['staged_sha256']:
        raise RuntimeError(f'Stage changed; review required: {relative}')

backup = root / 'backups' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
backup.mkdir(parents=True, exist_ok=False)
manifest = {'source_root': str(destination), 'staged_root': str(stage), 'files': files}
(backup / 'applied.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
# Finish every backup before changing any installed source.
for item in files:
    relative = Path(item['path'])
    if item['sha256'] is not None:
        saved = backup / relative
        saved.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(destination / relative, saved)
for item in files:
    relative = Path(item['path'])
    target = destination / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(stage / relative, target)
    if digest(target) != item['staged_sha256']:
        raise RuntimeError(f'Post-copy verification failed: {relative}')
print(f'Applied and verified {len(files)} native UI files. Originals: {backup}')
