local addon = assert(arg[1], "addon path required")
dofile(addon .. "/VesperVoiceCore.lua")
local C = VesperVoiceCore
local now, total = 0, 0
local GUID = "0000000000000066"
local function eq(actual, expected)
  assert(actual == expected, tostring(actual) .. " ~= " .. tostring(expected))
end
local function test(name, fn)
  now = 0
  local ok, err = pcall(fn)
  assert(ok, name .. ": " .. tostring(err))
  total = total + 1
end
local function state() return C.New("Azeroth Core", function() return now end) end
local function wire(seq, text, lane, provider, model, chat, guid, nonce)
  return table.concat({ "V1", nonce or string.format("%016x", seq), tostring(seq), "5000", guid or GUID,
    tostring(chat or 2), tostring(#text), C.Fingerprint(text), lane or "social",
    provider or "openai", model or "gpt-6-luna" }, "|")
end
local function receive(s, body, sender, channel)
  return s:Receive("VESPERVOICE", body, channel or "WHISPER", sender or "Vesper")
end
local function match(s, text, line, event, guid)
  return s:Match(event or "CHAT_MSG_PARTY", guid or ("0x" .. GUID), text, line or 1)
end

test("UTF-8 byte checksum agrees with Adler-32", function()
  eq(C.Fingerprint("hello"), "062c0215")
  eq(C.Fingerprint("<3 ✨"), "077302b6")
  eq(C.Guid("0xF130000000000066"), "f130000000000066")
  eq(C.Guid("0x0000000000000000"), nil)
end)

test("authenticates sender, local realm, channel and exact GUID", function()
  local s = state()
  eq(receive(s, wire(1, "Hello"), "Vesper-AzerothCore"), true)
  eq(match(s, "Hello").lane, "social")
  for _, sender in ipairs({ "Aurenne", "Vesper-OtherRealm", "Vesper ", "Other-Vesper" }) do
    eq(receive(state(), wire(2, "Hello"), sender), false)
  end
  eq(receive(state(), wire(2, "Hello"), "Vesper", "PARTY"), false)
  eq(match(s, "Hello", 2, nil, "0x0000000000000067"), nil)
end)

test("MCP never invents a model and unknown lanes stay unlabeled", function()
  local s = state()
  eq(receive(s, wire(1, "Hi", "mcp", "-", "-")), true)
  eq(C.Label(match(s, "Hi")), "MCP")
  eq(receive(state(), wire(1, "Hi", "mcp", "openai", "gpt-6-luna")), false)
  eq(receive(state(), wire(1, "Hi", "unknown", "-", "-")), false)
  eq(receive(state(), wire(1, "Hi", "body", "-", "-")), false)
end)

test("party leader channel is exact and labels follow the declared model rather than lane", function()
  local s = state()
  receive(s, wire(1, "Lead", "body", "openai", "gpt-6-luna", 51))
  eq(match(s, "Lead", 1, "CHAT_MSG_PARTY"), nil)
  eq(C.Label(match(s, "Lead", 2, "CHAT_MSG_PARTY_LEADER")), "Luna")
  local q = state()
  receive(q, wire(1, "Social", "social", "local", "qwen3.5-4b-action"))
  eq(C.Label(match(q, "Social")), "Qwen")
end)

test("malformed metadata cannot acquire attribution", function()
  local base = wire(1, "Hello")
  local cases = {
    base:gsub("^V1", "V2"), base .. "|extra", base:gsub("|5000|", "|6000|"),
    base:gsub("|1|5000|", "|01|5000|"), base:gsub("|1|5000|", "|0|5000|"),
    base:gsub("|1|5000|", "|4294967296|5000|"), base:gsub("|2|5|", "|3|5|"),
    base:gsub("gpt%-6%-luna", "gpt 6 luna"), base:gsub("gpt%-6%-luna", "bad|model"),
    base:gsub("gpt%-6%-luna", string.rep("a", 97)), base:gsub("openai", string.rep("a", 25)),
    base:gsub("|5|", "|0|"), string.rep("a", 256),
  }
  for _, body in ipairs(cases) do eq(receive(state(), body), false) end
  eq(state():Receive("OTHER", base, "WHISPER", "Vesper"), false)
end)

test("exact byte length, checksum, channel and line ID are mandatory", function()
  local s = state()
  receive(s, wire(1, "Hello"))
  eq(match(s, "Hello!"), nil)
  eq(match(s, "Hello", 2), nil) -- A mismatch cannot leave a reusable tag behind.
  local checksum = state()
  receive(checksum, wire(1, "Hello"))
  eq(match(checksum, "HELLO"), nil)
  local other = state()
  receive(other, wire(1, "Hello"))
  eq(match(other, "Hello", 1, "CHAT_MSG_SAY"), nil)
  eq(match(other, "Hello", 2).seq, 1)
  local noID = state()
  receive(noID, wire(1, "Hello"))
  eq(noID:Match("CHAT_MSG_PARTY", GUID, "Hello", nil), nil)
  eq(match(noID, "Hello", 3), nil)
  local noGUID = state()
  receive(noGUID, wire(1, "Hello"))
  eq(noGUID:Match("CHAT_MSG_PARTY", nil, "Hello", 1), nil)
  eq(match(noGUID, "Hello", 3), nil)
  local wrongGUID = state()
  receive(wrongGUID, wire(1, "Hello"))
  eq(match(wrongGUID, "Hello", 1, nil, "0x0000000000000067"), nil)
  eq(match(wrongGUID, "Hello", 2), nil)
end)

test("metadata expires at the TTL boundary and replay stays rejected", function()
  local s = state()
  receive(s, wire(1, "Hello"))
  now = 5
  eq(match(s, "Hello"), nil)
  eq(receive(s, wire(1, "Hello")), false)
  now = 11
  eq(receive(s, wire(2, "Hello")), true)
  assert(match(s, "Hello", 2))
end)

test("same normal line can be rendered in several frames but not a later line", function()
  local s = state()
  receive(s, wire(1, "Hello"))
  local first = match(s, "Hello", 100)
  assert(first)
  eq(match(s, "Hello", 100), first)
  eq(match(s, "Hello", 101), nil)
end)

test("duplicate and conflicting metadata fail conservatively", function()
  local s = state()
  local body = wire(1, "Hello")
  receive(s, body)
  local ok, reason = receive(s, body)
  eq(ok, false); eq(reason, "duplicate")
  assert(match(s, "Hello", 1))
  ok, reason = receive(s, (body:gsub("gpt%-6%-luna", "qwen3.5-4b-action")))
  eq(reason, "conflict")
  eq(match(s, "Hello", 1), nil)
end)

test("identical pending speech is ambiguous and late metadata is never reused", function()
  local s = state()
  receive(s, wire(1, "Hello")); receive(s, wire(2, "Hello"))
  eq(match(s, "Hello", 1), nil)
  eq(match(s, "Hello", 2), nil)
  local late = state()
  eq(match(late, "Hello", 5), nil)
  local ok, reason = receive(late, wire(1, "Hello"))
  eq(ok, false); eq(reason, "late")
  eq(match(late, "Hello", 6), nil)
end)

test("retained state is bounded and old high-water sequences cannot be replayed", function()
  local s = state()
  for i = 1, 200 do receive(s, wire(i, "Message " .. i)) end
  local count = 0
  for _ in pairs(s.records) do count = count + 1 end
  assert(count <= C.MAX_RECORDS)
  eq(receive(s, wire(1, "Message 1")), false)
  assert(match(s, "Message 200", 200) == nil) -- Several unconsumed candidates are ambiguous.
end)

test("a lower server sequence is accepted only after explicit world lifecycle reset", function()
  local s = state()
  receive(s, wire(100, "Before reconnect"))
  assert(match(s, "Before reconnect", 10))
  s:ClearPending()
  eq(s.highest, 100)
  local fresh = wire(1, "After reconnect", "social", "openai", "gpt-6-luna", 2, GUID, "abcdef0123456789")
  eq(receive(s, fresh), false)
  s:Reset()
  eq(s.highest, 0)
  eq(receive(s, fresh), true)
  eq(match(s, "After reconnect", 10).seq, 1)
  eq(match(s, "Before reconnect", 10), nil)
end)

local function UI(normalHandler)
  now = 0
  local function frame()
    local f = { scripts = {}, messages = {} }
    function f:GetScript(name) return self.scripts[name] end
    function f:SetScript(name, fn) self.scripts[name] = fn end
    function f:RegisterEvent() end
    function f:AddMessage(...) self.messages[#self.messages + 1] = { n = select("#", ...), ... }; return "added" end
    return f
  end
  local observed = {}
  GetRealmName = function() return "Azeroth Core" end
  GetTime = function() return now end
  CreateFrame = function() local f = frame(); observed[#observed + 1] = f; return f end
  NUM_CHAT_WINDOWS, CHAT_FRAMES = 2, { "ChatFrame1", "ChatFrame2" }
  ChatFrame1, ChatFrame2 = frame(), frame()
  local delegated = { enter = 0, leave = 0, click = 0 }
  ChatFrame1:SetScript("OnHyperlinkClick", function() delegated.click = delegated.click + 1 end)
  ChatFrame1:SetScript("OnHyperlinkEnter", function() delegated.enter = delegated.enter + 1 end)
  ChatFrame1:SetScript("OnHyperlinkLeave", function() delegated.leave = delegated.leave + 1 end)
  local raw, filtered = {}, false
  ChatFrame_MessageEventHandler = normalHandler or function(f, event, ...)
    local a = { n = select("#", ...), ... }
    raw[#raw + 1] = { event = event, args = a }
    if filtered then return true end
    local body = "|cff123456[Party] |Hplayer:" .. a[2] .. ":" .. a[11] .. ":PARTY|h[Vesper]|h: " .. a[1]
    f:AddMessage(body, .2, .3, .4, 7, false, 55, 66)
    return true, "normal-return"
  end
  GameTooltip = { lines = {} }
  function GameTooltip:SetOwner() end
  function GameTooltip:ClearLines() self.lines = {} end
  function GameTooltip:AddLine(text) self.lines[#self.lines + 1] = text end
  function GameTooltip:Show() self.shown = true end
  function GameTooltip:Hide() self.shown = false end
  hooksecurefunc = function() end
  dofile(addon .. "/VesperVoice.lua")
  VesperVoice.Install()
  local eventFrame = observed[#observed]
  eventFrame:GetScript("OnEvent")(eventFrame, "PLAYER_ENTERING_WORLD")
  return VesperVoice, raw, delegated, function(value) filtered = value end, eventFrame
end

local function say(frame, text, line, author, event, guid)
  return ChatFrame_MessageEventHandler(frame, event or "CHAT_MSG_PARTY", text, author or "Vesper", "Orcish",
    "", "", "", 0, 0, "", 0, line or 1, guid or ("0x" .. GUID))
end

test("rendering adds one chip outside speech and preserves player links, raw args and colors", function()
  local a, raw = UI()
  receive(a.state, wire(1, "Hello, love. 50% ✨", "body", "local", "qwen3.5-4b-action"))
  local one, two = say(ChatFrame1, "Hello, love. 50% ✨", 42)
  eq(one, true); eq(two, "normal-return")
  eq(raw[1].args[1], "Hello, love. 50% ✨")
  eq(raw[1].args[2], "Vesper"); eq(raw[1].args[11], 42); eq(raw[1].args[12], "0x" .. GUID)
  local output = ChatFrame1.messages[1]
  assert(output[1]:find("|h[Qwen]|h|r |cff123456|Hplayer:Vesper:42:PARTY|h[Vesper]|h: Hello, love. 50% ✨", 1, true))
  eq(output[2], .2); eq(output[3], .3); eq(output[4], .4)
  eq(output[5], 7); eq(output[6], false); eq(output[7], 55); eq(output[8], 66)
  say(ChatFrame2, "Hello, love. 50% ✨", 42)
  assert(ChatFrame2.messages[1][1]:find("[Qwen]", 1, true))
  say(ChatFrame1, "Hello, love. 50% ✨", 43)
  assert(not ChatFrame1.messages[2][1]:find("vespervoice:", 1, true))
end)

test("unknown, late, different-author and unsupported channel lines stay untouched", function()
  local a = UI()
  say(ChatFrame1, "No metadata", 1)
  assert(not ChatFrame1.messages[1][1]:find("vespervoice:", 1, true))
  receive(a.state, wire(1, "Hello"))
  say(ChatFrame1, "Hello", 2, "Aurenne")
  assert(not ChatFrame1.messages[2][1]:find("vespervoice:", 1, true))
  say(ChatFrame1, "Hello", 3, "Vesper", "CHAT_MSG_EMOTE")
  assert(not ChatFrame1.messages[3][1]:find("vespervoice:", 1, true))
end)

test("normal filters still run and suppressed lines never get extra output", function()
  local a, raw, _, filter = UI()
  filter(true)
  receive(a.state, wire(1, "Filtered"))
  say(ChatFrame1, "Filtered", 10)
  eq(#raw, 1); eq(#ChatFrame1.messages, 0)
  eq(a.contexts[ChatFrame1], nil)
  filter(false)
  ChatFrame1:AddMessage("Unrelated output", .5, .5, .5)
  eq(ChatFrame1.messages[1][1], "Unrelated output")
end)

test("renderer changes do not attach a chip when original speech is no longer present", function()
  local a = UI()
  ChatFrame_MessageEventHandler = function(f)
    return f:AddMessage("[Party] |Hplayer:Vesper:8:PARTY|h[Vesper]|h: replacement", .3, .4, .5)
  end
  a.installed = false
  a.Install()
  receive(a.state, wire(1, "Original"))
  say(ChatFrame1, "Original", 8)
  eq(ChatFrame1.messages[1][1], "[Party] |Hplayer:Vesper:8:PARTY|h[Vesper]|h: replacement")
end)

test("a player link inside speech cannot be mistaken for a removed author header", function()
  local a = UI()
  local text = "Look: |Hplayer:Vesper:8:PARTY|h[Vesper]|h"
  receive(a.state, wire(1, text))
  -- A formatter that removes the actual author header should lose the optional chip.
  ChatFrame_MessageEventHandler = function(f, _, message) return f:AddMessage(message, 1, 1, 1) end
  a.installed = false
  a.Install()
  say(ChatFrame1, text, 8)
  eq(ChatFrame1.messages[1][1], text)
end)

test("hover identifies exact source while normal hyperlink handlers remain unchanged", function()
  local a, _, delegated = UI()
  receive(a.state, wire(1, "Hi", "social", "openai", "gpt-6-luna"))
  say(ChatFrame1, "Hi", 9)
  local link = ChatFrame1.messages[1][1]:match("|H(vespervoice:[0-9a-f]+:%d+)|h")
  ChatFrame1:GetScript("OnHyperlinkEnter")(ChatFrame1, link)
  eq(GameTooltip.lines[2], "Lane: social")
  eq(GameTooltip.lines[3], "Provider: openai")
  eq(GameTooltip.lines[4], "Requested model: gpt-6-luna")
  ChatFrame1:GetScript("OnHyperlinkLeave")(ChatFrame1, link)
  eq(GameTooltip.shown, false)
  ChatFrame1:GetScript("OnHyperlinkClick")(ChatFrame1, "player:Vesper:9:PARTY", "[Vesper]", "RightButton")
  ChatFrame1:GetScript("OnHyperlinkEnter")(ChatFrame1, "item:123")
  ChatFrame1:GetScript("OnHyperlinkLeave")(ChatFrame1, "item:123")
  eq(delegated.click, 1); eq(delegated.enter, 1); eq(delegated.leave, 1)
  receive(a.state, wire(2, "Direct", "mcp", "-", "-"))
  say(ChatFrame1, "Direct", 10)
  link = ChatFrame1.messages[2][1]:match("|H(vespervoice:[0-9a-f]+:%d+)|h")
  ChatFrame1:GetScript("OnHyperlinkClick")(ChatFrame1, link)
  eq(GameTooltip.lines[3], "Direct MCP control; model identity unavailable.")
end)

test("normal handler failures clean the scoped render context", function()
  UI()
  ChatFrame_MessageEventHandler = function() error("normal failure") end
  VesperVoice.installed = false
  VesperVoice.Install()
  receive(VesperVoice.state, wire(1, "Hi"))
  local ok = pcall(say, ChatFrame1, "Hi", 1)
  eq(ok, false)
  eq(VesperVoice.contexts[ChatFrame1], nil)
end)

test("leaving world clears context and entering world safely permits a restarted server", function()
  local a, _, _, _, eventFrame = UI()
  local event = eventFrame:GetScript("OnEvent")
  receive(a.state, wire(100, "Before reconnect"))
  say(ChatFrame1, "Before reconnect", 1)
  local oldTips = a.tips
  a.contexts[ChatFrame1] = { used = false }
  event(eventFrame, "PLAYER_LEAVING_WORLD")
  eq(a.inWorld, false); eq(next(a.contexts), nil); eq(next(a.state.records), nil)
  event(eventFrame, "CHAT_MSG_ADDON", "VESPERVOICE", wire(101, "During loading"), "WHISPER", "Vesper")
  eq(next(a.state.records), nil)
  say(ChatFrame1, "During loading", 2)
  assert(not ChatFrame1.messages[2][1]:find("vespervoice:", 1, true))
  event(eventFrame, "PLAYER_ENTERING_WORLD")
  eq(a.inWorld, true); eq(a.state.highest, 0); eq(a.tips, oldTips)
  receive(a.state, wire(1, "After reconnect", "body", "openai", "gpt-6-luna", 2, GUID, "abcdef0123456789"))
  say(ChatFrame1, "After reconnect", 1)
  assert(ChatFrame1.messages[3][1]:find("[Luna]", 1, true))
end)

test("missing LFG notice template is supplied without changing normal event arguments", function()
  local old, oldBN = CHAT_NOT_IN_LFG_NOTICE, CHAT_NOT_IN_LFG_NOTICE_BN
  CHAT_NOT_IN_LFG_NOTICE, CHAT_NOT_IN_LFG_NOTICE_BN = nil, nil
  local seen
  local function normal(frame, event, ...)
    local a = { n = select("#", ...), ... }
    seen = { event = event, args = a }
    -- Same template lookup and argument order as 3.3.5 ChatFrame.lua:2792-2802.
    local template = _G["CHAT_" .. a[1] .. "_NOTICE_BN"] or _G["CHAT_" .. a[1] .. "_NOTICE"]
    frame:AddMessage(string.format(template, a[8], a[4]), .2, .3, .4, 8, false, 55, 66)
    return true, "normal-notice"
  end
  local a = UI(normal)
  local one, two = ChatFrame_MessageEventHandler(ChatFrame1, "CHAT_MSG_CHANNEL_NOTICE",
    "NOT_IN_LFG", "", "", "5. LookingForGroup", "", "", 0, 5, "LookingForGroup", 0, 99, "")
  eq(one, true); eq(two, "normal-notice")
  eq(seen.event, "CHAT_MSG_CHANNEL_NOTICE"); eq(seen.args.n, 12)
  eq(seen.args[1], "NOT_IN_LFG"); eq(seen.args[4], "5. LookingForGroup")
  eq(seen.args[8], 5); eq(seen.args[11], 99); eq(seen.args[12], "")
  eq(ChatFrame1.messages[1][1], "|Hchannel:CHANNEL:5|h[5. LookingForGroup]|h " ..
    "You must be queued in Looking for Group before joining this channel.")
  eq(ChatFrame1.messages[1][7], 55); eq(ChatFrame1.messages[1][8], 66)
  eq(a.contexts[ChatFrame1], nil)
  CHAT_NOT_IN_LFG_NOTICE, CHAT_NOT_IN_LFG_NOTICE_BN = old, oldBN
end)

test("existing localized LFG notice templates are never replaced", function()
  local old, oldBN = CHAT_NOT_IN_LFG_NOTICE, CHAT_NOT_IN_LFG_NOTICE_BN
  CHAT_NOT_IN_LFG_NOTICE, CHAT_NOT_IN_LFG_NOTICE_BN = "localized fallback", nil
  UI()
  eq(CHAT_NOT_IN_LFG_NOTICE, "localized fallback"); eq(CHAT_NOT_IN_LFG_NOTICE_BN, nil)
  CHAT_NOT_IN_LFG_NOTICE, CHAT_NOT_IN_LFG_NOTICE_BN = nil, "localized BN"
  UI()
  eq(CHAT_NOT_IN_LFG_NOTICE, nil); eq(CHAT_NOT_IN_LFG_NOTICE_BN, "localized BN")
  CHAT_NOT_IN_LFG_NOTICE, CHAT_NOT_IN_LFG_NOTICE_BN = old, oldBN
end)

print("VesperVoice Lua 5.1: " .. total .. " checks passed")
