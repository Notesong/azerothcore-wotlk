from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from presence_acore.mcp_server import Inspector, Server
from test_mcp_server import FakeClient, initialize, request
from test_model_context import capture


def incident():
    recorded = capture()
    recorded['context']['extra_context']['native_observation']['protection'] = {
        'active': True, 'protected_target_guid': '99', 'instruction': 'Keep this creature alive.',
        'instruction_version': 'moon/v1'}
    return {'schema': 'moon-violation/v1', 'inspection_only': True, 'character': 'Vesper', 'lane': 'body',
        'incident_id': 'e' * 32, 'recorded_at': '2026-10-28T12:00:00Z',
        'classification': 'planner_action_with_protected_effect_blocked', 'capture': recorded,
        'planned_action': {'type': 'cast', 'spell_id': 123, 'target_guid': '1'},
        'submitted_action': {'type': 'cast', 'spell_id': 123, 'target_guid': '1'},
        'guard_result': {'error_code': '', 'status': 'accepted', 'outcome': 'accepted_with_guard_intervention',
            'request_id': 'd' * 32, 'submitted': True, 'executed': False, 'guard_interventions_truncated': False,
            'guard_interventions_dropped': 0, 'guard_interventions': [{'type': 'moon_guard_intervention',
                'attribution': 'synchronous_action', 'action_type': 'cast', 'request_id': 'd' * 32,
                'protected_target_guid': '99', 'target_guid': '99', 'reason': 'protected_target_effect',
                'observed_sequence': 42, 'hook': 'spell_target'}]},
        'protection_at_request': {'active': True, 'protected_target_guid': '99'},
        'pre_action_protection': {'active': False},
        'provenance': {'capture_id': recorded['capture_id'], 'request_context_available': True,
            'planner_had_moon_instruction': True, 'protection_active_in_request': True,
            'explicit_protected_target_proposal': False, 'action_changed_before_submission': False,
            'action_projection_changed': False, 'protection_projection_changed': False,
            'guard_context_source': 'pre_action_observation_not_guard_callback'},
        'retention': {'max_records': 100, 'max_record_bytes': 327680}}


def status():
    return {'schema': 'moon-audit-status/v1', 'character': 'Vesper', 'latest_incident_id': 'e' * 32,
            'updated_at': '2026-10-28T12:00:00Z', 'last_error': '', 'retained_records': 1,
            'total_recorded': 1, 'total_rotated': 0, 'max_records': 100, 'max_record_bytes': 327680}


class MoonContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent, prefix='moon-inspection-')
        self.directory = Path(self.temp.name)
        self.client = FakeClient()
        self.inspector = Inspector(self.client, data_dir=self.directory)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, value):
        path = self.directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')

    def install(self, record=None, index=None):
        self.write('runtime-game-player-moon-audit-status.json', index or status())
        self.write('runtime-game-player-moon-violations/' + 'e' * 32 + '.json', record or incident())

    def test_archived_context_survives_new_latest_body_and_fresh_reader_without_observing(self):
        record = incident()
        self.install(record)
        latest = capture()
        latest['observation_sequence'] = 999
        self.write('runtime-game-player-context-body.json', latest)
        value = self.inspector.model_context(source='last_violation')
        self.assertTrue(value['available'])
        self.assertEqual(value['view_kind'], 'guarded_violation')
        self.assertEqual(value['capture'], record['capture'])
        self.assertEqual(value['capture']['observation_sequence'], 42)
        self.assertEqual(value['violation']['guard_result']['status'], 'accepted')
        again = Inspector(self.client, data_dir=self.directory).model_context(source='last_violation')
        self.assertEqual(again['violation'], value['violation'])
        self.assertEqual(self.client.observations, [])

    def test_commerce_action_fields_survive_historical_inspection(self):
        action = {'type': 'equip_item', 'item_guid': '123', 'item_id': 456, 'equipment_slot': 16,
                  'vendor_slot': 2, 'count': 3, 'page': 1, 'buyback_slot': 74,
                  'menu_id': 20, 'option_id': 0, 'target_guid': '80'}
        record = incident()
        record['classification'] = 'guard_intervention_requires_review'
        record['planned_action'] = action
        record['submitted_action'] = action
        for event in record['guard_result']['guard_interventions']:
            event['action_type'] = 'equip_item'
            event['reason'] = 'reflection_declined'
        self.install(record)
        value = self.inspector.model_context(source='last_violation')
        self.assertTrue(value['available'])
        self.assertEqual(value['violation']['planned_action'], action)
        self.assertEqual(value['violation']['submitted_action'], action)
        self.assertFalse(value.get('transport_truncated', False))

    def test_missing_or_write_failure_are_distinct_and_social_lane_is_explicit(self):
        missing = self.inspector.model_context(source='last_violation')
        self.assertEqual(missing['error']['code'], 'no_recorded_violation')
        self.assertEqual(self.inspector.model_context(lane='social', source='last_violation')['error']['code'], 'no_recorded_violation')
        self.write('runtime-game-player-moon-audit-status.json', {**status(), 'latest_incident_id': None,
                                                               'last_error': 'audit_write_failed'})
        failed = self.inspector.model_context(source='last_violation')
        self.assertEqual(failed['error']['code'], 'audit_write_failed')
        self.assertEqual(failed['audit_status']['last_error'], 'audit_write_failed')

    def test_metadata_path_escape_is_rejected_without_opening_its_target(self):
        self.install(index={**status(), 'latest_incident_id': '../../secret'})
        self.write('secret.json', {'password': 'DO-NOT-ECHO'})
        opened = []
        original = Path.open
        def track(path, *args, **kwargs):
            opened.append(path.name)
            return original(path, *args, **kwargs)
        with patch.object(Path, 'open', track):
            value = self.inspector.model_context(source='last_violation')
        self.assertFalse(value['available'])
        self.assertNotIn('secret.json', opened)
        self.assertNotIn('DO-NOT-ECHO', json.dumps(value))

    def test_foreign_capture_join_or_unattributed_telemetry_is_rejected(self):
        for change in ('capture_id', 'attribution', 'request_id'):
            record = incident()
            if change == 'capture_id':
                record['provenance']['capture_id'] = 'f' * 32
            elif change == 'attribution':
                record['guard_result']['guard_interventions'][0]['attribution'] = 'unattributed_execution'
            else:
                record['guard_result']['guard_interventions'][0]['request_id'] = 'f' * 32
            self.install(record=record)
            value = self.inspector.model_context(source='last_violation')
            self.assertEqual(value['error']['code'], 'invalid_violation')
            self.assertNotIn('capture', value)

    def test_redaction_is_explicit_without_shortening_legitimate_context(self):
        record = incident()
        record['planned_action']['api_key'] = 'DO-NOT-ECHO'
        record['capture']['context']['session_state']['notes'] = 'long ♥ ' * 1000
        self.install(record)
        value = self.inspector.model_context(source='last_violation')
        self.assertTrue(value['available'])
        self.assertEqual(value['capture']['context']['session_state']['notes'], record['capture']['context']['session_state']['notes'])
        self.assertNotIn('DO-NOT-ECHO', json.dumps(value))
        self.assertTrue(value['transport_truncated'])

    def test_partial_context_and_oversized_record_never_fall_back_to_current_state(self):
        record = incident()
        record['capture']['context'] = None
        record['classification'] = 'guard_intervention_requires_review'
        record['capture']['exactness'].update(context_available=False, copied_values_exact=False, unavailable_reason='oversize')
        record['provenance'].update(request_context_available=False, planner_had_moon_instruction=False,
                                    protection_active_in_request=False)
        self.install(record)
        self.assertEqual(self.inspector.model_context(source='last_violation')['error']['code'], 'capture_context_unavailable')
        record = incident()
        record['capture']['context']['session_state']['notes'] = 'x' * 330000
        self.install(record)
        value = self.inspector.model_context(source='last_violation')
        self.assertEqual(value['error']['code'], 'violation_record_unavailable')
        self.assertEqual(self.client.observations, [])

    def test_standalone_dispatch_advertises_last_violation_and_never_starts_models(self):
        server = Server(self.inspector)
        initialize(server)
        tool = next(tool for tool in server.tools() if tool['name'] == 'wow_model_context')
        self.assertIn('last_violation', tool['inputSchema']['properties']['source']['enum'])
        result = server.handle(request('tools/call', {'name': 'wow_model_context',
            'arguments': {'source': 'last_violation'}}))['result']
        self.assertEqual(result['structuredContent']['error']['code'], 'no_recorded_violation')
        self.assertEqual(self.client.observations, [])

    def test_proposal_stopped_before_submission_does_not_invent_a_server_veto(self):
        record = incident()
        record['classification'] = 'planner_protected_target_proposal'
        record['planned_action'] = {'type': 'attack', 'target_guid': '99'}
        record['submitted_action'] = {'type': 'wait'}
        record['guard_result'].update(outcome='proposal_not_submitted', status='completed', submitted=False,
                                     executed=True, guard_interventions=[], request_id='')
        record['provenance'].update(explicit_protected_target_proposal=True, action_changed_before_submission=True)
        self.install(record)
        value = self.inspector.model_context(source='last_violation')
        self.assertTrue(value['available'])
        self.assertEqual(value['violation']['guard_result']['outcome'], 'proposal_not_submitted')
        record['provenance']['planner_had_moon_instruction'] = False
        self.install(record)
        self.assertEqual(self.inspector.model_context(source='last_violation')['error']['code'], 'invalid_violation')

    def install_social(self, record=None):
        record = deepcopy(record or incident())
        record['lane'] = record['capture']['lane'] = 'social'
        record['capture']['context']['planner_mode'] = 'social'
        self.write('runtime-game-player-moon-audit-status-social.json', status())
        self.write('runtime-game-player-moon-violations-social/' + 'e' * 32 + '.json', record)
        return record

    def test_social_guard_reads_only_its_own_preserved_context_after_new_body_and_social_requests(self):
        body = incident()
        self.install(body)
        social = self.install_social()
        social['capture']['context']['session_state']['notes'] = 'Social source context ♥ ' * 200
        self.install_social(social)
        self.write('runtime-game-player-context-body.json', capture())
        self.write('runtime-game-player-context-social.json', capture('social'))
        value = self.inspector.model_context(lane='social', source='last_violation')
        self.assertTrue(value['available'])
        self.assertEqual(value['capture'], social['capture'])
        self.assertEqual(value['violation']['lane'], 'social')
        self.assertEqual(self.inspector.model_context(source='last_violation')['capture'], body['capture'])
        self.assertEqual(self.client.observations, [])

    def test_social_guard_never_borrows_body_and_rejects_cross_lane_or_failed_capture(self):
        self.install()
        self.assertEqual(self.inspector.model_context(lane='social', source='last_violation')['error']['code'],
                         'no_recorded_violation')
        for mutation in ('capture_lane', 'record_lane', 'capture_id', 'outcome', 'http_status'):
            record = self.install_social()
            if mutation == 'capture_lane':
                record['capture']['lane'] = 'body'
            elif mutation == 'record_lane':
                record['lane'] = 'body'
            elif mutation == 'capture_id':
                record['provenance']['capture_id'] = 'f' * 32
            elif mutation == 'outcome':
                record['capture']['outcome']['state'] = 'request_error'
            else:
                record['capture']['outcome']['http_status'] = 400
            self.write('runtime-game-player-moon-violations-social/' + 'e' * 32 + '.json', record)
            value = self.inspector.model_context(lane='social', source='last_violation')
            self.assertEqual(value['error']['code'], 'invalid_violation')
            self.assertNotIn('capture', value)

    def test_social_guard_keeps_identical_privacy_filters_and_read_only_dispatch(self):
        record = self.install_social()
        record['planned_action']['api_key'] = 'DO-NOT-ECHO'
        self.write('runtime-game-player-moon-violations-social/' + 'e' * 32 + '.json', record)
        server = Server(self.inspector)
        initialize(server)
        result = server.handle(request('tools/call', {'name': 'wow_model_context',
            'arguments': {'lane': 'social', 'source': 'last_violation'}}))['result']['structuredContent']
        self.assertTrue(result['available'])
        self.assertTrue(result['transport_truncated'])
        self.assertNotIn('DO-NOT-ECHO', json.dumps(result))
        self.assertEqual(self.client.observations, [])

    def test_full_social_preview_uses_action_capable_projection_without_changing_recorded_context(self):
        seen = []
        def compact(value, mode):
            seen.append(mode)
            return {'object': {'guid': '77'}, 'protection': {'instruction': 'Keep Moon safe'}}
        with patch('presence_acore.model_context._projection', return_value=compact):
            value = self.inspector.model_context(lane='social', source='live_preview')
        self.assertTrue(value['available'])
        self.assertEqual(seen, ['social_gameplay'])
        self.assertEqual(value['preview']['native_observation']['object']['guid'], '77')
        self.assertFalse(value['preview']['is_actual_request'])


if __name__ == '__main__':
    unittest.main()
