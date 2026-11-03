from __future__ import annotations

import builtins
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from presence_acore.mcp_server import Inspector, Server
from presence_acore.model_context import MAX_CAPTURE_BYTES, _OMITTED, _projection
from test_mcp_server import FakeClient, initialize, request


def capture(lane="body"):
    return {
        "schema": "native-model-context/v1", "inspection_only": True, "source": "last_request_attempt",
        "runtime": "full", "character": "Vesper", "lane": lane, "capture_id": "a" * 32,
        "session": {"run_id": "b" * 32, "started_at": "2026-10-23T19:45:37Z", "pid": 12345},
        "provider": "openai", "model": "fixture-model", "prepared_at":
        (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat(),
        "observation_sequence": 42, "observation_timestamp": "2026-10-23T20:00:00Z",
        "source_prompt_sha256": "c" * 64, "source_prompt_bytes": 123,
        "context": {"planner_mode": "gameplay" if lane == "body" else "social",
                    "session_state": {"lead_character": "Aurenne", "notes": "stay close ♥"},
                    "recent_chat_transcript": [{"text": "do not touch the cat ♥"}],
                    "allowed_actions": ["wait", "follow"],
                    "extra_context": {"game_backend": "azerothcore", "native_observation": {"sequence": 42}}},
        "images": {"count": 1, "bytes_omitted": True}, "omitted_sections": list(_OMITTED),
        "exactness": {"source": "already_serialized_native_prompt", "context_available": True,
                      "copied_values_exact": True, "truncated": False, "omitted_dynamic_fields": 0,
                      "max_capture_bytes": MAX_CAPTURE_BYTES},
        "outcome": {"state": "response_received", "provider_read_confirmed": False, "http_status": 200},
    }


class ModelContextTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="model-context-unit-", dir=Path(__file__).parent)
        self.data_dir = Path(self.directory.name)
        self.client = FakeClient()
        self.inspector = Inspector(self.client, data_dir=self.data_dir)
        self.server = Server(self.inspector)
        self.pid_patch = patch("presence_acore.mcp_server._pid_alive", return_value=False)
        self.pid_patch.start()

    def tearDown(self):
        self.pid_patch.stop()
        self.directory.cleanup()

    def write(self, name, value):
        (self.data_dir / name).write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def test_defaults_read_exact_body_capture_without_observation_or_display_truncation(self):
        record = capture()
        record["context"]["session_state"]["notes"] = "Eversong ♥ ".join(str(i) for i in range(900))
        record["context"]["recent_chat_transcript"] = [{"text": str(i)} for i in range(150)]
        self.write("runtime-game-player-context-body.json", record)
        value = self.inspector.model_context()
        self.assertTrue(value["available"])
        self.assertEqual(value["view_kind"], "last_request_attempt")
        self.assertEqual(value["capture"], record)
        self.assertGreaterEqual(value["age_sec"], 29)
        self.assertNotIn("transport_truncated", value)
        self.assertEqual(self.client.observations, [])

    def test_missing_capture_is_unavailable_without_observing_or_falling_back(self):
        value = self.inspector.model_context(lane="social")
        self.assertFalse(value["available"])
        self.assertEqual(value["error"]["code"], "no_recorded_request")
        self.assertNotIn("preview", value)
        self.assertEqual(self.client.observations, [])

    def test_runtime_identity_uses_status_start_time_and_reports_stale_capture(self):
        record = capture()
        self.write("runtime-game-player-context-body.json", record)
        self.write("runtime-game-player-state.json", {"pid": 12345, "started_at": "2026-10-23T19:45:36Z"})
        self.write("runtime-game-player-status.json", {"running": True, "started_at": "2026-10-23T19:45:37Z",
                                                      "controlled_character": "Vesper", "game_backend": "azerothcore"})
        self.write("runtime-game-player-control.json", {"paused": True})
        with patch("presence_acore.mcp_server._pid_alive", return_value=True):
            runtime = self.inspector.model_context()["runtime"]
        self.assertEqual(runtime, {"running": True, "paused": True, "process_alive": True,
                                  "pid_matches_capture": True, "started_at_matches_capture": True})
        self.write("runtime-game-player-state.json", {"pid": 54321})
        self.write("runtime-game-player-status.json", {"running": False, "started_at": "2026-10-23T20:00:00Z",
                                                      "controlled_character": "Vesper", "game_backend": "azerothcore"})
        value = self.inspector.model_context()
        self.assertTrue(value["available"])
        self.assertFalse(value["runtime"]["pid_matches_capture"])
        self.assertFalse(value["runtime"]["started_at_matches_capture"])
        self.assertFalse(value["runtime"]["process_alive"])

    def test_mismatched_capture_schema_character_lane_runtime_and_source_fail_closed(self):
        for changes in ({"schema": "unknown"}, {"character": "Aurenne"}, {"lane": "social"},
                        {"source": "live_preview"}, {"runtime": "social"}, {"inspection_only": False},
                        {"provider": {"private_persona": "DO-NOT-ECHO"}}, {"prepared_at": "yesterday"}):
            with self.subTest(changes=changes):
                record = capture()
                record.update(changes)
                self.write("runtime-game-player-context-body.json", record)
                value = self.inspector.model_context()
                self.assertFalse(value["available"])
                self.assertEqual(value["error"]["code"], "invalid_capture")
                self.assertNotIn("capture", value)
                self.assertNotIn("DO-NOT-ECHO", json.dumps(value))
        self.assertEqual(self.client.observations, [])

    def test_metadata_only_capture_is_explicitly_unavailable(self):
        record = capture()
        record["context"] = None
        record["exactness"].update(context_available=False, copied_values_exact=False, unavailable_reason="oversize")
        self.write("runtime-game-player-context-body.json", record)
        value = self.inspector.model_context()
        self.assertFalse(value["available"])
        self.assertEqual(value["capture"], record)
        self.assertEqual(value["error"]["code"], "capture_context_unavailable")

    def test_capture_allowlist_removes_persona_credentials_image_bytes_and_marks_changed_context(self):
        record = capture()
        record["raw_http_request"] = {"password": "DO-NOT-ECHO"}
        record["context"]["user_instruction"] = "DO-NOT-ECHO"
        record["context"]["extra_context"]["persona"] = "DO-NOT-ECHO"
        record["context"]["extra_context"]["native_observation"]["api_key"] = "DO-NOT-ECHO"
        record["images"]["image_url"] = "data:DO-NOT-ECHO"
        self.write("runtime-game-player-context-body.json", record)
        value = self.inspector.model_context()
        self.assertTrue(value["available"])
        self.assertTrue(value["transport_truncated"])
        self.assertFalse(value["exact_dynamic_context"])
        self.assertFalse(value["capture"]["exactness"]["copied_values_exact"])
        self.assertNotIn("DO-NOT-ECHO", json.dumps(value))
        self.assertEqual(value["capture"]["source_prompt_sha256"], "c" * 64)

    def test_strict_capture_json_rejects_duplicates_nonfinite_and_oversize_without_echo(self):
        path = self.data_dir / "runtime-game-player-context-body.json"
        for raw, code in ((b'{"x":1,"x":2}', "invalid_capture"), (b'{"x":NaN}', "invalid_capture"),
                          (b"x" * (MAX_CAPTURE_BYTES + 1), "capture_too_large")):
            with self.subTest(code=code):
                path.write_bytes(raw)
                value = self.inspector.model_context()
                self.assertEqual(value["error"]["code"], code)
                self.assertNotIn("capture", value)

    def test_reader_only_opens_fixed_capture_and_runtime_files(self):
        record = capture()
        record["credentials_file"] = str(self.data_dir / "sensitive.json")
        self.write("runtime-game-player-context-body.json", record)
        self.write("sensitive.json", {"password": "DO-NOT-ECHO"})
        original = Path.open
        opened = []
        def track(path, *args, **kwargs):
            opened.append(path.name)
            return original(path, *args, **kwargs)
        with patch.object(Path, "open", track):
            value = self.inspector.model_context()
        self.assertTrue(value["available"])
        self.assertEqual(set(opened), {"runtime-game-player-context-body.json", "runtime-game-player-state.json",
                                      "runtime-game-player-status.json", "runtime-game-player-control.json"})
        self.assertNotIn("DO-NOT-ECHO", json.dumps(value))

    def test_live_preview_uses_current_compact_projection_and_labels_missing_enrichment(self):
        observation = self.client.observe("Vesper")
        observation["nearby_units"] = [{"guid": i, "name": f"Mob {i}", "distance": i} for i in range(20)]
        observation["inventory"] = [{"guid": i, "name": f"Item {i}"} for i in range(24)]
        self.client.observations.clear()
        self.client.observe = lambda *args, **kwargs: deepcopy(observation)
        projection = _projection(self.inspector.presence_root)
        for lane, mode in (("body", "gameplay"), ("social", "social_gameplay")):
            with self.subTest(lane=lane):
                # Exercise the default projection independently of live model settings.
                with patch("presence_acore.model_context._read_json", return_value=({}, "no_recorded_request")):
                    value = self.inspector.model_context(lane=lane, source="live_preview")
                self.assertTrue(value["available"])
                preview = value["preview"]
                self.assertEqual(preview["native_observation"], projection({**observation, '_fresh': True}, mode))
                self.assertFalse(preview["is_actual_request"])
                self.assertEqual(preview["basis"], "fresh_bridge_snapshot")
                self.assertIn("controller_enrichment", preview["unavailable_sections"])
                self.assertIn("images", preview["unavailable_sections"])
                self.assertNotIn("capture", value)
                self.assertEqual(value["view_kind"], "live_projection_preview")

    def test_failed_preview_never_returns_exception_details(self):
        self.client.failure = ValueError("DO-NOT-ECHO")
        value = self.inspector.model_context(source="live_preview")
        self.assertFalse(value["available"])
        self.assertEqual(value["error"]["code"], "preview_unavailable")
        self.assertNotIn("DO-NOT-ECHO", json.dumps(value))

    def test_standalone_schema_and_dispatch_defaults_social_lane_and_input_rejection(self):
        initialize(self.server)
        tools = self.server.handle(request("tools/list"))["result"]["tools"]
        tool = next(item for item in tools if item["name"] == "wow_model_context")
        self.assertFalse(tool["inputSchema"]["additionalProperties"])
        self.assertEqual(tool["inputSchema"]["properties"]["lane"]["enum"], ["body", "social"])
        self.write("runtime-game-player-context-social.json", capture("social"))
        result = self.server.handle(request("tools/call", {"name": "wow_model_context",
                                                         "arguments": {"lane": "social"}}))["result"]
        self.assertFalse(result["isError"])
        self.assertEqual(result["structuredContent"]["lane"], "social")
        result = self.server.handle(request("tools/call", {"name": "wow_model_context"}))["result"]
        self.assertTrue(result["isError"])
        self.assertEqual(result["structuredContent"]["error"]["code"], "no_recorded_request")
        for arguments in ({"lane": []}, {"lane": True}, {"source": "raw"}, {"source": None},
                          {"character": "Aurenne"}, {"path": "secret.json"}, {"action": "attack"}, []):
            with self.subTest(arguments=arguments):
                self.assertEqual(self.server.handle(request("tools/call", {"name": "wow_model_context",
                    "arguments": arguments}))["error"]["code"], -32602)
        self.assertEqual(self.client.observations, [])

    def test_direct_parameters_are_validated_before_any_file_or_bridge_read(self):
        for arguments in ({"lane": []}, {"lane": "unknown"}, {"source": {}}, {"source": "../private"}):
            with patch.object(Path, "open", side_effect=AssertionError("must not read")):
                with self.assertRaises(ValueError):
                    self.inspector.model_context(**arguments)
        self.assertEqual(self.client.observations, [])


class ProjectionLoaderTests(unittest.TestCase):
    CONTEXT = """\
from tools.game_player_native_gear import stamp, LOAD_TOKEN
from tools.game_player_native_gear import LOAD_TOKEN as SECOND_TOKEN
assert LOAD_TOKEN is SECOND_TOKEN

def compact_native_observation(observation, mode='gameplay'):
    return {'helper': stamp(observation['number']), 'mode': mode}
"""
    HELPER = """\
import math
LOAD_TOKEN = object()

def stamp(number):
    return math.sqrt(number)
"""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="projection-loader-unit-", dir=Path(__file__).parent)
        self.root = Path(self.directory.name)
        self.tools = self.root / "backend" / "tools"
        self.tools.mkdir(parents=True)
        self.context = self.tools / "game_player_native_context.py"
        self.helper = self.tools / "game_player_native_gear.py"
        self.context.write_text(self.CONTEXT, encoding="utf-8")
        self.helper.write_text(self.HELPER, encoding="utf-8")

    def tearDown(self):
        self.directory.cleanup()

    def test_on_demand_preview_grounds_real_ready_offers_without_fabricating_controller_state(self):
        helper = Path('C:/Files/Programs/Codex/Presence/working/backend/tools/game_player_native_item_use.py')
        if not helper.is_file():
            self.skipTest('Presence item-use projection source is not installed')
        (self.tools / helper.name).write_bytes(helper.read_bytes())
        self.context.write_text(
            'from tools.game_player_native_item_use import item_use_context\n'
            'def compact_native_observation(value, mode="gameplay"):\n'
            '    return {"item_choices": item_use_context(value), "controller": value.get("controller")}\n',
            encoding='utf-8')
        action = {'type': 'use_item', 'item_guid': '123'}
        raw = {'sequence': 8, 'self': {'alive': True}, 'inventory': [{'guid': '123', 'count': 1,
            'use_state': {'supported': True, 'ready': True, 'target_mode': 'self', 'scope': 'self_restoration_v1',
                'cooldown_ms': 0, 'spell_id': 439, 'restores_health': True, 'next_action': action}}]}
        original = deepcopy(raw)
        client = FakeClient()
        client.observe = lambda *args, **kwargs: raw
        inspector = Inspector(client, presence_root=self.root, data_dir=self.root)
        for lane in ('body', 'social'):
            value = inspector.model_context(lane=lane, source='live_preview')
            self.assertTrue(value['available'])
            view = value['preview']['native_observation']
            self.assertEqual(view['item_choices']['candidates'][0]['next_action'], action)
            self.assertIsNone(view['controller'])
            self.assertFalse(value['preview']['is_actual_request'])
        self.assertEqual(raw, original)
        raw['_fresh'] = False
        stale = inspector.model_context(lane='social', source='live_preview')
        self.assertEqual(stale['preview']['native_observation']['item_choices']['candidates'], [])

    def test_fresh_standalone_loader_needs_no_tools_package_or_global_import_mutation(self):
        # -I -S removes the current directory, PYTHONPATH, and site packages.
        # The child imports only the stdlib harness and these fixed fixtures.
        code = textwrap.dedent("""\
            import builtins
            import math
            from pathlib import Path
            import sys
            sys.path.insert(0, sys.argv[2])
            from presence_acore.model_context import _projection
            assert not any(name == 'tools' or name.startswith('tools.') for name in sys.modules)
            before_path = list(sys.path)
            normal_import = builtins.__import__

            def guard(name, globals=None, locals=None, fromlist=(), level=0):
                if name == 'tools' or name.startswith(('tools.', 'app.')):
                    raise AssertionError('External package import was attempted: ' + name)
                return normal_import(name, globals, locals, fromlist, level)

            builtins.__import__ = guard
            projection = _projection(Path(sys.argv[1]))
            assert projection({'number': 81}, 'gameplay') == {'helper': 9.0, 'mode': 'gameplay'}
            assert projection({'number': 16}, 'social') == {'helper': 4.0, 'mode': 'social'}
            assert builtins.__import__ is guard
            assert sys.path == before_path
            assert not any(name == 'tools' or name.startswith('tools.') for name in sys.modules)
            assert 'presence_readonly_native_gear' not in sys.modules
            assert 'presence_readonly_native_projection' not in sys.modules
            assert not list(Path(sys.argv[1]).rglob('__pycache__'))
            print('isolated projection passed')
        """)
        process = subprocess.run(
            [sys.executable, "-I", "-S", "-B", "-c", code, str(self.root), str(Path(__file__).resolve().parents[1])],
            capture_output=True, text=True, timeout=15, check=False,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(process.stdout.strip(), "isolated projection passed")
        self.assertFalse(list(self.root.rglob("__pycache__")))

    def test_old_projection_without_helper_import_remains_lazy_and_compatible(self):
        self.helper.unlink()
        self.context.write_text(
            "def compact_native_observation(observation, mode='gameplay'):\n"
            "    return {'sequence': observation['sequence'], 'mode': mode}\n", encoding="utf-8",
        )
        original = Path.open
        opened = []

        def track(path, *args, **kwargs):
            opened.append(path.name)
            return original(path, *args, **kwargs)

        with patch.object(Path, "open", track):
            projection = _projection(self.root)
            self.assertEqual(projection({"sequence": 42}), {"sequence": 42, "mode": "gameplay"})
        self.assertEqual(opened, ["game_player_native_context.py"])

    def test_only_exact_absolute_helper_import_is_special_cased(self):
        original = builtins.__import__
        delegated = []

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name.startswith("tools") or level:
                delegated.append((name, level))
                raise ImportError("Ordinary import delegation was preserved.")
            return original(name, globals, locals, fromlist, level)

        for name, level in (("tools.game_player_native_gear_extra", 0), ("tools", 0),
                            ("tools.game_player_native_gear", 1),
                            ("tools.game_player_native_buffs_extra", 0),
                            ("tools.game_player_native_quest_items_extra", 0),
                            ("tools.game_player_native_buffs", 1),
                            ("tools.game_player_native_quest_items", 1)):
            with self.subTest(name=name, level=level):
                self.context.write_text(
                    f"__import__({name!r}, globals(), locals(), ('stamp',), {level})\n", encoding="utf-8",
                )
                with patch.object(builtins, "__import__", guarded_import):
                    with self.assertRaises(ImportError):
                        _projection(self.root)
                self.assertEqual(delegated[-1], (name, level))

    def test_fixed_buff_and_quest_helpers_are_lazy_cached_and_private(self):
        for helper in ("game_player_native_buffs", "game_player_native_quest_items"):
            with self.subTest(helper=helper):
                path = self.tools / (helper + ".py")
                path.write_text("from math import sqrt\ndef stamp(value): return sqrt(value)\n", encoding="utf-8")
                self.context.write_text(
                    "def compact_native_observation(value, mode='gameplay'):\n"
                    f"    from tools.{helper} import stamp\n"
                    "    return {'number': stamp(value['number'])}\n", encoding="utf-8")
                original_open, original_import = Path.open, builtins.__import__
                opened, before_path, before_modules = [], list(sys.path), set(sys.modules)

                def track(path, *args, **kwargs):
                    opened.append(path.name)
                    return original_open(path, *args, **kwargs)

                def deny_tools(name, globals=None, locals=None, fromlist=(), level=0):
                    if name == 'tools' or name.startswith(('tools.', 'app.', 'openai', 'anthropic')):
                        raise AssertionError('Runtime imports are forbidden')
                    return original_import(name, globals, locals, fromlist, level)

                with patch.object(Path, 'open', track), patch.object(builtins, '__import__', deny_tools):
                    projection = _projection(self.root)
                    self.assertEqual(opened, ['game_player_native_context.py'])
                    self.assertEqual(projection({'number': 25}), {'number': 5.0})
                    self.assertEqual(projection({'number': 36}), {'number': 6.0})
                    self.assertEqual(opened.count(path.name), 1)
                self.assertEqual(sys.path, before_path)
                self.assertFalse(any(name.startswith(('tools.', 'presence_readonly_', 'openai', 'anthropic'))
                    for name in set(sys.modules) - before_modules))
                self.assertFalse(list(self.root.rglob('__pycache__')))

    def test_current_installed_projection_uses_only_fixed_pure_helpers(self):
        source = Path('C:/Files/Programs/Codex/Presence/working/backend/tools')
        names = ['game_player_native_' + suffix + '.py'
            for suffix in ('context', 'gear', 'attention', 'focus', 'buffs', 'quest_items',
                'combat', 'pickup_surroundings')]
        if not all((source / name).is_file() for name in names):
            self.skipTest('Current Presence pure projections are not installed')
        for name in names:
            (self.tools / name).write_bytes((source / name).read_bytes())
        for suffix in ('item_use', 'loot_rolls', 'taxi'):
            helper = source / ('game_player_native_' + suffix + '.py')
            if helper.is_file():
                (self.tools / helper.name).write_bytes(helper.read_bytes())
        original_import, before_path, before_modules = builtins.__import__, list(sys.path), set(sys.modules)

        def deny_runtime(name, globals=None, locals=None, fromlist=(), level=0):
            if name == 'tools' or name.startswith(('tools.', 'app.', 'openai', 'anthropic')):
                raise AssertionError('Runtime imports are forbidden')
            return original_import(name, globals, locals, fromlist, level)

        observation = {'self': {'guid': '42', 'name': 'Vesper', 'class': 2, 'level': 12},
            'inventory': [], 'equipment': [], 'nearby_units': [], 'quests': [], 'known_spells': []}
        before = deepcopy(observation)
        with patch.object(builtins, '__import__', deny_runtime):
            projection = _projection(self.root)
            self.assertIsInstance(projection(observation, 'gameplay'), dict)
            self.assertIsInstance(projection(observation, 'social'), dict)
        self.assertEqual(observation, before)
        self.assertEqual(sys.path, before_path)
        self.assertFalse(any(name.startswith(('tools.', 'presence_readonly_', 'openai', 'anthropic'))
            for name in set(sys.modules) - before_modules))
        self.assertFalse(list(self.root.rglob('__pycache__')))

    def test_missing_or_oversize_helper_fails_closed_before_observation_without_echo(self):
        for kind in ("missing", "oversize"):
            with self.subTest(kind=kind):
                if kind == "missing":
                    self.helper.unlink(missing_ok=True)
                else:
                    self.helper.write_bytes(b"# DO-NOT-ECHO\n" + b"x" * MAX_CAPTURE_BYTES)
                client = FakeClient()
                inspector = Inspector(client, presence_root=self.root, data_dir=self.root)
                value = inspector.model_context(source="live_preview")
                self.assertFalse(value["available"])
                self.assertEqual(value["error"]["code"], "preview_unavailable")
                self.assertNotIn("preview", value)
                self.assertNotIn("DO-NOT-ECHO", json.dumps(value))
                self.assertEqual(client.observations, [])
                self.assertFalse(list(self.root.rglob("__pycache__")))

    def test_helper_is_compiled_once_per_projection_without_registering_a_module(self):
        original = Path.open
        opened = []
        before_path = list(sys.path)
        private_before = {name for name in sys.modules if name.startswith("presence_readonly_native_")}

        def track(path, *args, **kwargs):
            opened.append(path.name)
            return original(path, *args, **kwargs)

        with patch.object(Path, "open", track):
            projection = _projection(self.root)
            self.assertEqual(projection({"number": 25})["helper"], 5.0)
            self.assertEqual(projection({"number": 36})["helper"], 6.0)
        self.assertEqual(opened.count("game_player_native_gear.py"), 1)
        self.assertEqual(sys.path, before_path)
        self.assertEqual({name for name in sys.modules if name.startswith("presence_readonly_native_")}, private_before)
        self.assertFalse(list(self.root.rglob("__pycache__")))

    def test_actual_staged_projection_preserves_gear_labels_guidance_and_raw_snapshot(self):
        workspace = Path(__file__).resolve().parents[2]
        source_directory = workspace / "gear-integration" / "stage"
        if not (source_directory / self.helper.name).is_file():
            source_directory = Path("C:/Files/Programs/Codex/Presence/working/backend/tools")
        if not all((source_directory / target.name).is_file() for target in (self.context, self.helper)):
            self.skipTest("Presence gear projection source is not installed")
        for target in (self.context, self.helper):
            target.write_bytes((source_directory / target.name).read_bytes())
        for suffix in ('attention', 'focus', 'buffs', 'quest_items', 'combat', 'pickup_surroundings', 'item_use'):
            dependency = source_directory / ('game_player_native_' + suffix + '.py')
            if dependency.is_file():
                (self.tools / dependency.name).write_bytes(dependency.read_bytes())
        observation = {
            "sequence": 8, "self": {"name": "Vesper", "class": 2, "level": 12},
            "inventory": [{"guid": "100", "name": "Test sword", "class": 2, "inventory_type": 13,
                           "damage_min": 10, "damage_max": 20, "delay_ms": 2000,
                           "stats": [{"type": 4, "value": 3}], "usable": True, "can_equip_now": True}],
            "equipment": [{"guid": "101", "name": "Test chest", "class": 4,
                           "stats": [{"type": 7, "value": 2}]}],
            "inspected_item": {"guid": "100", "class": 2,
                               "damage_min": 10, "damage_max": 20, "delay_ms": 2000,
                               "stats": [{"type": 4, "value": 3}]},
        }
        before = deepcopy(observation)
        client = FakeClient()
        client.observe = lambda *args, **kwargs: deepcopy(observation)
        inspector = Inspector(client, presence_root=self.root, data_dir=self.root)
        original_import = builtins.__import__

        def deny_tools(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "tools" or name.startswith(("tools.", "app.")):
                raise AssertionError("Presence imports are forbidden in standalone inspection.")
            return original_import(name, globals, locals, fromlist, level)

        with patch.object(builtins, "__import__", deny_tools):
            value = inspector.model_context(source="live_preview")
            social = inspector.model_context(lane="social", source="live_preview")
        self.assertTrue(value["available"])
        view = value["preview"]["native_observation"]
        self.assertEqual(view["item_fact_formats"]["stat_names"], {"4": "Strength", "7": "Stamina"})
        self.assertEqual(view["inventory"][0]["stats"], [[4, 3]])
        self.assertEqual({key: view["inventory"][0][key] for key in ("damage_min", "damage_max", "delay_ms")},
                         {"damage_min": 10, "damage_max": 20, "delay_ms": 2000})
        for item in view["inventory"] + view["equipment"]:
            self.assertNotIn("base_component_dps", item)
        self.assertEqual(view["inspected_item"]["base_component_dps"], 7.5)
        self.assertIn("first template damage component", view["item_fact_formats"]["base_component_dps"])
        self.assertEqual(view["gear_guidance"]["source"], "advisory_default")
        self.assertIn("not an observed talent specialization", view["gear_guidance"]["profile"])
        self.assertTrue(social["available"])
        self.assertEqual(social["preview"]["native_observation"]["gear_guidance"], view["gear_guidance"])
        legacy_social = _projection(self.root)(observation, "social")
        self.assertNotIn("gear_guidance", legacy_social)
        self.assertEqual(observation, before)
        self.assertFalse(list(self.root.rglob("__pycache__")))


if __name__ == "__main__":
    unittest.main()
