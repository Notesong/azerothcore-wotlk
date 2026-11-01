"""Explicit SDK-session-owned Vesper control, with durable idempotent operations.

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
    return {key: item for key, item in value.items() if key != 'control_token'}


class McpControlManager:
    def __init__(self, runtime=None, client=None, *, control_path: Path | None = None,
                 receipt_root: Path | None = None, lock_factory=None, lifecycle_lock_factory=None) -> None:
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

    def _owned(self, owner_hash: str, token: str | None, *, allow_released=False) -> dict[str, Any]:
        state = self._state()
        if (state.get('owner_session_hash') != owner_hash or not isinstance(token, str)
                or not _TOKEN.fullmatch(token) or not secrets.compare_digest(state.get('token_hash', ''), _hash(token))):
            raise ControlError('control_not_owned')
        if state['state'] != 'active' and not (allow_released and state['state'] in _STATES):
            raise ControlError('control_not_active')
        return state

    def status(self, owner_session: str | None = None) -> dict[str, Any]:
        with self.lock_factory():
            state = self._state()
            return {'available': True, 'character': CHARACTER, 'state': state['state'],
                'generation': state['generation'], 'owned_by_session': bool(owner_session)
                    and state.get('owner_session_hash') == _owner(owner_session)}

    def require_owner(self, owner_session: str, token: str) -> dict[str, Any]:
        with self.lock_factory():
            state = self._owned(_owner(owner_session), token)
            return {'character': CHARACTER, 'state': state['state'], 'generation': state['generation']}

    def take_over(self, owner_session: str, operation_id: str, *, resume_previous=True) -> dict[str, Any]:
        with self.lifecycle_lock_factory():
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
                'generation': current['generation'], 'controllers_stopped': True})

    def hand_back(self, owner_session: str, token: str | None, operation_id: str, *, resume_previous=True,
                  _disconnect=False) -> dict[str, Any]:
        return self._release(_owner(owner_session), token, operation_id,
            resume_previous=resume_previous, disconnect=_disconnect)

    def _release(self, owner_hash: str, token: str | None, operation_id: str, *, resume_previous: bool,
                 disconnect=False, operator=False) -> dict[str, Any]:
        with self.lifecycle_lock_factory():
            return self._release_transition(owner_hash, token, operation_id, resume_previous=resume_previous,
                disconnect=disconnect, operator=operator)

    def _release_transition(self, owner_hash: str, token: str | None, operation_id: str, *, resume_previous: bool,
                            disconnect=False, operator=False) -> dict[str, Any]:
        operation_id = _operation(operation_id)
        if type(resume_previous) is not bool:
            raise ControlError('invalid_resume_previous')
        with self.lock_factory():
            record, _ = self._new(operation_id, 'hand_back', {'owner_session_hash': owner_hash,
                'token_hash': _hash(token) if isinstance(token, str) else None,
                'resume_previous': resume_previous, 'disconnect': bool(disconnect), 'operator': bool(operator)})
            if record.get('phase') == 'completed':
                return dict(record['response'])
            state = self._state()
            if disconnect:
                if state.get('owner_session_hash') != owner_hash:
                    return self._finish(record, {'available': True, 'character': CHARACTER, 'status': 'not_owned'})
            else:
                state = self._owned(owner_hash, token, allow_released=True)
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
            return self._finish(record, response)

    def session_closed(self, owner_session: str, operation_id: str | None = None) -> dict[str, Any]:
        with self.lock_factory():
            state = self._state()
            if state.get('owner_session_hash') != _owner(owner_session) or state['state'] == 'released':
                return {'available': True, 'character': CHARACTER, 'status': 'not_owned'}
            operation_id = operation_id or str(uuid.uuid5(uuid.NAMESPACE_URL,
                'presence-mcp-disconnect:' + _owner(owner_session) + ':' + str(state['generation'])))
        return self.hand_back(owner_session, None, operation_id,
            resume_previous=state.get('resume_previous', True), _disconnect=True)

    def control(self, action: str, owner_session: str | None = None, operation_id: str | None = None, control_token: str | None = None,
                resume_previous: bool = True) -> dict[str, Any]:
        if action == 'status':
            return self.status(owner_session)
        if type(resume_previous) is not bool:
            raise ControlError('invalid_resume_previous')
        if action == 'take_over':
            if control_token is not None:
                raise ControlError('unexpected_control_token')
            return self.take_over(owner_session, operation_id, resume_previous=resume_previous)
        if action == 'hand_back':
            return self.hand_back(owner_session, control_token, operation_id, resume_previous=resume_previous)
        raise ControlError('invalid_control_action')

    def recover(self, *, resume_previous: bool = False) -> dict[str, Any]:
        """Local operator CLI only; never registered as a public MCP operation."""
        with self.lock_factory():
            state = self._state()
            if state['state'] == 'released':
                return {'available': True, 'character': CHARACTER, 'status': 'released'}
            original = self._record(state['operation_id'])
            token = original.get('lease_token') if original else None
            if not isinstance(token, str) or not secrets.compare_digest(_hash(token), state['token_hash']):
                raise ControlError('lease_receipt_unavailable')
        return self._release(state['owner_session_hash'], token, str(uuid.uuid4()),
            resume_previous=resume_previous, operator=True)

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
            record, fresh = self._new(operation_id, 'action', {'owner_session_hash': owner_hash,
                'token_hash': _hash(control_token), 'action': wire, 'observed_sequence': observed_sequence})
            if not fresh:
                return _safe_result(record.get('response') or {'available': True, 'character': CHARACTER,
                    'operation_id': operation_id, 'request_id': operation_id, 'status': 'unknown',
                    'outcome_uncertain': True})
            state = self._owned(owner_hash, control_token)
            record.update(phase='dispatching', generation=state['generation'])
            self._save(record)  # Persist before sending. A crash can never authorize a resend.
            try:
                result = self.client.execute(CHARACTER, wire, request_id=operation_id,
                    observed_sequence=observed_sequence)
                if not isinstance(result, dict):
                    raise ControlError('invalid_response')
                response = {'available': True, 'character': CHARACTER, 'operation_id': operation_id,
                    'request_id': operation_id, 'action_type': wire['type'], 'status': result.get('status', 'unknown'),
                    'result': result, 'outcome_uncertain': result.get('status') not in {'accepted', 'completed', 'failed'}}
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
            if response and response.get('status') not in {'accepted', 'unknown'}:
                return _safe_result(response)
            try:
                polled = self.client.action_result(CHARACTER, operation_id)
                envelope = polled.get('response') if isinstance(polled, dict) else None
                if (not isinstance(envelope, dict) or polled.get('request_id') != operation_id
                        or type(envelope.get('v')) is not int or envelope['v'] != 1
                        or envelope.get('id') != operation_id or envelope.get('op') != 'action'
                        or envelope.get('character') != CHARACTER or type(envelope.get('ok')) is not bool):
                    raise ControlError('mismatched_action_result')
                result = envelope.get('result') if envelope['ok'] else envelope.get('error')
                if not isinstance(result, dict) or result.get('request_id', operation_id) != operation_id:
                    raise ControlError('mismatched_action_result')
                action_type = record['request']['action']['type']
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
                if not envelope['ok']:
                    resolved['error'] = result
                return self._finish(record, resolved)
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


def default_manager(client) -> McpControlManager:
    return McpControlManager(client=client)


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description='Local operator recovery for the fixed Vesper MCP lease.')
    parser.add_argument('--recover', action='store_true', required=True)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--resume-previous', action='store_true', help='Explicitly restore prior autonomous intent.')
    group.add_argument('--leave-stopped', action='store_true', help='Release ownership and keep runners stopped (default).')
    args = parser.parse_args(argv)
    try:
        result = default_manager(None).recover(resume_previous=args.resume_previous)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get('available') else 1
    except Exception as error:
        code = error.code if isinstance(error, ControlError) else 'recovery_unavailable'
        print(json.dumps({'available': False, 'character': CHARACTER, 'error': code}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
