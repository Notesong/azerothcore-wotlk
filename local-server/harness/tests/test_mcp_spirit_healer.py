"""Offline Spirit Healer contract checks; no native gameplay or provider calls."""
from contextlib import contextmanager
import uuid

import pytest

from presence_acore.mcp_actions import ACTION_SCHEMA, normalize_action
from presence_acore.mcp_control import McpControlManager


ACTION = {'type': 'spirit_healer_activate', 'target_guid': '18446744073709551615'}
INVALID = [
    {'type': ACTION['type']},
    *[{**ACTION, 'target_guid': value} for value in
      (42, True, None, '', '0', '01', '-1', '+1', ' 42', '42 ', '١٢٣', '4.2', '4e2',
       '18446744073709551616', '100000000000000000000')],
    {**ACTION, 'character': 'Other'},
    {**ACTION, 'spell_id': 17251},
    {**ACTION, 'type': 'resurrect'},
    {**ACTION, 'type': 'spirit_healer_confirm'},
]


@pytest.mark.parametrize('value', INVALID)
def test_spirit_healer_rejects_inexact_identity_unknown_arguments_and_spoofed_actions(value):
    with pytest.raises(ValueError, match='invalid_action'):
        normalize_action(value)


@pytest.mark.parametrize('guid', ['1', '42', '18446744073709551615'])
def test_spirit_healer_keeps_exact_unsigned_guid_and_closed_schema(guid):
    value = {**ACTION, 'target_guid': guid}
    assert normalize_action(value) == value
    variant = next(row for row in ACTION_SCHEMA['oneOf']
                   if row['properties']['type']['const'] == ACTION['type'])
    assert variant['required'] == ['type', 'target_guid']
    assert set(variant['properties']) == {'type', 'target_guid'}
    assert variant['additionalProperties'] is False


class Runtime:
    def snapshot(self): return {}
    def stop_gracefully(self, prior): pass
    def proves_stopped(self): return True
    def restore(self, prior, **kwargs): return {}


class Client:
    def __init__(self): self.calls = []
    def execute(self, character, action, **kwargs):
        self.calls.append((character, action, kwargs))
        return {'status': 'completed', 'recovery_receipt': {
            'target_guid': action['target_guid'], 'life_changed': True,
            'alive_before': False, 'alive_after': True, 'resurrection_sickness': None}}


def test_spirit_healer_uses_existing_lease_and_replays_original_operation_once(tmp_path):
    private = tmp_path / 'private'
    private.mkdir()
    @contextmanager
    def locked(): yield
    client = Client()
    manager = McpControlManager(Runtime(), client, control_path=tmp_path / 'control.json',
        receipt_root=private / 'receipts', lock_factory=locked, authorization_mode='lease_token')
    lease = manager.take_over('first-transport', str(uuid.uuid4()))
    operation_id = str(uuid.uuid4())
    result = manager.act('second-transport', lease['control_token'], operation_id, ACTION,
                         observed_sequence=9)
    assert result['result']['recovery_receipt']['life_changed'] is True
    assert result['result']['recovery_receipt']['resurrection_sickness'] is None
    assert manager.act('third-transport', lease['control_token'], operation_id, ACTION,
                       observed_sequence=9) == result
    assert len(client.calls) == 1
    assert client.calls[0][0:2] == ('Vesper', ACTION)
    assert client.calls[0][2]['observed_sequence'] == 9
