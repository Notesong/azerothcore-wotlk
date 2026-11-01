# QuestHelper 1.4.1 inventory refresh patch

This small patch refreshes QuestHelper's tracker after bag changes and changes to
the player's inventory. It coalesces a burst of inventory events into one scan
after 0.1 seconds, using the existing `QH_UpdateQuests(true)` path and notifier.
Other units' inventory events do not trigger that scan.

The observed failure had different counts in two client views: the normal
Blizzard quest log showed the purchased item at 1/1, while QuestHelper stayed red
until relogging. QuestHelper refreshed its director on `QUEST_LOG_UPDATE` but had
no inventory-event refresh. This patch reads the existing quest-log objectives;
it does not infer progress from item names or fabricate item counts. That matters
because different item IDs can have the same name.

November 1 status: the one-file `director_quest.lua` update is installed, with the
earlier collector fix preserved. The user confirmed that the normal quest log
showed the bottle at 1/1 and reported that relogging corrected QuestHelper's
existing display. That relog's timing relative to this patch is unconfirmed.
A new purchase updating the tracker without another relog remains unverified.

No game-server update, database change, extra model call or saved-data reset is
required. The separate `collect_quest.lua` objective-shape fix is retained and is
not part of this patch.

## Apply

Back up `Interface/AddOns/QuestHelper/director_quest.lua`. Apply
`inventory-refresh.patch` relative to the QuestHelper folder, then use `/reload`
or restart the client. Verify a new purchase, item loss and ordinary loot while
comparing the tracker with the normal quest log. An offline check does not prove
that the installed client has loaded the new Lua file.

This package contains only a patch and checks, not the full QuestHelper addon or
its database. It targets QuestHelper 1.4.1. Its TOC credits **zorbathut, smariot,
vipersniper and nesher**. The installed package's `changes.lua` records that the
source was GPL'ed, but it contains no top-level license file identifying a GPL
version; retain the original addon's licensing and notices. The added refresh
logic and regression checks are authored for this local integration.

## Offline checks

Use Python with `lupa.lua51`. The tests load `director_quest.lua`, `pattern.lua`
and `collect_notifier.lua` from the selected addon folder, replacing only game,
UI and database services. They make no game or model calls and do not modify the
selected addon or saved data.

```powershell
$env:QUESTHELPER_ADDON_PATH = 'C:/path/to/QuestHelper'
# Optional when lupa is installed in an isolated folder rather than this Python environment:
$env:LUPA_RUNTIME_PATH = 'C:/path/to/lua-runtime'
python tests/test_inventory_refresh.py
```

Five checks cover purchase without a quest-log event, burst coalescing, player
unit filtering, unchanged/lost item counts and separate party progress. The
original director fails all five checks; the patched director passes all five.
