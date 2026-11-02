"""Tune Marketkeeper through the module's normal live commands; preserve seller settings."""
from datetime import datetime, timezone
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path('C:/Games/AzerothCore')
DATA = ROOT / 'economy-integration'
HOUSES = (2, 6, 7)
MULTIPLIERS = {'white': 50, 'green': 30, 'blue': 40, 'purple': 60}
ATTEMPTS = 100


def support():
    spec = importlib.util.spec_from_file_location('market_buyer_support', ROOT / 'scripts/Provision-Auction-Market.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def snapshot(market):
    columns = [row[0] for row in market.sql('SHOW COLUMNS FROM acore_world.mod_auctionhousebot')]
    rows = market.sql('SELECT * FROM acore_world.mod_auctionhousebot ORDER BY auctionhouse')
    assert [int(row[0]) for row in rows] == list(HOUSES), 'Unexpected auction houses'
    return [dict(zip(columns, row, strict=True)) for row in rows]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Apply and persist the reviewed buyer profile live.')
    args = parser.parse_args()
    market = support()
    before = snapshot(market)
    values = {'buyerprice' + quality: value for quality, value in MULTIPLIERS.items()}
    values.update(buyerbiddinginterval=1, buyerbidsperinterval=ATTEMPTS)
    expected = [{**row, **{key: str(value) for key, value in values.items()}} for row in before]
    if not args.apply:
        print(json.dumps({'apply': False, 'buyer_changes': values, 'houses': list(HOUSES)}))
        return
    backup = DATA / ('buyer-before-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json')
    backup.write_text(json.dumps({'houses': before, 'buyer_changes': values}, indent=2) + '\n', 'utf-8')
    client = market.Client()
    for house in HOUSES:
        for quality, value in MULTIPLIERS.items():
            market.admin(client, f'ahbotoptions buyerprice {house} {quality} {value}')
        market.admin(client, f'ahbotoptions bidinterval {house} 1')
        market.admin(client, f'ahbotoptions bidsperinterval {house} {ATTEMPTS}')
    deadline = time.monotonic() + 5
    after = snapshot(market)
    while after != expected and time.monotonic() < deadline:
        time.sleep(0.1)
        after = snapshot(market)
    assert after == expected, 'Buyer settings did not verify; inspect the saved before snapshot before retrying'
    receipt = {'applied_at': datetime.now(timezone.utc).isoformat(), 'buyer_changes': values,
        'houses': list(HOUSES), 'backup': str(backup), 'all_other_market_settings_preserved': True,
        'server_restart_required': False, 'existing_highest_bids_are_not_reconsidered': True}
    (DATA / 'buyer-settings.json').write_text(json.dumps(receipt, indent=2) + '\n', 'utf-8')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
