"""v4 policy attachments affect visited targets, never the employee graph."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from tests.test_request_scenario_terminal_sla import graph, submission
from tickets.request_scenario_validation import validate_scenario
from tickets.request_scenario_runtime import ScenarioRuntime, RuntimeState
from tickets.request_scenario_submission import build_scenario_submission
from web_api.dto.request_scenario import ScenarioDefinition, ScenarioDraftDefinition, ScenarioAnswerRequest
pytestmark = pytest.mark.no_db


def attachment(raw, kind='sla_attachment', target='questions', **settings):
    value={'id':kind, 'kind':kind, 'title':kind, 'attached_to':target, **settings}
    raw['blocks'].append(value)
    return value


def test_attachment_before_edge_then_final_explicit_values_win():
    raw=graph(route='default',sla_profile='standard')
    attachment(raw,sla_profile='standard',processing_facts={'impact':'department'})
    attachment(raw,'routing_attachment',route='default')
    selected=submission(raw)
    assert selected['map_processing']['route']['key']=='default'
    assert selected['map_processing']['route']['source']=={'kind':'terminal','block_id':'submit'}
    assert selected['map_processing']['sla_profile']['key']=='standard'
    assert selected['processing_facts']['impact']=='department'
    terminal=next(b for b in raw['blocks'] if b['kind']=='submit_ticket')
    terminal.pop('route'); terminal.pop('sla_profile')
    selected=submission(raw)
    assert selected['map_processing']['route']['key']=='printing'
    assert selected['map_processing']['sla_profile']['key']=='urgent'
    selected=submission(raw,'one')
    assert selected['map_processing']['route']['key']=='default'
    assert selected['map_processing']['route']['source']['kind']=='attachment'


def test_terminal_attachments_contribute_facts_and_precede_terminal_overrides():
    raw=graph(route='default',sla_profile='standard')
    attachment(raw,target='submit',sla_profile='urgent',processing_facts={'urgency':'blocked'})
    attachment(raw,'routing_attachment',target='submit',route='printing')
    snapshot=submission(raw,'one')
    assert snapshot['processing_facts']=={'urgency':'blocked'}
    assert snapshot['map_processing']['route']['key']=='default'
    assert snapshot['map_processing']['sla_profile']['key']=='standard'


def test_unvisited_branch_attachment_and_backtracking_contribute_nothing():
    raw=graph()
    raw['blocks'][0]['transitions'][0]['to']='branch'
    raw['blocks'].append({'id':'branch','kind':'instruction','title':'Branch','content':{'body':'Branch'},'transitions':[{'to':'submit'}]})
    attachment(raw,target='branch',sla_profile='urgent',processing_facts={'urgency':'blocked'})
    engine=ScenarioRuntime(ScenarioDefinition.model_validate(raw))
    state=engine.advance(engine.initial_state(),ScenarioAnswerRequest(expected_block_id='questions',revision=1,answers={'affected':'all'}))
    assert state.current_block_id=='branch'
    state=engine.advance(state,ScenarioAnswerRequest(expected_block_id='branch',revision=state.revision,current_result='acknowledged'))
    first=build_scenario_submission(engine.definition,state,session_id='s',version_id='v')[1]
    assert first['processing_facts']['urgency']=='blocked'
    back=engine.back(state,'questions',expected_revision=state.revision)
    state=engine.advance(back,ScenarioAnswerRequest(expected_block_id='questions',revision=back.revision,answers={'affected':'one'}))
    snapshot=build_scenario_submission(engine.definition,state,session_id='s',version_id='v')[1]
    assert snapshot['processing_facts']=={}
    assert snapshot['map_processing']['sla_profile']['key']=='standard'
    assert 'sla_attachment' not in state.history


@pytest.mark.parametrize('target',[None,'missing','routing_attachment','sla_attachment'])
def test_invalid_or_unattached_target_is_a_publish_issue(target):
    raw=graph(); attachment(raw,target=target); attachment(raw,'routing_attachment',target='submit')
    value=ScenarioDraftDefinition.model_validate(raw)
    issues=validate_scenario(value)
    assert any(i.path=='blocks.sla_attachment.attached_to' for i in issues)
    assert not any(i.code in {'missing_fallback','unreachable_block'} and 'sla_attachment' in i.path for i in issues)


def test_duplicate_attachment_and_flow_target_are_rejected():
    raw=graph(); attachment(raw)
    raw['blocks'].append({'id':'another','kind':'sla_attachment','title':'Another','attached_to':'questions'})
    raw['blocks'][0]['transitions'][0]['to']='sla_attachment'
    issues=validate_scenario(ScenarioDefinition.model_validate(raw))
    assert {'duplicate_attachment','modifier_flow_target'} <= {i.code for i in issues}
    raw['entry_block_id']='sla_attachment'
    assert any(i.code=='modifier_flow_target' and i.path=='entry_block_id' for i in validate_scenario(ScenarioDefinition.model_validate(raw)))


@pytest.mark.parametrize('version',[1,2,3])
def test_attachments_and_terminal_routes_reject_old_versions(version):
    for attached in [True,False]:
        raw=graph(); raw['schema_version']=version; raw.pop('execution_semantics')
        if attached: attachment(raw)
        else: raw['blocks'][1]['route']='default'
        with pytest.raises(ValueError,match='schema_version 4'):
            ScenarioDefinition.model_validate(raw)


def test_no_transition_fields_on_modifier_wire_and_no_new_inherited_terminal_fields():
    raw=graph(); item=attachment(raw)
    value=ScenarioDefinition.model_validate(raw)
    encoded=value.model_dump(mode='json')
    assert 'transitions' not in encoded['blocks'][-1]
    assert 'route' not in encoded['blocks'][1] and 'routing_policy_ref' not in encoded['blocks'][1]
    item['transitions']=[]
    with pytest.raises(ValueError): ScenarioDefinition.model_validate(raw)


@pytest.mark.parametrize('field,value', [('route','missing'),('routing_policy_ref','policy')])
def test_map_route_reference_and_policy_source_validation(field,value):
    raw=graph(**{field:value})
    assert any(i.path.startswith('blocks.submit') for i in validate_scenario(ScenarioDefinition.model_validate(raw)))


def test_registry_policy_attachments_and_terminal_override():
    raw=graph(routing_policy_ref='final_route',policy_ref='final_sla'); raw['processing']=None
    raw['blocks'][0]['transitions']=[{'to':'submit'}]
    raw['process_binding']['policy_refs']={'routing':'default_route','sla':'default_sla'}
    attachment(raw,policy_ref='attached_sla')
    attachment(raw,'routing_attachment',policy_ref='attached_route')
    selected=submission(raw)
    assert selected['policy_refs']=={'routing':'final_route','sla':'final_sla'}
    assert selected['routing_selection']=={'kind':'policy','key':'final_route','source':{'kind':'terminal','block_id':'submit'}}


@pytest.mark.parametrize('format',['json','yaml'])
def test_document_roundtrip_and_fragment_internal_attachment_remap(format):
    from tickets.request_scenario_document import export_scenario_document,parse_scenario_document
    from tickets.request_scenario_fragments import extract_fragment,insert_fragment
    raw=graph(route='printing'); attachment(raw,target='submit',sla_profile='urgent')
    restored=parse_scenario_document(export_scenario_document(raw,format),format)
    assert restored.blocks[-1].attached_to=='submit'
    fragment,deps=extract_fragment(raw,['submit','sla_attachment'])
    merged,ids=insert_fragment(raw,fragment,position={'x':0,'y':0},mappings={'routes':{'printing':'default'},'sla_profiles':{'urgent':'standard'}})
    added=[b for b in merged['blocks'] if b['id'] in ids]
    assert added[1]['attached_to']==added[0]['id']
    assert added[1]['sla_profile']=='standard' and added[0]['route']=='default'


def test_fragment_external_attachment_requires_explicit_block_mapping():
    from tickets.request_scenario_fragments import extract_fragment,insert_fragment,FragmentDependencyError
    raw=graph(); attachment(raw,target='submit')
    fragment,deps=extract_fragment(raw,['sla_attachment'])
    assert {'kind':'attachment_target','key':'submit','label':'submit'} in deps
    with pytest.raises(FragmentDependencyError): insert_fragment(raw,fragment,position={'x':0,'y':0},mappings={})
    target=deepcopy(raw); target['blocks'].pop()
    merged,ids=insert_fragment(target,fragment,position={'x':0,'y':0},mappings={'blocks':{'submit':'questions'}})
    assert merged['blocks'][-1]['attached_to']=='questions'


def test_readiness_skips_modifier_steps_and_scoped_simulation_preserves_settings():
    from tickets.request_scenario_readiness import submission_variants
    from tickets.request_scenario_simulation import simulation_definition
    raw=graph(); attachment(raw,target='submit',sla_profile='urgent')
    value=ScenarioDefinition.model_validate(raw)
    states=submission_variants(value)
    assert states and all('sla_attachment' not in state.history for state in states)
    assert {build_scenario_submission(value,state,session_id='s',version_id='v')[1]['map_processing']['sla_profile']['key'] for state in states}=={'urgent'}
    raw['blocks'].append({'id':'unconnected','kind':'review','title':'Unconnected','transitions':[]})
    effective,scope=simulation_definition(raw)
    assert scope['excluded_block_ids']==['unconnected']
    assert effective.blocks[-1].kind=='sla_attachment'
    assert submission(effective.model_dump(mode='json'))['map_processing']['sla_profile']['key']=='urgent'


@pytest.mark.asyncio
async def test_routing_reference_availability_checked_for_all_targets(monkeypatch):
    import tickets.request_scenario_processing as processing
    from tickets.request_scenario_document import document_reference_issues
    raw=graph(routing_policy_ref='missing_final');raw['processing']=None
    raw['blocks'][0]['transitions']=[{'to':'submit'}]
    attachment(raw,'routing_attachment',policy_ref='missing_attachment')
    resolver=AsyncMock(side_effect=ValueError('unavailable'))
    monkeypatch.setattr(processing,'apply_scenario_policy_refs',resolver)
    issues=await document_reference_issues(SimpleNamespace(),ScenarioDefinition.model_validate(raw))
    assert {i['path'] for i in issues}=={'blocks.submit.routing_policy_ref','blocks.routing_attachment.policy_ref'}
    assert [call.args[2] for call in resolver.await_args_list]==[{'routing':'missing_final'},{'routing':'missing_attachment'}]


@pytest.mark.parametrize('semantics',[1,2,3])
def test_v4_attachment_preserves_execution_semantics(semantics):
    raw=graph();raw['execution_semantics']=semantics
    raw['entry_points']=[{'key':'main','title':'Main','target_block_id':'questions'}]
    attachment(raw,target='submit',sla_profile='urgent')
    value=ScenarioDefinition.model_validate(raw)
    assert value.execution_semantics==semantics
    assert submission(raw)['map_processing']['sla_profile']['key']=='urgent'


def test_later_target_settings_win_independently_without_adding_sla_minutes():
    raw=graph();raw['blocks'][0]['transitions']=[{'to':'later'}]
    raw['blocks'].append({'id':'later','kind':'review','title':'Later','transitions':[{'to':'submit'}]})
    attachment(raw,sla_profile='urgent',processing_facts={'impact':'department','urgency':'blocked'})
    raw['blocks'].append({'id':'later_sla','kind':'sla_attachment','title':'Later SLA','attached_to':'later','sla_profile':'standard','processing_facts':{'impact':'single_user'}})
    attachment(raw,'routing_attachment',route='printing')
    value=ScenarioDefinition.model_validate(raw)
    state=RuntimeState('submit',3,{'affected':'one'},['questions','later'],{})
    snapshot=build_scenario_submission(value,state,session_id='s',version_id='v')[1]
    assert snapshot['map_processing']['route']['key']=='printing'
    assert snapshot['map_processing']['sla_profile']['key']=='standard'
    assert snapshot['map_processing']['sla_profile']['resolution_minutes']==300
    assert snapshot['map_processing']['sla_profile']['source']['block_id']=='later_sla'
    assert snapshot['processing_facts']=={'impact':'department','urgency':'blocked'}


@pytest.mark.asyncio
async def test_saved_fragment_resolves_routing_policy_as_routing_before_cloning(monkeypatch):
    import tickets.request_scenario_fragment_library as library
    import tickets.request_scenario_processing as processing
    from tickets.request_scenario_fragments import extract_fragment
    from web_api.dto.request_scenario_fragments import FragmentInsert
    raw=graph();raw['processing']=None;raw['blocks'][0]['transitions']=[{'to':'submit'}]
    attachment(raw,'routing_attachment',target='submit',policy_ref='source_route')
    fragment,_=extract_fragment(raw,['routing_attachment'])
    destination=deepcopy(raw);destination['blocks'].pop()
    saved=SimpleNamespace(id='fragment',archived=False,revision=1,definition=fragment)
    monkeypatch.setattr(library,'get_fragment',AsyncMock(return_value=saved))
    row=SimpleNamespace(id='destination',service_code='workplace',archived=False)
    draft=SimpleNamespace(revision=1,definition=destination)
    repo=SimpleNamespace(detail=AsyncMock(return_value=(row,draft)),_service_lock=AsyncMock(),
        session=SimpleNamespace(scalars=AsyncMock(return_value=SimpleNamespace(all=lambda:[]))),
        auth=SimpleNamespace(actor_id='admin'),save=AsyncMock(return_value={}),_audit=AsyncMock())
    resolve=AsyncMock(return_value={'template_context':{}})
    monkeypatch.setattr(processing,'apply_scenario_policy_refs',resolve)
    clone=AsyncMock(return_value=(fragment,{}));monkeypatch.setattr(library,'clone_material_assets',clone)
    result=await library.insert_saved_fragment(repo,'destination','fragment',FragmentInsert(revision=1,fragment_revision=1,
        position={'x':0,'y':0},mappings={'blocks':{'submit':'submit'},'policy_refs':{'source_route':'published_route'}}))
    assert result['inserted_block_ids']
    assert resolve.await_args.args[2]=={'routing':'published_route'}


@pytest.mark.asyncio
async def test_full_scenario_copy_preserves_modifiers_and_terminal_overrides(monkeypatch):
    from app.repos.request_scenario_repo import RequestScenarioRepo
    import app.repos.request_scenario_repo as repository
    import tickets.request_scenario_assets as assets
    raw=graph(route='printing',sla_profile='urgent');attachment(raw,target='submit',sla_profile='standard')
    value=ScenarioDraftDefinition.model_validate(raw)
    added=[]
    def add(row):
        if not getattr(row,'id',None) and hasattr(row,'scenario_key'):row.id='new_scenario'
        added.append(row)
    repo=RequestScenarioRepo.__new__(RequestScenarioRepo)
    repo.session=SimpleNamespace(add=add,flush=AsyncMock());repo.auth=SimpleNamespace(actor_id='admin')
    repo._service_lock=AsyncMock();repo._binding=AsyncMock();repo._audit=AsyncMock()
    monkeypatch.setattr(assets,'copy_material_sources',AsyncMock(return_value={}))
    monkeypatch.setattr(repository,'serialize',lambda row:dict(vars(row)))
    result=await repo.create(value,copy_source_id='original')
    copied=ScenarioDraftDefinition.model_validate(result['draft']['definition'])
    assert copied.blocks[-1].attached_to=='submit'
    assert copied.blocks[1].route=='printing' and copied.blocks[1].sla_profile=='urgent'
    assert result['asset_rebindings']=={}
    assert 'transitions' not in result['draft']['definition']['blocks'][-1]
    assert raw['blocks'][-1]['attached_to']=='submit'


@pytest.mark.asyncio
async def test_final_route_reaches_canonical_adapter_and_queue_availability():
    from tickets.request_scenario_processing import apply_scenario_map_processing,ScenarioProcessingUnavailable
    snapshot=submission(graph(route='printing'),'one')
    session=SimpleNamespace(scalar=AsyncMock(return_value=SimpleNamespace(id=8,code='printing',is_active=True)))
    result=await apply_scenario_map_processing(session,{'template_context':{'routing_policy':{'fallback':{'queue_id':1}}}},snapshot['map_processing'])
    assert result['template_context']['routing_policy']['fallback']=={'queue_id':8,'queue_code':'printing'}
    assert result['template_context']['scenario_processing']['route']['source']=={'kind':'terminal','block_id':'submit'}
    session.scalar.return_value.is_active=False
    with pytest.raises(ScenarioProcessingUnavailable):
        await apply_scenario_map_processing(session,{'template_context':{}},snapshot['map_processing'])


@pytest.mark.parametrize('kind,settings,processing',[
    ('routing_attachment',{'route':'missing'},True),
    ('sla_attachment',{'sla_profile':'missing'},True),
    ('routing_attachment',{'policy_ref':'published'},True),
    ('sla_attachment',{'policy_ref':'published'},True),
    ('routing_attachment',{'route':'default'},False),
    ('sla_attachment',{'sla_profile':'standard'},False),
    ('routing_attachment',{'route':'default','policy_ref':'published'},True),
    ('sla_attachment',{'sla_profile':'standard','policy_ref':'published'},True),
])
def test_attachment_source_must_match_processing_context(kind,settings,processing):
    raw=graph();attachment(raw,kind,**settings)
    if not processing:
        raw['processing']=None;raw['blocks'][0]['transitions']=[{'to':'submit'}]
    issues=validate_scenario(ScenarioDefinition.model_validate(raw))
    assert any(i.path.startswith('blocks.'+kind) for i in issues)


def test_modifiers_cannot_be_catalog_entrances_or_expose_button_mode():
    raw=graph();item=attachment(raw)
    raw['entry_points']=[{'key':'wrong','title':'Wrong','target_block_id':'sla_attachment'}]
    assert any(i.code=='modifier_flow_target' and i.path=='entry_points.wrong.target_block_id' for i in validate_scenario(ScenarioDefinition.model_validate(raw)))
    item['transition_mode']='buttons'
    with pytest.raises(ValueError):ScenarioDefinition.model_validate(raw)


@pytest.mark.parametrize('terminal',[False,True])
def test_fragment_policy_dependencies_distinguish_identical_registry_codes(terminal):
    from tickets.request_scenario_fragments import extract_fragment,insert_fragment,FragmentDependencyError
    raw=graph(**({'policy_ref':'shared','routing_policy_ref':'shared'} if terminal else {}))
    raw['processing']=None;raw['blocks'][0]['transitions']=[{'to':'submit'}]
    ids=['submit']
    if not terminal:
        attachment(raw,target='submit',policy_ref='shared')
        attachment(raw,'routing_attachment',target='submit',policy_ref='shared')
        ids+=['sla_attachment','routing_attachment']
    fragment,deps=extract_fragment(raw,ids)
    assert {(dep['kind'],dep['key']) for dep in deps}=={('sla_policy_ref','shared'),('routing_policy_ref','shared')}
    mappings={'sla_policy_refs':{'shared':'sla_destination'},'routing_policy_refs':{'shared':'routing_destination'}}
    result,inserted=insert_fragment(raw,fragment,position={'x':0,'y':0},mappings=mappings)
    blocks={b['kind']:b for b in result['blocks'] if b['id'] in inserted}
    if terminal:
        assert blocks['submit_ticket']['policy_ref']=='sla_destination'
        assert blocks['submit_ticket']['routing_policy_ref']=='routing_destination'
    else:
        assert blocks['sla_attachment']['policy_ref']=='sla_destination'
        assert blocks['routing_attachment']['policy_ref']=='routing_destination'
    with pytest.raises(FragmentDependencyError) as error:
        insert_fragment(raw,fragment,position={'x':0,'y':0},mappings={'policy_refs':{'shared':'legacy_sla'}})
    assert {dep['kind'] for dep in error.value.dependencies}=={'routing_policy_ref'}
    legacy={**mappings,'policy_refs':{'shared':'legacy_sla'}};legacy.pop('sla_policy_refs')
    result,inserted=insert_fragment(raw,fragment,position={'x':0,'y':0},mappings=legacy)
    added=[b for b in result['blocks'] if b['id'] in inserted]
    assert next(b for b in added if b['kind']==('submit_ticket' if terminal else 'sla_attachment'))['policy_ref']=='legacy_sla'


def test_fragment_mapping_dto_accepts_kind_specific_and_legacy_sla_maps():
    from web_api.dto.request_scenario_fragments import FragmentMappings
    value=FragmentMappings.model_validate({'sla_policy_refs':{'shared':'sla_dest'},'routing_policy_refs':{'shared':'route_dest'},'policy_refs':{'old_sla':'legacy_dest'}})
    assert value.sla_policy_refs['shared']=='sla_dest'
    assert value.routing_policy_refs['shared']=='route_dest'
    assert value.policy_refs['old_sla']=='legacy_dest'


def test_legacy_sequential_sla_fragment_still_accepts_old_policy_mapping():
    from tickets.request_scenario_fragments import extract_fragment,insert_fragment
    raw=graph();raw['processing']=None;raw['blocks'][0]['transitions']=[{'to':'legacy_sla'}]
    raw['blocks'].append({'id':'legacy_sla','kind':'sla','title':'Legacy','policy_ref':'old_sla','transitions':[{'to':'submit'}]})
    fragment,deps=extract_fragment(raw,['legacy_sla','submit'])
    assert {'kind':'sla_policy_ref','key':'old_sla','label':'old_sla'} in deps
    result,ids=insert_fragment(raw,fragment,position={'x':0,'y':0},mappings={'policy_refs':{'old_sla':'new_sla'}})
    assert next(b for b in result['blocks'] if b['id'] in ids and b['kind']=='sla')['policy_ref']=='new_sla'
