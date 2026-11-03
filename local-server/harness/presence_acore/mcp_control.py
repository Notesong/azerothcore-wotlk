"""Explicit Vesper control with durable, generation-bound ownership.

No model calls, lease expiry, arbitrary commands, or forced process termination.
Runtime actions and credentials are resolved locally only during authorized
takeover/handback. Tests inject the runtime, transport, lock and storage paths.
"""
from __future__ import annotations

import base64
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any
import uuid

from .mcp_actions import normalize_action


PRESENCE_ROOT = Path('C:/Files/Programs/Codex/Presence/working')
PRIVATE_ROOT = Path('C:/Games/AzerothCore/local-qwen-private/mcp-control')
CONTROL_SCHEMA = 'native-mcp-control/v1'
CHARACTER = 'Vesper'
_STATES = {'preparing', 'active', 'releasing', 'released'}
_AUTHORIZATION_MODES = {'sdk_session', 'lease_token'}
_TOKEN = re.compile(r'[a-f0-9]{64}')
_UNCERTAIN = {'timeout', 'connection_failed', 'connection_closed', 'invalid_response',
    'response_mismatch', 'response_too_large'}
_TEST_LIFECYCLE_LOCKS: dict[str, Any] = {}
_TEST_LIFECYCLE_LOCKS_MUTEX = threading.Lock()


class ControlError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _owner(value: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 4096:
        raise ControlError('sdk_session_required')
    return _hash(value)


def _operation(value: str) -> str:
    try:
        if not isinstance(value, str):
            raise ValueError()
        return str(uuid.UUID(value))
    except (ValueError, AttributeError):
        raise ControlError('invalid_operation_id') from None


def _strict(raw: bytes) -> Any:
    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result:
                raise ValueError('duplicate_key')
            result[key] = value
        return result
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError('nonfinite_json')))


def _plain(path: Path) -> Path:
    if path.is_symlink() or path.exists() and getattr(path.lstat(), 'st_file_attributes', 0) & 0x400:
        raise ControlError('unsafe_control_storage')
    return path


def _read(path: Path) -> dict[str, Any] | None:
    try:
        value = _strict(_plain(path).read_bytes())
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except FileNotFoundError:
        return None
    except (OSError, ValueError, UnicodeError, RecursionError):
        raise ControlError('control_storage_unavailable') from None


def _write(path: Path, value: dict[str, Any]) -> None:
    _write_bytes(path, json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8'))


def _write_bytes(path: Path, raw: bytes) -> None:
    _plain(path.parent)
    _plain(path)
    descriptor, temporary_name = tempfile.mkstemp(prefix='.mcp-control-', dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        _plain(path)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _safe_result(value: dict[str, Any]) -> dict[str, Any]:
    def clean(item):
        if isinstance(item, dict):
            return {key: clean(child) for key, child in item.items()
                if key not in {'control_token', 'lease_token'}}
        if isinstance(item, list):
            return [clean(child) for child in item]
        return item
    return clean(value)


class McpControlManager:
    def __init__(self, runtime=None, client=None, *, control_path: Path | None = None,
                 receipt_root: Path | None = None, lock_factory=None, lifecycle_lock_factory=None,
                 authorization_mode: str = 'sdk_session') -> None:
        if not isinstance(authorization_mode, str) or authorization_mode not in _AUTHORIZATION_MODES:
            raise ControlError('invalid_authorization_mode')
        self.authorization_mode = authorization_mode
        self.runtime = runtime if runtime is not None else PresenceRuntimeAdapter()
        self.client = client
        self.control_path = Path(control_path) if control_path else PRESENCE_ROOT / 'backend/data/runtime-game-player-mcp-control.json'
        self.receipt_root = Path(receipt_root) if receipt_root else PRIVATE_ROOT
        if lock_factory is None:
            helper_path = PRESENCE_ROOT / 'backend/app/game_player_native_mcp_control.py'
            spec = importlib.util.spec_from_file_location('_presence_mcp_control_interlock', helper_path)
            helper = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(helper)
            lock_factory = lambda: helper.mcp_control_lock(self.control_path)
            if lifecycle_lock_factory is None:
                lifecycle_path = self.control_path.with_name(self.control_path.name + '.lifecycle')
                lifecycle_lock_factory = lambda: helper.mcp_control_lock(lifecycle_path, timeout_ms=60_000)
        self.lock_factory = lock_factory
        if lifecycle_lock_factory is None:
            # Injected offline runtimes need no host Win32 namespace. Production
            # always uses the separate cross-process helper mutex above.
            with _TEST_LIFECYCLE_LOCKS_MUTEX:
                lifecycle_lock = _TEST_LIFECYCLE_LOCKS.setdefault(str(self.control_path.resolve()), threading.RLock())
            @contextmanager
            def test_lifecycle_lock():
                with lifecycle_lock:
                    yield
            lifecycle_lock_factory = test_lifecycle_lock
        self.lifecycle_lock_factory = lifecycle_lock_factory

    def _state(self) -> dict[str, Any]:
        state = _read(self.control_path)
        if state is None:
            return {'state': 'released', 'generation': 0}
        if (state.get('schema') != CONTROL_SCHEMA or state.get('character') != CHARACTER
                or not isinstance(state.get('state'), str) or state['state'] not in _STATES
                or type(state.get('generation')) is not int or state['generation'] < 1
                or not isinstance(state.get('authorization_mode', 'sdk_session'), str)
                or state.get('authorization_mode', 'sdk_session') not in _AUTHORIZATION_MODES
                or not _TOKEN.fullmatch(str(state.get('owner_session_hash', '')))
                or not _TOKEN.fullmatch(str(state.get('token_hash', '')))):
            raise ControlError('invalid_control_state')
        return state

    def _record_path(self, operation_id: str) -> Path:
        _plain(self.receipt_root.parent)
        if not self.receipt_root.parent.is_dir():
            raise ControlError('private_receipt_parent_missing')
        _plain(self.receipt_root)
        self.receipt_root.mkdir(exist_ok=True)
        return self.receipt_root / (operation_id + '.json')

    def _record(self, operation_id: str) -> dict[str, Any] | None:
        value = _read(self._record_path(operation_id))
        if value is not None and (value.get('schema') != 'native-mcp-operation/v1'
                or value.get('operation_id') != operation_id):
            raise ControlError('invalid_operation_receipt')
        return value

    def _save(self, record: dict[str, Any]) -> None:
        _write(self._record_path(record['operation_id']), record)

    @staticmethod
    def _taxi_identity(record: dict[str, Any], result: Any) -> bool:
        action = record.get('request', {}).get('action', {})
        return (isinstance(result, dict) and result.get('operation') == 'taxi_start'
            and result.get('request_id') == record.get('operation_id')
            and all(type(result.get(key)) is type(action.get(key)) and result.get(key) == action.get(key)
                for key in ('target_guid', 'taxi_menu_id', 'destination_node_id')))

    @classmethod
    def _taxi_terminal(cls, record: dict[str, Any]) -> bool:
        response = record.get('response')
        result = response.get('result') if isinstance(response, dict) else None
        return (cls._taxi_identity(record, result)
            and result.get('terminal') is True and result.get('pending') is False
            and (result.get('status') == 'completed' and result.get('arrived') is True
                or result.get('status') == 'failed' and result.get('arrived') is False))

    @classmethod
    def _taxi_valid_result(cls, record: dict[str, Any], result: Any) -> bool:
        if not cls._taxi_identity(record, result):
            return False
        return (cls._taxi_terminal({**record, 'response': {'result': result}})
            or result.get('status') == 'accepted' and result.get('pending') is True
                and result.get('terminal') is False and result.get('arrived') is False)

    def _pending_taxi(self) -> str | None:
        # The prepared receipt is durable before dispatch. Use it as the fence,
        # including after a crash, handback or a new transport/generation. A
        # second index file would leave a crash gap between the two writes.
        _plain(self.receipt_root)
        if not self.receipt_root.exists():
            return None
        for path in sorted(self.receipt_root.glob('*.json')):
            try:
                operation_id = _operation(path.stem)
            except ControlError:
                continue
            record = self._record(operation_id)
            if (record and record.get('kind') == 'action'
                    and record.get('request', {}).get('action', {}).get('type') == 'taxi_start'
                    and not self._taxi_terminal(record)):
                return operation_id
        return None

    def _new(self, operation_id: str, kind: str, request: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        fingerprint = _hash(json.dumps(request, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':')))
        existing = self._record(operation_id)
        if existing is not None:
            if existing.get('kind') != kind or existing.get('fingerprint') != fingerprint:
                raise ControlError('operation_id_conflict')
            return existing, False
        record = {'schema': 'native-mcp-operation/v1', 'operation_id': operation_id,
            'kind': kind, 'fingerprint': fingerprint, 'phase': 'prepared', 'request': request}
        self._save(record)
        return record, True

    def _finish(self, record: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
        record.update(phase='completed', response=response)
        self._save(record)
        return dict(response)

    @staticmethod
    def _token_matches(state: dict[str, Any], token: str | None) -> bool:
        return (isinstance(token, str) and bool(_TOKEN.fullmatch(token))
            and secrets.compare_digest(state.get('token_hash', ''), _hash(token)))

    def _owned(self, owner_hash: str, token: str | None, *, allow_released=False,
               operator=False) -> dict[str, Any]:
        state = self._state()
        if (state.get('owner_session_hash') != owner_hash or not self._token_matches(state, token)
                or not operator and state.get('authorization_mode', 'sdk_session') != self.authorization_mode):
            raise ControlError('control_not_owned')
        if state['state'] != 'active' and not (allow_released and state['state'] in _STATES):
            raise ControlError('control_not_active')
        return state

    def _authorized(self, owner_session: str, token: str | None, *, allow_released=False) -> dict[str, Any]:
        state = self._state()
        owner_hash = state.get('owner_session_hash') if self.authorization_mode == 'lease_token' else _owner(owner_session)
        return self._owned(owner_hash, token, allow_released=allow_released)

    def status(self, owner_session: str | None = None, control_token: str | None = None) -> dict[str, Any]:
        with self.lock_factory():
            state = self._state()
            mode = state.get('authorization_mode', 'sdk_session')
            pending_taxi = self._pending_taxi()
            return {'available': True, 'character': CHARACTER, 'state': state['state'],
                'generation': state['generation'], 'control_mode': mode,
                'owned_by_session': mode == 'sdk_session' and bool(owner_session)
                    and state.get('owner_session_hash') == _owner(owner_session),
                'owned_by_control_token': mode == self.authorization_mode == 'lease_token'
                    and state['state'] == 'active' and self._token_matches(state, control_token),
                **({'pending_taxi_operation_id': pending_taxi} if pending_taxi else {})}

    def require_owner(self, owner_session: str, token: str) -> dict[str, Any]:
        with self.lock_factory():
            state = self._authorized(owner_session, token)
            return {'character': CHARACTER, 'state': state['state'], 'generation': state['generation']}

    def take_over(self, owner_session: str, operation_id: str, *, resume_previous=True,
                  control_token: str | None = None) -> dict[str, Any]:
        with self.lifecycle_lock_factory():
            if self.authorization_mode == 'lease_token':
                return self._take_over_capability(owner_session, operation_id,
                    resume_previous=resume_previous, control_token=control_token)
            if control_token is not None:
                raise ControlError('unexpected_control_token')
            return self._take_over_transition(owner_session, operation_id, resume_previous=resume_previous)

    def _take_over_transition(self, owner_session: str, operation_id: str, *, resume_previous=True) -> dict[str, Any]:
        if type(resume_previous) is not bool:
            raise ControlError('invalid_resume_previous')
        owner_hash, operation_id = _owner(owner_session), _operation(operation_id)
        with self.lock_factory():
            record, fresh = self._new(operation_id, 'take_over', {'owner_session_hash': owner_hash,
                'resume_previous': bool(resume_previous)})
            if record.get('phase') == 'completed':
                state = self._state()
                return {**record['response'], 'replayed': True, 'lease_active': state['state'] == 'active'
                    and state.get('owner_session_hash') == owner_hash
                    and state.get('generation') == record['response'].get('generation')}
            state = self._state()
            if state['state'] == 'active' and state.get('owner_session_hash') == owner_hash:
                original = self._record(state['operation_id'])
                if not original or 'lease_token' not in original:
                    raise ControlError('lease_receipt_unavailable')
                return self._finish(record, {'available': True, 'character': CHARACTER, 'status': 'active',
                    'operation_id': operation_id, 'control_token': original['lease_token'],
                    'generation': state['generation'], 'controllers_stopped': True})
            if state['state'] != 'released':
                if state.get('owner_session_hash') != owner_hash:
                    raise ControlError('control_owned')
                if state['state'] != 'preparing' or state.get('operation_id') != operation_id:
                    raise ControlError('control_busy')
            else:
                prior = self.runtime.snapshot()
                token = secrets.token_hex(32)
                record['lease_token'] = token
                self._save(record)
                state = {'schema': CONTROL_SCHEMA, 'character': CHARACTER, 'state': 'preparing',
                    'owner_session_hash': owner_hash, 'token_hash': _hash(token),
                    'generation': state['generation'] + 1, 'operation_id': operation_id,
                    'prior_controllers': prior, 'resume_previous': bool(resume_previous)}
                _write(self.control_path, state)
        return self._activate(record, state)

    def _take_over_capability(self, owner_session: str, operation_id: str, *, resume_previous: bool,
                              control_token: str | None) -> dict[str, Any]:
        if type(resume_previous) is not bool:
            raise ControlError('invalid_resume_previous')
        initiator, operation_id = _owner(owner_session), _operation(operation_id)
        with self.lock_factory():
            state = self._state()
            existing = self._record(operation_id)
            if existing is not None:
                request = existing.get('request', {})
                same_lease = (state.get('authorization_mode') == 'lease_token'
                    and request.get('owner_session_hash') == state.get('owner_session_hash')
                    and request.get('generation') == state['generation'])
                original_retry = (same_lease and state.get('operation_id') == operation_id
                    and existing.get('initiator_session_hash') == initiator and control_token is None)
                if not (original_retry or same_lease and self._token_matches(state, control_token)):
                    raise ControlError('control_owned')
                if (existing.get('kind') != 'take_over' or request.get('authorization_mode') != 'lease_token'
                        or request.get('resume_previous') is not resume_previous):
                    raise ControlError('operation_id_conflict')
                record, _ = self._new(operation_id, 'take_over', request)
                if state['state'] == 'active' and state.get('operation_id') == operation_id and record.get('phase') != 'completed':
                    if not self._token_matches(state, record.get('lease_token')):
                        raise ControlError('lease_receipt_unavailable')
                    return self._finish(record, {'available': True, 'character': CHARACTER, 'status': 'active',
                        'operation_id': operation_id, 'control_token': record['lease_token'],
                        'control_mode': 'lease_token', 'generation': state['generation'], 'controllers_stopped': True})
                if record.get('phase') == 'completed':
                    active = state['state'] == 'active'
                    response = dict(record['response']) if active else _safe_result(record['response'])
                    return {**response, 'replayed': True, 'lease_active': active}
                if state['state'] != 'preparing' or state.get('operation_id') != operation_id:
                    raise ControlError('control_busy')
            elif state['state'] != 'released':
                # The initial operation is the only token-less retry allowed to
                # return a capability. Knowing a session ID or a new UUID is not proof.
                if state.get('authorization_mode') != 'lease_token' or state['state'] != 'active' or not self._token_matches(state, control_token):
                    raise ControlError('control_owned')
                record, _ = self._new(operation_id, 'take_over', {
                    'owner_session_hash': state['owner_session_hash'], 'generation': state['generation'],
                    'authorization_mode': 'lease_token', 'resume_previous': resume_previous})
                record['initiator_session_hash'] = initiator
                return self._finish(record, {'available': True, 'character': CHARACTER, 'status': 'active',
                    'operation_id': operation_id, 'control_token': control_token,
                    'control_mode': 'lease_token', 'generation': state['generation'], 'controllers_stopped': True})
            else:
                if control_token is not None:
                    raise ControlError('unexpected_control_token')
                prior = self.runtime.snapshot()
                token, owner_hash = secrets.token_hex(32), _hash('lease:' + secrets.token_hex(32))
                generation = state['generation'] + 1
                record, _ = self._new(operation_id, 'take_over', {
                    'owner_session_hash': owner_hash, 'generation': generation,
                    'authorization_mode': 'lease_token', 'resume_previous': resume_previous})
                record.update(lease_token=token, initiator_session_hash=initiator)
                self._save(record)
                state = {'schema': CONTROL_SCHEMA, 'character': CHARACTER, 'state': 'preparing',
                    'authorization_mode': 'lease_token', 'owner_session_hash': owner_hash,
                    'token_hash': _hash(token), 'generation': generation, 'operation_id': operation_id,
                    'prior_controllers': prior, 'resume_previous': resume_previous}
                _write(self.control_path, state)
        return self._activate(record, state)

    def _activate(self, record: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        operation_id = record['operation_id']
        # Never hold the interlock while waiting for runners to observe stop.
        try:
            self.runtime.stop_gracefully(state['prior_controllers'])
            stopped = self.runtime.proves_stopped()
        except Exception:
            stopped = False
        with self.lock_factory():
            latest = self._record(operation_id)
            if latest and latest.get('phase') == 'completed':
                return {**latest['response'], 'replayed': True}
            current = self._state()
            if current.get('operation_id') != operation_id or current['state'] != 'preparing':
                raise ControlError('takeover_superseded')
            if not stopped:
                record['phase'] = 'pending'
                record['response'] = {'available': False, 'character': CHARACTER, 'status': 'preparing',
                    'operation_id': operation_id, 'reason': 'controllers_not_confirmed_stopped'}
                self._save(record)
                return dict(record['response'])
            current['state'] = 'active'
            _write(self.control_path, current)
            return self._finish(record, {'available': True, 'character': CHARACTER, 'status': 'active',
                'operation_id': operation_id, 'control_token': record['lease_token'],
                'control_mode': current.get('authorization_mode', 'sdk_session'),
                'generation': current['generation'], 'controllers_stopped': True})

    def hand_back(self, owner_session: str, token: str | None, operation_id: str, *, resume_previous=True,
                  _disconnect=False) -> dict[str, Any]:
        if self.authorization_mode == 'lease_token':
            with self.lifecycle_lock_factory():
                with self.lock_factory():
                    state = self._authorized(owner_session, token, allow_released=True)
                return self._release_transition(state['owner_session_hash'], token, operation_id,
                    resume_previous=resume_previous, expected_generation=state['generation'])
        return self._release(_owner(owner_session), token, operation_id,
            resume_previous=resume_previous, disconnect=_disconnect)

    def _release(self, owner_hash: str, token: str | None, operation_id: str, *, resume_previous: bool,
                 disconnect=False, operator=False, expected_generation: int | None = None) -> dict[str, Any]:
        with self.lifecycle_lock_factory():
            return self._release_transition(owner_hash, token, operation_id, resume_previous=resume_previous,
                disconnect=disconnect, operator=operator, expected_generation=expected_generation)

    def _release_transition(self, owner_hash: str, token: str | None, operation_id: str, *, resume_previous: bool,
                            disconnect=False, operator=False, expected_generation: int | None = None) -> dict[str, Any]:
        operation_id = _operation(operation_id)
        if type(resume_previous) is not bool:
            raise ControlError('invalid_resume_previous')
        with self.lock_factory():
            state = self._state()
            if expected_generation is not None and state['generation'] != expected_generation:
                raise ControlError('control_generation_changed')
            # Capability authorization precedes receipt creation and replay, so
            # an invalid or obsolete token cannot poison or reuse operation IDs.
            if not disconnect:
                state = self._owned(owner_hash, token, allow_released=True, operator=operator)
            elif state.get('authorization_mode', 'sdk_session') != 'sdk_session' or state.get('owner_session_hash') != owner_hash:
                return {'available': True, 'character': CHARACTER, 'status': 'not_owned'}
            request = {'owner_session_hash': owner_hash,
                'token_hash': _hash(token) if isinstance(token, str) else None,
                'resume_previous': resume_previous, 'disconnect': bool(disconnect), 'operator': bool(operator)}
            if expected_generation is not None:
                request['generation'] = expected_generation
            record, _ = self._new(operation_id, 'hand_back', request)
            if record.get('phase') == 'completed':
                return dict(record['response'])
            if state['state'] == 'released':
                if record.get('phase') == 'restoring' and resume_previous:
                    try:
                        restored = self.runtime.restore(state['prior_controllers'], operation_id=operation_id)
                        return self._finish(record, {'available': True, 'character': CHARACTER, 'status': 'released',
                            'operation_id': operation_id, 'restoration': restored})
                    except Exception:
                        raise ControlError('controller_restore_failed') from None
                return self._finish(record, {'available': True, 'character': CHARACTER, 'status': 'released',
                    'operation_id': operation_id, 'already_released': True})
            state['state'] = 'releasing'
            _write(self.control_path, state)
        try:
            self.runtime.stop_gracefully(state['prior_controllers'])
            stopped = self.runtime.proves_stopped()
        except Exception:
            stopped = False
        with self.lock_factory():
            latest = self._record(operation_id)
            if latest and latest.get('phase') == 'completed':
                return dict(latest['response'])
            current = self._state()
            if current.get('generation') != state['generation'] or current['state'] != 'releasing':
                raise ControlError('handback_superseded')
            if not stopped:
                record.update(phase='pending', response={'available': False, 'character': CHARACTER,
                    'status': 'releasing', 'operation_id': operation_id,
                    'reason': 'controllers_not_confirmed_stopped'})
                self._save(record)
                return dict(record['response'])
            record['phase'] = 'restoring'
            self._save(record)
            current['state'] = 'released'
            _write(self.control_path, current)
            try:
                restored = self.runtime.restore(current['prior_controllers'], operation_id=operation_id) if resume_previous else {'resumed': False}
                response = {'available': True, 'character': CHARACTER, 'status': 'released',
                    'operation_id': operation_id, 'restoration': restored}
            except Exception:
                response = {'available': False, 'character': CHARACTER, 'status': 'released',
                    'operation_id': operation_id, 'reason': 'controller_restore_failed'}
                record['response'] = response
                self._save(record)  # Keep restoring retryable under the same UUID.
                return dict(response)
            return self._finish(record, response)

    def session_closed(self, owner_session: str, operation_id: str | None = None) -> dict[str, Any]:
        with self.lock_factory():
            state = self._state()
            if state.get('authorization_mode', 'sdk_session') == 'lease_token':
                return {'available': True, 'character': CHARACTER, 'status': 'lease_retained',
                    'control_mode': 'lease_token'}
            if state.get('owner_session_hash') != _owner(owner_session) or state['state'] == 'released':
                return {'available': True, 'character': CHARACTER, 'status': 'not_owned'}
            operation_id = operation_id or str(uuid.uuid5(uuid.NAMESPACE_URL,
                'presence-mcp-disconnect:' + _owner(owner_session) + ':' + str(state['generation'])))
        return self._release(_owner(owner_session), None, operation_id,
            resume_previous=state.get('resume_previous', True), disconnect=True,
            expected_generation=state['generation'])

    def control(self, action: str, owner_session: str | None = None, operation_id: str | None = None, control_token: str | None = None,
                resume_previous: bool = True) -> dict[str, Any]:
        if action == 'status':
            return self.status(owner_session, control_token)
        if type(resume_previous) is not bool:
            raise ControlError('invalid_resume_previous')
        if action == 'take_over':
            return self.take_over(owner_session, operation_id, resume_previous=resume_previous,
                control_token=control_token)
        if action == 'hand_back':
            return self.hand_back(owner_session, control_token, operation_id, resume_previous=resume_previous)
        raise ControlError('invalid_control_action')

    def recover(self, *, resume_previous: bool = False, expected_generation: int | None = None) -> dict[str, Any]:
        """Local operator CLI only; never registered as a public MCP operation."""
        if expected_generation is not None and (type(expected_generation) is not int or expected_generation < 1):
            raise ControlError('invalid_expected_generation')
        with self.lifecycle_lock_factory():
            with self.lock_factory():
                state = self._state()
                if expected_generation is not None and state['generation'] != expected_generation:
                    raise ControlError('control_generation_changed')
                if state['generation'] == 0:
                    return {'available': True, 'character': CHARACTER, 'status': 'released'}
                operation_id = str(uuid.uuid5(uuid.NAMESPACE_URL,
                    'presence-mcp-recover:' + state['owner_session_hash'] + ':' + str(state['generation'])))
                recovery = self._record(operation_id)
                if state['state'] == 'released' and recovery is None:
                    return {'available': True, 'character': CHARACTER, 'status': 'released'}
                original = self._record(state['operation_id'])
                token = original.get('lease_token') if original else None
                if (not original or original.get('kind') != 'take_over'
                        or original.get('request', {}).get('owner_session_hash') != state['owner_session_hash']
                        or original.get('phase') == 'completed'
                            and original.get('response', {}).get('generation') != state['generation']
                        or state.get('authorization_mode') == 'lease_token'
                            and original.get('request', {}).get('generation') != state['generation']
                        or not self._token_matches(state, token)):
                    raise ControlError('lease_receipt_unavailable')
                if recovery is not None:
                    resume_previous = recovery.get('request', {}).get('resume_previous')
            return self._release_transition(state['owner_session_hash'], token, operation_id,
                resume_previous=resume_previous, operator=True, expected_generation=state['generation'])

    def act(self, owner_session: str, control_token: str, operation_id: str, action: dict[str, Any],
            observed_sequence: int | None = None) -> dict[str, Any]:
        owner_hash, operation_id = _owner(owner_session), _operation(operation_id)
        try:
            wire = normalize_action(action)
        except (ValueError, TypeError, OverflowError):
            raise ControlError('invalid_action') from None
        if observed_sequence is not None and (type(observed_sequence) is not int or not 0 <= observed_sequence <= 2**53 - 1):
            raise ControlError('invalid_observed_sequence')
        if not isinstance(control_token, str) or not _TOKEN.fullmatch(control_token):
            raise ControlError('invalid_control_token')
        with self.lock_factory():
            state = self._authorized(owner_session, control_token)
            owner_hash = state['owner_session_hash']
            request = {'owner_session_hash': owner_hash,
                'token_hash': _hash(control_token), 'action': wire, 'observed_sequence': observed_sequence}
            if self.authorization_mode == 'lease_token':
                request.update(authorization_mode='lease_token', generation=state['generation'])
            pending_taxi = self._pending_taxi()
            if pending_taxi and self._record(operation_id) is None:
                pending_result = (self._record(pending_taxi) or {}).get('response', {}).get('result', {})
                safe = wire['type'] == 'say' or (wire['type'] == 'loot_roll'
                    and pending_result.get('status') == 'accepted' and pending_result.get('phase') == 'in_flight')
                if not safe:
                    raise ControlError('taxi_start_unresolved')
            record, fresh = self._new(operation_id, 'action', request)
            if not fresh:
                return _safe_result(record.get('response') or {'available': True, 'character': CHARACTER,
                    'operation_id': operation_id, 'request_id': operation_id, 'status': 'unknown',
                    'outcome_uncertain': True})
            record.update(phase='dispatching', generation=state['generation'])
            speech = {'v': 1, 'origin': 'mcp', 'provider': None, 'model': None} if wire['type'] == 'say' else None
            if speech is not None:
                record['speech_provenance'] = speech
            self._save(record)  # Persist before sending. A crash can never authorize a resend.
            try:
                result = self.client.execute(CHARACTER, wire, request_id=operation_id,
                    observed_sequence=observed_sequence,
                    **({'speech_provenance': speech} if speech is not None else {}))
                if not isinstance(result, dict):
                    raise ControlError('invalid_response')
                if wire['type'] == 'taxi_start' and not self._taxi_valid_result(record, result):
                    raise ControlError('invalid_response')
                response = {'available': True, 'character': CHARACTER, 'operation_id': operation_id,
                    'request_id': operation_id, 'action_type': wire['type'], 'status': result.get('status', 'unknown'),
                    'result': result, 'outcome_uncertain': result.get('status') not in {'accepted', 'completed', 'failed'}}
                if wire['type'] == 'taxi_start' and result.get('phase') == 'outcome_unknown':
                    response['outcome_uncertain'] = True
            except Exception as error:
                code = getattr(error, 'code', 'bridge_error')
                if not isinstance(code, str) or not re.fullmatch('[a-z0-9_]{1,64}', code):
                    code = 'bridge_error'
                uncertain = code in _UNCERTAIN or code == 'bridge_error'
                response = {'available': False, 'character': CHARACTER, 'operation_id': operation_id,
                    'request_id': operation_id, 'action_type': wire['type'],
                    'status': 'unknown' if uncertain else 'failed', 'error': code, 'outcome_uncertain': uncertain}
                interventions = getattr(error, 'guard_interventions', None)
                if isinstance(interventions, list):
                    response['guard_interventions'] = [item for item in interventions if isinstance(item, dict)
                        and item.get('request_id') == operation_id and item.get('action_type') == wire['type']]
            return self._finish(record, response)

    def action_result(self, operation_id: str) -> dict[str, Any]:
        operation_id = _operation(operation_id)
        with self.lock_factory():
            record = self._record(operation_id)
            if not record:
                raise ControlError('unknown_operation')
            response = record.get('response')
            if record['kind'] != 'action':
                return _safe_result(response or {'available': True, 'character': CHARACTER,
                    'operation_id': operation_id, 'status': 'pending'})
            taxi_pending = (record.get('request', {}).get('action', {}).get('type') == 'taxi_start'
                and not self._taxi_terminal(record))
            if response and response.get('status') not in {'accepted', 'unknown'} and not taxi_pending:
                return _safe_result(response)
            try:
                polled = self.client.action_result(CHARACTER, operation_id)
                envelope = polled.get('response') if isinstance(polled, dict) else None
                if (not isinstance(envelope, dict) or polled.get('request_id') != operation_id
                        or type(envelope.get('v')) is not int or envelope['v'] != 1
                        or envelope.get('id') != operation_id or envelope.get('op') != 'action'
                        or envelope.get('character') != CHARACTER or type(envelope.get('ok')) is not bool):
                    raise ControlError('mismatched_action_result')
                action_type = record['request']['action']['type']
                # Taxi rejections carry their exact terminal identity in result
                # even when the normal game envelope is unsuccessful.
                result = envelope.get('result') if envelope['ok'] or action_type == 'taxi_start' else envelope.get('error')
                if not isinstance(result, dict) or result.get('request_id', operation_id) != operation_id:
                    raise ControlError('mismatched_action_result')
                if action_type == 'taxi_start' and not self._taxi_valid_result(record, result):
                    raise ControlError('mismatched_action_result')
                if result.get('action_type', action_type) != action_type:
                    raise ControlError('mismatched_action_result')
                if isinstance(result.get('guard_interventions'), list):
                    result = {**result, 'guard_interventions': [item for item in result['guard_interventions']
                        if isinstance(item, dict) and item.get('request_id') == operation_id
                        and item.get('action_type') == action_type and item.get('attribution') == 'synchronous_action']}
                status = result.get('status', 'failed' if not envelope['ok'] else 'unknown')
                resolved = {'available': True, 'character': CHARACTER, 'operation_id': operation_id,
                    'request_id': operation_id, 'action_type': action_type,
                    'status': status, 'outcome_uncertain': status not in {'accepted', 'completed', 'failed'},
                    'result': result, 'resolution': 'original_request_result'}
                if action_type == 'taxi_start' and result.get('phase') == 'outcome_unknown':
                    resolved['outcome_uncertain'] = True
                if not envelope['ok']:
                    error = envelope.get('error', result) if action_type == 'taxi_start' else result
                    if isinstance(error, dict) and isinstance(error.get('guard_interventions'), list):
                        error = {**error, 'guard_interventions': [item for item in error['guard_interventions']
                            if isinstance(item, dict) and item.get('request_id') == operation_id
                            and item.get('action_type') == action_type
                            and item.get('attribution') == 'synchronous_action']}
                    resolved['error'] = error
                return _safe_result(self._finish(record, resolved))
            except Exception:
                return {**_safe_result(response or {}), 'available': False, 'character': CHARACTER,
                    'operation_id': operation_id, 'request_id': operation_id,
                    'status': response.get('status', 'unknown') if response else 'unknown',
                    'outcome_uncertain': True, 'resolution_error': 'original_result_unavailable'}


class PresenceRuntimeAdapter:
    """Fixed local runners; no PID kills and no credential values in receipts."""
    def __init__(self, presence_root: Path = PRESENCE_ROOT, *, inventory=None, credentials=None,
                 fingerprint=None, sleep=time.sleep, stop_timeout: float = 45.0) -> None:
        self.root = Path(presence_root)
        self.inventory = inventory or self._inventory
        self.credentials = credentials or self._credentials
        self.fingerprint = fingerprint or self._fingerprint
        self.sleep, self.stop_timeout = sleep, stop_timeout

    def _paths(self, lane):
        prefix = 'runtime-game-player' + ('-social' if lane == 'social' else '')
        backend = self.root / 'backend'
        return {'config': self.root / 'local' / ('game_player_social.config.json' if lane == 'social' else 'game_player.config.json'),
            'control': backend / 'data' / (prefix+'-control.json'),
            'state': backend / 'data' / (prefix+'-state.json'),
            'status': backend / 'data' / (prefix+'-status.json'),
            'ledger': backend / 'data' / (prefix+'-ledger.jsonl'),
            'script': backend / 'tools' / ('game_player_modes/social/game_player_social.py' if lane == 'social' else 'game_player.py')}

    def _inventory(self):
        if os.name != 'nt':
            raise ControlError('windows_runtime_required')
        script = "$ErrorActionPreference='Stop'; $p=@(Get-CimInstance Win32_Process -Filter \"Name='python.exe' OR Name='pythonw.exe' OR Name='py.exe'\" | Select-Object ProcessId,ParentProcessId,CommandLine,ExecutablePath); ConvertTo-Json -InputObject @($p) -Compress"
        env = {key: value for key, value in os.environ.items() if key.casefold() != 'psmodulepath'}
        result = subprocess.run(['powershell.exe', '-NoLogo', '-NoProfile', '-NonInteractive', '-Command', script],
            capture_output=True, text=True, check=True, timeout=5, env=env, creationflags=subprocess.CREATE_NO_WINDOW)
        rows = json.loads(result.stdout)
        if not isinstance(rows, list):
            raise ControlError('runtime_identity_unavailable')
        found = []
        for row in rows:
            text = row.get('CommandLine')
            executable = row.get('ExecutablePath')
            if not isinstance(text, str) or not text or not isinstance(executable, str) or not executable:
                raise ControlError('runtime_identity_unavailable')
            args = self._argv(text)
            lane = self.classify_process(args, executable)
            if lane:
                pid = row.get('ProcessId')
                if type(pid) is not int or pid <= 0:
                    raise ControlError('runtime_identity_unavailable')
                found.append({'lane': lane, 'pid': pid, 'parent_pid': row.get('ParentProcessId'),
                    'redirector': self._same_path(executable, self.root / 'backend/.venv/Scripts/python.exe'),
                    'argv': args})
        return self.collapse_redirectors(found)

    @staticmethod
    def collapse_redirectors(rows):
        """One exact venv redirector/base-child pair is one Popen-owned runner."""
        by_pid = {row['pid']: row for row in rows}
        groups = {}
        for row in rows:
            parent = by_pid.get(row.get('parent_pid'))
            paired = (not row['redirector'] and parent is not None and parent['redirector']
                and parent['lane'] == row['lane'] and parent['argv'][1:] == row['argv'][1:])
            root = parent['pid'] if paired else row['pid']
            group = groups.setdefault((row['lane'], root), {'lane': row['lane'], 'pid': root, 'member_pids': []})
            group['member_pids'].append(row['pid'])
        return list(groups.values())

    @staticmethod
    def _argv(text):
        import ctypes
        from ctypes import wintypes
        shell = ctypes.WinDLL('shell32', use_last_error=True)
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        shell.CommandLineToArgvW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_int)]
        shell.CommandLineToArgvW.restype = ctypes.POINTER(wintypes.LPWSTR)
        kernel.LocalFree.argtypes = [wintypes.HLOCAL]
        kernel.LocalFree.restype = wintypes.HLOCAL
        count = ctypes.c_int()
        values = shell.CommandLineToArgvW(text, ctypes.byref(count))
        if not values:
            raise ControlError('runtime_identity_unavailable')
        try:
            return [values[index] for index in range(count.value)]
        finally:
            kernel.LocalFree(ctypes.cast(values, wintypes.HLOCAL))

    @staticmethod
    def _same_path(value, expected):
        return isinstance(value, str) and str(Path(value).resolve()).casefold() == str(Path(expected).resolve()).casefold()

    def _runtime_executable(self, executable):
        """Windows venv redirectors may execute their configured base interpreter."""
        venv = self.root / 'backend/.venv'
        if self._same_path(executable, venv / 'Scripts/python.exe'):
            return True
        try:
            fields = {}
            for line in _plain(venv / 'pyvenv.cfg').read_text(encoding='utf-8').splitlines():
                key, separator, value = line.partition('=')
                if separator:
                    fields[key.strip().casefold()] = value.strip()
            home = Path(fields['home'])
            base = Path(fields.get('executable') or home / 'python.exe')
            return (base.name.casefold() == 'python.exe' and base.is_file()
                and self._same_path(str(base.parent), home) and self._same_path(executable, base))
        except (OSError, KeyError, ValueError):
            return False

    def classify_process(self, args, executable):
        """Exact argv proof, never a path found inside a string or arbitrary argument."""
        if not isinstance(args, list) or len(args) < 2 or any(not isinstance(arg, str) for arg in args):
            raise ControlError('runtime_identity_unavailable')
        offset = 1
        while offset < len(args) and args[offset] in {'-u', '-B', '-E', '-I', '-s', '-S', '-O', '-OO', '-q'}:
            offset += 1
        if offset >= len(args):
            return None
        for lane in ('full', 'social'):
            paths = self._paths(lane)
            module = 'tools.game_player_modes.social.game_player_social' if lane == 'social' else 'tools.game_player'
            direct = self._same_path(args[offset], paths['script'])
            module_run = args[offset:offset+2] == ['-m', module]
            if not direct and Path(args[offset]).name.casefold() == paths['script'].name.casefold():
                raise ControlError('unproven_runner_path')
            if not direct and not module_run:
                continue
            python = self.root / 'backend/.venv/Scripts/python.exe'
            argv_identity = self._same_path(args[0], python) or (
                not self._same_path(executable, python) and self._same_path(args[0], executable))
            if not self._runtime_executable(executable) or not argv_identity:
                raise ControlError('unexpected_runner_python')
            tail = args[offset+2:] if module_run else args[offset+1:]
            if tail.count('--config') != 1:
                raise ControlError('unexpected_runner_configuration')
            for key in ('config', 'control', 'status', 'ledger'):
                flag = '--' + key
                if flag not in tail:
                    if key == 'config':
                        raise ControlError('unexpected_runner_configuration')
                    continue
                offset = tail.index(flag)
                if tail.count(flag) != 1 or offset + 1 >= len(tail) or not self._same_path(tail[offset + 1], paths[key]):
                    raise ControlError('unexpected_runner_configuration')
            return lane
        return None

    def snapshot(self):
        inventory = self.inventory()
        result = {}
        for lane in ('full', 'social'):
            paths = self._paths(lane)
            raw = _plain(paths['control']).read_bytes()
            flags = _strict(raw)
            if not isinstance(flags, dict) or any(type(flags.get(key)) is not bool for key in ('paused', 'stop')):
                raise ControlError('invalid_prior_controls')
            config = _plain(paths['config']).read_bytes()
            config_value = _strict(config)
            if not isinstance(config_value, dict):
                raise ControlError('invalid_prior_config')
            session = config_value.get('session_state')
            managed = (config_value.get('game_backend') == 'azerothcore' and isinstance(session, dict)
                and str(session.get('controlled_character', '')).casefold() == CHARACTER.casefold())
            running = any(row['lane'] == lane for row in inventory)
            if running and not managed:
                raise ControlError('unrelated_controller_running')
            result[lane] = {'running': running, 'managed': managed,
                'paused': flags['paused'], 'stop': flags['stop'],
                'control_bytes': base64.b64encode(raw).decode('ascii'),
                'config_sha256': hashlib.sha256(config).hexdigest()}
        return result

    def stop_gracefully(self, prior):
        for lane in ('full', 'social'):
            if not prior[lane]['managed']:
                continue
            path = self._paths(lane)['control']
            current = _read(path)
            if current is None:
                raise ControlError('control_file_missing')
            _write(path, {**current, 'stop': True})
        deadline = time.monotonic() + self.stop_timeout
        while self.inventory():
            if time.monotonic() >= deadline:
                return
            self.sleep(.1)

    def proves_stopped(self):
        return not self.inventory()

    def _credentials(self, config):
        backend = str(self.root / 'backend')
        if backend not in sys.path:
            sys.path.insert(0, backend)
        from app.db import SessionLocal
        from app.routes_runtime import _game_player_provider_env
        with SessionLocal() as db:
            provider = str(config.get('provider') or 'openai')
            social_provider = str(config.get('social_provider') or provider)
            return _game_player_provider_env(db, provider, social_provider)

    def _fingerprint(self, config):
        backend = str(self.root / 'backend')
        if backend not in sys.path:
            sys.path.insert(0, backend)
        from app.game_player_runtime_service import _game_player_config_fingerprint
        return _game_player_config_fingerprint(config)

    def restore(self, prior, *, operation_id):
        result = {}
        for lane in ('full', 'social'):
            paths, intended = self._paths(lane), prior[lane]
            if not intended['managed']:
                result[lane] = 'unchanged'
                continue
            config_raw = _plain(paths['config']).read_bytes()
            if hashlib.sha256(config_raw).hexdigest() != intended['config_sha256']:
                raise ControlError('prior_config_changed')
            control_raw = base64.b64decode(intended['control_bytes'], validate=True)
            flags = _strict(control_raw)
            if intended['running'] and not intended['stop']:
                existing = [row for row in self.inventory() if row['lane'] == lane]
                if existing:
                    state = _read(paths['state']) or {}
                    if (len(existing) == 1 and state.get('pid') == existing[0]['pid']
                            and state.get('mcp_handback_operation_id') == operation_id):
                        result[lane] = 'already_restored'
                        continue
                    raise ControlError('unexpected_existing_runner')
                _write_bytes(paths['control'], control_raw)  # Exact paused state exists before spawning.
                config = _strict(config_raw)
                env = {**os.environ, **self.credentials(config)}
                fingerprint = self.fingerprint(config)
                python = _plain(self.root / 'backend/.venv/Scripts/python.exe')
                if not python.is_file():
                    raise ControlError('runtime_python_missing')
                cmd = [str(python), str(paths['script']), '--config', str(paths['config']),
                    '--control', str(paths['control']), '--status', str(paths['status']), '--ledger', str(paths['ledger'])]
                proc = subprocess.Popen(cmd, cwd=str(self.root / 'backend'), env=env,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                _write(paths['state'], {'pid': proc.pid, 'started_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                    'mcp_handback_operation_id': operation_id,
                    'config_fingerprint': fingerprint,
                    'command': cmd, 'config_path': str(paths['config']), 'control_path': str(paths['control']),
                    'status_path': str(paths['status']), 'ledger_path': str(paths['ledger'])})
                result[lane] = 'paused' if flags['paused'] else 'running'
            else:
                _write_bytes(paths['control'], control_raw)
                result[lane] = 'stopped'
        return result


def default_manager(client, *, authorization_mode: str = 'sdk_session') -> McpControlManager:
    return McpControlManager(client=client, authorization_mode=authorization_mode)


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description='Local operator recovery for the fixed Vesper MCP lease.')
    parser.add_argument('--recover', action='store_true', required=True)
    parser.add_argument('--expected-generation', type=int, help='Refuse recovery if the lease generation has changed.')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--resume-previous', action='store_true', help='Explicitly restore prior autonomous intent.')
    group.add_argument('--leave-stopped', action='store_true', help='Release ownership and keep runners stopped (default).')
    args = parser.parse_args(argv)
    try:
        result = default_manager(None).recover(resume_previous=args.resume_previous,
            expected_generation=args.expected_generation)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get('available') else 1
    except Exception as error:
        code = error.code if isinstance(error, ControlError) else 'recovery_unavailable'
        print(json.dumps({'available': False, 'character': CHARACTER, 'error': code}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
