# Presence bridge

This local module exposes structured observations and ordinary gameplay actions over
AzerothCore's authenticated console transport. Configure RA on `127.0.0.1`, not a
public interface. The bridge does not create an additional network listener.

Configure `PresenceBridge.Account` and `PresenceBridge.AllowedCharacters` in
`presence_bridge.conf`. Defaults are `PRESENCE` and `Vesper,Acoreprobe`. Actions
require a headless session owned by this module on that dedicated account. Observing
another online character is read-only. Existing online characters cannot be taken
over. Nothing automatically creates or attaches a character at startup.

## Protected creatures

Moon means an explicit, persistent instruction for Vesper to leave that creature
alone and evade it if attacked. Protection affects only Vesper and units he
controls. Other players, their pets, playerbots and other bridge characters remain
free to attack it. There is no low-health rescue override: Vesper also withholds
beneficial intervention on the human party while this instruction remains active.
His reflection mechanics are disabled so they cannot retaliate against the target.

Mark the creature before combat. A bound GUID survives visibility loss, deaths,
corpse runs, disconnects and party changes. Only the original human protector's
explicit marker removal/reassignment, or `/p Vesper clear protection`, releases
it. An unchanged Moon is ignored after the clear command until the protector
explicitly reapplies it. If a marker was changed while Vesper was offline, reapply
it after attaching him. The first existing Moon can be adopted when Aurenne leads
his party; later transitions use normal post-update marker receipts with her GUID.

`PresenceBridge.ProtectedCharacter` defaults to `Vesper`. Binding transitions are
appended to `PresenceBridge.ProtectionFile`, default
`presence-bridge-protection.jsonl` relative to the worldserver working directory.
The journal is capped at 2 MiB and replayed on startup. Read/write/corruption errors
stop this character's risky actions instead of silently losing protection. Keep
the journal when updating the server. Database creatures use map, instance, spawn
ID and entry to resolve changed runtime GUIDs after restart; a recovered summoned
creature without a stable spawn ID remains unavailable until explicitly cleared
or remarked by its protector.

New direct and area spell targets are filtered before their effects, and ordinary
attributable melee, periodic, passive and spell damage is suppressed. Existing
attacks/casts are stopped; controlled pets become passive until release. Escape
uses only a complete checked navigation path away from the attacker, preferably
toward a living nearby protector, and otherwise stops without attacking. Model
movement/attack/stop orders cannot cancel an active escape.

This cannot retract control effects or missiles already selected/reflected before
the mark, or safely attribute a pre-existing periodic effect whose caster no
longer exists. Mark before starting a tame. It does not add world-wide immunity,
erase threat, teleport, heal or resurrect anyone.

Observations always include `protection`, independently of the nearby-unit limit:
the binding/protector, current avoidance mode, persistence and creature identity
facts, withheld assistance/reflection policy, and bounded observed tame attempts.
Unit facts distinguish selection, outgoing attack victim and current spells;
`semantic_tame` follows the spell's tame-creature effect rather than its name.

Guard callbacks now report bounded `moon_guard_intervention` diagnostics without
changing their existing enforcement. A veto during the synchronous bridge action
is returned under `result.guard_interventions` (or `error.guard_interventions`),
with the request ID, observed sequence and current protected GUID. This includes
accepted spells whose implicit protected targets were removed. At most 16 callback
receipts accompany one action; dropped counts and a truncation flag are explicit.
The callback count is not a count of independent planner decisions.

Damage ticks, ongoing casts and passive effects outside that synchronous action
have `attribution: unattributed_execution`. They are not attributed to the latest
planner decision. Fresh observations expose a separate `guard_interventions`
ring (64 receipts), `guard_event_cursor`, `guard_intervention_total` and
`guard_intervention_suppressed`. Repeated passive callbacks for the same effect
are sampled at most once every two seconds, with a bounded 128-key cache.
These diagnostics do not enter the normal chat/event attention stream. They
remain in memory until the world server restarts; Presence separately archives
matched planner incidents with their actual captured request context.

## Wire protocol

Send one console command:

```text
presence request <standard base64 of UTF-8 JSON>
```

The command returns exactly one protocol line, apart from the RA transport's own
prompt:

```text
PRESENCE_JSON:{"v":1,"id":"example","op":"observe","character":"Vesper","ok":true,"result":{...}}
```

Requests use `{v:1,id:string,op:string,character:string}`. `id` is required and
limited to 128 bytes. Errors have `ok:false` and `error:{code,message}`.
Mutating requests are deduplicated by ID in a bounded 512-entry cache; a duplicate
ID with changed bytes is rejected. Retry the exact same encoded request after a
transport failure. The cache is in memory and resets on server restart.

- `capabilities`: `result.protocol`, `result.operations`, `result.actions` describe
  the implemented interface. Character is optional for this operation.
- `observe`: live self state, visible nearby units and objects, quest log,
  inventory, active known spells, cooldowns, gossip options, available quest menu,
  current party roster, a received pending party invitation, and recent events.
  `party_invite` is null unless a normal invitation is pending, otherwise it names
  the exact `inviter` and `inviter_guid` along with the party leader. `party` is
  null when ungrouped; its roster contains at most 40 member names, GUIDs and
  online flags. Optional `radius` is clamped to 1-90 yards. `since` or
  `after_event_id` requests events after a cursor. Snapshots carry monotonic
  `sequence` and UTC `timestamp`; all GUIDs are unsigned decimal strings.
- `attach`: load an existing owned character through normal login queries.
  Returns `result.status:"accepted"` while loading, then becomes `completed` or
  `failed` in the result cache. Login is cancelled if still pending after 90
  seconds. No random bot manager or default AI is registered. An ordinary client
  cannot log into a character while the bridge owns it; detach before doing so.
- `detach`: save and log out this module's character. Pending creation/login must
  finish first. Detaching an already detached character is harmless.
- `action`: includes `action:{type,...}`. Supported types are listed below.
- `action_result`: includes `request_id` naming an earlier mutating request;
  `result.response` is that request's latest complete response envelope.

`create` is an operator provisioning operation, deliberately omitted from model
capabilities. It creates a normal level-one character through
`WorldSession::HandleCharCreateOpcode`, with ordinary name/race/class/account
checks. Fields are `account`, `race`, `class`, `gender`, and optional `skin`,
`face`, `hair_style`, `hair_color`, `facial_hair`. For Vesper the agreed choices
are Blood Elf male Paladin (`race:10,class:2,gender:0`). Defaults (Human Priest)
are for the disposable `Acoreprobe` only; always pass explicit race and class
when provisioning a real character. The dedicated game account must already
exist. Creation never overwrites a character, and does not automatically attach.

## Actions and completion

### Carried items, shops and trainers

These actions use the normal session handlers, prices, requirements, money and
inventory rules. There are no free items, gold grants, automatic purchases,
automatic selling, automatic upgrades or automatic training. Every transaction
is one planner choice. Existing Moon enforcement and action audit callbacks stay
active for spells or passive effects triggered during these actions.

- `vendor_list`: nearby visible vendor `target_guid`, optional zero-based `page`.
  Opens the normal vendor list and captures its actual outgoing packet. Each
  observation page has at most 24 offers. A gossip-selected virtual vendor keeps
  its catalog when browsing another page or refreshing after purchase.
- `vendor_buy`: `target_guid`, advertised one-based `vendor_slot`, `item_id`, and
  `count` from 1 through 255. **Count is bundles**; `buy_count` in an offer is the
  units per bundle, and `price` is the displayed copper price per bundle. The
  normal handler rechecks current stock, money, turn-ins, currencies and conditions.
  Success requires the purchased carried-item count to increase by the expected
  units. Results report `bundle_count`, actual `item_count` and money deltas.
- `vendor_sell`: `target_guid`, carried `item_guid`, and explicit positive `count`
  in **individual units**. No zero-count sell-all shortcut is accepted. Only the
  chosen stack is sent to the normal seller; actual removed units and money are
  reported. Selling is not restricted by quality or quest relevance beyond the
  ordinary game rules; these facts are observations for the planner to interpret.
- `vendor_buyback`: `target_guid`, the advertised sold `item_guid`, and absolute
  `buyback_slot` from 74 through 85. The slot/GUID must still match. The normal
  handler restores the full sold stack; verification uses carried-item counts,
  the removed buyback offer and actual price paid, including stack merging.
- `vendor_repair`: nearby repairer's `target_guid`, optional carried `item_guid`.
  Omitting the item requests normal paid repair-all using personal money, never
  guild funds. Results report actual repaired-item count, partial completion and
  money spent. Display/inspection never invokes a free repair to estimate cost.
- `trainer_list`: nearby trainer `target_guid`, optional zero-based `page`.
  Eligibility, costs and prerequisites come from the actual normal trainer-list
  packet, including script adjustments. A page contains at most 24 offers.
- `train_spell`: `target_guid` and advertised `spell_id`. The ordinary trainer
  handler applies class/level/skill/prerequisite and money checks. Completion
  requires newly learned spells and the selected offer's expected learned spells
  to be present; a successful packet alone is insufficient. Results retain actual
  new spell IDs and money changes even when training cannot be verified.
- `equip_item`: carried `item_guid`, optional `equipment_slot` from 0 through 22.
  Omit the slot for the normal automatic equipment/bag slot selection. The normal
  handler handles swaps, two-handed/offhand rules, binding, bags and requirements.
- `unequip_item`: equipped `item_guid`; the normal handler finds carried storage.
  Full bags, non-empty equipped bags and ordinary restrictions can reject it.
- `inspect_item`: carried `item_guid`; read-only. The current rich item state is
  returned in the next observation's `inspected_item` until the item leaves carried
  storage or another inspection replaces it.
- `gossip_select`: nearby creature `target_guid`, current `menu_id`, advertised
  `option_id`. The sender, menu and non-coded option must match the current gossip
  frame. Normal scripts, costs and handlers execute. `accepted` means submitted,
  not proof that an arbitrary script's intended outcome completed.

Vendor purchase/sale/buyback and trainer purchase require a menu advertised by
that same NPC within the last two minutes, plus current range and line of sight.
Bank, mail and buyback GUIDs cannot be used as carried items. Buyback lookup is
available only through its dedicated verb. Handler rejection or unverified state
uses `status: failed`, retaining actual state/money deltas; no rollback is faked.

Observations expose friendly NPC `services`, `is_vendor`, `is_trainer` and
`can_repair`; `vendor`, `trainer`, `buyback`, `equipment`, `inventory_index` and
`inspected_item`; and bound gossip IDs. The inventory index has at most 200 carried
items; all 23 equipped/bag slots are separately represented. Trainer caches cap at
1024 rows, with total and cached counts reported. Item stats identify their source
as the item template. Random property/suffix IDs and names, enchantment descriptions
and raw effects are retained, but final modified/combat stat totals are not resolved.
Base vendor sale prices are marked estimates; the actual sale receipt is authoritative.

### Movement, combat, quests and conversation

- `say`: `text`, 1-255 UTF-8 bytes without line breaks. Optional `channel` is
  `say` (the default) or `party`. Party chat requires a current normal group and
  uses the normal session chat handler, including language, mute/flood/script
  checks and party/subgroup routing. A lost group returns `not_grouped`; it never
  falls back to public speech. Unknown channels return `invalid_channel`.
  Successful results report the actual `channel`. Party completion requires the
  normal outgoing party-chat receipt; handler rejection returns `chat_not_sent`.
  Sending literal `/p` in `text` does not select a channel.
- `emote`: `text`, 1-255 UTF-8 bytes without line breaks; normal public text emote.
- `party_accept`, `party_decline`: required `inviter_guid`, copied from the
  currently observed `party_invite`. These use the normal group accept/decline
  handlers and verify the result. A missing invitation or a different pending
  inviter is rejected, so an old decision cannot join a replacement inviter's
  party. The bridge never automatically accepts an invite or forces membership.
- `move_to`: `x,y,z` on the current map, within 80 yards. Optional `map_id` must
  match the current map. Requires a complete
  normal navigation path. There is no teleport or direct-line fallback. Returns
  `accepted`; the cached result becomes `completed` on arrival or `failed` on
  timeout, death, replacement or cancellation. Maximum wait is 45 seconds.
- `stop`: stop movement, melee and casting. Completes immediately.
- `follow`: `target_guid`, optional `distance` (1-20 yards). Requires a friendly
  visible target. Defaults to 3 yards beside the target on their left, using normal follow
  movement at the character's own speed. Returns `accepted` for a persistent
  movement intent, with the chosen `follow_distance` and `follow_angle` in radians.
- `target`: `target_guid`; `"0"` clears the selected target.
- `attack`: `target_guid`; normal attack checks apply. `accepted` acknowledges
  starting melee attack mode, not a hit or kill. A mobile character faces and
  chases the target through the normal movement generator; pending point movement
  is superseded. There is no teleport or damage shortcut.
- `cast`: `spell_id`, optional `target_guid` (defaults to current target, or self
  if no target is selected). Only active learned unit-targeted spells are allowed.
  Normal casting checks, power costs, range, cooldowns and global cooldown apply.
  `accepted` acknowledges the cast start, not a completed or successful effect.
- `interact`: nearby visible NPC/game-object `target_guid`; normal interaction
  range and line of sight apply. Returns `accepted`; inspect subsequent dialogue
  and events for the result.
- `loot`: visible dead creature `target_guid` within normal interaction distance
  and line of sight. The character must have normal loot eligibility. Only slots
  advertised as lootable/owned in the ordinary loot response are attempted through
  normal autostore handlers; money and release use their ordinary handlers too.
  Returns actual acquired `items`, `copper`, `skipped_slots` and `partial`.
  Reserved rolls and other players' loot are not overridden. Full bags can produce
  `loot_not_stored` or a partial result.
- `query_quest`: explicit `target_guid`, `quest_id` from the current quest menu.
  Opens the normal details window. This uses the ordinary query handler, which
  can accept a quest carrying the game's auto-accept flag; it is not a guaranteed
  read-only operation. Hidden quest rewards remain hidden.
- `accept_quest`: explicit `target_guid`, `quest_id` matching the current details
  window. Uses the normal accept handler and verifies newly active quest-log
  membership. Tracking quests that immediately complete through the ordinary core
  path are reported separately. An already active quest is not a new acceptance.
- `complete_quest`: explicit `target_guid`, `quest_id` from the current quest menu.
  Opens the normal turn-in window, either `request_items` or `offer_reward`.
  It does not force completion, hand over items or choose a reward.
- `request_reward`: explicit `target_guid`, `quest_id` matching the current
  `request_items` window. Advances through the ordinary request-reward handler.
  That handler can mark the quest complete when its normal objectives permit it;
  the bridge verifies that an actual matching reward offer was received.
- `reward_quest`: explicit `target_guid`, `quest_id` and `reward_index` matching the
  current `offer_reward` window. Reward indices are zero-based and must be chosen
  explicitly, including `0` when there are no choices. The advertised item/count
  must still match that reward slot. The normal handler checks requirements,
  inventory and costs; completion requires a fresh normal quest-reward receipt,
  including for repeatable quests. Results report actual carried-item and money
  changes, rather than assuming displayed rewards were received unchanged.

The core can automatically reward a tracking quest while accepting or advancing
its normal dialog, without sending a public reward packet. These results use a
synchronous, action/character/quest-bound `OnPlayerCompleteQuest` callback, which
this core fires after `RewardQuest` finishes. `quest_reward_hook` and
`tracking_quest_rewarded` report that outcome separately from `reward_receipt`;
repeated tracking rewards do not rely on a sticky previously-rewarded flag.

Quest actions require the same visible, normally interactable NPC or questgiver
game object within interaction range and line of sight. Interact first to obtain
its current menu. Menus expire after two minutes; another dialog, a normal close,
or a vendor/trainer window supersedes them. Verified synchronous quest operations
return `completed` for the requested window/action transition; `phase_after`,
`accepted_quest` and `reward_receipt` distinguish opening a window from accepting
or receiving rewards. A failed verification retains actual state and money facts.

`quest_dialog` exposes the current actual client window: bound `target_guid` and
`quest_id`, `phase`, availability/staleness, revision, clipped text, costs and
requirements, and at most six choice/four fixed rewards with rich item facts.
`rewards_hidden` and `rewards_visible` distinguish hidden or not-yet-offered
rewards from a quest with no reward. Displayed money/XP come from the actual
packet, including script adjustments; hidden values are never backfilled from
templates. `available_quests` contains at most 64 current advertised rows, each
bound to its source with live status and start/turn-in relation. Visible questgiver
units/objects expose their normal quest status and related IDs from Vesper's own
quest log; the bridge does not discover questgivers elsewhere in the world.
Logged objectives include their known creature/game-object entry, type and text.

`bag_capacity` reports the backpack and all four equipped bag positions, including
empty bag slots, with total/used/free space. `general_free_slots` excludes specialty
bags, whose free slots cannot hold arbitrary rewards. Item facts identify bags,
their container size, bag-family restrictions and maximum stack size. Equipping
a carried bag uses the existing `equip_item`, optionally naming slot 19 through 22;
the normal inventory handler applies bag replacement and storage restrictions.

Snapshots are bounded: 64 nearby units, 64 objects, 200 inventory entries, 256
active non-passive spells, and 64 events per read from a 128-event ring. Bounds
are reported in each snapshot. Events currently include received chat, party invitations, gossip,
quest dialogue, cast failures, spell launches and level-ups. `event_cursor` is the
last returned event, so another read drains a larger backlog without skipping it.
Some dialogue/packet events are notifications, not full decoded client UI state.
Both ordinary and GM-formatted received chat packets are decoded, including
say, whisper and party messages. Only packets addressed to the bridge-owned
session are captured; this does not add a global chat listener or widen normal
chat visibility. `gm_message` records the packet format, not the speaker's
current in-game GM mode.
Carried-item use, corpse recovery, coded gossip, auctions and player trade are not
implemented and are not advertised as capabilities. There are no automatic
GM grants, resurrection, equipment changes, leveling or combat rotations.

## Ordinary emotes

Named gestures use `{"type":"emote","emote":"wave","target_guid":"..."}`.
Supported names are bow, cheer, clap, dance, hug, kiss, laugh, nod, point, salute,
shrug, slap, smile, thank and wave. Omitting the target, or supplying zero, means
untargeted; selection does not supply a default. The normal text-emote handler
applies the gesture, and completion requires its actual delivered self receipt.
Custom `{"type":"emote","text":"..."}` prose remains a separate action form
and cannot include a target GUID.

Only normal text-emote packets delivered to an owned session become events.
Animation packets do not duplicate them. Events expose sender, gesture, direction
and explicit target facts. The wire packet has only a target name, so a narrow
normal-handler hook provides bounded, short-lived GUID provenance. It emits no
event itself and never derives identity from names. Unknown or stale provenance
stays unknown. A directed social gesture can therefore identify its recipient
without adding a global emote listener or widening ordinary client visibility.

## Chest and quest-object pickup

`loot(target_guid)` supports eligible creature corpses and ordinary chest game
objects, including quest books. Chest pickup uses the character's normal known
opening spell and the normal game-object spell target. It applies ordinary lock,
range, line-of-sight, cast, quest and storage checks. It does not force an unlock
or expose unopened loot-table contents. `interact` on a chest directs the caller
to `loot` rather than accepting a no-op.

A cast-time opening returns `accepted` under its original request UUID. Bounded
`pending_loot` facts identify the source, spell and remaining timeout. The world
update waits for the matching normal loot-window receipt, stores only offered
permitted slots through the normal handler and verifies actual inventory gains.
`action_result` resolves the same UUID to stored items or an honest failure.
Explicit movement/combat actions can supersede opening; merely selecting a unit
does not. A failed cast, lost source, death or timeout does not count as pickup.

## Personal catch-up XP

The optional catch-up hook multiplies one configured character's ordinary XP
award while their level is below a configured reference character's level. It is
disabled by default. Set `PresenceBridge.CatchupXP.Enable = 1`, `Character`,
`LeadCharacter` and `Multiplier` in `presence_bridge.conf`; the example pair is
Vesper/Aurenne at 2.0. A config reload updates the cached settings.

Kill, quest/LFG quest, exploration and battleground XP use the existing player
hook. The receiver's exact cached GUID and account must match. Reference levels
come from CharacterCache, including offline characters; no group membership,
model call or SQL query is required. At equal/higher level the next award is
normal, and falling behind enables catch-up again. Each award is atomic, so a
large reward can carry the receiver past the matching level. Ordinary eligibility,
group/global/module rates, rested and recruit-a-friend rules remain in effect.
Missing identities/levels or unsafe amounts leave the ordinary award unchanged.
This does not grant levels or XP directly or change any other character's rate.

## Lifetime and threads

The module owns its socketless `WorldSession` instances, pumps their asynchronous
database callbacks, acknowledges normal teleports, and saves/logs them out during
world shutdown. It stores GUIDs in events, not long-lived unit pointers.

RA uses `World::QueueCliCommand`. `World::Update` calls `MapMgr::Update` before
`ProcessCliCommands`; `MapMgr::Update` joins map workers with `m_updater.wait()`
before returning. Module world updates follow CLI processing. Consequently bridge
requests and owned-session callbacks execute at that world-thread safe point.
Packet hooks may run on map workers; their small event queues use a mutex, and
only registered bridge sessions are recorded. GPT/network requests never block a
world or map update.

The module builds through the ordinary AzerothCore static module discovery and
uses Boost.JSON from the existing Boost installation (its implementation is
compiled once inside this translation unit). No external service or API key is
needed for the bridge itself.
