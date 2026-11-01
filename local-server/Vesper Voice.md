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

## Occasional body reports

The body can optionally include a short natural report in an existing gameplay
decision when fresh typed facts support it. There is no additional model request.
Useful examples are a measured item sale, stored loot, an equipped item, a learned
spell, a verified quest reward or a current nontransient action failure.
An accepted action, an opened menu and a proposed next step do not prove completion.
One operation does not prove that an entire request is finished.

Reports wait for a later fresh, settled, quiet observation. Danger and active
gameplay take priority, and a pending human reply wins. Only one line can be sent
in a tick. Reports share the ordinary speech cooldown, have an additional
60-second report cooldown, and expire after 180 seconds. Recent repeated evidence
is deduplicated; resolved blockers and superseded equipment reports are discarded.
The model still decides whether the evidence matters enough to mention.

Conversation, personality replies and emotes remain in the Social lane. Internal
evidence tags, state notes and source labels are not spoken. Body output cannot
use a recent human line verbatim as Vesper's own report. Speech with an uncertain
transport result is resolved using its original request identity rather than
resent under a new one.

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
