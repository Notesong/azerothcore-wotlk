"""Closed self-restoration item action; no gameplay or provider calls."""
from contextlib import contextmanager
from pathlib import Path
import json
import subprocess
import sys
import uuid

import pytest

from presence_acore.mcp_actions import ACTION_SCHEMA, normalize_action
from presence_acore.mcp_control import McpControlManager
from presence_acore.mcp_server import _additional_tools


ACTION = {'type': 'use_item', 'item_guid': '4611686018429209808'}
INVALID = [{'type': 'use_item'},
    *[{**ACTION, 'item_guid': value} for value in
      (42, True, None, '', '0', '01', '-1', '+1', ' 42', '42 ', '١٢٣', '4.2', '4e2',
       '18446744073709551616')],
    *[{**ACTION, key: value} for key, value in
      [('target_guid', '102'), ('spell_id', 439), ('count', 1), ('x', 1), ('character', 'Other')]],
    {**ACTION, 'type': 'item_use'}]


@pytest.mark.parametrize('value', INVALID)
def test_rejects_inexact_instances_extra_targets_and_alternate_action_names(value):
    with pytest.raises(ValueError, match='invalid_action'):
        normalize_action(value)


def test_closed_schema_and_discovery_keep_self_restoration_scope_explicit():
    assert normalize_action(ACTION) == ACTION
    row = next(row for row in ACTION_SCHEMA['oneOf'] if row['properties']['type']['const'] == 'use_item')
    assert row['required'] == ['type', 'item_guid'] and set(row['properties']) == {'type', 'item_guid'}
    assert row['additionalProperties'] is False
    tool = next(row for row in _additional_tools() if row['name'] == 'wow_act')
    assert 'use_item(item_guid)' in tool['description'] and 'self-restoration' in tool['description']
    assert 'accepted is pending' in tool['description']


class Runtime:
    def snapshot(self): return {}
    def stop_gracefully(self, prior): pass
    def proves_stopped(self): return True
    def restore(self, prior, **kwargs): return {}


class Client:
    def __init__(self): self.calls = []
    def execute(self, character, action, **kwargs):
        self.calls.append((character, action, kwargs))
        return {'status': 'accepted', 'request_id': kwargs['request_id'], 'action_type': 'use_item',
            'item_guid': action['item_guid'], 'cast_emitted': False, 'applied': False}


def test_item_use_preserves_lease_token_and_original_operation_id_without_resending(tmp_path):
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
    assert result['status'] == 'accepted' and result['result']['cast_emitted'] is False
    assert manager.act('third-transport', lease['control_token'], operation_id, ACTION, observed_sequence=9) == result
    assert len(client.calls) == 1 and client.calls[0][0:2] == ('Vesper', ACTION)
    assert client.calls[0][2]['request_id'] == operation_id and client.calls[0][2]['observed_sequence'] == 9


def test_item_use_projection_helper_loads_in_isolated_read_only_inspection(tmp_path):
    tools = tmp_path / 'backend' / 'tools'
    tools.mkdir(parents=True)
    (tools / 'game_player_native_item_use.py').write_text(
        'def item_use_context(value):\n'
        '    return {"state": value["item_use"]}\n', encoding='utf-8')
    (tools / 'game_player_native_context.py').write_text(
        'from tools.game_player_native_item_use import item_use_context\n'
        'def compact_native_observation(value, mode="gameplay"):\n'
        '    return item_use_context(value)\n', encoding='utf-8')
    observation = {'_fresh': True, 'sequence': 7, 'self': {'alive': True}, 'item_use': {
        'pending': {'request_id': 'old', 'action_type': 'use_item', 'item_guid': ACTION['item_guid'], 'status': 'unknown'},
        'last_receipt': None}, 'inventory': []}
    code = ('import sys,json,builtins\nfrom pathlib import Path\n'
        f'sys.path.insert(0,{str(Path(__file__).resolve().parents[1])!r})\n'
        'from presence_acore.model_context import _projection\n'
        'before=set(sys.modules); original=builtins.__import__\n'
        f'fn=_projection(Path({str(tmp_path)!r}))\n'
        f'value=fn(json.loads({json.dumps(observation)!r}))\n'
        'assert value["state"]["pending"]["request_id"]=="old"\n'
        'assert builtins.__import__ is original\n'
        'assert not any(n.startswith(("tools.","app.","openai","anthropic")) for n in set(sys.modules)-before)\n'
        'print("item use inspection loaded without runtime")\n')
    result = subprocess.run([sys.executable, '-I', '-S', '-B', '-c', code], capture_output=True, text=True, check=True)
    assert 'item use inspection loaded without runtime' in result.stdout
