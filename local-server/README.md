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

The October 31 local-body update adds a dedicated Qwen3.5-4B launcher on loopback
port 8082, with thinking disabled and strict process ownership for shutdown.
`Start Qwen Body.cmd` starts that model server independently of ChatGPT; starting
Presence's controller remains a separate choice. It leaves other helper endpoints
and the social model unchanged. Model files, runtime logs and ownership state
under `local-qwen-private/` are excluded from this source backup.
The private Presence changes add party/distance attention, explicit invalid-output
reporting, addon-message filtering and a compact local body view/schema. MCP live
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

## Historical migration helpers

The `Apply-*` and `Install-*` migration scripts preserve reviewed deployment
mechanisms and hash guards. They require their original private staging
manifests, source files and backups; those artifacts are intentionally not
published. Do not treat them as complete installers or rerun them against a
different version without review. Three `Stage-*` scripts that embed private
Presence frontend/backend patches are omitted from this public backup and belong
with the private Presence source history.

## Checks and exclusions

The harness has offline unit tests under `harness/tests/`. Four standalone C++
regression sources are archived under `modules/mod-presence-bridge/tests/`;
their test bodies are unchanged and only their include paths are relative now.
They are outside the module's automatically collected `src/` directory.

This is a source backup, not a character/world backup. Credentials, databases and
SQL dumps, game/client data, compiled tools/binaries, logs, caches, runtime status,
model request captures, journals, and whole integration/backups folders are
excluded. Keep private database backups separately and stop the server cleanly
before filesystem snapshots. Generated desktop icons can be recreated by the
shortcut helper and are not required in this source backup.
