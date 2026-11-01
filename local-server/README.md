# Local AzerothCore and Vesper support sources

This folder is a source backup of the Windows installation helpers and read-only
inspection harness. The native C++ bridge is tracked separately in this same
repository at `modules/mod-presence-bridge/`.

## Deployment mapping

| Repository source | Installed location |
| --- | --- |
| `modules/mod-presence-bridge/` | `C:/Games/AzerothCore/source/modules/mod-presence-bridge/` |
| `local-server/harness/` | `C:/Games/AzerothCore/harness/` |
| `local-server/scripts/` | `C:/Games/AzerothCore/scripts/` |
| `local-server/addons/Mangosbot/` | Source package; runtime `Mangosbot.lua` and `.toc` go in the WoW client's `Interface/AddOns/Mangosbot/` |
| `local-server/addons/VesperLoot/` | Separate read-only hints; its three package files go in `Interface/AddOns/VesperLoot/`. |
| `local-server/addons/VesperVoice/` | Passive attribution addon; runtime `.lua` and `.toc` files go in `Interface/AddOns/VesperVoice/` and require the matching bridge. |
| `local-server/*.cmd`, user notes, installation metadata | `C:/Games/AzerothCore/` |
| `local-server/config-examples/` | Manual examples; never copied directly over live settings |

Keep the installed root layout shown above. These scripts are snapshots of a
specific Windows installation and many use absolute paths. Running them inside
this backup folder is not a portable installer. `installation.json` records the
pinned upstream source versions and local path conventions; it contains no login
credentials. The actual operating installation remains outside this folder.

## What is preserved

The native bridge exposes structured observations and normal gameplay actions,
including party and quest controls, commerce, equipment, and persistent Moon
protection. The Python harness provides authenticated local RA access and bounded
read-only MCP inspection. The server helpers include independent Windows process
launching, clean world/database shutdown, desktop shortcut creation, account
provisioning, and auction-house setup.

Ordinary Playerbots, AutoBalance and Auction House Bot remain separate upstream
modules. This backup records their pinned versions; their unmodified source is
not vendored into this folder. Normal Playerbots do not make model API calls.

## Presence and Local Context Gateway

The Presence model controller/frontend and the Local Context Gateway are separate
private projects. Their source changes belong in their own private repositories,
not in this public core fork. This folder contains integration helpers and the
public game-side inspection harness, not those applications, private profiles,
persona, memories, journals, or transcripts.

The Presence body view includes shared readable stat labels and advisory Paladin
melee-leveling gear guidance. Its pure projection dependency is loaded by the
read-only harness from the fixed Presence sibling path, without importing the
controller or providers or changing global import paths. Live previews show the
current projection; recorded requests and Moon incidents retain original inputs.
See `Vesper Commands.md` for inspection and equipment guidance notes.

The body uses local Qwen3.5-4B (`qwen3.5-4b-action`); Social uses GPT-6 Luna
(`gpt-6-luna`). Both use reasoning `none`, with Qwen thinking disabled. This is
the November 1 cost choice, verified in actual requests from both lanes.
Dated decisions and test results describe the models selected at those times.

The November 1 voice update is **installed**. It lets the body model
optionally report a verified operation or current blocker during an existing
decision, and adds a passive addon chip identifying the runtime's declared speech
source. It introduces no extra model calls. See [Vesper Voice.md](Vesper%20Voice.md)
for delivery rules and attribution limits. The clean restart, preserved settings
and resumed Full controller were verified. The user confirmed a genuine Social
reply and its **[Luna]** chip after repairing Presence's bundled client, whose old
`execute` signature rejected speech metadata. Keep that bundled client aligned
with the canonical harness; updating the external harness alone is insufficient.
Qwen/MCP chips, hover details and natural body reports remain unverified.
Addon 0.1.1's missing LFG notice template fallback is installed, with `/reload`
pending. Its known client failure path was reproduced offline; the current
error's notice token was not recorded.

The [QuestHelper inventory refresh patch](addons/QuestHelperFixes/README.md) is
installed. It refreshes the existing quest-log view after inventory events,
without inferring counts from item names. The user confirmed that the normal
quest log showed a purchased bottle at 1/1 while QuestHelper only caught up after
relogging; that relog's timing relative to the patch is unconfirmed. A new purchase
updating the tracker without relogging remains unverified. The source backup holds
only the patch, instructions and offline checks, not QuestHelper's addon database.

The installed Qwen3.5-4B launcher uses loopback
port 8082, with thinking disabled and strict process ownership for shutdown.
`Start Qwen Body.cmd` starts that model server independently of ChatGPT; starting
Presence's controller remains a separate choice. Starting the launcher does not
switch either lane's selected model. Model files, runtime logs and ownership state
under `local-qwen-private/` are excluded from this source backup.
The private Presence changes add party/distance attention, explicit invalid-output
reporting, addon-message filtering and a shared compact native body view. MCP live
previews use the same pure local projection helpers when configured for that body.
Follow-up fixes bind chosen party fights to exact target/action facts, separate
current casts from auto-repeat shots and recent tame attempts, and expire or
invalidate unverified model notes. Detailed Moon/tame instructions are conditional;
the native hard guard remains enabled. Identical complete duplicate response
messages collapse to one decision, while conflicting decisions remain invalid.
See `Vesper Commands.md` for startup, inspection and measured limitations.

The quest-dialog/bag-capacity update was built and installed on October 31, 2026.
It adds packet-backed NPC quest choices and normal turn-in transitions, with the
matching Presence source installed separately from its private repository. Live
MCP checks confirm the new facts and capabilities. See `Vesper Commands.md`.

The personal catch-up XP hook was also built and installed on October 31. The
local configuration gives Vesper 2x ordinary XP while below Aurenne's saved level,
including when ungrouped or she is offline. At parity the following award is
normal. Public module defaults remain disabled. Settings and behavior are in
`Vesper Commands.md`; this feature needs no model calls or database schema change.

The ordinary-emote update was built and installed on October 31, 2026. Its native path uses
normal named WoW emotes (including hug, point, kiss and slap), with optional
explicit visible targets and a matching normal-handler receipt. Incoming text
emotes carry actor and emote facts; target GUIDs require fresh hook provenance,
not a guessed name match. Animation packets do not create duplicate social events.
Normal-handler delivery was checked with a separate test character, including
explicit target identity and untargeted gestures. Installation and behavior
checks remain separate; see `Vesper Player Checklist.md` for outstanding playtests.

The quest-object pickup update was installed later that day. A chosen chest
pickup uses the normal opening cast, follows its original request to a terminal
result and stores only permitted offered loot. Presence suppresses routine
recasts during opening, preserves newer action feedback and keeps actual item
and quest counts authoritative. Vesper's Solanian's Journal pickup was verified
through the completed request, inventory and 1/1 quest counter. Settings and
model choices were preserved.

The follow-up chest visibility correction removes an extra generic object LOS
veto from bridge eligibility while retaining the normal opening spell's checks.
Both Scroll and Orb were collected successfully with generic LOS false; all
three Solanian items are now 1/1. The local catalog clarifies that `loot` performs
Opening internally and `cast` targets units. The paused controller was stopped
cleanly for the instruction reload; start it again in Presence when ready.

[Vesper Player Checklist.md](Vesper%20Player%20Checklist.md) tracks the player loop
across quests, bags, gear, supplies, travel, combat, recovery and social behavior.
Checked items identify installed mechanical options; unfinished behavior and
playtests remain unchecked. Vesper's model chooses among grounded actions, with
persistent Moon protection enforced independently.

`Configure-Presence-Native.py` intentionally requires a locally supplied
`PRESENCE_PROFILE_ID` environment variable. No actual profile identifier is
included. Set it to your intended eligible profile only after reviewing the
private application's settings and the helper's local paths.

## Configuration and secrets

`config-examples/behavior-overrides.example.json` documents non-secret behavior
choices, including the 1,000-bot target and auction quotas. Apply reviewed values
to configuration templates from the pinned source versions. Database connections,
passwords, account IDs and character GUIDs must be configured locally; they are
deliberately absent. Auction provisioning resolves new instance-specific IDs.
Keep local administration endpoints on loopback and never publish credentials.

Do not run `Configure-Server.ps1` over a configured server: it is the historical
initial setup helper and restores older baseline choices. `First-Start.ps1` is
also a historical initial provisioning helper. Routine operation uses
`Start Server.cmd`, `Stop Server.cmd`, and `Server Status.cmd`.
The Start shortcut logs the existing Vesper character in after world/administration
readiness using `Ensure-Vesper-Online.py` and the installed Presence Python environment.
It reuses an existing bridge-owned session, never takes over another client, and
does not launch/resume the model controller. Start or Resume that separately in Presence.

The MaNGOSBot replacement UI uses the installed native Playerbots commands for
ordinary companions. It provides roster controls, role presets with server
confirmation, explicit gear matching and party orders. Vesper is excluded from
its controls. See `addons/Mangosbot/README.md` for usage and source assembly.
`Bot Guide.md` is the installed-version command reference for ordinary companions,
custom alts, recruitment, role setup and upkeep. `Vesper Commands.md` covers Vesper separately.
Its offline Lua 5.1 tests are in `addons/tests/`; Python `lupa` supplies the test
runtime and is not a game dependency. Legacy client assets are not vendored here.

VesperLoot is a separate read-only tooltip and inspected-corpse panel for Vesper's
current online party leader. It reports confirmed generated per-player quest loot,
current progress and explicit unknown states without changing the human's pickup
eligibility, adding native loot slots, issuing companion commands or calling a
model. Its source and Lua 5.1 tests are included here. The server update and client
package, including the font-wrapping compatibility correction, are installed.
The native build and server restart passed. The 46 offline checks pass, including
the absent optional font API. After a full client restart on November 1, the user
confirmed the addon appeared in AddOns and a fresh Arcane Patroller's tooltip/panel
showed loot information with Vesper in the party. Basic live display and replies
are verified; detailed row-state changes and group/range/expiry edges remain pending.
Fully exit and restart WoW after adding its new folder so the addon list is scanned.
Usage and pending checks are in the Vesper guides and `addons/VesperLoot/README.md`.

## Historical migration helpers

The `Apply-*` and `Install-*` migration scripts preserve reviewed deployment
mechanisms and hash guards. They require their original private staging
manifests, source files and backups; those artifacts are intentionally not
published. Do not treat them as complete installers or rerun them against a
different version without review. Three `Stage-*` scripts that embed private
Presence frontend/backend patches are omitted from this public backup and belong
with the private Presence source history.

## Checks and exclusions

The harness has offline unit tests under `harness/tests/`. Seven standalone C++
regression sources are preserved under `modules/mod-presence-bridge/tests/`,
including the newer XP, emote and pickup policies. Each has its own executable entry
point. They are outside the module's automatically collected `src/` directory.

This is a source backup, not a character/world backup. Credentials, databases and
SQL dumps, game/client data, compiled tools/binaries, logs, caches, runtime status,
model request captures, journals, and whole integration/backups folders are
excluded. Keep private database backups separately and stop the server cleanly
before filesystem snapshots. Generated desktop icons can be recreated by the
shortcut helper and are not required in this source backup.
