from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import json
from types import SimpleNamespace


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from presence_acore.model_context import _projection
from presence_acore.mcp_server import Inspector


class AttentionProjectionTests(unittest.TestCase):
    def test_attention_helper_loads_in_fresh_isolated_stdlib_process(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            root = Path(folder)
            tools = root / 'backend/tools'
            tools.mkdir(parents=True)
            (tools / 'game_player_native_context.py').write_text(
                'from tools.game_player_native_attention import attention_facts\n'
                'def compact_native_observation(value, mode="gameplay"):\n'
                '    return attention_facts(value)\n', encoding='utf-8')
            (tools / 'game_player_native_attention.py').write_text(
                'def attention_facts(value):\n'
                '    return {"lead_activity": {"guid": value["guid"], "distance": value["distance"]}}\n',
                encoding='utf-8')
            program = (
                'import sys,json,builtins\nfrom pathlib import Path\n'
                f'sys.path.insert(0,{str(Path(__file__).resolve().parents[1])!r})\n'
                'from presence_acore.model_context import _projection\n'
                'before=set(sys.modules); original=builtins.__import__\n'
                f'fn=_projection(Path({str(root)!r}))\n'
                'assert fn({"guid":"18446744073709551615","distance":12})["lead_activity"]["distance"]==12\n'
                'assert builtins.__import__ is original\n'
                'assert not any(n.startswith(("tools.","openai","anthropic")) for n in set(sys.modules)-before)\n'
                'print("isolated attention projection passed")\n'
            )
            result = subprocess.run([sys.executable, '-I', '-S', '-B', '-c', program],
                                    capture_output=True, text=True, check=True)
            self.assertIn('isolated attention projection passed', result.stdout)

    def test_missing_fixed_helper_fails_instead_of_silently_dropping_attention(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            tools = Path(folder) / 'backend/tools'
            tools.mkdir(parents=True)
            (tools / 'game_player_native_context.py').write_text(
                'from tools.game_player_native_attention import attention_facts\n', encoding='utf-8')
            with self.assertRaises(FileNotFoundError):
                _projection(Path(folder))

    def test_live_preview_matches_local_body_focus_without_forwarding_config(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            root = Path(folder)
            tools = root / 'backend/tools'
            tools.mkdir(parents=True)
            (root / 'local').mkdir()
            (tools / 'game_player_native_context.py').write_text(
                'def compact_native_observation(value, mode="gameplay"):\n'
                '    return {"mode": mode, "sequence": value["sequence"]}\n', encoding='utf-8')
            (root / 'local/game_player.config.json').write_text(json.dumps({
                'game_backend': 'azerothcore', 'session_state': {'controlled_character': 'Vesper'},
                'provider': 'local', 'native_action_base_url': 'http://127.0.0.1:8082/v1',
                'user_instruction': 'DO_NOT_FORWARD_CONFIG', 'api_key': 'DO_NOT_FORWARD_KEY',
            }), encoding='utf-8')
            client = SimpleNamespace(observe=lambda *args, **kwargs: {'sequence': 42})
            inspector = Inspector(client, presence_root=root)
            body = inspector.model_context(source='live_preview')
            social = inspector.model_context(lane='social', source='live_preview')
            self.assertTrue(body['available'])
            # Existing gateway preview metadata has a fixed allowlist. The view
            # identifies its format; an extra mode field would falsely flag truncation.
            self.assertNotIn('projection_mode', body['preview'])
            self.assertEqual(body['preview']['native_observation']['mode'], 'local_gameplay')
            self.assertEqual(social['preview']['native_observation']['mode'], 'social_gameplay')
            self.assertNotIn('DO_NOT_FORWARD', json.dumps(body))


if __name__ == '__main__':
    unittest.main()
