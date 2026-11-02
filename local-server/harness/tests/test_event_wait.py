import unittest

from presence_acore.event_wait import wait_events, valid_cursor, _matches


EPOCH = "c"*32
def result(n, events=None, **fields):
    return {"schema": "native-event-journal/v1", "cursor": EPOCH+":"+str(n), "events": events or [],
            "gap": False, "reset": False, "has_more": False, **fields}


class FakeClient:
    def __init__(self, results): self.results = iter(results); self.calls = []
    def request(self, op, character, **args):
        self.calls.append((op, character, args)); return next(self.results)


class WaitTests(unittest.TestCase):
    def test_wait_wakes_on_matching_event_with_fresh_snapshot(self):
        client = FakeClient([result(1), result(2, [{"type": "combat_started", "cursor": EPOCH+":2"}])])
        now = [0.0]
        def sleep(t): now[0] += t
        calls = []
        value = wait_events(client, lambda: calls.append("fresh") or {"sequence": 9},
                            event_types=["combat_start"], monotonic=lambda: now[0], sleep=sleep)
        self.assertEqual(value["wake_reason"], "event")
        self.assertEqual(value["snapshot"], {"sequence": 9})
        self.assertEqual(calls, ["fresh"])
        self.assertEqual(client.calls[1][2]["since"], EPOCH+":1")

    def test_filter_consumes_irrelevant_events_without_repeating(self):
        client = FakeClient([result(2, [{"type": "chat"}]), result(3, [{"type": "death"}])])
        value = wait_events(client, lambda: {}, since=EPOCH+":1", event_types=["death"], sleep=lambda _: None)
        self.assertEqual(value["events"], [{"type": "death"}])
        self.assertEqual(client.calls[1][2]["since"], EPOCH+":2")

    def test_gap_wakes_even_if_filter_has_no_match(self):
        value = wait_events(FakeClient([result(90, gap=True, lost_events="20")]), lambda: {},
                            since=EPOCH+":1", event_types=["damage"])
        self.assertEqual(value["wake_reason"], "history_changed")
        self.assertEqual(value["journal"]["lost_events"], "20")

    def test_zero_timeout_is_fresh_nonblocking_baseline(self):
        value = wait_events(FakeClient([result(1)]), lambda: {"fresh": True}, timeout_sec=0)
        self.assertEqual(value["wake_reason"], "timeout")
        self.assertTrue(value["snapshot"]["fresh"])

    def test_uint64_epoch_and_bad_filters(self):
        self.assertTrue(valid_cursor(EPOCH+":"+str(2**64-1)))
        self.assertFalse(valid_cursor(EPOCH+":"+str(2**64)))
        self.assertFalse(valid_cursor(2))
        self.assertFalse(wait_events(FakeClient([]), lambda: {}, event_types=["whatever"])["available"])

    def test_directed_filters_use_exact_packet_facts_not_names(self):
        self.assertFalse(_matches({"type": "chat", "payload": {"direction": "incoming", "speaker": "Aurenne"}}, ["directed_chat"]))
        self.assertTrue(_matches({"type": "chat", "payload": {"direction": "incoming", "speaker": "Other", "directed_at_self": True}}, ["directed_chat"]))
        self.assertFalse(_matches({"type": "text_emote", "payload": {"direction": "outgoing", "directed_at_self": True}}, ["directed_emote"]))
        self.assertTrue(_matches({"type": "text_emote", "payload": {"direction": "incoming", "directed_at_self": True}}, ["directed_emote"]))

    def test_loot_change_includes_each_roll_phase_without_enabling_other_filters(self):
        for kind in ("loot_roll_started", "loot_roll_vote", "loot_roll_resolved"):
            with self.subTest(kind=kind):
                event = {"type": kind, "payload": {"roll_id": "a"*32}}
                self.assertTrue(_matches(event, ["loot_change"]))
                self.assertFalse(_matches(event, ["quest_change"]))
                value = wait_events(FakeClient([result(4, [event])]),
                                    lambda: {"sequence": 7, "loot_rolls": []},
                                    since=EPOCH+":3", event_types=["loot_change"])
                self.assertEqual(value["wake_reason"], "event")
                self.assertEqual(value["events"], [event])
                self.assertEqual(value["snapshot"], {"sequence": 7, "loot_rolls": []})


if __name__ == "__main__": unittest.main()
