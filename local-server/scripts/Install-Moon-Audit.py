"""Install a frozen Moon audit manifest after verifying all originals and stages."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile


integration = Path('C:/Games/AzerothCore/moon-audit-integration')
roots = {
    'presence': Path('C:/Files/Programs/Codex/Presence/working'),
    'gateway': Path('C:/Files/Programs/Codex/ChatGPT-Scratchpad'),
}


def digest(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def within(root: Path, relative: str) -> Path:
    result = (root / relative).resolve()
    result.relative_to(root.resolve())
    return result


manifest = json.loads((integration / 'deployment-manifest.json').read_text(encoding='utf-8'))
plans = []
identities = set()
for item in manifest['files']:
    component, relative = item['component'], item['path']
    identity = (component, relative)
    if identity in identities:
        raise SystemExit('Duplicate deployment target; nothing installed.')
    identities.add(identity)
    target = within(roots[component], relative)
    stage = within(integration, item['stage'])
    expected = item['sha256']
    installed = item['staged_sha256']
    if digest(stage) != installed:
        raise SystemExit(f'Staged file changed; nothing installed: {component}/{relative}')
    if digest(target) not in {expected, installed}:
        raise SystemExit(f'Original changed; nothing installed: {component}/{relative}')
    plans.append((component, relative, target, stage, expected, installed))

for component, relative, target, stage, expected, installed in plans:
    if digest(target) == installed:
        continue
    backup = within(integration / 'deployment-backups' / component, relative)
    if target.is_file():
        backup.parent.mkdir(parents=True, exist_ok=True)
        if not backup.exists():
            shutil.copy2(target, backup)
        elif digest(backup) != expected:
            raise SystemExit(f'Unexpected backup: {component}/{relative}')
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.moon-install-', delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(stage.read_bytes())
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    if digest(target) != installed:
        raise SystemExit(f'Installed file mismatch: {component}/{relative}')

(integration / 'installed-files.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print(f'Installed and verified {len(plans)} Moon instruction/audit files.')
