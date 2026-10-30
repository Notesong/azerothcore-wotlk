"""One read-only health and population sample for the local game server."""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path('C:/Games/AzerothCore')
spec = importlib.util.spec_from_file_location('market_setup', ROOT / 'scripts/Provision-Auction-Market.py')
market = importlib.util.module_from_spec(spec)
spec.loader.exec_module(market)

rows = market.sql("SELECT COUNT(*) FROM acore_characters.characters c JOIN acore_auth.account a ON a.id=c.account "
                  "WHERE a.username LIKE 'RNDBOT%' AND c.online=1")
auctions = market.sql('SELECT houseid,COUNT(*) FROM acore_characters.auctionhouse GROUP BY houseid ORDER BY houseid')
sample = {'at': datetime.now(timezone.utc).isoformat(), 'online_random_bots': int(rows[0][0]),
          'auction_stacks': {row[0]: int(row[1]) for row in auctions},
          'server_info': market.admin(market.Client(), 'server info').replace('\r', '').replace('AC>', '').strip()}
with (ROOT / 'economy-integration/population-samples.jsonl').open('a', encoding='utf-8') as handle:
    handle.write(json.dumps(sample) + '\n')
print(json.dumps(sample))
