# Vesper command reference

Current AzerothCore setup — October 28, 2026.

For ordinary Playerbots, custom alts, recruitment and addon controls, see
[Bot Guide.md](Bot%20Guide.md) (verified October 30, 2026).

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
| `/p Vesper, check the trainer and see what you can afford.` | Asks him to inspect a nearby trainer's offers and choose training. |
| `/p Vesper, compare that new sword with your current weapon.` | Asks him to inspect carried gear and decide what to equip. |
| `/p Vesper, sell the junk you don't need and repair your gear.` | Asks him to inspect a nearby vendor and choose sales or repairs. |

The follow/wait sentences are examples of ordinary requests, not additional
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
handlers. These are available choices for Luna; they do not automatically sell
junk, spend money, train every spell or equip an item.

Lost transaction replies are marked uncertain. The controller checks the original
request once, without resending the purchase; fresh inventory, money and learned
spells help resolve what happened. Actual partial results remain visible.

These action names are internal planner controls, not slash commands to type:
`vendor_list`, `vendor_buy`, `vendor_sell`, `vendor_buyback`, `vendor_repair`,
`trainer_list`, `train_spell`, `inspect_item`, `equip_item`, `unequip_item`,
and `gossip_select`. Ordinary requests above go through his models and need the
controller unpaused.

## Quest dialogs, rewards and bags

Installed October 31, 2026. Vesper receives current NPC quest dialogs, advertised reward choices and item
comparisons, the normal item-check-to-reward transition, explicit quest status
names and nearby questgiver relations. Luna chooses whether to accept, turn in
or select a reward. A dialog opening is distinct from receiving a reward.

Its internal planner actions are `quest_query`, `quest_accept`, `quest_complete`,
`quest_request_reward` and `quest_reward`. They use observed NPC/quest identities;
reward selection requires the exact advertised zero-based index. These are not
WoW slash commands. Normal quest handlers still check eligibility, objectives,
required items, money and inventory capacity. Querying a quest can trigger the
game's ordinary auto-accept behavior, so it is not a read-only MCP operation.

His view also exposes backpack and bag capacity, separating general-purpose free
space from specialty bags. The existing `equip_item` action can equip a carried
bag or request a particular bag slot. Luna receives guidance to notice usable
bags and compare capacity; the controller does not select equipment for him.

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

## MCP inspection tools

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
They use the existing **Local Context Gateway**, are read-only, and never start
models, resume the controller, move Vesper or make him speak. Refresh that
connection if a tool is missing.

| Tool call | What it shows |
| --- | --- |
| `wow_status({})` | Live character state, controller status, last decision/action and available Vesper-attributed Chronicle entries. |
| `wow_observe({})` | Fresh structured surroundings, quests and recent game events. |
| `wow_model_context({"lane":"body","source":"live_preview"})` | A fresh observation filtered for the body planner. |
| `wow_model_context({"lane":"social","source":"live_preview"})` | A fresh observation filtered for the social planner. |
| `wow_model_context({"lane":"body","source":"last_request"})` | Dynamic context recorded at the latest body-model request attempt. |
| `wow_model_context({"lane":"social","source":"last_request"})` | Dynamic context recorded at the latest social-model request attempt. |
| `wow_model_context({"lane":"body","source":"last_violation"})` | The latest retained Moon attempt/intervention, with its original body request context and action outcome. |

`wow_status` optionally accepts `{"chronicle_limit":3}` (0–10; default 3).
`wow_observe` optionally accepts `{"since":123}`; replace 123 with the event
cursor returned by a previous observation to request newer events.
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

## Local Qwen body and attention

Installed October 31, 2026. The body uses **Qwen3.5-4B**, alias
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
alone does not count as choosing to fight. Luna decides how to respond; these
signals do not force an attack, heal or follow. Moon/tame guards remain active.
Explicit model waits have bounded review deadlines; persistent follow keeps
executing locally. Addon protocol messages no longer count as player conversation.
Invalid/empty model output is reported as a failed decision, with bounded retry
backoff, instead of appearing to be an intentional wait.

The local body receives a smaller structured view and an action-specific JSON
schema. Critical units, protection, spells and open menus remain available;
nearby-unit indexes and explicitly scoped item defaults reduce repetition.
Images remain a social/observer feature and are omitted from this text-only body.
`wow_model_context` live previews select this local view from the saved body
configuration; `last_request` retains the actual dynamic context of a genuine call.

In read-only samples with his configured continuity, Qwen took about **3.4–4.1
seconds** per decision; startup and GPU contention can take longer. The measured
dynamic context was **36.6% smaller**. The 4B model is experimental: it made some
sensible choices and an invalid NPC interaction in synthetic tests. Normal server
validation and the hard Moon guard remain in place. These probes executed no game actions.
