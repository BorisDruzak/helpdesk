import pytest

pytestmark = pytest.mark.no_db

@pytest.mark.asyncio
async def test_explicitly_unlisted_registry_template_is_not_merged_into_public_forms(monkeypatch):
    from tickets import form_pack_handlers as handlers
    class Repo:
        def __init__(self, session): pass
        async def list_form_schemas(self, **kwargs): return []
        async def list_request_templates(self, **kwargs):
            return [{'template_code':'test_mail','config':{'requester_catalog':{'visible':False}}}]
    monkeypatch.setattr(handlers,'HelpdeskPolicyRepo',Repo)
    def unexpected(*args, **kwargs): raise AssertionError('Unlisted template must not resolve a public form')
    monkeypatch.setattr(handlers,'_find_registry_form_schema',unexpected)
    original={'pack_key':'request_forms','version':'1','forms':[]}
    assert await handlers._merge_registry_requester_forms(None,original) == original

def test_cleanup_preserves_template_processing_and_only_changes_discovery_config():
    from scripts.helpdesk_requester_catalog_cleanup import publication_payload
    template={'template_code':'test_mail','public_title':'Тест','version':'1','is_active':True,
              'ticket_type':'incident','routing_policy_code':'route','form_schema_id':'schema',
              'config':{'custom':'keep'},'overrides':{'priority':'P3'}}
    result=publication_payload(template)
    assert result['routing_policy_code']=='route' and result['form_schema_id']=='schema'
    assert result['overrides']==template['overrides']
    assert result['config']=={'custom':'keep','requester_catalog':{'visible':False}}
    assert template['config']=={'custom':'keep'}
    assert 'version' not in result and 'is_active' not in result
