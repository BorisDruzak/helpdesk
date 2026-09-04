from __future__ import annotations

import json

import pytest

from diagnostics.capability_registry import CapabilityRegistry
from diagnostics.execution_router import CapabilityExecutionRouter
from diagnostics.providers.server_connector import ServerConnectorProvider
from diagnostics.providers.zabbix_provider import list_zabbix_capabilities


class _FakeHttpResponse:
    def __init__(self, payload: dict):
        self._payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return self._payload


def _capability(capability_id: str):
    return {cap.id: cap for cap in list_zabbix_capabilities()}[capability_id]


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_zabbix_problem_lookup_calls_jsonrpc_and_redacts_token(monkeypatch):
    calls = []

    def fake_urlopen(request, timeout=0, context=None):
        payload = json.loads(request.data.decode("utf-8"))
        calls.append({"url": request.full_url, "timeout": timeout, "payload": payload, "headers": dict(request.headers)})
        return _FakeHttpResponse(
            {
                "jsonrpc": "2.0",
                "id": payload["id"],
                "result": [
                    {
                        "eventid": "9001",
                        "objectid": "7001",
                        "name": "Backend web is unavailable",
                        "severity": "4",
                        "clock": "1710000000",
                        "hosts": [{"hostid": "10101", "host": "backend-web-01"}],
                    }
                ],
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    provider = ServerConnectorProvider()

    result = await provider.run_query(
        _capability("zabbix.problems.lookup"),
        params={
            "integration_config": {"url": "https://zabbix.example/api_jsonrpc.php", "timeout_sec": 7},
            "credentials_ref": {"api_token": "secret-zabbix-token"},
            "mapping": {"hostid": "10101"},
        },
    )
    normalized = provider.normalize_result(_capability("zabbix.problems.lookup"), result)
    evidence = provider.map_evidence(_capability("zabbix.problems.lookup"), normalized)

    assert result["status"] == "success"
    assert result["output"]["problem_count"] == 1
    assert result["output"]["problems"][0]["name"] == "Backend web is unavailable"
    assert "secret-zabbix-token" not in json.dumps(result)
    assert calls[0]["url"] == "https://zabbix.example/api_jsonrpc.php"
    assert calls[0]["timeout"] == 7
    assert calls[0]["payload"]["method"] == "problem.get"
    assert calls[0]["payload"]["auth"] == "secret-zabbix-token"
    assert calls[0]["payload"]["params"]["hostids"] == ["10101"]
    assert evidence["kind"] == "monitoring.problem"
    assert evidence["status"] == "ok"


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_zabbix_host_health_and_item_history_use_bounded_jsonrpc_queries(monkeypatch):
    calls = []

    def fake_urlopen(request, timeout=0, context=None):
        payload = json.loads(request.data.decode("utf-8"))
        calls.append(payload)
        if payload["method"] == "host.get":
            return _FakeHttpResponse(
                {
                    "jsonrpc": "2.0",
                    "id": payload["id"],
                    "result": [
                        {
                            "hostid": "10101",
                            "host": "backend-web-01",
                            "name": "Backend Web 01",
                            "status": "0",
                            "available": "1",
                        }
                    ],
                }
            )
        return _FakeHttpResponse(
            {
                "jsonrpc": "2.0",
                "id": payload["id"],
                "result": [
                    {"itemid": "3001", "clock": "1710000000", "value": "42"},
                    {"itemid": "3001", "clock": "1710000060", "value": "43"},
                ],
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    provider = ServerConnectorProvider()

    health = await provider.run_query(
        _capability("zabbix.host.health"),
        params={
            "integration_config": {"url": "https://zabbix.example/api_jsonrpc.php"},
            "credentials_ref": "plain-test-token",
            "mapping": {"hostid": "10101"},
        },
    )
    history = await provider.run_query(
        _capability("zabbix.item.history"),
        params={
            "integration_config": {"url": "https://zabbix.example/api_jsonrpc.php"},
            "credentials_ref": "plain-test-token",
            "mapping": {"itemid": "3001"},
            "limit": 500,
        },
    )

    assert health["status"] == "success"
    assert health["output"]["host"]["hostid"] == "10101"
    assert history["status"] == "success"
    assert history["output"]["value_count"] == 2
    assert calls[0]["method"] == "host.get"
    assert calls[0]["params"]["hostids"] == ["10101"]
    assert calls[1]["method"] == "history.get"
    assert calls[1]["params"]["itemids"] == ["3001"]
    assert calls[1]["params"]["limit"] == 100


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_zabbix_api_errors_are_structured_and_do_not_leak_credentials(monkeypatch):
    def fake_urlopen(request, timeout=0, context=None):
        payload = json.loads(request.data.decode("utf-8"))
        return _FakeHttpResponse(
            {
                "jsonrpc": "2.0",
                "id": payload["id"],
                "error": {"code": -32602, "message": "Invalid params.", "data": "Bad hostids"},
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    provider = ServerConnectorProvider()

    result = await provider.run_query(
        _capability("zabbix.problems.lookup"),
        params={
            "integration_config": {"url": "https://zabbix.example/api_jsonrpc.php"},
            "credentials_ref": {"api_token": "secret-zabbix-token"},
            "mapping": {"hostid": "10101"},
        },
    )

    assert result["status"] == "error"
    assert result["error_code"] == "ZABBIX_API_ERROR"
    assert result["message"] == "Invalid params."
    assert "secret-zabbix-token" not in json.dumps(result)


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_zabbix_connector_routes_through_router_without_tool_execution(monkeypatch):
    def fake_urlopen(request, timeout=0, context=None):
        payload = json.loads(request.data.decode("utf-8"))
        return _FakeHttpResponse({"jsonrpc": "2.0", "id": payload["id"], "result": []})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    router = CapabilityExecutionRouter(capability_registry=CapabilityRegistry())
    result = await router.run_capability(
        ticket_id="ticket-1",
        device_id="device-1",
        capability_id="zabbix.problems.lookup",
        params={
            "integration_config": {"url": "https://zabbix.example/api_jsonrpc.php"},
            "credentials_ref": "plain-test-token",
            "mapping": {"hostid": "10101"},
        },
        actor=None,
        readiness={"readiness": "available"},
        idempotency_key="idem-zabbix",
        timeout_ms=1000,
    )

    assert result["status"] == "success"
    assert result["execution_target"] == "server_connector"
    assert result["execution_kind"] == "query"
    assert result["provider_id"] == "zabbix_connector"
    assert result["idempotency_key"] == "idem-zabbix"
