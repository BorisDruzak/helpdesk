import pytest
from web_api.dto.request_scenario import ScenarioDraftDefinition
from tickets.request_scenario_validation import validate_scenario, ScenarioValidationError
from tickets.request_scenario_author_preview import require_author_preview_definition

pytestmark=pytest.mark.no_db

def raw():
    return {'schema_version':1,'scenario_key':'pending','service_code':'it','offering_full_code':'it.pending','title':'Test','entry_block_id':'done','blocks':[{'id':'done','kind':'submit_ticket','title':'Ticket'}],'process_binding':{'request_template_key':'request'}}

def test_pending_catalog_entrance_roundtrips_without_becoming_a_runtime_entry():
    value=raw();value['editor_layout']={'pending_entrances':[{'key':'draft_entry','title':'Новый вход','position':{'x':120,'y':50}}]}
    model=ScenarioDraftDefinition.model_validate(value)
    assert model.entry_points==[]
    assert model.model_dump(mode='json')['editor_layout']['pending_entrances']==value['editor_layout']['pending_entrances']
    assert 'unconnected_catalog_entry' in {x.code for x in validate_scenario(model)}
    require_author_preview_definition(model)

def test_empty_pending_metadata_does_not_change_legacy_serialization():
    assert ScenarioDraftDefinition.model_validate(raw()).model_dump(mode='json')['editor_layout']=={'positions':{}}

def test_pending_keys_cannot_shadow_existing_entrances_or_exceed_total_limit():
    value=raw();value['entry_points']=[{'key':'same','title':'Old','target_block_id':'done'}]
    value['editor_layout']={'pending_entrances':[{'key':'same','title':'New','position':{'x':0,'y':0}}]}
    model=ScenarioDraftDefinition.model_validate(value)
    assert 'duplicate_entry' in {x.code for x in validate_scenario(model)}
    with pytest.raises(ScenarioValidationError):require_author_preview_definition(model)

def test_combined_entrance_limit_blocks_publication_and_author_preview():
    value=raw();value['entry_points']=[{'key':f'e{i}','title':'Entry','target_block_id':'done'} for i in range(64)]
    value['editor_layout']={'pending_entrances':[{'key':'new','title':'New','position':{'x':0,'y':0}}]}
    model=ScenarioDraftDefinition.model_validate(value)
    assert 'entry_limit' in {x.code for x in validate_scenario(model)}
    with pytest.raises(ScenarioValidationError):require_author_preview_definition(model)

@pytest.mark.parametrize('point',[{'x':float('nan'),'y':0},{'x':100001,'y':0},{'x':0,'y':float('inf')}])
def test_pending_entrance_positions_are_bounded(point):
    value=raw();value['editor_layout']={'pending_entrances':[{'key':'entry','title':'New','position':point}]}
    with pytest.raises(ValueError):ScenarioDraftDefinition.model_validate(value)
