"""Create one normal, offline auction character; restore the bridge allowlist afterward."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid

ROOT = Path('C:/Games/AzerothCore')
DATA = ROOT / 'economy-integration'
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'harness'))
from presence_acore.client import Client, _Reader


def sql(statement):
    result = subprocess.run([str(ROOT / 'tools/mysql-8.4.13-winx64/bin/mysql.exe'),
        f'--defaults-extra-file={ROOT / "database-admin.cnf"}', '--batch', '--skip-column-names',
        '--execute', statement], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError('A local database operation failed; credentials were not printed.')
    return [row.split('\t') for row in result.stdout.splitlines() if row]


def admin(client, command):
    username, password = client._login()
    with socket.create_connection((client.host, client.port), timeout=client.timeout) as connection:
        reader = _Reader(connection, time.monotonic() + client.timeout)
        reader.until((b'Username: ',))
        connection.sendall(username.encode() + b'\r\n')
        reader.until((b'Password: ',))
        connection.sendall(password.encode() + b'\r\n')
        if b'Authentication failed' in reader.until((b'AC>', b'Authentication failed')):
            raise RuntimeError('Local administrator authentication failed.')
        connection.sendall(command.encode() + b'\r\n')
        return reader.until((b'AC>',)).decode('utf-8', errors='replace')


def atomic_write(path, data):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.market-setup-', delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main():
    DATA.mkdir(exist_ok=True)
    with urllib.request.urlopen('http://127.0.0.1:8000/runtime/game-player', timeout=10) as response:
        runtime = json.load(response)
    if not runtime.get('paused') or runtime.get('controlled_character') != 'Vesper':
        raise RuntimeError('Vesper must remain paused during market provisioning.')
    client = Client()
    accounts = sql("SELECT id FROM acore_auth.account WHERE username='AHBOT'")
    if not accounts:
        password = secrets.token_hex(8)
        admin(client, f'account create AHBOT {password}')
        accounts = sql("SELECT id FROM acore_auth.account WHERE username='AHBOT'")
        if not accounts:
            raise RuntimeError('The dedicated auction account was not created.')
        (DATA / 'auction-account.json').write_text(json.dumps(
            {'username': 'AHBOT', 'password': password}, indent=2), encoding='utf-8')
    account = int(accounts[0][0])
    admin(client, 'account set addon AHBOT 2')
    existing = sql("SELECT guid,account,online FROM acore_characters.characters WHERE name='Marketkeeper'")
    if existing and (int(existing[0][1]) != account or existing[0][2] != '0'):
        raise RuntimeError('Marketkeeper already exists with a different owner or is online; nothing replaced.')
    if not existing:
        config = ROOT / 'server/configs/modules/presence_bridge.conf'
        original = config.read_bytes()
        text = original.decode('utf-8-sig')
        pattern = r'(?m)^(PresenceBridge\.AllowedCharacters\s*=\s*)"([^"\r\n]*)"\s*$'
        match = re.search(pattern, text)
        if not match or 'Marketkeeper' in match.group(2).split(','):
            raise RuntimeError('Unexpected bridge allowlist; no broadening performed.')
        temporary_text = text[:match.start()] + match.group(1) + '"' + match.group(2) + ',Marketkeeper"\n' + text[match.end():]
        backup = DATA / ('bridge-before-provision-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '.conf')
        backup.write_bytes(original)
        try:
            atomic_write(config, temporary_text.encode('utf-8'))
            admin(client, 'reload config')
            request_id = str(uuid.uuid4())
            result = client.request('create', 'Marketkeeper', request_id=request_id,
                                    account='PRESENCE', race=10, **{'class': 8}, gender=0)
            deadline = time.monotonic() + 95
            while result.get('status') == 'accepted':
                if time.monotonic() >= deadline:
                    raise RuntimeError('Character creation is unresolved; inspect before retrying.')
                time.sleep(0.25)
                envelope = client.action_result('Marketkeeper', request_id).get('response', {})
                result = envelope.get('result', {})
                if envelope.get('ok') is not True:
                    raise RuntimeError('Normal character creation failed.')
            if result.get('status') != 'completed':
                raise RuntimeError('Normal character creation was not confirmed.')
            client.detach('Marketkeeper')
            admin(client, 'character changeaccount AHBOT Marketkeeper')
        finally:
            atomic_write(config, original)
            admin(client, 'reload config')
    rows = sql("SELECT guid,account,online,level FROM acore_characters.characters WHERE name='Marketkeeper'")
    if len(rows) != 1 or int(rows[0][1]) != account or rows[0][2] != '0':
        raise RuntimeError('Dedicated offline auction identity did not verify.')
    if sql(f'SELECT gmlevel FROM acore_auth.account_access WHERE id={account} AND gmlevel<>0'):
        raise RuntimeError('Auction account unexpectedly has administrator permissions.')
    identity = {'account': account, 'guid': int(rows[0][0]), 'name': 'Marketkeeper',
                'offline': True, 'gm_level': 0, 'level': int(rows[0][3])}
    (DATA / 'auction-identity.json').write_text(json.dumps(identity, indent=2), encoding='utf-8')
    print(json.dumps(identity))


if __name__ == '__main__':
    main()
