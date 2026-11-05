from copy import deepcopy
import json
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / 'server'))


def test_new_information_services_inherit_processing_and_safe_submission_questions():
    from scripts.helpdesk_phase1_catalog import build_definitions as phase1
    from scripts.helpdesk_catalog_service_search import build_definitions
    from web_api.dto.request_scenario import ScenarioDefinition
    from tickets.request_scenario_validation import validate_scenario
    base = json.loads((Path(__file__).parents[1] / 'server/tests/fixtures/phase1_other_base.json').read_text(encoding='utf-8'))
    source = next(d for d in phase1(base) if d['scenario_key'] == 'phase1_business_system')
    before = deepcopy(source)
    definitions = build_definitions(source, 'information_systems')
    assert [d['title'] for d in definitions] == ['Электронный бюджет', 'ЕИС — Единая информационная система в сфере закупок']
    for raw in definitions:
        assert raw['processing'] == source['processing']
        assert raw['process_binding']['policy_refs'] == source['process_binding']['policy_refs']
        assert len(raw['entry_points']) == 3
        assert not raw['process_binding']['request_template_key']
        bound = {**raw, 'offering_full_code': 'information_systems.test',
            'process_binding': {**raw['process_binding'], 'request_template_key': 'general_request'}}
        assert not validate_scenario(ScenarioDefinition.model_validate(bound))
    assert source == before


@pytest.mark.asyncio
async def test_publication_rejects_untrusted_actor_before_opening_database():
    from types import SimpleNamespace
    from scripts.helpdesk_catalog_service_search import publish_additions
    def forbidden_factory():
        raise AssertionError('Must not open database')
    with pytest.raises(ValueError, match='admin'):
        await publish_additions(forbidden_factory, SimpleNamespace(is_admin=lambda: False, actor_id='someone'), apply=True)
