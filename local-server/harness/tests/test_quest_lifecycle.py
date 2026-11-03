"""Quest lifecycle facts remain inspectable through existing read-only MCP paths."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

from presence_acore.event_wait import _matches, wait_events
from presence_acore.mcp_server import Inspector

EPOCH = 'c'*32


def lifecycle():
    return {'schema': 'native-quest-lifecycle/v1', 'epoch': EPOCH, 'actor_guid': '102',
        'oldest_sequence': '1', 'newest_sequence': '64', 'dropped_total': '0', 'capacity': 64,
        'included': 64, 'scope': 'owned_character_actual_hooks', 'backfilled_from_quest_log': False,
        'receipts': [{'transition_id': EPOCH+':quest:'+str(index), 'sequence': str(index), 'actor_guid': '102',
            'quest_id': index, 'title': 'Observed quest '+str(index),
            'kind': 'accepted' if index % 2 else 'rewarded', 'timestamp': '2026-11-03T02:00:00Z',
            'source': 'normal_player_quest_accept_hook' if index % 2 else 'normal_player_reward_quest_hook',
            'in_log': bool(index % 2), 'active': bool(index % 2), 'quest_status': 1 if index % 2 else 0,
            'quest_status_name': 'incomplete' if index % 2 else 'none', 'rewarded': not bool(index % 2)}
            for index in range(1, 65)]}


def test_full_lifecycle_receipts_are_unclipped_in_live_mcp_observation_without_actions():
    observation = {'sequence': 90, 'self': {'guid': '102', 'name': 'Vesper'}, 'quest_lifecycle': lifecycle()}
    class Client:
        def __init__(self): self.calls = []
        def request(self, operation, character, **kwargs):
            self.calls.append((operation, character, kwargs))
            assert operation == 'events'
            return {'schema': 'native-event-journal/v1', 'cursor': EPOCH+':70', 'events': []}
        def observe(self, character, **kwargs):
            self.calls.append(('observe', character, kwargs))
            return deepcopy(observation)
    client = Client()
    value = Inspector(client).live()
    assert value['available'] is True and value['observation'] == observation
    assert len(value['observation']['quest_lifecycle']['receipts']) == 64
    assert [call[0] for call in client.calls] == ['events', 'observe']


def test_existing_quest_change_wait_keeps_lifecycle_kind_and_id_then_fetches_new_state():
    for receipt in (lifecycle()['receipts'][0], lifecycle()['receipts'][1]):
        event = {'type': 'quest_changed', 'payload': receipt}
        assert _matches(event, ['quest_change'])
        assert not _matches(event, ['loot_change'])
        class Client:
            def request(self, operation, character, **kwargs):
                assert operation == 'events' and kwargs['since'] == EPOCH+':70'
                return {'schema': 'native-event-journal/v1', 'cursor': EPOCH+':71', 'events': [event]}
        calls = []
        value = wait_events(Client(), lambda: calls.append('fresh') or {'sequence': 91,
            'quest_lifecycle': lifecycle()}, since=EPOCH+':70', event_types=['quest_change'])
        assert value['events'] == [event] and value['snapshot']['quest_lifecycle'] == lifecycle()
        assert value['cursor'] == EPOCH+':71' and calls == ['fresh']


def test_quest_notice_projection_loads_fixed_pure_helper_without_importing_controllers_or_providers(tmp_path):
    tools = tmp_path / 'backend/tools'
    tools.mkdir(parents=True)
    (tools / 'game_player_native_quest_notices.py').write_text(
        'def quest_notice_context(value): return value["quest_lifecycle"]\n', encoding='utf-8')
    (tools / 'game_player_native_context.py').write_text(
        'from tools.game_player_native_quest_notices import quest_notice_context\n'
        'def compact_native_observation(value, mode="gameplay"): return quest_notice_context(value)\n', encoding='utf-8')
    value = {'quest_lifecycle': lifecycle()}
    code = ('import sys,json,builtins\nfrom pathlib import Path\n'
        f'sys.path.insert(0,{str(Path(__file__).resolve().parents[1])!r})\n'
        'from presence_acore.model_context import _projection\n'
        'before=set(sys.modules); original=builtins.__import__\n'
        f'fn=_projection(Path({str(tmp_path)!r}))\n'
        f'value=fn(json.loads({json.dumps(value)!r}))\n'
        'assert len(value["receipts"])==64\n'
        f'assert value["receipts"][-1]["transition_id"]=={EPOCH+":quest:64"!r}\n'
        'assert builtins.__import__ is original\n'
        'assert not any(n.startswith(("tools.","app.","openai","anthropic")) for n in set(sys.modules)-before)\n')
    subprocess.run([sys.executable, '-I', '-S', '-B', '-c', code], check=True, capture_output=True, text=True)
