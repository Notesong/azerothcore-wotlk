# Vesper command reference

Current AzerothCore setup — November 1, 2026.

Feature progress and remaining playtests: [Vesper Player Checklist.md](Vesper%20Player%20Checklist.md).

For ordinary Playerbots, custom alts, recruitment and addon controls, see
[Bot Guide.md](Bot%20Guide.md) (verified October 30, 2026).

## Social gestures

Select Vesper, then use an ordinary WoW emote such as `/wave`, `/hug`, `/kiss`,
`/point`, `/laugh`, `/dance` or `/slap`. His social lane receives the actor,
gesture and explicit recipient. An untargeted or uncertain gesture does not
count as a direct request for his attention. The update is installed; start
Presence's AzerothCore controller to use it. Deployment and playtest status
are recorded in the checklist.

He can choose bow, cheer, clap, dance, hug, kiss, laugh, nod, point, salute,
shrug, slap, smile, thank or wave, with an explicit recipient or no recipient.
Custom free-text emotes remain separate. He chooses whether to respond, and
combat still takes priority. His current emote cooldown is **90 seconds**;
receiving your gesture does not reset it or require a reply.

These are social gestures, not fixed commands that order a particular reply.

Autonomous speech and emotes belong to the social lane; the body lane chooses
gameplay actions. Body decisions do not repeat your chat as Vesper's own speech.
Direct MCP speech and emote controls remain available.

## Quest-object pickup

The native body view now lists current corpse/chest loot candidates with their
exact GUID and matching `loot` action. Candidate corpses retain full alive/lootable
facts. This helps the model choose an available pickup; it does not promise a
quest drop or execute loot automatically. Pending openings are excluded from
repeat candidates. Normal bag, ownership, range and opening rules still apply.

Vesper can choose `loot` for an eligible quest book or ordinary chest. A chosen
pickup stops movement for its normal opening cast, then collects permitted loot
and checks actual item gains. The same request remains pending until it completes
or fails; routine observation does not recast it. Movement, combat or another
chosen action can interrupt it.

Fresh inventory and quest counts show what he actually collected. His journal,
orb and scroll pickups were verified at 1/1 each; Solanian's Belongings is ready
to turn in. Generic object line of sight is diagnostic for chest pickup; the
normal Opening handler decides access. `loot` performs Opening internally,
including when an informative `opening_spell_id` is present in the observation.
Generic carried quest-item activation remains on the development checklist;
quest-starting carried items are supported as described below.

On November 1, direct MCP control opened an Unstable Mana Crystal Crate
(object 180600) through normal Opening (3365). The original request completed
with one Unstable Mana Crystal (20743), no skipped slots and no pending opening.
Fresh inventory rose 0 → 1 and quest 8463 advanced 0/6 → 1/6. This verifies the
pickup mechanic.

After hand-back, Vesper chose two further `loot` actions at 15:34:19 and
15:34:57 UTC. Their original requests each completed with one crystal (20743),
no skipped slots and `partial: false`; the captured follow-up views showed
quest progress 2/6 and then 3/6. These demonstrate autonomous pickup choices.
Later live observation and user confirmation showed the crystal objective at
6/6: one direct MCP pickup and the remaining five during autonomous play. The
two receipts above establish individual results; the later count establishes
objective completion, not a turn-in or reward. Arcane Cores were 1/6 and the
Head of Thaelis was 0/1 at that check. Sustained reliability remains playtest work.

The missing Head was not a demonstrated failed loot operation. At 15:38:59 UTC,
Thaelis the Hungerer was dead, lootable and about 0.24 yards away, but the four
pickup choices shown to the body model were crates 5–48 yards away. Chest-first
ordering had omitted the nearby corpse. The retained ledger contained no loot
attempt on that Thaelis corpse. Its actual contents were never established.
The installed candidate correction now keeps ready corpse pickups ahead of
distant crates and mixes source kinds within the bounded list without
displacing ready pickups. At 16:07:36 UTC after that deployment, Qwen chose
`loot` on a new Thaelis corpse. Its original completed receipt stored one Head
of Thaelis (21781), with no skipped slots and `partial: false`. Fresh state
confirmed inventory count 1 and quest 8468 at 1/1 while Vesper was alive; the
user also confirmed the pickup. This demonstrates autonomous named-corpse
pickup, not the contents of the earlier unlooted corpse or sustained reliability.
It occurred before the follow-up approach freshness correction described below.

Navigation also remains a known problem. At 15:40:19 UTC, Qwen chose the exact
Bonfire center to "rest and recover gear durability" despite full health. A
later live check found him alive at that center with 135 health. Resting at a
fire does not repair gear; durability repair requires an actual repair service
and its normal receipt. The observation supplied no rest or repair service for
that object. The installed body guide now explains this when visible fires or
spell-focus objects are present: a name, selectable flag or object-center
coordinate establishes no repair service or useful waypoint. It does not ban
movement or label every spell-focus object hazardous.

Generated approach choices for loot, questgivers, services and a blocked lead
now use points two yards to the actor's side of the observed target in the horizontal
plane. They retain the observed target height and keep the source's actual
coordinates separate. These are choices for normal pathfinding, not proven
safe or reachable locations; fresh range and line-of-sight checks still decide
whether the intended interaction can proceed. An explicitly blocked follow
reports the line-of-sight problem and can offer this approach choice instead
of advertising another unchanged follow attempt.

The seven-file controller update is installed and passed 2,182 offline checks.
Head inventory and objective completion are now verified. The two-file follow-up
passing fresh observations into approach generation is also installed, with
2,190 offline checks passed. The actual Qwen 4B request at 16:12:26 UTC contained
two loot approach choices, each two horizontal yards to the actor's side of its
source with the observed source height preserved and no target-center destination.
This verifies model-visible choices, not executed movement or route safety.
Continued Bonfire avoidance and reliable follow recovery remain playtests.
Native hazard-script metadata and safe interaction zones are still unavailable.

## Vesper's quest-loot hints

The separate **VesperLoot** addon adds read-only corpse tooltip hints and a small
non-clickable panel. The server update and client package are installed, and the
server build and restart are complete. The font-wrapping compatibility correction
is installed; all 46 offline Lua 5.1 checks pass, including the absent optional API.
After a full client restart on November 1, the addon appeared in the AddOns list.
With Vesper in the party, the user confirmed a fresh Arcane Patroller's tooltip
and panel showed loot information. This verifies basic live display and replies;
detailed row states, group changes and range/expiry edges still need playtests.

After the addon folder is installed, **fully exit and restart WoW**, then enable
**Vesper Loot Hints** in the character-selection AddOns list. A newly added folder
needs the client's addon-list scan; `/reload` alone is not sufficient to discover it.
The client package is `Interface/AddOns/VesperLoot/`; it is separate from MaNGOSBot.

Be Vesper's current party leader, with Vesper online in the same party. Hover or
target a visible creature corpse. The panel labels the **inspected corpse** and
appears beside an open LootFrame, or independently if your own loot window is
empty. Its rows are hints, not extra native loot slots or pickup buttons.
Aurenne's quest quota and normal pickup eligibility remain unchanged.

| Hint | Meaning |
| --- | --- |
| `available for Vesper` | Remaining eligible loot matches his current need; normal bag/range rules apply. |
| `not currently needed` | His held objectives do not need it; this does not establish a pickup. |
| `already collected from this corpse` | The server recorded Vesper's actual pickup from this corpse. |
| `not available for Vesper` | The current per-player loot facts do not permit that item for him. |
| `unknown` / `not checked` | Facts are missing, pending, incomplete or expired; absence is not established. |

Item names use the client's item cache; an uncached item displays its item ID.
Progress belongs to Vesper. A partial reply leaves other items unknown. Replies
must match the sender, nonce and exact corpse GUID before any rows appear. Hints
expire after five seconds and refresh only while the corpse is still inspected;
offline Vesper shows unknown without sending whispers. No model call is made.

The bridge reads actual generated loot and per-player state, not potential drops
from a template. If generation or personal loot state cannot be confirmed, the
answer remains unknown. Confirming each row state and its change after a completed
Vesper pickup remains part of the pending live validation.

## Custom in-game commands

Type these in WoW chat. Both work while Vesper's model controller is paused and
do not call a model. Vesper must be online and in your party.

| Command | What it does | Who can use it |
| --- | --- | --- |
| `/p Vesper drop quest <quest link or numeric ID>` | Abandons one active quest and reports the result in party chat. | The current party leader. |
| `/p Vesper clear protection` | Releases Vesper's persistent Moon protection. | Aurenne, as the original person who marked the creature, while in his party. |

### Drop a quest

```text
/p Vesper drop quest <quest link or numeric ID>
```

Replace the placeholder with the full clickable quest link or its numeric ID;
do not type the angle brackets. Shift-click the quest in your quest log to insert
its link into chat. A plain quest title or partial name does not work. This drops
one quest at a time, using the normal quest-abandon rules and item cleanup.
Vesper confirms which quest was dropped, or tells you why it failed.

To share it again, select it in your quest log and click **Share Quest**. Shared
quests are accepted locally when Vesper is eligible, including while the model
controller is paused.

### Protect a creature with Moon

Mark the creature **Moon** using the normal target-marker menu while grouped
with Vesper. Apply it before fighting or starting a tame.

- Vesper and units he controls leave it alone, including in self-defense.
- He attempts normal movement away if it attacks him; a failed escape does not
  authorize retaliation.
- Human party healing and beneficial assistance are withheld while protection
  is active. His reflection mechanics are disabled too.
- Positive area-aura sources owned by Vesper are also cancelled during Moon,
  uncertain protection or an active/recent tame, so a self aura cannot keep
  assisting through propagation. Other casters' aura sources are not changed.
- The stored creature identity survives death, lost visibility, disconnects and
  party changes. Low health and failed tame attempts do not release it.
- Other players, their pets and other bots retain their normal behavior.

To release it, explicitly remove/change Moon while Vesper is online, or send:

```text
/p Vesper clear protection
```

The command releases the stored instruction even if the icon remains visible.
Remove and reapply Moon to protect it again. Marker changes made while Vesper
is offline cannot clear his stored instruction; use the command after reconnecting
or explicitly reapply/change the marker while he is online.

Some control effects and missiles already selected or launched before marking
cannot be recalled. Mark first.

### Moon instructions and attempted violations

The body planner receives the full standing Moon instruction whenever protection
is active or its stored state is unavailable. Attack and cast remain choices;
the hard guard still enforces protection.

The detailed Moon script is conditional, rather than an always-present body
instruction. An active/recent tame without Moon gets its own short hands-off
instruction. Ordinary play carries protection status without the full script.

Direct proposals against the protected creature and action-linked guard
interventions are saved with the original request context, proposed/submitted
actions and result. This includes a proposal changed to a wait before submission,
and an accepted cast whose protected effects the server filtered out. Automatic
or delayed effects without a reliable decision link are reported separately;
they do not prove the planner chose to violate Moon.

Read the latest saved incident through the MCP call below. Older retained records
are individual JSON files in:

```text
C:\Files\Programs\Codex\Presence\working\backend\data\runtime-game-player-moon-violations\
```

The archive keeps the newest 100 records. Later model requests and controller
restarts do not overwrite a retained incident's context. Stable persona,
credentials, image bytes and hidden reasoning remain omitted, as in the existing
model-context inspection. Capture or storage failures are reported explicitly.

## Ordinary chat and requests

| Type in WoW | Meaning |
| --- | --- |
| `/invite Vesper` | Sends a normal party invitation. His planner chooses whether to accept. |
| `/p Hello, Vesper!` | Sends party chat he can receive. |
| `/p Vesper, follow beside me.` | Asks his planner to follow you; his saved spacing is one yard beside you. |
| `/p Vesper, wait here a moment.` | Asks his planner to stay put. |
| `/p Vesper, turn in Thirst Unending with Arcanist Helion.` | Asks him to approach the observed questgiver and advance the quest's normal dialog and reward steps. |
| `/p Vesper, check whether anything in your bags starts a quest.` | Asks him to inspect carried quest starters and decide whether their offers fit the adventure. |
| `/p Vesper, check the trainer and see what you can afford.` | Asks him to inspect a nearby trainer's offers and choose training. |
| `/p Vesper, compare that new sword with your current weapon.` | Asks him to inspect carried gear and decide what to equip. |
| `/p Vesper, check your carried gear and equip useful upgrades and bags.` | Asks him to review available equipment during safe downtime. |
| `/p Vesper, sell the junk you don't need and repair your gear.` | Asks him to inspect a nearby vendor and choose sales or repairs. |

These sentences are examples of ordinary requests, not additional
fixed commands. Party invitation decisions and ordinary requests need his model
controller running and unpaused. Use
**Pause** in Presence when you need to suspend model decisions reliably. Local
movement, melee and protection behavior can continue between decisions.

Vesper normally speaks in party chat while grouped and `/say` while solo.
WoW's `/follow Vesper` makes **your character** follow him.

## Vesper's shopping, training and gear controls

The body planner can inspect nearby vendor and trainer menus, buy and sell items,
use the normal vendor buyback list, repair gear, learn offered spells, inspect
carried items, and equip or unequip them. Prices and stock, training requirements,
equipment and item details appear in his structured view. Long menus have pages.

He must reach the NPC normally. Purchases, training, repairs and equipment use
ordinary money, inventory space, class/level requirements and the normal game
handlers. These are available choices for the body planner; they do not automatically sell
junk, spend money, train every spell or equip an item.

The November 1 local service view links observed NPCs to approach/list actions,
current available trainer offers to exact learning actions, and ordinary poor
miscellaneous drops to a vendor or sale step. The junk list excludes held quest
requirements even after their counters are full, plus equipment, bags, supplies
and uncertain items. Other items still allow deliberate inspection and ordinary
sale choices. A positive price or `usable=true` alone does not make an item junk.
Opening a trainer list does not spend money; learning a chosen lesson does.

In live autonomous play, Vesper sold **four junk stacks for 52 copper**, then
learned **Devotion Aura, Judgement of Light and Blessing of Might** at Jesthenis
Sunstriker. Normal receipts confirmed three new spells and **199 copper spent**
(9 + 95 + 95). His money changed **905 → 957 → 758 copper**, leaving **7 silver
58 copper** after training. These were model choices, without operator sale or
training actions. Reliable future discovery and buyback recovery still need
playtesting; he tried several wrong-class trainers before finding the right one.

NPC trainer metadata is now installed. Names were already visible; nearby NPC
rows can now also show their title and default trainer type, requirement and
class. These facts reach bounded body/social views and the full MCP observation
when the NPC is visible. No online-player roster is needed to identify NPC
trainers. `class_matches_self` is an advisory comparison, not a promised lesson
or forced action. Default-provider metadata does not establish current spell
offers; the actual menu, requirements and normal handlers decide learning.

The clean restart preserved his three learned spells and 758 copper. No trainer
was in his post-restart observation, so seeing the new class/title fields in a
real trainer encounter remains the next playtest.

Lost transaction replies are marked uncertain. The controller checks the original
request once, without resending the purchase; fresh inventory, money and learned
spells help resolve what happened. Actual partial results remain visible.

These action names are internal planner controls, not slash commands to type:
`vendor_list`, `vendor_buy`, `vendor_sell`, `vendor_buyback`, `vendor_repair`,
`trainer_list`, `train_spell`, `inspect_item`, `equip_item`, `unequip_item`,
and `gossip_select`. Ordinary requests above go through his models and need the
controller unpaused.

## Buffs, auras and blessings

Installed November 1. Vesper can now observe bounded non-passive aura lists,
including caster, duration, rank family and active-effect masks. Known support
spells expose their actual target roles, effects, power cost, range, reagents
and cooldowns. Learned spells and currently active effects are separate facts.

Devotion Aura is cast on himself and can propagate to nearby party members.
Blessing of Might needs a separate cast on each intended recipient; having it
on Vesper does not establish that Aurenne has it. A cast request alone does not
prove application: check the recipient's fresh aura facts.

| Effect state | Meaning |
| --- | --- |
| `present` | A matching effective aura or rank is observed; avoid redundant recasts. |
| `suppressed` | The application exists with no active effects; blindly recasting is not a fix. |
| `alternative_active` | His own other aura/seal in a verified exclusive group is active; switching is a choice. |
| `missing` | Complete observations show no matching effect; a ready cast may be offered as a choice. |
| `unknown` | Observations are unavailable, partial or uncertain; this does not establish absence. |

Useful effect changes can wake the body planner during safe downtime. Duration
ticks do not summon a new decision each time. Buff-change wakes defer to active
loot/trade waits, combat and party priorities. Routine upkeep candidates exclude
temporary spells shorter than 60 seconds and Honorless Target effects
(`aura_type: 159`). Those spells remain ordinary cast choices for situations
where they are useful; a missing defensive shield is not unfinished routine upkeep.
This is not a fixed buff rotation.

Live verification around 06:30 UTC confirmed Vesper autonomously activated
Devotion Aura, Blessing of Might and Seal of Righteousness on himself, then
waited with upkeep complete. Aurenne's fresh aura list also confirmed Devotion
Aura (465, effect mask 1) and Blessing of Might (19740, effect mask 3), both from
Vesper (caster GUID 102). Party application is verified. Unnecessary repeated
casts have still occurred; consistent upkeep and expiry recovery need playtesting.

Moon/taming protection still governs beneficial spells, including self-targeted
area auras. The hard guard blocks new protected area assistance and cancels
Vesper-owned positive area-aura sources; it leaves other casters' sources alone.
Cast choices stay visible for deliberate decisions and attempted violations
remain auditable. These new guarded area-aura cases still need a live playtest.

## Quest dialogs, rewards and bags

Installed October 31, 2026. Vesper receives current NPC quest dialogs, advertised reward choices and item
comparisons, the normal item-check-to-reward transition, explicit quest status
names and nearby questgiver relations. The body planner chooses whether to accept, turn in
or select a reward. A dialog opening is distinct from receiving a reward.

Its internal planner actions are `quest_query`, `quest_accept`, `quest_complete`,
`quest_request_reward` and `quest_reward`. They use observed source/quest identities;
reward selection requires the exact advertised zero-based index. These are not
WoW slash commands. Normal quest handlers still check eligibility, objectives,
required items, money and inventory capacity. Querying a quest can trigger the
game's ordinary auto-accept behavior, so it is not a read-only MCP operation.

### NPC quest acceptance

For a new NPC quest, `interact` opens a fresh menu, `quest_query` reads the exact
offered quest, and `quest_accept` accepts it when matching fresh details enable
acceptance. A `both` relation does not mean the quest is already held. An unheld
quest's `request_items` page needs a query, not another completion/reward attempt.
If the menu is stale, use `interact` to refresh it before querying.

On November 1, direct MCP control accepted **Swift Discipline (9066)** from
Instructor Antheol. The normal receipt and fresh quest log confirmed acceptance;
fresh inventory contained one **Antheol's Disciplinary Rod (22473)**.

The planner correction is installed, with 2,350 offline game-player checks passing.
It supplies exact current query/accept choices across body providers while leaving
the choice to Vesper. An autonomous offered-quest playtest is still pending.
Targeted use of the granted quest item remains on the development checklist.
The November 1 observation showed Ralen 1/1 and Meledor 0/1; normal group credit
can advance these objectives without Vesper using the rod. `cast` requires a
learned spell and does not activate carried items.

### Quest-starting carried items

A carried item's `start_quest` facts identify its offered quest and current
normal eligibility. The local view links the exact owned item GUID and quest ID
to `quest_query`; fresh enabled details can then offer `quest_accept`. Reading
the item does not require travelling to a vendor or NPC. During safe downtime,
the local guide highlights this opportunity before optional buff or service work;
Vesper still chooses whether it fits the current party plan.

On November 1 at 07:05:42 UTC, a normal query of Tainted Arcane Sliver (item 20483)
accepted quest 8338 through the game's normal auto-accept behavior. The quest was
verified complete in his log. The sliver remained because the turn-in required
one; its continued presence was not an acceptance failure. The item started the
quest; Arcanist Helion was the turn-in NPC.

At 07:39:51 UTC, Qwen chose `quest_reward` for Helion and quest 8338 with the
advertised index 0. The normal receipt confirmed the quest became rewarded and
left the log, the sliver count fell 1 → 0, and money rose 753 → 903 copper
(150 copper received). This quest had no selectable item reward. Generic
quest-item activation and broader reward-selection judgment remain separate.

Turning in takes several decisions: `interact` opens the NPC's menu;
`quest_complete` selects the held quest and opens its turn-in dialog;
`quest_request_reward` advances a ready item-check dialog when needed;
`quest_reward` claims the selected offered reward. Opening the NPC repeatedly
does not finish the quest. The local body view now links each ready held quest
to a currently observed questgiver and its exact next menu/dialog action, with
the advertised reward indices kept as choices for the planner. Current positions
support ordinary local approach; this does not locate distant unseen NPCs.

During safe current-dialog work, a short guide emphasizes the actual phase:
current NPC menu → `quest_complete`; ready `request_items` → `quest_request_reward`;
`offer_reward` → a chosen advertised `quest_reward` option. It discourages
reopening an earlier phase after advancing. An explicitly empty, complete,
visible choice list permits index 0 to claim the normal XP/money/fixed rewards;
missing or hidden choices do not. All actions and real reward choices remain.

His view also exposes backpack and bag capacity, separating general-purpose free
space from specialty bags. The existing `equip_item` action can equip a carried
bag or request a particular bag slot. The body model receives guidance to notice usable
bags and compare capacity; the controller does not select equipment for him.

The social view now retains up to four current equipped-bag identities, matched
by exact GUID and equipment slot. Missing or conflicting facts stay unknown.
At the November 1 check, Small Brown Pouch (4496) was already equipped in slot
20 with six slots; total inventory capacity was 26. A failed quest action had
been mistaken for an equip failure in speech. Social guidance now attributes
failures only to the matching action and item/target, using current equipment
facts for equipment status. This verifies that bag at that check, not future
equipment decisions.

The native body view now links carried eligible gear to its exact observed slot,
the current item or an empty slot, and an equip action. During safe downtime he
can choose preparation instead of repeatedly waiting or moving to his own
position. This was verified with his quest-reward gauntlets, vest, boots and
other carried armor, plus the Sunstrider Book Satchel. You can also ask in party
chat: `/p Vesper, check your carried gear and equip useful upgrades and bags.`

After the November 1 context update, Qwen chose and successfully equipped the
Shoddy Chain Pants (37 armor, +35 base armor) and Shoddy Chain Belt (24 armor,
+5 base armor). Green Chain Boots remained equipped at 46 armor. These were
autonomous choices with normal completion receipts; stable future gear choices
still need playtesting.

Equipment candidates are legal options, not upgrade recommendations or a list
to work through. Comparisons show signed base-template armor and stat changes
against the currently equipped item. For example, replacing 46-armor boots with
2-armor boots shows `base_armor_delta: -44`. Missing comparisons stay unknown;
enchantment and random-property bonuses are excluded from these base deltas.
The planner still chooses whether an actual tradeoff is useful. It should not
swap equipment merely to test the interface unless you ask for an experiment.

Failed movement includes the exact attempted destination and recent failure
counts. `no_path` means the normal pathfinder rejected that attempt; an observed
upstairs NPC position alone does not establish a route to that floor.

Meaningful quest readiness/dialog changes receive bounded body-planner attention.
Individual objective-counter ticks do not summon a new model decision each time.
Lost quest-action replies use the original request identity for one recovery
check, instead of automatically resending an acceptance or reward choice.

The server and Presence changes are installed. MCP's `live_preview` shows the new
facts immediately; a quest dialog is empty until Vesper opens one normally.
`last_request` changes after the next genuine model request. Start the controller
in Presence when ready to test his choices; installation preserves its stopped or paused setting.

Remaining player-loop work includes targeted quest-item/consumable use, talent
spending, dungeon Need/Greed/Pass choices, hearthstone/flight/bind actions, and
release, corpse reclaim and real resurrection-offer controls. Ordinary game-object
interaction and known unit-targeted spell casting already exist, but do not cover
every quest mechanic.

## Giving Vesper gear through trade

Updated November 1, 2026. With Presence running and unpaused, initiate WoW's normal
trade with Vesper. His `trade_begin` choice opens the window; it does not accept
an exchange. Place the gear or money in your offer and click Accept. He sees the
real partner, offer, available bag space and acceptance state, then chooses
whether to accept. Changed offers need fresh consent. Both players must accept
before anything transfers.

While an open trade is empty, or Vesper has accepted and is waiting for your
acceptance, the local controller can wait up to 60 seconds without repeatedly
asking the body model. Offer/acceptance changes and other meaningful interrupts
can still wake it. This waiting state does not count as a completed transfer.

A real gift of **three items and 600 copper (6 silver)** was verified through
the server's completed-transfer receipt and before/after inventory and money
facts. Receiving an item does not establish that he has equipped it.

This first version receives gifts; it does not put Vesper's items or money into
the window or perform trade-slot services. Its internal actions are
`trade_begin`, `trade_accept`, `trade_unaccept` and `trade_cancel`, bound to the
current partner, trade identity and offer revision. These are not slash commands.
Acceptance alone is distinct from the server's completed-transfer receipt.
After a server restart, reopen any interrupted trade normally.

## Visible interaction feedback

Vesper makes a brief hand/talk gesture when a normal NPC interaction or quest
dialog advances, including opening a vendor or trainer menu. Opening a valid
corpse loot window gives a brief pickup gesture. Chest pickups retain their
normal opening spell animation. Extra gestures skip movement, combat and casting
and are rate-limited. They indicate an interaction began, not that an item was
received or a quest reward was claimed.

The November 1 core update clears Vesper's stored `/dance` loop when he resumes
a mechanical action or is moving, fighting or casting. This clears the cosmetic
animation without changing his posture, movement, spell or combat decision.
It applies to the Presence-owned character; other bots keep their own behavior.
Normal-action QA verified dance state `10` returning to `0` after native `stop`.
Following after a dance still needs a live check with Aurenne online.

## MCP context and direct gameplay

Vesper's body view now has shared readable stat labels and advisory gear guidance.
For Paladin melee leveling, it favors usable weapon upgrades and Strength for
damage, Stamina/armor for survival, secondary Intellect for mana and low priority
for Spirit. A different explicitly agreed role takes precedence. This does not
force equipment changes or assert that his talent specialization was observed.

Rarity alone is not an upgrade rule. Candidate eligibility and weapon/shield
tradeoffs matter; unresolved suffix/enchantment bonuses stay unknown. Inspecting
a weapon adds its exposed first-component base DPS, not total character DPS.
Numeric stats, damage bounds, weapon speed and existing collection caps remain.

`wow_model_context` with `source: "live_preview"` can show this current view
without a model call. `last_request` shows the original request that was recorded;
new guidance appears there after the next genuine body-model call.

These are tool calls for Vesper's ChatGPT/MCP connection, not WoW chat commands.
They use the existing **Local Context Gateway**. Refresh that connection if a
tool is missing. Reading context never makes a model call. Direct actions require
an explicit takeover, which stops both local model lanes first. Hand-back can
restore controllers that were running before the visit; stopped ones stay stopped.
MCP has no artificial model-call or token quota. Native game rules and Moon
protection still apply.

| Tool call | What it shows |
| --- | --- |
| `wow_status({})` | Live character state, controller status, last decision/action and available Vesper-attributed Chronicle entries. |
| `wow_observe({})` | Fresh structured surroundings, quests and recent game events. |
| `wow_model_context({"lane":"body","source":"live_preview"})` | A fresh observation filtered for the body planner. |
| `wow_model_context({"lane":"social","source":"live_preview"})` | A fresh observation filtered for the social planner. |
| `wow_model_context({"lane":"body","source":"last_request"})` | Dynamic context recorded at the latest body-model request attempt. |
| `wow_model_context({"lane":"social","source":"last_request"})` | Dynamic context recorded at the latest social-model request attempt. |
| `wow_model_context({"lane":"body","source":"last_violation"})` | The latest retained Moon attempt/intervention, with its original body request context and action outcome. |
| `wow_full_context({"lane":"social"})` | Complete recorded HTTP request: personality, instructions, dynamic input, schema, generation settings and any included image data. Authentication headers are never recorded. |
| `wow_control({"action":"status"})` | Current manual-control generation and hand-back status; this alone does not prove ownership. |
| `wow_control({"action":"status","control_token":"<exact takeover token>"})` | Check `owned_by_control_token` for the active remote lease. |
| `wow_control({"action":"take_over","operation_id":"<new UUID>"})` | Stop the local controllers and receive the secret control token and generation for Vesper. |
| `wow_act({"control_token":"<token>","operation_id":"<new UUID>","action":{"type":"follow","target_guid":"<observed GUID>","distance":1}})` | Choose a normal native action, using exact observed identities. |
| `wow_action_result({"operation_id":"<action UUID>"})` | Check the actual result of an accepted action. |
| `wow_wait({"since":"<wait cursor>","timeout_sec":20,"event_types":["combat_start","directed_chat","directed_emote"]})` | Wait for relevant changes, then receive a fresh snapshot. No model call. |
| `wow_control({"action":"hand_back","control_token":"<token>","operation_id":"<new UUID>"})` | End the visit and restore the prior local controller intent. |

`wow_status` optionally accepts `{"chronicle_limit":3}` (0–10; default 3).
`wow_observe` optionally accepts `{"since":123}`; replace 123 with the event
cursor returned by a previous observation to request newer events.
That integer cursor belongs to the legacy observation history. For `wow_wait`,
use the separate **`wait_cursor`** returned by `wow_observe`, then the `cursor`
returned by each wait. It contains a server epoch and character sequence. Waits
last at most 30 seconds; omission of `since` starts at the current journal baseline.
History rollover and server restarts are reported explicitly. A returned event
is a reason to inspect the fresh snapshot, not a complete account of current state.

Wait filters also include `combat_stop`, `damage`, `death`, `party_separation`,
`arrival`, `action_result`, `loot_change`, `quest_change`, `area_change`, and broad
`chat`/`combat`. Damage entries are observed health deltas, not a complete combat
log. Separation uses measured 30-yard departure and 25-yard reunion thresholds,
plus map/visibility facts; those events do not prescribe what to do.

For a large full request, keep the returned `revision` and `sha256` and request
the next UTF-8 byte page using `offset: next_offset`. A rotated-away revision
returns unavailable rather than switching to a different call. The archive keeps
64 complete requests per lane; a stopped controller's old capture remains valid
history. Old calls that were never fully captured cannot be recovered exactly.

Reuse a mutation's UUID only when checking/retrying that **identical** operation.
After a timeout, inspect its receipt before choosing another mutation. An accepted
movement, spell or loot action is not proof of completion. Persistent movement and
melee can continue locally between tool calls.

The November 1 remote-ownership correction is installed and verified;
the live result is recorded below. Its remote lease belongs
to the exact secret takeover token and generation. SDK connection/session changes
do not transfer that identity. Send the token with `wow_act` and `hand_back`, and
prove current ownership with token-bearing status: `owned_by_control_token` must
be true. Public status, a session ID or an operation UUID is not ownership proof.
Do not publish the token in notes or logs. Old tokens and retries cannot affect
a later generation.

Hand back explicitly before ending the visit. The server cannot infer that a
ChatGPT turn ended. Closing or replacing the remote MCP transport alone does
not revoke its lease; it has no automatic expiry. Optional local stdio diagnostic
sessions retain strict session-bound ownership and disconnect cleanup.
`resume_previous:false` leaves prior controllers stopped.

Presence now displays **Preparing MCP control**, **MCP-controlled** or
**Handing back MCP control** instead of a misleading stopped state. Start and
Resume are disabled while the interlock blocks autonomy; invalid or unreadable
lease status stays blocked. This display reads status and never releases control.
After `hand_back`, verify ownership is released and the previously running
autonomous controller has resumed. Ending the chat does not perform this step.

On November 1, local operator recovery released a completed visit's stranded
generation 38 and restored the local controller. A complete normal MCP visit
through explicit hand-back remains on the playtest checklist.

If a crash strands ownership, inspect status, then run this locally in PowerShell
to release only the generation you just checked, keeping the model runners
stopped. Replace `<observed generation>` with its integer value:

```powershell
$env:PYTHONPATH='C:\Games\AzerothCore\harness'
& 'C:\Files\Programs\Codex\Presence\working\backend\.venv\Scripts\python.exe' -B -m presence_acore.mcp_control --recover --expected-generation <observed generation> --leave-stopped
```

Use `--resume-previous` instead only when you want the saved running/paused intent
restored. A changed generation makes this recovery fail without releasing the
new owner. This recovery command is local operator tooling, not an MCP action.
The `chat` filter includes party conversation; `directed_chat` requires an actual
packet recipient, and `directed_emote` requires an explicit incoming target GUID.
`wow_model_context({})` defaults to body/last_request.
`last_violation` supports the body lane only; an empty archive means no retained
incident, not a new model call or a completed behavior test.

**Live preview** omits the running controller's additional notes and conversation
selection. **Last request** records the actual serialized dynamic context and
request outcome, with stable persona/instructions, credentials, image bytes and
hidden reasoning omitted. Check its timestamp and session: it may be historical.
It is not proof that a chosen game action succeeded. A lane has no recorded request
until its next real model call; inspecting it does not generate one.

## Death, ghost navigation and Spirit Healers

The native ghost-navigation fix is installed and verified through actual movement.
It permits normal `move_to` and `stop` after Vesper has released as a ghost,
and exposes `self.is_ghost` plus numeric `self.death_state`. Normal same-map,
range, pathfinding and immobility checks remain. Pending movement fails on a
living/ghost transition or unreleased death before arrival is reported.

Ghost following, combat, casting and looting remain blocked. An already released
ghost can now use an observed Spirit Healer through the normal dialog:

1. Reach the visible healer, choose `interact`, then select the exact advertised
   `gossip_select` recovery option. This opens the server's confirmation; it does
   not resurrect Vesper.
2. Choose the exact `recovery.spirit_healer_confirmation.next_action`,
   `spirit_healer_activate(target_guid)`, while that confirmation is current.
   Inspect the resulting `recovery_receipt` for actual life, sickness and
   durability changes.

The confirmation lasts 30 seconds and is bound to that character, session,
healer and current scene. Movement, another target/dialog, death/release,
resurrection or logout invalidates it; submitting it consumes it once. The
healer must remain visible, normally interactable and in range and line of sight.
A lost reply is checked through its original request identity, without another
activation. Historical receipts do not authorize a new recovery.

The normal server applies its configured costs. At level 6, Vesper had no
resurrection sickness; sickness starts at level 11 in this setup. Spirit Healer
recovery uses a 25% maximum-durability loss on equipped and carried durable items,
including bag contents. Read the actual receipt rather than assuming every
item loses the same number of points.

Direct MCP verification on November 1, generation 30, used healer menu 83,
option 0 and the normal confirmation. The activation receipt confirmed
`alive: false → true`, `is_ghost: true → false`, health 1 → 79 of 158,
14 actual durability changes and `resurrection_sickness: null`. Later health
regenerated to 158. Explicit hand-back restored Full running with Social stopped.
This verifies chosen Spirit Healer recovery, not autonomous recovery decisions.

Release, corpse reclaim and acceptance of a real resurrection offer remain
unimplemented. The full death/recovery/rejoin loop is still incomplete. Continue
to verify each move and recovery through fresh state and its original receipt;
Moon protection remains active.

**MCP ownership and ghost-navigation update — November 1:** the generation 23
orphaned lease was released locally and the prior Full controller was restored.
The ownership changes passed 218 harness tests, 86 subtests and 36 focused
TypeScript tests. The native change passed 181 source predicate/state checks
and its build; the gateway and native update are installed.

Live verification used separate connected MCP calls under generation 25.
Token-bearing status returned `control_mode: lease_token`,
`owned_by_control_token: true` and `owned_by_session: false`.
A normal map-530 ghost `move_to` advanced X 9407 → 9410; its original UUID
receipt completed with `arrived: true`. Fresh observation remained
`is_ghost: true`, `alive: false` at `(9410, -6847.6699, 15.468)`, about
3.047 yards from the starting position. Explicit hand-back released the lease
and restored Full running with Social stopped. This proves remote ownership,
normal ghost movement and hand-back. The later Spirit Healer test adds normal
recovery; release, corpse reclaim and real resurrection offers remain open.

## Ordinary companion bots and the addon

Type `/bot` to open the updated MaNGOSBot window. It controls ordinary native
Playerbots; Vesper's Presence character is excluded from its roster and orders.
The window supports companion login/logout, recruiting by class, party orders,
server inspection, role presets and explicit gear matching.

Create a Horde alt on Aurenne's normal player account, log the alt out, and use
`.playerbots bot add AltName` on Aurenne to bring it in as a companion. Remove it
with `.playerbots bot remove AltName`. Ordinary online bots can be invited with
`/invite Name` when available.

For a pooled companion, use `.playerbots bot addclass warrior` (or another class).
If an exact level/gear match is wanted, run `.playerbots bot init=auto BotName`
before choosing a role, since initialization can rebuild talents too.

In the addon, select the companion and choose **Tank**, **Healer** or **Damage**.
Wait for the server confirmation, then use **Match gear** if wanted. Unsupported
class roles are disabled. Gear matching generates upgrades; it does not strip
old equipment first. Check a new tank's weapon/shield and available abilities.

For dungeon planning, count Vesper as damage/support for now. A dedicated tank
or healer role for his model-controlled character needs separate development
and testing; the ordinary bot addon does not assign him a role.

Full addon notes: [MaNGOSBot guide](C:/Games/AzerothCore/addons/Mangosbot/README.md).

## Starting, pausing and reconnecting

- Start the game server with `C:\Games\AzerothCore\Start Server.cmd`.
  The desktop shortcut also logs Vesper's existing character in. You can run it
  again while the server is running; it keeps an already connected Vesper online.
- In [Presence](http://127.0.0.1:5173/), open **Utilities → Game Player → AzerothCore**.
  Click **Start AzerothCore** if stopped, or **Resume** if it shows **Vesper · Paused**.
  This starts his decisions/conversation. Desktop startup preserves the controller's
  paused/stopped setting and does not call a model. No separate WoW window is needed.
- Use Presence's pause/stop controls for the model loop. Pausing is not a logout.
- Stop the game server with `C:\Games\AzerothCore\Stop Server.cmd` to save characters.

Full setup and behavior notes: [harness README](C:/Games/AzerothCore/harness/README.md).

## Catch-up experience

Installed October 31, 2026. Vesper receives **2× his normal XP** whenever his
level is below Aurenne's. Equal/higher level means normal XP on the next award;
falling behind activates the bonus again. It works outside a party and while
Aurenne is offline, using her saved level. Kill, quest/LFG quest and exploration
XP are covered; ordinary eligibility, group and rested XP rules still apply.
The check is per award, so a large reward can carry him past the matching level.
No model call or manual quest tracking is needed for this bonus.

Settings are in `server/configs/modules/presence_bridge.conf` under
`PresenceBridge.CatchupXP.*`. The current multiplier is 2.0; set `Enable = 0`
to disable it. Once this binary is installed, `.reload config` updates the cached
settings without a server restart.

## Combat attention card — installed; combat behavior playtest pending

Installed November 1 after the approved native build and clean server restart.
The body context links current combat facts to exact target GUIDs and matching
`cast` attempts. Vesper still chooses his action; it adds no fixed
rotation or automatic assist rule.

The native additions describe learned spell roles, partial target applicability,
normal melee range, spell cooldowns, the global cooldown and base resource costs.
Effective cost, exact spell range and full castability remain unknown. Passing
the target checks does not guarantee a cast will succeed; normal execution
validation remains authoritative. The compact card covers supported unit-targeted
spells and self-heals. Self-area and other target modes remain in the full spell
catalog and action space but are outside this compact first version.

The initial combat-card package passed 2,404 offline game-player checks. A synthetic fixture
produced a 1,567-byte card; its combat guide was 3,609 characters versus 15,331
for the generic guide, with all 27 body actions retained. These guide sizes describe
that earlier version, before the follow/combat clarification below. They are
representation checks; useful model choices and response latency still need playtesting.

Live self/ally checks passed for Holy Light (635/639); Judgement (20271) rejected
those targets with result 12. All three nearby rows reported native melee-range
booleans. No hostile unit was present at that deployment check.
The actual Qwen body request retained all 29 exposed active spells and the new melee facts;
the combat card was absent during the healthy, quiet observation, as intended.
Later November 1 requests did contain active lead combat, the exact hostile and
matching attack/cast choices before Vesper chose follow. Combat information was
already reaching him; this did not establish the desired interpretation or action.
Settings, full MCP access/actions and the hard Moon/taming guards are preserved.

### Follow/combat interpretation correction — installed; behavior playtest pending

A small Python-only update is installed to highlight the lead's current
life state, combat and actual outgoing actions before choosing follow. `follow`
tracks the friendly lead; it does not join their attack. `attack` selects the
hostile, pursues it and starts normal autoattack, so a separate move into melee
is not required first.

This keeps the decision with Vesper: assisting, another useful action, closing
distance, following a retreat or respecting a tame can each fit the current
situation. It adds no automatic assist, dispatch veto or forced replan. The
update passed 2,427 offline checks and was deployed without a game-server restart;
saved settings were preserved and the Full controller resumed.

The actual Qwen body request at 20:04:54 UTC on November 1 (sequence 466) contained
the new lead facts: Aurenne was alive, out of combat and at 202/202 health. This
verifies that the facts reached a real model request. Corrected choices during
a fresh fight, informed following/retreat and reliable assistance still need playtesting.

## Models and attention

The body is back on local **Qwen3.5-4B Q4_K_XL** (`qwen3.5-4b-action`); the social
lane uses **GPT-6 Luna** (`gpt-6-luna`). Both use reasoning `none`, with Qwen
thinking disabled. This is the November 1 cost choice; dated decisions and tests
below describe the models selected at those times.

Qwen uses the dedicated `http://127.0.0.1:8082/v1` endpoint. Its launcher remains
available; starting that server does not switch either controller lane's model.
Separate local model servers share the computer's GPU and memory.

1. Start the game server normally.
2. Run [Start Qwen Body.cmd](C:/Games/AzerothCore/Start%20Qwen%20Body.cmd) if Qwen is offline.
3. In Presence's AzerothCore panel, click **Start AzerothCore** when ready to play.
   Starting Qwen alone makes no game decisions or changes to the selected models.

[Stop Qwen Body.cmd](C:/Games/AzerothCore/Stop%20Qwen%20Body.cmd) stops only this owned
Qwen process. Stop/pause the controller first. Qwen runs independently of ChatGPT;
the normal game-server Stop command remains responsible for saving the world.
For runtime status, run `powershell -File scripts/Qwen-Body.ps1 -Action Status`
from the AzerothCore folder. These helpers use fixed local executable/model paths.

The observation interval is one second, not one model call per second. Deliberate
party attacks/casts, danger, Aurenne moving away, a growing distance gap and useful
action results can now wake the body planner. A selected target or being chased
alone does not count as choosing to fight. The body planner decides how to respond; these
signals do not force an attack, heal or follow. Moon/tame guards remain active.
Vesper's saved Full-controller preference now puts routine healing of Aurenne
below fighting or keeping up with her while she is at **50% health or above**.
Below 50%, he can consider a heal; the model still chooses. Safe recovery outside
combat is a separate choice. This preference does not set a self/other-party
healing threshold, and low health never overrides a protected tame or Moon.
The local view explicitly labels Aurenne's current health and maximum. Healing-only
spells restore friendly/self health; they do not replace melee against a hostile.
Explicit model waits have bounded review deadlines; persistent follow keeps
executing locally. Addon protocol messages no longer count as player conversation.
Invalid/empty model output is reported as a failed decision, with bounded retry
backoff, instead of appearing to be an intentional wait.

Derived attention facts carry their source snapshot sequence/time and distinguish
current channels, auto-repeat shots and recent tame attempts. Native model notes
are unverified prior proposals, kept for at most 30 seconds and invalidated when
their underlying party/protection activity changes. The native body prompt now
omits those unverified prior-proposal notes so they cannot keep reviving an old
vendor trip or buff plan. Archives, social context and full MCP access are preserved.
Repeating a note does not renew its age or evidence. A new runner starts with
fresh working notes; the original configuration and complete decision ledger remain.

`controller.accepted_movement_intent` records the latest accepted controller
choice, with `provenance: accepted_controller_intention`, its `source_sequence`,
`request_id`, exact submitted `action` and result state. It explicitly reports
`server_motion_verified: false`: an accepted intention is not proof that movement
is still running. Selecting an NPC can be inspection, not a travel goal. An
accepted follow supersedes the previous NPC trip; returning there should be a
new deliberate choice justified by fresh facts and the agreed party plan. This
does not force following or forbid a useful detour. Consistent behavior across
interruptions still needs playtesting.

The native body lead facts now include an exact optional `follow_action`. For the
observed Aurenne GUID 103 and one-yard setting, it was
`{"type":"follow","target_guid":"103","follow_distance":1}`. The action binds
the current visible, alive, friendly lead; GUIDs must come from fresh observations.
Configured Aurenne remains the lead even if another bot leads the party.
Following a person is different from moving to an old NPC's coordinates.

Her latest recorded message appears beside these facts. Actual matching server
events can establish `server_sender_guid` authorship; otherwise the message keeps
its recorded speaker name without inventing a sender GUID. Known timestamps can
establish order; transcript order alone is labelled as such. The model reads the
request and chooses a response; no keyword rule automatically executes follow.

Quiet party-spacing guidance takes precedence over optional service/buff work
when a gap opens. A nearby stationary follow still allows ordinary upkeep and
carried-item interactions. Completed movement is past execution, not a standing
goal. Fresh position evidence also distinguishes real progress from repeatedly
requesting a destination already reached. Repeated verified already-there results
no longer create their own body wake loop; new chat, danger and other meaningful
changes still receive attention.

Frozen before/after tests changed the same stuck case from a trainer waypoint to
following Aurenne (GUID 103, one yard), and the same reward-page case from
`quest_complete` to `quest_reward` index 0. No game actions ran in those replays.
The live quest reward above then succeeded. Aurenne reported that he was following
and staying with her; fresh 07:41:28 UTC context confirmed persistent follow of
GUID 103 at one yard while she moved, with a local wait preserving that motion.
This single live test passed; long-term oscillation/recovery still needs playtesting.
The installed controller package passed **2,065 offline checks**,
preserved settings and running state, and needed no game-server restart.

Chosen party fights now include bounded target summaries with exact GUIDs and
optional attack actions, including neutral creatures that the party deliberately
engaged. The agreed party role is melee damage/support. Following only positions
him; `attack` chases and begins continuous melee. These are planner choices.
An accepted attack matched to the current living hostile victim now counts as
an ongoing chosen pursuit before melee contact sets `in_combat`. An idle lead
or spacing gap does not by itself make Vesper idle. The planner still chooses
continuation, withdrawal or following, respecting fresh directions and protection.

Identical complete JSON decisions repeated in multiple response messages collapse
to one decision even when whitespace or key order differs. Differing decisions
remain a parse failure. Native responses must be one complete JSON object, with
an optional complete JSON code fence; trailing fragments and duplicate keys are
rejected. Rejection diagnostics record bounded framing/count/error facts, without
provider text or reasoning.

Every native body model now receives the same compact gameplay facts and focused
guidance, whether it uses local inference or an API. This includes current lead
messages, exact actions, actor-side approach choices and omission of old model
proposal notes. Names and object coordinates do not establish a route; already
holding an item is not a reason to revisit its pickup source. Unknown routes
remain unknown. API/local transport and schema handling remain separate.
Critical units, protection, spells and open menus remain available. The current
Qwen body is text-only; observer/Social image policies retain their settings.
Shared grounding changes no provider image support or full MCP context/control permissions.
`wow_model_context` live previews select the body view from the saved configuration;
`last_request` retains the actual dynamic context of a genuine call.

The November 1 update passed **2,279 offline checks** and was installed without a
game-server restart (manifest `c9506d3e1769`). Full control resumed after explicit
hand-back. The reviewed Luna run had 44 rejected outputs among 126 retained
decisions: 36 invalid JSON and 8 incomplete outputs. Their precise cause remains
unproven; the parser correction does not establish why those outputs failed.
Avoiding the old book, continuing chosen fights and accurate bag reporting still
need a fresh behavior playtest. Moon's hard guard remains active.

With identical frozen prompts, 4B, 9B and GPT-6 Luna chose attacks for deliberate
party fights, restraint for taming, and follow for a passing threat. Reasoning was
off and no proposed game action was executed. Warm 4B median was about **3.0
seconds**, with the two attack choices at **2.9–3.0 seconds**; 9B took about
**3.7–4.1 seconds** and Luna about **1.8–2.0 seconds** on those combat/protection
cases. One cold 4B request took about 26 seconds. Hardware contention and output
length affect latency; these few cases establish a useful play-test baseline,
not reliable behavior in every situation. The normal server checks and hard
Moon guard remain active. Refresh Presence, then start the controller for a live test.
