# Vesper Voice

WoW 3.3.5 addon source. It places a muted `[Qwen]`, `[Luna]`, or `[MCP]` chip beside Vesper's normal author link, outside his spoken message. Other declared models use a Body or Social chip. Hover or click the chip for the lane, provider, and requested model ID. A model ID is the configured request name, not proof of the weights behind an alias. MCP reports its model identity as unavailable.

The addon is passive. It sends no chat, addon requests, commands, gameplay actions, or model calls. Normal message text, sender link, line ID, colors, access IDs, filters, and the sender's existing context menu are preserved. Standardized emotes and unsupported channels remain unlabeled.

This source has not been installed into the live client. Installation consists of copying the `VesperVoice` folder into `Interface/AddOns`, then fully exiting and reopening WoW so the new addon is discovered. Later source updates can use `/reload`. The matching server metadata update must be present first. No metadata means normal unlabeled chat.

## Attribution contract

The server sends a private addon whisper immediately **before** each normal speech packet is enqueued for the same human recipient. The side channel contains no utterance text:

```text
prefix: VESPERVOICE
body: V1|nonce|sequence|5000|senderGUID|chatType|byteLength|adler32|origin|provider|model
```

- The entire prefix, tab separator, and body are at most 255 bytes.
- `nonce`: exactly 16 lowercase hexadecimal digits; fresh per speech action.
- `sequence`: canonical decimal integer 1–4294967295, increasing during this UI session.
- `5000`: fixed metadata lifetime in milliseconds, measured from receipt.
- `senderGUID`: 16 lowercase hexadecimal digits without `0x`; never converted to a Lua number.
- `chatType`: `1` SAY, `2` PARTY, or `51` PARTY_LEADER.
- `byteLength`: exact UTF-8 byte length, 1–255.
- `adler32`: eight lowercase hex digits, over the exact post-validation speech bytes.
- `origin`: `body`, `social`, or `mcp`. Unknown is never labeled.
- Provider IDs are at most 24 bytes and model IDs at most 96, using only ASCII letters, digits, `.`, `_`, `:`, `/`, and `-`. A body/social label needs both IDs. MCP requires `-|-`, explicitly meaning unknown.

Metadata is accepted only as a whisper from Vesper on the local realm. The normal event must independently identify Vesper and provide the exact matching GUID, channel, checksum, byte length, and a valid chat line ID. Party membership is unnecessary for SAY; actual normal-event sender identity is required.

Records expire after five seconds and retained caches are bounded. Duplicate metadata cannot create additional labels; conflicting duplicates poison their cached record. Identical ambiguous pending lines, stale records, missing fields, malformed identifiers, and late metadata remain unlabeled. A normal event may be rendered in several chat frames using its same line ID, but a later line cannot reuse that attribution. Sequence replay is rejected until the explicit `PLAYER_ENTERING_WORLD` lifecycle reset. Leaving the world clears pending attribution and render contexts and ignores metadata during loading. Entering the world clears the high-water sequence so a restarted server can start from a low sequence without reusing old pending labels. Already-rendered tooltip details can remain available.

The checksum is a correlation check, not a cryptographic signature. Sender identity comes from the game's authenticated addon and normal-chat event fields. The addon does not infer origin from phrasing or an unverified model-written prefix.

## Rendering and compatibility

The addon wraps `ChatFrame_MessageEventHandler` and each chat frame's `AddMessage` method. A render context exists only while the original handler handles a verified event. The chip is inserted only when the formatted output still includes the matching author link before the original message. Existing hyperlink callbacks receive all ordinary links unchanged. The optional chip uses its own cached tooltip hyperlink.

No chat event is delayed, suppressed, replayed, or re-emitted by this addon. If another chat addon changes the message or removes the author link, the optional chip can be omitted. The spoken line still follows that addon's normal rendering. Tooltips retain the most recent 128 labeled lines; older chip details expire without inventing a replacement source.

The implementation was checked against the 3.3.5 client [ChatFrame.lua](https://github.com/wowgaming/3.3.5-interface-files/blob/main/ChatFrame.lua) and [FloatingChatFrame.lua](https://github.com/wowgaming/3.3.5-interface-files/blob/main/FloatingChatFrame.lua), including all 12 normal chat-event arguments and the original `AddMessage` parameters.

## Offline checks

`../tests/test_vesper_voice.lua` runs under Lua 5.1 and checks attribution, UTF-8 checksums, sender/GUID/channel binding, TTL, replay, ambiguity, duplicate conflicts, bounded caches, intact rendering parameters, normal filters, multiple chat frames, and hyperlink behavior.

Use a Python environment containing `lupa.lua51`, or pass the directory containing an isolated `lupa` package through `--runtime-path` or `VESPERVOICE_LUA51_PATH`. This dependency is not part of the addon. From this addon folder, run:

```powershell
python ../tests/run_lua51.py --runtime-path C:/path/to/isolated/lua-runtime
```
