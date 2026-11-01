"""Exercise QuestHelper's actual director and delayed notifier under Lua 5.1.

Only WoW/UI/database services are mocked. No game, model, inventory or saved-data
mutation occurs. --baseline runs the same checks against the unfixed director.
"""
from pathlib import Path
import os
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, os.environ.get("LUPA_RUNTIME_PATH", str(
    ROOT.parent / "body-reporting-integration" / "test-tools")))
from lupa.lua51 import LuaRuntime

BASELINE = "--baseline" in sys.argv
if BASELINE:
    sys.argv.remove("--baseline")
ADDON = Path(os.environ.get("QUESTHELPER_ADDON_PATH", str(
    ROOT / ("baseline" if BASELINE else "stage") / "QuestHelper")))


class Director:
    def __init__(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True,
                             register_eval=False, register_builtins=False)
        self.lua.execute(r'''
            os, io = nil, nil
            clock, scans, tracker_rescans = 0, 0, 0
            own_count, required, other_count = 0, 1, 0
            handlers, clusters, messages = {}, {}, {}
            QuestHelper_File, QuestHelper_Loadtime = {}, {}
            QuestHelper_Pref = {solo = true, share = false, track_ocolour = true}
            QuestHelper = {}
            function QuestHelper:Assert(value) assert(value) end
            function QuestHelper:CreateTable() return {} end
            function QuestHelper:ReleaseTable() end
            function QuestHelper:TextOut(text) messages[#messages+1] = text end
            function QuestHelper:nop() end
            function GetTime() return clock end
            function UnitName(unit) if unit == "player" then return "Aurenne" end end
            function UnitLevel() return 10 end
            function GetItemCount() error("Inventory counts must not replace quest facts") end
            floor = math.floor
            QUEST_OBJECTS_FOUND = "%s: %d/%d"
            QUEST_MONSTERS_KILLED = "%s slain: %d/%d"
            QUEST_FACTION_NEEDED = "%s: %s/%s"
            function DB_Ready() return true end
            function DB_GetItem() return nil end
            function DB_ReleaseItem() end
            function QHText(token) return token end
            function QHFormat(token, ...) return token end
            function QH_Timeslice_PushUnyieldable() end
            function QH_Timeslice_PopUnyieldable() end
            function QH_Route_ClusterAdd(row) clusters[#clusters+1] = row end
            function QH_Route_ClusterRemove() end
            function QH_Route_ClusterRequires() end
            function QH_Route_IgnoreCluster() end
            function QH_Route_Filter_Rescan() end
            function QH_Route_SetClusterPriority() end
            function QH_Tracker_SetPin() end
            function QH_Tracker_Unpin() end
            function QH_Tracker_Rescan() tracker_rescans = tracker_rescans+1 end
            function QH_Tooltip_Defer_Add() end
            function QH_Tooltip_Defer_Remove() end
            function QH_Tooltip_Canned_Add() end
            function QH_Tooltip_Canned_Remove() end
            function QuestHelper_ErrorCatcher_ExplicitError() end
            function GetQuestLogTitle(index)
              if index ~= 1 then return nil end
              scans = scans+1
              return "The Party Never Ends", 10, nil, nil, false, false, nil
            end
            function GetQuestLink(index)
              if index == 1 then return "|cffffff00|Hquest:9067:10|h[The Party Never Ends]|h|r" end
            end
            function IsQuestWatched() return true end
            function GetQuestIndexForTimer() return nil end
            function GetNumQuestLeaderBoards() return 2 end
            function GetQuestLogLeaderBoard(objective)
              if objective == 1 then
                return "Suntouched Special Reserve: "..own_count.."/"..required,
                       "item", own_count >= required
              end
              return "Springpaw Appetizers: "..other_count.."/5", "item", other_count >= 5
            end
            function QH_Event(event, callback)
              handlers[event] = handlers[event] or {}
              table.insert(handlers[event], callback)
            end
            function Fire(event, ...)
              for _, callback in ipairs(handlers[event] or {}) do callback(...) end
            end
            function Objective()
              for _, row in ipairs(clusters) do
                if row.target == "Suntouched Special Reserve" then return row end
              end
            end
            function OwnProgress()
              local row = Objective()
              return row.progress.Aurenne[1], row.progress.Aurenne[2]
            end
            function PartyProgress()
              local row = Objective()
              return row.progress.Vesper[1], row.progress.Vesper[2]
            end
        ''')
        for file in ["pattern.lua", "collect_notifier.lua", "director_quest.lua"]:
            self.lua.execute((ADDON / file).read_text(encoding="utf-8-sig"))
        self.g = self.lua.globals()
        self.lua.execute('''
            local api = {Registrar_OnUpdateHook = function(callback) NotifierTick = callback end}
            QH_Collect_Notifier_Init({}, api)
            Fire("QUEST_LOG_UPDATE")
        ''')

    def fire(self, event, *args):
        self.g.Fire(event, *args)

    def advance(self, seconds):
        self.g.clock += seconds
        self.g.NotifierTick()

    def progress(self):
        return self.g.OwnProgress()


class InventoryRefreshTests(unittest.TestCase):
    def test_purchase_refreshes_actual_leaderboard_without_quest_log_event(self):
        c = Director()
        self.assertEqual(c.progress(), (0, 1))
        c.g.own_count = 1
        c.fire("BAG_UPDATE", 0)
        self.assertEqual(c.progress(), (0, 1))
        c.advance(0.11)
        self.assertEqual(c.progress(), (1, 1))

    def test_burst_events_queue_one_scan_after_inventory_settles(self):
        c = Director()
        before = c.g.scans
        for bag in range(5):
            c.fire("BAG_UPDATE", bag)
        c.fire("UNIT_INVENTORY_CHANGED", "player")
        c.g.own_count = 1
        c.advance(0.05)
        self.assertEqual(c.g.scans, before)
        c.advance(0.06)
        self.assertEqual(c.g.scans, before + 1)
        self.assertEqual(c.progress(), (1, 1))
        c.fire("BAG_UPDATE", 0)
        c.advance(0.11)
        self.assertEqual(c.g.scans, before + 2)

    def test_player_inventory_event_refreshes_but_other_units_do_not(self):
        c = Director()
        before = c.g.scans
        c.g.own_count = 1
        c.fire("UNIT_INVENTORY_CHANGED", "party1")
        c.advance(0.11)
        self.assertEqual(c.g.scans, before)
        c.fire("UNIT_INVENTORY_CHANGED", "player")
        c.advance(0.11)
        self.assertEqual(c.progress(), (1, 1))

    def test_item_loss_and_unchanged_leaderboard_keep_authoritative_counts(self):
        c = Director()
        c.fire("BAG_UPDATE", 0)
        c.advance(0.11)
        self.assertEqual(c.progress(), (0, 1))
        c.g.own_count = 1
        c.fire("QUEST_LOG_UPDATE")
        self.assertEqual(c.progress(), (1, 1))
        c.g.own_count = 0
        c.fire("BAG_UPDATE", 0)
        c.advance(0.11)
        self.assertEqual(c.progress(), (0, 1))

    def test_refresh_preserves_remote_party_progress(self):
        c = Director()
        c.lua.execute('''
            local data = {9067, "The Party Never Ends", 10, false, false, false, false, false,
              "Suntouched Special Reserve: 0/1", "item", false,
              "Springpaw Appetizers: 0/5", "item", false}
            local parts = {}
            for i = 1, #data do parts[i] = SerItem(data[i]) end
            QH_InsertCommPacket("Vesper", "q:"..table.concat(parts, ":"))
        ''')
        self.assertEqual(c.g.PartyProgress(), (0, 1))
        c.g.own_count = 1
        c.fire("BAG_UPDATE", 0)
        c.advance(0.11)
        self.assertEqual(c.progress(), (1, 1))
        self.assertEqual(c.g.PartyProgress(), (0, 1))


if __name__ == "__main__":
    unittest.main(verbosity=2)
