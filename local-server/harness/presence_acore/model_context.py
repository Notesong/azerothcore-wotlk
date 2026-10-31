"""Read-only, fixed-file model-input diagnostics; never load the Full controller."""
from __future__ import annotations

import builtins
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from types import ModuleType
from typing import Any, Callable


MAX_CAPTURE_BYTES = 262_144
MAX_MOON_RECORD_BYTES = 327_680
_MOON_ARCHIVE = "runtime-game-player-moon-violations"
_MOON_STATUS = "runtime-game-player-moon-audit-status.json"
_AUDIT_STATUS_FIELDS = {"schema", "character", "latest_incident_id", "updated_at", "last_error", "retained_records",
                        "total_recorded", "total_rotated", "max_records", "max_record_bytes"}
_VIOLATION_FIELDS = {"schema", "inspection_only", "character", "lane", "incident_id", "recorded_at", "classification",
                     "planned_action", "submitted_action", "guard_result", "protection_at_request",
                     "pre_action_protection", "provenance", "retention"}
_ACTION_FIELDS = {"type", "target_guid", "spell_id", "x", "y", "z", "map_id", "distance", "follow_distance",
                  "quest_id", "reward_index", "inviter_guid", "reason", "item_guid", "item_id", "vendor_slot",
                  "count", "equipment_slot", "page", "buyback_slot", "menu_id", "option_id"}
_PROTECTION_FIELDS = {"active", "state", "protected_target_guid", "protected_target_name", "protected_by_guid",
                      "protected_by", "policy", "mode", "reason", "target_present", "binding", "identity_status",
                      "persistence_ok", "party_beneficial_blocked", "reflection_disabled", "tame_intent",
                      "instruction", "instruction_version"}
_INTERVENTION_FIELDS = {"id", "type", "attribution", "request_id", "observed_sequence", "action_type", "owner_guid",
                        "source_guid", "target_guid", "protected_target_guid", "protected_by_guid", "hook", "reason",
                        "spell_id", "cast_count", "timestamp"}
_CAPTURE_FILES = {"body": "runtime-game-player-context-body.json",
                  "social": "runtime-game-player-context-social.json"}
_CAPTURE_FIELDS = {
    "schema", "inspection_only", "source", "runtime", "character", "lane", "capture_id", "session",
    "provider", "model", "prepared_at", "observation_sequence", "observation_timestamp",
    "source_prompt_sha256", "source_prompt_bytes", "context", "images", "omitted_sections", "exactness", "outcome",
}
_NESTED_FIELDS = {
    "session": {"run_id", "started_at", "pid"},
    "images": {"count", "bytes_omitted", "source", "perspective", "trigger_reason", "available", "included"},
    "exactness": {"source", "context_available", "copied_values_exact", "truncated", "omitted_dynamic_fields",
                  "max_capture_bytes", "unavailable_reason"},
    "outcome": {"state", "provider_read_confirmed", "at", "http_status", "error_type"},
}
_CONTEXT_FIELDS = {"planner_mode", "session_state", "recent_chat_transcript", "allowed_actions", "extra_context"}
_EXTRA_FIELDS = {"game_backend", "observation_source", "observation_fresh", "native_observation",
                 "image_context", "native_image_context", "planning_reason", "trigger_reason", "gameplay_decision",
                 "accepted_gameplay_decision", "gameplay_execution", "observed_lead_chat", "scene_ledger"}
_SESSION_FIELDS = {"session_goal", "controlled_character", "lead_character", "current_activity", "role", "notes",
                   "recent_events", "context_kind", "coverage"}
_FORBIDDEN_KEY = re.compile(
    r"password|secret|credential|api.?key|authorization|access.?token|"
    r"^(?:presence_continuity|persona(?:_.*)?|system(?:_.*)?|user_instruction|"
    r"headers|request|messages|input|image_url|data_url|detail_data_urls|reasoning|reasoning_content|"
    r"thinking|analysis|chain_of_thought)$", re.I)
_OMITTED = ["stable_system_instructions", "presence_continuity", "user_instruction", "raw_http_request",
            "authentication", "image_bytes", "model_response", "hidden_reasoning"]


def _read_json(path: Path, max_bytes: int = MAX_CAPTURE_BYTES) -> tuple[dict[str, Any], str]:
    def invalid(_: str) -> None:
        raise ValueError("nonfinite_json")

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate_key")
            result[key] = value
        return result

    try:
        with path.open("rb") as handle:
            raw = handle.read(max_bytes + 1)
        if len(raw) > max_bytes:
            return {}, "capture_too_large"
        value = json.loads(raw.decode("utf-8-sig"), parse_constant=invalid, object_pairs_hook=pairs)
        return (value, "available") if isinstance(value, dict) else ({}, "invalid_capture")
    except FileNotFoundError:
        return {}, "no_recorded_request"
    except (OSError, ValueError, RecursionError):
        return {}, "invalid_capture"


def _runtime(data_dir: Path, capture: dict[str, Any], character: str,
             pid_alive: Callable[[Any], bool | None]) -> dict[str, Any]:
    status, _ = _read_json(data_dir / "runtime-game-player-status.json")
    state, _ = _read_json(data_dir / "runtime-game-player-state.json")
    control, _ = _read_json(data_dir / "runtime-game-player-control.json")
    session = capture.get("session") if isinstance(capture.get("session"), dict) else {}
    pid = state.get("pid")
    capture_pid = session.get("pid")
    attributed = (status.get("controlled_character") == character and status.get("game_backend") == "azerothcore")
    started_at = status.get("started_at") if attributed else None
    return {"running": status.get("running") is True and attributed,
            "paused": control.get("paused") is True or status.get("paused") is True,
            "process_alive": pid_alive(pid),
            "pid_matches_capture": isinstance(pid, int) and not isinstance(pid, bool) and pid > 0
            and pid == capture_pid,
            "started_at_matches_capture": isinstance(started_at, str) and bool(started_at)
            and started_at == session.get("started_at")}


def _timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("invalid_timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp_requires_timezone")
    return parsed


def _clean_capture(raw: dict[str, Any], lane: str, character: str) -> tuple[dict[str, Any], bool]:
    if (raw.get("schema") != "native-model-context/v1" or raw.get("inspection_only") is not True
            or raw.get("source") != "last_request_attempt" or raw.get("runtime") != "full"
            or raw.get("character") != character or raw.get("lane") != lane):
        raise ValueError("invalid_capture")
    _timestamp(raw.get("prepared_at"))
    if not isinstance(raw.get("session"), dict) or not isinstance(raw.get("exactness"), dict):
        raise ValueError("invalid_capture")
    session, exactness = raw["session"], raw["exactness"]
    def integer(value: Any, minimum: int = 0) -> bool:
        return isinstance(value, int) and not isinstance(value, bool) and value >= minimum

    if (not isinstance(raw.get("capture_id"), str) or not re.fullmatch(r"[a-f0-9]{32}", raw["capture_id"])
            or not isinstance(session.get("run_id"), str) or not re.fullmatch(r"[a-f0-9]{32}", session["run_id"])
            or not integer(session.get("pid"), 1)
            or any(not isinstance(raw.get(key), str) or len(raw[key]) > 200 for key in ("provider", "model"))
            or not isinstance(raw.get("source_prompt_sha256"), str)
            or not re.fullmatch(r"[a-f0-9]{64}", raw["source_prompt_sha256"])
            or not integer(raw.get("source_prompt_bytes"))
            or raw.get("observation_sequence") is not None and not integer(raw["observation_sequence"])
            or not isinstance(raw.get("observation_timestamp"), str)
            or exactness.get("source") != "already_serialized_native_prompt"
            or type(exactness.get("context_available")) is not bool
            or type(exactness.get("copied_values_exact")) is not bool
            or exactness.get("truncated") is not False
            or not integer(exactness.get("omitted_dynamic_fields"))
            or exactness.get("max_capture_bytes") != MAX_CAPTURE_BYTES
            or exactness.get("unavailable_reason") not in (None, "oversize", "invalid_or_unrecognized_context")):
        raise ValueError("invalid_capture")
    _timestamp(session.get("started_at"))
    images, outcome = raw.get("images"), raw.get("outcome")
    if (not isinstance(images, dict) or not integer(images.get("count")) or images.get("bytes_omitted") is not True
            or not isinstance(outcome, dict) or outcome.get("state") not in ("prepared", "response_received", "request_error")
            or outcome.get("provider_read_confirmed") is not False):
        raise ValueError("invalid_capture")
    for key in ("source", "perspective", "trigger_reason", "available", "included"):
        value = images.get(key)
        if key in images and not (isinstance(value, bool) or isinstance(value, str) and len(value) <= 600):
            raise ValueError("invalid_capture")
    if "at" in outcome:
        _timestamp(outcome["at"])
    if "http_status" in outcome and not integer(outcome["http_status"]):
        raise ValueError("invalid_capture")
    if "error_type" in outcome and (not isinstance(outcome["error_type"], str)
                                    or not re.fullmatch(r"[A-Za-z0-9_]{0,80}", outcome["error_type"])):
        raise ValueError("invalid_capture")
    expected_mode = "gameplay" if lane == "body" else "social"
    context = raw.get("context")
    if context is not None and (not isinstance(context, dict) or context.get("planner_mode") != expected_mode):
        raise ValueError("invalid_capture")
    changed = bool(set(raw) - _CAPTURE_FIELDS)

    def project(item: Any, allowed: set[str] | None = None, depth: int = 0) -> Any:
        nonlocal changed
        if depth > 24:
            raise ValueError("invalid_capture")
        if isinstance(item, dict):
            result = {}
            for key, value in item.items():
                if _FORBIDDEN_KEY.search(key) or (allowed is not None and key not in allowed):
                    changed = True
                    continue
                result[key] = project(value, depth=depth + 1)
            return result
        if isinstance(item, list):
            return [project(value, depth=depth + 1) for value in item]
        if isinstance(item, str) and item.startswith("data:"):
            changed = True
            return "[image data omitted]"
        return item

    clean = {key: value for key, value in raw.items() if key in _CAPTURE_FIELDS}
    for key, fields in _NESTED_FIELDS.items():
        if key in clean:
            if not isinstance(clean[key], dict):
                raise ValueError("invalid_capture")
            clean[key] = project(clean[key], fields)
    if context is not None:
        clean_context = project(context, _CONTEXT_FIELDS)
        for key, allowed in (("extra_context", _EXTRA_FIELDS), ("session_state", _SESSION_FIELDS)):
            if key in context:
                if not isinstance(context[key], dict):
                    raise ValueError("invalid_capture")
                clean_context[key] = project(context[key], allowed)
        clean["context"] = clean_context
    # Prevent arbitrary data from hiding inside metadata fields, while leaving
    # legitimate strings/arrays/context values intact rather than truncating.
    clean = project(clean)
    if clean.get("omitted_sections") != _OMITTED:
        clean["omitted_sections"] = list(_OMITTED)
        changed = True
    if changed:
        clean["exactness"]["copied_values_exact"] = False
    return clean, changed


def _projection(presence_root: Path) -> Callable[..., dict[str, Any]]:
    # This fixed module contains pure projection helpers. Compile its source
    # directly so this inspection does not write import bytecode or import Full.
    path = presence_root / "backend" / "tools" / "game_player_native_context.py"
    with path.open("rb") as handle:
        source = handle.read(MAX_CAPTURE_BYTES + 1)
    if len(source) > MAX_CAPTURE_BYTES:
        raise ValueError("projection_unavailable")
    normal_import = builtins.__import__
    projection_builtins = vars(builtins).copy()
    helper_modules: dict[str, ModuleType] = {}
    helper_paths = {
        "tools.game_player_native_gear": "game_player_native_gear.py",
        "tools.game_player_native_attention": "game_player_native_attention.py",
        "tools.game_player_native_focus": "game_player_native_focus.py",
    }

    def projection_import(name: str, globals: Any = None, locals: Any = None,
                          fromlist: Any = (), level: int = 0) -> Any:
        if name not in helper_paths or level != 0:
            return normal_import(name, globals, locals, fromlist, level)
        if name not in helper_modules:
            # Resolve only these fixed pure siblings independently of the MCP process's
            # import path. Never import a tools package, Full, or a provider.
            helper_path = path.with_name(helper_paths[name])
            with helper_path.open("rb") as handle:
                helper_source = handle.read(MAX_CAPTURE_BYTES + 1)
            if len(helper_source) > MAX_CAPTURE_BYTES:
                raise ValueError("projection_unavailable")
            private = ModuleType("presence_readonly_" + helper_path.stem)
            private.__file__ = str(helper_path)
            private.__dict__["__builtins__"] = projection_builtins
            exec(compile(helper_source, str(helper_path), "exec"), private.__dict__)
            helper_modules[name] = private
        return helper_modules[name]

    projection_builtins["__import__"] = projection_import
    namespace: dict[str, Any] = {"__name__": "presence_readonly_native_projection", "__file__": str(path),
                                 "__builtins__": projection_builtins}
    exec(compile(source, str(path), "exec"), namespace)
    function = namespace.get("compact_native_observation")
    if not callable(function):
        raise ValueError("projection_unavailable")
    return function


def _clean_audit_value(value: Any, allowed: set[str] | None = None, depth: int = 0) -> tuple[Any, bool]:
    if depth > 24:
        raise ValueError("invalid_violation")
    changed = False
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if _FORBIDDEN_KEY.search(key) or allowed is not None and key not in allowed:
                changed = True
                continue
            result[key], nested_changed = _clean_audit_value(item, depth=depth + 1)
            changed |= nested_changed
        return result, changed
    if isinstance(value, list):
        result = []
        for item in value:
            clean, nested_changed = _clean_audit_value(item, depth=depth + 1)
            result.append(clean)
            changed |= nested_changed
        return result, changed
    if isinstance(value, str) and value.startswith("data:"):
        return "[image data omitted]", True
    return value, False


def _clean_violation(raw: dict[str, Any], character: str, incident_id: str) -> tuple[dict[str, Any], dict[str, Any], bool]:
    if (raw.get("schema") != "moon-violation/v1" or raw.get("inspection_only") is not True
            or raw.get("character") != character or raw.get("lane") != "body" or raw.get("incident_id") != incident_id
            or raw.get("classification") not in {"planner_protected_target_proposal", "planner_action_with_protected_effect_blocked",
                                                  "guard_intervention_requires_review"}):
        raise ValueError("invalid_violation")
    _timestamp(raw.get("recorded_at"))
    capture, changed = _clean_capture(raw.get("capture"), "body", character)
    clean, reduced = _clean_audit_value(raw, _VIOLATION_FIELDS | {"capture"})
    changed |= reduced
    clean.pop("capture", None)
    sections = {
        "planned_action": _ACTION_FIELDS, "submitted_action": _ACTION_FIELDS,
        "guard_result": {"error_code", "status", "outcome", "request_id", "executed", "submitted", "guard_interventions",
                         "guard_interventions_truncated", "guard_interventions_dropped"},
        "protection_at_request": _PROTECTION_FIELDS, "pre_action_protection": _PROTECTION_FIELDS,
        "provenance": {"capture_id", "request_context_available", "planner_had_moon_instruction",
                       "protection_active_in_request", "explicit_protected_target_proposal", "action_changed_before_submission", "action_projection_changed",
                       "protection_projection_changed", "guard_context_source"},
        "retention": {"max_records", "max_record_bytes"},
    }
    for key, fields in sections.items():
        if not isinstance(raw.get(key), dict):
            raise ValueError("invalid_violation")
        clean[key], reduced = _clean_audit_value(raw[key], fields)
        changed |= reduced
    provenance, guard = clean["provenance"], clean["guard_result"]
    context = capture.get("context") if isinstance(capture.get("context"), dict) else {}
    extra = context.get("extra_context") if isinstance(context.get("extra_context"), dict) else {}
    observation = extra.get("native_observation") if isinstance(extra.get("native_observation"), dict) else {}
    protection = observation.get("protection") if isinstance(observation.get("protection"), dict) else {}
    active = protection.get("active") is True
    had_instruction = active and bool(protection.get("instruction"))
    target = protection.get("protected_target_guid")
    proposed = clean["planned_action"]
    explicit = (had_instruction and isinstance(target, str) and re.fullmatch(r"[0-9]{1,20}", target) is not None
                and int(target) > 0 and proposed.get("type") in {"attack", "cast"}
                and proposed.get("target_guid") == target)
    if (provenance.get("capture_id") != capture.get("capture_id")
            or provenance.get("guard_context_source") != "pre_action_observation_not_guard_callback"
            or provenance.get("request_context_available") is not capture["exactness"]["context_available"]
            or provenance.get("planner_had_moon_instruction") is not had_instruction
            or provenance.get("protection_active_in_request") is not active
            or provenance.get("explicit_protected_target_proposal") is not explicit
            or clean["classification"] == "planner_protected_target_proposal" and not explicit
            or guard.get("error_code") not in {"", "protected_target", "protection_escape"}
            or guard.get("outcome") not in {"blocked", "accepted_with_guard_intervention", "rejected_with_guard_intervention",
                                            "proposal_submitted", "proposal_not_submitted"}
            or not isinstance(guard.get("guard_interventions"), list)
            or len(guard["guard_interventions"]) > 16
            or not isinstance(guard.get("request_id"), str)
            or not re.fullmatch(r"[a-fA-F0-9]{0,32}", guard["request_id"])):
        raise ValueError("invalid_violation")
    cleaned_interventions = []
    for event in guard["guard_interventions"]:
        if (not isinstance(event, dict) or event.get("type") != "moon_guard_intervention"
                or event.get("attribution") != "synchronous_action" or not guard["request_id"]
                or event.get("request_id") != guard["request_id"]
                or event.get("action_type") != clean["submitted_action"].get("type")):
            raise ValueError("invalid_violation")
        cleaned_event, reduced = _clean_audit_value(event, _INTERVENTION_FIELDS)
        cleaned_interventions.append(cleaned_event)
        changed |= reduced
    guard["guard_interventions"] = cleaned_interventions
    if clean["classification"] == "planner_action_with_protected_effect_blocked" and not (
            had_instruction and isinstance(target, str) and re.fullmatch(r"[0-9]{1,20}", target)
            and int(target) > 0 and any(event.get("reason") in {"protected_target_effect", "protected_damage"}
                and event.get("target_guid") == target and event.get("protected_target_guid") == target
                for event in cleaned_interventions)):
        raise ValueError("invalid_violation")
    if not guard["error_code"] and not cleaned_interventions and not explicit:
        raise ValueError("invalid_violation")
    return clean, capture, changed


def inspect_model_context(client: Any, *, character: str, presence_root: Path, data_dir: Path,
                          lane: str, source: str, pid_alive: Callable[[Any], bool | None]) -> dict[str, Any]:
    if (not isinstance(lane, str) or lane not in _CAPTURE_FILES or not isinstance(source, str)
            or source not in {"last_request", "live_preview", "last_violation"}):
        raise ValueError("Invalid model context lane or source.")
    result: dict[str, Any] = {
        "schema": "wow-model-context/v1", "inspection_only": True, "character": character, "available": False,
        "lane": lane, "source": source, "collected_at": datetime.now(timezone.utc).isoformat(),
        "view_kind": {"last_request": "last_request_attempt", "live_preview": "live_projection_preview",
                      "last_violation": "guarded_violation"}[source],
        "runtime": _runtime(data_dir, {}, character, pid_alive),
        "limitations": ["Recorded request attempts do not prove a model read the input or a gameplay action succeeded.",
                        "Stable persona, hidden reasoning, authentication and image bytes are omitted."],
    }

    def unavailable(code: str) -> dict[str, Any]:
        result["error"] = {"code": code, "message": "The requested model-context inspection is unavailable."}
        return result

    if source == "last_violation":
        if lane != "body":
            return unavailable("violations_body_only")
        status, availability = _read_json(data_dir / _MOON_STATUS, 16_384)
        if availability != "available":
            return unavailable("no_recorded_violation" if availability == "no_recorded_request" else "audit_status_unavailable")
        if (status.get("schema") != "moon-audit-status/v1" or status.get("character") != character
                or status.get("last_error", "") not in {"", "capture_not_found", "capture_not_successful",
                    "record_too_large", "unsafe_archive_directory", "unsafe_archive_record",
                    "invalid_existing_record", "audit_write_failed"}
                or any(type(status[key]) is not int or status[key] < 0
                       for key in ("retained_records", "total_recorded", "total_rotated") if key in status)
                or status.get("max_records") != 100 or status.get("max_record_bytes") != MAX_MOON_RECORD_BYTES):
            return unavailable("invalid_audit_status")
        result["audit_status"], status_changed = _clean_audit_value(status, _AUDIT_STATUS_FIELDS)
        incident_id = status.get("latest_incident_id")
        if not isinstance(incident_id, str) or not re.fullmatch(r"[a-f0-9]{32}", incident_id):
            return unavailable("audit_write_failed" if status.get("last_error") else "no_recorded_violation")
        archive = data_dir / _MOON_ARCHIVE
        if archive.is_symlink() or archive.resolve() != data_dir.resolve() / _MOON_ARCHIVE:
            return unavailable("unsafe_archive_directory")
        path = archive / f"{incident_id}.json"
        if path.is_symlink():
            return unavailable("unsafe_archive_record")
        raw, availability = _read_json(path, MAX_MOON_RECORD_BYTES)
        if availability != "available":
            return unavailable("violation_record_unavailable")
        try:
            violation, capture, changed = _clean_violation(raw, character, incident_id)
            result.update(violation=violation, capture=capture,
                          runtime=_runtime(data_dir, capture, character, pid_alive),
                          age_sec=max(0.0, round((datetime.now(timezone.utc) - _timestamp(violation["recorded_at"])).total_seconds(), 1)))
            if changed or status_changed:
                result.update(transport_truncated=True, exact_dynamic_context=False)
            if capture["exactness"].get("context_available") is not True or not isinstance(capture.get("context"), dict):
                return unavailable("capture_context_unavailable")
            result["available"] = True
            return result
        except (ValueError, TypeError, KeyError, AttributeError, RecursionError):
            result.pop("violation", None)
            result.pop("capture", None)
            return unavailable("invalid_violation")

    if source == "last_request":
        raw, availability = _read_json(data_dir / _CAPTURE_FILES[lane])
        if availability != "available":
            return unavailable(availability)
        try:
            capture, changed = _clean_capture(raw, lane, character)
            result["capture"] = capture
            result["runtime"] = _runtime(data_dir, capture, character, pid_alive)
            result["age_sec"] = max(0.0, round((datetime.now(timezone.utc) - _timestamp(capture["prepared_at"])).total_seconds(), 1))
            if changed:
                result.update(transport_truncated=True, exact_dynamic_context=False)
            if capture["exactness"].get("context_available") is not True or not isinstance(capture.get("context"), dict):
                return unavailable("capture_context_unavailable")
            result["available"] = True
            return result
        except (ValueError, TypeError, KeyError, RecursionError):
            result.pop("capture", None)
            return unavailable("invalid_capture")
    try:
        compact = _projection(presence_root)
        raw = client.observe(character, after_event_id=0)
        if not isinstance(raw, dict):
            return unavailable("observation_failed")
        projection_mode = "gameplay" if lane == "body" else "social"
        if lane == "body":
            saved, _ = _read_json(presence_root / "local" / "game_player.config.json")
            identity = saved.get("session_state") if isinstance(saved.get("session_state"), dict) else {}
            if (saved.get("game_backend") == "azerothcore" and identity.get("controlled_character") == character
                    and saved.get("provider") in {"local", "openai_compatible"}
                    and isinstance(saved.get("native_action_base_url"), str) and saved["native_action_base_url"].strip()):
                projection_mode = "local_gameplay"
        result["preview"] = {"basis": "fresh_bridge_snapshot", "is_actual_request": False,
                             "projection_mode": projection_mode,
                             "native_observation": compact(raw, projection_mode),
                             "unavailable_sections": ["controller_enrichment", "session_notes", "recent_chat_transcript",
                                                      "scene_ledger", "persona", "images"]}
        result["available"] = True
        return result
    except Exception:
        return unavailable("preview_unavailable")
