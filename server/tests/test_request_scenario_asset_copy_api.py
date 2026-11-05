"""Copy author files explicitly; generic cross-scenario references stay forbidden."""
from copy import deepcopy
import uuid

from aiohttp import FormData
import pytest
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import HelpdeskService
from app.db.request_scenario_models import RequestStudioAsset, RequestStudioDraft, RequestStudioScenarioVersion
from tests.test_request_scenario_assets_api import ADMIN
from tests.test_request_scenario_submit_api import setup

pytestmark = [pytest.mark.db_cleanup("full"), pytest.mark.light_app]
BASE = "/api/web/admin/request-studio"


@pytest.mark.asyncio
async def test_copy_material_rebinds_once_roundtrips_and_retries_without_duplicate_assets(test_client_light, test_engine, tmp_path, monkeypatch):
    monkeypatch.setattr("web_api.request_scenario_asset_handlers.UPLOAD_DIR", tmp_path)
    definition = await setup(test_engine)
    async with async_sessionmaker(test_engine)() as session:
        version = await session.scalar(select(RequestStudioScenarioVersion).where(
            RequestStudioScenarioVersion.offering_full_code == definition["offering_full_code"]))
        source_id = version.scenario_id
        session.add(RequestStudioDraft(scenario_id=source_id, definition=definition, updated_by="test"))
        await session.commit()
    form = FormData()
    form.add_field("file", b"copy material", filename="guide.txt", content_type="text/plain")
    response = await test_client_light.post(f"{BASE}/scenarios/{source_id}/attachments", headers=ADMIN, data=form)
    assert response.status == 200, await response.text()
    source_ref = (await response.json())["data"]
    definition["blocks"][0]["fields"][0]["help_attachments"] = [source_ref]
    definition["blocks"].append({"id": "manual", "kind": "instruction", "title": "Manual",
        "content": {"body": "Read", "attachments": [source_ref]}})
    # Persist the source definition through the same normal draft save as UI.
    response = await test_client_light.put(f"{BASE}/scenarios/{source_id}/draft", headers=ADMIN,
        json={"definition": definition, "revision": 1})
    assert response.status == 200, await response.text()
    copied = deepcopy(definition)
    copied.update(scenario_key="copy_" + uuid.uuid4().hex, title="Copied with files", schema_version=2,
        offering_full_code="", publish_offering=False)
    copied["process_binding"]["request_template_key"] = ""
    # RED: the existing copy path clones these refs; initial server implementation
    # rejects every cross-scenario ref because the new scenario has no id yet.
    response = await test_client_light.post(BASE + "/services", headers=ADMIN,
        json={"definition": copied, "copy_source_id": source_id})
    assert response.status == 200, await response.text()
    created = (await response.json())["data"]
    target_id = created["scenario"]["id"]
    new_ref = created["draft"]["definition"]["blocks"][0]["fields"][0]["help_attachments"][0]
    assert target_id != source_id and new_ref["asset_id"] != source_ref["asset_id"]
    assert created["asset_rebindings"] == {source_ref["asset_id"]: new_ref}
    assert created["draft"]["definition"]["blocks"][-1]["content"]["attachments"] == [new_ref]
    assert (await test_client_light.get(new_ref["url"], headers=ADMIN)).status == 200
    async with async_sessionmaker(test_engine)() as session:
        source_asset = await session.get(RequestStudioAsset, source_ref["asset_id"])
        copied_asset = await session.get(RequestStudioAsset, new_ref["asset_id"])
        assert copied_asset.scenario_id == target_id and copied_asset.storage_path == source_asset.storage_path
        assert copied_asset.sha256 == source_asset.sha256
        count = await session.scalar(select(func.count()).select_from(RequestStudioAsset))
    response = await test_client_light.post(BASE + "/services", headers=ADMIN,
        json={"definition": copied, "copy_source_id": source_id})
    assert response.status == 200, await response.text()
    retried = (await response.json())["data"]
    assert retried["scenario"]["id"] == target_id and retried["asset_rebindings"] == created["asset_rebindings"]
    async with async_sessionmaker(test_engine)() as session:
        assert await session.scalar(select(func.count()).select_from(RequestStudioAsset)) == count
    generic = deepcopy(copied)
    generic["scenario_key"] = "generic_" + uuid.uuid4().hex
    rejected = await test_client_light.post(BASE + "/services", headers=ADMIN, json={"definition": generic})
    assert rejected.status == 400 and (await rejected.json())["error_code"] == "ATTACHMENT_REFERENCE_INVALID"
    # Even with explicit copy provenance, metadata and the claimed source must match.
    forged = deepcopy(copied)
    forged["scenario_key"] = "forged_" + uuid.uuid4().hex
    forged["blocks"][0]["fields"][0]["help_attachments"][0]["name"] = "forged"
    rejected = await test_client_light.post(BASE + "/services", headers=ADMIN,
        json={"definition": forged, "copy_source_id": source_id})
    assert rejected.status == 400
    rejected = await test_client_light.post(BASE + "/services", headers=ADMIN,
        json={"definition": generic, "copy_source_id": target_id})
    assert rejected.status == 400
