"""Canonical purge owns Studio claims while preserving other blob owners."""
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Artifact, Ticket
from app.db.request_scenario_models import RequestStudioAsset, RequestStudioScenarioVersion, RequestStudioSession
from tests.test_request_scenario_assets_api import start, upload_form
from tests.test_request_scenario_session_api import OWNER
from tests.test_request_scenario_submit_api import setup
from tickets.purge_service import TicketPurgeService

pytestmark = [pytest.mark.db_cleanup("full"), pytest.mark.light_app]


@pytest.mark.asyncio
@pytest.mark.parametrize("shared", [False, True])
async def test_purge_claimed_studio_file_cancels_session_and_preserves_author_material(test_client_light, test_engine, tmp_path, monkeypatch, shared):
    monkeypatch.setattr("web_api.request_scenario_asset_handlers.UPLOAD_DIR", tmp_path)
    monkeypatch.setattr("tickets.purge_service.UPLOAD_DIR", tmp_path)
    definition = await setup(test_engine)
    identifier, url = await start(test_client_light, definition)
    response = await test_client_light.post(url + "/attachments", headers=OWNER, data=upload_form())
    assert response.status == 200, await response.text()
    asset_id = (await response.json())["data"]["asset_id"]
    assert (await test_client_light.post(url + "/answer", headers=OWNER,
        json={"expected_block_id": "questions", "revision": 1, "answers": {"summary": "No print"}})).status == 200
    assert (await test_client_light.post(url + "/advance", headers=OWNER,
        json={"expected_block_id": "review", "revision": 2})).status == 200
    response = await test_client_light.post(url + "/submit", headers=OWNER, json={"revision": 3, "confirm": True})
    assert response.status == 200, await response.text()
    ticket_id = (await response.json())["data"]["linked_ticket_id"]
    material_id, shared_id = str(uuid.uuid4()), str(uuid.uuid4())
    material_path = tmp_path / f"studio_{material_id}.bin"
    material_path.write_bytes(b"keep author material")
    async with async_sessionmaker(test_engine, expire_on_commit=False)() as session:
        asset = await session.get(RequestStudioAsset, asset_id)
        blob = tmp_path / asset.storage_path
        row = await session.get(RequestStudioSession, identifier)
        version = await session.get(RequestStudioScenarioVersion, row.version_id)
        session.add(RequestStudioAsset(id=material_id, scenario_id=version.scenario_id, owner_actor_id="admin",
            storage_path=material_path.name, name="guide.txt", mime_type="text/plain", size_bytes=20, sha256="a" * 64))
        if shared:
            session.add(Artifact(artifact_id=shared_id, storage_path=asset.storage_path, original_name="shared.txt",
                mime_type="text/plain", size_bytes=asset.size_bytes, sha256=asset.sha256, device_id="other-device"))
        await session.commit()
        preview = await TicketPurgeService(session).preview([ticket_id])
        assert preview["can_purge"] and preview["affected_counts"]["request_studio_assets"] == 1
        failed = TicketPurgeService(session)
        failed_result = await failed.purge([ticket_id], actor_id="test", reason="commit failure regression")
        with pytest.raises(RuntimeError, match="commit"):
            await failed.finalize_committed_purge(failed_result)
        with patch.object(session, "commit", AsyncMock(side_effect=RuntimeError("commit outcome unknown"))):
            with pytest.raises(RuntimeError, match="unknown"):
                await session.commit()
        await session.rollback()
        assert blob.exists()
        # A mistaken finalizer call after rollback also rechecks restored owners.
        await failed.finalize_committed_purge(failed_result)
        assert blob.exists() and await session.get(RequestStudioAsset, asset_id) is not None
        service = TicketPurgeService(session)
        result = await service.purge([ticket_id], actor_id="test", reason="isolated regression")
        assert result["purged_ticket_ids"] == [ticket_id]
        assert blob.exists(), "Uncommitted purge must preserve blobs"
        await session.commit()
        await service.finalize_committed_purge(result)
    async with async_sessionmaker(test_engine)() as session:
        assert await session.get(Ticket, ticket_id) is None
        assert await session.get(RequestStudioAsset, asset_id) is None
        assert await session.get(RequestStudioAsset, material_id) is not None
        row = await session.get(RequestStudioSession, identifier)
        assert row.state == "canceled" and row.linked_ticket_id is None
        assert blob.exists() is shared
        assert material_path.read_bytes() == b"keep author material"
