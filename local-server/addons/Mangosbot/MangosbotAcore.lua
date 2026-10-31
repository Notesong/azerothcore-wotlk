-- AzerothCore Playerbots protocol. Loading this file sends no commands.
MangosbotAcore = {}
local C = MangosbotAcore
C.bots = {}
C.last_error = nil

local clock, nextSend, serial = 0, 0, 0
local queue = {}
local interval, queueLimit = 0.35, 256

local classes = {
    warrior = "Warrior", paladin = "Paladin", hunter = "Hunter", rogue = "Rogue",
    priest = "Priest", shaman = "Shaman", mage = "Mage", warlock = "Warlock",
    druid = "Druid", deathknight = "DeathKnight", dk = "DeathKnight",
}
local profiles = {
    Warrior = { tank = { "prot pve", "prot" }, dps = { "arms pve", "arms" } },
    Paladin = { tank = { "prot pve", "prot" }, heal = { "holy pve", "holy" }, dps = { "ret pve", "ret" } },
    Priest = { heal = { "holy pve", "holy heal" }, dps = { "shadow pve", "shadow" } },
    Druid = { tank = { "bear pve", "bear" }, heal = { "resto pve", "resto" }, dps = { "balance pve", "balance" } },
    Shaman = { heal = { "resto pve", "resto" }, dps = { "ele pve", "ele" } },
    DeathKnight = { tank = { "blood pve", "blood" }, dps = { "frost pve", "frost" } },
    Hunter = { dps = { "bm pve", "bm" } }, Rogue = { dps = { "combat pve", "combat" } },
    Mage = { dps = { "frost pve", "frost" } }, Warlock = { dps = { "affli pve", "affli" } },
}
local combatNames = {
    Warrior = { "prot", "arms", "fury" }, Paladin = { "prot", "holy", "ret" },
    Priest = { "disc", "holy heal", "holy dps", "shadow" },
    Druid = { "bear", "cat", "balance", "resto" }, Shaman = { "ele", "enh", "resto" },
    DeathKnight = { "blood", "frost", "unholy" }, Hunter = { "bm", "mm", "surv" },
    Rogue = { "assassin", "combat" }, Mage = { "arcane", "fire", "frost", "frostfire" },
    Warlock = { "affli", "demo", "destro" },
}
local tankNames = { prot = true, bear = true, blood = true, tank = true }
local healNames = { holy = true, disc = true, ["holy heal"] = true, resto = true, heal = true }
local directCommands = {
    follow = true, stay = true, flee = true, summon = true, leave = true,
    attack = true, pull = true, repair = true, revive = true,
    ["do attack my target"] = true, who = true, talents = true,
    ["talents spec list"] = true, ["co ?"] = true, ["autogear match"] = true,
}

local function trim(value)
    return type(value) == "string" and (value:gsub("^%s+", ""):gsub("%s+$", "")) or ""
end

local function validText(value)
    return type(value) == "string" and #value > 0 and #value <= 255
        and not value:find("[%z\1-\31\127]")
end

local function playerName(value)
    if type(value) ~= "string" then return nil end
    value = trim(value)
    if #value < 2 or #value > 12 or not value:match("^%a+$") then return nil end
    return value:sub(1, 1):upper() .. value:sub(2):lower()
end

local function selfName()
    if type(C.selfName) == "string" then return playerName(C.selfName) end
    if type(UnitName) == "function" then
        local ok, name = pcall(UnitName, "player")
        if ok then return playerName(name) end
    end
    return nil
end

local function excluded(name)
    local normalized = playerName(name)
    return not normalized or normalized == "Vesper" or normalized == selfName()
end

local function botFor(name, online)
    local normalized = playerName(name)
    if not normalized or excluded(normalized) then return nil end
    local bot = C.bots[normalized]
    if not bot or (online and not bot.online) then return nil end
    return bot
end

local function changed()
    if type(C.onChange) == "function" then pcall(C.onChange) end
end

local function log(name, text)
    if type(C.onReply) == "function" then pcall(C.onReply, name or "Addon", text) end
end

local function fail(name, text)
    C.last_error = text
    local bot = botFor(name, false)
    if bot then bot.last_error = text end
    changed()
    return false, text
end

local function cancelRole(bot, text)
    bot.role_pending = nil
    bot.last_error = text
    log(bot.name, "Addon: " .. text)
    changed()
end

local function enqueue(job)
    for _, queued in ipairs(queue) do
        if queued.kind == job.kind and queued.name == job.name and queued.text == job.text
            and queued.token == job.token then return true end
    end
    if #queue >= queueLimit then return fail(job.name, "The command queue is full; wait before trying again.") end
    queue[#queue + 1] = job
    return true
end

local function queueBot(bot, command, token, afterSend)
    return enqueue({ kind = "bot", name = bot.name, text = command, token = token, afterSend = afterSend })
end

local function commandAllowed(bot, command)
    if directCommands[command] then return true end
    local spec = command:match("^talents spec (.+)$")
    if spec then
        for _, profile in pairs(profiles[bot.class] or {}) do
            if profile[1] == spec then return true end
        end
        return false
    end
    -- Role workflows use only the installed class strategies and assist flags.
    local modifiers = command:match("^co (.+)$")
    if modifiers then
        local allowed = { ["tank assist"] = true, ["dps assist"] = true }
        for _, name in ipairs(combatNames[bot.class] or {}) do allowed[name] = true end
        local count = 0
        for part in (modifiers .. ","):gmatch("(.-),") do
            count = count + 1
            local operation, name = part:match("^([+-])(.+)$")
            if part ~= "?" and (not operation or not allowed[name]) then return false end
        end
        return count > 0
    end
    return false
end

function C.ParseRoster(message)
    if type(message) ~= "string" then return false end
    local text = message:match("^Bot roster:%s?(.*)$")
    if text == nil then return false end
    local nextBots = {}
    for row in (text .. ","):gmatch("(.-),") do
        row = trim(row)
        if row ~= "" then
            local status, rawName, class = row:match("^([+-])(%a+)%s+(.+)$")
            local name = playerName(rawName)
            class = class and classes[trim(class):lower():gsub("%s+", "")]
            if not status or not name or not class then return false end
            if not excluded(name) then
                if nextBots[name] and nextBots[name].class ~= class then return false end
                local bot = nextBots[name]
                if not bot and C.bots[name] and C.bots[name].class == class then
                    -- Stage independent records: a malformed later row must
                    -- not mutate the authoritative roster before validation.
                    bot = {}
                    for key, value in pairs(C.bots[name]) do bot[key] = value end
                end
                if not bot or bot.class ~= class then
                    bot = { name = name, class = class, role = "unknown" }
                end
                local wasOnline = nextBots[name] and nextBots[name].online or false
                bot.online = wasOnline or status == "+"
                nextBots[name] = bot
            end
        end
    end
    for name, bot in pairs(nextBots) do
        local previous = C.bots[name]
        if not bot.online or (previous and not previous.online) then
            -- A newly logged-in bot can have been automatically initialized.
            -- Its previous session's role/spec receipt no longer proves state.
            bot.role = "unknown"
            bot.combat_strategies = nil
            bot.spec = nil
            bot.talent_spec = nil
        end
        if bot.role_pending and not bot.online then
            cancelRole(bot, "Role change cancelled because the bot left the online roster.")
        end
    end
    for name, bot in pairs(C.bots) do
        if bot.role_pending and not nextBots[name] then
            cancelRole(bot, "Role change cancelled because the bot left the online roster.")
        end
    end
    C.bots = nextBots
    changed()
    return true
end

function C.SendAdmin(verb, argument)
    if type(verb) ~= "string" then return fail(nil, "Unknown server command.") end
    verb = trim(verb):lower()
    local text
    if verb == "list" and (argument == nil or argument == "") then
        text = ".playerbots bot list"
    elseif verb == "addclass" and validText(argument) then
        local class = trim(argument):lower():gsub("%s+", "")
        if class == "deathknight" then class = "dk" end
        if not classes[class] then return fail(nil, "Choose a supported bot class.") end
        text = ".playerbots bot addclass " .. class
    elseif (verb == "add" or verb == "remove") and validText(argument) then
        local names = {}
        for name in (argument .. ","):gmatch("(.-),") do
            local bot = botFor(name, false)
            if not bot then return fail(nil, "Only names in the current bot roster may be added or removed.") end
            names[#names + 1] = bot.name
        end
        if #names == 0 then return fail(nil, "Choose a bot first.") end
        text = ".playerbots bot " .. verb .. " " .. table.concat(names, ",")
    else
        return fail(nil, "Unsupported server command or invalid argument.")
    end
    if not validText(text) then return fail(nil, "The server command is too long or contains control characters.") end
    return enqueue({ kind = "admin", text = text, verb = verb, argument = argument })
end

function C.SendBot(name, command)
    local bot = botFor(name, true)
    if not bot then return fail(name, "Choose an online ordinary bot from the current roster.") end
    if not validText(command) or not commandAllowed(bot, command) then
        return fail(name, "This command is not supported by this AzerothCore control panel.")
    end
    return queueBot(bot, command)
end

function C.Query(name)
    local bot = botFor(name, true)
    if not bot then return fail(name, "Choose an online ordinary bot before querying it.") end
    for _, command in ipairs({ "who", "talents", "co ?" }) do
        local ok, error = queueBot(bot, command)
        if not ok then return false, error end
    end
    return true
end

function C.GetRole(name)
    local bot = botFor(name, true)
    return bot and bot.role or "unknown"
end

function C.CanRole(name, role)
    local bot = botFor(name, true)
    return bot ~= nil and type(role) == "string" and profiles[bot.class] ~= nil
        and profiles[bot.class][role] ~= nil
end

function C.RequestRole(name, role)
    local bot = botFor(name, true)
    if not bot or not C.CanRole(name, role) then return fail(name, "That bot class cannot use this role preset.") end
    if bot.role_pending then return fail(name, "Wait for the current role change to finish or time out.") end
    serial = serial + 1
    local profile = profiles[bot.class][role]
    local pending = { role = role, spec = profile[1], strategy = profile[2],
        token = serial, phase = "queued_spec", deadline = clock + 45 }
    bot.role_pending = pending
    bot.last_error = nil
    local ok, error = queueBot(bot, "talents spec " .. pending.spec, pending.token, function()
        pending.phase = "await_spec"
        pending.deadline = clock + 20
    end)
    if not ok then bot.role_pending = nil; return false, error end
    changed()
    return true
end

local function strategyRole(bot, strategies)
    local permitted = {}
    for _, name in ipairs(combatNames[bot.class] or {}) do permitted[name] = true end
    local found = {}
    for name in pairs(strategies) do
        if permitted[name] then
            local role = tankNames[name] and "tank" or (healNames[name] and "heal" or "dps")
            found[role] = true
        end
    end
    local result
    for role in pairs(found) do
        if result then return "unknown" end
        result = role
    end
    return result or "unknown"
end

local function cleanReply(text)
    text = text:gsub("|c%x%x%x%x%x%x%x%x", ""):gsub("|r", "")
    text = text:gsub("|H.-|h(.-)|h", "%1"):gsub("|h", "")
    return trim(text)
end

function C.HandleReply(message, sender)
    if type(message) ~= "string" or type(sender) ~= "string" then return false end
    local bot = botFor(sender, true)
    if not bot then return false end
    bot.last_reply = message
    local text = cleanReply(message)
    local pending = bot.role_pending
    local picked = text:match("^Picking (.+)$")
    if picked then
        bot.spec = picked
        if pending and pending.phase == "await_spec" and picked == pending.spec then
            -- SpecPick resets strategies server-side. Do not carry an old role
            -- claim forward while waiting for the new combat-strategy receipt.
            bot.role = "unknown"
            bot.combat_strategies = nil
            pending.phase = "queued_strategy"
            pending.deadline = clock + 30
            local modifiers = {}
            for _, strategy in ipairs(combatNames[bot.class] or {}) do
                if strategy ~= pending.strategy then modifiers[#modifiers + 1] = "-" .. strategy end
            end
            modifiers[#modifiers + 1] = "+" .. pending.strategy
            modifiers[#modifiers + 1] = pending.role == "tank" and "-dps assist" or "-tank assist"
            modifiers[#modifiers + 1] = pending.role == "tank" and "+tank assist" or "+dps assist"
            modifiers[#modifiers + 1] = "?"
            local ok = queueBot(bot, "co " .. table.concat(modifiers, ","), pending.token, function()
                pending.phase = "await_strategy"
                pending.deadline = clock + 20
            end)
            if ok then C.Query(bot.name)
            else cancelRole(bot, "The role verification could not be queued.") end
        end
    end
    local talentSpec = text:match("^My current talent spec is:%s*([^\r\n]+)")
    if talentSpec then
        bot.talent_spec = trim(talentSpec)
        if not bot.spec then bot.spec = bot.talent_spec end
    end
    local strategyText = text:match("^Strategies:%s*(.*)$") or text:match("^Combat Strategies:%s*(.*)$")
    if strategyText then
        local strategies = {}
        for strategy in (strategyText .. ","):gmatch("(.-),") do
            strategy = trim(strategy)
            if strategy ~= "" then strategies[strategy] = true end
        end
        bot.combat_strategies = strategies
        bot.role = strategyRole(bot, strategies)
        if pending and pending.phase == "await_strategy" and bot.role == pending.role then
            bot.role_pending = nil
            bot.last_error = nil
        end
    end
    if pending and bot.role_pending and pending.phase == "await_spec"
        and (text:match("^Spec .+ not found$") or text == "Unknown command." or text:match("^ERROR:")) then
        cancelRole(bot, "The server rejected the talent preset: " .. text)
    end
    log(bot.name, message)
    changed()
    return true
end

function C.HandleSystem(message)
    return C.ParseRoster(message)
end

function C.Tick(elapsed)
    if type(elapsed) ~= "number" or elapsed ~= elapsed or elapsed < 0 or elapsed == math.huge then return end
    clock = clock + elapsed
    for _, bot in pairs(C.bots) do
        if bot.role_pending and clock >= bot.role_pending.deadline then
            cancelRole(bot, "Role change timed out without the required server confirmation.")
        end
    end
    if clock < nextSend then return end
    while #queue > 0 do
        local job = table.remove(queue, 1)
        local valid = true
        local bot
        if job.kind == "bot" then
            bot = botFor(job.name, true)
            valid = bot ~= nil and (not job.token or (bot.role_pending and bot.role_pending.token == job.token))
        elseif job.verb == "add" or job.verb == "remove" then
            for name in (job.argument .. ","):gmatch("(.-),") do
                if not botFor(name, false) then valid = false; break end
            end
        end
        if valid then
            nextSend = clock + interval
            local ok = false
            if type(SendChatMessage) == "function" then
                if job.kind == "admin" then ok = pcall(SendChatMessage, job.text, "SAY")
                else ok = pcall(SendChatMessage, job.text, "WHISPER", nil, bot.name) end
            end
            if not ok then
                if bot and bot.role_pending and job.token then cancelRole(bot, "The command could not be sent.")
                else fail(job.name, "The command could not be sent.") end
            elseif job.afterSend then job.afterSend() end
            -- Delayed frames never drain the queue in a burst.
            return
        end
    end
end
