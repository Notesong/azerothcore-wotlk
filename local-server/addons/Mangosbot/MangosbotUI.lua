-- Ordinary mod-playerbots companions for WoW 3.3.5a; Vesper stays in Presence.
local C = assert(MangosbotAcore, "MangosbotAcore.lua must load before the UI")
local selected, page, replyLines = nil, 1, {}
local rows, controls, roleButtons = {}, {}, {}
local frame = CreateFrame("Frame", "MangosbotFrame", UIParent)
frame:SetWidth(740)
frame:SetHeight(592)
frame:SetPoint("CENTER", UIParent, "CENTER", 0, 0)
frame:SetFrameStrata("DIALOG")
frame:SetMovable(true)
frame:EnableMouse(true)
frame:RegisterForDrag("LeftButton")
frame:SetClampedToScreen(true)
frame:SetBackdrop({bgFile = "Interface\\DialogFrame\\UI-DialogBox-Background",
    edgeFile = "Interface\\DialogFrame\\UI-DialogBox-Border", tile = true, tileSize = 32, edgeSize = 32,
    insets = {left = 9, right = 9, top = 9, bottom = 9}})
frame:SetScript("OnDragStart", function(self) self:StartMoving() end)
frame:SetScript("OnDragStop", function(self)
    self:StopMovingOrSizing()
    local point, _, relativePoint, x, y = self:GetPoint()
    mangosbot_options = mangosbot_options or {}
    mangosbot_options.acorePosition = {point, relativePoint, x, y}
end)
frame:Hide()
UISpecialFrames = UISpecialFrames or {}
tinsert(UISpecialFrames, "MangosbotFrame")

local function label(text, x, y, width, height, size)
    local item = frame:CreateFontString(nil, "OVERLAY", "GameFontNormal")
    item:SetFont("Fonts\\FRIZQT__.TTF", size or 13)
    item:SetPoint("TOPLEFT", frame, "TOPLEFT", x, y)
    item:SetWidth(width)
    item:SetHeight(height)
    item:SetJustifyH("LEFT")
    item:SetJustifyV("TOP")
    item:SetText(text)
    return item
end

local function tooltip(widget, text)
    widget:SetScript("OnEnter", function(self)
        GameTooltip:SetOwner(self, "ANCHOR_RIGHT")
        GameTooltip:SetText(text, 1, 1, 1, 1, true)
        GameTooltip:Show()
    end)
    widget:SetScript("OnLeave", function() GameTooltip:Hide() end)
end

local function button(text, x, y, width, callback, hint)
    local item = CreateFrame("Button", nil, frame, "UIPanelButtonTemplate")
    item:SetPoint("TOPLEFT", frame, "TOPLEFT", x, y)
    item:SetWidth(width)
    item:SetHeight(25)
    item:SetText(text)
    item:SetScript("OnClick", callback)
    if hint then tooltip(item, hint) end
    return item
end

local RefreshUI
local function log(name, text)
    if selected and name and name ~= selected then return end
    text = tostring(text or ""):gsub("[\r\n]+", " ")
    if #text > 320 then text = text:sub(1, 317) .. "..." end
    tinsert(replyLines, text)
    while #replyLines > 7 do tremove(replyLines, 1) end
end
local function result(ok, reason) if not ok and reason then log(nil, reason) end end
local function send(command)
    if selected then result(C.SendBot(selected, command)); RefreshUI() end
end

label("MaNGOSBot | AzerothCore", 23, -19, 635, 27, 18)
label("Ordinary bot companions", 23, -55, 217, 22, 14)
local title = label("Select a companion", 250, -55, 456, 25, 16)
local status = label("Use Refresh to load your server roster.", 250, -82, 456, 49)
local rosterStatus = label("", 23, -408, 217, 21)
local replies = label("", 250, -354, 456, 159, 12)
local activity = label("", 250, -326, 456, 22)
local close = CreateFrame("Button", nil, frame, "UIPanelCloseButton")
close:SetPoint("TOPRIGHT", frame, "TOPRIGHT", -5, -5)
close:SetScript("OnClick", function() frame:Hide() end)

local function selectBot(name)
    if not C.bots[name] then return end
    selected, replyLines = name, {}
    if C.bots[name].last_reply then log(name, C.bots[name].last_reply) end
    if C.bots[name].online then result(C.Query(name)) end
    RefreshUI()
end
for i = 1, 10 do
    local row = button("", 23, -85 - (i - 1) * 31, 217, function() end)
    row:SetScript("OnClick", function(self) if self.botName then selectBot(self.botName) end end)
    rows[i] = row
end
button("<", 23, -435, 38, function() page = math.max(1, page - 1); RefreshUI() end)
button(">", 65, -435, 38, function() page = page + 1; RefreshUI() end)
button("Refresh", 110, -435, 130, function() result(C.SendAdmin("list")); RefreshUI() end,
    "Read your own alts, controlled companions and grouped ordinary bots from the server.")

for i, definition in ipairs({
    {"Follow", "follow", "Follow your character."},
    {"Stay", "stay", "Stay at the current location."},
    {"Flee", "flee", "Return toward you while ignoring combat."},
    {"Summon", "summon", "Use the server's ordinary bot summon command."},
    {"Attack target", "do attack my target", "Attack your currently selected enemy."},
    {"Leave party", "leave", "Leave the party. Use Logout to log a controlled companion out."}
}) do
    local command = definition[2]
    controls[#controls + 1] = button(definition[1],
        250 + ((i - 1) % 3) * 153, -141 - math.floor((i - 1) / 3) * 31, 145,
        function() send(command) end, definition[3])
end
local loginButton = button("Login", 250, -203, 145, function()
    local bot = selected and C.bots[selected]
    if not bot then return end
    result(C.SendAdmin(bot.online and "remove" or "add", selected))
    RefreshUI()
end, "Login an offline alt, or log out your controlled ordinary bot. Vesper is managed in Presence.")
local inviteButton = button("Invite", 403, -203, 145, function()
    if selected and C.bots[selected] and C.bots[selected].online then InviteUnit(selected) end
end, "Invite this online companion to your party.")
local inspectButton = button("Inspect", 556, -203, 145, function()
    if selected then result(C.Query(selected)); RefreshUI() end
end, "Ask for current character details, talent spec and combat strategies.")

label("Role preset", 250, -243, 456, 23, 14)
for i, definition in ipairs({{"Tank", "tank"}, {"Healer", "heal"}, {"Damage", "dps"}}) do
    local role = definition[2]
    roleButtons[role] = button(definition[1], 250 + (i - 1) * 153, -268, 145, function()
        if selected then result(C.RequestRole(selected, role)); RefreshUI() end
    end, "Apply a configured PvE talent preset and combat strategies; wait for the server reply. " ..
        "Equipment is separate. Below level 10, talent builds and tank/healer toolkits are limited.")
end
local gearButton = button("Match gear", 250, -300, 145, function() send("autogear match") end,
    "Generate upgrades for the current spec within the server's autogear limits. Match uses your average " ..
    "item level. Existing gear is not stripped first. Choose the role and wait for its reply before using this.")
local talentsButton = button("Available specs", 403, -300, 145, function() send("talents spec list") end,
    "List this class's talent presets configured on the server.")
local reviveButton = button("Revive", 556, -300, 145, function() send("revive") end,
    "Ask the ordinary bot to revive under the server's bot rules.")

label("Recruit a class companion", 23, -478, 217, 23, 13)
local recruitClass = "priest"
local classMenu = CreateFrame("Frame", "MangosbotClassMenu", frame, "UIDropDownMenuTemplate")
classMenu:SetPoint("TOPLEFT", frame, "TOPLEFT", 7, -501)
UIDropDownMenu_SetWidth(classMenu, 114)
UIDropDownMenu_SetText(classMenu, "Priest")
UIDropDownMenu_Initialize(classMenu, function()
    for _, className in ipairs({"warrior", "paladin", "hunter", "rogue", "priest", "shaman", "mage",
        "warlock", "druid", "dk"}) do
        local name = className
        local info = UIDropDownMenu_CreateInfo()
        info.text = name == "dk" and "Death Knight" or name:sub(1, 1):upper() .. name:sub(2)
        info.checked = recruitClass == name
        info.func = function()
            recruitClass = name
            UIDropDownMenu_SetText(classMenu, info.text)
            CloseDropDownMenus()
        end
        UIDropDownMenu_AddButton(info)
    end
end)
button("Recruit", 167, -504, 73, function()
    result(C.SendAdmin("addclass", recruitClass)); RefreshUI()
end, "Recruit a class companion from the server's pool. They may need level/gear initialization. " ..
    "This does not create a custom character or start a model.")

local function groupCommand(command)
    local count, prefix = GetNumRaidMembers(), "raid"
    if count == 0 then count, prefix = GetNumPartyMembers(), "party" end
    local sent = 0
    for i = 1, count do
        local name = UnitName(prefix .. i)
        if name and C.bots[name] and C.bots[name].online then
            if C.SendBot(name, command) then sent = sent + 1 end
        end
    end
    log(nil, "Queued for " .. sent .. " ordinary party/raid bots.")
    RefreshUI()
end
for i, definition in ipairs({{"Party follow", "follow"}, {"Party stay", "stay"}, {"Party flee", "flee"}}) do
    local command = definition[2]
    button(definition[1], 250 + (i - 1) * 153, -517, 145, function() groupCommand(command) end,
        "Whisper this order only to roster-confirmed ordinary bots in your party or raid.")
end
label("Vesper uses Presence. These controls do not change his character or model controller.",
    23, -557, 689, 22, 12)

local function enable(widget, allowed) if allowed then widget:Enable() else widget:Disable() end end
RefreshUI = function()
    local names = {}
    for name in pairs(C.bots) do names[#names + 1] = name end
    table.sort(names)
    local pages = math.max(1, math.ceil(#names / 10))
    page = math.min(math.max(1, page), pages)
    rosterStatus:SetText(#names .. " companions | Page " .. page .. "/" .. pages)
    for i, row in ipairs(rows) do
        local name = names[(page - 1) * 10 + i]
        row.botName = name
        if name then
            row:SetText((selected == name and "> " or "") .. name ..
                (C.bots[name].online and "  [on]" or "  [off]"))
            tooltip(row, name .. " - " .. tostring(C.bots[name].class or "Unknown") .. "\nClick to select and inspect.")
            row:Show()
        else row:Hide() end
    end
    local bot = selected and C.bots[selected]
    local online = bot and bot.online
    title:SetText(bot and (selected .. " | " .. tostring(bot.class or "Unknown")) or "Select a companion")
    status:SetText(bot and ((online and "Online" or "Offline") .. " | Observed role: " .. C.GetRole(selected) ..
        (bot.spec and ("\nSpec: " .. bot.spec) or "\nUse Inspect to request current server details.")) or
        "Use Refresh to load your own alts and ordinary bot companions.")
    activity:SetText(bot and bot.role_pending and "Role change pending server confirmation..." or "Latest server replies:")
    for _, item in ipairs(controls) do enable(item, online) end
    enable(loginButton, bot ~= nil)
    loginButton:SetText(online and "Logout" or "Login")
    for _, item in ipairs({inviteButton, inspectButton, gearButton, talentsButton, reviveButton}) do
        enable(item, online and not bot.role_pending)
    end
    for role, item in pairs(roleButtons) do
        enable(item, online and not bot.role_pending and C.CanRole(selected, role))
    end
    replies:SetText(table.concat(replyLines, "\n"))
end
C.onChange = RefreshUI
C.onReply = function(name, text) log(name, text); RefreshUI() end

local function open()
    frame:Show()
    result(C.SendAdmin("list")); RefreshUI()
end
SLASH_MANGOSBOT1, SLASH_MANGOSBOT2 = "/bot", "/mangosbot"
SlashCmdList.MANGOSBOT = function(message)
    message = (message or ""):lower():match("^%s*(.-)%s*$")
    if message == "hide" or message == "roster hide" then frame:Hide(); return end
    if message == "refresh" then open(); return end
    if message ~= "" and message ~= "roster" and message ~= "show" and message ~= "roster show" then
        DEFAULT_CHAT_FRAME:AddMessage("MaNGOSBot: /bot, /bot show, /bot hide, /bot refresh"); return
    end
    if (message == "" or message == "roster") and frame:IsShown() then frame:Hide() else open() end
end

local events = CreateFrame("Frame")
for _, event in ipairs({"ADDON_LOADED", "CHAT_MSG_SYSTEM", "CHAT_MSG_WHISPER", "PARTY_MEMBERS_CHANGED",
    "RAID_ROSTER_UPDATE", "PLAYER_TARGET_CHANGED"}) do events:RegisterEvent(event) end
events:SetScript("OnEvent", function(_, event, ...)
    local first, sender = ...
    if event == "ADDON_LOADED" and tostring(first):lower() == "mangosbot" then
        mangosbot_options = mangosbot_options or {}
        local position = mangosbot_options.acorePosition
        if type(position) == "table" and type(position[1]) == "string" and type(position[2]) == "string"
            and type(position[3]) == "number" and type(position[4]) == "number" then
            frame:ClearAllPoints()
            frame:SetPoint(position[1], UIParent, position[2], position[3], position[4])
        end
        DEFAULT_CHAT_FRAME:AddMessage("MaNGOSBot for AzerothCore loaded. Type /bot for ordinary companions.")
    elseif event == "CHAT_MSG_SYSTEM" then
        if not C.ParseRoster(first) and C.HandleSystem then C.HandleSystem(first) end
    elseif event == "CHAT_MSG_WHISPER" then C.HandleReply(first, sender)
    elseif event == "PLAYER_TARGET_CHANGED" and frame:IsShown() then
        local name = UnitName("target")
        if name and C.bots[name] and name ~= selected then selectBot(name) end
    elseif frame:IsShown() and (event == "PARTY_MEMBERS_CHANGED" or event == "RAID_ROSTER_UPDATE") then
        C.SendAdmin("list")
    end
end)
events:SetScript("OnUpdate", function(_, elapsed) C.Tick(elapsed) end)
RefreshUI()
