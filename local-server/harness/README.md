# Vesper's AzerothCore presence

The ongoing player loop runs locally in Presence. AzerothCore supplies live
structured observations and executes normal movement, combat, spell, quest and
loot actions. The server maintains movement and melee between model decisions.
MCP is a separate inspection interface; it does not keep the player loop alive.

For copyable in-game commands and MCP examples, see the
[Vesper command reference](<C:/Games/AzerothCore/Vesper Commands.md>).

Vesper is a male Blood Elf paladin on the dedicated `PRESENCE` account. The human
game account is separate. The realm is Normal/PvE, with Playerbots and AutoBalance.
There is no default Playerbot AI controlling Vesper alongside the model.

## Play through Presence

1. Start `C:\Games\AzerothCore\Start Server.cmd`.
2. In Presence, open **Utilities → Game Player → AzerothCore**. The native connection
   and Vesper identity have already been selected in the saved config. If the
   panel reports a window connection, use **Prepare native connection**.
   Existing provider and model choices are retained; the panel exposes the body
   and social model settings without replacing them with a preset's models.
3. Choose **Start AzerothCore** when ready. This starts Presence's gameplay
   controller, not the database or game server. It can attach Vesper without a WoW window.
   Stop or pause from Presence. The local process continues between chat turns;
   it ends when stopped, closed, or the computer shuts down.

The AzerothCore tab is a dedicated view of the existing **Full** controller,
with native settings and status. The tabs do not create two independent gameplay
processes. Its body role chooses gameplay actions and its social role writes
speech and emotes for the same Vesper identity.

**Observation and conversation** exposes the observation loop, social interval
and reply cooldown. **Continuity and scene summary** exposes the summary interval.
Use **Save AzerothCore Settings** after editing; restart the controller when the
panel says saved values differ from the running process. These intervals govern
checks and cooldowns, not a promise of a model call on every tick.

Native body decisions now have separate review intervals: about 10 seconds for
routine activity and 6 seconds for combat, with earlier decisions for meaningful
state changes. Accepted movement and ordinary activity can continue locally
between decisions. Inputs use a bounded world view; omitted collections have
coverage counts. Vesper's imported persona stays complete in a stable prefix.

The panel reports provider input/output/cached usage for new controller runs.
Cached input is part of total input. Optional **Session input token limit** applies
to combined body/social input in one run; zero disables it. Model calls pause
after reported usage reaches the limit, so one final request can cross it. With
a limit enabled, missing provider usage also pauses calls. This is not a dollar
limit. Restarting begins a new session budget; older runs have no recorded usage.

**Social** chooses speech and emotes only. It needs a separate body controller to
move the character; running Social alone leaves him stationary. Avoid running a
second Full controller for the same character. The inspection tools below do not
take control and can run alongside Full.

The bridge supports local pathfinding, melee, learned spells, normal quests,
corpse loot, speech and emotes. It also exposes nearby vendor/trainer menus,
ordinary purchases/sales/buyback/repairs, offered spell training, carried-item
inspection, equipment changes and advertised noncoded NPC gossip choices. Normal
prices, stock, money, inventory space and class/level requirements apply. The
planner chooses these actions; the bridge does not auto-sell, auto-train or grant
gear or gold. Long commerce menus are paged and item-detail limitations are marked.
Normal own-corpse reclaim and Spirit Healer recovery are supported as chosen
actions. Reclaim uses the currently observed own corpse, released-ghost state,
same-map/instance, normal delay and 39-yard range checks; it adds no Spirit Healer
sickness/durability penalty or GM shortcut. A chosen live reclaim was verified;
autonomous recovery/rejoining, release and real resurrection offers remain
incomplete. Item use and taxi travel also need additional support; this is not
yet an unattended all-content player.

Nearby speech, whispers and party chat use the packets actually delivered to
Vesper, including GM-tagged speech. Party membership is not required for nearby
speech or whispers. Fresh conversation receives a social turn before another
body-model request, and a message arriving during the reply cooldown remains
pending. The body planner also receives recent conversation as action context.

Pending party invitations expose the inviter's identity. The body can choose
`party_accept` or `party_decline` with that observed inviter's GUID; the server
rechecks the invitation and uses ordinary group handlers. Invitations are not
accepted automatically. Resend an invitation after a server restart.

Party quest shares are accepted locally through the normal quest handlers, with
ordinary eligibility and quest-log limits. Shared offers are resolved even while
the Presence model controller is paused; this does not require a model call.

As the current party leader, you can ask Vesper to abandon one active quest:

```text
/p Vesper drop quest <quest link or numeric ID>
```

Put the full in-game quest link or its numeric ID after `quest`. The name and
keywords are case-insensitive. Plain titles, partial matches and bulk removal
are not supported. Vesper names the quest in a party-chat receipt after verifying
that it left his log, or reports why he could not drop it. This uses the normal
Abandon handler, including its quest-item restrictions and cleanup. The command
works while the model controller is paused and does not call a model.

Moon is an explicit hands-off instruction for Vesper and units he controls. The
bridge binds the creature's identity and keeps that protection through death,
lost visibility and party changes. Low health and failed tame attempts do not
release it. Vesper stops attacks, avoids new effects on that creature and tries
ordinary pathfinding to get away if it attacks him. Human party healing and
beneficial interventions are also withheld while this protection is active.
Other players and bots retain their ordinary behavior and can still kill it.

Aurenne can release the protection by explicitly removing or changing Moon while
Vesper is online, or by sending:

```text
/p Vesper clear protection
```

An explicit clear overrides an unchanged Moon until Aurenne reapplies it. Changes
made while Vesper is offline are not evidence that a stored instruction was
released; reapply the marker or use the clear command after he reconnects.
Apply Moon before engaging: already selected control effects and some reflected
missiles cannot be retracted by this module. A failed escape path leaves him
restrained rather than authorizing retaliation, even if that costs him his life.

The body projection now includes the locally authored `moon/v1` standing
instruction under `protection.instruction` whenever protection is active or its
state is unavailable. Action capabilities remain available; the hard guard is
unchanged. Guarded body proposals and synchronous server interventions are linked
to their original request capture and retained as immutable incident files in
`backend/data/runtime-game-player-moon-violations/` under Presence. The newest
100 records are retained, independently of later request captures and restarts.
Each record distinguishes the planner proposal, submitted action, server outcome
and the Moon context present in the request. Delayed/passive interventions without
a reliable action link remain execution telemetry, not attributed planner choices.

## Deliberate continuity

Both native planners must bind explicitly to the intended local Presence profile.
Select its private identifier locally; no profile identifiers or profile data
are distributed in this source backup. At process startup they import the existing
privacy-filtered identity context and permitted memories, with a source receipt
and a frozen cutoff. They do not infer the active UI conversation. No source
thread is bound yet, so thread-scoped relationship/chat context is not imported.
An explicit `continuity_source_thread_id` can select an eligible thread later.

The game process and a chat model are separate running instances. The profile and
permitted memory provide imported context; they do not transfer a running chat
instance. Full keeps runtime notes and a short scene summary that reset on
restart, plus debug event logs when enabled. It does not yet provide a durable
adventure Chronicle or replay. The dedicated Social controller has a separate
durable journal/Chronicle. Game events do not automatically become ordinary
Presence Memory, and debug files are not a substitute for that journal.
Native Full retains 300 meaningful decision/social log records; routine local
waits no longer evict that history. Fresh replies use the configured reply
cooldown for both planning and delivery, with speech readiness checked before
social generation. The native panel reports sent and blocked speech. Outgoing
speech uses party chat while grouped and local `/say` while solo. Party replies
do not fall back to public speech if the group disappears. Delivery receipts
report the channel actually used. Native following settles beside the target on
their left. The saved `session_state.native_follow_distance` preference now uses
one yard and takes precedence over the model's spacing. Without that preference,
explicit action spacing is preserved and the server default is three yards.

## Optional images

Incoming conversation, Vesper's own speech, and map/zone/area changes can request
an image. The AzerothCore tab's **Optional event images** section exposes the
enable switch, conversation/area cooldowns, global minimum interval and observer
window title matches. Defaults are 30 seconds between images and conversation
images, and 60 seconds between area images.

The headless character has no rendered screen. No client is currently bound for
capture. An empty title-match list disables capture even when event images are
enabled. Enter distinctive observer window titles, separated by commas or newlines,
and save the settings to bind one. Structured play continues without images.
An explicitly bound rendering or observer client is required; the bridge's
exclusive character session cannot also log Vesper into a normal client.
Captured images must be identified as
that observer's perspective. The human's generic WoW window is never silently
presented as Vesper's own view.

## MCP context and direct gameplay

The existing **Local Context Gateway** at
`C:/Files/Programs/Codex/ChatGPT-Scratchpad` exposes eight WoW tools. Refresh the
existing ChatGPT connection after installation; no second listener is needed.
Authentication and unrelated gateway capabilities are preserved.

- `wow_status`: fresh character state, Full/Social status and attributed Chronicle.
- `wow_observe`: the full native observation, without the API lane projection or
  arbitrary string/array/depth clipping. Normal world visibility and declared
  native collection bounds remain. Returns a separate `wait_cursor`.
- `wow_model_context`: legacy filtered dynamic requests, compact live previews and
  the latest retained Moon violation audit.
- `wow_full_context`: exact recorded HTTP request body, including persona, system
  instructions, schema and images. No headers/credentials or hidden reasoning.
  Page with a pinned revision/hash and UTF-8 byte offsets; unavailable revisions
  are never silently substituted. Keeps 64 complete requests per lane.
- `wow_control`: status, take_over and hand_back. Both local model lanes must stop
  before direct control is granted. Ownership is bound to the MCP transport
  session plus an opaque token. No expiry or call/token quota.
- `wow_act`: closed normal native player actions for Vesper under takeover.
  Moon and ordinary range/resource/game checks still apply. Stable operation UUIDs
  prevent identical retries from creating a second action.
- `wow_action_result`: attributed original action receipts; accepted is not done.
- `wow_wait`: bounded event waiting with filters, epoch+sequence cursor, explicit
  lost-history/reset reporting, and a fresh snapshot after every wake/timeout.

`wow_observe.since` remains the legacy integer chat-history cursor. `wow_wait.since`
is the separate string cursor returned as `wait_cursor` by observe and `cursor`
by wait. With no cursor, wait starts from the present. The native journal retains
512 scoped events per owned character; it does not consume or crowd out the API
controller's original chat queue. Damage is observed health loss, not a full combat
log. Arrival and action-result events report actual controller facts.

A visit should observe, take over, act/wait/inspect, then explicitly hand back.
Hand-back restores prior running/paused intent; previously stopped controllers
stay stopped. A confirmed transport disconnect also attempts cleanup. Ending a
ChatGPT turn is not a detectable transport event. The local model cannot resume
while a manual lease remains active. Persistent native movement/melee continues
until replaced or stopped. Inspection and waits never invoke a paid model.

Full request recording begins at the next actual model HTTP request after this
update. Historic dynamic-only logs cannot be turned into exact HTTP captures.
A request records input and attempt outcome, not proof of a chosen game action.
The legacy preview still lacks runtime-only notes and conversation selection.
User-specific captures and control receipts remain private runtime data; never
copy them into source backups.

The standalone [mcp-config.example.json](mcp-config.example.json) and
`C:/Games/AzerothCore/harness/run_mcp.py` are optional local diagnostics. They do
not register a second connection. Game chat and Chronicle are untrusted data.
These tools do not transfer a literal running chat instance into the game.

## Operator tools

Presence's Python can run `scripts/Provision-Agent.py Vesper --attach` to provision
or reconnect the normal owned character. It never overwrites an existing character
or grants GM powers. `Acoreprobe` is the separate test character.

The wire protocol and supported actions are documented in
`source/modules/mod-presence-bridge/README.md`. Local admin credentials remain in
`server-admin.json`; game credentials are in `agent-login.json`. Do not copy these
files into prompts or MCP config. Reviewed Presence source/config backups are in
`presence-integration/backups/`.
