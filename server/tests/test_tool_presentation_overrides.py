from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import DiagnosticCapability, DiagnosticProvider, Ticket, TicketEvent
from diagnostics.capability_models import CapabilityDescriptor
from diagnostics.presentation_overrides import (
    PresentationSchemaValidationError,
    ToolPresentationOverrideService,
)


DEFAULT_SCHEMA = {
    "version": "1.0",
    "kind": "tool_result",
    "title": "Module default",
    "blocks": [{"type": "field_grid", "fields": [{"path": "status", "label": "Status"}]}],
}

OVERRIDE_SCHEMA = {
    "version": "1.0",
    "kind": "tool_result",
    "title": "Server override",
    "blocks": [{"type": "raw_json", "collapsed": True}],
    "fallback": {"show_raw_json": True},
}


def _admin_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-ui-admin-token"}


def _support_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-ui-support-token"}


async def _seed_persisted_capability(test_engine, *, capability_id: str = "sample.collect") -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(
            DiagnosticProvider(
                provider_id="sample_provider",
                provider_type="managed_module",
                title="Sample Provider",
                status="available",
            )
        )
        await session.flush()
        session.add(
            DiagnosticCapability(
                capability_id=capability_id,
                provider_id="sample_provider",
                execution_target="agent_builtin",
                title="Sample Collect",
                status="active",
                latest_version="1.0.0",
                descriptor_json={
                    "id": capability_id,
                    "title": "Sample Collect",
                    "provider_id": "sample_provider",
                    "provider_type": "managed_module",
                    "execution_target": "agent_builtin",
                    "presentation_schema": DEFAULT_SCHEMA,
                    "output_schema": {"type": "object", "properties": {"status": {"type": "string"}}},
                },
            )
        )
        await session.commit()


@pytest.mark.asyncio
async def test_service_resolves_module_default_override_and_reset(test_engine) -> None:
    descriptor = CapabilityDescriptor(
        id="sample.collect",
        title="Sample Collect",
        provider_id="sample_provider",
        execution_target="agent_builtin",
        presentation_schema=DEFAULT_SCHEMA,
    )
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        service = ToolPresentationOverrideService(session)

        detail = await service.get_presentation_detail(descriptor)
        assert detail["module_default_schema"] == DEFAULT_SCHEMA
        assert detail["override_schema"] is None
        assert detail["effective_schema"] == DEFAULT_SCHEMA
        assert detail["source"] == "module_default"

        await service.upsert_override("sample.collect", OVERRIDE_SCHEMA, actor_id="admin-test")
        detail = await service.get_presentation_detail(descriptor)
        assert detail["module_default_schema"] == DEFAULT_SCHEMA
        assert detail["override_schema"] == OVERRIDE_SCHEMA
        assert detail["effective_schema"] == OVERRIDE_SCHEMA
        assert detail["source"] == "server_override"

        await service.delete_or_disable_override("sample.collect", actor_id="admin-test")
        detail = await service.get_presentation_detail(descriptor)
        assert detail["override_schema"] is None
        assert detail["effective_schema"] == DEFAULT_SCHEMA
        assert detail["source"] == "module_default"


@pytest.mark.asyncio
async def test_validation_rejects_invalid_or_dangerous_schema(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        service = ToolPresentationOverrideService(session)

        with pytest.raises(PresentationSchemaValidationError) as bad_root:
            await service.upsert_override("sample.collect", ["not", "object"])
        assert bad_root.value.code == "PRESENTATION_SCHEMA_INVALID"
        assert bad_root.value.path == "$"

        with pytest.raises(PresentationSchemaValidationError) as bad_block:
            await service.upsert_override(
                "sample.collect",
                {"version": "1.0", "blocks": [{"type": "unsupported_widget"}]},
            )
        assert bad_block.value.path == "$.blocks[0].type"

        with pytest.raises(PresentationSchemaValidationError) as bad_html:
            await service.upsert_override(
                "sample.collect",
                {"version": "1.0", "blocks": [{"type": "raw_json", "label": "<script>alert(1)</script>"}]},
            )
        assert bad_html.value.path == "$.blocks[0].label"


@pytest.mark.asyncio
async def test_tool_presentation_api_get_put_delete_roundtrip(test_client, test_engine) -> None:
    await _seed_persisted_capability(test_engine)

    get_default = await test_client.get("/api/web/tool-presentations?tool_id=sample.collect", headers=_admin_headers())
    assert get_default.status == 200, await get_default.text()
    default_payload = await get_default.json()
    assert default_payload["module_default_schema"] == DEFAULT_SCHEMA
    assert default_payload["override_schema"] is None
    assert default_payload["effective_schema"] == DEFAULT_SCHEMA
    assert default_payload["source"] == "module_default"

    put_override = await test_client.put(
        "/api/web/tool-presentations?tool_id=sample.collect",
        headers=_admin_headers(),
        json={"presentation_schema": OVERRIDE_SCHEMA, "enabled": True},
    )
    assert put_override.status == 200, await put_override.text()
    override_payload = await put_override.json()
    assert override_payload["override_schema"] == OVERRIDE_SCHEMA
    assert override_payload["effective_schema"] == OVERRIDE_SCHEMA
    assert override_payload["source"] == "server_override"
    assert override_payload["updated_by"] == "admin-test"

    delete_override = await test_client.delete(
        "/api/web/tool-presentations?tool_id=sample.collect",
        headers=_admin_headers(),
    )
    assert delete_override.status == 200, await delete_override.text()
    reset_payload = await delete_override.json()
    assert reset_payload["override_schema"] is None
    assert reset_payload["effective_schema"] == DEFAULT_SCHEMA
    assert reset_payload["source"] == "module_default"


@pytest.mark.asyncio
async def test_tool_presentation_api_invalid_schema_returns_400(test_client, test_engine) -> None:
    await _seed_persisted_capability(test_engine)

    response = await test_client.put(
        "/api/web/tool-presentations?tool_id=sample.collect",
        headers=_admin_headers(),
        json={"presentation_schema": {"version": 1, "blocks": [{"type": "raw_json"}]}},
    )

    assert response.status == 400
    payload = await response.json()
    assert payload["status"] == "error"
    assert payload["error_code"] == "PRESENTATION_SCHEMA_INVALID"
    assert payload["path"] == "$.version"


@pytest.mark.asyncio
async def test_capability_list_exposes_effective_presentation_schema(test_client) -> None:
    put_override = await test_client.put(
        "/api/web/tool-presentations?tool_id=server.dns.resolve",
        headers=_admin_headers(),
        json={"presentation_schema": OVERRIDE_SCHEMA, "enabled": True},
    )
    assert put_override.status == 200, await put_override.text()

    response = await test_client.get("/api/web/admin/capabilities", headers=_admin_headers())
    assert response.status == 200, await response.text()
    payload = await response.json()
    dns = next(item for item in payload["capabilities"] if item["id"] == "server.dns.resolve")

    assert dns["presentation_schema"] != OVERRIDE_SCHEMA
    assert dns["effective_presentation_schema"] == OVERRIDE_SCHEMA
    assert dns["presentation_schema_source"] == "server_override"
    assert dns["has_presentation_override"] is True


@pytest.mark.asyncio
async def test_support_timeline_tool_result_exposes_render_payload_and_effective_schema(test_client, test_engine) -> None:
    capability_id = "sample.collect"
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())
    operation_id = str(uuid.uuid4())
    await _seed_persisted_capability(test_engine, capability_id=capability_id)

    put_override = await test_client.put(
        f"/api/web/tool-presentations?tool_id={capability_id}",
        headers=_admin_headers(),
        json={"presentation_schema": OVERRIDE_SCHEMA, "enabled": True},
    )
    assert put_override.status == 200, await put_override.text()

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id=device_id,
                title="Presentation timeline",
                description="Render real tool result",
                status="in_progress",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        )
        session.add(
            TicketEvent(
                ticket_id=ticket_id,
                device_id=device_id,
                agent_seq=None,
                event_type="tool_call_result",
                operation_id=operation_id,
                payload={
                    "type": "tool_call_result",
                    "tool_name": capability_id,
                    "operation_id": operation_id,
                    "status": "success",
                    "summary": "Sample collect completed",
                    "result": {"status": "ok", "hostname": "pc-01"},
                    "ts": datetime.now(timezone.utc).isoformat(),
                },
            )
        )
        await session.commit()

    response = await test_client.get(
        f"/api/web/support/tickets/{ticket_id}/timeline?filter=diagnostics",
        headers=_support_headers(),
    )
    assert response.status == 200, await response.text()
    payload = await response.json()
    item = payload["data"]["items"][0]

    assert item["tool_name"] == capability_id
    assert item["result_payload"] == {"status": "ok", "hostname": "pc-01"}
    assert item["result_presentation_schema"] == OVERRIDE_SCHEMA
    assert item["result_presentation_schema_source"] == "server_override"
