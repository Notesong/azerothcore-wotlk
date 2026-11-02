"""Grounded group-loot voting through normal MCP control; no live game or model calls."""
from contextlib import contextmanager
import json
from pathlib import Path
import subprocess
import sys
import uuid

import pytest

from presence_acore.mcp_actions import ACTION_SCHEMA, normalize_action
from presence_acore.mcp_control import ControlError, McpControlManager
from presence_acore.mcp_server import _additional_tools


ROLL_ID = '0123456789abcdef0123456789abcdef'
ACTION = {'type': 'loot_roll', 'roll_id': ROLL_ID, 'choice': 'greed'}
INVALID = [
    {'type': 'loot_roll'}, {'type': 'loot_roll', 'roll_id': ROLL_ID},
    *[{**ACTION, 'roll_id': value} for value in (
        42, True, None, '', '1', 'a'*31, 'a'*33, 'A'*32, 'g'*32, ' '+ROLL_ID, ROLL_ID+'\n', '١'*32)],
    *[{**ACTION, 'choice': value} for value in (
        0, 1, 2, True, None, '', 'Need', 'GREED', 'disenchant', 'need ', 'pass\n')],
    *[{**ACTION, key: value} for key, value in (
        ('target_guid', '102'), ('item_guid', '4611686018429209808'), ('item_id', 14094),
        ('loot_slot', 0), ('slot', 0), ('force', True), ('winner', '102'), ('character', 'Other'),
        ('roll_type', 1), ('operation_id', str(uuid.uuid4())), ('control_token', 'a'*64))],
    {**ACTION, 'type': 'roll'}, {**ACTION, 'type': 'roll_loot'},
]


@pytest.mark.parametrize('value', INVALID)
def test_vote_rejects_malformed_rounds_alternate_choices_and_authority_arguments(value):
    with pytest.raises(ValueError, match='invalid_action'):
        normalize_action(value)


def test_round_nonce_and_choice_are_exact_and_discovery_describes_vote_scope():
    for roll_id in (ROLL_ID, '0'*32, 'f'*32):
        for choice in ('need', 'greed', 'pass'):
            value = {**ACTION, 'roll_id': roll_id, 'choice': choice}
            assert normalize_action(value) == value
    row = next(row for row in ACTION_SCHEMA['oneOf'] if row['properties']['type']['const'] == 'loot_roll')
    assert set(row['properties']) == {'type', 'roll_id', 'choice'}
    assert row['required'] == ['type', 'roll_id', 'choice'] and row['additionalProperties'] is False
    assert row['properties']['roll_id']['pattern'] == '^[a-f0-9]{32}$'
    assert row['properties']['choice']['enum'] == ['need', 'greed', 'pass']
    tool = next(row for row in _additional_tools() if row['name'] == 'wow_act')
    assert 'loot_roll(roll_id, choice)' in tool['description']
    assert 'not proof of winning or receiving the item' in tool['description']


class Runtime:
    def snapshot(self): return {}
    def stop_gracefully(self, prior): pass
    def proves_stopped(self): return True
    def restore(self, prior, **kwargs): return {}


class Client:
    def __init__(self): self.calls = []
    def execute(self, character, action, **kwargs):
        self.calls.append((character, action, kwargs))
        return {'status': 'completed', 'request_id': kwargs['request_id'], 'action_type': 'loot_roll',
            'loot_roll_receipt': {'roll_id': action['roll_id'], 'choice': action['choice'],
                'vote_recorded': True, 'roll_resolved': False}}


def test_recorded_vote_is_replayed_by_original_id_without_resubmitting_or_claiming_a_win(tmp_path):
    private = tmp_path / 'private'
    private.mkdir()
    @contextmanager
    def locked(): yield
    client = Client()
    manager = McpControlManager(Runtime(), client, control_path=tmp_path / 'control.json',
        receipt_root=private / 'receipts', lock_factory=locked, authorization_mode='lease_token')
    lease = manager.take_over('first-transport', str(uuid.uuid4()))
    operation_id = str(uuid.uuid4())
    result = manager.act('second-transport', lease['control_token'], operation_id, ACTION, observed_sequence=9)
    assert result['status'] == 'completed'
    assert result['result']['loot_roll_receipt']['vote_recorded'] is True
    assert result['result']['loot_roll_receipt']['roll_resolved'] is False
    assert manager.act('third-transport', lease['control_token'], operation_id, ACTION, observed_sequence=9) == result
    assert len(client.calls) == 1 and client.calls[0][0:2] == ('Vesper', ACTION)
    assert client.calls[0][2] == {'request_id': operation_id, 'observed_sequence': 9}
    for changed in ({**ACTION, 'choice': 'need'}, {**ACTION, 'roll_id': 'a'*32}):
        with pytest.raises(ControlError, match='operation_id_conflict'):
            manager.act('third-transport', lease['control_token'], operation_id, changed, observed_sequence=9)
    assert len(client.calls) == 1


def test_invalid_or_unowned_vote_never_reaches_the_bridge(tmp_path):
    private = tmp_path / 'private'
    private.mkdir()
    @contextmanager
    def locked(): yield
    client = Client()
    manager = McpControlManager(Runtime(), client, control_path=tmp_path / 'control.json',
        receipt_root=private / 'receipts', lock_factory=locked, authorization_mode='lease_token')
    lease = manager.take_over('owner', str(uuid.uuid4()))
    for action in INVALID:
        with pytest.raises(ControlError, match='invalid_action'):
            manager.act('owner', lease['control_token'], str(uuid.uuid4()), action)
    with pytest.raises(ControlError, match='control_not_owned'):
        manager.act('owner', 'b'*64, str(uuid.uuid4()), ACTION)
    assert client.calls == []


def test_loot_roll_preview_helper_loads_without_importing_the_autonomous_runtime(tmp_path):
    tools = tmp_path / 'backend' / 'tools'
    tools.mkdir(parents=True)
    (tools / 'game_player_native_gear.py').write_text(
        'def role_context(value): return {"role": "damage"}\n', encoding='utf-8')
    (tools / 'game_player_native_loot_rolls.py').write_text(
        'def loot_roll_context(value):\n'
        '    from tools.game_player_native_gear import role_context\n'
        '    return {"rolls": value["loot_rolls"], "gear": role_context(value)}\n', encoding='utf-8')
    (tools / 'game_player_native_context.py').write_text(
        'from tools.game_player_native_loot_rolls import loot_roll_context\n'
        'def compact_native_observation(value, mode="gameplay"):\n'
        '    return loot_roll_context(value)\n', encoding='utf-8')
    observation = {'_fresh': True, 'sequence': 7, 'loot_rolls': [{'roll_id': ROLL_ID,
        'state': 'pending', 'remaining_ms': None, 'deadline_known': False, 'allowed_choices': ['greed', 'pass']}]}
    code = ('import sys,json,builtins\nfrom pathlib import Path\n'
        f'sys.path.insert(0,{str(Path(__file__).resolve().parents[1])!r})\n'
        'from presence_acore.model_context import _projection\n'
        'before=set(sys.modules); original=builtins.__import__\n'
        f'fn=_projection(Path({str(tmp_path)!r}))\n'
        f'value=fn(json.loads({json.dumps(observation)!r}))\n'
        f'assert value["rolls"][0]["roll_id"]=={ROLL_ID!r}\n'
        'assert value["rolls"][0]["remaining_ms"] is None\n'
        'assert value["rolls"][0]["allowed_choices"]==["greed","pass"]\n'
        'assert value["gear"]["role"]=="damage"\n'
        'assert builtins.__import__ is original\n'
        'assert not any(n.startswith(("tools.","app.","openai","anthropic")) for n in set(sys.modules)-before)\n'
        'print("loot roll inspection loaded without runtime")\n')
    result = subprocess.run([sys.executable, '-I', '-S', '-B', '-c', code],
        capture_output=True, text=True, check=True)
    assert 'loot roll inspection loaded without runtime' in result.stdout
