"""Run the actual Auctioneer posting queue with mocked WoW APIs in Lua 5.1.

No game requests, auctions, inventory changes or model calls are made. The
StartAuction mock records the API contract; only an explicit fixture bag update
can satisfy the existing confirmation path.
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
ADDON = Path(os.environ.get("AUCTIONEER_ADDON_PATH", str(
    ROOT / ("baseline" if BASELINE else "stage") / "Auc-Advanced")))


class PostingQueue:
    def __init__(self, size=1):
        self.lua = LuaRuntime(unpack_returned_tuples=True,
                             register_eval=False, register_builtins=False)
        self.lua.execute(r'''
            os, io = nil, nil
            floor, max, tinsert, tremove = math.floor, math.max, table.insert, table.remove
            ITEM_SOULBOUND, ITEM_BIND_QUEST, ITEM_BIND_ON_PICKUP = "Soulbound", "Quest", "Pickup"
            ITEM_CONJURED, ITEM_ACCOUNTBOUND, ITEM_BIND_TO_ACCOUNT = "Conjured", "Account", "Account2"
            YES, NO, UIParent = "Yes", "No", {}
            StaticPopupDialogs = {}
            clock, stack_size, prepared_size = 0, 1, nil
            bag_link = "|cff1eff00|Hitem:14094:0:0:0:0:0:1800:0:10|h[Beaded Wraps of Arcane Wrath]|h|r"
            cursor, auction_slot = false, false
            starts, results, notices = {}, {}, {}
            function CreateFrame()
              return {Show=function() end, Hide=function() end, SetScript=function() end}
            end
            AucAdvanced = {
              Const = {},
              Print = function() end,
              Debug = {DebugPrint=function() end},
              localizations = function(key) return key end,
              RegisterRevision = function() end,
              Settings = {GetSetting=function() return false end},
              SendProcessorMessage = function(event, ...)
                if event == "postresult" then
                  results[#results+1] = {n=select("#", ...), ...}
                end
              end,
              API = {DecodeSig=function() return 14094, 1800, 0, 0 end}
            }
            AuctionFrame = {IsVisible=function() return true end}
            function GetTime() return clock end
            function GetNetStats() return 0, 0, 10 end
            function GetContainerItemLink(bag, slot)
              assert(bag == 0 and slot == 1)
              return bag_link
            end
            function GetContainerItemInfo() return "texture", stack_size, false, 2, false end
            function GetAuctionSellItemInfo()
              if auction_slot then return "Beaded Wraps of Arcane Wrath", "texture", stack_size end
            end
            function PickupContainerItem(bag, slot)
              assert(bag == 0 and slot == 1 and bag_link)
              cursor = true
            end
            function CursorHasItem() return cursor end
            function ClickAuctionSellItemButton()
              if cursor then
                cursor, auction_slot = false, true
              end
              -- A pending server operation can keep the sell slot locked.
            end
            function ClearCursor() cursor = false end
            function StartAuction(...)
              assert(auction_slot)
              starts[#starts+1] = {n=select("#", ...), ...}
            end
            function message(text) notices[#notices+1] = text end
        ''')
        self.lua.execute((ADDON / "CorePost.lua").read_text(encoding="utf-8-sig"))
        self.g = self.lua.globals()
        self.g.stack_size = size
        self.lua.execute('''
            post = AucAdvanced.Post
            engine = post.Private
            post.OnLoad("auc-advanced")
            engine.FindOrMakeStack = function(sig, size)
              prepared_size = size
              return 0, 1
            end
            request = engine.NewRequestTable("14094:1800", stack_size, 123, 456, 2)
            engine.QueueInsert(request)
        ''')

    def process(self, seconds=0):
        self.g.clock += seconds
        self.g.engine.ProcessPosts("offline-test")

    def first_call(self):
        row = self.g.starts[1]
        return tuple(row[i] for i in range(1, row.n + 1))


class PostingQueueTests(unittest.TestCase):
    def test_unstackable_random_property_uses_exact_stack_and_one_auction(self):
        q = PostingQueue()
        original_link = q.g.bag_link
        q.process()
        self.assertEqual(q.first_call(), (123, 456, 2, 1, 1))
        self.assertEqual(q.g.prepared_size, 1)
        self.assertEqual(q.g.request[7], original_link)
        self.assertIn(":1800:", q.g.request[7])
        self.assertEqual(q.g.post.GetQueueLen(), 1)
        self.assertEqual(len(q.g.results), 0)

    def test_prepared_stack_n_does_not_become_n_auctions(self):
        q = PostingQueue(size=7)
        q.process()
        self.assertEqual(q.first_call(), (123, 456, 2, 7, 1))
        self.assertEqual(q.g.prepared_size, 7)
        self.assertEqual(len(q.g.starts), 1)
        self.assertEqual(q.g.post.GetQueueLen(), 1)

    def test_submission_does_not_prove_success_until_bag_changes(self):
        q = PostingQueue()
        q.process()
        q.process(1)
        self.assertEqual(q.g.post.GetQueueLen(), 1)
        self.assertEqual(len(q.g.results), 0)
        self.assertEqual(len(q.g.starts), 1)
        q.g.bag_link = None
        q.process(1)
        self.assertEqual(q.g.post.GetQueueLen(), 0)
        self.assertEqual(len(q.g.results), 1)
        self.assertTrue(q.g.results[1][1])
        self.assertEqual(len(q.g.starts), 1)

    def test_unchanged_bag_times_out_without_success_or_automatic_retry(self):
        q = PostingQueue()
        q.process()
        q.process(7)
        self.assertEqual(q.g.post.GetQueueLen(), 0)
        self.assertEqual(len(q.g.results), 1)
        self.assertFalse(q.g.results[1][1])
        self.assertEqual(q.g.results[1][4], "FailTimeout")
        self.assertEqual(len(q.g.notices), 1)
        self.assertIn("Timed out", q.g.notices[1])
        q.process(10)
        self.assertEqual(len(q.g.starts), 1)

    def test_explicit_second_queue_entry_remains_separate(self):
        q = PostingQueue()
        q.process()
        q.lua.execute('''
            second_request = engine.NewRequestTable("14094:1800", 1, 789, 999, 3)
            engine.QueueInsert(second_request)
        ''')
        self.assertEqual(q.g.post.GetQueueLen(), 2)
        q.g.bag_link = None
        q.process(1)
        self.assertEqual(q.g.post.GetQueueLen(), 1)
        self.assertEqual(len(q.g.starts), 1)
        self.assertEqual(q.g.engine.GetQueueIndex(1)[6], q.g.second_request[6])


if __name__ == "__main__":
    unittest.main(verbosity=2)
