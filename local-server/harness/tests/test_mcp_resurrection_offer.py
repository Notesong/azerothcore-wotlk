"""Offline offered-resurrection MCP contract checks; no providers or live game actions."""
from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import uuid

import pytest

from presence_acore.event_wait import _matches, wait_events
from presence_acore.mcp_actions import ACTION_SCHEMA, normalize_action
from presence_acore.mcp_control import ControlError, McpControlManager
from presence_acore.mcp_server import Inspector, _additional_tools

NONCE = '0123456789abcdef0123456789abcdef'
ACTION = {'type': 'resurrection_respond', 'resurrection_offer_id': NONCE,
          'caster_guid': '18446744073709551615', 'choice': 'accept'}
INVALID = [
    {'type': ACTION['type']},
    *[{**ACTION, 'resurrection_offer_id': value} for value in
      (42, True, None, '', 'a'*31, 'a'*33, 'A'*32, 'g'*32, NONCE+'\n')],
    *[{**ACTION, 'caster_guid': value} for value in
      (42, True, None, '', '0', '01', '-1', '+1', ' 42', '42 ', '١٢٣', '4.2', '4e2',
       '18446744073709551616')],
    *[{**ACTION, 'choice': value} for value in (True, None, '', 'resurrect', 'ACCEPT', 'pass')],
    *[{**ACTION, key: 1} for key in ('target_guid', 'spell_id', 'force', 'map_id', 'restore_health',
        'request_revision', 'expires_at', 'character', 'operation_id', 'control_token')],
    {**ACTION, 'type': 'resurrection_accept'}, {**ACTION, 'type': 'resurrect'},
]


@pytest.mark.parametrize('value', INVALID)
def test_resurrection_respond_rejects_malformed_or_authority_override_arguments(value):
    with pytest.raises(ValueError, match='invalid_action'):
        normalize_action(value)


def test_resurrection_response_closed_discovery_schema_preserves_exact_identity_and_choices():
    for choice in ('accept', 'decline'):
        for caster_guid in ('1', '42', '18446744073709551615'):
            value = {**ACTION, 'choice': choice, 'caster_guid': caster_guid}
            assert normalize_action(value) == value
    variant = next(row for row in ACTION_SCHEMA['oneOf']
                   if row['properties']['type']['const'] == ACTION['type'])
    assert set(variant['properties']) == {'type', 'resurrection_offer_id', 'caster_guid', 'choice'}
    assert set(variant['required']) == set(variant['properties'])
    assert variant['additionalProperties'] is False
    assert variant['properties']['resurrection_offer_id']['pattern'] == '^[a-f0-9]{32}$'
    tool = next(row for row in _additional_tools() if row['name'] == 'wow_act')
    assert 'resurrection_respond(resurrection_offer_id, caster_guid, choice)' in tool['description']
    assert 'Accepted is pending' in tool['description']
    assert 'declined only means the offer was declined' in tool['description']


class Runtime:
    def snapshot(self): return {}
    def stop_gracefully(self, prior): pass
    def proves_stopped(self): return True
    def restore(self, prior, **kwargs): return {}


def receipt(operation_id, action=None, **fields):
    action = action or ACTION
    return {'operation': action['type'], 'request_id': operation_id,
        **{key: action[key] for key in ('resurrection_offer_id', 'caster_guid', 'choice')},
        'status': 'accepted', 'pending': True, 'terminal': False,
        'alive_after': False, 'is_ghost_after': True, 'recovered': False, 'declined': False, **fields}


class Client:
    def __init__(self):
        self.calls, self.polls = [], []
        self.fields, self.polled = {}, None
        self.ok = True
        self.timeout = False

    def execute(self, character, action, **kwargs):
        self.calls.append((character, action, kwargs))
        if self.timeout:
            raise ControlError('timeout')
        return receipt(kwargs['request_id'], action, **self.fields)

    def action_result(self, character, operation_id):
        self.polls.append(operation_id)
        return {'request_id': operation_id, 'response': {'v': 1, 'id': operation_id, 'op': 'action',
            'character': character, 'ok': self.ok, 'result': self.polled,
            **({'error': {'code': 'stale_resurrection_offer'}} if not self.ok else {})}}


def manager_at(tmp_path, client):
    (tmp_path / 'private').mkdir(exist_ok=True)
    @contextmanager
    def locked(): yield
    return McpControlManager(Runtime(), client, control_path=tmp_path / 'control.json',
        receipt_root=tmp_path / 'private/receipts', lock_factory=locked, authorization_mode='lease_token')


def test_pending_response_uses_existing_capability_and_original_uuid_across_transport_and_restart(tmp_path):
    client = Client()
    manager = manager_at(tmp_path, client)
    with pytest.raises(ControlError):
        manager.act('transport', 'a'*64, str(uuid.uuid4()), ACTION)
    lease = manager.take_over('first-transport', str(uuid.uuid4()))
    operation_id = str(uuid.uuid4())
    first = manager.act('second-transport', lease['control_token'], operation_id, ACTION, observed_sequence=41)
    assert first['status'] == 'accepted' and first['result']['recovered'] is False
    assert first['result']['alive_after'] is False and first['result']['terminal'] is False
    manager = manager_at(tmp_path, client)
    assert manager.act('third-transport', lease['control_token'], operation_id,
                       ACTION, observed_sequence=41) == first
    with pytest.raises(ControlError, match='operation_id_conflict'):
        manager.act('third-transport', lease['control_token'], operation_id,
                    {**ACTION, 'choice': 'decline'}, observed_sequence=41)
    with pytest.raises(ControlError):
        manager.act('third-transport', 'f'*64, str(uuid.uuid4()), ACTION)
    assert client.calls == [('Vesper', ACTION, {'request_id': operation_id, 'observed_sequence': 41})]
    client.polled = receipt(operation_id, status='completed', pending=False, terminal=True,
        recovered=True, alive_after=True, is_ghost_after=False)
    result = manager.action_result(operation_id)
    assert result['status'] == 'completed' and result['result']['recovered'] is True
    assert client.polls == [operation_id]


@pytest.mark.parametrize('fields', [
    {'operation': 'reclaim_corpse'}, {'request_id': str(uuid.uuid4())},
    {'resurrection_offer_id': 'f'*32}, {'caster_guid': '42'}, {'caster_guid': 42}, {'choice': 'decline'},
    {'pending': True}, {'terminal': False}, {'recovered': False}, {'recovered': 1},
    {'alive_after': False}, {'alive_after': None}, {'is_ghost_after': True}, {'declined': True},
])
def test_accept_cannot_report_success_from_mismatched_pending_or_unrecovered_receipt(tmp_path, fields):
    client = Client()
    manager = manager_at(tmp_path, client)
    lease = manager.take_over('transport', str(uuid.uuid4()))
    operation_id = str(uuid.uuid4())
    client.fields = {'status': 'completed', 'pending': False, 'terminal': True,
        'recovered': True, 'alive_after': True, 'is_ghost_after': False, **fields}
    result = manager.act('transport', lease['control_token'], operation_id, ACTION)
    assert result['status'] == 'unknown' and result['outcome_uncertain'] is True
    assert 'result' not in result
    client.polled = receipt(operation_id, **client.fields)
    result = manager.action_result(operation_id)
    assert result['status'] == 'unknown' and result['outcome_uncertain'] is True
    assert result['resolution_error'] == 'original_result_unavailable'
    assert len(client.calls) == 1


def test_decline_completes_without_resurrection_and_offline_rejection_keeps_unknown_life_facts(tmp_path):
    client = Client()
    manager = manager_at(tmp_path, client)
    lease = manager.take_over('transport', str(uuid.uuid4()))
    operation_id = str(uuid.uuid4())
    decline = {**ACTION, 'choice': 'decline'}
    client.fields = {'status': 'completed', 'pending': False, 'terminal': True, 'declined': True}
    result = manager.act('transport', lease['control_token'], operation_id, decline)
    assert result['status'] == 'completed' and result['result']['declined'] is True
    assert result['result']['recovered'] is False and result['result']['alive_after'] is False
    client.timeout = True
    operation_id = str(uuid.uuid4())
    assert manager.act('transport', lease['control_token'], operation_id, ACTION)['status'] == 'unknown'
    client.ok = False
    client.polled = receipt(operation_id, status='failed', pending=False, terminal=True,
        alive_after=None, is_ghost_after=None, reason='not_attached')
    result = manager.action_result(operation_id)
    assert result['status'] == 'failed' and result['result']['alive_after'] is None
    assert result['error'] == {'code': 'stale_resurrection_offer'}
    assert result['outcome_uncertain'] is False


def test_timeout_response_is_durable_before_dispatch_and_never_resends_original_uuid(tmp_path):
    client = Client()
    client.timeout = True
    manager = manager_at(tmp_path, client)
    lease = manager.take_over('transport', str(uuid.uuid4()))
    operation_id = str(uuid.uuid4())
    first = manager.act('transport', lease['control_token'], operation_id, ACTION)
    assert first['status'] == 'unknown'
    manager = manager_at(tmp_path, client)
    assert manager.act('next-transport', lease['control_token'], operation_id, ACTION) == first
    assert len(client.calls) == 1


def test_explicit_unknown_phase_remains_uncertain_on_original_acceptance_and_receipt_poll(tmp_path):
    client = Client()
    client.fields = {'phase': 'outcome_unknown'}
    manager = manager_at(tmp_path, client)
    lease = manager.take_over('transport', str(uuid.uuid4()))
    operation_id = str(uuid.uuid4())
    first = manager.act('transport', lease['control_token'], operation_id, ACTION)
    assert first['status'] == 'accepted' and first['outcome_uncertain'] is True
    client.polled = receipt(operation_id, phase='outcome_unknown')
    polled = manager.action_result(operation_id)
    assert polled['status'] == 'accepted' and polled['outcome_uncertain'] is True
    assert polled['result']['recovered'] is False and len(client.calls) == 1


def offer():
    return {'resurrection_offer_id': NONCE, 'caster_guid': ACTION['caster_guid'],
        'caster_name': 'Aurenne', 'caster_is_player': True, 'spell_id': None, 'spell_name': None,
        'request_revision': '18446744073709551615', 'received_at': '2026-11-03T22:00:00Z', 'age_ms': 100,
        'expires_at': None, 'remaining_ms': None, 'expiry_policy': 'native_request_has_no_timeout',
        'restore_health': 120, 'restore_mana': 80,
        'destination': {'map_id': 530, 'x': 10332.5, 'y': -6387.25, 'z': 32.5, 'instance_id': None},
        'available': True, 'blocked_reason': None, 'next_actions': [ACTION, {**ACTION, 'choice': 'decline'}]}


def test_full_offer_facts_remain_unclipped_and_do_not_require_caster_visibility_in_mcp_observation():
    epoch = 'c'*32
    observation = {'sequence': 41, 'self': {'guid': '102', 'alive': False, 'is_ghost': True},
        'nearby_units': [], 'recovery': {'resurrection_offer': offer(), 'resurrection_receipt': None}}
    class ReadClient:
        def request(self, operation, character, **kwargs):
            assert operation == 'events'
            return {'schema': 'native-event-journal/v1', 'cursor': epoch+':70', 'events': []}
        def observe(self, character, **kwargs): return deepcopy(observation)
    value = Inspector(ReadClient()).live()
    assert value['available'] is True and value['observation'] == observation


def test_existing_death_wait_wakes_for_offer_changes_then_collects_fresh_life_state():
    epoch = 'c'*32
    event = {'type': 'resurrection_offer_changed', 'payload': {'resurrection_offer_id': NONCE,
        'change': 'available', 'recovered': False}}
    assert _matches(event, ['death'])
    assert not _matches(event, ['quest_change'])
    class Journal:
        def request(self, operation, character, **kwargs):
            assert operation == 'events' and kwargs['since'] == epoch+':70'
            return {'schema': 'native-event-journal/v1', 'cursor': epoch+':71', 'events': [event]}
    calls = []
    value = wait_events(Journal(), lambda: calls.append('fresh') or {'sequence': 42,
        'recovery': {'resurrection_offer': None}, 'self': {'alive': True}},
        since=epoch+':70', event_types=['death'])
    assert value['events'] == [event] and value['snapshot']['self']['alive'] is True
    assert value['snapshot']['recovery']['resurrection_offer'] is None and calls == ['fresh']


def test_resurrection_preview_helper_is_fixed_and_isolated_from_controllers_and_providers(tmp_path):
    tools = tmp_path / 'backend/tools'
    tools.mkdir(parents=True)
    (tools / 'game_player_native_resurrection.py').write_text(
        'def resurrection_context(value): return value["recovery"]\n', encoding='utf-8')
    (tools / 'game_player_native_context.py').write_text(
        'from tools.game_player_native_resurrection import resurrection_context\n'
        'def compact_native_observation(value, mode="gameplay"): return resurrection_context(value)\n',
        encoding='utf-8')
    value = {'recovery': {'resurrection_offer': offer()}}
    code = ('import sys,json,builtins\nfrom pathlib import Path\n'
        f'sys.path.insert(0,{str(Path(__file__).resolve().parents[1])!r})\n'
        'from presence_acore.model_context import _projection\n'
        'before=set(sys.modules); original=builtins.__import__\n'
        f'fn=_projection(Path({str(tmp_path)!r}))\n'
        f'value=fn(json.loads({json.dumps(value)!r}))\n'
        f'assert value["resurrection_offer"]["resurrection_offer_id"]=={NONCE!r}\n'
        'assert value["resurrection_offer"]["spell_id"] is None\n'
        'assert builtins.__import__ is original\n'
        'assert not any(n.startswith(("tools.","app.","openai","anthropic")) for n in set(sys.modules)-before)\n')
    subprocess.run([sys.executable, '-I', '-S', '-B', '-c', code], check=True, capture_output=True, text=True)
