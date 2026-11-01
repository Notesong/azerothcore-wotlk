-- WoW 3.3.5: separate read-only hints, never native loot slots or bot commands.
local PREFIX, RESPONDER = "VESPERLOOT", "Vesper"
local TTL, TIMEOUT, THROTTLE, MAX_ROWS = 5, 3, 1, 8
local A = { status = "not_checked", serial = 0, lastQuery = -100, elapsed = 0 }
VesperLoot = A

local function Guid(value)
  if type(value) ~= "string" or #value ~= 18 or not value:match("^0[xX]%x+$") then return nil end
  local hex = value:sub(3):upper()
  if hex == "0000000000000000" then return nil end
  return "0x" .. hex -- Never convert a 64-bit GUID through a Lua number.
end

local function Sender(name)
  if type(name) ~= "string" then return false end
  local localRealm = (GetRealmName() or ""):gsub("%s+", ""):lower()
  local short, realm = name:match("^([^%-]+)%-(.+)$")
  if not short then return name:lower() == RESPONDER:lower() end
  return short:lower() == RESPONDER:lower() and realm:gsub("%s+", ""):lower() == localRealm
end

local function Eligible()
  local raid = GetNumRaidMembers()
  local count = raid > 0 and raid or GetNumPartyMembers()
  if count < 1 then return false end
  local leader = raid == 0 and IsPartyLeader()
  local buddy, online = false, false
  for i = 1, count do
    local unit = (raid > 0 and "raid" or "party") .. i
    local name, realm = UnitName(unit)
    if name and Sender(name .. (realm and realm ~= "" and "-" .. realm or "")) then
      buddy = true
      online = UnitIsConnected(unit) and true or false
    end
    if raid > 0 then
      local _, rank = GetRaidRosterInfo(i)
      if rank == 2 and UnitGUID(unit) == UnitGUID("player") then leader = true end
    end
  end
  return leader and buddy, online
end

local function Corpse(unit)
  if not unit or not UnitExists(unit) or UnitIsPlayer(unit) or not UnitIsDead(unit) then return nil end
  return Guid(UnitGUID(unit))
end

local function Bound()
  return A.focus and Eligible() and Corpse(A.focus.unit) == A.focus.guid
end

local panel = CreateFrame("Frame", "VesperLootPanel", UIParent)
A.panel = panel
panel:SetWidth(300)
panel:SetClampedToScreen(true)
panel:SetFrameStrata("DIALOG")
panel:EnableMouse(false)
panel:SetBackdrop({ bgFile = "Interface\\Tooltips\\UI-Tooltip-Background",
  edgeFile = "Interface\\Tooltips\\UI-Tooltip-Border", tile = true, tileSize = 16,
  edgeSize = 16, insets = { left = 4, right = 4, top = 4, bottom = 4 } })
panel:SetBackdropColor(0.06, 0.07, 0.10, 0.95)
local texts = {}
for i = 1, MAX_ROWS + 5 do
  texts[i] = panel:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
  texts[i]:SetWidth(276)
  texts[i]:SetJustifyH("LEFT")
  if texts[i].SetWordWrap then texts[i]:SetWordWrap(true) end
end
panel:Hide()

local function Lines()
  local lines = { "Vesper quest loot", "Inspected corpse: " .. (A.focus and A.focus.name or "unknown") }
  if not A.data then
    lines[#lines + 1] = A.status == "offline" and "Unknown: Vesper is offline." or
      A.status == "unknown" and "Unknown: no complete current reply." or "Not checked: awaiting server facts."
  elseif A.data.state == "unknown" then
    lines[#lines + 1] = "Unknown: current loot facts could not be confirmed."
  elseif A.data.state == "unavailable" then
    lines[#lines + 1] = "Not available for inspection by Vesper."
  else
    for _, row in ipairs(A.data.rows) do
      local name = GetItemInfo(row.item) or ("Item #" .. row.item)
      local labels = { available = "available for Vesper", not_needed = "not currently needed",
        collected = "already collected from this corpse", unavailable = "not available for Vesper",
        unknown = "availability unknown" }
      local progress = row.required > 0 and string.format(" (%d/%d; needs %d, here %d)",
        row.owned, row.required, row.needed, row.remaining) or ""
      lines[#lines + 1] = name .. " - " .. labels[row.state] .. progress
    end
    if A.data.state == "partial" then
      lines[#lines + 1] = "Partial result: other items remain unknown."
    elseif #A.data.rows == 0 then
      lines[#lines + 1] = "No matching quest loot reported for Vesper."
    end
  end
  lines[#lines + 1] = "Hints only; normal range, bags and loot rules still apply."
  return lines
end
A.Lines = Lines

local refreshing = false
local function RefreshTooltip()
  if refreshing or not GameTooltip:IsShown() or not A.tooltipUnit or not A.focus then return end
  if Corpse(A.tooltipUnit) ~= A.focus.guid then return end
  refreshing = true
  GameTooltip:SetUnit(A.tooltipUnit)
  refreshing = false
end

local function Render()
  if not Bound() then panel:Hide(); return end
  panel:ClearAllPoints()
  if LootFrame and LootFrame:IsShown() then panel:SetPoint("TOPLEFT", LootFrame, "TOPRIGHT", 8, 0)
  else panel:SetPoint("TOPLEFT", UIParent, "TOPLEFT", 24, -180) end
  local lines, y = Lines(), -10
  for i, text in ipairs(texts) do
    text:ClearAllPoints()
    if lines[i] then
      text:SetHeight(0)
      text:SetText(lines[i])
      text:SetPoint("TOPLEFT", panel, "TOPLEFT", 12, y)
      local height = math.max(14, text:GetStringHeight())
      text:SetHeight(height)
      y = y - height - 4
      text:Show()
    else text:SetText(""); text:Hide() end
  end
  panel:SetHeight(-y + 8)
  panel:Show()
end

local function Clear()
  local oldTooltipUnit = A.tooltipUnit
  A.focus, A.pending, A.data, A.tooltipUnit = nil, nil, nil, nil
  A.status, A.expires = "not_checked", nil
  panel:Hide()
  if not refreshing and oldTooltipUnit and UnitExists(oldTooltipUnit) and GameTooltip:IsShown() then
    refreshing = true
    GameTooltip:SetUnit(oldTooltipUnit) -- Rebuild native text without stale addon hints.
    refreshing = false
  end
end

local function Unknown()
  A.pending, A.data = nil, nil
  A.status, A.expires = "unknown", GetTime() + TTL
  Render()
  RefreshTooltip()
end

local function Query()
  if not Bound() or A.pending or GetTime() < A.lastQuery + THROTTLE then return end
  local _, online = Eligible()
  if not online then A.status = "offline"; return end
  A.serial = A.serial + 1
  local nonce = string.format("vl%x%x", math.floor(GetTime() * 1000) % 2147483647, A.serial % 2147483647)
  A.pending = { nonce = nonce, guid = A.focus.guid, deadline = GetTime() + TIMEOUT }
  A.lastQuery, A.status = GetTime(), "not_checked"
  SendAddonMessage(PREFIX, "Q1|" .. nonce .. "|" .. A.focus.guid, "WHISPER", RESPONDER)
end

local function Inspect(unit)
  local guid = Corpse(unit)
  if not Eligible() or not guid then Clear(); return end
  if not A.focus or A.focus.guid ~= guid then
    A.focus = { guid = guid, name = UnitName(unit) or "unknown", unit = unit }
    A.pending, A.data, A.expires, A.status = nil, nil, nil, "not_checked"
  else A.focus.unit = unit end
  if not A.data and not A.pending and (not A.expires or GetTime() >= A.expires) then Query() end
  Render()
end

local function UInt(value, positive)
  if type(value) ~= "string" or #value > 10 or not value:match("^%d+$")
    or (#value > 1 and value:sub(1, 1) == "0") then return nil end
  local number = tonumber(value)
  if not number or number > 4294967295 or (positive and number == 0) then return nil end
  return number
end

local function Receive(prefix, message, channel, sender)
  if prefix ~= PREFIX or channel ~= "WHISPER" or not Sender(sender) or not Bound() or not A.pending then return end
  local _, online = Eligible()
  if not online then return end
  if GetTime() >= A.pending.deadline then Unknown(); return end
  if type(message) ~= "string" or #PREFIX + 1 + #message > 255 then Unknown(); return end
  local fields = {}
  for field in (message .. "|"):gmatch("(.-)|") do fields[#fields + 1] = field end
  local p = A.pending
  if fields[2] ~= p.nonce or fields[3] ~= p.guid or Guid(fields[3]) ~= p.guid then return end
  if fields[1] == "R1" then
    local states = { checked = true, partial = true, unknown = true, unavailable = true }
    local count = UInt(fields[5])
    if #fields ~= 5 or p.rows or not states[fields[4]] or not count or count > MAX_ROWS
      or ((fields[4] == "unknown" or fields[4] == "unavailable") and count ~= 0) then Unknown(); return end
    p.state, p.count, p.rows, p.items = fields[4], count, {}, {}
  elseif fields[1] == "I1" then
    local item, remaining = UInt(fields[4], true), UInt(fields[5])
    local needed, owned, required = UInt(fields[6]), UInt(fields[7]), UInt(fields[8])
    local states = { available = true, not_needed = true, collected = true, unavailable = true, unknown = true }
    if #fields ~= 9 or not p.rows or #p.rows >= p.count or not item or not remaining
      or not needed or not owned or not required or p.items[item] or not states[fields[9]]
      or (fields[9] == "available" and (remaining == 0 or needed == 0 or owned >= required))
      or (fields[9] == "not_needed" and needed ~= 0) then Unknown(); return end
    p.items[item] = true
    p.rows[#p.rows + 1] = { item = item, remaining = remaining, needed = needed,
      owned = owned, required = required, state = fields[9] }
  elseif fields[1] == "E1" then
    if #fields ~= 5 or not p.rows or fields[4] ~= p.state
      or UInt(fields[5]) ~= p.count or #p.rows ~= p.count then Unknown(); return end
    A.data, A.pending = { state = p.state, rows = p.rows }, nil
    A.status, A.expires = "checked", GetTime() + TTL
    Render()
    RefreshTooltip()
  else Unknown() end
end
A.Receive = Receive

GameTooltip:HookScript("OnTooltipSetUnit", function(tooltip)
  if refreshing and not A.focus then return end
  local _, unit = tooltip:GetUnit()
  if not Corpse(unit) or not Eligible() then return end
  Inspect(unit)
  A.tooltipUnit = unit
  for _, line in ipairs(Lines()) do tooltip:AddLine(line, 0.65, 0.85, 1, true) end
  tooltip:Show()
end)
GameTooltip:HookScript("OnTooltipCleared", function() if not refreshing then A.tooltipUnit = nil end end)
GameTooltip:HookScript("OnHide", function() A.tooltipUnit = nil end)

local frame = CreateFrame("Frame", "VesperLootEvents", UIParent)
A.frame = frame
local function Event(_, event, ...)
  if event == "CHAT_MSG_ADDON" then Receive(...)
  elseif event == "PLAYER_TARGET_CHANGED" or event == "PLAYER_ENTERING_WORLD" then Clear(); Inspect("target")
  elseif event == "LOOT_OPENED" then Inspect(Corpse("mouseover") and "mouseover" or "target")
  elseif event == "LOOT_CLOSED" then
    if A.focus and Corpse("target") == A.focus.guid then A.focus.unit = "target"; Render()
    elseif A.tooltipUnit and A.focus and Corpse(A.tooltipUnit) == A.focus.guid then Render()
    else Clear() end
  elseif event == "LOOT_SLOT_CLEARED" or event == "LOOT_SLOT_CHANGED" then
    A.pending, A.data, A.expires = nil, nil, nil; A.status = "not_checked"; Query(); Render(); RefreshTooltip()
  elseif event == "PARTY_MEMBERS_CHANGED" or event == "PARTY_LEADER_CHANGED"
    or event == "RAID_ROSTER_UPDATE" then Clear(); Inspect("target")
  elseif event == "PLAYER_LOGOUT" then Clear() end
end
frame:SetScript("OnEvent", Event)
for _, event in ipairs({ "CHAT_MSG_ADDON", "PLAYER_TARGET_CHANGED", "PLAYER_ENTERING_WORLD",
  "LOOT_OPENED", "LOOT_CLOSED", "LOOT_SLOT_CLEARED", "LOOT_SLOT_CHANGED", "PARTY_MEMBERS_CHANGED",
  "PARTY_LEADER_CHANGED", "RAID_ROSTER_UPDATE", "PLAYER_LOGOUT" }) do frame:RegisterEvent(event) end
frame:SetScript("OnUpdate", function(_, elapsed)
  A.elapsed = A.elapsed + elapsed
  if A.elapsed < 0.25 then return end
  A.elapsed = 0
  if not Eligible() then Clear(); return end
  if not A.focus then if Corpse("target") then Inspect("target") end; return end
  if not Bound() then
    if Corpse("target") == A.focus.guid then A.focus.unit = "target" else Clear(); RefreshTooltip(); return end
  end
  local _, online = Eligible()
  if not online then
    local changed = A.status ~= "offline" or A.data or A.pending
    A.pending, A.data, A.expires, A.status = nil, nil, nil, "offline"
    if changed then Render(); RefreshTooltip() end
    return
  elseif A.status == "offline" then
    A.status = "not_checked"
    Query(); Render(); RefreshTooltip()
  end
  if A.pending and GetTime() >= A.pending.deadline then Unknown() end
  if A.expires and GetTime() >= A.expires then
    A.data, A.expires, A.status = nil, nil, "not_checked"
    Query(); Render(); RefreshTooltip()
  elseif not A.pending and not A.data and not A.expires then Query() end
end)
