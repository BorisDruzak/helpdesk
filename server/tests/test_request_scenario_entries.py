"""Versioned entrances cannot grant facts or bypass graph safety."""
from copy import deepcopy
import pytest
from pydantic import ValidationError
from tests.test_request_scenario_runtime import pilot
from web_api.dto.request_scenario import ScenarioDefinition, ScenarioDraftDefinition
from web_api.dto.request_scenario_session import SessionStart
from web_api.dto.request_scenario_admin import SimulationInput
from tickets.request_scenario_runtime import ScenarioRuntime, ScenarioInputError
from tickets.request_scenario_validation import validate_scenario
from tickets.request_scenario_readiness import submission_variants

pytestmark = pytest.mark.no_db


def test_partial_admin_simulation_retains_strict_selected_graph_and_discloses_errors():
    from tickets.request_scenario_simulation import simulation_definition
    raw = entries_graph()
    raw['blocks'].append(dict(id='unfinished', kind='instruction', title='Unfinished', content={'body': 'Draft instruction'}, transitions=[]))
    selected, scope = simulation_definition(raw, 'paper')
    assert scope['limited_scope'] is True
    assert scope['excluded_block_ids'] == ['questions', 'unfinished']
    assert scope['issues']
    state = ScenarioRuntime(selected).initial_state('paper')
    assert state.current_block_id == 'instruction'
    assert validate_scenario(ScenarioDefinition.model_validate(raw))


def test_partial_simulation_never_discards_broken_reachable_edges():
    from tickets.request_scenario_simulation import simulation_definition
    from tickets.request_scenario_validation import ScenarioValidationError
    raw = entries_graph()
    raw['blocks'][1]['transitions'] = [{'to': 'missing'}]
    with pytest.raises(ScenarioValidationError):
        simulation_definition(raw, 'paper')


@pytest.mark.asyncio
async def test_category_archive_checks_draft_entrance_dependencies():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from app.repos.request_scenario_repo import RequestScenarioRepo, ScenarioAdminError
    session = SimpleNamespace(scalar=AsyncMock(side_effect=[None, None, 'entrance-draft']))
    repo = RequestScenarioRepo(session, SimpleNamespace(actor_id='test', actor_role='admin'))
    with pytest.raises(ScenarioAdminError, match='CATEGORY_NOT_EMPTY'):
        await repo._archive_category_check(SimpleNamespace(id='00000000-0000-0000-0000-000000000001'))


def entries_graph():
    raw = pilot()
    raw['entry_points'] = [dict(key='paper', title='Paper jam', target_block_id='instruction',
        visibility='public', enabled=True, reported_symptom='Paper jam reported')]
    raw['editor_layout'] = {'positions': {'questions': {'x': 10, 'y': -20}}}
    return raw


def test_legacy_and_optional_selection_contract():
    assert ScenarioDefinition.model_validate(pilot()).entry_points == []
    assert SessionStart.model_validate({'offering_full_code': 'workplace.printer_issue', 'entry_point_key': 'paper'}).entry_point_key == 'paper'
    assert SimulationInput.model_validate({'revision': 1, 'entry_point_key': 'paper'}).entry_point_key == 'paper'


def test_selected_entry_has_separate_reported_context_and_no_answers():
    engine = ScenarioRuntime(ScenarioDefinition.model_validate(entries_graph()))
    state = engine.initial_state('paper')
    assert state.current_block_id == 'instruction'
    assert state.answers == {}
    assert state.results['_entry_point']['reported_symptom'] == 'Paper jam reported'
    assert engine.initial_state().current_block_id == 'questions'
    with pytest.raises(ScenarioInputError): engine.initial_state('absent')


@pytest.mark.parametrize('mutation', ['duplicate', 'unknown', 'finish'])
def test_every_entry_is_validated(mutation):
    raw = entries_graph()
    if mutation == 'duplicate': raw['entry_points'].append(deepcopy(raw['entry_points'][0]))
    if mutation == 'unknown': raw['entry_points'][0]['target_block_id'] = 'absent'
    if mutation == 'finish': raw['entry_points'][0]['target_block_id'] = 'done'
    expected = {'duplicate': 'duplicate_entry', 'unknown': 'unknown_entry', 'finish': 'unconfirmed_finish'}[mutation]
    assert expected in {issue.code for issue in validate_scenario(ScenarioDefinition.model_validate(raw))}


def test_readiness_covers_specialized_entrance_even_when_disabled():
    raw = entries_graph()
    raw['entry_points'][0]['enabled'] = False
    states = submission_variants(ScenarioDefinition.model_validate(raw))
    assert any('questions' not in state.history and state.current_block_id == 'submit' for state in states)
    assert any('questions' in state.history and state.current_block_id == 'submit' for state in states)


def test_entrance_and_layout_bounds():
    raw = entries_graph()
    raw['editor_layout']['positions']['questions']['x'] = float('inf')
    with pytest.raises(ValidationError): ScenarioDraftDefinition.model_validate(raw)
    raw = entries_graph()
    raw['entry_points'][0]['reported_symptom'] = {'priority': 'critical'}
    with pytest.raises(ValidationError): ScenarioDraftDefinition.model_validate(raw)
    raw = entries_graph()
    raw['entry_points'] *= 65
    with pytest.raises(ValidationError): ScenarioDraftDefinition.model_validate(raw)


def test_catalog_omits_hidden_disabled_and_hidden_category_entries():
    from tickets.request_scenario_catalog import project_catalog_entries
    raw = entries_graph()
    for key, changes in [('hidden', {'visibility': 'internal'}), ('disabled', {'enabled': False}),
                         ('category', {'category_id': '00000000-0000-0000-0000-000000000001'})]:
        raw['entry_points'].append({**raw['entry_points'][0], 'key': key, **changes})
    categories = {'00000000-0000-0000-0000-000000000001': {'visibility': 'internal', 'lifecycle_status': 'published'}}
    items = project_catalog_entries(ScenarioDefinition.model_validate(raw), categories, 'pinned')
    assert [item['entry_point_key'] for item in items] == ['paper']
    assert items[0]['version_id'] == 'pinned'
    assert 'reported_symptom' not in items[0]


def test_back_preserves_pinned_entry_and_reported_symptom_does_not_supply_facts():
    from tickets.request_scenario_submission import build_scenario_submission
    from web_api.dto.request_scenario import ScenarioAnswerRequest
    runtime = ScenarioRuntime(ScenarioDefinition.model_validate(entries_graph()))
    state = runtime.initial_state('paper')
    for result in ('acknowledged', 'no', None):
        state = runtime.advance(state, ScenarioAnswerRequest(expected_block_id=state.current_block_id,
            revision=state.revision, current_result=result))
    assert state.current_block_id == 'submit'
    payload, snapshot = build_scenario_submission(runtime.definition, state, session_id='test', version_id='pinned')
    assert payload['form_payload'] == {} and snapshot['facts'] == {}
    assert snapshot['reported_context']['reported_symptom'] == 'Paper jam reported'
    back = runtime.back(state, 'instruction', expected_revision=state.revision)
    assert back.results['_entry_point'] == state.results['_entry_point']


def test_all_entry_variants_share_one_readiness_limit():
    from tickets.request_scenario_readiness import ReadinessCoverageError
    raw = entries_graph()
    raw['entry_points'] = [{**raw['entry_points'][0], 'key': 'entry_' + str(index)} for index in range(64)]
    with pytest.raises(ReadinessCoverageError):
        submission_variants(ScenarioDefinition.model_validate(raw), limit=64)


@pytest.mark.asyncio
async def test_required_canonical_data_bypass_blocks_publication(monkeypatch):
    from types import SimpleNamespace
    from tickets import request_scenario_publication as module
    monkeypatch.setattr(module, 'PolicyHealthService', lambda: SimpleNamespace(evaluate=lambda **_: {'templates': [{'health_status': 'ok'}]}))
    seen = []
    async def canonical_processing(session, payload, *, scenario_snapshot):
        seen.append(scenario_snapshot)
        if not payload['form_payload'].get('summary'):
            raise ValueError('Required canonical summary is missing')
        return None, {'routing': {'queue_id': 1}, 'sla': {'resolution_min': 30},
                      'approval': {'required': False}, 'priority': {}}
    monkeypatch.setattr(module, 'simulate_service_catalog_processing', canonical_processing)
    raw = entries_graph()
    source = {'effective_template': {'request_template': {'published_at': 'now'},
        'resolved_policies': {'closure': {}, 'visibility': {}}}, 'policies': {},
        'queues': [{'id': 1, 'is_active': True}], 'service': {'visibility': 'public', 'lifecycle_status': 'published'},
        'offering': {'visibility': 'public', 'lifecycle_status': 'published', 'request_template_key': 'printer'}, 'taxonomy': []}
    source['effective_template']['resolved_policies'] = {'closure': {'configured': True}, 'visibility': {'configured': True}}
    result = await module.ScenarioPublicationService(SimpleNamespace(session=None))._assess(
        SimpleNamespace(archived=False, category_id=None), SimpleNamespace(definition=raw), source)
    assert any(item['reported_context'] for item in seen)
    assert any(item['reported_context'] is None for item in seen)
    assert result['readiness']['can_publish'] is False
    assert 'processing_invalid' in {issue['code'] for issue in result['readiness']['issues']}
