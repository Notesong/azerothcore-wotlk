"""Install the reviewed Presence commerce files with original/staged hash guards."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile


integration = Path('C:/Games/AzerothCore/commerce-integration')
roots = {
    'presence': Path('C:/Files/Programs/Codex/Presence/working'),
    'gateway': Path('C:/Files/Programs/Codex/ChatGPT-Scratchpad'),
}


def digest(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def inside(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    path.relative_to(root.resolve())
    return path


manifest = json.loads((integration / 'deployment-manifest.json').read_text(encoding='utf-8-sig'))
plans, seen = [], set()
for item in manifest['files']:
    component, relative = item.get('component', 'presence'), item['path']
    identity = (component, relative)
    if identity in seen:
        raise SystemExit(f'Duplicate target; nothing installed: {relative}')
    seen.add(identity)
    target = inside(roots[component], relative)
    stage = inside(integration, item['stage'])
    backup = inside(integration / 'deployment-backups' / component, relative)
    if digest(stage) != item['staged_sha256']:
        raise SystemExit(f'Stage changed; nothing installed: {relative}')
    if digest(target) not in {item['sha256'], item['staged_sha256']}:
        raise SystemExit(f'Original changed; nothing installed: {relative}')
    if backup.exists() and digest(backup) != item['sha256']:
        raise SystemExit(f'Backup changed; nothing installed: {relative}')
    plans.append((target, stage, backup, item))

for target, stage, backup, item in plans:
    if digest(target) == item['staged_sha256']:
        continue
    if target.is_file():
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, backup)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.commerce-install-', delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(stage.read_bytes())
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    if digest(target) != item['staged_sha256']:
        raise SystemExit(f'Installed file hash mismatch: {item["path"]}')

(integration / 'installed-files.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print(f'Installed and verified {len(plans)} Vesper commerce files.')
