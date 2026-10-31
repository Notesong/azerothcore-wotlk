from __future__ import annotations

from collections import deque
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import uuid

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "harness"))
from presence_acore import BridgeError


SPEC = importlib.util.spec_from_file_location("acore_startup_login", ROOT / "scripts" / "Ensure-Vesper-Online.py")
assert SPEC is not None and SPEC.loader is not None
login = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(login)

ATTACH_ID = "a6e15455-c6be-460c-87b2-84f1fc8127c5"


def offline(phase="Character is offline"):
    return BridgeError("character_offline", phase)


def owned():
    return {"self": {"name": "Vesper", "controller_owned": True}}


def accepted(request_id):
    return {"status": "accepted", "request_id": request_id, "phase": "loading"}


def receipt(request_id, *, status="completed", attached=True, ok=True, error_code="action_failed"):
    envelope = {
        "v": 1, "id": request_id, "op": "attach", "character": "Vesper", "ok": ok,
        "result": {"status": status, "attached": attached},
    }
    if not ok:
        envelope["error"] = {"code": error_code, "message": "Offline test rejection."}
    return {"request_id": request_id, "response": envelope}


class FakeTime:
    def __init__(self):
        self.now = 1000.0
        self.reads = 0

    def monotonic(self):
        self.reads += 1
        if self.reads > 5000:
            raise AssertionError("The login helper busy-looped without advancing its deadline.")
        return self.now

    def sleep(self, seconds):
        if seconds < 0:
            raise AssertionError("Negative sleep requested.")
        self.now += max(float(seconds), 0.001)


class FakeClient:
    """Only the three bridge operations needed for existing-character login."""

    def __init__(self, observations=(), *, attach=accepted, polls=(), poll_default=None,
                 online_after_polls=None, online_after_attach=False, observation_default=None):
        self.observations = deque(observations)
        self.attach_outcome = attach
        self.polls = deque(polls)
        self.poll_default = poll_default or BridgeError("unknown_request", "No cached request.")
        self.online_after_polls = online_after_polls
        self.online_after_attach = online_after_attach
        self.observation_default = observation_default
        self.observe_calls = []
        self.attach_calls = []
        self.result_calls = []

    @staticmethod
    def deliver(value, request_id=None):
        if callable(value):
            value = value(request_id)
        if isinstance(value, Exception):
            raise value
        return value

    def observe(self, character):
        if character != "Vesper":
            raise AssertionError("The helper attempted to inspect another character.")
        self.observe_calls.append(character)
        if self.observations:
            return self.deliver(self.observations.popleft())
        if (self.online_after_attach and self.attach_calls) or (
            self.online_after_polls is not None and len(self.result_calls) >= self.online_after_polls
        ):
            return owned()
        if self.observation_default is not None:
            return self.deliver(self.observation_default)
        raise offline("loading")

    def request(self, operation, character, *, request_id, **arguments):
        if operation != "attach" or character != "Vesper":
            raise AssertionError("Startup must never create, detach, act, or control another character.")
        if set(arguments) - {"account"} or arguments.get("account", "PRESENCE") != "PRESENCE":
            raise AssertionError("Unexpected login arguments or account.")
        self.attach_calls.append((operation, character, request_id))
        return self.deliver(self.attach_outcome, request_id)

    def action_result(self, character, request_id):
        if character != "Vesper":
            raise AssertionError("The helper queried another character's result.")
        self.result_calls.append((character, request_id))
        value = self.polls.popleft() if self.polls else self.poll_default
        return self.deliver(value, request_id)


class StartupLoginTests(unittest.TestCase):
    def run_ensure(self, client, timeout=3.0):
        self.clock = FakeTime()
        with patch.object(login.time, "monotonic", self.clock.monotonic), \
                patch.object(login.time, "sleep", self.clock.sleep), \
                patch.object(login.uuid, "uuid4", return_value=uuid.UUID(ATTACH_ID)) as identifier, \
                patch.object(login, "Client", side_effect=AssertionError("Use the supplied fake client.")), \
                patch("socket.create_connection", side_effect=AssertionError("Live sockets are forbidden.")), \
                patch("socket.socket", side_effect=AssertionError("Live sockets are forbidden.")):
            try:
                return login.ensure_online(client, timeout=timeout)
            finally:
                self.uuid_calls = identifier.call_count

    def assert_one_attach(self, client):
        self.assertEqual(client.attach_calls, [("attach", "Vesper", ATTACH_ID)])
        self.assertEqual(self.uuid_calls, 1)
        self.assertTrue(all(call == ("Vesper", ATTACH_ID) for call in client.result_calls))

    def test_already_owned_online_never_submits_or_polls_a_login(self):
        client = FakeClient([owned()])
        self.assertIs(self.run_ensure(client), True)
        self.assertEqual(client.attach_calls, [])
        self.assertEqual(client.result_calls, [])
        self.assertEqual(self.uuid_calls, 0)

    def test_external_online_session_is_never_taken_over(self):
        client = FakeClient([{"self": {"name": "Vesper", "controller_owned": False}}])
        with self.assertRaises(BridgeError):
            self.run_ensure(client)
        self.assertEqual(client.attach_calls, [])
        self.assertEqual(client.result_calls, [])

    def test_initial_non_offline_observation_errors_do_not_attempt_login(self):
        for code in ("authentication_failed", "timeout", "connection_failed", "bridge_unavailable"):
            with self.subTest(code=code):
                client = FakeClient([BridgeError(code, "Observation unavailable.")])
                with self.assertRaises(BridgeError) as caught:
                    self.run_ensure(client)
                self.assertEqual(caught.exception.code, code)
                self.assertEqual(client.attach_calls, [])

    def test_malformed_or_wrong_character_observations_raise_bridge_errors(self):
        for state in (None, [], "not an observation", {}, {"self": None},
                      {"self": {"name": "Aurenne", "controller_owned": True}},
                      {"self": {"name": "Vesper", "controller_owned": 1}}):
            with self.subTest(state=state):
                client = FakeClient([state])
                with self.assertRaises(BridgeError):
                    self.run_ensure(client)
                self.assertEqual(client.attach_calls, [])

    def test_existing_loading_creating_or_temporarily_offline_ready_waits_without_attach(self):
        # Core Observe can say character_offline with actor.phase='ready' during
        # a world transition. That text is not a successful owned observation.
        for phase in ("loading", "creating", "ready"):
            with self.subTest(phase=phase):
                client = FakeClient([offline(phase), offline(phase), owned()])
                self.assertIs(self.run_ensure(client), False)
                self.assertEqual(client.attach_calls, [])
                self.assertEqual(client.result_calls, [])
                self.assertEqual(self.uuid_calls, 0)

    def test_accepted_attach_waits_for_completion_and_owned_observation(self):
        client = FakeClient([offline()], polls=[
            lambda request_id: receipt(request_id, status="accepted"), receipt,
        ], online_after_polls=2)
        self.assertIs(self.run_ensure(client), False)
        self.assert_one_attach(client)
        self.assertEqual(len(client.result_calls), 2)

    def test_previous_failed_login_can_start_one_new_attempt(self):
        client = FakeClient([offline("failed")], polls=[receipt], online_after_polls=1)
        self.assertIs(self.run_ensure(client), False)
        self.assert_one_attach(client)

    def test_completion_receipt_cannot_replace_final_owned_observation(self):
        client = FakeClient([offline()], poll_default=receipt)
        with self.assertRaises(BridgeError) as caught:
            self.run_ensure(client)
        self.assertEqual(caught.exception.code, "login_timeout")
        self.assert_one_attach(client)
        self.assertGreaterEqual(len(client.result_calls), 2)

    def test_each_ambiguous_attach_failure_polls_original_uuid_without_resubmission(self):
        for code in ("timeout", "connection_closed", "connection_failed", "invalid_response",
                     "response_mismatch", "response_too_large"):
            with self.subTest(code=code):
                client = FakeClient([offline()], attach=BridgeError(code, "Uncertain reply."),
                                    polls=[receipt], online_after_polls=1)
                self.assertIs(self.run_ensure(client), False)
                self.assert_one_attach(client)
                self.assertEqual(client.result_calls, [("Vesper", ATTACH_ID)])

    def test_busy_or_character_online_race_waits_instead_of_resubmitting(self):
        for code in ("busy", "character_online"):
            with self.subTest(code=code):
                client = FakeClient([offline()], attach=BridgeError(code, "Racing login."),
                                    online_after_attach=True)
                self.assertIs(self.run_ensure(client), False)
                self.assert_one_attach(client)
                self.assertEqual(client.result_calls, [])

    def test_character_online_race_still_rejects_an_external_session(self):
        client = FakeClient([offline()], attach=BridgeError("character_online", "Racing session."),
                            observation_default={"self": {"name": "Vesper", "controller_owned": False}})
        with self.assertRaises(BridgeError):
            self.run_ensure(client)
        self.assert_one_attach(client)
        self.assertEqual(client.result_calls, [])

    def test_permanent_attach_rejections_do_not_poll_or_retry(self):
        for code in ("character_not_owned", "account_in_use", "character_not_allowed", "account_missing"):
            with self.subTest(code=code):
                client = FakeClient([offline()], attach=BridgeError(code, "Login rejected."))
                with self.assertRaises(BridgeError) as caught:
                    self.run_ensure(client)
                self.assertEqual(caught.exception.code, code)
                self.assert_one_attach(client)
                self.assertEqual(client.result_calls, [])

    def test_asynchronous_failure_or_completed_without_attachment_is_not_success(self):
        replies = (
            lambda request_id: receipt(request_id, ok=False, status="failed"),
            lambda request_id: receipt(request_id, status="failed"),
            lambda request_id: receipt(request_id, attached=False),
        )
        for reply in replies:
            with self.subTest(reply=reply):
                client = FakeClient([offline()], polls=[reply])
                with self.assertRaises(BridgeError):
                    self.run_ensure(client)
                self.assert_one_attach(client)
                self.assertEqual(len(client.result_calls), 1)

    def test_pending_actor_failure_without_a_known_request_is_reported(self):
        client = FakeClient([offline("loading"), offline("failed")])
        with self.assertRaises(BridgeError):
            self.run_ensure(client)
        self.assertEqual(client.attach_calls, [])
        self.assertEqual(client.result_calls, [])

    def test_unknown_cache_result_can_be_resolved_by_owned_observation(self):
        client = FakeClient([offline()], online_after_polls=2)
        self.assertIs(self.run_ensure(client), False)
        self.assert_one_attach(client)
        self.assertEqual(len(client.result_calls), 2)

    def test_unknown_cache_timeout_preserves_original_uuid_and_never_retries_attach(self):
        client = FakeClient([offline()], attach=BridgeError("timeout", "Attach reply lost."))
        with self.assertRaises(BridgeError) as caught:
            self.run_ensure(client)
        self.assertEqual(caught.exception.code, "login_timeout")
        self.assertEqual(caught.exception.request_id, ATTACH_ID)
        self.assert_one_attach(client)
        self.assertGreaterEqual(len(client.result_calls), 2)

    def test_existing_pending_login_timeout_never_submits_a_second_operation(self):
        client = FakeClient([offline("loading")])
        with self.assertRaises(BridgeError) as caught:
            self.run_ensure(client)
        self.assertEqual(caught.exception.code, "login_timeout")
        self.assertEqual(client.attach_calls, [])
        self.assertEqual(client.result_calls, [])

    def test_wrong_cached_envelope_is_not_treated_as_a_permanent_attach_rejection(self):
        for field, value in (("v", 2), ("id", "another-request"), ("op", "detach"), ("character", "Aurenne")):
            with self.subTest(field=field):
                def wrong_receipt(request_id):
                    value_dict = receipt(request_id, ok=False, error_code="account_missing")
                    value_dict["response"][field] = value
                    return value_dict

                client = FakeClient([offline()], poll_default=wrong_receipt)
                with self.assertRaises(BridgeError) as caught:
                    self.run_ensure(client)
                self.assertEqual(caught.exception.code, "login_timeout")
                self.assert_one_attach(client)

    def test_malformed_attach_results_remain_bridge_errors_and_never_duplicate_login(self):
        for result in (None, [], {}, {"status": "unexpected"},
                       {"status": "completed", "attached": False}, {"status": "failed"}):
            with self.subTest(result=result):
                client = FakeClient([offline()], attach=lambda request_id: result)
                with self.assertRaises(BridgeError):
                    self.run_ensure(client)
                self.assert_one_attach(client)

    def test_malformed_cached_wrappers_results_and_errors_do_not_escape_as_python_errors(self):
        def bad_result(request_id):
            value = receipt(request_id)
            value["response"]["result"] = "malformed"
            return value

        def bad_error(request_id):
            value = receipt(request_id, ok=False)
            value["response"]["error"] = "malformed"
            return value

        for result in ([], {"response": None}, {"response": "bad"}, bad_result, bad_error):
            with self.subTest(result=result):
                client = FakeClient([offline()], polls=[result])
                with self.assertRaises(BridgeError):
                    self.run_ensure(client)
                self.assert_one_attach(client)


if __name__ == "__main__":
    unittest.main()
