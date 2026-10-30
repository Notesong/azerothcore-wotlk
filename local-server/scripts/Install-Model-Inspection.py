"""Install reviewed inspection files only when every original still matches."""
import hashlib
import json
from pathlib import Path
import shutil

integration = Path('C:/Games/AzerothCore/model-context-integration')
presence = Path('C:/Files/Programs/Codex/Presence/working')
gateway = Path('C:/Files/Programs/Codex/ChatGPT-Scratchpad')

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None

def within(root, relative):
    path = (root / relative).resolve()
    path.relative_to(root.resolve())
    return path

full = json.loads((integration / 'full-inspection-manifest.json').read_text())
gateway_originals = {item['path']: item['sha256'] for item in
                     json.loads((integration / 'gateway/original-hashes.json').read_text())}
plans = []
installed_record = integration / 'installed-files.json'
prior = {(item['component'], item['path']): item['sha256'] for item in
         (json.loads(installed_record.read_text()) if installed_record.is_file() else [])}
for item in full['files']:
    relative = item['path']
    plans.append(('presence', relative, within(presence, relative),
                  within(integration / 'working', relative), item['sha256'], item['staged_sha256']))
for item in json.loads((integration / 'gateway/deploy-manifest.json').read_text()):
    relative = item['path']
    plans.append(('gateway', relative, within(gateway, relative),
                  within(integration / 'gateway', relative), gateway_originals[relative], item['sha256']))

for label, relative, target, staged, original_hash, staged_hash in plans:
    current = digest(target)
    allowed = {original_hash.lower() if original_hash else None,
               prior.get((label, relative)), staged_hash.lower()}
    if current not in allowed:
        raise SystemExit(f'Original changed; nothing installed: {label}/{relative}')
    if digest(staged) != staged_hash.lower():
        raise SystemExit(f'Staged file changed; nothing installed: {label}/{relative}')

results = []
for label, relative, target, staged, original_hash, staged_hash in plans:
    if original_hash is not None and target.is_file():
        backup = within(integration / 'deployment-backups' / label, relative)
        backup.parent.mkdir(parents=True, exist_ok=True)
        if not backup.exists():
            shutil.copy2(target, backup)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(staged, target)
    if digest(target) != staged_hash.lower():
        raise SystemExit(f'Installed hash mismatch: {label}/{relative}')
    results.append({'component': label, 'path': relative, 'sha256': staged_hash.lower()})
(integration / 'installed-files.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
print(f'Installed and verified {len(results)} reviewed inspection files.')
