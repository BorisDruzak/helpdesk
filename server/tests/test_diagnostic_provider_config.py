from __future__ import annotations

from datetime import datetime, timezone
import json
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import DiagnosticProviderAudit, DiagnosticProviderConfig, Ticket
from app.repos.diagnostic_provider_config_repo import DiagnosticProviderConfigRepo
from diagnostics.capability_registry import CapabilityRegistry
from diagnostics.provider_config import DiagnosticProviderConfigService
from diagnostics.readiness import CapabilityReadinessService, ReadinessContext


ADMIN_TOKEN = "test-ui-admin-token"


def _admin_auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {ADMIN_TOKEN}"}


class _FakeHttpResponse:
    def __init__(self, payload: dict):
        self._payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return self._payload


def _ticket(ticket_id: str) -> Ticket:
    return Ticket(
        ticket_id=ticket_id,
        device_id=str(uuid.uuid4()),
        title="Zabbix provider config run",
        description="Ticket for persisted Zabbix connector run",
        status="in_progress",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_provider_config_service_persists_redacts_and_audits(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)

    async with session_maker() as session:
        service = DiagnosticProviderConfigService(session)
        saved = await service.upsert_provider_config(
            provider_id="zabbix_connector",
            provider_type="server_connector",
            integration_key="zabbix",
            enabled=True,
            config={
                "url": "https://zabbix.local",
                "api_token": "plain-secret-must-not-leak",
                "mappings": {"zabbix.host": {"source": "device.hostname"}},
            },
            credential_refs=[{"credential_key": "api_token", "secret_ref": "vault://zabbix/api-token", "status": "ready"}],
            actor_id="admin-test",
            actor_role="admin",
        )
        await session.commit()

    assert saved.provider_id == "zabbix_connector"

    async with session_maker() as session:
        row = (await session.execute(select(DiagnosticProviderConfig))).scalar_one()
        audits = (await session.execute(select(DiagnosticProviderAudit))).scalars().all()
        serialized = await DiagnosticProviderConfigService(session).get_provider_config("zabbix_connector")

    assert row.status == "ready"
    assert row.config_json["api_token"] == "***redacted***"
    assert len(audits) == 1
    assert audits[0].action == "provider_config.upsert"
    assert serialized is not None
    assert serialized["config"]["api_token"] == "***redacted***"
    assert serialized["credential_refs"][0]["secret_ref"] == "***redacted***"


@pytest.mark.asyncio
async def test_provider_config_service_feeds_zabbix_readiness_context(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    registry = CapabilityRegistry()
    zabbix = {
        capability.id: capability
        for capability in await registry.list_capabilities(device_id=None)
    }["zabbix.problems.lookup"]

    async with session_maker() as session:
        service = DiagnosticProviderConfigService(session)
        empty_maps = await service.build_readiness_maps()
        no_config = await CapabilityReadinessService().get_readiness(
            zabbix,
            ReadinessContext(
                integration_configs=empty_maps.integration_configs,
                credential_keys=empty_maps.credential_keys,
                mappings=empty_maps.mappings,
                permissions={"monitoring.zabbix.view"},
                policy_flags={"monitoring.zabbix.enabled": True},
            ),
        )
        await service.upsert_provider_config(
            provider_id="zabbix_connector",
            provider_type="server_connector",
            integration_key="zabbix",
            enabled=True,
            config={"url": "https://zabbix.local"},
            credential_refs=[],
            actor_id="admin-test",
            actor_role="admin",
        )
        missing_credentials_maps = await service.build_readiness_maps()
        missing_credentials = await CapabilityReadinessService().get_readiness(
            zabbix,
            ReadinessContext(
                integration_configs=missing_credentials_maps.integration_configs,
                credential_keys=missing_credentials_maps.credential_keys,
                mappings=missing_credentials_maps.mappings,
                permissions={"monitoring.zabbix.view"},
                policy_flags={"monitoring.zabbix.enabled": True},
            ),
        )
        await service.upsert_provider_config(
            provider_id="zabbix_connector",
            provider_type="server_connector",
            integration_key="zabbix",
            enabled=True,
            config={"url": "https://zabbix.local"},
            credential_refs=[{"credential_key": "api_token", "secret_ref": "vault://zabbix/api-token", "status": "ready"}],
            actor_id="admin-test",
            actor_role="admin",
        )
        missing_mapping_maps = await service.build_readiness_maps()
        missing_mapping = await CapabilityReadinessService().get_readiness(
            zabbix,
            ReadinessContext(
                integration_configs=missing_mapping_maps.integration_configs,
                credential_keys=missing_mapping_maps.credential_keys,
                mappings=missing_mapping_maps.mappings,
                permissions={"monitoring.zabbix.view"},
                policy_flags={"monitoring.zabbix.enabled": True},
            ),
        )
        await service.upsert_provider_config(
            provider_id="zabbix_connector",
            provider_type="server_connector",
            integration_key="zabbix",
            enabled=True,
            config={
                "url": "https://zabbix.local",
                "mappings": {"zabbix.host": {"source": "device.hostname"}},
            },
            credential_refs=[{"credential_key": "api_token", "secret_ref": "vault://zabbix/api-token", "status": "ready"}],
            actor_id="admin-test",
            actor_role="admin",
        )
        available_maps = await service.build_readiness_maps()
        available = await CapabilityReadinessService().get_readiness(
            zabbix,
            ReadinessContext(
                integration_configs=available_maps.integration_configs,
                credential_keys=available_maps.credential_keys,
                mappings=available_maps.mappings,
                permissions={"monitoring.zabbix.view"},
                policy_flags={"monitoring.zabbix.enabled": True},
            ),
        )

    assert no_config.readiness == "integration_not_configured"
    assert missing_credentials.readiness == "credentials_missing"
    assert missing_mapping.readiness == "mapping_missing"
    assert available.readiness == "available"
    assert available_maps.credential_refs["zabbix"] == "vault://zabbix/api-token"


@pytest.mark.asyncio
async def test_provider_config_api_upserts_and_lists_redacted_config(test_client):
    payload = {
        "provider_type": "server_connector",
        "integration_key": "zabbix",
        "enabled": True,
        "config": {
            "url": "https://zabbix.local",
            "password": "must-not-leak",
            "mappings": {"zabbix.host": {"source": "device.hostname"}},
        },
        "credential_refs": [
            {"credential_key": "api_token", "secret_ref": "vault://zabbix/api-token", "status": "ready"}
        ],
    }

    put_resp = await test_client.put(
        "/api/diagnostics/providers/configs/zabbix_connector",
        json=payload,
        headers=_admin_auth(),
    )
    assert put_resp.status == 200
    put_data = await put_resp.json()

    list_resp = await test_client.get("/api/diagnostics/providers/configs", headers=_admin_auth())
    assert list_resp.status == 200
    list_data = await list_resp.json()

    assert put_data["status"] == "ok"
    assert put_data["provider_config"]["status"] == "ready"
    assert put_data["provider_config"]["config"]["password"] == "***redacted***"
    assert put_data["provider_config"]["credential_refs"][0]["secret_ref"] == "***redacted***"
    assert list_data["status"] == "ok"
    assert list_data["provider_configs"][0]["provider_id"] == "zabbix_connector"
    assert list_data["provider_configs"][0]["config"]["password"] == "***redacted***"


@pytest.mark.asyncio
async def test_provider_config_web_admin_aliases_use_same_redacted_contract(test_client):
    payload = {
        "provider_type": "server_connector",
        "integration_key": "zabbix",
        "enabled": True,
        "config": {
            "url": "https://zabbix.local",
            "api_token": "must-not-leak",
            "mappings": {"zabbix.host": {"source": "device.hostname"}},
        },
        "credential_refs": [
            {"credential_key": "api_token", "secret_ref": "vault://zabbix/api-token", "status": "ready"}
        ],
    }

    put_resp = await test_client.put(
        "/api/web/admin/diagnostics/providers/configs/zabbix_connector",
        json=payload,
        headers=_admin_auth(),
    )
    assert put_resp.status == 200

    get_resp = await test_client.get(
        "/api/web/admin/diagnostics/providers/configs/zabbix_connector",
        headers=_admin_auth(),
    )
    list_resp = await test_client.get("/api/web/admin/diagnostics/providers/configs", headers=_admin_auth())
    assert get_resp.status == 200
    assert list_resp.status == 200

    get_data = await get_resp.json()
    list_data = await list_resp.json()
    assert get_data["provider_config"]["config"]["api_token"] == "***redacted***"
    assert get_data["provider_config"]["credential_refs"][0]["secret_ref"] == "***redacted***"
    assert list_data["count"] == 1


@pytest.mark.asyncio
async def test_zabbix_capability_run_uses_persisted_provider_config(monkeypatch, test_client, test_engine):
    calls = []

    def fake_urlopen(request, timeout=0, context=None):
        payload = json.loads(request.data.decode("utf-8"))
        calls.append(payload)
        return _FakeHttpResponse({"jsonrpc": "2.0", "id": payload["id"], "result": []})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    ticket_id = str(uuid.uuid4())
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(_ticket(ticket_id))
        service = DiagnosticProviderConfigService(session)
        await service.upsert_provider_config(
            provider_id="zabbix_connector",
            provider_type="server_connector",
            integration_key="zabbix",
            enabled=True,
            config={
                "url": "https://zabbix.example/api_jsonrpc.php",
                "mappings": {"zabbix.host": {"hostid": "10101"}},
            },
            credential_refs=[{"credential_key": "api_token", "secret_ref": "plain-test-token", "status": "ready"}],
            actor_id="admin-test",
            actor_role="admin",
        )
        await session.commit()

    response = await test_client.post(
        f"/api/tickets/{ticket_id}/diagnostics/capabilities/zabbix.problems.lookup/run",
        json={},
        headers=_admin_auth(),
    )
    data = await response.json()

    assert response.status == 200
    assert data["status"] == "success"
    assert data["execution_target"] == "server_connector"
    assert data["output"]["problem_count"] == 0
    assert calls[0]["auth"] == "plain-test-token"
    assert calls[0]["params"]["hostids"] == ["10101"]
