# Vesper Loot Hints

A separate WoW 3.3.5 addon for Vesper's current party leader. Hover or target a visible creature corpse to see
server-confirmed quest-loot hints in its tooltip and a small, non-clickable panel. The panel sits beside an open
LootFrame, or stands alone when your own loot window is empty. It explicitly identifies the **inspected corpse**;
it does not claim to identify the native loot-window source.

Item names come from the client's item cache; uncached names display their item ID. Rows distinguish **available
for Vesper**, **not currently needed**, **already collected from this corpse**, **not available**, and **unknown**.
Progress belongs to Vesper. A partial, missing, expired, or incomplete reply never means the corpse has no quest
items. Availability remains subject to normal range, bags and loot rules.

The addon does not add loot slots, click items, move either player, send bot commands, or change Aurenne's pickup
eligibility. It has no model calls and no saved settings. Current party leadership and Vesper's membership are
checked before querying and displaying results. Offline Vesper displays **unknown** without sending whispers;
reconnecting permits a fresh query.

## Protocol

Only `VESPERLOOT` addon whispers to/from Vesper are used. GUIDs remain canonical `0x` plus 16 uppercase hexadecimal
digits; they are never converted through Lua numbers.

```
Q1|nonce|GUID
R1|nonce|GUID|state|rowCount
I1|nonce|GUID|itemId|remaining|needed|owned|required|rowState
E1|nonce|GUID|state|rowCount
```

Header states: `checked`, `partial`, `unknown`, `unavailable`. Row states: `available`, `not_needed`, `collected`,
`unavailable`, `unknown`. A matching complete start/rows/end transaction is required before any rows appear. Eight
rows maximum, 255 bytes including prefix per message, three-second reply deadline, five-second display lifetime,
and one query per second maximum. The sender, local realm, nonce, corpse GUID and current inspection are bound
together. Target/group changes discard pending replies. Closing loot discards the panel unless that corpse is still
explicitly targeted or tooltip-inspected.

Requires the matching read-only server bridge. Without it, hints become **unknown**. Client installation and live
validation are separate steps; this source has offline Lua 5.1 tests only.

API references: Blizzard's 3.3.5 FrameXML source:
[PlayerFrame.lua][playerframe] and [LootFrame.lua][lootframe].

[playerframe]: https://github.com/wowgaming/3.3.5-interface-files/blob/main/PlayerFrame.lua
[lootframe]: https://github.com/wowgaming/3.3.5-interface-files/blob/main/LootFrame.lua
