"""Closed normal-player MCP actions. The core remains the gameplay authority."""
from __future__ import annotations

import math
from typing import Any


EMOTES = ('bow', 'cheer', 'clap', 'dance', 'hug', 'kiss', 'laugh', 'nod', 'point',
          'salute', 'shrug', 'slap', 'smile', 'thank', 'wave')
ALIASES = {'quest_query': 'query_quest', 'quest_accept': 'accept_quest',
    'quest_complete': 'complete_quest', 'quest_request_reward': 'request_reward', 'quest_reward': 'reward_quest'}
_GUID = {'type': 'string', 'pattern': '^[1-9][0-9]{0,19}$',
         'description': 'Exact observed nonzero unsigned64 decimal GUID.'}
_UINT = {'type': 'integer', 'minimum': 0, 'maximum': 4294967295}
_POSITIVE = {**_UINT, 'minimum': 1}
_TEXT = {'type': 'string', 'minLength': 1, 'description': 'One line; at most255 UTF-8 bytes.'}
_SPECS: dict[str, tuple[dict[str, Any], tuple[str, ...]]] = {}


def _spec(name, required=None, optional=None):
    required, optional = required or {}, optional or {}
    _SPECS[name] = ({**required, **optional}, tuple(required))


_spec('say', {'text': _TEXT}, {'channel': {'enum': ['say', 'party']}})
_spec('move_to', {key: {'type': 'number'} for key in ('x', 'y', 'z')}, {'map_id': _UINT})
_spec('stop')
_spec('follow', {'target_guid': _GUID}, {'distance': {'type': 'number', 'minimum': 1, 'maximum': 20}})
_spec('target', {'target_guid': {'type': 'string', 'pattern': '^(0|[1-9][0-9]{0,19})$'}})
for _name in ('attack', 'interact', 'loot', 'spirit_healer_activate', 'reclaim_corpse'):
    _spec(_name, {'target_guid': _GUID})
_spec('cast', {'target_guid': _GUID, 'spell_id': _POSITIVE})
for _name in ALIASES:
    _required = {'target_guid': _GUID, 'quest_id': _POSITIVE}
    if _name == 'quest_reward':
        _required['reward_index'] = {**_UINT, 'maximum': 5}
    _spec(_name, _required)
for _name in ('party_accept', 'party_decline'):
    _spec(_name, {'inviter_guid': _GUID})
for _name in ('trade_begin', 'trade_accept', 'trade_unaccept', 'trade_cancel'):
    _spec(_name, {'target_guid': _GUID, 'trade_id': _GUID, 'trade_revision': _POSITIVE})
for _name in ('vendor_list', 'trainer_list'):
    _spec(_name, {'target_guid': _GUID}, {'page': _UINT})
_spec('vendor_buy', {'target_guid': _GUID, 'item_id': _POSITIVE,
    'vendor_slot': {**_POSITIVE, 'maximum': 255}, 'count': {**_POSITIVE, 'maximum': 255}})
_spec('vendor_sell', {'target_guid': _GUID, 'item_guid': _GUID, 'count': _POSITIVE})
_spec('vendor_repair', {'target_guid': _GUID}, {'item_guid': _GUID})
_spec('vendor_buyback', {'target_guid': _GUID, 'item_guid': _GUID,
    'buyback_slot': {'type': 'integer', 'minimum': 74, 'maximum': 85}})
_spec('train_spell', {'target_guid': _GUID, 'spell_id': _POSITIVE})
_spec('equip_item', {'item_guid': _GUID}, {'equipment_slot': {'type': 'integer', 'minimum': 0, 'maximum': 22}})
for _name in ('unequip_item', 'inspect_item'):
    _spec(_name, {'item_guid': _GUID})
_spec('gossip_select', {'target_guid': _GUID, 'menu_id': _UINT, 'option_id': _UINT})


def _object(name, fields, required):
    return {'type': 'object', 'properties': {'type': {'const': name}, **fields},
            'required': ['type', *required], 'additionalProperties': False}


JSON_SCHEMA = {'oneOf': [_object(name, fields, required) for name, (fields, required) in _SPECS.items()] + [
    _object('emote', {'emote': {'enum': list(EMOTES)}, 'target_guid': _GUID}, ['emote']),
    _object('emote', {'text': _TEXT}, ['text'])]}
ACTION_SCHEMA = JSON_SCHEMA


def _valid(value: Any, field: str, spec: dict[str, Any]) -> bool:
    if 'enum' in spec:
        return value in spec['enum'] and isinstance(value, str)
    kind = spec.get('type')
    if field.endswith('_guid') or field == 'trade_id':
        if not isinstance(value, str) or not value.isascii() or not value.isdecimal():
            return False
        return (value == '0' and field == 'target_guid' and spec.get('pattern', '').startswith('^(0|')) or (
            1 <= len(value) <= 20 and value[0] != '0' and 0 < int(value) <= 18446744073709551615)
    if kind == 'string':
        return isinstance(value, str) and bool(value) and len(value.encode('utf-8')) <= 255 and not any(
            character in value for character in '\r\n\x00')
    if kind == 'integer':
        return type(value) is int and spec.get('minimum', 0) <= value <= spec.get('maximum', 4294967295)
    if kind == 'number':
        try:
            return type(value) in (int, float) and math.isfinite(value) and spec.get('minimum', -math.inf) <= value <= spec.get('maximum', math.inf)
        except OverflowError:
            return False
    return False


def normalize_action(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or not isinstance(value.get('type'), str):
        raise ValueError('invalid_action')
    name = value['type']
    if name == 'emote':
        named = 'emote' in value
        fields = {'emote': {'enum': EMOTES}, 'target_guid': _GUID} if named else {'text': _TEXT}
        required = ('emote',) if named else ('text',)
    elif name in _SPECS:
        fields, required = _SPECS[name]
    else:
        raise ValueError('invalid_action')
    if set(value) - {'type', *fields} or any(key not in value for key in required):
        raise ValueError('invalid_action')
    if any(not _valid(item, key, fields[key]) for key, item in value.items() if key != 'type'):
        raise ValueError('invalid_action')
    return {**value, 'type': ALIASES.get(name, name)}
