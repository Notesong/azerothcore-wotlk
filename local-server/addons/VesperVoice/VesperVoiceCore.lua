-- Lua 5.1. Metadata is a separate server side channel, never part of speech.
local C = { PREFIX = "VESPERVOICE", TTL = 5, MAX_RECORDS = 64 }
VesperVoiceCore = C

local function UInt(value, positive)
  if type(value) ~= "string" or #value > 10 or not value:match("^%d+$")
    or (#value > 1 and value:sub(1, 1) == "0") then return nil end
  local n = tonumber(value)
  if not n or n > 4294967295 or (positive and n == 0) then return nil end
  return n
end

function C.Guid(value)
  if type(value) ~= "string" then return nil end
  value = value:gsub("^0[xX]", "")
  if #value ~= 16 or not value:match("^%x+$") or value == "0000000000000000" then return nil end
  return value:lower() -- Never pass a 64-bit GUID through a Lua number.
end

function C.Sender(name, realm)
  if type(name) ~= "string" then return false end
  local short, other = name:match("^([^%-]+)%-(.+)$")
  if not short then return name:lower() == "vesper" end
  return short:lower() == "vesper" and type(realm) == "string"
    and other:gsub("%s+", ""):lower() == realm:gsub("%s+", ""):lower()
end

function C.Fingerprint(text)
  if type(text) ~= "string" or #text < 1 or #text > 255 then return nil end
  local a, b = 1, 0
  for i = 1, #text do
    a = (a + text:byte(i)) % 65521
    b = (b + a) % 65521
  end
  -- Two small words avoid unsigned-32 formatting differences between Lua builds.
  return string.format("%04x%04x", b, a)
end

local function Identifier(value, limit)
  return type(value) == "string" and #value >= 1 and #value <= limit
    and value:match("^[A-Za-z0-9._:/%-]+$") ~= nil
end

function C.Parse(prefix, body, channel, sender, realm)
  if prefix ~= C.PREFIX or channel ~= "WHISPER" or not C.Sender(sender, realm)
    or type(body) ~= "string" or #prefix + 1 + #body > 255 then return nil end
  local f = {}
  for field in (body .. "|"):gmatch("(.-)|") do f[#f + 1] = field end
  if #f ~= 11 or f[1] ~= "V1" or #f[2] ~= 16 or not f[2]:match("^[0-9a-f]+$")
    or f[4] ~= "5000" or #f[5] ~= 16 or not f[5]:match("^[0-9a-f]+$")
    or C.Guid(f[5]) ~= f[5] or (f[6] ~= "1" and f[6] ~= "2" and f[6] ~= "51")
    or #f[8] ~= 8 or not f[8]:match("^[0-9a-f]+$") then return nil end
  local seq, size = UInt(f[3], true), UInt(f[7], true)
  if not seq or not size or size > 255 or not Identifier(f[10], 24) or not Identifier(f[11], 96) then return nil end
  if f[9] == "mcp" then
    if f[10] ~= "-" or f[11] ~= "-" then return nil end
  elseif f[9] == "body" or f[9] == "social" then
    if f[10] == "-" or f[11] == "-" then return nil end
  else return nil end -- Unknown is deliberately unlabeled.
  return { nonce = f[2], seq = seq, guid = f[5], chat = tonumber(f[6]), size = size,
    hash = f[8], lane = f[9], provider = f[10], model = f[11], wire = body }
end

local function Key(guid, chat, size, hash)
  return guid .. ":" .. chat .. ":" .. size .. ":" .. hash
end

function C.New(realm, clock)
  local S = { records = {}, lines = {}, unmatched = {}, highest = 0, realm = realm, clock = clock }

  function S:ClearPending()
    self.records, self.lines, self.unmatched = {}, {}, {}
  end

  function S:Reset()
    self:ClearPending()
    self.highest = 0
  end

  function S:Prune()
    local now = self.clock()
    for seq, r in pairs(self.records) do if now >= r.expires then self.records[seq] = nil end end
    for key, r in pairs(self.lines) do if now >= r.expires then self.lines[key] = nil end end
    for key, expires in pairs(self.unmatched) do if now >= expires then self.unmatched[key] = nil end end
  end

  local function Bound(t, limit)
    local count, oldestKey, oldest = 0, nil, nil
    for key, row in pairs(t) do
      count = count + 1
      local expiry = type(row) == "table" and row.expires or row
      if not oldest or expiry < oldest then oldestKey, oldest = key, expiry end
    end
    if count > limit then t[oldestKey] = nil end
  end

  function S:Receive(prefix, body, channel, sender)
    self:Prune()
    local r = C.Parse(prefix, body, channel, sender, self.realm)
    if not r then return false, "invalid" end
    local old = self.records[r.seq]
    if old then
      if old.wire == r.wire then return false, "duplicate" end
      old.poisoned, old.spent = true, true
      return false, "conflict"
    end
    if r.seq <= self.highest then return false, "replay" end
    self.highest = r.seq
    r.key = Key(r.guid, r.chat, r.size, r.hash)
    r.expires = self.clock() + C.TTL
    if self.unmatched[r.key] then return false, "late" end
    for _, existing in pairs(self.records) do
      if existing.nonce == r.nonce then
        existing.poisoned, existing.spent = true, true
        return false, "nonce_reused"
      end
    end
    self.records[r.seq] = r
    Bound(self.records, C.MAX_RECORDS)
    return true
  end

  function S:Match(event, guid, text, lineID)
    self:Prune()
    local chat = event == "CHAT_MSG_SAY" and 1 or event == "CHAT_MSG_PARTY" and 2
      or event == "CHAT_MSG_PARTY_LEADER" and 51 or nil
    guid = C.Guid(guid)
    local hash = C.Fingerprint(text)
    if not chat then return nil end
    local pending = {}
    for _, r in pairs(self.records) do
      if not r.spent and not r.poisoned and r.chat == chat then
        pending[#pending + 1] = r
      end
    end
    if not guid or not hash or type(lineID) ~= "number" or lineID < 1
      or lineID > 4294967295 or lineID ~= math.floor(lineID) then
      for _, r in ipairs(pending) do r.spent = true end
      return nil
    end
    local key = Key(guid, chat, #text, hash)
    local lineKey = guid .. ":" .. chat .. ":" .. lineID
    local known = self.lines[lineKey]
    if known then return known.key == key and not known.poisoned and known or nil end
    if #pending == 1 and pending[1].key == key then
      local r = pending[1]
      r.spent = true
      self.lines[lineKey] = r -- Same normal event may be rendered in several chat frames.
      Bound(self.lines, C.MAX_RECORDS)
      return r
    end
    for _, r in ipairs(pending) do r.spent = true end
    self.unmatched[key] = self.clock() + C.TTL
    Bound(self.unmatched, C.MAX_RECORDS)
    return nil
  end

  return S
end

function C.Label(r)
  if r.lane == "mcp" then return "MCP" end
  local model = r.model:lower()
  if model:find("qwen", 1, true) then return "Qwen" end
  if model:find("luna", 1, true) then return "Luna" end
  return r.lane == "body" and "Body" or "Social"
end
