"""Configure the official AH module and native batched bot login; preserve other settings."""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil

ROOT = Path('C:/Games/AzerothCore')
DATA = ROOT / 'economy-integration'
identity = json.loads((DATA / 'auction-identity.json').read_text(encoding='utf-8'))
backup = DATA / 'config-backups' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
backup.mkdir(parents=True, exist_ok=False)


def changed(text, key, value):
    pattern = r'(?m)^' + re.escape(key) + r'\s*=\s*[^\r\n]*$'
    if len(re.findall(pattern, text)) != 1:
        raise RuntimeError('Unexpected configuration key count: ' + key)
    return re.sub(pattern, lambda _: key + ' = ' + str(value), text)


bot_path = ROOT / 'server/configs/modules/playerbots.conf'
world_path = ROOT / 'server/configs/worldserver.conf'
ah_path = ROOT / 'server/configs/modules/mod_ahbot.conf'
if ah_path.exists():
    raise RuntimeError('Auction configuration already exists; inspect before replacing.')
shutil.copy2(bot_path, backup / bot_path.name)
shutil.copy2(world_path, backup / world_path.name)
bot = bot_path.read_text(encoding='utf-8-sig')
world = world_path.read_text(encoding='utf-8-sig')
ah = (ROOT / 'source/modules/mod-ah-bot/conf/mod_ahbot.conf.dist').read_text(encoding='utf-8-sig')
for key, value in {
    'Playerbots.MinRandomBots': 1000,
    'Playerbots.MaxRandomBots': 1000,
    'Playerbots.DisabledWithoutRealPlayer': 0,
    'Playerbots.RandomBotsPerInterval': 20,
}.items():
    bot = changed(bot, key, value)
world = changed(world, 'PlayerLimit', 1500)
for key, value in {
    'AuctionHouseBot.EnableSeller': 1,
    'AuctionHouseBot.EnableBuyer': 1,
    'AuctionHouseBot.Account': identity['account'],
    'AuctionHouseBot.GUID': identity['guid'],
    'AuctionHouseBot.ItemsPerCycle': 100,
    'AuctionHouseBot.DuplicatesCount': 3,
    'AuctionHouseBot.DivisibleStacks': 0,
    'AuctionHouseBot.ProfessionItems': 1,
}.items():
    ah = changed(ah, key, value)
for path, text in ((bot_path, bot), (world_path, world), (ah_path, ah)):
    with path.open('w', encoding='utf-8', newline='\n') as handle:
        handle.write(text)
shutil.copy2(ROOT / 'source/modules/mod-ah-bot/conf/mod_ahbot.conf.dist', ah_path.with_suffix('.conf.dist'))
print('Configured market supply/demand and a 1000-bot target with bounded login batches; other settings preserved.')
