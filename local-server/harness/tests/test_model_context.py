from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import tempfile
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
        for lane, mode in (("body", "gameplay"), ("social", "social")):
            with self.subTest(lane=lane):
                value = self.inspector.model_context(lane=lane, source="live_preview")
                self.assertTrue(value["available"])
                preview = value["preview"]
                self.assertEqual(preview["native_observation"], projection(observation, mode))
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


if __name__ == "__main__":
    unittest.main()
