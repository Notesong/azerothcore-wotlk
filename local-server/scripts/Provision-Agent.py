"""Provision a normal, dedicated Presence character without granting GM privileges."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness"))
from presence_acore import BridgeError, Client
from presence_acore.client import _Reader


def sql(statement: str) -> list[list[str]]:
    process = subprocess.run([
        str(ROOT / "tools/mysql-8.4.13-winx64/bin/mysql.exe"),
        f"--defaults-extra-file={ROOT / 'database-admin.cnf'}", "--batch", "--skip-column-names",
        "--execute", statement,
    ], capture_output=True, text=True, check=True)
    return [line.split("\t") for line in process.stdout.splitlines() if line]


def admin_command(client: Client, command: str) -> None:
    username, password = client._login()
    with socket.create_connection((client.host, client.port), timeout=client.timeout) as connection:
        reader = _Reader(connection, time.monotonic() + client.timeout)
        reader.until((b"Username: ",))
        connection.sendall(username.encode() + b"\r\n")
        reader.until((b"Password: ",))
        connection.sendall(password.encode() + b"\r\n")
        greeting = reader.until((b"AC>", b"Authentication failed"))
        if b"Authentication failed" in greeting:
            raise RuntimeError("Local administrator authentication failed.")
        connection.sendall(command.encode() + b"\r\n")
        reader.until((b"AC>",))


def wait_result(client: Client, character: str, request_id: str) -> dict:
    deadline = time.monotonic() + 95
    while time.monotonic() < deadline:
        response = client.action_result(character, request_id).get("response", {})
        result = response.get("result", {})
        if result.get("status") != "accepted":
            if response.get("ok") is not True:
                raise RuntimeError(f"Operation failed: {result}")
            return result
        time.sleep(0.25)
    raise RuntimeError("Character operation timed out; inspect the result before retrying.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("character", choices=["Vesper", "Acoreprobe"])
    parser.add_argument("--attach", action="store_true", help="Log in after provisioning")
    args = parser.parse_args()
    client = Client()
    account = sql("SELECT id FROM acore_auth.account WHERE username='PRESENCE'")
    if not account:
        password = secrets.token_hex(8)  # Wrath account passwords are limited to 16 characters.
        admin_command(client, f"account create PRESENCE {password}")
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            account = sql("SELECT id FROM acore_auth.account WHERE username='PRESENCE'")
            if account:
                break
            time.sleep(0.25)
        if not account:
            raise RuntimeError("Dedicated game account was not created.")
        (ROOT / "agent-login.json").write_text(json.dumps({"Username": "PRESENCE", "Password": password}, indent=2), encoding="utf-8")
    admin_command(client, "account set addon PRESENCE 2")
    rows = sql(f"SELECT account,race,class FROM acore_characters.characters WHERE name='{args.character}'")
    race, player_class = (10, 2) if args.character == "Vesper" else (1, 5)
    if rows:
        if rows[0] != [account[0][0], str(race), str(player_class)]:
            raise RuntimeError("Existing character identity differs; no existing character was changed.")
        print(f"{args.character} already exists on the dedicated account.")
    else:
        request_id = str(uuid.uuid4())
        result = client.request("create", args.character, request_id=request_id,
                                account="PRESENCE", race=race, **{"class": player_class}, gender=0)
        if result.get("status") == "accepted":
            wait_result(client, args.character, request_id)
        print(f"Created {args.character} normally at level one (race {race}, class {player_class}).")
    if args.attach:
        try:
            state = client.observe(args.character)
            attached = bool(state.get("self", {}).get("controller_owned"))
        except BridgeError as error:
            if error.code != "character_offline":
                raise
            attached = False
        if not attached:
            request_id = str(uuid.uuid4())
            result = client.request("attach", args.character, request_id=request_id)
            if result.get("status") == "accepted":
                wait_result(client, args.character, request_id)
        state = client.observe(args.character)
        actor = state["self"]
        print(json.dumps({"character": actor["name"], "controller_owned": actor["controller_owned"],
                          "level": actor["level"], "race": actor["race"], "class": actor["class"],
                          "map_id": actor["map_id"], "zone_id": actor["zone_id"],
                          "nearby_units": len(state.get("nearby_units", []))}, indent=2))


if __name__ == "__main__":
    main()
