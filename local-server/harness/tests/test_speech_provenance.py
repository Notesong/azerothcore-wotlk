"""Runtime provenance is separate from model-controlled speech and MCP actions."""
from copy import deepcopy

import pytest

from presence_acore.client import Client
from presence_acore.mcp_actions import normalize_action
from test_mcp_control import operation, setup  # noqa: F401


UNKNOWN = {'v': 1, 'origin': 'unknown', 'provider': None, 'model': None}


def capture_client():
    client = Client()
    calls = []

    def request(*args, **kwargs):
        calls.append((args, kwargs))
        return {'status': 'completed', 'speech_provenance': {'status': 'announced'}}

    client.request = request
    return client, calls


@pytest.mark.parametrize('origin,provider,model', [
    ('body', 'local', 'qwen3.5-4b-action'), ('social', 'openai', 'gpt-6-luna'),
    ('mcp', None, None), ('body', None, None),
])
def test_trusted_metadata_is_top_level_and_does_not_change_text_or_request_identity(origin, provider, model):
    client, calls = capture_client()
    action = {'type': 'say', 'text': 'That path is blocked.', 'channel': 'party'}
    provenance = {'v': 1, 'origin': origin, 'provider': provider, 'model': model}
    before = deepcopy((action, provenance))
    result = client.execute('Vesper', action, request_id='original-operation', observed_sequence=7,
        speech_provenance=provenance)
    args, envelope = calls[0]
    assert args == ('action', 'Vesper')
    assert envelope['action'] == action and 'speech_provenance' not in envelope['action']
    assert envelope['request_id'] == 'original-operation' and envelope['observed_sequence'] == 7
    assert envelope['speech_provenance'] == provenance
    assert result['speech_provenance']['status'] == 'announced'
    assert (action, provenance) == before


@pytest.mark.parametrize('changes', [
    {'origin': 'unknown'}, {'origin': ['body']}, {'v': True}, {'v': 1.0},
    {'provider': 'x' * 25}, {'model': 'x' * 97}, {'model': 'private|field'},
    {'model': 'two\nlines'}, {'model': '✨'}, {'model': '-'}, {'extra': 'private-context'},
    {'origin': 'mcp', 'provider': 'openai', 'model': 'invented-model'},
])
def test_malformed_metadata_degrades_to_unknown_without_losing_ordinary_speech(changes):
    client, calls = capture_client()
    provenance = {'v': 1, 'origin': 'body', 'provider': 'local', 'model': 'qwen3.5-4b-action', **changes}
    result = client.execute('Vesper', {'type': 'say', 'text': 'Unchanged.'}, speech_provenance=provenance)
    assert result['status'] == 'completed'
    assert calls[0][1]['action']['text'] == 'Unchanged.'
    assert calls[0][1]['speech_provenance'] == UNKNOWN


def test_non_speech_and_legacy_speech_have_no_added_metadata_or_permissions():
    client, calls = capture_client()
    client.execute('Vesper', {'type': 'attack', 'target_guid': '500'}, speech_provenance=UNKNOWN)
    client.execute('Vesper', {'type': 'say', 'text': 'Legacy speech.'})
    assert all('speech_provenance' not in envelope for _, envelope in calls)


@pytest.mark.parametrize('field', ['speech_provenance', 'origin', 'model', 'provider'])
def test_mcp_model_action_cannot_choose_its_origin_or_model(field):
    with pytest.raises(ValueError, match='invalid_action'):
        normalize_action({'type': 'say', 'text': 'Hello.', field: 'body'})


def test_mcp_manager_stamps_unknown_model_and_replay_does_not_dispatch_twice(setup):
    manager, _, client = setup
    lease = manager.take_over('sdk-owner', operation())
    op = operation()
    first = manager.act('sdk-owner', lease['control_token'], op, {'type': 'say', 'text': 'Hello.'})
    replay = manager.act('sdk-owner', lease['control_token'], op, {'type': 'say', 'text': 'Hello.'})
    dispatched = [call for call in client.calls if call[0] == 'execute']
    assert len(dispatched) == 1 and first == replay
    assert dispatched[0][2] == {'type': 'say', 'text': 'Hello.'}
    expected = {'v': 1, 'origin': 'mcp', 'provider': None, 'model': None}
    assert dispatched[0][3]['speech_provenance'] == expected
    assert manager._record(op)['speech_provenance'] == expected


def test_mcp_non_speech_keeps_existing_wire_and_model_schema(setup):
    manager, _, client = setup
    lease = manager.take_over('sdk-owner', operation())
    manager.act('sdk-owner', lease['control_token'], operation(), {'type': 'stop'})
    assert 'speech_provenance' not in client.calls[-1][3]
