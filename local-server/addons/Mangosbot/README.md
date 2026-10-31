# MaNGOSBot for this AzerothCore server

Type `/bot` in WoW to open the companion window. `/bot show`, `/bot hide`,
`/bot refresh` and `/mangosbot` also work. No server restart is required.

This replaces the older MaNGOS/SPP controls with the commands supported by the
installed `mod-playerbots`. It is for ordinary bot companions. Vesper remains a
separate Presence-controlled character and is excluded from these controls,
queries and group orders. No model calls are made by this addon.

## Using the window

1. Click **Refresh** to read the server's bot roster. Offline alts on your own
   account appear alongside controlled companions and grouped ordinary bots.
2. Select a companion. **Login/Logout** controls that character's bot session;
   **Invite** sends an ordinary party invitation. **Inspect** requests current
   character details, talents and combat strategies.
3. **Tank**, **Healer** and **Damage** apply a configured PvE talent preset for
   that class, wait for the server's acknowledgement, and apply the corresponding
   combat strategies. The displayed observed role comes from the server's reply.
   Unsupported roles are disabled. A missing reply produces a timeout rather
   than an assumed success. Below level 10, talent builds and role abilities
   are limited by the character's level.
4. After the role change completes, **Match gear** explicitly requests
   `autogear match`: generate upgrades for the current spec, within the server's
   quality limits and your average item level. It does not strip equipment
   first. Existing gear can remain if the server does not consider a replacement
   an upgrade; inspect weapon/shield suitability before relying on a new tank.
5. **Follow**, **Stay**, **Flee**, **Summon**, **Attack target**, **Leave party**
   and **Revive** affect only the selected ordinary bot. **Party follow/stay/flee**
   send individual orders to roster-confirmed bots in the party or raid.

The role preset is not a combat-performance guarantee. The companion still needs
the appropriate learned abilities and equipment for the encounter. The addon
does not automatically spend money, apply roles, generate gear or recruit bots.
Those changes require a button press.

## Recruiting and custom characters

**Recruit** uses `.playerbots bot addclass CLASS` and selects a companion from
the existing pool. It does not create a custom character. To match a recruited
companion's level and gear exactly, wait for it to join, then type:

```text
.playerbots bot init=auto ActualBotName
```

Do that before choosing a role preset: initialization can rebuild talents as
well as equipment. Your own custom alts instead use `.playerbots bot add Name`.
Create a Horde alt on your normal player account and log it out before adding it.
Do not use pooled-bot initialization as a progression routine for custom alts.

## Installation and source maintenance

The runtime files are `Mangosbot.toc` and `Mangosbot.lua`, installed under
`C:/Games/WoW/WotLK/Interface/AddOns/Mangosbot/`. The main Lua is standalone so
an already running client's cached original TOC/XML list can still load it.
It also prevents the original XML from creating a duplicate interface.

Edit `MangosbotAcore.lua` for protocol/role logic and `MangosbotUI.lua` for the
interface, then run `scripts/Prepare-Mangosbot-Addon.py` from the installation
root to regenerate `Mangosbot.lua`. Both source parts are included here for
maintenance; the runtime TOC loads only the assembled main.

The installed older addon was backed up and all 168 original files were
hash-verified before replacement. Its local backup location and deployment
record are in `addon-integration/deployment.json`. Old assets and XML may remain
in the client folder, but the new TOC does not load them. Existing saved settings
are retained; this edition saves its window position under `acorePosition`.

The original MaNGOSBot UI was developed by ike3 and maintained in related forks.
The previous local checkout was revision
`f385d2cdd5bd6ba7ba87dd77e9031af79eef9224` (davidonete, "Update priest commands").
This edition uses its existing addon folder/name with a replacement interface
and protocol layer for the local AzerothCore installation.

## Validation

Offline Lua 5.1 tests cover current command names, real elapsed-time throttling,
roster ownership, role acknowledgements/timeouts, quiet loading, Wrath UI event
arguments, pagination for 40 bots, cached old load order and Vesper exclusion.
They use a local `lupa.lua51` test runtime; the game does not need Python or Lupa.

From the installation/source-backup root, install `lupa` in a development Python
environment and run `python -m unittest discover -s addons/tests -v`.
