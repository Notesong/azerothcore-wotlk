"""Offline control lifecycle/receipt tests. No real processes, providers or game calls."""
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
import base64
import json
import os
from pathlib import Path
import threading
from types import SimpleNamespace
import uuid

import pytest

from presence_acore import mcp_control as module
from presence_acore.mcp_actions import normalize_action, JSON_SCHEMA


def operation():
    return str(uuid.uuid4())


class Runtime:
    def __init__(self):
        self.calls = []
        self.stopped = True
        self.prior = {'full': {'running': True, 'paused': True}, 'social': {'running': False, 'paused': False}}
    def snapshot(self):
        self.calls.append('snapshot')
        return self.prior
    def stop_gracefully(self, prior):
        self.calls.append('stop')
    def proves_stopped(self):
        self.calls.append('proof')
        return self.stopped
    def restore(self, prior, *, operation_id):
        self.calls.append(('restore', prior, operation_id))
        return {'full': 'paused', 'social': 'stopped'}


class Client:
    def __init__(self):
        self.calls = []
        self.error = None
        self.cached = None
    def execute(self, character, action, **kwargs):
        self.calls.append(('execute', character, action, kwargs))
        if self.error:
            raise self.error
        return {'status': 'completed', 'actual': True}
    def action_result(self, character, request_id):
        self.calls.append(('result', character, request_id))
        return self.cached


@pytest.fixture
def setup(tmp_path):
    private = tmp_path / 'private'
    private.mkdir()
    lock = threading.RLock()
    @contextmanager
    def locked():
        with lock:
            yield
    runtime, client = Runtime(), Client()
    manager = module.McpControlManager(runtime, client, control_path=tmp_path/'control.json',
        receipt_root=private/'receipts', lock_factory=locked)
    return manager, runtime, client


def take(setup, owner='sdk-owner'):
    manager, _, _ = setup
    return manager.take_over(owner, operation())


def test_status_is_read_only_without_storage_or_provider_calls(setup):
    manager, runtime, client = setup
    assert manager.control(action='status') == {'available': True, 'character': 'Vesper',
        'state': 'released', 'generation': 0, 'control_mode': 'sdk_session',
        'owned_by_session': False, 'owned_by_control_token': False}
    assert not manager.receipt_root.exists() and not manager.control_path.exists()
    assert runtime.calls == client.calls == []


def test_takeover_proves_both_stopped_before_returning_token_and_replays_once(setup):
    manager, runtime, _ = setup
    op = operation()
    first = manager.take_over('stdio-'+uuid.uuid4().hex, op)
    owner = manager._record(op)['request']['owner_session_hash']
    assert first['status'] == 'active' and len(first['control_token']) == 64
    assert runtime.calls == ['snapshot', 'stop', 'proof']
    state = json.loads(manager.control_path.read_text())
    assert state['owner_session_hash'] == owner and 'control_token' not in state
    assert first['control_token'] not in manager.control_path.read_text()


def test_same_operation_replay_does_not_stop_again_and_other_session_cannot_take_token(setup):
    manager, runtime, _ = setup
    op = operation()
    first = manager.take_over('owner', op)
    second = manager.take_over('owner', op)
    assert second['control_token'] == first['control_token'] and second['replayed']
    assert runtime.calls == ['snapshot', 'stop', 'proof']
    with pytest.raises(module.ControlError, match='operation_id_conflict'):
        manager.take_over('other', op)
    with pytest.raises(module.ControlError, match='control_owned'):
        manager.take_over('other', operation())
    assert 'control_token' not in manager.action_result(op)


def test_preparing_never_grants_lease_until_actual_dead_proof(setup):
    manager, runtime, _ = setup
    runtime.stopped = False
    op = operation()
    pending = manager.take_over('owner', op)
    assert pending['status'] == 'preparing' and 'control_token' not in pending
    assert manager.status()['state'] == 'preparing'
    runtime.stopped = True
    assert manager.take_over('owner', op)['status'] == 'active'


@pytest.mark.parametrize('owner,token_kind', [('other', 'correct'), ('owner', 'wrong')])
def test_owner_and_opaque_token_are_both_required(owner, token_kind, setup):
    manager, _, client = setup
    lease = manager.take_over('owner', operation())
    token = lease['control_token'] if token_kind == 'correct' else 'a'*64
    with pytest.raises(module.ControlError, match='control_not_owned'):
        manager.act(owner, token, operation(), {'type': 'stop'})
    assert client.calls == []


def test_action_retries_use_original_receipt_not_another_dispatch(setup):
    manager, _, client = setup
    lease = take(setup)
    op = operation()
    action = {'type': 'quest_request_reward', 'target_guid': '1001', 'quest_id': 8330}
    first = manager.act('sdk-owner', lease['control_token'], op, action, observed_sequence=19)
    assert first['status'] == 'completed'
    assert manager.act('sdk-owner', lease['control_token'], op, action, observed_sequence=19) == first
    assert len(client.calls) == 1
    assert client.calls[0][2]['type'] == 'request_reward'
    assert client.calls[0][3] == {'request_id': op, 'observed_sequence': 19}
    with pytest.raises(module.ControlError, match='operation_id_conflict'):
        manager.act('sdk-owner', lease['control_token'], op, {'type': 'stop'})


def test_timeout_is_durable_unknown_never_resent_and_original_cache_resolves(setup):
    manager, _, client = setup
    lease = take(setup)
    error = RuntimeError('credential-text-must-not-leak')
    error.code = 'timeout'
    client.error = error
    op, action = operation(), {'type': 'vendor_buy', 'target_guid': '1001', 'vendor_slot': 1, 'item_id': 22, 'count': 1}
    first = manager.act('sdk-owner', lease['control_token'], op, action)
    assert first['outcome_uncertain'] and first['status'] == 'unknown'
    assert 'credential' not in json.dumps(first)
    assert manager.act('sdk-owner', lease['control_token'], op, action) == first
    assert len(client.calls) == 1
    client.cached = {'request_id': op, 'response': {'v': 1, 'id': op, 'op': 'action', 'character': 'Vesper',
        'ok': True, 'result': {'status': 'completed', 'spent': 50}}}
    result = manager.action_result(op)
    assert result['status'] == 'completed' and not result['outcome_uncertain']
    assert result['result']['spent'] == 50 and len(client.calls) == 2
    assert len([call for call in client.calls if call[0] == 'execute']) == 1


@pytest.mark.parametrize('field,bad', [('id', 'other'), ('op', 'observe'), ('character', 'Aurenne'), ('v', True)])
def test_cached_result_identity_mismatch_never_claims_completion(field, bad, setup):
    manager, _, client = setup
    lease = take(setup)
    client.execute = lambda *a, **kw: {'status': 'accepted'}
    op = operation()
    manager.act('sdk-owner', lease['control_token'], op, {'type': 'stop'})
    envelope = {'v': 1, 'id': op, 'op': 'action', 'character': 'Vesper', 'ok': True, 'result': {'status': 'completed'}}
    envelope[field] = bad
    client.cached = {'request_id': op, 'response': envelope}
    result = manager.action_result(op)
    assert result['outcome_uncertain'] and result['status'] != 'completed'


def test_cached_guard_rejection_preserves_true_original_evidence(setup):
    manager, _, client = setup
    lease = take(setup)
    client.execute = lambda *a, **kw: {'status': 'accepted'}
    op = operation()
    manager.act('sdk-owner', lease['control_token'], op, {'type': 'attack', 'target_guid': '1001'})
    good = {'id': 5, 'request_id': op, 'action_type': 'attack', 'attribution': 'synchronous_action'}
    client.cached = {'request_id': op, 'response': {'v': 1, 'id': op, 'op': 'action', 'character': 'Vesper',
        'ok': False, 'error': {'code': 'protected_target', 'message': 'Moon target',
            'guard_interventions': [good, {**good, 'request_id': 'wrong'}], 'guard_interventions_truncated': True}}}
    result = manager.action_result(op)
    assert result['status'] == 'failed' and result['error']['code'] == 'protected_target'
    assert result['error']['guard_interventions'] == [good]
    assert result['error']['guard_interventions_truncated']


@pytest.mark.parametrize('resume', [True, False])
def test_explicit_handback_releases_then_restores_only_requested_prior_intent(resume, setup):
    manager, runtime, _ = setup
    lease = take(setup)
    op = operation()
    result = manager.control('hand_back', 'sdk-owner', op, lease['control_token'], resume)
    assert result['status'] == 'released' and manager.status()['state'] == 'released'
    restores = [call for call in runtime.calls if isinstance(call, tuple)]
    assert bool(restores) == resume
    assert manager.control('hand_back', 'sdk-owner', op, lease['control_token'], resume) == result
    assert [call for call in runtime.calls if isinstance(call, tuple)] == restores
    with pytest.raises(module.ControlError, match='control_not_active'):
        manager.require_owner('sdk-owner', lease['control_token'])


def test_disconnect_only_releases_own_session_and_is_idempotent(setup):
    manager, runtime, _ = setup
    lease = take(setup)
    before = list(runtime.calls)
    assert manager.session_closed('not-owner')['status'] == 'not_owned'
    assert runtime.calls == before
    assert manager.session_closed('sdk-owner')['status'] == 'released'
    assert manager.session_closed('sdk-owner')['status'] == 'not_owned'
    assert len([call for call in runtime.calls if isinstance(call, tuple)]) == 1


def test_parallel_handback_replay_cannot_stop_the_restored_runner(setup):
    manager, runtime, _ = setup
    lease = take(setup)
    entered, proceed = threading.Event(), threading.Event()
    stop_calls, restored = [], []
    def stop(prior):
        stop_calls.append('stop')
        entered.set()
        assert proceed.wait(3)
        assert not restored, 'a delayed duplicate stop ran after restoration'
    runtime.stop_gracefully = stop
    runtime.restore = lambda prior, **kwargs: restored.append('restored') or {'full': 'paused'}
    op = operation()
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(manager.hand_back, 'sdk-owner', lease['control_token'], op)
        assert entered.wait(3)
        second = pool.submit(manager.hand_back, 'sdk-owner', lease['control_token'], op)
        assert not second.done()
        proceed.set()
        assert first.result(timeout=3) == second.result(timeout=3)
    assert stop_calls == ['stop'] and restored == ['restored']


def test_local_operator_recovery_uses_private_lease_receipt_and_defaults_stopped(setup):
    manager, runtime, _ = setup
    take(setup)
    assert manager.recover()['status'] == 'released'
    assert not any(isinstance(call, tuple) for call in runtime.calls)


def test_malformed_control_fails_closed_without_runtime_calls(setup):
    manager, runtime, _ = setup
    manager.control_path.write_text('{bad')
    with pytest.raises(module.ControlError):
        manager.take_over('owner', operation())
    assert runtime.calls == []


@pytest.mark.parametrize('action', [
    {'type': 'say', 'text': 'Hello ♥', 'channel': 'party'}, {'type': 'emote', 'emote': 'hug', 'target_guid': '1001'},
    {'type': 'emote', 'text': 'checks his map'}, {'type': 'move_to', 'x': 1.5, 'y': 2, 'z': 3, 'map_id': 530},
    {'type': 'stop'}, {'type': 'follow', 'target_guid': '1001', 'distance': 1},
    {'type': 'target', 'target_guid': '0'}, {'type': 'attack', 'target_guid': '1001'},
    {'type': 'cast', 'target_guid': '1001', 'spell_id': 635}, {'type': 'loot', 'target_guid': '1001'},
    {'type': 'interact', 'target_guid': '1001'},
    *[{'type': name, 'target_guid': '1001', 'quest_id': 8330} for name in ('quest_query', 'quest_accept', 'quest_complete', 'quest_request_reward')],
    {'type': 'quest_reward', 'target_guid': '1001', 'quest_id': 8330, 'reward_index': 0},
    {'type': 'party_accept', 'inviter_guid': '1001'}, {'type': 'party_decline', 'inviter_guid': '1001'},
    {'type': 'vendor_list', 'target_guid': '1001', 'page': 0},
    {'type': 'vendor_buy', 'target_guid': '1001', 'item_id': 22, 'vendor_slot': 1, 'count': 255},
    {'type': 'vendor_sell', 'target_guid': '1001', 'item_guid': '2001', 'count': 1},
    {'type': 'vendor_repair', 'target_guid': '1001'},
    {'type': 'vendor_buyback', 'target_guid': '1001', 'item_guid': '2001', 'buyback_slot': 74},
    {'type': 'trainer_list', 'target_guid': '1001'}, {'type': 'train_spell', 'target_guid': '1001', 'spell_id': 635},
    {'type': 'equip_item', 'item_guid': '2001', 'equipment_slot': 22},
    {'type': 'unequip_item', 'item_guid': '2001'}, {'type': 'inspect_item', 'item_guid': '2001'},
    {'type': 'gossip_select', 'target_guid': '1001', 'menu_id': 1, 'option_id': 0},
])
def test_closed_normal_actions_preserve_fields_and_translate_only_quest_aliases(action):
    result = normalize_action(action)
    assert {key: value for key, value in result.items() if key != 'type'} == {
        key: value for key, value in action.items() if key != 'type'}
    assert result['type'] != 'admin'


@pytest.mark.parametrize('action', [None, {'type': 'create'}, {'type': 'wait'},
    {'type': 'stop', 'command': '.levelup 80'}, {'type': 'stop', 'character': 'Aurenne'},
    {'type': 'attack', 'target_guid': '18446744073709551616'}, {'type': 'attack', 'target_guid': '01'},
    {'type': 'attack', 'target_guid': '0'}, {'type': 'attack', 'target_guid': True},
    {'type': 'cast', 'target_guid': '1001', 'spell_id': True},
    {'type': 'move_to', 'x': float('nan'), 'y': 2, 'z': 3},
    {'type': 'move_to', 'x': 10**1000, 'y': 2, 'z': 3},
    {'type': 'emote', 'emote': 'hug', 'text': 'mixed'}, {'type': 'emote', 'text': 'custom', 'target_guid': '1001'},
    {'type': 'say', 'text': '♥'*86}, {'type': 'say', 'text': 'a\nb'},
    {'type': 'quest_reward', 'target_guid': '1001', 'quest_id': 8330, 'reward_index': 6},
    {'type': 'vendor_buy', 'target_guid': '1001', 'item_id': 22, 'vendor_slot': 0, 'count': 1},
    {'type': 'vendor_buy', 'target_guid': '1001', 'item_id': 22, 'vendor_slot': 1, 'count': 256},
])
def test_invalid_or_administration_actions_are_rejected(action):
    with pytest.raises(ValueError):
        normalize_action(action)


def adapter_files(tmp_path, *, inventory=None, full_running=False, paused=True, social_managed=False):
    env_calls = []
    adapter = module.PresenceRuntimeAdapter(tmp_path, inventory=inventory or (lambda: []),
        credentials=lambda config: env_calls.append('credentials') or {'OPENAI_API_KEY': 'private-secret'},
        fingerprint=lambda config: 'unchanged-config-fingerprint',
        sleep=lambda delay: None, stop_timeout=0)
    for lane in ('full', 'social'):
        paths = adapter._paths(lane)
        for path in paths.values():
            path.parent.mkdir(parents=True, exist_ok=True)
        paths['config'].write_text(json.dumps({'game_backend': 'azerothcore' if lane == 'full' or social_managed else 'window',
            'session_state': {'controlled_character': 'Vesper' if lane == 'full' or social_managed else 'OtherCharacter'}}))
        paths['control'].write_bytes(json.dumps({'paused': paused, 'stop': False}).encode()+b'\n')
    python = tmp_path/'backend/.venv/Scripts/python.exe'
    python.parent.mkdir(parents=True, exist_ok=True)
    python.touch()
    return adapter, env_calls


def test_adapter_refuses_running_other_character_before_writing_any_controls(tmp_path):
    adapter, env_calls = adapter_files(tmp_path, inventory=lambda: [{'lane': 'social', 'pid': 1001}])
    before = {lane: adapter._paths(lane)['control'].read_bytes() for lane in ('full', 'social')}
    with pytest.raises(module.ControlError, match='unrelated_controller_running'):
        adapter.snapshot()
    assert before == {lane: adapter._paths(lane)['control'].read_bytes() for lane in ('full', 'social')}
    assert env_calls == []


def test_adapter_stops_only_managed_lanes_and_never_forces_processes(tmp_path):
    adapter, env_calls = adapter_files(tmp_path)
    prior = adapter.snapshot()
    social = adapter._paths('social')['control'].read_bytes()
    config = adapter._paths('full')['config'].read_bytes()
    adapter.stop_gracefully(prior)
    assert json.loads(adapter._paths('full')['control'].read_text())['stop']
    assert adapter._paths('social')['control'].read_bytes() == social
    assert adapter._paths('full')['config'].read_bytes() == config
    assert env_calls == []


def test_adapter_restore_pauses_before_fixed_venv_launch_and_keeps_credentials_private(tmp_path, monkeypatch):
    adapter, env_calls = adapter_files(tmp_path)
    prior = adapter.snapshot()
    prior['full']['running'] = True
    configs = {lane: adapter._paths(lane)['config'].read_bytes() for lane in ('full', 'social')}
    launches = []
    def launch(cmd, **kwargs):
        assert json.loads(adapter._paths('full')['control'].read_text()) == {'paused': True, 'stop': False}
        assert cmd[0] == str(tmp_path/'backend/.venv/Scripts/python.exe')
        assert kwargs['env']['OPENAI_API_KEY'] == 'private-secret'
        launches.append(cmd)
        return SimpleNamespace(pid=2001)
    monkeypatch.setattr(module.subprocess, 'Popen', launch)
    result = adapter.restore(prior, operation_id=operation())
    assert result == {'full': 'paused', 'social': 'unchanged'} and len(launches) == 1
    assert env_calls == ['credentials']
    assert 'private-secret' not in adapter._paths('full')['state'].read_text()
    assert json.loads(adapter._paths('full')['state'].read_text())['config_fingerprint'] == 'unchanged-config-fingerprint'
    assert configs == {lane: adapter._paths(lane)['config'].read_bytes() for lane in ('full', 'social')}


def test_stop_already_requested_before_takeover_is_not_restarted(tmp_path, monkeypatch):
    adapter, env_calls = adapter_files(tmp_path, inventory=lambda: [{'lane': 'full', 'pid': 1001}])
    path = adapter._paths('full')['control']
    path.write_bytes(b'{ "paused": false, "stop": true }\n')
    original = path.read_bytes()
    prior = adapter.snapshot()
    monkeypatch.setattr(module.subprocess, 'Popen', lambda *a, **k: pytest.fail('stop intent was restarted'))
    assert adapter.restore(prior, operation_id=operation())['full'] == 'stopped'
    assert path.read_bytes() == original and not env_calls


def test_restore_after_crash_does_not_spawn_an_already_restored_lane(tmp_path, monkeypatch):
    current = []
    adapter, env_calls = adapter_files(tmp_path, inventory=lambda: list(current))
    prior = adapter.snapshot()
    prior['full']['running'] = True
    op = operation()
    def launch(*args, **kwargs):
        current.append({'lane': 'full', 'pid': 2001})
        return SimpleNamespace(pid=2001)
    monkeypatch.setattr(module.subprocess, 'Popen', launch)
    assert adapter.restore(prior, operation_id=op)['full'] == 'paused'
    assert adapter.restore(prior, operation_id=op)['full'] == 'already_restored'
    assert len(current) == len(env_calls) == 1


def test_exact_process_classification_rejects_substrings_foreign_python_and_config(tmp_path):
    adapter, _ = adapter_files(tmp_path)
    python = str(tmp_path/'backend/.venv/Scripts/python.exe')
    paths = adapter._paths('full')
    args = [python, str(paths['script']), '--config', str(paths['config'])]
    assert adapter.classify_process(args, python) == 'full'
    assert adapter.classify_process([python, '-u', *args[1:]], python) == 'full'
    assert adapter.classify_process([python, '-m', 'tools.game_player', '--config', str(paths['config'])], python) == 'full'
    assert adapter.classify_process([python, '-c', 'print('+repr(str(paths['script']))+')'], python) is None
    with pytest.raises(module.ControlError, match='unexpected_runner_python'):
        adapter.classify_process(args, str(tmp_path/'other-python.exe'))
    with pytest.raises(module.ControlError, match='unexpected_runner_configuration'):
        adapter.classify_process([*args[:-1], str(tmp_path/'other-config.json')], python)
    with pytest.raises(module.ControlError, match='unproven_runner_path'):
        adapter.classify_process([python, 'tools/game_player.py', '--config', str(paths['config'])], python)


def test_windows_venv_base_redirector_requires_trusted_pyvenv_and_exact_venv_argv(tmp_path):
    adapter, _ = adapter_files(tmp_path)
    venv_python = str(tmp_path/'backend/.venv/Scripts/python.exe')
    base = tmp_path/'installed-python/python.exe'
    base.parent.mkdir()
    base.touch()
    cfg = tmp_path/'backend/.venv/pyvenv.cfg'
    cfg.write_text('home = '+str(base.parent)+'\nexecutable = '+str(base)+'\n', encoding='utf-8')
    paths = adapter._paths('full')
    args = [venv_python, str(paths['script']), '--config', str(paths['config'])]
    assert adapter.classify_process(args, str(base)) == 'full'
    assert adapter.classify_process([str(base), *args[1:]], str(base)) == 'full'
    with pytest.raises(module.ControlError, match='unexpected_runner_python'):
        adapter.classify_process([str(tmp_path/'arbitrary-python.exe'), *args[1:]], str(base))
    cfg.write_text('home = '+str(tmp_path/'wrong-home')+'\nexecutable = '+str(base)+'\n', encoding='utf-8')
    with pytest.raises(module.ControlError, match='unexpected_runner_python'):
        adapter.classify_process(args, str(base))


def test_redirector_and_exact_base_child_are_one_runner_but_duplicates_stay_separate():
    root = {'lane': 'full', 'pid': 1001, 'parent_pid': 50, 'redirector': True,
        'argv': ['fixed-venv', 'fixed-script', '--config', 'fixed-config']}
    child = {**root, 'pid': 1002, 'parent_pid': 1001, 'redirector': False,
        'argv': ['configured-base', *root['argv'][1:]]}
    assert module.PresenceRuntimeAdapter.collapse_redirectors([root, child]) == [
        {'lane': 'full', 'pid': 1001, 'member_pids': [1001, 1002]}]
    duplicate = {**child, 'pid': 2001, 'parent_pid': 70}
    assert len(module.PresenceRuntimeAdapter.collapse_redirectors([root, child, duplicate])) == 2
    foreign_child = {**child, 'argv': ['different-command']}
    assert len(module.PresenceRuntimeAdapter.collapse_redirectors([root, foreign_child])) == 2


@pytest.mark.skipif(os.name != 'nt', reason='Windows parser only; no process is launched')
def test_windows_command_line_parser_retains_quoted_exact_arguments():
    assert module.PresenceRuntimeAdapter._argv('"C:\\Program Files\\python.exe" "C:\\Some Place\\player.py" --config "C:\\Some Place\\c.json"') == [
        'C:\\Program Files\\python.exe', 'C:\\Some Place\\player.py', '--config', 'C:\\Some Place\\c.json']
