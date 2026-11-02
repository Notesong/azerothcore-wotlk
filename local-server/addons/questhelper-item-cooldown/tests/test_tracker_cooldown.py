"""Exercise the staged guard with Lua 5.1 and, when available, exact client UI functions."""
from pathlib import Path
import os
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, os.environ.get('LUPA_RUNTIME_PATH', str(
    ROOT.parent/'body-reporting-integration/test-tools')))
from lupa.lua51 import LuaRuntime

BASELINE = '--baseline' in sys.argv
if BASELINE:
    sys.argv.remove('--baseline')
ADDON = Path(os.environ.get('QUESTHELPER_ADDON_PATH', str(
    ROOT/('baseline' if BASELINE else 'stage')/'QuestHelper')))
CLIENT = Path(os.environ.get('WOW_FRAMEXML_PATH', str(ROOT/'client-framexml')))

# Small UI doubles for the public patch package. A local extracted client takes
# precedence, so installation checks exercise the actual two unsafe comparisons.
FALLBACK = r'''
function CooldownFrame_SetTimer(frame, start, duration, enable)
  local active = math.min(start, duration, enable) > 0
  if not active then frame:Hide(); return end
  frame:SetCooldown(start, duration)
  frame:Show()
end
local function renderQuestCooldown(button)
  local values = {GetQuestLogSpecialItemCooldown(button:GetID())}
  CooldownFrame_SetTimer(_G[button:GetName()..'Cooldown'], values[1], values[2], values[3])
  local shade = values[3] == 0 and values[2] > 0 and .4 or 1
  SetItemButtonTextureVertexColor(button, shade, shade, shade)
end
WatchFrameItem_UpdateCooldown = renderQuestCooldown
function WatchFrameItem_OnEvent(button, event)
  local handlers = {BAG_UPDATE_COOLDOWN = WatchFrameItem_UpdateCooldown}
  if handlers[event] then return handlers[event](button) end
end
function WatchFrameItem_OnShow(button) button:RegisterEvent('BAG_UPDATE_COOLDOWN') end
function WatchFrameItem_OnHide(button) button:UnregisterEvent('BAG_UPDATE_COOLDOWN') end
'''


def client_functions():
    if not (CLIENT/'WatchFrame.lua').is_file() or not (CLIENT/'Cooldown.lua').is_file():
        return FALLBACK
    source = (CLIENT/'WatchFrame.lua').read_text('utf-8-sig')
    chunks = [(CLIENT/'Cooldown.lua').read_text('utf-8-sig')]
    for name, following in (('WatchFrameItem_UpdateCooldown', 'WatchFrameItem_OnLoad'),
            ('WatchFrameItem_OnEvent', 'WatchFrameItem_OnUpdate'),
            ('WatchFrameItem_OnShow', 'WatchFrameItem_OnHide'),
            ('WatchFrameItem_OnHide', 'WatchFrameItem_OnEnter')):
        start = source.index('function '+name+' ')
        chunks.append(source[start:source.index('function '+following+' ', start)])
    return '\n'.join(chunks)


class UI:
    def __init__(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True, register_eval=False, register_builtins=False)
        self.lua.execute(r'''
            os, io = nil, nil
            QuestHelper, QuestHelper_File, QuestHelper_Loadtime = {}, {}, {}
            function GetTime() return 0 end
            data, api_calls, original_calls = {}, 0, 0
            function GetQuestLogSpecialItemCooldown(index)
              api_calls = api_calls + 1
              local row = data[index] or {}
              return row.start, row.duration, row.enable
            end
            function SetItemButtonTextureVertexColor(button, r, g, b) button.tint = {r,g,b} end
            function NewButton(name, id)
              local button = {name=name, id=id, events={}, tint={.4,.4,.4}}
              function button:GetName() return self.name end
              function button:GetID() return self.id end
              function button:RegisterEvent(event) self.events[event]=true end
              function button:UnregisterEvent(event) self.events[event]=nil end
              local cd = {shown=true, hidden=0}
              function cd:Hide() self.shown=false; self.hidden=self.hidden+1 end
              function cd:Show() self.shown=true end
              function cd:SetCooldown(start, duration) self.start=start; self.duration=duration end
              button.cooldown=cd; _G[name..'Cooldown']=cd
              return button
            end
            function Fire(button, event)
              if button.events[event] then WatchFrameItem_OnEvent(button,event) end
            end
        ''')
        self.lua.execute(client_functions())
        self.lua.execute(r'''
            original_timer, original_api = CooldownFrame_SetTimer, GetQuestLogSpecialItemCooldown
            local client_update = WatchFrameItem_UpdateCooldown
            WatchFrameItem_UpdateCooldown = function(self, ...)
              original_calls = original_calls+1; last_self=self; extra_count=select('#',...)
              client_update(self)
              return 'delegated', extra_count
            end
        ''')
        self.source = (ADDON/'tracker.lua').read_text('utf-8-sig')
        self.prefix = self.source[:self.source.index('local debug_output = false')]
        self.lua.execute(self.prefix)
        self.g = self.lua.globals()

    def button(self, name='QH_SpecItem_1', index=1):
        button = self.g.NewButton(name, index)
        self.g.WatchFrameItem_OnShow(button)
        return button

    def values(self, start=None, duration=None, enable=None, index=1):
        self.g.data[index] = self.lua.table_from({'start': start, 'duration': duration, 'enable': enable})

    def update(self, button):
        self.g.Fire(button, 'BAG_UPDATE_COOLDOWN')


class CooldownGuard(unittest.TestCase):
    def test_turn_in_removes_item_before_visible_button_refresh(self):
        ui = UI(); button = ui.button()
        ui.values(100, 30, 1); ui.update(button)
        self.assertTrue(button.cooldown.shown)
        ui.values(); ui.update(button)
        self.assertFalse(button.cooldown.shown)
        self.assertEqual(tuple(button.tint[i] for i in (1, 2, 3)), (1, 1, 1))
        self.assertEqual(ui.g.original_calls, 1)

    def test_missing_duration_also_guards_the_comparison_after_the_timer(self):
        ui = UI(); button = ui.button('WatchFrameItem1')
        ui.values(0, None, 1); ui.update(button)
        self.assertFalse(button.cooldown.shown)
        self.assertEqual(ui.g.original_calls, 0)

    def test_missing_or_nonnumeric_fields_never_reach_the_unsafe_original(self):
        for values in ((None, 20, 1), (10, None, 1), (10, 20, None),
                ('10', 20, 1), (10, '20', 1), (10, 20, '1'), (False, 20, 1), (10, 20, True)):
            with self.subTest(values=values):
                ui = UI(); button = ui.button(); ui.values(*values); ui.update(button)
                self.assertFalse(button.cooldown.shown)
                self.assertEqual(ui.g.original_calls, 0)

    def test_all_numeric_values_keep_original_timer_tint_and_return_semantics(self):
        for start, duration, enable in ((100,30,1), (100,30,0), (0,0,1), (-1,20,1), (0,5,0), (100,-1,1)):
            with self.subTest(values=(start,duration,enable)):
                ui = UI(); button = ui.button(); ui.values(start,duration,enable)
                result = ui.g.WatchFrameItem_UpdateCooldown(button, 'one', 'two')
                self.assertEqual(result, ('delegated', 2))
                self.assertEqual(ui.g.original_calls, 1)
                self.assertEqual(button.cooldown.shown, start > 0 and duration > 0 and enable > 0)
                color = .4 if duration > 0 and enable == 0 else 1
                self.assertEqual(tuple(button.tint[i] for i in (1, 2, 3)), (color, color, color))

    def test_button_can_be_reused_after_missing_item_without_disabling_events(self):
        ui = UI(); button = ui.button(); ui.values(); ui.update(button)
        ui.values(200,40,1); ui.update(button)
        self.assertTrue(button.cooldown.shown)
        self.assertEqual(button.cooldown.start, 200)
        self.assertTrue(button.events['BAG_UPDATE_COOLDOWN'])

    def test_only_the_invalid_buttons_cooldown_is_cleared(self):
        ui = UI(); first = ui.button(); second = ui.button('WatchFrameItem2', 2)
        ui.values(10,20,1,index=2); ui.update(second); ui.update(first)
        self.assertFalse(first.cooldown.shown)
        self.assertTrue(second.cooldown.shown)

    def test_hidden_buttons_already_unregister_events(self):
        ui = UI(); button = ui.button(); ui.g.WatchFrameItem_OnHide(button); ui.update(button)
        self.assertEqual(ui.g.api_calls, 0)

    def test_global_cooldown_api_and_getter_are_not_modified(self):
        ui = UI()
        self.assertTrue(ui.lua.eval(
            'CooldownFrame_SetTimer == original_timer and GetQuestLogSpecialItemCooldown == original_api'))
        with self.assertRaises(Exception):
            ui.g.CooldownFrame_SetTimer(ui.button().cooldown, None, None, None)

    def test_guard_is_not_wrapped_twice(self):
        ui = UI(); ui.lua.execute(ui.prefix); button = ui.button(); ui.values(10,20,1); ui.update(button)
        self.assertEqual(ui.g.original_calls, 1)
        self.assertEqual(ui.g.api_calls, 1 if BASELINE else 2)

    def test_full_tracker_remains_valid_lua_51(self):
        ui = UI()
        self.assertIsNotNone(ui.lua.eval('function(source) return assert(loadstring(source)) end')(ui.source))


if __name__ == '__main__':
    print('Client UI functions: ' + (
        'extracted local FrameXML' if (CLIENT/'WatchFrame.lua').is_file() else 'minimal UI doubles'))
    unittest.main()
