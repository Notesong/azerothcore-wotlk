"""Reload the saved Full controller with its pause set before process creation."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True
backend = Path('C:/Files/Programs/Codex/Presence/working/backend')
sys.path.insert(0, str(backend))
os.environ.setdefault('PRESENCE_DISABLE_SCHEDULER', '1')
from app import game_player_runtime_service as runtime
from app.db import SessionLocal
from app.routes_runtime import _game_player_lead_character, _game_player_provider_env

archive = Path('C:/Games/AzerothCore/model-context-integration/runtime-before-reload')
archive.mkdir(parents=True, exist_ok=True)
paths = runtime.game_player_paths()
before = runtime.game_player_runtime_snapshot(paths)
raw_before = runtime.read_json_file(paths['status'])
control_before = runtime.read_json_file(paths['control'])
state_before = runtime.read_json_file(paths['state'])
old_pid = int(state_before.get('pid') or 0)
old_alive = old_pid > 0 and runtime.is_pid_running(old_pid)
if control_before.get('paused') is not True or control_before.get('stop') is True:
    raise SystemExit('Expected an explicit saved pause without a stop request; no reload performed.')
if old_alive and (not before.get('running') or not before.get('paused')
        or raw_before.get('paused') is not True
        or paths['status'].stat().st_mtime_ns < paths['control'].stat().st_mtime_ns):
    raise SystemExit('The old loop has not confirmed the current pause; no reload performed.')
if before.get('game_backend') != 'azerothcore' or before.get('controlled_character') != 'Vesper':
    raise SystemExit('The active controller is not Vesper on AzerothCore; no reload performed.')
for key in ('config', 'status', 'state', 'control'):
    source = paths.get(key)
    if isinstance(source, Path) and source.is_file():
        shutil.copy2(source, archive / source.name)

with SessionLocal() as db:
    provider_env = _game_player_provider_env(db, before.get('provider'), before.get('social_provider'))
    lead = _game_player_lead_character(db)

original_control = runtime.set_game_player_control
original_popen = runtime.subprocess.Popen

def paused_control(*, paused=None, stop=None, paths=None):
    selected = paths or runtime.game_player_paths()
    control_path = selected['control']
    current = runtime.read_json_file(control_path)
    value = {'paused': True, 'stop': bool(current.get('stop', False)) if stop is None else bool(stop)}
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=control_path.parent,
                                         prefix='.paused-reload-', suffix='.tmp', delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(value, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, control_path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return value

log_path = archive.parent / 'reloaded-controller.log'
with log_path.open('ab', buffering=0) as log:
    def hidden_popen(*args, **kwargs):
        kwargs.update(creationflags=subprocess.CREATE_NO_WINDOW, stdout=log,
                      stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        return original_popen(*args, **kwargs)

    runtime.set_game_player_control = paused_control
    runtime.subprocess.Popen = hidden_popen
    try:
        runtime.stop_game_player_runtime(paths)
        if old_pid > 0 and runtime.is_pid_running(old_pid):
            raise RuntimeError('The old controller is still running; a second loop was not started.')
        runtime.start_game_player_runtime({}, provider_env=provider_env, lead_character=lead, paths=paths)
    finally:
        runtime.set_game_player_control = original_control
        runtime.subprocess.Popen = original_popen

deadline = time.monotonic() + 30
while True:
    after = runtime.game_player_runtime_snapshot(paths)
    raw_status = runtime.read_json_file(paths['status'])
    initialized = (raw_status.get('running') is True and raw_status.get('paused') is True
                   and raw_status.get('started_at') and raw_status.get('started_at') != raw_before.get('started_at')
                   and raw_status.get('controlled_character') == 'Vesper'
                   and raw_status.get('game_backend') == 'azerothcore'
                   and after.get('pid') != before.get('pid'))
    if after.get('running') and after.get('paused') and initialized:
        break
    if time.monotonic() >= deadline:
        raise SystemExit('Reload did not report a running, paused controller; inspect the local log.')
    time.sleep(0.5)
if after.get('gameplay_model_calls', 0) or after.get('social_model_calls', 0):
    raise SystemExit('Unexpected model activity after paused reload; inspect the local status.')
print(json.dumps({key: after.get(key) for key in
                 ('running', 'paused', 'pid', 'gameplay_model_calls', 'social_model_calls', 'last_error')}))
