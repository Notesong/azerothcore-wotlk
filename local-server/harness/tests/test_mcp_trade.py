"""Offline receive-only trade actions and event waits; no game/provider calls."""
from contextlib import contextmanager
import uuid

import pytest

from presence_acore.event_wait import FILTERS, wait_events
from presence_acore.mcp_actions import JSON_SCHEMA, normalize_action
from presence_acore.mcp_control import McpControlManager


KINDS = ('trade_begin', 'trade_accept', 'trade_unaccept', 'trade_cancel')
OFFER = {'target_guid': '42', 'trade_id': '18446744073709551615', 'trade_revision': 7}


@pytest.mark.parametrize('kind', KINDS)
def test_trade_contract_carries_exact_partner_transaction_and_offer(kind):
    value = {'type': kind, **OFFER}
    assert normalize_action(value) == value
    schema = next(row for row in JSON_SCHEMA['oneOf'] if row['properties']['type']['const'] == kind)
    assert set(schema['required']) == set(value)
    assert schema['additionalProperties'] is False


@pytest.mark.parametrize('field,value', [('target_guid', 42), ('target_guid', '0'),
    ('trade_id', 1), ('trade_id', '01'), ('trade_id', '0'), ('trade_id', '١٢٣'),
    ('trade_id', '18446744073709551616'), ('trade_revision', '7'), ('trade_revision', True),
    ('trade_revision', 7.0), ('trade_revision', 0), ('trade_revision', 0x100000000)])
def test_trade_contract_rejects_coerced_or_out_of_range_identity(field, value):
    with pytest.raises(ValueError, match='invalid_action'):
        normalize_action({'type': 'trade_accept', **OFFER, field: value})


def test_trade_contract_rejects_missing_fields_and_unsupported_outgoing_transfer():
    for field in OFFER:
        value = {'type': 'trade_accept', **OFFER}
        del value[field]
        with pytest.raises(ValueError, match='invalid_action'):
            normalize_action(value)
    for value in ({'type': 'trade_set_item', **OFFER, 'item_guid': '99'},
                  {'type': 'trade_accept', **OFFER, 'money': 100},
                  {'type': 'trade_accept', **OFFER, 'character': 'Other'}):
        with pytest.raises(ValueError, match='invalid_action'):
            normalize_action(value)


class Runtime:
    def snapshot(self): return {}
    def stop_gracefully(self, prior): pass
    def proves_stopped(self): return True
    def restore(self, prior, **kwargs): return {}


class Client:
    def __init__(self): self.calls = []
    def execute(self, character, action, **kwargs):
        self.calls.append((character, action, kwargs))
        return {'status': 'completed', 'outcome': 'awaiting_partner_acceptance', 'transfer_completed': False}


def test_mcp_forwarding_preserves_consent_receipt_and_replays_same_operation_once(tmp_path):
    private = tmp_path/'private'
    private.mkdir()
    @contextmanager
    def locked(): yield
    client = Client()
    manager = McpControlManager(Runtime(), client, control_path=tmp_path/'control.json',
        receipt_root=private/'receipts', lock_factory=locked)
    lease = manager.take_over('test-sdk-session', str(uuid.uuid4()))
    operation_id = str(uuid.uuid4())
    value = {'type': 'trade_accept', **OFFER}
    result = manager.act('test-sdk-session', lease['control_token'], operation_id, value, observed_sequence=9)
    assert result['result']['outcome'] == 'awaiting_partner_acceptance'
    assert result['result']['transfer_completed'] is False
    manager.act('test-sdk-session', lease['control_token'], operation_id, value, observed_sequence=9)
    assert len(client.calls) == 1
    assert client.calls[0][1] == value


@pytest.mark.parametrize('kind', sorted(FILTERS['trade_change']))
def test_trade_wait_wakes_on_actual_native_event_and_returns_fresh_snapshot(kind):
    epoch = 'a'*32
    event = {'type': kind, 'payload': {'trade_id': OFFER['trade_id'], 'revision': 7}}
    class Journal:
        def request(self, op, character, **kwargs):
            return {'schema': 'native-event-journal/v1', 'cursor': epoch+':1', 'events': [event],
                    'gap': False, 'reset': False, 'has_more': False}
    calls = []
    result = wait_events(Journal(), lambda: calls.append('observe') or {'sequence': 10},
                         since=epoch+':0', event_types=['trade_change'])
    assert result['events'] == [event]
    assert result['wake_reason'] == 'event'
    assert result['snapshot'] == {'sequence': 10}
    assert calls == ['observe']
