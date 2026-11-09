from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from tests.test_request_scenario_terminal_sla import graph, submission
from tickets.request_scenario_validation import validate_scenario
from web_api.dto.request_scenario import ScenarioDefinition

pytestmark = pytest.mark.no_db


def timing(raw, **settings):
    raw['blocks'].append(dict(id='timing', kind='sla_attachment', title='Сроки обработки', attached_to='questions', **settings))


def test_combined_deadlines_and_terminal_overrides_are_independent():
    raw = graph()
    timing(raw, sla_profile='standard', ola_targets={'ack_minutes': 7, 'processing_minutes': 43})
    first = submission(raw, 'one')
    assert first['map_processing']['sla_profile']['key'] == 'standard'
    assert first['ola_selection']['targets'] == {'ack_minutes': 7, 'processing_minutes': 43}
    assert first['ola_selection']['source']['block_id'] == 'timing'
    terminal = next(b for b in raw['blocks'] if b['id'] == 'submit')
    terminal['sla_profile'] = 'urgent'
    assert submission(raw, 'one')['ola_selection'] == first['ola_selection']
    terminal['ola_targets'] = {'ack_minutes': 3, 'processing_minutes': 20}
    final = submission(raw, 'one')
    assert final['map_processing']['sla_profile']['key'] == 'urgent'
    assert final['ola_selection']['source']['kind'] == 'terminal'
    assert final['ola_selection']['targets']['ack_minutes'] == 3


def test_legacy_attachment_wire_omits_new_inherited_fields():
    raw = graph(); timing(raw, sla_profile='standard')
    encoded = ScenarioDefinition.model_validate(raw).model_dump(mode='json')['blocks'][-1]
    assert 'ola_targets' not in encoded and 'ola_policy_ref' not in encoded
    assert submission(raw).get('ola_selection') is None


def test_combined_internal_only_and_old_separate_assignments_remain_valid():
    raw = graph(); timing(raw, ola_targets={'ack_minutes': 7, 'processing_minutes': 43})
    assert not validate_scenario(ScenarioDefinition.model_validate(raw))
    raw['blocks'][-1].pop('ola_targets')
    raw['blocks'].append(dict(id='legacy_ola', kind='ola_attachment', title='OLA', attached_to='questions', targets={'ack_minutes': 5, 'processing_minutes': 30}))
    assert not validate_scenario(ScenarioDefinition.model_validate(raw))
    assert submission(raw)['ola_selection']['source']['block_id'] == 'legacy_ola'
    raw['blocks'][-2]['ola_targets'] = {'ack_minutes': 7, 'processing_minutes': 43}
    assert 'duplicate_attachment' in {i.code for i in validate_scenario(ScenarioDefinition.model_validate(raw))}


def test_internal_targets_and_policy_are_mutually_exclusive():
    raw = graph(); timing(raw, ola_policy_ref='internal', ola_targets={'ack_minutes': 7, 'processing_minutes': 43})
    assert 'invalid_ola' in {i.code for i in validate_scenario(ScenarioDefinition.model_validate(raw))}


@pytest.mark.asyncio
async def test_internal_policy_reference_is_validated_independently(monkeypatch):
    import tickets.request_scenario_processing as processing
    raw = graph(); timing(raw, ola_policy_ref='unpublished')
    monkeypatch.setattr(processing, 'apply_scenario_policy_refs', AsyncMock(side_effect=ValueError('unpublished')))
    issues = await processing.scenario_sla_reference_issues(SimpleNamespace(), ScenarioDefinition.model_validate(raw))
    assert any(i['path'] == 'blocks.timing.ola_policy_ref' for i in issues)


def test_fragment_preserves_distinct_policy_kinds_with_same_code():
    from tickets.request_scenario_fragments import extract_fragment, insert_fragment
    raw = graph(); raw.pop('processing'); timing(raw, policy_ref='shared', ola_policy_ref='shared')
    fragment, dependencies = extract_fragment(raw, ['timing'])
    assert {d['kind'] for d in dependencies} >= {'sla_policy_ref', 'ola_policy_ref'}
    target = deepcopy(raw); target['blocks'] = [b for b in target['blocks'] if b['id'] != 'timing']
    result, _ = insert_fragment(target, fragment, position={'x': 0, 'y': 0}, mappings={'blocks': {'questions': 'submit'}, 'sla_policy_refs': {'shared': 'employee'}, 'ola_policy_refs': {'shared': 'internal'}})
    assert result['blocks'][-1]['policy_ref'] == 'employee'
    assert result['blocks'][-1]['ola_policy_ref'] == 'internal'
