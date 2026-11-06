"""Plan/apply the verified test-template discovery change on staging only.

Caller owns exact release/backup guards. Templates, fields, routing, published
versions and existing tickets remain available; a new audited version only opts
the verified test template out of automatic public form discovery.
"""
from copy import deepcopy

TARGET_CODE = "template_1792b61daf914ce5afcd6dd83be9c46f"
TARGET_TITLE = "Тест шаблона почты 20261012143808 — форма"
FIELDS = ("template_code", "public_title", "ticket_type", "internal_name", "description",
          "category_id", "service_id", "subcategory_id", "form_schema_id", "workflow_profile_id",
          "priority_policy_code", "routing_policy_code", "sla_policy_id", "sla_policy_code", "ola_policy_code",
          "approval_policy_code", "diagnostic_policy_code", "closure_policy_code", "visibility_policy_code",
          "notification_policy_code", "reporting_policy_code", "config", "overrides")

def publication_payload(template):
    payload = {key: deepcopy(template[key]) for key in FIELDS if key in template}
    config = payload.setdefault("config", {})
    config["requester_catalog"] = {**config.get("requester_catalog", {}), "visible": False}
    return payload

async def cleanup_test_template(factory, auth, *, apply=False, expected_fingerprint=None):
    from sqlalchemy import select, text
    from app.db.models import RequestTemplate
    from app.repos.helpdesk_policy_repo import HelpdeskPolicyRepo
    from app.repos.service_catalog_repo import ServiceCatalogRepo
    from scripts.helpdesk_phase1_catalog import require_target, fingerprint

    if not auth.is_admin() or not auth.actor_id:
        raise ValueError("A trusted admin context is required")
    async with factory() as session:
        async with session.begin():
            require_target(await session.scalar(text("SELECT current_database()")))
            if apply:
                await session.execute(select(RequestTemplate).where(RequestTemplate.template_code == TARGET_CODE).order_by(RequestTemplate.version).with_for_update())
            repo = HelpdeskPolicyRepo(session)
            targets = [row for row in await repo.list_request_templates(include_inactive=False) if row['template_code'] == TARGET_CODE]
            if len(targets) != 1 or targets[0]['public_title'] != TARGET_TITLE:
                raise ValueError("Verified test template changed; obtain a fresh review")
            template = targets[0]
            if any(row.get('request_template_key') == TARGET_CODE and row.get('lifecycle_status') != 'retired'
                   for row in await ServiceCatalogRepo(session).list_offerings()):
                raise ValueError("Template has catalog consumers; do not unlist automatically")
            digest = fingerprint(template)
            changed = (template.get('config') or {}).get('requester_catalog', {}).get('visible') is not False
            result = {'template_code': TARGET_CODE, 'version': template['version'], 'fingerprint': digest, 'changed': changed, 'applied': False}
            if apply:
                if digest != expected_fingerprint:
                    raise ValueError("Publication inputs changed; obtain a fresh plan")
                if changed:
                    payload = publication_payload(template)
                    published = await repo.publish_request_template(**payload, actor_id=auth.actor_id, actor_role=auth.actor_role)
                    if any(published.get(key) != template.get(key) for key in FIELDS if key != 'config') or published.get('config') != payload['config']:
                        raise ValueError("Publication changed template processing; transaction rolled back")
                    result['new_version'] = published['version']
                result['applied'] = True
            return result
