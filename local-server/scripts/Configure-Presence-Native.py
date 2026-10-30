"""Select the native Vesper connection without starting a model or game loop."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import os
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
PRESENCE = Path('C:/Files/Programs/Codex/Presence/working')
sys.path.insert(0, str(PRESENCE / 'backend'))
from app.game_player_runtime_service import (
    apply_game_player_preset, game_player_paths, social_game_player_paths,
    SOCIAL_GAME_PLAYER_PRESET_DEFINITIONS, read_json_file, write_json_file,
    sync_game_player_identity,
)


def main() -> None:
    presence_id = os.environ.get('PRESENCE_PROFILE_ID', '').strip()
    if not presence_id:
        raise SystemExit('Set PRESENCE_PROFILE_ID to your intended local profile; no settings changed.')
    backup = ROOT / 'presence-integration/backups' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    for mode, paths, preset in (
        ('full', game_player_paths(), 'azerothcore_independent'),
        ('social', social_game_player_paths(), 'azerothcore_social'),
    ):
        original = paths['config']
        if original.exists():
            target = backup / original.relative_to(PRESENCE)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, target)
        apply_game_player_preset(
            preset, paths=paths, instruction_mode=mode,
            preset_definitions=SOCIAL_GAME_PLAYER_PRESET_DEFINITIONS if mode == 'social' else None,
        )
        payload = read_json_file(original)
        payload['continuity_presence_id'] = presence_id
        payload['continuity_source_thread_id'] = ''
        state = payload['session_state']
        state['current_activity'] = 'Starting a fresh AzerothCore adventure as a Blood Elf paladin.'
        state['recent_events'] = []
        sync_game_player_identity(payload, instruction_mode=mode)
        write_json_file(original, payload)
        print(f'{mode}: native Vesper connection and explicit Presence identity selected; loop remains stopped.')
    print(f'Previous game configs saved under {backup}')


if __name__ == '__main__':
    main()
