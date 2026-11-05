"""Isolated PostgreSQL acceptance of pre-ticket files and ownership."""
from copy import deepcopy
import asyncio
from datetime import datetime, timedelta, timezone
import uuid
from unittest.mock import AsyncMock

from aiohttp import FormData
import pytest
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Artifact, Ticket, TicketEvent
from app.db.request_scenario_models import RequestStudioAsset, RequestStudioDraft, RequestStudioScenario, RequestStudioScenarioVersion, RequestStudioSession
from app.repos.request_scenario_repo import ScenarioAdminError
from tests.test_request_scenario_session_api import BASE, OWNER, OTHER, seed
from tickets.request_scenario_assets import validate_material_references

pytestmark = [pytest.mark.db_cleanup("full"), pytest.mark.light_app]
ADMIN = {"Authorization": "Bearer test-ui-admin-token"}


def upload_form(*, revision=1, field="summary", block="questions", answers=None, body=b"test file", name="report.txt"):
    import json
    form = FormData()
    form.add_field("file", body, filename=name, content_type="text/plain")
    form.add_field("field_key", field)
    form.add_field("expected_block_id", block)
    form.add_field("revision", str(revision))
    if answers is not None:
        form.add_field("answers", json.dumps(answers))
    return form


async def start(client, definition):
    response = await client.post(BASE, headers=OWNER, json={"offering_full_code": definition["offering_full_code"]})
    assert response.status == 200, await response.text()
    identifier = (await response.json())["data"]["id"]
    return identifier, BASE + "/" + identifier


@pytest.mark.asyncio
async def test_upload_owner_cas_reload_remove_and_no_placeholder_ticket(test_client_light, test_engine, tmp_path, monkeypatch):
    monkeypatch.setattr("web_api.request_scenario_asset_handlers.UPLOAD_DIR", tmp_path)
    definition, vid = await seed(test_engine, guided=True)
    identifier, url = await start(test_client_light, definition)
    async with async_sessionmaker(test_engine)() as session:
        before = await session.scalar(select(func.count()).select_from(Ticket))
    assert (await test_client_light.post(url + "/attachments", headers=OTHER, data=upload_form())).status == 404
    assert (await test_client_light.post(url + "/attachments", headers=OWNER, data=upload_form(revision=99))).status == 409
    assert (await test_client_light.post(url + "/attachments", headers=OWNER, data=upload_form(field="details"))).status == 400
    response = await test_client_light.post(url + "/attachments", headers=OWNER, data=upload_form())
    assert response.status == 200, await response.text()
    ref = (await response.json())["data"]
    assert ref["name"] == "report.txt" and ref["size_bytes"] == 9
    view = (await (await test_client_light.get(url, headers=OWNER)).json())["data"]
    assert view["revision"] == 1 and view["block"]["fields"][0]["answer_attachments"] == [ref]
    assert (await test_client_light.get(ref["url"], headers=OTHER)).status == 404
    download = await test_client_light.get(ref["url"], headers=OWNER)
    assert download.status == 200 and await download.read() == b"test file"
    assert download.headers["X-Content-Type-Options"] == "nosniff"
    assert download.headers["Content-Disposition"].startswith("attachment;")
    assert (await test_client_light.delete(url + "/attachments/" + ref["asset_id"], headers=OTHER,
        json={"expected_block_id": "questions", "revision": 1})).status == 404
    assert (await test_client_light.delete(url + "/attachments/" + ref["asset_id"], headers=OWNER,
        json={"expected_block_id": "questions", "revision": 1})).status == 200
    assert (await test_client_light.get(ref["url"], headers=OWNER)).status == 404
    async with async_sessionmaker(test_engine)() as session:
        assert await session.scalar(select(func.count()).select_from(Ticket)) == before
        assert await session.scalar(select(func.count()).select_from(Artifact)) == 0
    assert list(tmp_path.iterdir()), "Removal retains the blob for safe bounded cleanup"


@pytest.mark.asyncio
async def test_file_limit_oversize_failed_upload_cleanup_and_hidden_files_pruned(test_client_light, test_engine, tmp_path, monkeypatch):
    monkeypatch.setattr("web_api.request_scenario_asset_handlers.UPLOAD_DIR", tmp_path)
    definition, vid = await seed(test_engine, guided=True)
    identifier, url = await start(test_client_light, definition)
    monkeypatch.setattr("web_api.request_scenario_asset_handlers.ARTIFACT_MAX_BYTES", 2)
    response = await test_client_light.post(url + "/attachments", headers=OWNER, data=upload_form())
    assert response.status == 413 and (await response.json())["error_code"] == "FILE_TOO_LARGE"
    assert not list(tmp_path.iterdir())
    monkeypatch.setattr("web_api.request_scenario_asset_handlers.ARTIFACT_MAX_BYTES", 209715200)
    response = await test_client_light.post(url + "/attachments", headers=OWNER,
        data=upload_form(field="details", answers={"summary": "other"}))
    assert response.status == 200, await response.text()
    hidden_ref = (await response.json())["data"]
    assert (await test_client_light.post(url + "/answer", headers=OWNER,
        json={"expected_block_id": "questions", "revision": 1, "answers": {"summary": "not-other"}})).status == 200
    async with async_sessionmaker(test_engine)() as session:
        asset = await session.get(RequestStudioAsset, hidden_ref["asset_id"])
        assert asset.removed_at is not None
    assert (await test_client_light.get(hidden_ref["url"], headers=OWNER)).status == 404


@pytest.mark.asyncio
async def test_limits_expiry_revocation_and_failed_audit_preserve_ownership(test_client_light, test_engine, tmp_path, monkeypatch):
    monkeypatch.setattr("web_api.request_scenario_asset_handlers.UPLOAD_DIR", tmp_path)
    definition, vid = await seed(test_engine)
    identifier, url = await start(test_client_light, definition)
    with monkeypatch.context() as patch:
        patch.setattr("app.repos.request_scenario_session_repo.RequestScenarioSessionRepo._audit",
                      AsyncMock(side_effect=RuntimeError("audit unavailable")))
        response = await test_client_light.post(url + "/attachments", headers=OWNER, data=upload_form())
        assert response.status == 500
    assert not list(tmp_path.iterdir())
    refs = []
    for _ in range(10):
        response = await test_client_light.post(url + "/attachments", headers=OWNER, data=upload_form())
        assert response.status == 200, await response.text()
        refs.append((await response.json())["data"])
    response = await test_client_light.post(url + "/attachments", headers=OWNER, data=upload_form())
    assert response.status == 409 and (await response.json())["error_code"] == "ATTACHMENT_LIMIT"
    assert len(list(tmp_path.iterdir())) == 10
    async with async_sessionmaker(test_engine)() as session:
        row = await session.get(RequestStudioSession, identifier)
        row.created_at = datetime.now(timezone.utc) - timedelta(days=2)
        row.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        await session.commit()
    assert (await test_client_light.get(refs[0]["url"], headers=OWNER)).status == 410
    assert (await test_client_light.post(url + "/attachments", headers=OWNER, data=upload_form())).status == 410
    async with async_sessionmaker(test_engine)() as session:
        version = await session.get(RequestStudioScenarioVersion, vid)
        version.state = "revoked"
        await session.commit()
    response = await test_client_light.get(refs[0]["url"], headers=OWNER)
    assert response.status == 410 and (await response.json())["error_code"] == "SESSION_REVOKED"


@pytest.mark.asyncio
async def test_back_discards_later_page_files_and_keeps_target_page_files(test_client_light, test_engine, tmp_path, monkeypatch):
    monkeypatch.setattr("web_api.request_scenario_asset_handlers.UPLOAD_DIR", tmp_path)
    definition, vid = await seed(test_engine)
    definition["blocks"][0]["transitions"] = [{"to": "details_page"}]
    definition["blocks"].append({"id": "details_page", "kind": "form_page", "title": "Details", "fields": [
        {"key": "details", "type": "textarea", "label": "Details"}], "transitions": [{"to": "review"}]})
    async with async_sessionmaker(test_engine)() as session:
        old = await session.get(RequestStudioScenarioVersion, vid)
        old.state = "retired"
        await session.flush()
        version = RequestStudioScenarioVersion(scenario_id=old.scenario_id, offering_full_code=definition["offering_full_code"],
            version=2, schema_version=1, definition=definition, content_hash="c" * 64, source_snapshot={}, published_by="test")
        session.add(version)
        await session.flush()
        scenario = await session.get(RequestStudioScenario, old.scenario_id)
        scenario.published_version_id = version.id
        await session.commit()
    identifier, url = await start(test_client_light, definition)
    first = await test_client_light.post(url + "/attachments", headers=OWNER, data=upload_form())
    assert first.status == 200, await first.text()
    first_ref = (await first.json())["data"]
    assert (await test_client_light.post(url + "/answer", headers=OWNER,
        json={"expected_block_id": "questions", "revision": 1, "answers": {"summary": "No print"}})).status == 200
    second = await test_client_light.post(url + "/attachments", headers=OWNER,
        data=upload_form(block="details_page", field="details", revision=2))
    assert second.status == 200, await second.text()
    second_ref = (await second.json())["data"]
    assert (await test_client_light.post(url + "/answer", headers=OWNER,
        json={"expected_block_id": "details_page", "revision": 2, "answers": {"details": "More"}})).status == 200
    response = await test_client_light.post(url + "/back", headers=OWNER, json={"target_block_id": "questions", "revision": 3})
    assert response.status == 200, await response.text()
    assert (await response.json())["data"]["block"]["fields"][0]["answer_attachments"] == [first_ref]
    assert (await test_client_light.get(first_ref["url"], headers=OWNER)).status == 200
    assert (await test_client_light.get(second_ref["url"], headers=OWNER)).status == 404


@pytest.mark.asyncio
async def test_author_material_requires_admin_and_rejects_cross_scenario_or_forged_refs(test_client_light, test_engine, tmp_path, monkeypatch):
    monkeypatch.setattr("web_api.request_scenario_asset_handlers.UPLOAD_DIR", tmp_path)
    definition, vid = await seed(test_engine)
    async with async_sessionmaker(test_engine, expire_on_commit=False)() as session:
        version = await session.get(RequestStudioScenarioVersion, vid)
        sid = version.scenario_id
        session.add(RequestStudioDraft(scenario_id=sid, definition=definition, updated_by="test"))
        await session.commit()
    url = f"/api/web/admin/request-studio/scenarios/{sid}/attachments"
    assert (await test_client_light.post(url, headers=OWNER, data=upload_form())).status == 403
    response = await test_client_light.post(url, headers=ADMIN, data=upload_form())
    assert response.status == 200, await response.text()
    ref = (await response.json())["data"]
    assert (await test_client_light.get(ref["url"], headers=OWNER)).status == 404
    raw = deepcopy(definition)
    raw["blocks"][0]["fields"][0]["help_attachments"] = [ref]
    async with async_sessionmaker(test_engine)() as session:
        await validate_material_references(session, sid, raw)
        with pytest.raises(ScenarioAdminError):
            await validate_material_references(session, str(uuid.uuid4()), raw)
        forged = deepcopy(raw)
        forged["blocks"][0]["fields"][0]["help_attachments"][0]["name"] = "forged"
        with pytest.raises(ScenarioAdminError):
            await validate_material_references(session, sid, forged)
        version = await session.get(RequestStudioScenarioVersion, vid)
        version.state = "retired"
        await session.flush()
        replacement = RequestStudioScenarioVersion(scenario_id=sid, offering_full_code=definition["offering_full_code"],
            version=2, schema_version=1, definition=raw, content_hash="b" * 64, source_snapshot={}, published_by="test")
        session.add(replacement)
        await session.flush()
        scenario = await session.get(RequestStudioScenario, sid)
        scenario.published_version_id = replacement.id
        await session.commit()
    assert (await test_client_light.get(ref["url"], headers=OWNER)).status == 200


@pytest.mark.asyncio
async def test_submission_claims_once_in_initial_message_and_context(test_client_light, test_engine, tmp_path, monkeypatch):
    from tests.test_request_scenario_submit_api import setup
    monkeypatch.setattr("web_api.request_scenario_asset_handlers.UPLOAD_DIR", tmp_path)
    definition = await setup(test_engine)
    identifier, url = await start(test_client_light, definition)
    response = await test_client_light.post(url + "/attachments", headers=OWNER, data=upload_form())
    assert response.status == 200, await response.text()
    ref = (await response.json())["data"]
    assert (await test_client_light.post(url + "/answer", headers=OWNER,
        json={"expected_block_id": "questions", "revision": 1, "answers": {"summary": "No print"}})).status == 200
    review = (await (await test_client_light.get(url, headers=OWNER)).json())["data"]
    assert review["block"]["answers"][0]["answer_attachments"] == [ref]
    assert (await test_client_light.post(url + "/advance", headers=OWNER,
        json={"expected_block_id": "review", "revision": 2})).status == 200
    responses = await asyncio.gather(*[test_client_light.post(url + "/submit", headers=OWNER,
        json={"revision": 3, "confirm": True}) for _ in range(2)])
    for response in responses:
        assert response.status == 200, await response.text()
    ticket_id = (await response.json())["data"]["linked_ticket_id"]
    async with async_sessionmaker(test_engine)() as session:
        files = (await session.scalars(select(Artifact).where(Artifact.ticket_id == ticket_id))).all()
        assert len(files) == 1 and files[0].device_id is None
        ticket = await session.get(Ticket, ticket_id)
        refs = ticket.custom_fields["request_scenario"]["answer_attachments"]
        assert refs[0]["field_key"] == "summary" and refs[0]["artifact_id"] == files[0].artifact_id
        event = await session.scalar(select(TicketEvent).where(TicketEvent.ticket_id == ticket_id,
            TicketEvent.event_type == "chat_message", TicketEvent.payload["is_initial"].as_boolean().is_(True)))
        assert event.payload["attachments"][0]["artifact_id"] == files[0].artifact_id
        assert event.payload["attachment_refs"] == [files[0].artifact_id]
