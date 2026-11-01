"""Offline capability authorization, transport churn, and local recovery regressions."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import hashlib
import json
import threading
import uuid

import pytest

from presence_acore import mcp_control as module


def operation():
    return str(uuid.uuid4())


class Runtime:
    def __init__(self):
        self.calls = []
        self.stopped = True
        self.restore_error = False
        self.prior = {'full': {'running': True, 'paused': True}, 'social': {'running': False}}

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
        if self.restore_error:
            raise RuntimeError('private restore details')
        return {'full': 'paused', 'social': 'stopped'}


class Client:
    def __init__(self):
        self.calls = []

    def execute(self, character, action, **kwargs):
        self.calls.append((character, action, kwargs))
        return {'status': 'completed'}


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
    manager = module.McpControlManager(runtime, client, control_path=tmp_path / 'control.json',
        receipt_root=private / 'receipts', lock_factory=locked, authorization_mode='lease_token')
    strict = module.McpControlManager(runtime, client, control_path=manager.control_path,
        receipt_root=manager.receipt_root, lock_factory=locked)
    return manager, strict, runtime, client


def test_capability_survives_sdk_churn_without_claiming_session_ownership(setup):
    manager, strict, runtime, client = setup
    lease = manager.take_over('first-sdk', operation())
    token = lease['control_token']
    state = json.loads(manager.control_path.read_text())
    assert state['authorization_mode'] == lease['control_mode'] == 'lease_token'
    assert state['owner_session_hash'] != hashlib.sha256(b'first-sdk').hexdigest()
    assert token not in manager.control_path.read_text()
    before = list(runtime.calls)
    status = manager.status('new-sdk', token)
    assert status['owned_by_control_token'] and not status['owned_by_session']
    assert not manager.status('first-sdk')['owned_by_control_token']
    assert not manager.status('new-sdk', '0' * 64)['owned_by_control_token']
    assert runtime.calls == before
    result = manager.act('new-sdk', token, operation(), {'type': 'stop'})
    assert result['status'] == 'completed' and len(client.calls) == 1
    assert strict.session_closed('first-sdk')['status'] == 'lease_retained'
    assert manager.session_closed('new-sdk')['status'] == 'lease_retained'
    assert manager.status()['state'] == 'active'
    assert manager.hand_back('third-sdk', token, operation())['status'] == 'released'
    assert len([call for call in runtime.calls if isinstance(call, tuple)]) == 1


def test_active_takeover_requires_capability_except_original_operation_retry(setup):
    manager, _, runtime, _ = setup
    original = operation()
    lease = manager.take_over('first-sdk', original)
    before = list(runtime.calls)
    for owner in ('first-sdk', 'new-sdk'):
        fresh = operation()
        with pytest.raises(module.ControlError, match='control_owned'):
            manager.take_over(owner, fresh)
        assert not (manager.receipt_root / (fresh + '.json')).exists()
    with pytest.raises(module.ControlError, match='control_owned'):
        manager.take_over('new-sdk', original)
    with pytest.raises(module.ControlError, match='control_owned'):
        manager.take_over('new-sdk', original, control_token='0' * 64)
    with pytest.raises(module.ControlError, match='control_owned'):
        manager.take_over('first-sdk', original, control_token='0' * 64)
    assert manager.take_over('first-sdk', original)['control_token'] == lease['control_token']
    assert manager.take_over('new-sdk', original, control_token=lease['control_token'])['control_token'] == lease['control_token']
    resumed = manager.take_over('new-sdk', operation(), control_token=lease['control_token'])
    assert resumed['generation'] == lease['generation']
    assert runtime.calls == before
    assert 'control_token' not in json.dumps(manager.action_result(original))
    assert lease['control_token'] not in json.dumps(manager.action_result(original))


@pytest.mark.parametrize('kind', ['action', 'hand_back'])
def test_bad_tokens_cannot_create_or_poison_mutation_receipts(kind, setup):
    manager, _, runtime, client = setup
    lease = manager.take_over('first-sdk', operation())
    op = operation()
    before = list(runtime.calls)
    with pytest.raises(module.ControlError, match='control_not_owned'):
        if kind == 'action':
            manager.act('new-sdk', '0' * 64, op, {'type': 'stop'})
        else:
            manager.hand_back('new-sdk', '0' * 64, op)
    assert not (manager.receipt_root / (op + '.json')).exists()
    assert runtime.calls == before and client.calls == []
    if kind == 'action':
        first = manager.act('new-sdk', lease['control_token'], op, {'type': 'stop'})
        assert manager.act('third-sdk', lease['control_token'], op, {'type': 'stop'}) == first
        assert len(client.calls) == 1
    else:
        assert manager.hand_back('new-sdk', lease['control_token'], op)['status'] == 'released'


def test_previous_generation_token_cannot_replay_action_or_handback(setup):
    manager, _, runtime, client = setup
    old = manager.take_over('first-sdk', operation())
    action_op, release_op = operation(), operation()
    manager.act('first-sdk', old['control_token'], action_op, {'type': 'stop'})
    manager.hand_back('second-sdk', old['control_token'], release_op)
    current = manager.take_over('second-sdk', operation())
    before = list(runtime.calls), list(client.calls)
    assert current['generation'] == old['generation'] + 1
    with pytest.raises(module.ControlError, match='control_not_owned'):
        manager.act('third-sdk', old['control_token'], action_op, {'type': 'stop'})
    with pytest.raises(module.ControlError, match='control_not_owned'):
        manager.hand_back('third-sdk', old['control_token'], release_op)
    assert (runtime.calls, client.calls) == before
    assert manager.status('third-sdk', current['control_token'])['owned_by_control_token']


def test_capability_cannot_authorize_session_mode_or_default_manager(setup):
    manager, strict, _, client = setup
    lease = strict.take_over('first-sdk', operation())
    with pytest.raises(module.ControlError, match='control_not_owned'):
        manager.act('new-sdk', lease['control_token'], operation(), {'type': 'stop'})
    strict.hand_back('first-sdk', lease['control_token'], operation())
    lease = manager.take_over('first-sdk', operation())
    with pytest.raises(module.ControlError, match='control_not_owned'):
        strict.act('first-sdk', lease['control_token'], operation(), {'type': 'stop'})
    assert client.calls == []


def test_remote_status_reports_legacy_lease_actual_session_mode(setup):
    manager, strict, _, _ = setup
    lease = strict.take_over('first-sdk', operation())
    assert 'authorization_mode' not in json.loads(strict.control_path.read_text())
    status = manager.status('new-sdk', lease['control_token'])
    assert status['control_mode'] == 'sdk_session'
    assert not status['owned_by_session'] and not status['owned_by_control_token']


def test_pending_takeover_does_not_expose_capability_to_another_session(setup):
    manager, _, runtime, _ = setup
    runtime.stopped = False
    op = operation()
    pending = manager.take_over('first-sdk', op)
    assert pending['status'] == 'preparing' and 'control_token' not in pending
    with pytest.raises(module.ControlError, match='control_owned'):
        manager.take_over('second-sdk', op)
    runtime.stopped = True
    assert manager.take_over('first-sdk', op)['status'] == 'active'


def test_active_state_written_before_takeover_receipt_is_repaired_without_stopping_again(setup):
    manager, _, runtime, _ = setup
    op = operation()
    lease = manager.take_over('first-sdk', op)
    record = manager._record(op)
    record.update(phase='pending')
    record.pop('response')
    manager._save(record)
    before = list(runtime.calls)
    assert manager.take_over('first-sdk', op)['control_token'] == lease['control_token']
    assert runtime.calls == before


def test_parallel_cross_session_handback_restores_once(setup):
    manager, _, runtime, _ = setup
    lease = manager.take_over('first-sdk', operation())
    entered, proceed = threading.Event(), threading.Event()
    calls = []

    def stop(prior):
        calls.append('stop')
        entered.set()
        assert proceed.wait(3)

    runtime.stop_gracefully = stop
    op = operation()
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(manager.hand_back, 'second-sdk', lease['control_token'], op)
        assert entered.wait(3)
        second = pool.submit(manager.hand_back, 'third-sdk', lease['control_token'], op)
        assert not second.done()
        proceed.set()
        assert first.result(timeout=3) == second.result(timeout=3)
    assert calls == ['stop']
    assert len([call for call in runtime.calls if isinstance(call, tuple)]) == 1


def test_local_recovery_is_exact_generation_and_retries_same_restore_operation(setup):
    manager, strict, runtime, _ = setup
    lease = manager.take_over('first-sdk', operation())
    before = list(runtime.calls)
    with pytest.raises(module.ControlError, match='control_generation_changed'):
        strict.recover(expected_generation=lease['generation'] + 1)
    assert runtime.calls == before
    runtime.restore_error = True
    failed = strict.recover(resume_previous=True, expected_generation=lease['generation'])
    assert failed['reason'] == 'controller_restore_failed'
    runtime.restore_error = False
    released = strict.recover(expected_generation=lease['generation'])
    assert released['restoration']['full'] == 'paused'
    assert released['operation_id'] == failed['operation_id']
    before = list(runtime.calls)
    assert strict.recover(expected_generation=lease['generation']) == released
    assert runtime.calls == before


def test_recovery_requires_matching_private_receipt_owner(setup):
    manager, strict, runtime, _ = setup
    op = operation()
    manager.take_over('first-sdk', op)
    record = manager._record(op)
    record['request']['owner_session_hash'] = '0' * 64
    manager._save(record)
    before = list(runtime.calls)
    with pytest.raises(module.ControlError, match='lease_receipt_unavailable'):
        strict.recover()
    assert runtime.calls == before


def test_delayed_stdio_disconnect_does_not_release_new_generation(setup, monkeypatch):
    _, strict, runtime, _ = setup
    old = strict.take_over('stdio-owner', operation())
    original_release = strict._release

    def delayed_release(*args, **kwargs):
        strict.hand_back('stdio-owner', old['control_token'], operation())
        strict.take_over('stdio-owner', operation())
        return original_release(*args, **kwargs)

    monkeypatch.setattr(strict, '_release', delayed_release)
    # Avoid intercepting explicit handback inside the delay a second time.
    def hand_back(owner, token, op):
        return original_release(module._owner(owner), token, op, resume_previous=True)
    monkeypatch.setattr(strict, 'hand_back', hand_back)
    with pytest.raises(module.ControlError, match='control_generation_changed'):
        strict.session_closed('stdio-owner')
    assert strict.status()['state'] == 'active'
    assert strict.status()['generation'] == old['generation'] + 1


def test_action_result_never_exposes_nested_capability_fields(setup):
    manager, _, _, _ = setup
    op = operation()
    manager.take_over('first-sdk', op)
    record = manager._record(op)
    record['response']['nested'] = {'lease_token': 'secret', 'control_token': 'secret', 'ok': True}
    manager._save(record)
    assert manager.action_result(op)['nested'] == {'ok': True}
