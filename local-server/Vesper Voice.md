# Vesper voice and source chips

November 1, 2026: **installed**. The matching native bridge, local harness, private
Presence controller and VesperVoice addon were applied as a 17-file update.
The world restarted cleanly; game and administration services are ready. Saved
model settings and controller preferences were preserved. Full resumed with
Vesper online and alive, and MCP control was released. The separate Social-only
controller remains stopped; Full runs both model lanes.

The user confirmed a genuine Social reply and its **[Luna]** chip after the bundled
Presence client repair. Controller delivery counters showed one Social speech
sent and zero blocked. Qwen and MCP chips, hover details, natural body completion
and blocker reports, and human-reply priority still need playtests.

Vesper keeps his ordinary speech. A small gray chip beside his player link shows
the declared source: **Qwen**, **Luna** or **MCP**. Hovering shows the lane,
provider and configured model ID. Other model families use a Body or Social chip.
The runtime supplies these facts; the addon does not guess from his wording.
A requested model name is not proof of the weights behind a server alias.

MCP shows **MCP** with model identity unavailable. The game gateway cannot reliably
identify the model making a ChatGPT tool call. Missing or mismatched metadata leaves
normal chat unlabeled. Standardized emotes are outside this first version.

## Body speech and factual reports

The November 2 update lets Qwen optionally speak in an existing gameplay decision.
He can explain what he intends to try, ask a question, mention a difficulty or
comment on the world. Ordinary top-level `say` needs no special evidence tag.
It is his choice; internal `state_update` notes are not automatically spoken.
There is no additional model request or paid Social call for this speech.

Ordinary body lines have a 20-second spacing limit and a 30-second queued lifetime.
They wait for fresh safe delivery, yield to a pending human reply, and retain
duplicate suppression. These limits apply to body speech without changing saved
Social settings. Speech does not replace the chosen gameplay action. Autonomous
standard emotes remain in the Social lane.

Typed factual reports remain available for verified sales, stored loot, equipment,
learning, repairs and quest rewards, as well as blockers and trainer-page progress.
Their evidence tags help bind a statement to an actual operation; they are no
longer the only route for body speech. An opened trainer menu is inspection, not
learning. A page containing no trainable spells says nothing about later pages;
the next-page action and incomplete coverage are explicit in both model lanes.
The original typed-report cooldown and expiry remain 60 and 180 seconds.

Luna can see delivered body lines in the shared transcript with source metadata
and timestamps. Those lines are Vesper's statements, not verified mechanical
facts: a plan, accepted action or spoken claim does not prove completion. Fresh
native observations and actual receipts remain authoritative. Vesper's own speech
does not become a new human message that summons another Social reply.

Body output cannot repeat a recent human line verbatim as Vesper's own speech.
Internal tags and source labels are not spoken. Uncertain delivery is resolved
with its original request identity rather than resent under a new one.

This ten-file Presence update is installed. **2,971 offline checks passed**;
the controller resumed with its saved settings and the world server stayed up.
A frozen local Qwen 4B replay chose the trainer's next page and wrote,
“Let's see what's on the next page.” It used 3,453 input tokens in about six
seconds, with thinking off and no proposed game action executed.
Subsequent live receipts confirmed delivered Qwen party speech at 02:26, 02:27,
02:31, 02:32 and 02:34 UTC on November 3 (November 2 local time), with Body/local
`qwen3.5-4b-action` provenance. This verifies actual ordinary body speech.
The user's November 2 screenshot confirmed the Qwen chip in party chat. Hover
details and consistent trainer follow-through remain separate checks.

## Quest confirmations

“Quest accepted: …” and “Quest turned in: …” are automatic controller notices
backed by native success events. They use ordinary party chat without a model
chip and cost no model call. They do not depend on Qwen or Luna deciding to speak.
Opening menus, attempted actions and abandoned quests do not trigger them.
Recent actual acceptance/reward facts also reach both model lanes with their
timestamps, separately from speech history and the current quest log.

## Learned abilities

The November 1 follow-up is **installed**. Three Presence files were updated without
a world restart. Saved settings were preserved, Full resumed unpaused with fresh
ticks and no reported error, and MCP control was released. The separate Social-only
controller remains stopped because Full supplies both lanes.

Only completed native training receipts establish that an ability was learned.
The actual learned IDs are joined to unambiguous observed spell-catalog names or
a direct trainer row with that same spell ID. A trainer wrapper's name cannot
stand in for a different learned spell. Unknown names stay unknown; ranks are not
guessed. Earlier live receipts verified **Hammer of Justice (853)**, **Purify
(1152)** and **Parry (3127)**; Parry's direct trainer row supplied its name because
passive abilities are absent from the active spell catalog.

The body can choose a brief, natural report during an existing decision, using
a supplied name or complete spell link in ordinary party/local speech. This adds
no model call or automatic announcement. Quiet-state checks, cooldowns and human
reply priority still apply. Link cleanup preserves whole tokens within the
180-character and 255-byte chat budgets, using safe plain text when needed.
For example, a supplied Hammer of Justice link has this form:

`|cff71d5ff|Hspell:853|h[Hammer of Justice]|h|r`

Both model lanes receive a bounded recent-learning view: at most four receipts
and eight abilities, retained for 30 minutes in memory and bound to the character.
It covers receipts observed by the running controller, with no historical
backfill or complete spellbook claim. MCP permissions are unchanged.

The final offline suite passed **2,498 checks**, with **26 independent feature
checks** also passing. A new in-game training report, its clickable link and
Social's use of the shared learning history still need a playtest. The earlier
receipts above do not establish those new behaviors.

## Addon and deployment

VesperVoice is passive: it sends no chat, gameplay commands or model calls. A
separate short server addon message identifies the following normal chat packet
by sender, channel and exact text fingerprint. The normal player link and message
remain usable. Metadata expires after five seconds and cannot label a later line.
See the [addon README](addons/VesperVoice/README.md) for the wire format and checks.

Keep Presence's bundled `tools.presence_acore.Client` in step with the canonical
harness client. Updating only the external harness left the Full runner using an
older `execute` signature, which rejected `speech_provenance` before speech reached
the server. The bundled-client correction is installed; its offline checks cover
default client selection and speech metadata serialization.

Addon 0.1.1 is installed; a client `/reload` is pending for its missing LFG notice
template fallback. The exact client channel-notice branch reproduced
`format(nil)` when both `CHAT_NOT_IN_LFG_NOTICE` variants were absent. The current
error's notice token was not recorded, so this verifies that known failure path
without establishing it as the cause of every channel-notice error. Existing
localized templates and the normal notice renderer are preserved.

After installation, fully exit and reopen WoW to discover the new addon folder.
Later Lua changes can use `/reload`. The matching native update needs a clean
server restart. Offline checks and the observed Luna chip do not verify the other
source chips or natural body reporting behavior.
