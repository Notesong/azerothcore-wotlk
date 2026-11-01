from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from presence_acore.mcp_server import Inspector, Server, dispatch_operation, gateway_dispatch


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(self.tmp.cleanup)
        self.inspector = Inspector(Mock(), data_dir=Path(self.tmp.name))

    def test_status_needs_no_mutation_uuid_and_preserves_sdk_session(self):
        manager = Mock()
        manager.status.return_value = {"character": "Vesper", "state": "active"}
        with patch("presence_acore.mcp_control.default_manager", return_value=manager):
            value = dispatch_operation(self.inspector, {"operation": "control", "action": "status", "owner_session": "sdk-session"})
        manager.status.assert_called_once_with(owner_session="sdk-session")
        self.assertEqual(value["state"], "active")

    def test_actions_pass_token_and_real_owner_out_of_band(self):
        manager = Mock()
        manager.act.return_value = {"character": "Vesper", "available": True}
        action = {"type": "target", "target_guid": "18446744073709551615"}
        with patch("presence_acore.mcp_control.default_manager", return_value=manager):
            dispatch_operation(self.inspector, {"operation": "act", "owner_session": "sdk-session", "control_token": "b"*64,
                "operation_id": "53fc9301-fcd7-499d-9469-502dc7e1cdb1", "action": action})
        self.assertEqual(manager.act.call_args.kwargs["control_token"], "b"*64)
        self.assertEqual(manager.act.call_args.kwargs["owner_session"], "sdk-session")
        self.assertEqual(manager.act.call_args.kwargs["action"], action)

    def test_only_fixed_operations_and_roots(self):
        for request in ({"operation": "recover"}, {"operation": "observe", "character": "Other"},
                        {"operation": "full_context", "path": "C:/secret"}, {"operation": "wait", "host": "example.com"}):
            self.assertIn("error", dispatch_operation(self.inspector, request))

    def test_stdio_cannot_supply_server_owner_or_internal_cleanup_tool(self):
        server = Server(self.inspector)
        server.initialized = server.ready = True
        value = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
            "name": "wow_control", "arguments": {"action": "status", "owner_session": "pretend"}}})
        self.assertEqual(value["error"]["code"], -32602)
        self.assertNotIn("recover", str(server.tools()))

    def test_fixed_gateway_only_selects_capability_mode_for_remote_control_and_actions(self):
        manager = Mock()
        manager.status.return_value = {"character": "Vesper", "state": "active"}
        for mode_field in ({}, {"authorization_mode": "lease_token"}):
            with patch("presence_acore.mcp_server.Inspector", return_value=self.inspector), \
                    patch("presence_acore.mcp_control.default_manager", return_value=manager) as factory:
                gateway_dispatch({"operation": "control", "action": "status", "owner_session": "sdk-session",
                    "control_token": "b" * 64, **mode_field})
                factory.assert_called_once_with(self.inspector.client, authorization_mode="lease_token")
                manager.status.assert_called_with(owner_session="sdk-session", control_token="b" * 64)

    def test_public_dispatch_and_stdio_cannot_request_capability_mode(self):
        request = {"operation": "control", "action": "status", "authorization_mode": "lease_token"}
        with patch("presence_acore.mcp_control.default_manager") as factory:
            self.assertIn("error", dispatch_operation(self.inspector, request))
            factory.assert_not_called()
        server = Server(self.inspector)
        server.initialized = server.ready = True
        value = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
            "name": "wow_control", "arguments": {"action": "status", "authorization_mode": "lease_token"}}})
        self.assertEqual(value["error"]["code"], -32602)

    def test_gateway_rejects_unexpected_internal_mode_and_mode_on_reads(self):
        with patch("presence_acore.mcp_control.default_manager") as factory:
            for request in ({"operation": "control", "action": "status", "authorization_mode": "sdk_session"},
                            {"operation": "control", "action": "status", "authorization_mode": None},
                            {"operation": "observe", "authorization_mode": "lease_token"}):
                self.assertIn("error", gateway_dispatch(request))
            factory.assert_not_called()


if __name__ == "__main__": unittest.main()
