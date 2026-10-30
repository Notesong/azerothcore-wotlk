"""Read-only deployment checks; attach only the existing dedicated character if offline."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
import urllib.request

sys.dont_write_bytecode = True
root = Path('C:/Games/AzerothCore')
integration = root / 'commerce-integration'
presence = Path('C:/Files/Programs/Codex/Presence/working')
sys.path.insert(0, str(root / 'harness'))
from presence_acore.client import BridgeError, Client
from presence_acore.mcp_server import Inspector

client = Client()
attached = False
try:
    observation = client.observe('Vesper')
except BridgeError as exc:
    if exc.code != 'character_offline':
        raise
    client.attach('Vesper')
    attached = True
    deadline = time.monotonic() + 45
    while True:
        try:
            observation = client.observe('Vesper')
            break
        except BridgeError as retry:
            if retry.code not in {'character_offline', 'not_ready'} or time.monotonic() >= deadline:
                raise
            time.sleep(0.5)

capabilities = client.capabilities('Vesper')
actions = {'vendor_list', 'vendor_buy', 'vendor_sell', 'vendor_repair', 'vendor_buyback',
           'trainer_list', 'train_spell', 'equip_item', 'unequip_item', 'inspect_item', 'gossip_select'}
assert actions <= set(capabilities['actions'])
config = json.loads((presence / 'local/game_player.config.json').read_text(encoding='utf-8-sig'))
assert actions <= set(config['allowed_actions'])
assert observation['self']['name'] == 'Vesper'
assert len(observation['equipment']) == 23
assert {row['equipment_slot'] for row in observation['equipment']} == set(range(23))
assert observation['bounds']['inventory'] == 200
assert observation['bounds']['vendor_page'] == observation['bounds']['trainer_page'] == 24
assert {'vendor', 'trainer', 'buyback', 'inspected_item', 'inventory_index'} <= observation.keys()
assert observation['protection']['policy'] == 'evade_only'

before = json.loads((integration / 'before-state.json').read_text(encoding='utf-8-sig'))
inventory_keys = ('guid', 'entry', 'count', 'bag', 'slot')
inventory = sorted([tuple(row[key] for key in inventory_keys) for row in observation['inventory']])
old_inventory = sorted([tuple(row[key] for key in inventory_keys) for row in before['inventory']])
comparisons = {
    'money_unchanged': before['self']['money'] == observation['self']['money'],
    'inventory_unchanged': inventory == old_inventory,
    'spells_unchanged': sorted(before['spell_ids']) == sorted(row['id'] for row in observation['spells']),
    'quests_unchanged': sorted(before['quest_ids']) == sorted(row['id'] for row in observation['quests']),
}
assert all(comparisons.values()), comparisons

preview = Inspector(client).model_context(lane='body', source='live_preview')
assert preview['available'] is True, preview.get('error')
projected = preview['preview']['native_observation']
assert {'vendor', 'trainer', 'equipment'} <= projected.keys()
assert len(projected['equipment']) == 23

with urllib.request.urlopen('http://127.0.0.1:8000/runtime/game-player', timeout=10) as response:
    runtime = json.load(response)
assert runtime['running'] and runtime['paused']
assert runtime.get('gameplay_model_calls', 0) == runtime.get('social_model_calls', 0) == 0
assert not runtime.get('last_error')

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

assert digest(root / 'build/bin/RelWithDebInfo/worldserver.exe') == digest(root / 'server/worldserver.exe')
summary = {
    'verified_at': datetime.now(timezone.utc).isoformat(),
    'character': 'Vesper', 'attached_existing_character': attached,
    'new_actions_enabled': sorted(actions), 'allowed_action_count': len(config['allowed_actions']),
    'equipment_slots': len(observation['equipment']), 'inventory_items': len(observation['inventory']),
    'known_active_spells': len(observation['spells']), 'quests': len(observation['quests']),
    'money_copper': observation['self']['money'], **comparisons,
    'body_preview_available': True, 'moon_policy': observation['protection']['policy'],
    'running': runtime['running'], 'paused': runtime['paused'], 'controller_pid': runtime['pid'],
    'gameplay_model_calls': 0, 'social_model_calls': 0, 'commerce_actions_executed': 0,
    'world_binary_hash_matches': True,
}
(integration / 'completed-verification.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
print(json.dumps(summary))
