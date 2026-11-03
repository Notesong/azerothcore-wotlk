"""Ordinary paid flight paths with exact identities and durable MCP uncertainty fences."""
from contextlib import contextmanager
import json
from pathlib import Path
import subprocess
import sys
import uuid

import pytest

from presence_acore.event_wait import _matches, wait_events
from presence_acore.mcp_actions import ACTION_SCHEMA, normalize_action
from presence_acore.mcp_control import ControlError, McpControlManager
from presence_acore.mcp_server import _additional_tools

NONCE = '0123456789abcdef0123456789abcdef'
LIST = {'type': 'taxi_list', 'target_guid': '17379390962022785123'}
START = {'type': 'taxi_start', 'target_guid': LIST['target_guid'],
    'taxi_menu_id': NONCE, 'destination_node_id': 82}
INVALID = [
    {'type': 'taxi_list'}, {**LIST, 'target_guid': '0'}, {**LIST, 'target_guid': '18446744073709551616'},
    {'type': 'taxi_start', 'target_guid': LIST['target_guid']},
    *[{**START, 'taxi_menu_id': value} for value in (
        42, True, None, '', 'a'*31, 'a'*33, 'A'*32, 'g'*32, NONCE+'\n')],
    *[{**START, 'destination_node_id': value} for value in (0, -1, True, None, 1.5, '82', 4294967296)],
    *[{**START, key: 1} for key in ('menu_id', 'path_id', 'route_node_ids', 'price_copper', 'free',
        'force', 'teleport', 'character', 'operation_id', 'control_token')],
    {**LIST, 'taxi_menu_id': NONCE}, {**LIST, 'destination_node_id': 82},
]


@pytest.mark.parametrize('value', INVALID)
def test_taxi_actions_reject_spoofed_authority_malformed_nonce_and_route_overrides(value):
    with pytest.raises(ValueError, match='invalid_action'):
        normalize_action(value)


def test_closed_discovery_schema_and_unchanged_numeric_gossip_menu():
    for value in (LIST, START, {**START, 'destination_node_id': 4294967295}):
        assert normalize_action(value) == value
    assert normalize_action({'type': 'gossip_select', 'target_guid': '12', 'menu_id': 3, 'option_id': 0})
    variant = next(row for row in ACTION_SCHEMA['oneOf'] if row['properties']['type']['const'] == 'taxi_start')
    assert set(variant['properties']) == {'type', 'target_guid', 'taxi_menu_id', 'destination_node_id'}
    assert variant['additionalProperties'] is False
    assert variant['properties']['taxi_menu_id']['pattern'] == '^[a-f0-9]{32}$'
    tool = next(row for row in _additional_tools() if row['name'] == 'wow_act')
    assert 'taxi_start(target_guid, taxi_menu_id, destination_node_id)' in tool['description']
    assert 'Accepted or in_flight is not arrival' in tool['description']


class Runtime:
    def snapshot(self): return {}
    def stop_gracefully(self, prior): pass
    def proves_stopped(self): return True
    def restore(self, prior, **kwargs): return {}


class Client:
    def __init__(self, *, timeout=False):
        self.calls = []
        self.timeout = timeout
        self.receipt = None
        self.ok = True

    def execute(self, character, action, **kwargs):
        self.calls.append((character, action, kwargs))
        if self.timeout:
            raise ControlError('timeout')
        return {**action, 'operation': action['type'], 'request_id': kwargs['request_id'],
            'status': 'accepted', 'pending': True, 'terminal': False, 'arrived': False}

    def action_result(self, character, operation_id):
        return {'request_id': operation_id, 'response': {'v': 1, 'id': operation_id, 'op': 'action',
            'character': character, 'ok': self.ok, 'result': self.receipt,
            **({'error': {'code': 'not_enough_money', 'message': 'Normal fare rejected.'}} if not self.ok else {})}}


def manager_at(tmp_path, client):
    (tmp_path / 'private').mkdir(exist_ok=True)
    @contextmanager
    def locked(): yield
    return McpControlManager(Runtime(), client, control_path=tmp_path / 'control.json',
        receipt_root=tmp_path / 'private/receipts', lock_factory=locked, authorization_mode='lease_token')


def terminal(operation_id, **fields):
    return {**START, 'operation': 'taxi_start', 'request_id': operation_id,
        'status': 'completed', 'pending': False, 'terminal': True, 'arrived': True, **fields}


@pytest.mark.parametrize('timeout', [False, True])
def test_paid_start_fence_survives_restart_and_blocks_new_operations_until_exact_terminal(tmp_path, timeout):
    client = Client(timeout=timeout)
    manager = manager_at(tmp_path, client)
    lease = manager.take_over('first-transport', str(uuid.uuid4()))
    operation_id = str(uuid.uuid4())
    first = manager.act('second-transport', lease['control_token'], operation_id, START, observed_sequence=8)
    assert first['status'] == ('unknown' if timeout else 'accepted')
    assert manager.status()['pending_taxi_operation_id'] == operation_id
    manager = manager_at(tmp_path, client)
    assert manager.act('third-transport', lease['control_token'], operation_id, START, observed_sequence=8) == first
    for action in (START, LIST, {'type': 'move_to', 'x': 1, 'y': 2, 'z': 3}, {'type': 'stop'}):
        with pytest.raises(ControlError, match='taxi_start_unresolved'):
            manager.act('third-transport', lease['control_token'], str(uuid.uuid4()), action)
    assert len(client.calls) == 1
    assert client.calls[0] == ('Vesper', START, {'request_id': operation_id, 'observed_sequence': 8})
    client.receipt = terminal(operation_id)
    assert manager.action_result(operation_id)['result']['arrived'] is True
    assert manager.status().get('pending_taxi_operation_id') is None
    client.timeout = False
    manager.act('third-transport', lease['control_token'], str(uuid.uuid4()), LIST)
    assert len(client.calls) == 2


@pytest.mark.parametrize('fields', [
    {'status': 'accepted'}, {'terminal': False}, {'pending': True}, {'arrived': False},
    {'operation': 'move_to'}, {'request_id': str(uuid.uuid4())}, {'target_guid': '123'},
    {'taxi_menu_id': 'f'*32}, {'destination_node_id': 83}, {'destination_node_id': True},
])
def test_pending_or_mismatched_flight_results_cannot_clear_paid_fence(tmp_path, fields):
    client = Client()
    manager = manager_at(tmp_path, client)
    lease = manager.take_over('owner', str(uuid.uuid4()))
    operation_id = str(uuid.uuid4())
    manager.act('owner', lease['control_token'], operation_id, START)
    client.receipt = terminal(operation_id, **fields)
    assert manager.action_result(operation_id)['status'] != 'completed'
    assert manager.status()['pending_taxi_operation_id'] == operation_id
    with pytest.raises(ControlError, match='taxi_start_unresolved'):
        manager.act('owner', lease['control_token'], str(uuid.uuid4()), LIST)
    assert len(client.calls) == 1


def test_known_rejection_clears_only_original_flight_and_changed_uuid_payload_does_not_resend(tmp_path):
    client = Client()
    manager = manager_at(tmp_path, client)
    lease = manager.take_over('owner', str(uuid.uuid4()))
    operation_id = str(uuid.uuid4())
    manager.act('owner', lease['control_token'], operation_id, START)
    with pytest.raises(ControlError, match='operation_id_conflict'):
        manager.act('owner', lease['control_token'], operation_id, {**START, 'destination_node_id': 83})
    client.receipt = terminal(operation_id, status='failed', arrived=False, phase='rejected', reason='no_money')
    client.ok = False
    assert manager.action_result(operation_id)['status'] == 'failed'
    assert manager.status().get('pending_taxi_operation_id') is None
    assert len(client.calls) == 1


def test_prepared_receipt_crash_already_fences_before_dispatch(tmp_path):
    client = Client()
    manager = manager_at(tmp_path, client)
    lease = manager.take_over('owner', str(uuid.uuid4()))
    operation_id = str(uuid.uuid4())
    manager._new(operation_id, 'action', {'action': START})
    with pytest.raises(ControlError, match='taxi_start_unresolved'):
        manager.act('owner', lease['control_token'], str(uuid.uuid4()), LIST)
    assert manager.status()['pending_taxi_operation_id'] == operation_id
    assert client.calls == []


def test_pending_flight_allows_speech_and_confirmed_flight_keeps_loot_votes_available(tmp_path):
    client = Client()
    manager = manager_at(tmp_path, client)
    lease = manager.take_over('owner', str(uuid.uuid4()))
    operation_id = str(uuid.uuid4())
    manager.act('owner', lease['control_token'], operation_id, START)
    manager.act('owner', lease['control_token'], str(uuid.uuid4()), {'type': 'say', 'text': 'Still flying.'})
    vote = {'type': 'loot_roll', 'roll_id': 'a'*32, 'choice': 'pass'}
    with pytest.raises(ControlError, match='taxi_start_unresolved'):
        manager.act('owner', lease['control_token'], str(uuid.uuid4()), vote)
    client.receipt = terminal(operation_id, status='accepted', pending=True, terminal=False,
        arrived=False, phase='in_flight')
    manager.action_result(operation_id)
    manager.act('owner', lease['control_token'], str(uuid.uuid4()), vote)
    assert len(client.calls) == 3
    assert manager.status()['pending_taxi_operation_id'] == operation_id


def test_accepted_ambiguous_dispatch_is_still_explicitly_uncertain(tmp_path):
    client = Client()
    normal_execute = client.execute
    def ambiguous(*args, **kwargs):
        return {**normal_execute(*args, **kwargs), 'phase': 'outcome_unknown'}
    client.execute = ambiguous
    manager = manager_at(tmp_path, client)
    lease = manager.take_over('owner', str(uuid.uuid4()))
    operation_id = str(uuid.uuid4())
    value = manager.act('owner', lease['control_token'], operation_id, START)
    assert value['status'] == 'accepted' and value['outcome_uncertain'] is True
    client.receipt = terminal(operation_id, status='accepted', pending=True, terminal=False,
        arrived=False, phase='outcome_unknown')
    assert manager.action_result(operation_id)['outcome_uncertain'] is True
    assert manager.status()['pending_taxi_operation_id'] == operation_id


def test_taxi_wait_filters_keep_phase_and_always_fetch_fresh_snapshot():
    epoch = 'c'*32
    class Journal:
        def request(self, op, character, **args):
            assert op == 'events' and character == 'Vesper' and args['since'] == epoch+':3'
            return {'schema': 'native-event-journal/v1', 'cursor': epoch+':4',
                'events': [{'type': 'taxi_arrived', 'payload': {'request_id': 'original'}}]}
    for kind in ('taxi_node_learned', 'taxi_menu_opened', 'taxi_started', 'taxi_arrived', 'taxi_interrupted'):
        assert _matches({'type': kind}, ['travel_change'])
        assert _matches({'type': kind}, ['arrival']) is (kind == 'taxi_arrived')
        assert not _matches({'type': kind}, ['quest_change'])
    value = wait_events(Journal(), lambda: {'sequence': 9, 'taxi': {'in_flight': False}},
        since=epoch+':3', event_types=['travel_change'])
    assert value['wake_reason'] == 'event' and value['cursor'] == epoch+':4'
    assert value['snapshot'] == {'sequence': 9, 'taxi': {'in_flight': False}}


def test_taxi_preview_helper_loads_without_provider_or_autonomous_runtime_imports(tmp_path):
    tools = tmp_path / 'backend/tools'
    tools.mkdir(parents=True)
    (tools / 'game_player_native_taxi.py').write_text(
        'def taxi_context(value): return value["taxi"]\n', encoding='utf-8')
    (tools / 'game_player_native_context.py').write_text(
        'from tools.game_player_native_taxi import taxi_context\n'
        'def compact_native_observation(value, mode="gameplay"): return taxi_context(value)\n', encoding='utf-8')
    observation = {'taxi': {'in_flight': False, 'menu': {'taxi_menu_id': NONCE,
        'destinations': [{'destination_node_id': 82, 'price_copper': 120, 'route_node_ids': [81, 82]}]}}}
    code = ('import sys,json,builtins\nfrom pathlib import Path\n'
        f'sys.path.insert(0,{str(Path(__file__).resolve().parents[1])!r})\n'
        'from presence_acore.model_context import _projection\n'
        'before=set(sys.modules); original=builtins.__import__\n'
        f'fn=_projection(Path({str(tmp_path)!r}))\n'
        f'value=fn(json.loads({json.dumps(observation)!r}))\n'
        f'assert value["menu"]["taxi_menu_id"]=={NONCE!r}\n'
        'assert value["menu"]["destinations"][0]["price_copper"]==120\n'
        'assert builtins.__import__ is original\n'
        'assert not any(n.startswith(("tools.","app.","openai","anthropic")) for n in set(sys.modules)-before)\n')
    subprocess.run([sys.executable, '-I', '-S', '-B', '-c', code], check=True, capture_output=True, text=True)
