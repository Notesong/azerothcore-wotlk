from __future__ import annotations

import base64
import ipaddress
import json
import os
from pathlib import Path
import socket
import time
from typing import Any
import uuid


def _guard_interventions(value: Any, request_id: str) -> list[dict[str, Any]]:
    """Keep bounded server guard facts tied to this exact action request."""
    if not isinstance(value, list):
        return []
    strings = {
        "type", "attribution", "request_id", "action_type", "owner_guid", "source_guid", "target_guid",
        "protected_target_guid", "protected_by_guid", "hook", "reason", "timestamp",
    }
    integers = {"id", "guard_event_id", "observed_sequence", "spell_id", "cast_count"}
    result = []
    for item in value[:16]:
        if (not isinstance(item, dict) or item.get("type") != "moon_guard_intervention"
                or item.get("attribution") != "synchronous_action" or item.get("request_id") != request_id):
            continue
        record = {key: entry for key, entry in item.items()
                  if key in strings and isinstance(entry, str) and len(entry) <= 256
                  or key in integers and isinstance(entry, int) and not isinstance(entry, bool) and entry >= 0}
        if record.get("request_id") == request_id:
            result.append(record)
    return result


class BridgeError(RuntimeError):
    """A bounded transport or game error; never includes administration credentials."""

    def __init__(self, code: str, message: str, *, request_id: str = "", guard_interventions: Any = None,
                 guard_interventions_truncated: Any = False, guard_interventions_dropped: Any = 0) -> None:
        self.code = str(code)
        self.request_id = str(request_id)
        self.guard_interventions = _guard_interventions(guard_interventions, self.request_id)
        self.guard_interventions_truncated = guard_interventions_truncated is True
        self.guard_interventions_dropped = (guard_interventions_dropped
            if isinstance(guard_interventions_dropped, int) and not isinstance(guard_interventions_dropped, bool)
            and 0 <= guard_interventions_dropped <= 2**53 - 1 else 0)
        super().__init__(str(message))


class _Reader:
    def __init__(self, connection: socket.socket, deadline: float, limit: int = 4_194_304) -> None:
        self.connection = connection
        self.deadline = deadline
        self.limit = limit
        self.buffer = b""

    def until(self, markers: tuple[bytes, ...]) -> bytes:
        while True:
            matches = [(self.buffer.find(marker), marker) for marker in markers]
            found = [(offset, marker) for offset, marker in matches if offset >= 0]
            if found:
                offset, marker = min(found, key=lambda item: item[0])
                end = offset + len(marker)
                result, self.buffer = self.buffer[:end], self.buffer[end:]
                return result
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise BridgeError("timeout", "The local game bridge did not respond before its deadline.")
            self.connection.settimeout(remaining)
            data = self.connection.recv(65536)
            if not data:
                raise BridgeError("connection_closed", "The world server closed its administration connection.")
            self.buffer += data
            if len(self.buffer) > self.limit:
                raise BridgeError("response_too_large", "The local game bridge response exceeded its size limit.")


class Client:
    """Versioned JSON commands over AzerothCore's authenticated localhost RA channel.

    Calls return the bridge's ``result`` object. Transport/envelope errors raise
    BridgeError. Accepted asynchronous actions remain accepted until the game
    confirms their outcome; this client never equates submission with completion.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        config = dict(config or {})
        self.host = str(config.get("host") or "127.0.0.1")
        try:
            local = self.host.lower() == "localhost" or ipaddress.ip_address(self.host).is_loopback
        except ValueError:
            local = False
        if not local:
            raise BridgeError("nonlocal_host", "The Presence game bridge must use a loopback address.")
        self.port = int(config.get("port", 3443))
        self.timeout = float(config.get("timeout", 15))
        if not 1 <= self.port <= 65535 or not 0 < self.timeout <= 120:
            raise BridgeError("invalid_config", "The local game bridge port or timeout is invalid.")
        root = Path(os.environ.get("PRESENCE_ACORE_ROOT", "C:/Games/AzerothCore"))
        self.credentials_file = Path(config.get("credentials_file") or root / "server-admin.json")
        self._credentials = config.get("credentials")

    def _login(self) -> tuple[str, str]:
        try:
            credentials = self._credentials or json.loads(self.credentials_file.read_text(encoding="utf-8-sig"))
            username = str(credentials.get("Username") or credentials.get("username") or "")
            password = str(credentials.get("Password") or credentials.get("password") or "")
        except (OSError, ValueError, AttributeError) as exc:
            raise BridgeError("credentials_unavailable", "Local world administration credentials are unavailable.") from exc
        if not username or not password or any(char in username + password for char in "\r\n\x00"):
            raise BridgeError("invalid_credentials", "Local world administration credentials are invalid.")
        return username, password

    def request(
        self, op: str, character: str = "", *, request_id: str | None = None,
        request_fields: dict[str, Any] | None = None, **arguments: Any
    ) -> dict[str, Any]:
        if op not in {"observe", "action", "capabilities", "attach", "detach", "create", "action_result"}:
            raise BridgeError("invalid_operation", "Unknown game bridge operation.")
        request_id = request_id or str(uuid.uuid4())
        payload = {**(request_fields or {}), **arguments, "v": 1, "id": request_id, "op": op, "character": str(character)}
        try:
            encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise BridgeError("invalid_request", "The game request contains invalid JSON values.", request_id=request_id) from exc
        if len(encoded) > 24576:
            raise BridgeError("request_too_large", "The game request exceeded its size limit.", request_id=request_id)
        command = b"presence request " + base64.b64encode(encoded) + b"\r\n"
        username, password = self._login()
        deadline = time.monotonic() + self.timeout
        try:
            with socket.create_connection((self.host, self.port), timeout=self.timeout) as connection:
                reader = _Reader(connection, deadline)
                reader.until((b"Username: ",))
                connection.sendall(username.encode("utf-8") + b"\r\n")
                reader.until((b"Password: ",))
                connection.sendall(password.encode("utf-8") + b"\r\n")
                greeting = reader.until((b"AC>", b"Authentication failed"))
                if b"Authentication failed" in greeting:
                    raise BridgeError("authentication_failed", "The local world administration login failed.")
                connection.sendall(command)
                prefix = reader.until((b"PRESENCE_JSON:", b"AC>"))
                if not prefix.endswith(b"PRESENCE_JSON:"):
                    raise BridgeError(
                        "bridge_unavailable", "The Presence module did not return a structured response. Check that it is installed.",
                        request_id=request_id,
                    )
                response_line = reader.until((b"\n",)).decode("utf-8", errors="strict").strip()
                reader.until((b"AC>",))
        except BridgeError:
            raise
        except (socket.timeout, TimeoutError) as exc:
            raise BridgeError("timeout", "The local world administration request timed out.", request_id=request_id) from exc
        except OSError as exc:
            raise BridgeError("connection_failed", "Could not reach the local world administration service.", request_id=request_id) from exc
        except UnicodeDecodeError as exc:
            raise BridgeError("invalid_response", "The Presence module returned invalid UTF-8.", request_id=request_id) from exc
        try:
            response = json.loads(response_line)
        except ValueError as exc:
            raise BridgeError("invalid_response", "The Presence module returned invalid JSON.", request_id=request_id) from exc
        if not isinstance(response, dict) or response.get("v") != 1 or response.get("id") != request_id:
            raise BridgeError("response_mismatch", "The Presence response version or request ID did not match.", request_id=request_id)
        if response.get("op") != op:
            raise BridgeError("response_mismatch", "The Presence response operation did not match.", request_id=request_id)
        if response.get("ok") is not True:
            error = response.get("error") or {}
            if not isinstance(error, dict):
                raise BridgeError("invalid_response", "The Presence module returned an invalid error.", request_id=request_id)
            raise BridgeError(str(error.get("code") or "game_error"), str(error.get("message") or "The game rejected the request."),
                              request_id=request_id, guard_interventions=error.get("guard_interventions"),
                              guard_interventions_truncated=error.get("guard_interventions_truncated"),
                              guard_interventions_dropped=error.get("guard_interventions_dropped"))
        result = response.get("result")
        if not isinstance(result, dict):
            raise BridgeError("invalid_response", "The Presence module returned an invalid result.", request_id=request_id)
        if "guard_interventions" in result:
            result["guard_interventions"] = _guard_interventions(result["guard_interventions"], request_id)
        return result

    def observe(self, character: str, after_event_id: int = 0) -> dict[str, Any]:
        return self.request("observe", character, since=max(0, int(after_event_id)))

    def execute(
        self, character: str, action: dict[str, Any], request_id: str | None = None,
        observed_sequence: int | None = None,
    ) -> dict[str, Any]:
        arguments: dict[str, Any] = {"action": dict(action)}
        if observed_sequence is not None:
            arguments["observed_sequence"] = int(observed_sequence)
        return self.request("action", character, request_id=request_id, **arguments)

    def capabilities(self, character: str = "") -> dict[str, Any]:
        return self.request("capabilities", character)

    def attach(self, character: str) -> dict[str, Any]:
        return self.request("attach", character)

    def detach(self, character: str) -> dict[str, Any]:
        return self.request("detach", character)

    def action_result(self, character: str, action_id: str) -> dict[str, Any]:
        return self.request("action_result", character, request_fields={"request_id": action_id})
