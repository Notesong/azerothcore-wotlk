"""Apply market quotas only after the normal updater has installed upstream SQL once."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path('C:/Games/AzerothCore')
spec = importlib.util.spec_from_file_location('market_setup', ROOT / 'scripts/Provision-Auction-Market.py')
market = importlib.util.module_from_spec(spec)
spec.loader.exec_module(market)
source = ROOT / 'source/modules/mod-ah-bot/data/sql/db-world'
names = ('auctionhousebot_professionItems.sql', 'mod_auctionhousebot.sql', 'z_filter_disabled_and_trash.sql')
for name in names:
    expected = hashlib.sha1((source / name).read_bytes()).hexdigest()
    rows = market.sql("SELECT hash,state FROM acore_world.updates WHERE name='" + name + "'")
    if len(rows) != 1 or rows[0][0].lower() != expected or rows[0][1] != 'MODULE':
        raise RuntimeError('The normal database updater has not confirmed module SQL: ' + name)
if market.sql('SELECT auctionhouse FROM acore_world.mod_auctionhousebot ORDER BY auctionhouse') != [['2'], ['6'], ['7']]:
    raise RuntimeError('Unexpected module market identities; no settings changed.')
backup = ROOT / 'economy-integration/auction-default-tables.sql'
if not backup.exists():
    with backup.open('wb') as handle:
        result = subprocess.run([str(ROOT / 'tools/mysql-8.4.13-winx64/bin/mysqldump.exe'),
            f'--defaults-extra-file={ROOT / "database-admin.cnf"}', 'acore_world',
            'mod_auctionhousebot', 'mod_auctionhousebot_disabled_items', 'auctionhousebot_professionItems'],
            stdout=handle, stderr=subprocess.PIPE)
    if result.returncode:
        raise RuntimeError('Module table backup failed; no settings changed.')
market.sql('UPDATE acore_world.mod_auctionhousebot SET minitems=2000,maxitems=2000,'
           'buyerbiddinginterval=1,buyerbidsperinterval=100,buyerpricewhite=50,buyerpricegreen=30,'
           'buyerpriceblue=40,buyerpricepurple=60,minpricewhite=400,maxpricewhite=600 '
           'WHERE auctionhouse IN (2,6)')
market.sql('UPDATE acore_world.mod_auctionhousebot SET minitems=500,maxitems=500,'
           'buyerbiddinginterval=1,buyerbidsperinterval=100,buyerpricewhite=50,buyerpricegreen=30,'
           'buyerpriceblue=40,buyerpricepurple=60,minpricewhite=400,maxpricewhite=600 '
           'WHERE auctionhouse=7')
market.admin(market.Client(), 'reload config')
rows = market.sql('SELECT auctionhouse,minitems,maxitems,buyerbiddinginterval,buyerbidsperinterval,'
                  'minpricewhite,maxpricewhite FROM acore_world.mod_auctionhousebot ORDER BY auctionhouse')
buyer_rows = market.sql('SELECT auctionhouse,buyerpricewhite,buyerpricegreen,buyerpriceblue,buyerpricepurple '
                        'FROM acore_world.mod_auctionhousebot ORDER BY auctionhouse')
expected = [['2', '2000', '2000', '1', '100', '400', '600'],
            ['6', '2000', '2000', '1', '100', '400', '600'],
            ['7', '500', '500', '1', '100', '400', '600']]
if rows != expected:
    raise RuntimeError('Market settings did not verify.')
if buyer_rows != [[str(house), '50', '30', '40', '60'] for house in (2, 6, 7)]:
    raise RuntimeError('Buyer prices did not verify.')
(ROOT / 'economy-integration/market-settings.json').write_text(json.dumps({
    'houses': rows, 'module_sql_recorded': True, 'buyer_enabled': True, 'seller_enabled': True,
    'profession_items_enabled': True, 'uses_normal_auction_mail_delay': True,
    'buyer_price_multipliers': {'white': 50, 'green': 30, 'blue': 40, 'purple': 60},
    'quota_is_background_target_not_guaranteed_catalog': True}, indent=2), encoding='utf-8')
print('Verified upstream SQL applied once; market targets 2000 Alliance / 2000 Horde / 500 neutral stacks, buyer enabled.')
