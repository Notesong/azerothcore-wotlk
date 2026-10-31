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
Item use, taxi travel and corpse recovery still need additional support; this is
not yet an unattended all-content player.

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

## MCP inspection

The tools below are installed in the existing **Local Context Gateway** at
`C:/Files/Programs/Codex/ChatGPT-Scratchpad`, version 0.29.0. Its normal gateway
and tunnel have been started using the saved configuration. Refresh the existing
ChatGPT developer-mode app connection to import the added tool schemas. No second
MCP connection is needed. Authentication and existing tools are preserved.

- `wow_status`: live character state, Full/Social runtime status, last decision
  and action result, plus available Social Chronicle entries explicitly attributed
  to Vesper. Full's current session notes do not provide durable adventure replay.
- `wow_observe`: fresh structured state and cursor-based game events.
- `wow_model_context`: inspect the latest recorded Full body/social request
  attempt, or preview a fresh observation through the current lane projection.
  Inputs are `lane: "body" | "social"` and
  `source: "last_request" | "live_preview" | "last_violation"`; defaults are
  body/last_request. `last_violation` supports the body lane and returns the latest
  retained incident with its historical request context, actions and guard outcome.

Raw MCP observations and model inputs are different. Full enriches observations
with controller state and chat direction, then selects up to 12 units for the
body or six for social, with different menus, inventories and history. A recorded
request copies the actual serialized dynamic context at the HTTP boundary;
stable persona/instructions, authentication, image bytes and hidden reasoning
are omitted explicitly. Its timestamp, lane, observation sequence, session
identity, exactness flags and HTTP outcome distinguish it from current state.
A fresh preview uses the same projection function but lacks the running loop's
controller enrichment, notes and conversation selection; it is not a replay.
No old request payloads are reconstructed. Recording begins with the next real
model request after this update; a paused loop can have no recorded request.
Neither inspection mode starts a model or resumes gameplay.

When the saved native body configuration uses a dedicated local action endpoint,
the body preview uses `local_gameplay` projection and reports
`local_gameplay_focus/v1`. It loads the fixed pure attention/focus helpers alongside
gear labels, without importing providers or the controller. The compact view keeps
critical units and uses explicit nearby indexes, scoped defaults and coverage
counters for repeated facts. It does not forward the saved config, credentials or
user instructions. A recorded request still shows its original dynamic input;
changing the current model never rewrites a historical request.

These tools are read-only and never attach, move or speak for the character.
Any later action/override interface should coordinate a pause and handoff with
the local controller first. The current chat's tool list still needs the existing
app connection to be refreshed before it can call these new tools directly.

The standalone [mcp-config.example.json](mcp-config.example.json) and
`C:/Games/AzerothCore/harness/run_mcp.py` entry point are optional local diagnostics.
They are not registered as a second connection. ChatGPT cannot automatically
reach a local stdio process without a configured connector/client bridge.

The module uses the [MCP stdio transport](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports).

## Operator tools

Presence's Python can run `scripts/Provision-Agent.py Vesper --attach` to provision
or reconnect the normal owned character. It never overwrites an existing character
or grants GM powers. `Acoreprobe` is the separate test character.

The wire protocol and supported actions are documented in
`source/modules/mod-presence-bridge/README.md`. Local admin credentials remain in
`server-admin.json`; game credentials are in `agent-login.json`. Do not copy these
files into prompts or MCP config. Reviewed Presence source/config backups are in
`presence-integration/backups/`.
