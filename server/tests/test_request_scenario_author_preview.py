from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from tickets.request_scenario_runtime import ScenarioInputError, ScenarioRuntime
from tickets.request_scenario_simulation import simulation_definition
from tickets.request_scenario_validation import ScenarioValidationError
from web_api.dto.request_scenario import ScenarioAnswerRequest
from web_api.dto.request_scenario_admin import SimulationInput

pytestmark = pytest.mark.no_db

def draft():
    return {'schema_version':4,'execution_semantics':3,'scenario_key':'preview','service_code':'it','offering_full_code':'it.preview','title':'Preview','entry_block_id':'q','entry_points':[],
      'processing':{'routes':{},'sla_profiles':{},'defaults':{'route':'','sla_profile':''}},'process_binding':{'request_template_key':'request'},
      'blocks':[{'id':'q','kind':'form_page','title':'Вопрос','fields':[{'key':'name','type':'text','label':'Имя','required':True}],
        'transition_mode':'buttons','transitions':[{'to':'a','button':{'key':'a','label':'Первый путь'}},{'to':'b','button':{'key':'b','label':'Второй путь'}}]},
       {'id':'a','kind':'form_page','title':'Первый','fields':[{'key':'first','type':'text','label':'Первый ответ'}],'transitions':[]},
       {'id':'b','kind':'instruction','title':'Второй','content':{'body':'Проверка'},'transitions':[]}]}

def engine(raw=None):
    from tickets.request_scenario_author_preview import AuthorPreviewRuntime
    definition,scope=simulation_definition(raw or draft(),author_preview=True)
    return AuthorPreviewRuntime(definition),scope

def answer(state,values=None,key=None):
    return ScenarioAnswerRequest.model_validate({'revision':state.revision,'expected_block_id':state.current_block_id,'answers':values or {},**({'action_key':key} if key else {})})

def test_strict_runtime_and_simulation_still_reject_incomplete_draft():
    with pytest.raises(ScenarioValidationError):simulation_definition(draft())
    value,_=simulation_definition(draft(),author_preview=True)
    with pytest.raises(ScenarioValidationError):ScenarioRuntime(value)
    assert SimulationInput.model_validate({'revision':1}).author_preview is False

def test_preview_walks_both_buttons_and_stops_at_unfinished_leaf():
    runtime,scope=engine();state=runtime.initial_state()
    codes = {issue['code'] for issue in scope['issues']}
    assert 'missing_fallback' in codes
    assert 'processing_default_missing' not in codes  # V4 omissions inherit service processing.
    state=runtime.advance(state,answer(state,{'name':'Тест'},'a'))
    assert state.current_block_id=='a' and state.history==['q'] and state.state=='active'
    assert runtime.stop_for(state)=={'code':'missing_continuation','block_id':'a'}
    returned=runtime.back(state,'q',expected_revision=state.revision)
    second=runtime.advance(returned,answer(returned,{'name':'Другой'},'b'))
    assert second.current_block_id=='b' and 'first' not in second.answers
    assert runtime.stop_for(second)['code']=='missing_continuation'

def test_preview_uses_required_normalization_and_dynamic_visibility():
    raw=draft();raw['blocks'][0]['fields']=[{'key':'show','type':'checkbox','label':'Показать?'},{'key':'detail','type':'text','label':'Деталь','required':True,'visible_when':{'op':'eq','source':'answer','field':'show','value':True}}];raw['blocks'][0]['layout']='group'
    runtime,_=engine(raw);state=runtime.initial_state()
    with pytest.raises(ScenarioInputError) as error:runtime.advance(state,answer(state,{'show':True},'a'))
    assert 'detail' in error.value.errors
    next_state=runtime.advance(state,answer(state,{'show':False,'detail':'скрытый ответ'},'a'))
    assert 'detail' not in next_state.answers

def test_missing_automatic_continuation_stops_without_a_phantom_traversed_step():
    raw=draft();raw['blocks'][0]['transitions'][0]['to']='branch';raw['blocks'].append({'id':'branch','kind':'decision','title':'Условие','transitions':[]})
    runtime,_=engine(raw);state=runtime.initial_state();state=runtime.advance(state,answer(state,{'name':'Тест'},'a'))
    assert state.current_block_id=='branch' and state.history==['q']
    assert runtime.stop_for(state)['block_id']=='branch'

@pytest.mark.parametrize('change',[
    lambda raw:raw['blocks'][0]['transitions'][0].update(to='unknown'),
    lambda raw:raw['blocks'][1]['transitions'].append({'to':'q'}),
    lambda raw:raw['blocks'][0]['fields'][0].update(key='actor_role'),
    lambda raw:raw['blocks'][0].update(transition_mode=None,transitions=[{'to':'a'},{'to':'b'}]),
    lambda raw:raw['processing']['defaults'].update(route='unknown_route'),
])
def test_author_preview_does_not_accept_unsafe_or_ambiguous_graphs(change):
    raw=draft();change(raw)
    with pytest.raises(ScenarioValidationError):engine(raw)

@pytest.mark.asyncio
async def test_repo_author_preview_is_read_only_and_has_explicit_stop():
    from app.repos.request_scenario_repo import RequestScenarioRepo
    session=SimpleNamespace(add=AsyncMock(),flush=AsyncMock(),commit=AsyncMock())
    repo=RequestScenarioRepo(session,None);repo.detail=AsyncMock(return_value=(SimpleNamespace(archived=False),SimpleNamespace(revision=1,definition=draft())))
    result=await repo.simulate('owned',SimulationInput.model_validate({'revision':1,'author_preview':True,'steps':[{'expected_block_id':'q','revision':1,'answers':{'name':'Тест'},'action_key':'a'}]}))
    assert result['current_step']['id']=='a' and result['preview_stop']['code']=='missing_continuation'
    assert result['processing'] is None
    session.add.assert_not_called();session.flush.assert_not_called();session.commit.assert_not_called()

@pytest.mark.asyncio
async def test_unfinished_terminal_processing_is_explicit_and_never_invents_sla(monkeypatch):
    from app.repos.request_scenario_repo import RequestScenarioRepo
    from tickets import service_catalog_preview
    processing=AsyncMock();monkeypatch.setattr(service_catalog_preview,'simulate_service_catalog_processing',processing)
    raw=draft();raw['blocks'][1]={'id':'a','kind':'submit_ticket','title':'Создание обращения','transitions':[]}
    repo=RequestScenarioRepo(SimpleNamespace(),None);repo.detail=AsyncMock(return_value=(SimpleNamespace(archived=False),SimpleNamespace(revision=1,definition=raw)))
    result=await repo.simulate('owned',SimulationInput.model_validate({'revision':1,'author_preview':True,'steps':[{'expected_block_id':'q','revision':1,'answers':{'name':'Тест'},'action_key':'a'}]}))
    assert result['processing'] is None and result['processing_error']=={'code':'AUTHOR_PREVIEW_INCOMPLETE'}
    processing.assert_not_called()
