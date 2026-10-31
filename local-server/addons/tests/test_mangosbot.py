"""Offline Lua 5.1 contract tests; no game, network, processes, or model calls."""
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "addon-integration/test-tools"))
from lupa.lua51 import LuaRuntime

ADDON = ROOT / "addons/Mangosbot"


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True, register_eval=False, register_builtins=False)
        self.lua.execute("""
            os = nil
            io = nil
            sent = {}
            messages = {}
            clock = 0
            DEFAULT_CHAT_FRAME = { AddMessage = function(self, text) table.insert(messages, text) end }
            function GetTime() return clock end
            function UnitName(unit) if unit == 'player' then return 'Aurenne' end end
            function SendChatMessage(text, channel, language, target)
                table.insert(sent, {text=text, channel=channel, language=language, target=target})
            end
            function SendAddonMessage() error('Addon transport is forbidden in these tests') end
        """)
        self.lua.execute((ADDON / "MangosbotAcore.lua").read_text(encoding="utf-8-sig"))
        self.c = self.lua.globals().MangosbotAcore
        self.parse("Bot roster: +Tankus Warrior, +Priestess Priest, -Sleepy Mage")

    def parse(self, text):
        return self.c.ParseRoster(text)

    def tick(self, elapsed=0.35):
        self.lua.globals().clock += elapsed
        self.c.Tick(elapsed)

    def flush(self, rounds=30):
        for _ in range(rounds):
            self.tick()

    def sent(self):
        return [dict(record) for record in self.lua.globals().sent.values()]

    @staticmethod
    def success(value):
        return value[0] if isinstance(value, tuple) else value

    def test_roster_is_authoritative_and_preserves_no_removed_bot(self):
        self.assertTrue(self.parse("Bot roster: +Tankus Warrior, -Fresh Rogue"))
        self.assertIsNone(self.c.bots.Priestess)
        self.assertIsNone(self.c.bots.Sleepy)
        self.assertTrue(self.c.bots.Tankus.online)
        self.assertFalse(self.c.bots.Fresh.online)

    def test_roster_deduplicates_and_excludes_vesper_and_self(self):
        self.assertTrue(self.parse(
            "Bot roster: +Tankus Warrior, +Tankus Warrior, +Vesper Paladin, +vesper Paladin, +Aurenne Hunter"
        ))
        self.assertEqual(list(self.c.bots.keys()), ["Tankus"])

    def test_empty_roster_clears_previous_entries(self):
        self.assertTrue(self.parse("Bot roster: "))
        self.assertEqual(list(self.c.bots.keys()), [])

    def test_offline_and_reconnect_invalidate_old_observed_role_and_spec(self):
        self.c.HandleReply("Picking prot pve", "Tankus")
        self.c.HandleReply("Combat Strategies: prot, tank assist", "Tankus")
        self.assertEqual(self.c.GetRole("Tankus"), "tank")
        self.assertEqual(self.c.bots.Tankus.spec, "prot pve")
        self.parse("Bot roster: -Tankus Warrior, +Priestess Priest")
        self.assertEqual(self.c.GetRole("Tankus"), "unknown")
        self.assertIsNone(self.c.bots.Tankus.spec)
        self.assertIsNone(self.c.bots.Tankus.combat_strategies)
        self.parse("Bot roster: +Tankus Warrior, +Priestess Priest")
        self.assertEqual(self.c.GetRole("Tankus"), "unknown")

    def test_non_roster_message_does_not_replace_ownership(self):
        self.assertFalse(self.parse("Formation: close"))
        self.assertIsNotNone(self.c.bots.Tankus)

    def test_invalid_roster_does_not_partially_mutate_previous_state(self):
        self.assertTrue(self.c.bots.Tankus.online)
        self.assertFalse(self.parse("Bot roster: -Tankus Warrior, malformed"))
        self.assertTrue(self.c.bots.Tankus.online)
        self.assertIsNotNone(self.c.bots.Priestess)

    def test_admin_commands_use_current_namespace(self):
        for verb, argument in (("list", None), ("add", "Sleepy"), ("remove", "Tankus"), ("addclass", "priest")):
            self.assertTrue(self.success(self.c.SendAdmin(verb, argument)))
        self.flush()
        self.assertEqual([record["text"] for record in self.sent()], [
            ".playerbots bot list", ".playerbots bot add Sleepy", ".playerbots bot remove Tankus",
            ".playerbots bot addclass priest",
        ])
        self.assertTrue(all(record["channel"] == "SAY" for record in self.sent()))

    def test_admin_rejects_unknown_verb_and_injected_arguments(self):
        for verb, argument in (("delete", "Tankus"), ("addclass", "priest\n.server shutdown"),
                               ("add", "Vesper"), ("remove", "Vesper"), ("add", "Stranger")):
            self.assertFalse(self.success(self.c.SendAdmin(verb, argument)), (verb, argument))
        self.flush()
        self.assertEqual(self.sent(), [])

    def test_bot_commands_are_plain_whispers_to_owned_online_bot(self):
        self.assertTrue(self.success(self.c.SendBot("Tankus", "follow")))
        self.flush()
        self.assertEqual(self.sent(), [{"text": "follow", "channel": "WHISPER", "target": "Tankus"}])

    def test_unknown_offline_human_and_vesper_cannot_receive_commands(self):
        for name in ("Sleepy", "Stranger", "Aurenne", "Vesper", "vesper"):
            self.assertFalse(self.success(self.c.SendBot(name, "follow")), name)
            self.assertFalse(self.success(self.c.Query(name)), name)
        self.flush()
        self.assertEqual(self.sent(), [])

    def test_bot_command_rejects_injected_lines_and_legacy_transport_prefix(self):
        for command in ("follow\n.server shutdown", "follow\rstay", "#a co +prot", ".server shutdown"):
            self.assertFalse(self.success(self.c.SendBot("Tankus", command)), command)
        self.flush()
        self.assertEqual(self.sent(), [])

    def test_replies_never_create_controlled_entries(self):
        for name in ("Stranger", "Aurenne", "Vesper", "vesper", "Sleepy"):
            self.assertFalse(self.success(self.c.HandleReply("Combat Strategies: prot, tank assist", name)), name)
        self.assertIsNone(self.c.bots.Stranger)
        self.assertIsNone(self.c.bots.Vesper)
        self.assertFalse(self.c.bots.Sleepy.online)

    def test_queued_command_is_revalidated_after_roster_change(self):
        self.assertTrue(self.success(self.c.SendBot("Tankus", "attack")))
        self.parse("Bot roster: +Priestess Priest")
        self.flush()
        self.assertEqual(self.sent(), [])

    def test_queue_uses_actual_elapsed_and_never_catches_up_in_a_burst(self):
        for command in ("follow", "stay", "talents"):
            self.c.SendBot("Tankus", command)
        self.tick(30)
        self.assertEqual(len(self.sent()), 1)
        for _ in range(20):
            self.tick(0)
        self.assertEqual(len(self.sent()), 1)
        self.tick(0.20)
        self.assertEqual(len(self.sent()), 1)
        self.tick(0.16)
        self.assertEqual(len(self.sent()), 2)

    def test_tank_role_waits_for_exact_spec_acknowledgement(self):
        self.assertTrue(self.success(self.c.RequestRole("Tankus", "tank")))
        self.flush(5)
        self.assertEqual([record["text"] for record in self.sent()], ["talents spec prot pve"])
        self.assertTrue(self.c.bots.Tankus.role_pending)
        self.c.HandleReply("Picking fury pve", "Tankus")
        self.flush(3)
        self.assertEqual(len(self.sent()), 1)
        self.c.HandleReply("Picking prot pve", "Tankus")
        self.flush()
        texts = [record["text"] for record in self.sent()]
        self.assertTrue(any(text.startswith("co ") and "+prot" in text for text in texts))
        self.assertFalse(any("autogear" in text or "init=" in text for text in texts))

    def test_role_cannot_target_unsupported_class_human_offline_or_vesper(self):
        self.parse("Bot roster: +Hunterbot Hunter, +Tankus Warrior, -Sleepy Priest")
        for name, role in (("Hunterbot", "tank"), ("Stranger", "tank"), ("Sleepy", "heal"),
                           ("Vesper", "tank"), ("Tankus", "tank\n.server shutdown")):
            self.assertFalse(self.success(self.c.RequestRole(name, role)), (name, role))
        self.flush()
        self.assertEqual(self.sent(), [])

    def test_only_observed_combat_strategies_establish_role(self):
        self.assertEqual(self.c.GetRole("Tankus"), "unknown")
        self.c.RequestRole("Tankus", "tank")
        self.flush(3)
        self.assertNotEqual(self.c.GetRole("Tankus"), "tank")
        self.c.HandleReply("Picking prot pve", "Tankus")
        self.assertNotEqual(self.c.GetRole("Tankus"), "tank")
        self.c.HandleReply("Combat Strategies: prot, tank assist", "Tankus")
        self.assertEqual(self.c.GetRole("Tankus"), "tank")

    def test_rejected_spec_does_not_apply_combat_role(self):
        self.c.RequestRole("Tankus", "tank")
        self.flush(3)
        self.c.HandleReply("Spec prot pve not found", "Tankus")
        self.flush()
        self.assertFalse(self.c.bots.Tankus.role_pending)
        self.assertTrue(self.c.bots.Tankus.last_error)
        self.assertEqual([record["text"] for record in self.sent()], ["talents spec prot pve"])

    def test_role_timeout_never_reports_success_or_sends_combat_change(self):
        self.c.RequestRole("Tankus", "tank")
        self.tick()
        self.tick(120)
        self.flush()
        self.assertFalse(self.c.bots.Tankus.role_pending)
        self.assertTrue(self.c.bots.Tankus.last_error)
        self.assertNotEqual(self.c.GetRole("Tankus"), "tank")
        self.assertEqual([record["text"] for record in self.sent()], ["talents spec prot pve"])


UI_FIXTURE = """
    frames = {}
    SlashCmdList = {}
    RAID_CLASS_COLORS = {}
    for _, class in ipairs({'WARRIOR','PALADIN','PRIEST','HUNTER','ROGUE','MAGE','SHAMAN','DRUID','WARLOCK','DEATHKNIGHT'}) do
        RAID_CLASS_COLORS[class] = {r=0.6,g=0.6,b=0.9}
    end
    local methods = {}
    function methods:SetScript(name, callback) self.scripts[name] = callback end
    function methods:GetScript(name) return self.scripts[name] end
    function methods:RegisterEvent(name)
        local valid = {ADDON_LOADED=true,PLAYER_LOGIN=true,CHAT_MSG_SYSTEM=true,CHAT_MSG_WHISPER=true,
            CHAT_MSG_ADDON=true,PARTY_MEMBERS_CHANGED=true,PLAYER_TARGET_CHANGED=true,PLAYER_LOGOUT=true,
            RAID_ROSTER_UPDATE=true}
        assert(valid[name], 'Invalid WotLK event: '..tostring(name))
        self.events[name] = true
    end
    function methods:UnregisterEvent(name) self.events[name] = nil end
    function methods:SetText(text) self.text = text end
    function methods:GetText() return self.text or '' end
    function methods:SetFormattedText(fmt, ...) self.text = string.format(fmt, ...) end
    function methods:SetWidth(width) self.width = width end
    function methods:SetHeight(height) self.height = height end
    function methods:GetWidth() return self.width or 100 end
    function methods:GetHeight() return self.height or 20 end
    function methods:GetName() return self.name end
    function methods:GetParent() return self.parent end
    function methods:GetID() return self.id or 0 end
    function methods:SetID(id) self.id = id end
    function methods:GetPoint() return 'CENTER',UIParent,'CENTER',0,0 end
    function methods:GetEffectiveScale() return 1 end
    function methods:GetStringWidth() return #(self.text or '') * 7 end
    function methods:GetStringHeight() return 14 end
    function methods:Show() self.shown = true; if self.scripts.OnShow then self.scripts.OnShow(self) end end
    function methods:Hide() self.shown = false; if self.scripts.OnHide then self.scripts.OnHide(self) end end
    function methods:IsShown() return self.shown end
    function methods:IsVisible() return self.shown end
    function methods:Enable() self.enabled = true end
    function methods:Disable() self.enabled = false end
    function methods:IsEnabled() return self.enabled end
    function methods:SetChecked(value) self.checked = value end
    function methods:GetChecked() return self.checked end
    function methods:GetVerticalScroll() return self.scroll or 0 end
    function methods:SetVerticalScroll(value) self.scroll = value end
    function methods:GetVerticalScrollRange() return 0 end
    for _, method in ipairs({'SetPoint','ClearAllPoints','SetAllPoints','SetBackdrop','SetBackdropColor',
        'SetBackdropBorderColor','SetFrameStrata','SetFrameLevel','SetMovable','SetClampedToScreen',
        'EnableMouse','EnableMouseWheel','RegisterForDrag','RegisterForClicks','StartMoving','StopMovingOrSizing',
        'SetFont','SetFontObject','SetTextColor','SetJustifyH','SetJustifyV','SetWordWrap','SetNonSpaceWrap',
        'SetNormalTexture','SetHighlightTexture','SetPushedTexture','SetDisabledTexture','SetTexture','SetTexCoord',
        'SetVertexColor','SetAlpha','SetAutoFocus','SetMaxLetters','SetNumeric','SetMultiLine','SetTextInsets',
        'SetFocus','ClearFocus','HighlightText','SetScrollChild','UpdateScrollChildRect','SetOwner','AddLine',
        'AddDoubleLine','ClearLines','SetMinResize','SetMaxResize','SetResizable','SetToplevel','SetHitRectInsets'}) do
        methods[method] = function() end
    end
    function newWidget(kind, name, parent)
        local widget = setmetatable({kind=kind,name=name,parent=parent,scripts={},events={},shown=true,enabled=true},
            {__index=methods})
        if name then
            assert(_G[name] == nil, 'Duplicate named widget: '..name)
            _G[name] = widget
        end
        table.insert(frames, widget)
        return widget
    end
    function methods:CreateFontString(name) return newWidget('FontString', name, self) end
    function methods:CreateTexture(name) return newWidget('Texture', name, self) end
    function CreateFrame(kind, name, parent) return newWidget(kind, name, parent) end
    UIParent = newWidget('Frame', 'UIParent')
    GameTooltip = newWidget('Frame', 'GameTooltip')
    GameFontNormal = newWidget('FontString', 'GameFontNormal')
    GameFontHighlight = newWidget('FontString', 'GameFontHighlight')
    UISpecialFrames = {}
    function GetCursorPosition() return 640,360 end
    function GetScreenWidth() return 1280 end
    function GetScreenHeight() return 720 end
    function GetNumPartyMembers() return 0 end
    function GetNumRaidMembers() return 0 end
    unitNames = {}
    function UnitName(unit) if unit == 'player' then return 'Aurenne' end return unitNames[unit] end
    function UnitExists() return false end
    function UnitIsPlayer() return true end
    function UnitIsEnemy() return false end
    function UnitClass() return 'Hunter','HUNTER' end
    function InviteUnit(name) error('No live invitations are allowed in the smoke test: '..tostring(name)) end
    function GetLocale() return 'enUS' end
    function getglobal(name) return _G[name] end
    function FauxScrollFrame_Update() end
    function FauxScrollFrame_GetOffset() return 0 end
    function FauxScrollFrame_OnVerticalScroll() end
    function PanelTemplates_SetNumTabs() end
    function PanelTemplates_SetTab() end
    function ChatFrame_OpenChat() end
    function IsShiftKeyDown() return false end
    function IsControlKeyDown() return false end
    function PlaySound() end
    function UIDropDownMenu_SetWidth(frame, width) frame.menuWidth = width end
    function UIDropDownMenu_SetText(frame, text) frame.menuText = text end
    function UIDropDownMenu_Initialize(frame, callback) frame.menuInitializer = callback; callback() end
    function UIDropDownMenu_CreateInfo() return {} end
    function UIDropDownMenu_AddButton() end
    function CloseDropDownMenus() end
    tinsert = table.insert
    tremove = table.remove
    strlower = string.lower
    strupper = string.upper
"""


class UISmokeTests(unittest.TestCase):
    setUp = ProtocolTests.setUp
    parse = ProtocolTests.parse
    tick = ProtocolTests.tick
    flush = ProtocolTests.flush
    sent = ProtocolTests.sent

    def load_ui(self):
        self.lua.execute(UI_FIXTURE)
        self.lua.execute((ADDON / "Mangosbot.lua").read_text(encoding="utf-8-sig"))

    def event_frame(self):
        return next(frame for frame in self.lua.globals().frames.values() if frame.scripts.OnEvent is not None)

    def dispatch(self, event, *args):
        frame = self.event_frame()
        frame.scripts.OnEvent(frame, event, *args)

    def click(self, text):
        button = next(frame for frame in self.lua.globals().frames.values()
                      if frame.kind == "Button" and frame.text == text)
        self.assertTrue(button.enabled, text)
        button.scripts.OnClick(button)

    def test_load_is_quiet_and_slash_open_requests_roster(self):
        self.load_ui()
        self.assertEqual(self.sent(), [])
        self.dispatch("ADDON_LOADED", "Mangosbot")
        self.assertEqual(self.sent(), [])
        self.lua.globals().SlashCmdList.MANGOSBOT("")
        self.assertTrue(self.lua.globals().MangosbotFrame.shown)
        self.flush()
        self.assertEqual([record["text"] for record in self.sent()], [".playerbots bot list"])

    def test_cached_old_toc_loads_main_without_preload_then_xml_without_duplicates(self):
        self.lua.globals().MangosbotAcore = None
        self.load_ui()
        self.c = self.lua.globals().MangosbotAcore
        self.assertIsNotNone(self.c)
        self.parse("Bot roster: +Tankus Warrior, +Vesper Paladin")
        first_frame = self.lua.globals().MangosbotFrame
        self.lua.execute((ADDON / "Mangosbot.lua").read_text(encoding="utf-8-sig"))
        self.assertTrue(self.lua.eval("function(other) return MangosbotFrame == other end")(first_frame))
        self.assertEqual(sum(frame.name == "MangosbotFrame" for frame in self.lua.globals().frames.values()), 1)
        event_frames = [frame for frame in self.lua.globals().frames.values() if frame.scripts.OnEvent is not None]
        self.assertEqual(len(event_frames), 1)
        self.assertIsNotNone(self.c.bots.Tankus)
        self.assertIsNone(self.c.bots.Vesper)
        self.assertEqual(self.sent(), [])
        self.dispatch("ADDON_LOADED", "Mangosbot")
        self.lua.globals().SlashCmdList.MANGOSBOT("")
        self.flush()
        self.assertEqual([record["text"] for record in self.sent()], [".playerbots bot list"])

    def test_embedded_protocol_is_exactly_the_separate_protocol_source(self):
        main = (ADDON / "Mangosbot.lua").read_text(encoding="utf-8-sig")
        start = "-- BEGIN EMBEDDED AZEROTHCORE PROTOCOL\n"
        end = "-- END EMBEDDED AZEROTHCORE PROTOCOL"
        self.assertEqual(main.count(start), 1)
        self.assertEqual(main.count(end), 1)
        embedded = main.split(start, 1)[1].split(end, 1)[0]
        protocol = (ADDON / "MangosbotAcore.lua").read_text(encoding="utf-8-sig")
        self.assertEqual(embedded, protocol.rstrip("\n") + "\n")

    def test_ui_loads_with_wotlk_callback_arguments_and_no_global_arg_values(self):
        self.load_ui()
        self.assertIsNotNone(self.lua.globals().MangosbotFrame)
        event_frames = [frame for frame in self.lua.globals().frames.values() if frame.scripts.OnEvent is not None]
        self.assertEqual(len(event_frames), 1)
        frame = event_frames[0]
        frame.scripts.OnEvent(frame, "CHAT_MSG_SYSTEM", "Bot roster: +Tankus Warrior, +Vesper Paladin")
        frame.scripts.OnEvent(frame, "CHAT_MSG_WHISPER", "Combat Strategies: prot, tank assist", "Tankus")
        frame.scripts.OnEvent(frame, "CHAT_MSG_WHISPER", "Hello", "Vesper")
        self.assertIsNone(self.c.bots.Vesper)
        self.assertIsNotNone(self.c.bots.Tankus)

    def test_targeting_human_or_vesper_never_queues_inspection(self):
        self.load_ui()
        self.lua.globals().MangosbotFrame.Show(self.lua.globals().MangosbotFrame)
        for name in ("Vesper", "Stranger", "Aurenne"):
            self.lua.globals().unitNames["target"] = name
            self.dispatch("PLAYER_TARGET_CHANGED")
        self.flush()
        self.assertEqual(self.sent(), [])

    def test_selecting_online_row_queries_that_bot(self):
        self.load_ui()
        row = next(frame for frame in self.lua.globals().frames.values() if frame.botName == "Tankus")
        row.scripts.OnClick(row)
        self.flush()
        self.assertTrue(self.sent())
        self.assertTrue(all(record["channel"] == "WHISPER" and record["target"] == "Tankus"
                            for record in self.sent()))

    def test_bulk_party_order_excludes_vesper_humans_and_offline_alts(self):
        self.load_ui()
        self.lua.execute("""
            function GetNumPartyMembers() return 4 end
            unitNames.party1 = 'Vesper'
            unitNames.party2 = 'Tankus'
            unitNames.party3 = 'Stranger'
            unitNames.party4 = 'Sleepy'
        """)
        self.click("Party follow")
        self.flush()
        self.assertEqual(self.sent(), [{"text": "follow", "channel": "WHISPER", "target": "Tankus"}])

    def test_pages_keep_all_forty_raid_members_reachable(self):
        names = ["Bot" + chr(ord("a") + index // 26) + chr(ord("a") + index % 26) for index in range(40)]
        self.parse("Bot roster: " + ", ".join("+" + name + " Warrior" for name in names))
        self.load_ui()
        self.lua.execute("function GetNumRaidMembers() return 40 end")
        for index, name in enumerate(names, 1):
            self.lua.globals().unitNames["raid" + str(index)] = name
        seen = set()
        for _ in range(4):
            seen.update(frame.botName for frame in self.lua.globals().frames.values()
                        if frame.kind == "Button" and frame.botName is not None and frame.shown)
            self.click(">")
        self.assertEqual(seen, set(names))
        self.click("Party stay")
        self.flush(45)
        self.assertEqual({record["target"] for record in self.sent()}, set(names))
        self.assertTrue(all(record["text"] == "stay" and record["channel"] == "WHISPER"
                            for record in self.sent()))

    def test_toc_loads_every_lua_source_once(self):
        included = []
        for line in (ADDON / "Mangosbot.toc").read_text(encoding="utf-8-sig").splitlines():
            name = line.strip()
            if not name or name.startswith("#"):
                continue
            if name.lower().endswith(".xml"):
                document = ET.parse(ADDON / name)
                for node in document.iter():
                    if node.tag.split("}")[-1] == "Script":
                        script = node.get("file") or node.get("File")
                        if script:
                            included.append(script)
            elif name.lower().endswith(".lua"):
                included.append(name)
        self.assertEqual(len(included), len(set(included)))
        self.assertEqual(included.count("Mangosbot.lua"), 1)
        self.assertEqual(included.count("MangosbotAcore.lua"), 0)
        self.assertEqual(included, ["Mangosbot.lua"])


if __name__ == "__main__":
    unittest.main()
