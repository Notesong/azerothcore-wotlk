-- WoW 3.3.5. Normal utterance, author link, filters and AddMessage arguments remain intact.
local C = VesperVoiceCore
local A = { contexts = {}, hooks = {}, tips = {}, tipOrder = {}, inWorld = false }
VesperVoice = A
local state = C.New(GetRealmName() or "", GetTime)
A.state = state

local function Pack(...) return { n = select("#", ...), ... } end
local function Unpack(t) return unpack(t, 1, t.n) end

local function ActiveColor(text)
  local active, i = "", 1
  while i <= #text do
    local code = text:sub(i, i + 1)
    if code == "||" then i = i + 2
    elseif code == "|c" and text:sub(i + 2, i + 9):match("^%x%x%x%x%x%x%x%x$") then
      active, i = text:sub(i, i + 9), i + 10
    elseif code == "|r" then active, i = "", i + 2
    else i = i + 1 end
  end
  return active
end

local function Badge(record)
  if record.badge then return record.badge end
  local key = record.nonce .. ":" .. record.seq
  A.tips[key] = { lane = record.lane, provider = record.provider, model = record.model }
  A.tipOrder[#A.tipOrder + 1] = key
  if #A.tipOrder > 128 then A.tips[table.remove(A.tipOrder, 1)] = nil end
  record.badge = "|cff8494a3|Hvespervoice:" .. key .. "|h[" .. C.Label(record) .. "]|h|r"
  return record.badge
end

local function Details(frame, link)
  local key = type(link) == "string" and #link <= 64 and link:match("^vespervoice:([0-9a-f]+:%d+)$")
  if not key then return false end
  local tip = A.tips[key]
  if tip and GameTooltip then
    GameTooltip:SetOwner(frame, "ANCHOR_CURSOR")
    GameTooltip:ClearLines()
    GameTooltip:AddLine("Vesper voice", 0.65, 0.73, 0.8)
    GameTooltip:AddLine("Lane: " .. tip.lane, 1, 1, 1)
    if tip.lane == "mcp" then
      GameTooltip:AddLine("Direct MCP control; model identity unavailable.", 1, 1, 1, true)
    else
      GameTooltip:AddLine("Provider: " .. tip.provider, 1, 1, 1, true)
      GameTooltip:AddLine("Requested model: " .. tip.model, 1, 1, 1, true)
    end
    GameTooltip:Show()
  elseif GameTooltip then
    GameTooltip:Hide()
  end
  return true -- Do not send our private link type to Blizzard's item-link parser.
end

function A.HookFrame(frame)
  if not frame or A.hooks[frame] or type(frame.AddMessage) ~= "function" then return end
  A.hooks[frame] = true
  local add = frame.AddMessage
  frame.AddMessage = function(self, text, ...)
    local context = A.contexts[self]
    if context and not context.used and type(text) == "string" then
      local speech = text:find(context.text, 1, true)
      local start = text:find(context.link, 1, true)
      if start and speech and start < speech then
        local prefix = text:sub(1, start - 1)
        text = prefix .. context.badge .. " " .. ActiveColor(prefix) .. text:sub(start)
        context.used = true
      end
    end
    return add(self, text, ...)
  end
  if type(frame.GetScript) ~= "function" or type(frame.SetScript) ~= "function" then return end
  local enter, leave, click = frame:GetScript("OnHyperlinkEnter"), frame:GetScript("OnHyperlinkLeave"), frame:GetScript("OnHyperlinkClick")
  frame:SetScript("OnHyperlinkEnter", function(self, link, ...)
    if Details(self, link) then return end
    if enter then return enter(self, link, ...) end
  end)
  frame:SetScript("OnHyperlinkLeave", function(self, link, ...)
    if type(link) == "string" and #link <= 64 and link:match("^vespervoice:[0-9a-f]+:%d+$") then
      if GameTooltip then GameTooltip:Hide() end
      return
    end
    if leave then return leave(self, link, ...) end
  end)
  frame:SetScript("OnHyperlinkClick", function(self, link, ...)
    if Details(self, link) then return end
    if click then return click(self, link, ...) end
  end)
end

function A.HookFrames()
  for i = 1, (NUM_CHAT_WINDOWS or 10) do A.HookFrame(_G["ChatFrame" .. i]) end
  if type(CHAT_FRAMES) == "table" then
    for _, name in ipairs(CHAT_FRAMES) do A.HookFrame(_G[name]) end
  end
end

function A.Install()
  if A.installed or type(ChatFrame_MessageEventHandler) ~= "function" then return end
  A.installed = true
  state.realm = GetRealmName() or ""
  A.HookFrames()
  local original = ChatFrame_MessageEventHandler
  ChatFrame_MessageEventHandler = function(frame, event, ...)
    if not A.inWorld or (event ~= "CHAT_MSG_SAY" and event ~= "CHAT_MSG_PARTY" and event ~= "CHAT_MSG_PARTY_LEADER") then
      return original(frame, event, ...)
    end
    local args = Pack(...)
    if not C.Sender(args[2], GetRealmName() or "") then return original(frame, event, ...) end
    local record = state:Match(event, args[12], args[1], args[11])
    if not record then return original(frame, event, ...) end
    A.HookFrame(frame)
    local previous = A.contexts[frame]
    A.contexts[frame] = { text = args[1], link = "|Hplayer:" .. args[2] .. ":" .. tostring(args[11]) .. ":",
      badge = Badge(record) }
    local result = Pack(pcall(original, frame, event, Unpack(args)))
    A.contexts[frame] = previous
    if not result[1] then error(result[2], 0) end
    return unpack(result, 2, result.n)
  end
  if type(hooksecurefunc) == "function" then
    if type(FCF_OpenTemporaryWindow) == "function" then hooksecurefunc("FCF_OpenTemporaryWindow", A.HookFrames) end
    if type(FCF_OpenNewWindow) == "function" then hooksecurefunc("FCF_OpenNewWindow", A.HookFrames) end
  end
end

local events = CreateFrame("Frame")
events:RegisterEvent("PLAYER_LOGIN")
events:RegisterEvent("PLAYER_ENTERING_WORLD")
events:RegisterEvent("PLAYER_LEAVING_WORLD")
events:RegisterEvent("CHAT_MSG_ADDON")
events:SetScript("OnEvent", function(_, event, ...)
  if event == "PLAYER_LOGIN" then A.Install()
  elseif event == "PLAYER_ENTERING_WORLD" then
    state:Reset()
    state.realm, A.contexts, A.inWorld = GetRealmName() or "", {}, true
    A.Install()
  elseif event == "PLAYER_LEAVING_WORLD" then
    state:ClearPending()
    A.contexts, A.inWorld = {}, false
  elseif A.inWorld then state:Receive(...) end
end)
