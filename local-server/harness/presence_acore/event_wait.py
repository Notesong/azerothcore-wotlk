"""Bounded waits over the native character journal; no model calls."""
from __future__ import annotations

import re
import time
from typing import Any, Callable

from .client import Client, BridgeError

CURSOR = re.compile(r"[0-9a-f]{32}:(?:0|[1-9][0-9]{0,19})\Z")
FILTERS = {
    "chat": {"chat"}, "directed_chat": {"chat"}, "directed_emote": {"text_emote"},
    "combat": {"combat_started", "combat_ended"}, "combat_start": {"combat_started"},
    "combat_stop": {"combat_ended"}, "damage": {"damage"},
    "death": {"death", "resurrected", "resurrection_offer_changed"},
    "party_separation": {"party_separation", "party_rejoined"}, "arrival": {"arrival", "taxi_arrived"},
    "action_result": {"action_result"},
    "loot_change": {"inventory_changed", "loot_result", "loot_roll_started", "loot_roll_vote", "loot_roll_resolved"},
    "quest_change": {"quest_changed"}, "area_change": {"area_changed"},
    "travel_change": {"taxi_node_learned", "taxi_menu_opened", "taxi_started", "taxi_arrived", "taxi_interrupted"},
    "trade_change": {"trade_request", "trade_open", "trade_offer_changed", "trade_partner_accepted",
                     "trade_acceptance_reset", "trade_complete", "trade_cancelled", "trade_error", "trade_closed"},
}


def valid_cursor(value: Any) -> bool:
    return (isinstance(value, str) and CURSOR.fullmatch(value) is not None
            and int(value.split(":")[1]) <= 2**64-1)


def journal(client: Client, since: str | None = None) -> dict[str, Any]:
    args = {"max_events": 512}
    if since is not None:
        if not valid_cursor(since):
            raise ValueError("invalid_cursor")
        args["since"] = since
    result = client.request("events", "Vesper", **args)
    if (result.get("schema") != "native-event-journal/v1"
            or not valid_cursor(result.get("cursor")) or not isinstance(result.get("events"), list)):
        raise ValueError("invalid_journal_response")
    return result


def _matches(event: dict[str, Any], filters: list[str] | None) -> bool:
    if not filters:
        return True
    kind = event.get("type")
    for name in filters:
        if kind not in FILTERS[name]:
            continue
        # Native packets expose facts; missing direction must not be invented.
        if name == "directed_chat":
            payload = event.get("payload", event)
            if payload.get("direction") == "incoming" and payload.get("directed_at_self") is True:
                return True
            continue
        if name == "directed_emote":
            payload = event.get("payload", event)
            if payload.get("direction") == "incoming" and payload.get("directed_at_self") is True:
                return True
            continue
        return True
    return False


def wait_events(client: Client, observe: Callable[[], dict[str, Any]], *, since: str | None = None,
                timeout_sec: int = 20, event_types: list[str] | None = None,
                monotonic: Callable[[], float] = time.monotonic,
                sleep: Callable[[float], None] = time.sleep) -> dict[str, Any]:
    base = {"schema": "wow-event-wait/v1", "character": "Vesper", "available": False}
    if (since is not None and not valid_cursor(since) or type(timeout_sec) is not int
            or not 0 <= timeout_sec <= 30 or event_types is not None and
            (not isinstance(event_types, list) or any(not isinstance(x, str) or x not in FILTERS for x in event_types))):
        return {**base, "error": {"code": "invalid_arguments"}}
    start = monotonic()
    cursor = since
    events: list[dict[str, Any]] = []
    try:
        while True:
            result = journal(client, cursor)
            cursor = result["cursor"]
            events.extend(event for event in result["events"] if isinstance(event, dict) and _matches(event, event_types))
            history_changed = result.get("reset") is True or result.get("gap") is True
            if events or history_changed or monotonic()-start >= timeout_sec:
                # Event facts can already be old; always collect authoritative current state.
                snapshot = observe()
                return {**base, "available": True, "cursor": cursor,
                        "wake_reason": "history_changed" if history_changed else "event" if events else "timeout",
                        "events": events, "journal": {k: v for k, v in result.items() if k != "events"},
                        "snapshot": snapshot, "elapsed_sec": round(monotonic()-start, 3)}
            if not result.get("has_more"):
                sleep(min(0.25, max(0, timeout_sec-(monotonic()-start))))
    except BridgeError as exc:
        code = exc.code if re.fullmatch(r"[a-z0-9_]{1,64}", exc.code) else "bridge_error"
    except (OSError, ValueError, TypeError, KeyError):
        code = "event_journal_unavailable"
    return {**base, "cursor": cursor, "error": {"code": code}, "snapshot": observe()}
