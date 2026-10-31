"""Log the existing Vesper character in without starting Presence or any models."""
from __future__ import annotations

from pathlib import Path
import sys
import time
import uuid

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness"))
from presence_acore import BridgeError, Client


# These failures can occur after an attach was received. Resolve its original
# UUID instead of submitting another login request with an uncertain outcome.
UNCERTAIN = {
    "timeout", "connection_closed", "connection_failed", "invalid_response",
    "response_mismatch", "response_too_large",
}


def observed_state(client: Client) -> tuple[bool, str]:
    try:
        observation = client.observe("Vesper")
    except BridgeError as error:
        if error.code == "character_offline":
            return False, str(error)
        raise
    actor = observation.get("self") if isinstance(observation, dict) else None
    if not isinstance(actor, dict) or actor.get("name") != "Vesper":
        raise BridgeError("invalid_response", "The bridge returned a different character.")
    if actor.get("controller_owned") is not True:
        raise BridgeError("character_in_use", "Vesper is online in another session; no takeover was attempted.")
    return True, ""


def check_login_result(result: object, request_id: str) -> None:
    status = result.get("status") if isinstance(result, dict) else None
    if not isinstance(status, str) or status not in {"accepted", "completed", "failed"}:
        raise BridgeError("invalid_response", "Invalid login result.", request_id=request_id)
    if status == "failed" or (status == "completed" and result.get("attached") is not True):
        raise BridgeError("login_failed", "Vesper's login did not complete.", request_id=request_id)


def ensure_online(client: Client, timeout: float = 120.0) -> bool:
    """Return whether already online; allow at most one new attach per invocation."""
    deadline = time.monotonic() + timeout
    owned, phase = observed_state(client)
    if owned:
        return True

    request_id = ""
    if phase not in {"loading", "creating", "ready"}:
        request_id = str(uuid.uuid4())
        try:
            result = client.request("attach", "Vesper", request_id=request_id)
            check_login_result(result, request_id)
        except BridgeError as error:
            if error.code in {"busy", "character_online"}:
                # Another runner may have attached between our observe and request.
                request_id = ""
            elif error.code not in UNCERTAIN:
                raise

    while time.monotonic() < deadline:
        try:
            owned, phase = observed_state(client)
            if owned:
                return False
            if phase == "failed":
                raise BridgeError("login_failed", "Vesper's asynchronous login failed.", request_id=request_id)
        except BridgeError as error:
            if error.code not in UNCERTAIN:
                raise

        if request_id:
            try:
                cached = client.action_result("Vesper", request_id)
                response = cached.get("response") if isinstance(cached, dict) else None
                if not isinstance(response, dict):
                    raise BridgeError("invalid_response", "Missing login result.", request_id=request_id)
                if (response.get("v") != 1 or response.get("id") != request_id
                        or response.get("op") != "attach" or response.get("character") != "Vesper"):
                    raise BridgeError(
                        "response_mismatch", "Login result does not match its request.", request_id=request_id
                    )
                if response.get("ok") is not True:
                    error = response.get("error")
                    if not isinstance(error, dict):
                        raise BridgeError("invalid_response", "Missing login error.", request_id=request_id)
                    code = str(error.get("code") or "login_failed")
                    if code in {"busy", "character_online"}:
                        request_id = ""
                    else:
                        raise BridgeError(code, "Vesper's login was rejected.", request_id=request_id)
                else:
                    check_login_result(response.get("result"), request_id)
            except BridgeError as error:
                if error.code not in UNCERTAIN | {"unknown_request"}:
                    raise
        time.sleep(1)

    raise BridgeError(
        "login_timeout", "Vesper did not become online; no login request was resent.", request_id=request_id
    )


def main() -> int:
    try:
        already_online = ensure_online(Client({"credentials_file": ROOT / "server-admin.json", "timeout": 5}))
    except BridgeError as error:
        print(f"Vesper login failed ({error.code}). The game server remains running.", file=sys.stderr)
        if error.request_id:
            print(f"Original login request: {error.request_id}", file=sys.stderr)
        return 1
    print("Vesper is already online." if already_online else "Vesper is online.")
    print("Presence's model controller keeps its existing Start/Pause/Resume setting.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
