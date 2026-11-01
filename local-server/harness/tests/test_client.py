from __future__ import annotations

import base64
import json
import socket
import threading
import unittest

from presence_acore import BridgeError, Client


class FakeRA:
    def __init__(self, *, result=None, error=None, wrong_id=False, authenticate=True, missing=False):
        self.listener = socket.socket()
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(1)
        self.port = self.listener.getsockname()[1]
        self.result = result if result is not None else {"events": [{"text": "AC> is ordinary chat text"}]}
        self.error = error
        self.wrong_id = wrong_id
        self.authenticate = authenticate
        self.missing = missing
        self.request = None
        self.exception = None
        self.thread = threading.Thread(target=self.run, daemon=True)

    def __enter__(self):
        self.thread.start()
        return Client({"host": "127.0.0.1", "port": self.port, "timeout": 3,
                       "credentials": {"Username": "TEST", "Password": "test-secret"}})

    def __exit__(self, *_):
        self.thread.join(4)
        self.listener.close()
        if self.exception:
            raise self.exception

    def run(self):
        try:
            with self.listener.accept()[0] as conn:
                conn.settimeout(3)
                stream = conn.makefile("rb")
                conn.sendall(b"Authentication Required\r\nUser")
                conn.sendall(b"name: ")
                assert stream.readline() == b"TEST\r\n"
                conn.sendall(b"Password: ")
                assert stream.readline() == b"test-secret\r\n"
                if not self.authenticate:
                    conn.sendall(b"Authentication failed\r\n")
                    return
                conn.sendall(b"Welcome\r\nAC>")
                line = stream.readline().decode().strip()
                assert line.startswith("presence request ")
                self.request = json.loads(base64.b64decode(line.split(" ", 2)[2]))
                if self.missing:
                    conn.sendall(b"No such command\r\nAC>")
                    return
                response = {"v": 1, "id": "wrong" if self.wrong_id else self.request["id"],
                            "op": self.request["op"], "character": self.request["character"], "ok": self.error is None}
                response.update({"error": self.error} if self.error else {"result": self.result})
                message = ("PRESENCE_JSON:" + json.dumps(response, ensure_ascii=False) + "\r\nAC>").encode()
                for offset in range(0, len(message), 13):
                    conn.sendall(message[offset:offset + 13])
        except Exception as exc:
            self.exception = exc


class ClientTests(unittest.TestCase):
    def test_fragmented_utf8_response_and_prompt_in_chat(self):
        fake = FakeRA(result={"events": [{"text": "Vesper: café AC> hello"}]})
        with fake as client:
            result = client.observe("Vesper", after_event_id=42)
        self.assertEqual(result["events"][0]["text"], "Vesper: café AC> hello")
        self.assertEqual(fake.request["since"], 42)
        self.assertEqual(fake.request["character"], "Vesper")

    def test_action_submission_is_not_completion(self):
        with FakeRA(result={"status": "accepted", "action_id": "walk-1"}) as client:
            result = client.execute("Vesper", {"type": "move_to", "x": 1, "y": 2, "z": 3}, request_id="walk-1")
        self.assertEqual(result["status"], "accepted")

    def test_game_error_is_typed(self):
        with FakeRA(error={"code": "out_of_range", "message": "Target is too far away."}) as client:
            with self.assertRaises(BridgeError) as caught:
                client.execute("Vesper", {"type": "cast", "spell_id": 1})
        self.assertEqual(caught.exception.code, "out_of_range")

    def test_guard_rejection_preserves_only_metadata_for_the_exact_request(self):
        event = {"type": "moon_guard_intervention", "attribution": "synchronous_action",
                 "request_id": "moon-action", "action_type": "attack", "protected_target_guid": "99",
                 "observed_sequence": 12, "hook": "action", "reason": "protected_target",
                 "credential": "must-not-pass", "nested": {"password": "must-not-pass"}}
        error = {"code": "protected_target", "message": "Protected creature.",
                 "guard_interventions": [event, {**event, "request_id": "different-action"}],
                 "guard_interventions_truncated": True, "guard_interventions_dropped": 7}
        with FakeRA(error=error) as client:
            with self.assertRaises(BridgeError) as caught:
                client.execute("Vesper", {"type": "attack", "target_guid": "99"}, request_id="moon-action")
        record = caught.exception.guard_interventions
        self.assertEqual(len(record), 1)
        self.assertEqual(record[0]["protected_target_guid"], "99")
        self.assertEqual(record[0]["observed_sequence"], 12)
        self.assertNotIn("credential", record[0])
        self.assertNotIn("nested", record[0])
        self.assertTrue(caught.exception.guard_interventions_truncated)
        self.assertEqual(caught.exception.guard_interventions_dropped, 7)

    def test_accepted_cast_keeps_guard_intervention_without_claiming_execution_failed(self):
        event = {"type": "moon_guard_intervention", "attribution": "synchronous_action",
                 "request_id": "moon-cast", "action_type": "cast", "protected_target_guid": "99",
                 "spell_id": 123, "cast_count": 0, "observed_sequence": 12}
        with FakeRA(result={"status": "accepted", "guard_interventions": [event]}) as client:
            result = client.execute("Vesper", {"type": "cast", "spell_id": 123}, request_id="moon-cast")
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(result["guard_interventions"], [event])

    def test_passive_unattributed_events_are_not_attached_to_a_planner_action(self):
        event = {"type": "moon_guard_intervention", "attribution": "unattributed_execution",
                 "request_id": "moon-cast", "protected_target_guid": "99"}
        error = BridgeError("protected_target", "Protected creature.", request_id="moon-cast",
                            guard_interventions=[event] * 100)
        self.assertEqual(error.guard_interventions, [])

    def test_guard_metadata_is_bounded(self):
        event = {"type": "moon_guard_intervention", "attribution": "synchronous_action",
                 "request_id": "moon-cast", "protected_target_guid": "99", "reason": "x" * 257,
                 "observed_sequence": True}
        error = BridgeError("protected_target", "Protected creature.", request_id="moon-cast",
                            guard_interventions=[event] * 100)
        self.assertEqual(len(error.guard_interventions), 16)
        self.assertNotIn("reason", error.guard_interventions[0])
        self.assertNotIn("observed_sequence", error.guard_interventions[0])

    def test_action_result_preserves_original_and_query_request_ids(self):
        fake = FakeRA(result={"response": {"result": {"status": "completed"}}})
        with fake as client:
            result = client.action_result("Vesper", "original-action-id")
        self.assertEqual(fake.request["request_id"], "original-action-id")
        self.assertNotEqual(fake.request["id"], "original-action-id")
        self.assertEqual(result["response"]["result"]["status"], "completed")

    def test_response_id_must_match(self):
        with FakeRA(wrong_id=True) as client:
            with self.assertRaises(BridgeError) as caught:
                client.observe("Vesper")
        self.assertEqual(caught.exception.code, "response_mismatch")

    def test_authentication_failure_does_not_include_password(self):
        with FakeRA(authenticate=False) as client:
            with self.assertRaises(BridgeError) as caught:
                client.capabilities()
        self.assertEqual(caught.exception.code, "authentication_failed")
        self.assertNotIn("test-secret", str(caught.exception))

    def test_missing_module_has_actionable_error(self):
        with FakeRA(missing=True) as client:
            with self.assertRaises(BridgeError) as caught:
                client.capabilities()
        self.assertEqual(caught.exception.code, "bridge_unavailable")

    def test_nonlocal_endpoint_and_nan_rejected(self):
        with self.assertRaises(BridgeError):
            Client({"host": "192.0.2.1"})
        client = Client({"credentials": {"Username": "TEST", "Password": "secret"}})
        with self.assertRaises(BridgeError) as caught:
            client.execute("Vesper", {"type": "move_to", "x": float("nan")})
        self.assertEqual(caught.exception.code, "invalid_request")


if __name__ == "__main__":
    unittest.main()
