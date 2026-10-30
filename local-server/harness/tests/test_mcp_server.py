from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from presence_acore.client import BridgeError
from presence_acore.mcp_server import Inspector, MAX_FRAME_BYTES, PROTOCOL_VERSION, Server, serve


class FakeClient:
    def __init__(self) -> None:
        self.observations = []
        self.failure = None

    def observe(self, character, after_event_id=0):
        self.observations.append((character, after_event_id))
        if self.failure:
            raise self.failure
        return {"sequence": 5, "self": {"name": character, "level": 1, "race": 10, "class": 2},
                "events": [{"id": 9, "text": "Greetings, traveller. ♥"}], "event_cursor": 9}


def request(method, params=None, request_id=1):
    result = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        result["params"] = params
    return result


def initialize(server):
    response = server.handle(request("initialize", {
        "protocolVersion": PROTOCOL_VERSION, "capabilities": {},
        "clientInfo": {"name": "offline-test", "version": "1"},
    }))
    server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"})
    return response


class McpServerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="mcp-unit-", dir=Path(__file__).parent)
        self.data_dir = Path(self.directory.name)
        self.client = FakeClient()
        self.inspector = Inspector(self.client, data_dir=self.data_dir)
        self.server = Server(self.inspector)

    def tearDown(self):
        self.directory.cleanup()

    def write(self, filename, value):
        (self.data_dir / filename).write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def test_initialize_negotiates_supported_version_and_lists_only_read_tools(self):
        response = initialize(self.server)
        self.assertEqual(response["result"]["protocolVersion"], PROTOCOL_VERSION)
        self.assertEqual(response["result"]["capabilities"], {"tools": {"listChanged": False}})
        tools = self.server.handle(request("tools/list"))["result"]["tools"]
        self.assertEqual({tool["name"] for tool in tools}, {"wow_status", "wow_observe", "wow_model_context"})
        for tool in tools:
            self.assertTrue(tool["annotations"]["readOnlyHint"])
            self.assertFalse(tool["annotations"]["destructiveHint"])
            self.assertFalse(tool["inputSchema"]["additionalProperties"])
        self.assertEqual(self.client.observations, [])

    def test_ping_before_initialize_and_lifecycle_enforcement(self):
        self.assertEqual(self.server.handle(request("ping"))["result"], {})
        self.assertEqual(self.server.handle(request("tools/list"))["error"]["code"], -32002)
        self.assertEqual(self.server.handle(request("initialize", {}))["error"]["code"], -32602)
        response = self.server.handle(request("initialize", {
            "protocolVersion": "2099-01-01", "capabilities": {},
            "clientInfo": {"name": "new-client", "version": "1"},
        }))
        self.assertEqual(response["result"]["protocolVersion"], PROTOCOL_VERSION)
        self.assertEqual(self.server.handle(request("tools/list"))["error"]["code"], -32002)
        self.server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self.assertIn("tools", self.server.handle(request("tools/list"))["result"])

    def test_observe_returns_live_data_and_preserves_cursor_and_unicode(self):
        initialize(self.server)
        result = self.server.handle(request("tools/call", {"name": "wow_observe", "arguments": {"since": 7}}))["result"]
        self.assertFalse(result["isError"])
        self.assertEqual(self.client.observations, [("Vesper", 7)])
        self.assertEqual(result["structuredContent"]["observation"]["event_cursor"], 9)
        self.assertEqual(json.loads(result["content"][0]["text"]), result["structuredContent"])
        self.assertIn("♥", result["content"][0]["text"])

    def test_status_combines_live_full_social_and_recent_chronicle(self):
        self.write("runtime-game-player-status.json", {
            "running": True, "game_backend": "azerothcore", "controlled_character": "Vesper",
            "last_tick_at": "2026-10-23T00:00:00Z", "model_api_key": "DO-NOT-ECHO",
            "last_error": "DO-NOT-ECHO", "last_decision": {"action": "move_to", "secret": "DO-NOT-ECHO"},
            "last_execution": {"status": "accepted", "action_id": "test-action"},
            "native_observation_sequence": 42,
        })
        self.write("runtime-game-player-state.json", {"pid": 424242, "command": ["DO-NOT-ECHO"]})
        self.write("runtime-game-player-control.json", {"paused": True, "stop": False})
        self.write("runtime-game-player-social-status.json", {"running": False, "game_backend": "azerothcore",
                   "controlled_character": "Vesper", "scene_ledger_text": "At the gates."})
        cards = [{"id": str(i), "summary": f"Memory {i}", "companion_character": "Vesper", "api_key": "DO-NOT-ECHO"} for i in range(4)]
        (self.data_dir / "game-player-social-marked-moments.jsonl").write_text(
            "\n".join(json.dumps(card) for card in cards) + "\n", encoding="utf-8")
        with patch("presence_acore.mcp_server._pid_alive", return_value=False):
            status = self.inspector.status(2)
        self.assertTrue(status["inspection_only"])
        self.assertTrue(status["live"]["available"])
        full = status["presence"]["full"]
        self.assertTrue(full["reported_running"])
        self.assertFalse(full["process_alive"])
        self.assertTrue(full["pause_requested"])
        self.assertTrue(full["last_error_present"])
        self.assertEqual(full["last_decision"], {"action": "move_to"})
        self.assertEqual(full["last_execution"], {"status": "accepted", "action_id": "test-action"})
        self.assertEqual(full["native_observation_sequence"], 42)
        self.assertEqual(status["presence"]["social"]["scene_ledger_text"], "At the gates.")
        self.assertEqual([card["id"] for card in status["chronicle"]["entries"]], ["3", "2"])
        self.assertNotIn("DO-NOT-ECHO", json.dumps(status))

    def test_runtime_does_not_attribute_another_characters_old_decision(self):
        self.write("runtime-game-player-status.json", {
            "running": False, "game_backend": "window", "controlled_character": "Vaelith",
            "last_decision": {"action": "follow_focus"}, "scene_ledger_text": "Another character's trip",
        })
        full = self.inspector.status(0)["presence"]["full"]
        self.assertFalse(full["attributed_to_configured_character"])
        self.assertNotIn("last_decision", full)
        self.assertNotIn("scene_ledger_text", full)

    def test_chronicle_excludes_other_characters_and_unattributed_records(self):
        cards = [
            {"id": "vesper-old", "summary": "A Vesper memory", "companion_character": "Vesper"},
            {"id": "other", "summary": "Another character's memory", "companion_character": "Vaelith"},
            {"id": "unknown", "summary": "An unattributed memory"},
            {"id": "empty", "summary": "No attribution", "companion_character": ""},
            {"id": "vesper-new", "summary": "A newer memory", "companion_character": " vesper "},
        ]
        (self.data_dir / "game-player-social-marked-moments.jsonl").write_text(
            "\n".join(json.dumps(card) for card in cards) + "\n", encoding="utf-8")
        chronicle = self.inspector.status(10)["chronicle"]
        self.assertEqual([card["id"] for card in chronicle["entries"]], ["vesper-new", "vesper-old"])
        self.assertEqual(chronicle["character_scope"], "Vesper")
        self.assertIn("unattributed records are skipped", chronicle["context"])

    def test_bridge_failure_is_tool_error_without_echoing_exception_secrets(self):
        initialize(self.server)
        self.client.failure = BridgeError("credentials_unavailable", "sensitive password DO-NOT-ECHO")
        response = self.server.handle(request("tools/call", {"name": "wow_observe"}))
        self.assertTrue(response["result"]["isError"])
        self.assertNotIn("DO-NOT-ECHO", json.dumps(response))
        status = self.server.handle(request("tools/call", {"name": "wow_status"}))["result"]
        self.assertFalse(status["isError"])
        self.assertFalse(status["structuredContent"]["live"]["available"])
        self.assertEqual(status["structuredContent"]["presence"]["full"]["availability"], "missing")

    def test_tool_arguments_reject_writes_other_characters_and_invalid_values(self):
        initialize(self.server)
        bad = [
            {"name": "wow_action", "arguments": {"type": "attack"}},
            {"name": "wow_observe", "arguments": {"character": "Aurenne"}},
            {"name": "wow_observe", "arguments": {"since": True}},
            {"name": "wow_observe", "arguments": {"since": -1}},
            {"name": "wow_observe", "arguments": {"since": 1.5}},
            {"name": "wow_status", "arguments": {"chronicle_limit": 11}},
            {"name": "wow_status", "arguments": []},
            {"name": ["wow_status"]},
        ]
        for params in bad:
            with self.subTest(params=params):
                self.assertEqual(self.server.handle(request("tools/call", params))["error"]["code"], -32602)
        self.assertEqual(self.client.observations, [])

    def test_notifications_never_receive_replies_or_invoke_tools(self):
        initialize(self.server)
        for method in ("notifications/cancelled", "unknown_notification", "tools/call"):
            self.assertIsNone(self.server.handle({"jsonrpc": "2.0", "method": method,
                                                  "params": {"name": "wow_observe"}}))
        self.assertEqual(self.client.observations, [])

    def test_stdio_is_only_newline_json_and_survives_bad_frames(self):
        messages = [request("initialize", {"protocolVersion": PROTOCOL_VERSION, "capabilities": {},
                     "clientInfo": {"name": "offline", "version": "1"}}),
                    {"jsonrpc": "2.0", "method": "notifications/initialized"},
                    request("tools/call", {"name": "wow_observe"}, request_id="♥")]
        raw = b"{bad json}\n" + b"\xff\n" + b'{"jsonrpc":"2.0","id":1,"id":2,"method":"ping"}\n'
        raw += b"\n".join(json.dumps(message, ensure_ascii=False).encode("utf-8") for message in messages) + b"\n"
        outgoing = BytesIO()
        self.assertEqual(serve(self.server, BytesIO(raw), outgoing), 0)
        responses = [json.loads(line.decode("utf-8")) for line in outgoing.getvalue().splitlines()]
        self.assertEqual(len(responses), 5)
        self.assertTrue(all(response["error"]["code"] == -32700 for response in responses[:3]))
        self.assertEqual(responses[-1]["id"], "♥")
        self.assertTrue(responses[-1]["result"]["structuredContent"]["available"])

    def test_nonfinite_json_and_batch_are_rejected(self):
        outgoing = BytesIO()
        serve(self.server, BytesIO(b'{"jsonrpc":"2.0","id":NaN,"method":"ping"}\n[]\n'), outgoing)
        responses = [json.loads(line) for line in outgoing.getvalue().splitlines()]
        self.assertEqual([response["error"]["code"] for response in responses], [-32700, -32600])

    def test_oversize_or_unterminated_frame_is_bounded_and_closes(self):
        for raw in (b"x" * (MAX_FRAME_BYTES + 100) + b"\n", b'{"jsonrpc":"2.0"}'):
            with self.subTest(length=len(raw)):
                outgoing = BytesIO()
                self.assertEqual(serve(self.server, BytesIO(raw), outgoing), 1)
                self.assertEqual(json.loads(outgoing.getvalue())["error"]["code"], -32700)

    def test_output_bounds_and_recursive_secret_key_removal(self):
        self.client.observe = lambda *args, **kwargs: {
            "inventory": [{"name": "x" * 6000, "password": "DO-NOT-ECHO"}] * 150,
            "nested": {"authorization": "DO-NOT-ECHO", "public": "yes"},
        }
        result = self.inspector.live()["observation"]
        self.assertEqual(len(result["inventory"]), 128)
        self.assertEqual(len(result["inventory"][0]["name"]), 4096)
        self.assertNotIn("DO-NOT-ECHO", json.dumps(result))

    def test_does_not_read_configs_or_follow_arbitrary_status_file_paths(self):
        self.write("runtime-game-player-social-status.json", {
            "adventure_ledger_path": str(self.data_dir / "sensitive.json"),
            "credentials_file": str(self.data_dir / "sensitive.json"),
        })
        self.write("sensitive.json", {"password": "DO-NOT-ECHO"})
        original_open = Path.open
        opened = []

        def track(path, *args, **kwargs):
            opened.append(path.name)
            return original_open(path, *args, **kwargs)

        with patch.object(Path, "open", track):
            status = self.inspector.status()
        self.assertNotIn("sensitive.json", opened)
        self.assertFalse(any("config" in name for name in opened))
        self.assertNotIn("DO-NOT-ECHO", json.dumps(status))


if __name__ == "__main__":
    unittest.main()
