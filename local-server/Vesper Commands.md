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

The local body view now lists current corpse/chest loot candidates with their
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
bag or request a particular bag slot. Luna receives guidance to notice usable
bags and compare capacity; the controller does not select equipment for him.

The local body view now links carried eligible gear to its exact observed slot,
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
death/corpse/resurrection recovery. Ordinary game-object interaction and known
unit-targeted spell casting already exist, but do not cover every quest mechanic.

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
| `wow_control({"action":"status"})` | Current manual-control ownership and hand-back status. |
| `wow_control({"action":"take_over","operation_id":"<new UUID>"})` | Stop the local controllers and receive a session-bound control token for Vesper. |
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

Hand back before ending the visit. The server cannot infer that a ChatGPT turn
ended. A known MCP transport disconnect also attempts hand-back; silence alone
does not release control. `resume_previous:false` leaves prior controllers stopped.
The Windows gateway restart shortcut can force-close its process, bypassing that
cleanup. Hand back first. If a crash strands ownership, run this locally in
PowerShell to release it while keeping the model runners stopped:

```powershell
$env:PYTHONPATH='C:\Games\AzerothCore\harness'
& 'C:\Files\Programs\Codex\Presence\working\backend\.venv\Scripts\python.exe' -B -m presence_acore.mcp_control --recover --leave-stopped
```

Use `--resume-previous` instead only when you want the saved running/paused intent
restored. This recovery command is local operator tooling, not an MCP action.
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

## Local Qwen body and attention

Installed October 31, 2026. The body uses **Qwen3.5-4B Q4_K_XL**, alias
`qwen3.5-4b-action`, at `http://127.0.0.1:8082/v1`, with thinking disabled.
This dedicated endpoint leaves the main/helper model endpoints available for
other helpers. The social provider/model is unchanged and still uses no reasoning.
Separate ports allow separate model servers; they still share the computer's GPU and memory.

1. Start the game server normally.
2. Run [Start Qwen Body.cmd](C:/Games/AzerothCore/Start%20Qwen%20Body.cmd) if Qwen is offline.
3. In Presence's AzerothCore panel, click **Start AzerothCore** when ready to play.
   The controller was left stopped after installation; starting Qwen alone makes no game decisions.

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
their underlying party/protection activity changes. The local body prompt now
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

The local lead facts now include an exact optional `follow_action`. For the
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
Identical complete JSON decisions repeated in multiple response messages collapse
to one decision; differing complete decisions remain an explicit parse failure.

The local body receives a smaller structured view and an action-specific JSON
schema. Critical units, protection, spells and open menus remain available;
nearby-unit indexes and explicitly scoped item defaults reduce repetition.
Images remain a social/observer feature and are omitted from this text-only body.
`wow_model_context` live previews select this local view from the saved body
configuration; `last_request` retains the actual dynamic context of a genuine call.

With identical frozen prompts, 4B, 9B and GPT-6 Luna chose attacks for deliberate
party fights, restraint for taming, and follow for a passing threat. Reasoning was
off and no proposed game action was executed. Warm 4B median was about **3.0
seconds**, with the two attack choices at **2.9–3.0 seconds**; 9B took about
**3.7–4.1 seconds** and Luna about **1.8–2.0 seconds** on those combat/protection
cases. One cold 4B request took about 26 seconds. Hardware contention and output
length affect latency; these few cases establish a useful play-test baseline,
not reliable behavior in every situation. The normal server checks and hard
Moon guard remain active. Refresh Presence, then start the controller for a live test.
