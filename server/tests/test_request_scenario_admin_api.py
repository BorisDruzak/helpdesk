"""P3 isolated PostgreSQL HTTP/RBAC/CAS/catalog acceptance."""
import asyncio
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import HelpdeskService, HelpdeskServiceOffering, HelpdeskServiceCatalogAudit, RequestTemplate
from app.db.request_scenario_models import RequestStudioCategory, RequestStudioDraft, RequestStudioScenario

pytestmark = [pytest.mark.db_cleanup("full"), pytest.mark.light_app]
BASE = "/api/web/admin/request-studio"
ADMIN = {"Authorization": "Bearer test-ui-admin-token"}
AUDITOR = {"Authorization": "Bearer test-ui-auditor-token"}


async def seed(engine, visibility="public"):
    code = "scenario_api_" + uuid.uuid4().hex[:8]
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        service = HelpdeskService(service_id=str(uuid.uuid4()), code=code, name="Studio test", public_title="Studio test", visibility=visibility, lifecycle_status="published")
        session.add(service)
        await session.flush()
        session.add(HelpdeskServiceOffering(offering_id=str(uuid.uuid4()), service_id=service.service_id, code="printer", full_code=code + ".printer", name="Printer", public_title="Не печатает", request_template_key=code, visibility="public", lifecycle_status="published"))
        session.add(RequestTemplate(template_code=code, version="1", public_title="Printer", ticket_type="incident"))
        await session.commit()
    return {"scenario_key": code, "service_code": code, "offering_full_code": code + ".printer", "title": "Не печатает", "process_binding": {"request_template_key": code}, "entry_block_id": "questions", "blocks": [
        {"id": "questions", "kind": "form_page", "title": "Вопрос", "fields": [{"key": "summary", "type": "text", "label": "Описание", "required": True}], "transitions": [{"to": "review"}]},
        {"id": "review", "kind": "review", "title": "Проверьте", "transitions": [{"to": "submit"}]},
        {"id": "submit", "kind": "submit_ticket", "title": "Отправить"},
    ]}


async def create(client, definition):
    response = await client.post(BASE + "/scenarios", headers=ADMIN, json={"definition": definition})
    assert response.status == 200, await response.text()
    return (await response.json())["data"]


@pytest.mark.asyncio
async def test_catalog_searches_offering_type_and_profile_for_scenario_and_legacy(test_client_light, test_engine):
    definition = await seed(test_engine)
    async with async_sessionmaker(test_engine)() as session:
        offering = await session.scalar(select(HelpdeskServiceOffering).where(HelpdeskServiceOffering.full_code == definition["offering_full_code"]))
        offering.request_type = "service_request"
        offering.metadata_json = {"studio_profile": "software_install"}
        session.add(HelpdeskServiceOffering(offering_id=str(uuid.uuid4()), service_id=offering.service_id,
            code="other", full_code=definition["service_code"] + ".other", name="Other", public_title="Другая форма",
            request_type="service_request", metadata_json={"studio_profile": "software_install"}, visibility="public"))
        await session.commit()
    created = await create(test_client_light, definition)
    for query in ("service_request", "Запрос услуги", "software_install", "Установка ПО"):
        response = await test_client_light.get(BASE + "/catalog", headers=AUDITOR, params={"q": query})
        assert response.status == 200, await response.text()
        data = (await response.json())["data"]
        assert created["scenario"]["id"] in {item["id"] for item in data["scenarios"]}
        assert definition["service_code"] + ".other" in {item["full_code"] for item in data["legacy_offerings"]}
        assert definition["offering_full_code"] not in {item["full_code"] for item in data["legacy_offerings"]}


@pytest.mark.asyncio
async def test_catalog_timestamp_tracks_block_only_edit_by_same_actor(test_client_light, test_engine):
    definition = await seed(test_engine)
    created = await create(test_client_light, definition)
    identifier = created["scenario"]["id"]
    old = datetime(2020, 1, 1, tzinfo=timezone.utc)
    async with async_sessionmaker(test_engine)() as session:
        (await session.get(RequestStudioScenario, identifier)).updated_at = old
        (await session.get(RequestStudioDraft, identifier)).updated_at = old
        await session.commit()
    definition["blocks"][0]["fields"][0]["label"] = "Подробное описание"
    response = await test_client_light.put(BASE + "/scenarios/" + identifier + "/draft", headers=ADMIN, json={"definition": definition, "revision": 1})
    assert response.status == 200, await response.text()
    saved = (await response.json())["data"]
    assert datetime.fromisoformat(saved["scenario"]["updated_at"]) == old
    response = await test_client_light.get(BASE + "/catalog", headers=ADMIN)
    assert response.status == 200, await response.text()
    item = next(item for item in (await response.json())["data"]["scenarios"] if item["id"] == identifier)
    assert item["updated_at"] == saved["draft"]["updated_at"]
    assert item["published_version"] is None


@pytest.mark.asyncio
async def test_category_crud_revision_tree_and_audit(test_client_light, test_engine):
    definition = await seed(test_engine)
    payload = {"service_code": definition["service_code"], "slug": "printers", "title": "Принтеры", "visibility": "public"}
    response = await test_client_light.post(BASE + "/categories", headers=ADMIN, json=payload)
    assert response.status == 200, await response.text()
    category = (await response.json())["data"]
    assert category["revision"] == 1 and category["id"]
    child = dict(payload, slug="office", parent_id=category["id"])
    response = await test_client_light.post(BASE + "/categories", headers=ADMIN, json=child)
    assert response.status == 200
    child_id = (await response.json())["data"]["id"]
    edited = dict(payload, title="Новая категория", revision=1)
    response = await test_client_light.put(BASE + "/categories/" + category["id"], headers=ADMIN, json=edited)
    assert response.status == 200 and (await response.json())["data"]["revision"] == 2
    assert (await test_client_light.put(BASE + "/categories/" + category["id"], headers=ADMIN, json=edited)).status == 409
    assert (await test_client_light.put(BASE + "/categories/" + category["id"], headers=ADMIN, json=dict(edited, revision=2, parent_id=child_id))).status == 400
    assert (await test_client_light.delete(BASE + "/categories/" + category["id"] + "?revision=2", headers=ADMIN)).status == 409
    assert (await test_client_light.delete(BASE + "/categories/" + child_id + "?revision=1", headers=ADMIN)).status == 200
    async with async_sessionmaker(test_engine)() as session:
        audits = (await session.scalars(select(HelpdeskServiceCatalogAudit).where(HelpdeskServiceCatalogAudit.object_code == category["id"]).order_by(HelpdeskServiceCatalogAudit.id))).all()
        assert [a.action for a in audits] == ["create", "update"]
        assert all(a.actor_role == "admin" and a.actor_id == "admin-test" for a in audits)


@pytest.mark.asyncio
async def test_auditor_cannot_mutate(test_client_light):
    # One app/cleanup for the same role boundary, preserving all six HTTP probes.
    identifier = str(uuid.UUID(int=1))
    for method, path, body in [
        ("post", "/categories", {}), ("put", "/categories/" + identifier, {}),
        ("delete", "/categories/" + identifier + "?revision=1", None),
        ("post", "/scenarios", {}), ("put", "/scenarios/" + identifier + "/draft", {}),
        ("post", "/scenarios/" + identifier + "/archive", {}),
    ]:
        response = await getattr(test_client_light, method)(BASE + path, headers=AUDITOR, json=body)
        assert response.status == 403, (method, path)


@pytest.mark.asyncio
async def test_catalog_read_auth_and_not_found(test_client_light, monkeypatch):
    # The generic fixture defaults missing credentials to support; retain the
    # real middleware/decorator while removing that compatibility fallback here.
    from auth import middleware
    original = middleware.extract_auth_context
    async def explicit_auth(request):
        return await original(request) if request.headers.get("Authorization") else None
    monkeypatch.setattr(middleware, "extract_auth_context", explicit_auth)
    assert (await test_client_light.get(BASE + "/catalog", headers=AUDITOR)).status == 200
    assert (await test_client_light.get(BASE + "/catalog", headers={"Authorization": "Bearer test-ui-support-token"})).status == 403
    assert (await test_client_light.get(BASE + "/catalog")).status == 401
    assert (await test_client_light.get(BASE + "/scenarios/" + str(uuid.UUID(int=1)), headers=ADMIN)).status == 404
    assert (await test_client_light.get(BASE + "/catalog?status=invalid", headers=ADMIN)).status == 400
    response = await test_client_light.get(BASE + "/catalog?offset=0&limit=25", headers=AUDITOR)
    assert response.status == 200
    assert (await response.json())["data"]["limit"] == 25
    for query in ("offset=-1", "limit=501", "limit=bad"):
        assert (await test_client_light.get(BASE + "/catalog?" + query, headers=AUDITOR)).status == 400


@pytest.mark.asyncio
async def test_scenario_draft_cas_simulation_archive_and_version_reads(test_client_light, test_engine):
    definition = await seed(test_engine)
    legacy_response = await test_client_light.get(BASE + "/catalog", headers=AUDITOR, params={"q": definition["offering_full_code"], "status": "form_only"})
    assert legacy_response.status == 200
    legacy_data = (await legacy_response.json())["data"]
    assert legacy_data["total"] == 1 and legacy_data["legacy_offerings"][0]["full_code"] == definition["offering_full_code"]
    category_response = await test_client_light.post(BASE + "/categories", headers=ADMIN, json={"service_code": definition["service_code"], "slug": "equipment", "title": "Equipment"})
    category_id = (await category_response.json())["data"]["id"]
    definition["category_id"] = category_id
    data = await create(test_client_light, definition)
    sid = data["scenario"]["id"]
    assert data["draft"]["revision"] == 1 and data["scenario"]["enabled"] is False
    category_catalog = await test_client_light.get(BASE + "/catalog", headers=AUDITOR, params={"category_id": category_id, "limit": "1"})
    assert category_catalog.status == 200
    category_data = (await category_catalog.json())["data"]
    assert category_data["total"] == 1 and category_data["scenarios"][0]["id"] == sid
    assert category_data["legacy_offerings"] == []
    bound_legacy = await test_client_light.get(BASE + "/catalog", headers=AUDITOR, params={"q": definition["offering_full_code"], "status": "form_only"})
    bound_data = (await bound_legacy.json())["data"]
    assert bound_data["total"] == 1
    assert bound_data["entries"][0]["active_mode"] == "form"
    url = BASE + "/scenarios/" + sid
    edit = dict(definition, title="Исправлено")
    response = await test_client_light.put(url + "/draft", headers=ADMIN, json={"definition": edit, "revision": 1})
    assert response.status == 200
    assert (await response.json())["data"]["draft"]["revision"] == 2
    assert (await test_client_light.put(url + "/draft", headers=ADMIN, json={"definition": definition, "revision": 1})).status == 409
    assert (await test_client_light.get(url + "/versions", headers=AUDITOR)).status == 200
    response = await test_client_light.post(url + "/simulate", headers=AUDITOR, json={"revision": 2, "steps": [{"expected_block_id": "questions", "revision": 1, "answers": {"summary": "x"}}]})
    assert response.status == 200 and (await response.json())["data"]["state"]["current_block_id"] == "review"
    async with async_sessionmaker(test_engine)() as session:
        assert (await session.get(RequestStudioDraft, sid)).revision == 2
    response = await test_client_light.get(BASE + "/catalog?q=Исправлено&status=draft", headers=AUDITOR)
    assert response.status == 200 and any(s["id"] == sid for s in (await response.json())["data"]["scenarios"])
    assert (await test_client_light.post(url + "/archive", headers=ADMIN, json={"revision": 2})).status == 200
    assert (await test_client_light.put(url + "/draft", headers=ADMIN, json={"definition": edit, "revision": 3})).status == 409


@pytest.mark.asyncio
async def test_binding_cannot_be_replaced_or_create_authority(test_client_light, test_engine):
    definition = await seed(test_engine)
    data = await create(test_client_light, definition)
    url = BASE + "/scenarios/" + data["scenario"]["id"] + "/draft"
    other = await seed(test_engine)
    assert (await test_client_light.put(url, headers=ADMIN, json={"definition": other, "revision": 1})).status == 400
    for key, value in (("enabled", True), ("actor_role", "admin"), ("queue_id", 999)):
        assert (await test_client_light.post(BASE + "/scenarios", headers=ADMIN, json={"definition": definition, key: value})).status == 400
    assert (await test_client_light.post(BASE + "/scenarios", headers=ADMIN, json={"definition": definition})).status == 409
    copied = dict(definition, scenario_key=definition["scenario_key"] + "_copy", title="Копия")
    copy_data = await create(test_client_light, copied)
    assert copy_data["scenario"]["id"] != data["scenario"]["id"]
    assert copy_data["draft"]["revision"] == 1 and copy_data["scenario"]["enabled"] is False


@pytest.mark.asyncio
async def test_category_cannot_cross_service_or_widen_effective_visibility(test_client_light, test_engine):
    first = await seed(test_engine, visibility="restricted")
    other = await seed(test_engine)
    category_resp = await test_client_light.post(BASE + "/categories", headers=ADMIN, json={"service_code": first["service_code"], "slug": "public", "title": "Открытая", "visibility": "public"})
    assert category_resp.status == 200
    category = (await category_resp.json())["data"]
    assert category["effective_visibility"] == "restricted"
    assert (await test_client_light.post(BASE + "/categories", headers=ADMIN, json={"service_code": other["service_code"], "parent_id": category["id"], "slug": "child", "title": "Child"})).status == 400
    other["category_id"] = category["id"]
    assert (await test_client_light.post(BASE + "/scenarios", headers=ADMIN, json={"definition": other})).status == 400


@pytest.mark.asyncio
async def test_category_delete_cannot_orphan_scenario(test_client_light, test_engine):
    definition = await seed(test_engine)
    response = await test_client_light.post(BASE + "/categories", headers=ADMIN, json={"service_code": definition["service_code"], "slug": "printer", "title": "Printer"})
    assert response.status == 200
    cid = (await response.json())["data"]["id"]
    definition["category_id"] = cid
    data = await create(test_client_light, definition)
    assert (await test_client_light.delete(BASE + "/categories/" + cid + "?revision=1", headers=ADMIN)).status == 409
    definition["category_id"] = None
    url = BASE + "/scenarios/" + data["scenario"]["id"]
    assert (await test_client_light.put(url + "/draft", headers=ADMIN, json={"definition": definition, "revision": 1})).status == 200
    response = await test_client_light.get(url, headers=AUDITOR)
    assert (await response.json())["data"]["scenario"]["category_id"] is None
    assert (await test_client_light.delete(BASE + "/categories/" + cid + "?revision=1", headers=ADMIN)).status == 200


@pytest.mark.asyncio
async def test_concurrent_draft_saves_have_exactly_one_winner(test_client_light, test_engine):
    definition = await seed(test_engine)
    data = await create(test_client_light, definition)
    sid = data["scenario"]["id"]
    url = BASE + "/scenarios/" + sid + "/draft"
    responses = await asyncio.gather(*[
        test_client_light.put(url, headers=ADMIN, json={"revision": 1, "definition": dict(definition, title=title)})
        for title in ("Первое изменение", "Второе изменение")
    ])
    assert sorted(response.status for response in responses) == [200, 409]
    async with async_sessionmaker(test_engine)() as session:
        draft = await session.get(RequestStudioDraft, sid)
        assert draft.revision == 2
        audits = (await session.scalars(select(HelpdeskServiceCatalogAudit).where(HelpdeskServiceCatalogAudit.object_code == sid, HelpdeskServiceCatalogAudit.action == "save_draft"))).all()
        assert len(audits) == 1


@pytest.mark.asyncio
async def test_failed_audit_rolls_back_draft_write(test_client_light, test_engine, monkeypatch):
    from app.repos.service_catalog_repo import ServiceCatalogRepo
    definition = await seed(test_engine)
    data = await create(test_client_light, definition)
    sid = data["scenario"]["id"]
    async def fail_audit(*args, **kwargs):
        raise RuntimeError("Synthetic audit failure")
    monkeypatch.setattr(ServiceCatalogRepo, "append_audit", fail_audit)
    response = await test_client_light.put(BASE + "/scenarios/" + sid + "/draft", headers=ADMIN, json={"revision": 1, "definition": dict(definition, title="Не сохранять")})
    assert response.status == 500
    async with async_sessionmaker(test_engine)() as session:
        draft = await session.get(RequestStudioDraft, sid)
        assert draft.revision == 1 and draft.definition["title"] == definition["title"]


@pytest.mark.asyncio
async def test_unified_catalog_counts_offering_once_and_keeps_archived_copies_in_detail(test_client_light, test_engine):
    definition = await seed(test_engine)
    primary = await create(test_client_light, definition)
    copy = await create(test_client_light, dict(definition, scenario_key=definition["scenario_key"] + "_copy"))
    response = await test_client_light.post(BASE + "/scenarios/" + copy["scenario"]["id"] + "/archive",
        headers=ADMIN, json={"revision": 1})
    assert response.status == 200
    response = await test_client_light.get(BASE + "/catalog", headers=AUDITOR,
        params={"offering_code": definition["offering_full_code"]})
    data = (await response.json())["data"]
    assert data["total"] == 1 and len(data["entries"]) == 1
    card = data["entries"][0]
    assert card["requester_available"] is True and card["active_mode"] == "form"
    assert {item["id"] for item in card["scenarios"]} == {primary["scenario"]["id"], copy["scenario"]["id"]}
    root = await test_client_light.get(BASE + "/catalog", headers=AUDITOR, params={"service_code": definition["service_code"]})
    assert (await root.json())["data"]["total"] == 1
    async with async_sessionmaker(test_engine)() as session:
        offering = await session.scalar(select(HelpdeskServiceOffering).where(HelpdeskServiceOffering.full_code == definition["offering_full_code"]))
        offering.lifecycle_status = "retired"
        await session.commit()
    response = await test_client_light.get(BASE + "/catalog", headers=AUDITOR, params={"offering_code": definition["offering_full_code"]})
    assert (await response.json())["data"]["entries"][0]["requester_available"] is False
