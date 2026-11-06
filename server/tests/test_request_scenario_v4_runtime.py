from copy import deepcopy
import pytest
from pydantic import ValidationError
from tests.test_request_scenario_v3_processing import definition
from tickets.request_scenario_runtime import ScenarioRuntime, ScenarioInputError
from tickets.request_scenario_session import project_step
from tickets.request_scenario_submission import build_scenario_submission
from web_api.dto.request_scenario import ScenarioAnswerRequest, ScenarioDefinition

pytestmark = pytest.mark.no_db


def graph():
    raw = definition().model_dump(mode='json')
    raw.update(schema_version=4, execution_semantics=3)
    raw['blocks'][0]['transition_mode'] = 'buttons'
    raw['blocks'][0]['transitions'] = [
        {'to': 'submit', 'button': {'key': 'normal', 'label': 'Normal'}},
        {'to': 'submit', 'button': {'key': 'urgent', 'label': 'Urgent'},
         'processing_facts': {'urgency': 'blocked'}, 'processing': {'sla_profile': 'urgent'}}]
    return ScenarioDefinition.model_validate(raw)


def test_button_selection_is_retained_for_same_destination_and_backtracking():
    engine = ScenarioRuntime(graph())
    state = engine.initial_state()
    assert project_step(engine.definition, state)['block']['actions'] == [
        {'key': 'normal', 'label': 'Normal'}, {'key': 'urgent', 'label': 'Urgent'}]
    request = ScenarioAnswerRequest(expected_block_id=state.current_block_id, revision=state.revision,
                                    answers={'affected': 'one'}, action_key='urgent')
    state = engine.advance(state, request)
    snapshot = build_scenario_submission(engine.definition, state, session_id='s', version_id='v')[1]
    assert snapshot['processing_facts']['urgency'] == 'blocked'
    assert snapshot['map_processing']['sla_profile']['key'] == 'urgent'
    assert 'urgent' not in state.answers.values()
    back = engine.back(state, 'questions', expected_revision=state.revision)
    state = engine.advance(back, ScenarioAnswerRequest(expected_block_id='questions', revision=back.revision,
                                                       answers={'affected': 'one'}, action_key='normal'))
    snapshot = build_scenario_submission(engine.definition, state, session_id='s', version_id='v')[1]
    assert 'urgency' not in snapshot['processing_facts']
    assert snapshot['map_processing']['sla_profile']['key'] == 'standard'


def test_button_rejects_unknown_action():
    engine = ScenarioRuntime(graph())
    state = engine.initial_state()
    with pytest.raises(ScenarioInputError):
        engine.advance(state, ScenarioAnswerRequest(expected_block_id=state.current_block_id, revision=state.revision,
                                                    answers={'affected': 'one'}, action_key='unknown'))

@pytest.mark.parametrize('count,valid', [(1, True), (10, True), (11, False)])
def test_button_count_limits(count, valid):
    from tickets.request_scenario_validation import validate_scenario
    raw = graph().model_dump(mode='json')
    raw['blocks'][0]['transitions'] = [dict(to='submit', button={'key': f'button_{i}', 'label': str(i)}) for i in range(count)]
    issues = validate_scenario(ScenarioDefinition.model_validate(raw))
    assert (not any(i.code == 'invalid_buttons' for i in issues)) is valid


def test_rich_document_rejects_external_image_and_script_links():
    raw = graph().model_dump(mode='json')
    raw['blocks'][0]['fields'][0]['help_document'] = {'type': 'doc', 'content': [
        {'type': 'image', 'attrs': {'src': 'https://evil.invalid/x'}}]}
    with pytest.raises(ValidationError):
        ScenarioDefinition.model_validate(raw)
    raw['blocks'][0]['fields'][0]['help_document'] = {'type': 'doc', 'content': [
        {'type': 'paragraph', 'content': [{'type': 'text', 'text': 'go', 'marks': [
            {'type': 'link', 'attrs': {'href': 'javascript:alert(1)'}}]}]}]}
    with pytest.raises(ValidationError):
        ScenarioDefinition.model_validate(raw)


def test_rich_image_must_be_declared_as_an_attachment():
    raw = graph().model_dump(mode='json')
    raw['blocks'][0]['fields'][0]['help_document'] = {'type': 'doc', 'content': [
        {'type': 'image', 'attrs': {'asset_id': '00000000-0000-0000-0000-000000000001', 'alt': 'x'}}]}
    from tickets.request_scenario_validation import validate_scenario
    assert any(issue.code == 'rich_asset_missing' for issue in validate_scenario(ScenarioDefinition.model_validate(raw)))

@pytest.mark.parametrize('version', [1, 2, 3])
def test_upgrade_preserves_original_execution_semantics(version):
    from tests.test_request_scenario_runtime import pilot
    from tickets.request_scenario_conversion import upgrade_scenario_to_v4
    raw = pilot() if version < 3 else definition().model_dump(mode='json')
    raw['schema_version'] = version
    if version == 2:
        raw['entry_points'] = [{'key': 'main', 'title': 'Main', 'target_block_id': raw['entry_block_id']}]
    upgraded = upgrade_scenario_to_v4(raw)
    assert upgraded.schema_version == 4
    assert upgraded.execution_semantics == version
    assert raw['schema_version'] == version

def test_legacy_serialization_omits_v4_defaults():
    from tests.test_request_scenario_runtime import pilot
    raw = ScenarioDefinition.model_validate(pilot()).model_dump(mode='json')
    assert 'execution_semantics' not in raw
    for block in raw['blocks']:
        assert 'transition_mode' not in block
        assert all('button' not in edge for edge in block['transitions'])
        assert all('help_document' not in field for field in block.get('fields', []))
        assert 'rich_document' not in block.get('content', {})

def test_navigation_and_sla_replay_after_back():
    raw = graph().model_dump(mode='json')
    raw['entry_block_id'] = 'menu'
    raw['entry_points'] = []
    raw['blocks'].insert(0, {'id': 'menu', 'kind': 'navigation', 'title': 'Menu', 'transition_mode': 'buttons',
        'transitions': [{'to': 'sla', 'button': {'key': 'urgent', 'label': 'Urgent'}},
                        {'to': 'questions', 'button': {'key': 'normal', 'label': 'Normal'}}]})
    raw['blocks'].insert(1, {'id': 'sla', 'kind': 'sla', 'title': 'SLA',
        'processing_facts': {'urgency': 'blocked'}, 'sla_profile': 'urgent', 'transitions': [{'to': 'questions'}]})
    engine = ScenarioRuntime(ScenarioDefinition.model_validate(raw))
    state = engine.initial_state()
    state = engine.advance(state, ScenarioAnswerRequest(expected_block_id='menu', revision=state.revision, action_key='urgent'))
    assert state.current_block_id == 'questions'
    state = engine.advance(state, ScenarioAnswerRequest(expected_block_id='questions', revision=state.revision, answers={'affected': 'one'}, action_key='normal'))
    snapshot = build_scenario_submission(engine.definition, state, session_id='s', version_id='v')[1]
    assert snapshot['processing_facts']['urgency'] == 'blocked'
    assert snapshot['map_processing']['sla_profile']['key'] == 'urgent'
    state = engine.back(state, 'menu', expected_revision=state.revision)
    state = engine.advance(state, ScenarioAnswerRequest(expected_block_id='menu', revision=state.revision, action_key='normal'))
    state = engine.advance(state, ScenarioAnswerRequest(expected_block_id='questions', revision=state.revision, answers={'affected': 'one'}, action_key='normal'))
    snapshot = build_scenario_submission(engine.definition, state, session_id='s', version_id='v')[1]
    assert 'urgency' not in snapshot['processing_facts']
    assert snapshot['map_processing']['sla_profile']['key'] == 'standard'

def test_legacy_policy_override_preserves_route_and_backtracking():
    from tests.test_request_scenario_unified import source
    raw = source()
    raw.update(schema_version=4, execution_semantics=2)
    raw['process_binding']['policy_refs'] = {'routing': 'legacy_queue', 'sla': 'legacy_sla'}
    raw['entry_block_id'] = 'menu'
    raw['entry_points'] = [{'key': 'main', 'title': 'Main', 'target_block_id': 'menu'}]
    raw['blocks'].insert(0, {'id': 'menu', 'kind': 'navigation', 'title': 'Menu', 'transition_mode': 'buttons',
        'transitions': [{'to': 'sla', 'button': {'key': 'urgent', 'label': 'Urgent'}},
                        {'to': 'questions', 'button': {'key': 'normal', 'label': 'Normal'}}]})
    raw['blocks'].insert(1, {'id': 'sla', 'kind': 'sla', 'title': 'SLA', 'policy_ref': 'urgent_sla',
        'transitions': [{'to': 'questions'}]})
    engine = ScenarioRuntime(ScenarioDefinition.model_validate(raw))
    state = engine.initial_state()
    state = engine.advance(state, ScenarioAnswerRequest(expected_block_id='menu', revision=state.revision, action_key='urgent'))
    state = engine.advance(state, ScenarioAnswerRequest(expected_block_id='questions', revision=state.revision, answers={'affected': 'one'}))
    snapshot = build_scenario_submission(engine.definition, state, session_id='s', version_id='v')[1]
    assert snapshot['policy_refs'] == {'routing': 'legacy_queue', 'sla': 'urgent_sla'}
    state = engine.back(state, 'menu', expected_revision=state.revision)
    state = engine.advance(state, ScenarioAnswerRequest(expected_block_id='menu', revision=state.revision, action_key='normal'))
    state = engine.advance(state, ScenarioAnswerRequest(expected_block_id='questions', revision=state.revision, answers={'affected': 'one'}))
    snapshot = build_scenario_submission(engine.definition, state, session_id='s', version_id='v')[1]
    assert snapshot['policy_refs'] == {'routing': 'legacy_queue', 'sla': 'legacy_sla'}

def test_action_does_not_bypass_required_fields_or_revision():
    from tickets.request_scenario_runtime import ScenarioConflict
    engine = ScenarioRuntime(graph())
    state = engine.initial_state()
    with pytest.raises(ScenarioInputError):
        engine.advance(state, ScenarioAnswerRequest(expected_block_id='questions', revision=state.revision, action_key='urgent'))
    with pytest.raises(ScenarioConflict):
        engine.advance(state, ScenarioAnswerRequest(expected_block_id='questions', revision=state.revision + 1,
                                                     answers={'affected': 'one'}, action_key='urgent'))


def test_readiness_enumerates_same_target_actions():
    from tickets.request_scenario_readiness import submission_variants
    from tickets.request_scenario_submission import map_processing
    graph_def = graph()
    states = submission_variants(graph_def)
    profiles = {map_processing(graph_def, state)['sla_profile']['key'] for state in states}
    assert profiles == {'standard', 'urgent'}

def test_conditional_action_on_current_answer_can_be_selected_without_preview():
    raw = graph().model_dump(mode='json')
    raw['blocks'][0]['transitions'][1]['when'] = {'op': 'eq', 'source': 'answer', 'field': 'affected', 'value': 'all'}
    engine = ScenarioRuntime(ScenarioDefinition.model_validate(raw))
    state = engine.initial_state()
    assert 'urgent' not in {action['key'] for action in project_step(engine.definition, state)['block']['actions']}
    assert project_step(engine.definition, state)['block']['has_dynamic_fields']
    preview = engine.preview_answers(state, ScenarioAnswerRequest(expected_block_id='questions', revision=state.revision, answers={'affected': 'all'}))
    assert 'urgent' in {action['key'] for action in project_step(engine.definition, preview)['block']['actions']}
    state = engine.advance(state, ScenarioAnswerRequest(expected_block_id='questions', revision=state.revision,
                                                       answers={'affected': 'all'}, action_key='urgent'))
    assert state.current_block_id == 'submit'

def test_conditional_action_is_rejected_when_submitted_guard_is_false():
    raw = graph().model_dump(mode='json')
    raw['blocks'][0]['transitions'][1]['when'] = {'op': 'eq', 'source': 'answer', 'field': 'affected', 'value': 'all'}
    engine = ScenarioRuntime(ScenarioDefinition.model_validate(raw))
    state = engine.initial_state()
    with pytest.raises(ScenarioInputError):
        engine.advance(state, ScenarioAnswerRequest(expected_block_id='questions', revision=state.revision,
                                                    answers={'affected': 'one'}, action_key='urgent'))

def test_upgrade_guard_rejects_semantics_changes_and_downgrade():
    from tickets.request_scenario_conversion import validate_scenario_upgrade
    from tests.test_request_scenario_runtime import pilot
    original = pilot()
    upgraded = deepcopy(original)
    upgraded.update(schema_version=4, execution_semantics=1)
    validate_scenario_upgrade(original, ScenarioDefinition.model_validate(upgraded))
    upgraded['execution_semantics'] = 3
    with pytest.raises(ValueError):
        validate_scenario_upgrade(original, ScenarioDefinition.model_validate(upgraded))
    with pytest.raises(ValueError):
        validate_scenario_upgrade({'schema_version': 4, 'execution_semantics': 1}, ScenarioDefinition.model_validate(original))

def test_readiness_rejects_valid_answer_with_no_applicable_action():
    from tickets.request_scenario_readiness import submission_variants, ReadinessCoverageError
    raw = graph().model_dump(mode='json')
    raw['blocks'][0]['transitions'] = [{'to': 'submit', 'button': {'key': 'only_one', 'label': 'One'},
        'when': {'op': 'eq', 'source': 'answer', 'field': 'affected', 'value': 'one'}}]
    with pytest.raises(ReadinessCoverageError):
        submission_variants(ScenarioDefinition.model_validate(raw))


def test_semantics_guard_preserves_v3_map_mode_after_upgrade():
    from tickets.request_scenario_conversion import validate_scenario_upgrade
    raw = graph().model_dump(mode='json')
    changed = deepcopy(raw)
    changed['processing'] = None
    with pytest.raises(ValueError):
        validate_scenario_upgrade(raw, ScenarioDefinition.model_validate(changed))

@pytest.mark.asyncio
async def test_atomic_upgrade_uses_server_source_and_rejects_stale_revision(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    import app.repos.request_scenario_repo as repo_module
    from tests.test_request_scenario_runtime import pilot
    repo = repo_module.RequestScenarioRepo.__new__(repo_module.RequestScenarioRepo)
    repo.session = SimpleNamespace(flush=AsyncMock(), refresh=AsyncMock())
    repo.auth = SimpleNamespace(actor_id='admin')
    repo._service_lock = AsyncMock()
    repo._binding = AsyncMock()
    repo._audit = AsyncMock()
    row = SimpleNamespace(id='s', service_code='workplace', archived=False, updated_by='old')
    draft = SimpleNamespace(revision=7, definition=pilot(), updated_by='old')
    repo.detail = AsyncMock(return_value=(row, draft))
    monkeypatch.setattr(repo_module, 'serialize', lambda value: dict(vars(value)))
    with pytest.raises(repo_module.ScenarioAdminError) as error:
        await repo.upgrade_v4('s', 6)
    assert error.value.code == 'REVISION_CONFLICT'
    result = await repo.upgrade_v4('s', 7)
    assert result['draft']['revision'] == 8
    assert draft.definition['schema_version'] == 4 and draft.definition['execution_semantics'] == 1
    assert draft.definition['blocks'][0]['fields'][0]['key'] == pilot()['blocks'][0]['fields'][0]['key']

@pytest.mark.parametrize('version', [1, 2, 3])
@pytest.mark.parametrize('answer', [{}, {'confirm': False}, {'confirm': True}])
def test_upgrade_keeps_checkbox_missing_and_required_semantics(version, answer):
    from tickets.request_scenario_conversion import upgrade_scenario_to_v4
    raw = definition().model_dump(mode='json')
    raw['schema_version'] = version
    if version < 3:
        raw['processing'] = None
        for edge in raw['blocks'][0]['transitions']:
            edge['processing'] = None
    raw['blocks'][0]['transitions'] = [{'to': 'submit', **({'processing': {'sla_profile': 'urgent'}} if version == 3 else {})}]
    raw['blocks'][0]['fields'] = [{'key': 'confirm', 'type': 'checkbox', 'label': 'Confirm', 'required': True}]
    old = ScenarioRuntime(ScenarioDefinition.model_validate(raw))
    upgraded = ScenarioRuntime(ScenarioDefinition.model_validate(upgrade_scenario_to_v4(raw).model_dump(mode='json')))
    def execute(engine):
        state = engine.initial_state()
        try:
            result = engine.advance(state, ScenarioAnswerRequest(expected_block_id=state.current_block_id, revision=state.revision, answers=answer))
            return ('ok', result.current_block_id, result.answers, result.history)
        except ScenarioInputError as exc:
            return ('invalid', exc.errors)
    assert execute(old) == execute(upgraded)

def test_map_owned_offering_runtime_simulation_exception_is_version_specific():
    from tickets.request_scenario_publication import offering_issue_blocks
    issue = {'severity': 'error', 'kind': 'runtime_simulation_failed'}
    assert not offering_issue_blocks({'schema_version': 3}, issue)
    assert not offering_issue_blocks({'schema_version': 4, 'processing': {}}, issue)
    assert offering_issue_blocks({'schema_version': 4, 'processing': None}, issue)
    assert offering_issue_blocks({'schema_version': 4, 'processing': {}}, {'severity': 'critical', 'kind': 'other'})

@pytest.mark.asyncio
async def test_save_cannot_upgrade_and_change_graph_simultaneously():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from app.repos.request_scenario_repo import RequestScenarioRepo, ScenarioAdminError
    from tests.test_request_scenario_runtime import pilot
    from web_api.dto.request_scenario_admin import ScenarioSave
    from tickets.request_scenario_conversion import upgrade_scenario_to_v4
    repo = RequestScenarioRepo.__new__(RequestScenarioRepo)
    row = SimpleNamespace(service_code='workplace', archived=False)
    draft = SimpleNamespace(revision=1, definition=pilot())
    repo.detail = AsyncMock(return_value=(row, draft))
    repo._service_lock = AsyncMock()
    modified = upgrade_scenario_to_v4(draft.definition).model_dump(mode='json')
    modified['title'] = 'Changed together'
    with pytest.raises(ScenarioAdminError) as error:
        await repo.save('id', ScenarioSave(revision=1, definition=modified))
    assert error.value.code == 'UPGRADE_REQUIRED'
    assert draft.definition['schema_version'] == 1 and draft.revision == 1

def test_instruction_actions_project_acknowledgement_guard():
    raw = graph().model_dump(mode='json')
    raw['entry_block_id'] = 'read'
    raw['entry_points'] = []
    raw['blocks'].insert(0, {'id': 'read', 'kind': 'instruction', 'title': 'Read', 'content': {'body': 'Read'},
        'transition_mode': 'buttons', 'transitions': [{'to': 'questions', 'button': {'key': 'ok', 'label': 'OK'},
        'when': {'source': 'current_result', 'op': 'eq', 'value': 'acknowledged'}}]})
    engine = ScenarioRuntime(ScenarioDefinition.model_validate(raw))
    state = engine.initial_state()
    assert project_step(engine.definition, state)['block']['actions'] == [{'key': 'ok', 'label': 'OK'}]


def test_resolution_check_rejects_button_mode():
    from tickets.request_scenario_validation import validate_scenario
    raw = graph().model_dump(mode='json')
    raw['blocks'].insert(0, {'id': 'check', 'kind': 'resolution_check', 'title': 'Check',
        'transition_mode': 'buttons', 'transitions': [{'to': 'questions', 'button': {'key': 'go', 'label': 'Go'}}]})
    raw['entry_block_id'] = 'check'
    assert any(issue.code == 'invalid_transition_mode' for issue in validate_scenario(ScenarioDefinition.model_validate(raw)))


def test_upgrade_equivalence_rejects_business_changes():
    from tickets.request_scenario_conversion import upgrade_scenario_to_v4, assert_upgrade_equivalent
    from tests.test_request_scenario_runtime import pilot
    original = pilot()
    upgrade = upgrade_scenario_to_v4(original)
    assert_upgrade_equivalent(original, upgrade)
    changed = upgrade.model_copy(deep=True)
    changed.blocks[0].fields[0].required = False
    with pytest.raises(ValueError):
        assert_upgrade_equivalent(original, changed)

@pytest.mark.parametrize('version', [1, 2, 3])
def test_upgrade_proves_effective_source_equivalence(version):
    from tests.test_request_scenario_runtime import pilot
    from tickets.request_scenario_conversion import upgrade_scenario_to_v4, assert_upgrade_equivalent
    raw = pilot() if version < 3 else definition().model_dump(mode='json')
    raw['schema_version'] = version
    if version == 2:
        raw['entry_points'] = [{'key': 'main', 'title': 'Main', 'target_block_id': raw['entry_block_id']}]
    assert_upgrade_equivalent(raw, upgrade_scenario_to_v4(raw))


def test_upgrade_proves_optional_screenshot_stage_equivalence():
    from tests.test_request_scenario_optional_evidence import legacy_definition
    from tickets.request_scenario_conversion import upgrade_scenario_to_v4, assert_upgrade_equivalent
    original = legacy_definition().model_dump(mode='json')
    upgraded = upgrade_scenario_to_v4(original)
    assert_upgrade_equivalent(original, upgraded)
    runtime = ScenarioRuntime(ScenarioDefinition.model_validate(upgraded.model_dump(mode='json')))
    assert not runtime.blocks['q_evidence'].fields[0].required

def test_instruction_button_cannot_require_unavailable_request_ticket_result():
    from tickets.request_scenario_validation import validate_scenario
    raw = graph().model_dump(mode='json')
    raw['entry_block_id'] = 'read'
    raw['entry_points'] = []
    raw['blocks'].insert(0, {'id': 'read', 'kind': 'instruction', 'title': 'Read', 'content': {'body': 'Read'},
        'transition_mode': 'buttons', 'transitions': [{'to': 'questions', 'button': {'key': 'go', 'label': 'Go'},
        'when': {'source': 'current_result', 'op': 'eq', 'value': 'request_ticket'}}]})
    issues = validate_scenario(ScenarioDefinition.model_validate(raw))
    assert any(issue.code == 'invalid_button_result' for issue in issues)

@pytest.mark.asyncio
async def test_material_content_comparison_handles_plain_attachment_refs():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from tickets.request_scenario_assets import material_content_definition
    asset_id = '00000000-0000-0000-0000-000000000001'
    ref = {'asset_id': asset_id, 'name': 'a', 'mime_type': 'text/plain', 'size_bytes': 1,
           'url': f'/api/web/request-scenario-assets/{asset_id}/download'}
    row = SimpleNamespace(id=asset_id, scenario_id='scenario', removed_at=None, name='a', mime_type='text/plain', size_bytes=1, sha256='a'*64)
    session = SimpleNamespace(get=AsyncMock(return_value=row))
    data = {'blocks': [{'content': {'attachments': [ref]}}]}
    result = await material_content_definition(session, 'scenario', data)
    assert result['blocks'][0]['content']['attachments'][0]['material_index'] == 0

@pytest.mark.asyncio
async def test_direct_v4_service_creation_passes_version_gate():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from app.repos.request_scenario_repo import RequestScenarioRepo
    class ReachedServiceLock(Exception):
        pass
    repo = RequestScenarioRepo.__new__(RequestScenarioRepo)
    repo._service_lock = AsyncMock(side_effect=ReachedServiceLock())
    with pytest.raises(ReachedServiceLock):
        await repo.create_service({'schema_version': 4, 'service_code': 'workplace'})

def test_upgrade_preserves_v2_catalog_entrance_requirement():
    from tickets.request_scenario_conversion import upgrade_scenario_to_v4
    from tickets.request_scenario_validation import validate_scenario
    from tests.test_request_scenario_unified import source
    raw = source()
    raw['entry_points'] = []
    original_issues = validate_scenario(ScenarioDefinition.model_validate(raw))
    upgraded_issues = validate_scenario(ScenarioDefinition.model_validate(upgrade_scenario_to_v4(raw).model_dump(mode='json')))
    assert any(issue.code == 'catalog_entry_required' for issue in original_issues)
    assert any(issue.code == 'catalog_entry_required' for issue in upgraded_issues)
