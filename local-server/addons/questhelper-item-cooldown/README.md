# QuestHelper 1.4.1 quest-item cooldown guard

This patch guards the quest-item cooldown update used by the watch frame. During
quest turn-in, a watch button can briefly outlive its special quest item, and
`GetQuestLogSpecialItemCooldown` can then return nonnumeric values. The reported
client error reached `FrameXML/Cooldown.lua` from `WatchFrameItem_UpdateCooldown`.

The guard wraps only `WatchFrameItem_UpdateCooldown`. When any of the three API
results is nonnumeric, it hides that button's cooldown, restores its normal
texture color and returns. Numeric results continue through the original
function with the original arguments and return values. Other cooldowns retain
their existing behavior. The fix is installed once when QuestHelper loads.

Local installation status: the one-file tracker update is installed. Ten offline
checks pass with the extracted client functions and with the public UI doubles.
The client still needs `/reload` or a restart; a new quest turn-in remains
unverified in play.

No game-server update, world restart, database change, extra model call or
saved-data reset is required. The existing `director_quest.lua` inventory refresh
and `collect_quest.lua` objective-shape fixes are separate and remain intact.

## Apply

Back up `Interface/AddOns/QuestHelper/tracker.lua`. Apply
`quest-item-cooldown.patch` relative to the QuestHelper folder. For example, with
Git available, run these commands from that folder:

```powershell
git -c core.autocrlf=false apply --check C:/path/to/quest-item-cooldown.patch
git -c core.autocrlf=false apply C:/path/to/quest-item-cooldown.patch
```

Use `/reload` or restart the client. Turn in a quest that removes a special quest
item and check the tracker; also check an ordinary usable quest item's cooldown. An
offline check does not establish that the client has loaded the new file.

The patch targets the following exact `tracker.lua` bytes:

| State | SHA-256 |
| --- | --- |
| Before | `e53f2456d586ad1ea1b171e12318a964c13521baa152d35a4e9f03413b86f8c7` |
| After | `bb1c13c19cdefea25a7cd97afa8e097ad4653d68bc5a55953e9f725d07857da3` |

To roll back, restore the original `tracker.lua` backup and use `/reload` or
restart the client.

## Offline checks

Use Python with `lupa.lua51`. The checks execute the guard from the selected
`tracker.lua` against small UI doubles and check the complete file's Lua 5.1
syntax. They make no game or model calls and do not modify the addon or saved
data.

```powershell
$env:QUESTHELPER_ADDON_PATH = 'C:/path/to/QuestHelper'
# Optional when lupa is installed in an isolated folder:
$env:LUPA_RUNTIME_PATH = 'C:/path/to/lua-runtime'
python tests/test_tracker_cooldown.py
```

If you have a private extraction of your client's `WatchFrame.lua` and
`Cooldown.lua`, set `WOW_FRAMEXML_PATH` to their folder to exercise the actual
client functions instead of the UI doubles. No client files are included here.

The ten checks cover quest-item removal, missing and nonnumeric API results,
normal cooldown behavior and return values, button reuse and isolation, hidden
button events, unchanged global APIs, repeated loading and Lua syntax.

## Contents and credits

This package contains a small patch, documentation and offline checks. It does
not include the full QuestHelper addon, its database, or Blizzard client source.
It targets QuestHelper 1.4.1. Its TOC credits **zorbathut, smariot, vipersniper and
nesher**. The installed package's `changes.lua` records that the source was
GPL'ed, but it contains no top-level license file identifying a GPL version;
retain the original addon's licensing and notices. The added guard and
regression checks are authored for this local integration.
