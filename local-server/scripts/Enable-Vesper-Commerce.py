"""Enable only the requested new native actions in Vesper's saved configuration."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile


config = Path('C:/Files/Programs/Codex/Presence/working/local/game_player.config.json')
integration = Path('C:/Games/AzerothCore/commerce-integration')
actions = ('vendor_list', 'vendor_buy', 'vendor_sell', 'vendor_repair', 'vendor_buyback',
           'trainer_list', 'train_spell', 'equip_item', 'unequip_item', 'gossip_select', 'inspect_item')
original = config.read_bytes()
payload = json.loads(original.decode('utf-8-sig'))
session = payload.get('session_state') or {}
if payload.get('game_backend') != 'azerothcore' or str(session.get('controlled_character') or '').casefold() != 'vesper':
    raise SystemExit('Saved configuration is not Vesper on AzerothCore; nothing changed.')
allowed = payload.get('allowed_actions')
if not isinstance(allowed, list) or not allowed:
    print('Saved actions use native defaults; the installed defaults already include commerce.')
    raise SystemExit(0)
enabled = list(allowed)
for action in actions:
    if action not in enabled:
        enabled.append(action)
if enabled == allowed:
    print('Vesper commerce actions are already enabled.')
    raise SystemExit(0)
backup = integration / 'config-backups' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
backup.mkdir(parents=True, exist_ok=False)
(backup / config.name).write_bytes(original)
payload['allowed_actions'] = enabled
temporary = None
try:
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=config.parent,
                                     prefix='.vesper-commerce-', delete=False) as handle:
        temporary = Path(handle.name)
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
        handle.flush()
        os.fsync(handle.fileno())
    if config.read_bytes() != original:
        raise RuntimeError('Saved configuration changed during preparation; nothing replaced.')
    os.replace(temporary, config)
finally:
    if temporary is not None:
        temporary.unlink(missing_ok=True)
after = json.loads(config.read_text(encoding='utf-8'))
assert {key: value for key, value in after.items() if key != 'allowed_actions'} == {
    key: value for key, value in json.loads(original.decode('utf-8-sig')).items() if key != 'allowed_actions'}
print(f'Enabled {len(enabled) - len(allowed)} commerce actions; other saved settings are unchanged.')
