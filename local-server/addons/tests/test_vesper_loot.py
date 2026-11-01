"""Offline WoW 3.3.5/Lua 5.1 tests; no game, network, bot or paid model calls."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "addon-integration/test-tools"))
from lupa.lua51 import LuaRuntime

ADDON = ROOT / "addons/VesperLoot"
GUID = "0xF130003D1C00FEDC"
OTHER = "0xF130003D1C00FEDF"

MOCK = r'''
os=nil; io=nil
clock=0; sent={}; frames={}; leader=true; partyCount=1; raidCount=0; connected=true
units={player={guid='0x0000000000000067',name='Aurenne',player=true},
 party1={guid='0x0000000000000066',name='Vesper',player=true},
 target={guid='0xF130003D1C00FEDC',name='Thaelis the Hungerer',dead=true}}
Mangosbot={untouched='ordinary companions'}
function GetTime() return clock end
function GetRealmName() return 'Azeroth Core' end
function GetNumPartyMembers() return partyCount end
function GetNumRaidMembers() return raidCount end
function IsPartyLeader() return leader end
function GetRaidRosterInfo(i) return UnitName('raid'..i),i==1 and 2 or 0 end
function UnitName(u) return units[u] and units[u].name,units[u] and units[u].realm end
function UnitGUID(u) return units[u] and units[u].guid end
function UnitExists(u) return units[u]~=nil end
function UnitIsPlayer(u) return units[u] and units[u].player or false end
function UnitIsDead(u) return units[u] and units[u].dead or false end
function UnitIsConnected(u) return connected end
function GetItemInfo(id)
 if id==21781 then return "Thaelis's Head" elseif id==20743 then return 'Unstable Mana Crystal' end
end
function SendAddonMessage(prefix,text,channel,target)
 table.insert(sent,{prefix=prefix,text=text,channel=channel,target=target})
end
function SendChatMessage() error('No bot or human chat commands') end
function LootSlot() error('No pickup actions') end
function GetNumLootItems() error('Do not replace or inspect native loot slots') end
function CloseLoot() error('Do not close native loot') end
local methods={}
function methods:SetScript(name,fn) self.scripts[name]=fn end
function methods:HookScript(name,fn)
 local before=self.scripts[name]
 self.scripts[name]=function(...) if before then before(...) end;fn(...) end
end
function methods:RegisterEvent(name) self.events[name]=true end
function methods:SetText(text) self.text=text end
function methods:GetText() return self.text or '' end
function methods:GetStringHeight() return 14 end
function methods:SetWidth(w) self.width=w end
function methods:SetHeight(h) self.height=h end
function methods:EnableMouse(value) self.mouse=value end
function methods:Show() self.shown=true end
function methods:Hide() self.shown=false;if self.scripts.OnHide then self.scripts.OnHide(self) end end
function methods:IsShown() return self.shown end
function methods:CreateFontString() return CreateFrame('FontString',nil,self) end
for _,name in ipairs({'SetClampedToScreen','SetFrameStrata','SetBackdrop','SetBackdropColor',
 'SetJustifyH','SetWordWrap','ClearAllPoints','SetPoint'})do methods[name]=function()end end
function CreateFrame(kind,name,parent)
 local f=setmetatable({kind=kind,name=name,parent=parent,scripts={},events={},shown=false},{__index=methods})
 table.insert(frames,f);if name then _G[name]=f end;return f
end
UIParent=CreateFrame('Frame','UIParent');UIParent:Show()
LootFrame=CreateFrame('Frame','LootFrame')
GameTooltip=CreateFrame('GameTooltip','GameTooltip')
function GameTooltip:GetUnit() return UnitName(self.unit),self.unit end
function GameTooltip:AddLine(text) table.insert(self.lines,text) end
function GameTooltip:SetUnit(unit)
 if self.scripts.OnTooltipCleared then self.scripts.OnTooltipCleared(self) end
 self.unit=unit;self.lines={'Native tooltip: '..(UnitName(unit)or'unknown')};self.shown=true
 if self.scripts.OnTooltipSetUnit then self.scripts.OnTooltipSetUnit(self) end
end
'''


class VesperLootTests(unittest.TestCase):
    def setUp(self):
        self.load_addon()

    def load_addon(self, without_word_wrap=False):
        self.lua = LuaRuntime(unpack_returned_tuples=True, register_eval=False, register_builtins=False)
        self.lua.execute(MOCK)
        if without_word_wrap:
            self.lua.execute("getmetatable(UIParent).__index.SetWordWrap=nil")
        self.lua.execute((ADDON / "VesperLoot.lua").read_text(encoding="utf-8"))
        self.g = self.lua.globals()
        self.a = self.g.VesperLoot

    def event(self, event, *args):
        self.a.frame.scripts.OnEvent(self.a.frame, event, *args)

    def tick(self, seconds):
        self.g.clock += seconds
        self.a.frame.scripts.OnUpdate(self.a.frame, seconds)

    def inspect(self):
        self.event("PLAYER_TARGET_CHANGED")
        return self.a.pending.nonce

    def reply(self, text, sender="Vesper", channel="WHISPER", prefix="VESPERLOOT"):
        self.event("CHAT_MSG_ADDON", prefix, text, channel, sender)

    def header(self, nonce=None, guid=GUID, state="checked", count=1):
        self.reply(f"R1|{nonce or self.a.pending.nonce}|{guid}|{state}|{count}")

    def row(self, item=21781, remaining=1, needed=1, owned=0, required=1, state="available", nonce=None, guid=GUID):
        self.reply(f"I1|{nonce or self.a.pending.nonce}|{guid}|{item}|{remaining}|{needed}|{owned}|{required}|{state}")

    def end(self, nonce=None, guid=GUID, state="checked", count=1):
        self.reply(f"E1|{nonce or self.a.pending.nonce}|{guid}|{state}|{count}")

    def complete(self, state="checked", count=1):
        self.header(state=state, count=count)
        if count:
            self.row()
        self.end(state=state, count=count)

    def lines(self):
        return "\n".join(self.a.Lines().values())

    def tooltip(self):
        return "\n".join(self.g.GameTooltip.lines.values())

    def test_standalone_addon_uses_exact_hex_guid_and_only_read_only_addon_whisper(self):
        self.inspect()
        record = dict(self.g.sent[1])
        self.assertEqual(record["text"].split("|")[2], GUID)
        self.assertEqual(record["prefix"], "VESPERLOOT")
        self.assertEqual(record["channel"], "WHISPER")
        self.assertEqual(record["target"], "Vesper")
        self.assertLessEqual(len(record["prefix"]) + 1 + len(record["text"]), 255)
        self.assertFalse(self.a.panel.mouse)
        self.assertEqual(self.g.Mangosbot.untouched, "ordinary companions")
        self.assertIn("## Interface: 30300", (ADDON / "VesperLoot.toc").read_text())

    def test_missing_optional_word_wrap_api_still_loads_and_renders_read_only_hints(self):
        self.load_addon(without_word_wrap=True)
        self.inspect()
        self.complete()
        self.assertTrue(self.a.panel.IsShown(self.a.panel))
        self.assertIn("Thaelis's Head - available for Vesper", self.lines())
        self.assertFalse(self.a.panel.mouse)

    def test_rows_commit_atomically_and_update_existing_native_tooltip(self):
        self.inspect()
        self.g.GameTooltip.SetUnit(self.g.GameTooltip, "target")
        self.header(); self.row()
        self.assertNotIn("available for Vesper", self.lines())
        self.end()
        self.assertIn("Thaelis's Head - available for Vesper (0/1; needs 1, here 1)", self.lines())
        self.assertIn("Thaelis the Hungerer", self.lines())
        self.assertIn("Native tooltip:", self.tooltip())
        self.assertIn("available for Vesper", self.tooltip())
        self.assertEqual(self.tooltip().count("Vesper quest loot"), 1)

    def test_authoritative_row_states_do_not_confuse_no_longer_needed_with_collected(self):
        self.inspect(); self.header(count=5)
        for i, state in enumerate(["available", "not_needed", "collected", "unavailable", "unknown"]):
            self.row(item=21781+i, needed=0 if state=="not_needed" else 1,
                     owned=1 if state=="not_needed" else 0, state=state)
        self.end(count=5)
        text = self.lines()
        for label in ["available for Vesper", "not currently needed", "already collected from this corpse",
                      "not available for Vesper", "availability unknown"]:
            self.assertIn(label, text)
        self.assertIn("Item #21782", text)

    def test_complete_empty_checked_reply_is_distinct_from_unknown_and_partial(self):
        for state in ["checked", "unknown", "unavailable", "partial"]:
            with self.subTest(state=state):
                self.setUp(); self.inspect(); self.complete(state=state, count=0)
                self.assertEqual("No matching quest loot" in self.lines(), state=="checked")
                if state=="partial": self.assertIn("other items remain unknown", self.lines())

    def test_partial_positive_rows_remain_explicitly_partial(self):
        self.inspect(); self.complete(state="partial")
        self.assertIn("available for Vesper", self.lines())
        self.assertIn("Partial result", self.lines())

    def test_spoofed_sender_wrong_realm_channel_prefix_nonce_and_guid_are_ignored(self):
        nonce=self.inspect()
        for sender, channel, prefix, n, guid in [
            ("Other", "WHISPER", "VESPERLOOT", nonce, GUID),
            ("Vesper-OtherRealm", "WHISPER", "VESPERLOOT", nonce, GUID),
            ("VesperExtra", "WHISPER", "VESPERLOOT", nonce, GUID),
            ("Vesper", "PARTY", "VESPERLOOT", nonce, GUID),
            ("Vesper", "WHISPER", "OTHER", nonce, GUID),
            ("Vesper", "WHISPER", "VESPERLOOT", "oldnonce", GUID),
            ("Vesper", "WHISPER", "VESPERLOOT", nonce, OTHER)]:
            self.reply(f"R1|{n}|{guid}|checked|0", sender, channel, prefix)
            self.assertIsNone(self.a.pending.rows)
        self.reply(f"R1|{nonce}|{GUID}|checked|0", "Vesper-AzerothCore")
        self.reply(f"E1|{nonce}|{GUID}|checked|0", "Vesper-AzerothCore")
        self.assertIsNotNone(self.a.data)

    def test_target_switch_discards_old_frames_and_obeys_global_throttle(self):
        old=self.inspect()
        self.g.units.target.guid=OTHER
        self.event("PLAYER_TARGET_CHANGED")
        self.assertEqual(len(self.g.sent),1)
        self.tick(1.1)
        nonce=self.a.pending.nonce
        self.assertNotEqual(nonce,old)
        self.reply(f"R1|{old}|{GUID}|checked|0")
        self.assertIsNone(self.a.pending.rows)
        self.header(guid=OTHER,count=0);self.end(guid=OTHER,count=0)
        self.assertEqual(self.a.focus.guid,OTHER)

    def test_malformed_truncated_duplicate_and_out_of_order_frames_never_display_rows(self):
        bads=["I1|{n}|{g}|21781|1|1|0|1|available", "E1|{n}|{g}|checked|0",
              "R1|{n}|{g}|checked|9", "R1|{n}|{g}|unknown|1", "R1|{n}|{g}|checked",
              "R1|{n}|{g}|checked|0|extra", "R1|{n}|{g}|checked|"+"x"*250]
        for template in bads:
            with self.subTest(template=template[:40]):
                self.setUp(); nonce=self.inspect();self.reply(template.format(n=nonce,g=GUID))
                self.assertEqual(self.a.status,"unknown")
                self.assertIsNone(self.a.data)
        for value in ["-1","01","1.0","true","4294967296","١"]:
            with self.subTest(value=value):
                self.setUp();nonce=self.inspect();self.header()
                self.reply(f"I1|{nonce}|{GUID}|{value}|1|1|0|1|available")
                self.assertEqual(self.a.status,"unknown")
        self.setUp();self.inspect();self.header(count=2);self.row();self.row()
        self.assertEqual(self.a.status,"unknown")
        self.setUp();self.inspect();self.header();self.end()
        self.assertEqual(self.a.status,"unknown")
        self.setUp();self.inspect();self.header();self.header()
        self.assertEqual(self.a.status,"unknown")

    def test_impossible_available_row_is_not_committed(self):
        for changes in [{"remaining":0},{"needed":0},{"owned":1},{"state":"invented"}]:
            with self.subTest(changes=changes):
                self.setUp();self.inspect();self.header();self.row(**changes)
                self.assertEqual(self.a.status,"unknown")

    def test_timeout_and_visible_ttl_expiry_remove_stale_positive_tooltip(self):
        self.inspect();self.g.GameTooltip.SetUnit(self.g.GameTooltip,"target")
        self.tick(3.1)
        self.assertIn("Unknown",self.tooltip())
        self.assertIsNone(self.a.pending)
        self.setUp();self.inspect();self.g.GameTooltip.SetUnit(self.g.GameTooltip,"target");self.complete()
        self.assertIn("available for Vesper",self.tooltip())
        self.tick(5.1)
        self.assertNotIn("available for Vesper",self.tooltip())
        self.assertIsNotNone(self.a.pending)
        self.assertEqual(len(self.g.sent),2)

    def test_role_or_group_loss_clears_visible_hints_and_pending_authorization(self):
        for field,value in [("leader",False),("partyCount",0)]:
            with self.subTest(field=field):
                self.setUp();self.inspect();self.g.GameTooltip.SetUnit(self.g.GameTooltip,"target");self.complete()
                setattr(self.g,field,value);self.event("PARTY_MEMBERS_CHANGED")
                self.assertFalse(self.a.panel.IsShown(self.a.panel))
                self.assertIsNone(self.a.pending)
                self.assertNotIn("available for Vesper",self.tooltip())

    def test_loot_close_hides_unbound_panel_but_keeps_explicit_target_inspection(self):
        self.inspect();self.complete();self.event("LOOT_CLOSED")
        self.assertTrue(self.a.panel.IsShown(self.a.panel))
        self.g.units.target=None;self.event("LOOT_CLOSED")
        self.assertFalse(self.a.panel.IsShown(self.a.panel))
        self.assertIsNone(self.a.pending)

    def test_loot_panel_identifies_inspected_mouseover_without_claiming_native_window_source(self):
        self.g.units.mouseover=self.lua.table_from({"guid":OTHER,"name":"A Different Fallen Creature","dead":True})
        self.g.LootFrame.Show(self.g.LootFrame);self.event("LOOT_OPENED")
        self.assertEqual(self.a.focus.guid,OTHER)
        self.assertIn("Inspected corpse: A Different Fallen Creature",self.lines())
        self.assertNotIn("LootFrame source",self.lines())

    def test_alive_target_death_and_full_mob_name_and_player_corpse(self):
        self.g.units.target.dead=False;self.event("PLAYER_TARGET_CHANGED")
        self.assertEqual(len(self.g.sent),0)
        self.g.units.target.dead=True;self.g.units.target.name="The Wretched's Fallen Apprentice"
        self.tick(.3)
        self.assertEqual(len(self.g.sent),1)
        self.assertIn("The Wretched's Fallen Apprentice",self.lines())
        self.g.units.target.player=True;self.tick(.3)
        self.assertFalse(self.a.panel.IsShown(self.a.panel))

    def test_repeated_tooltip_events_do_not_spam_queries_or_duplicate_hint_sections(self):
        for _ in range(20): self.g.GameTooltip.SetUnit(self.g.GameTooltip,"target")
        self.assertEqual(len(self.g.sent),1)
        self.assertEqual(self.tooltip().count("Vesper quest loot"),1)
        self.complete();self.event("LOOT_SLOT_CLEARED")
        self.assertEqual(len(self.g.sent),1)
        self.tick(1.1)
        self.assertEqual(len(self.g.sent),2)

    def test_nonleader_or_missing_vesper_or_invalid_guid_cannot_query(self):
        for code in ["leader=false", "units.party1.name='Someone Else'", "units.target.guid='0x0000000000000000'",
                     "units.target.guid='17379391229602595296'", "units.target.guid='0x1234'"]:
            with self.subTest(code=code):
                self.setUp();self.lua.execute(code);self.event("PLAYER_TARGET_CHANGED")
                self.assertEqual(len(self.g.sent),0)

    def test_offline_vesper_shows_unknown_without_whispers_and_reconnects_freshly(self):
        self.g.connected=False;self.event("PLAYER_TARGET_CHANGED")
        self.assertIn("Vesper is offline",self.lines())
        self.assertEqual(len(self.g.sent),0)
        self.tick(20)
        self.assertEqual(len(self.g.sent),0)
        self.g.connected=True;self.tick(.3)
        self.assertEqual(len(self.g.sent),1)
        self.complete()
        self.g.GameTooltip.SetUnit(self.g.GameTooltip,"target")
        self.g.connected=False;self.tick(.3)
        self.assertIsNone(self.a.data)
        self.assertIn("Vesper is offline",self.tooltip())
        self.assertNotIn("available for Vesper",self.tooltip())
        self.assertEqual(len(self.g.sent),1)


if __name__ == "__main__":
    unittest.main()
