"""Real cross-repository acceptance for the Endpoint Module Platform v1 path."""

from __future__ import annotations

import ipaddress
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import aiohttp
import pytest
import websockets
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import DeviceOutbox, DiagnosticEvidence, EndpointOperationLink, Operation, Ticket
from app.services.endpoint_module_operation_reconciler import (
    EndpointModuleOperationReconciler,
    SqlAlchemyEndpointModuleOperationReconcileStore,
)
from app.services.endpoint_module_operation_service import (
    EndpointModuleOperationRequest,
    EndpointModuleOperationService,
    SqlAlchemyEndpointModuleOperationStore,
    StoredTicketEndpointModuleDeviceResolver,
)
from endpoint_adapter.modules_http import ExternalEndpointModuleHttpAdapter
from tests.acceptance.test_endpoint_operations_v1_acceptance import (
    _DEVICE_PEPPER,
    _DEVICE_TOKEN,
    _SERVICE_PEPPER,
    _disposable_endpoint_postgres,
    _free_port,
    _start,
    _stop,
)

from endpoint_contracts import AgentResultV1
from endpoint_contracts.network_primitives import (
    DnsResolveResultV1,
    NetworkPingResultV1,
    TcpConnectResultV1,
)
from endpoint_server.auth.service_tokens import create_service_credential
from endpoint_server.config import Settings
from endpoint_server.db.models import Device, DeviceCredential, EndpointOperation, ServiceClient
from endpoint_server.db.session import AsyncSessionProvider
from endpoint_server.enrollment.credentials import device_token_digest
from endpoint_server.main import create_app


pytestmark = pytest.mark.manual


_MODULE_KEY = "network.basic.check"
_MODULE_VERSION = "1.0.0"


class _Access:
    async def require_ticket_operation_access(self, *, actor: object, ticket_id: str) -> None:
        assert getattr(actor, "actor_id", None) == "module-acceptance"
        assert ticket_id


async def _issue_token(
    provider: AsyncSessionProvider, *, client_id: object, scopes: tuple[str, ...], identifier: str
) -> str:
    async with provider() as session:
        issued = await create_service_credential(
            session,
            client_id,
            _SERVICE_PEPPER,
            actor_kind="test",
            actor_identifier="module-platform-acceptance",
            request_id="module-platform-acceptance",
            scopes=scopes,
            credential_identifier=identifier,
        )
    return issued.token


def _recipe() -> dict[str, object]:
    return {
        "schema_version": "endpoint_recipe_module_v1",
        "module_key": _MODULE_KEY,
        "supported_platforms": ["linux_amd64"],
        "inputs": [
            {"name": "target", "value_type": "string"},
            {"name": "port", "value_type": "integer"},
        ],
        "steps": [
            {"step_id": "dns", "capability": "dns.resolve", "parameters": {
                "target": {"kind": "input", "name": "target"},
                "family": {"kind": "literal", "value": "any"},
            }},
            {"step_id": "ping", "capability": "network.ping", "parameters": {
                "target": {"kind": "input", "name": "target"},
                "count": {"kind": "literal", "value": 1},
                "timeout_ms": {"kind": "literal", "value": 500},
            }},
            {"step_id": "tcp", "capability": "tcp.connect", "parameters": {
                "target": {"kind": "input", "name": "target"},
                "port": {"kind": "input", "name": "port"},
                "timeout_ms": {"kind": "literal", "value": 500},
            }},
        ],
    }


def _hello(device_id: str) -> dict[str, object]:
    return {
        "schema_version": "gateway_ws_envelope_v1",
        "kind": "agent_hello",
        "sequence": 1,
        "payload": {
            "schema_version": "agent_hello_v1", "device_id": device_id,
            "agent_instance_id": str(uuid4()), "agent_version": "4.0.0",
            "launcher_version": "2.0.0", "platform": "linux_amd64", "boot_id": "module-acceptance",
            "capabilities": ["dns.resolve", "network.ping", "tcp.connect"],
            "last_result_sequence": 0, "last_policy_revision": 0,
        },
    }


def _result_for(command: dict[str, object]) -> dict[str, object]:
    now = datetime.now(UTC)
    parameters = command["parameters"]
    target = parameters["target"]
    capability = command["capability"]
    if capability == "dns.resolve":
        return DnsResolveResultV1(schema_version="dns_resolve_result_v1", target=target, canonical_name=None,
            addresses=[], address_count=0, status="succeeded", error_code=None, collected_at=now).model_dump(mode="json")
    if capability == "network.ping":
        return NetworkPingResultV1(schema_version="network_ping_result_v1", target=target, resolved_ip=None,
            transmitted=1, received=0, packet_loss_percent=100.0, min_ms=None, avg_ms=None, max_ms=None,
            reachable=False, status="succeeded", error_code=None, collected_at=now).model_dump(mode="json")
    assert capability == "tcp.connect"
    return TcpConnectResultV1(schema_version="tcp_connect_result_v1", target=target, resolved_ip=None,
        port=parameters["port"], reachable=False, latency_ms=None, status="succeeded", error_code=None,
        collected_at=now).model_dump(mode="json")


async def _complete_module_recipe(websocket, *, device_id: str, sequence: int) -> tuple[int, list[dict[str, object]]]:
    commands: list[dict[str, object]] = []
    for _ in range(3):
        await websocket.send(json.dumps({
            "schema_version": "gateway_ws_envelope_v1", "kind": "heartbeat", "sequence": sequence,
            "payload": {"schema_version": "agent_heartbeat_v1", "device_id": device_id, "platform": "linux",
                "agent_version": "4.0.0", "reported_at": datetime.now(UTC).isoformat()},
        }))
        while True:
            message = json.loads(await websocket.recv())
            if message["kind"] != "command":
                continue
            command = message["payload"]
            serialized = json.dumps(command, sort_keys=True).lower()
            assert not any(value in serialized for value in ("helpdesk", "ticket", "requester", "authorization", "recipe"))
            commands.append(command)
            result = AgentResultV1(schema_version="agent_result_v1", command_id=command["command_id"],
                device_id=device_id, status="succeeded", result_items=[_result_for(command)], completed_at=datetime.now(UTC))
            await websocket.send(json.dumps({
                "schema_version": "gateway_ws_envelope_v1", "kind": "command_result", "sequence": sequence + 1,
                "payload": result.model_dump(mode="json"),
            }))
            while json.loads(await websocket.recv())["kind"] != "result_ack":
                pass
            sequence += 2
            break
    return sequence, commands


@pytest.mark.asyncio
@pytest.mark.cross_repo_acceptance
async def test_module_recipe_real_provider_wss_and_helpdesk_evidence(
    tmp_path, test_database_admin_url: str, test_engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise lifecycle, ordered primitive delivery and one Helpdesk evidence projection."""

    provider_database = await _disposable_endpoint_postgres(test_database_admin_url)
    provider = provider_database.provider
    async with provider() as session:
        owner = ServiceClient(id=uuid4(), client_identifier="module-owner", display_name="Module owner")
        helpdesk = ServiceClient(id=uuid4(), client_identifier="module-helpdesk", display_name="Module Helpdesk")
        device = Device(id=uuid4(), device_identifier="module-acceptance-device", display_name="Module device")
        session.add_all((owner, helpdesk, device))
        await session.flush()
        session.add(DeviceCredential(id=uuid4(), device_id=device.id, credential_identifier="module-device-credential",
            token_digest=device_token_digest(_DEVICE_TOKEN, _DEVICE_PEPPER), pending_token_digest=None,
            rotation_overlap_expires_at=None, expires_at=None, revoked_at=None))
        await session.commit()
    owner_token = await _issue_token(provider, client_id=owner.id, identifier="c" * 32,
        scopes=("modules.read", "modules.write", "modules.validate", "modules.publish", "module_operations.create", "module_operations.read"))
    helpdesk_token = await _issue_token(provider, client_id=helpdesk.id, identifier="d" * 32,
        scopes=("modules.read", "module_operations.create", "module_operations.read"))
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    settings = Settings(database_url=provider_database.database_url, public_base_url="https://endpoint.sosnadmin.local",
        device_token_pepper=_DEVICE_PEPPER, service_token_pepper=_SERVICE_PEPPER, session_secret=b"module-acceptance",
        allowed_agent_cidrs=(ipaddress.ip_network("127.0.0.0/8"),), allowed_admin_cidrs=(),
        trusted_proxy_cidrs=(ipaddress.ip_network("127.0.0.0/8"),), artifact_root=artifacts,
        endpoint_operations_api_enabled=True, endpoint_network_primitives_enabled=True,
        endpoint_network_probe_allowed_suffixes=("example.test",), endpoint_module_platform_enabled=True,
        endpoint_module_execution_enabled=True)
    port = _free_port()
    server, task = await _start(create_app(settings, provider), port)
    base_url = f"http://127.0.0.1:{port}"
    headers = {"Authorization": f"Bearer {owner_token}", "X-Correlation-ID": "module-acceptance"}
    version_path = f"/api/v1/modules/{_MODULE_KEY}/versions/{_MODULE_VERSION}"
    try:
        async with aiohttp.ClientSession() as http:
            created = await http.post(f"{base_url}/api/v1/modules/versions", headers=headers,
                json={"schema_version": "module_version_create_v1", "display_name": "Network acceptance",
                      "version": _MODULE_VERSION, "recipe": _recipe()})
            assert created.status == 201
            validated = await http.post(f"{base_url}{version_path}/validate", headers=headers)
            assert validated.status == 200 and (await validated.json())["data"]["status"] == "succeeded"
            lab = await http.post(f"{base_url}{version_path}/lab-operations/{device.id}", headers=headers | {"Idempotency-Key": "module-lab-acceptance-0001"},
                json={"schema_version": "endpoint_module_lab_operation_create_v1", "inputs": {"target": "api.example.test", "port": 443}})
            assert lab.status == 201
            lab_operation_id = (await lab.json())["data"]["operation_id"]
        async with websockets.connect(f"ws://127.0.0.1:{port}/agent/v1/connect", additional_headers={
            "Authorization": f"Bearer {_DEVICE_TOKEN}", "X-Forwarded-Proto": "https", "X-Forwarded-For": "127.0.0.1"}) as websocket:
            await websocket.send(json.dumps(_hello(str(device.id))))
            assert json.loads(await websocket.recv())["kind"] == "gateway_hello"
            _, lab_commands = await _complete_module_recipe(websocket, device_id=str(device.id), sequence=2)
        assert [command["capability"] for command in lab_commands] == ["dns.resolve", "network.ping", "tcp.connect"]
        async with aiohttp.ClientSession() as http:
            live_test = await http.post(f"{base_url}{version_path}/live-tests/{lab_operation_id}", headers=headers,
                json={"schema_version": "module_live_test_record_v1"})
            accepted = await http.post(f"{base_url}{version_path}/accept-labs", headers=headers)
            published = await http.post(f"{base_url}{version_path}/publish", headers=headers)
            assert live_test.status == 201 and accepted.status == 200 and published.status == 200

        adapter = ExternalEndpointModuleHttpAdapter(base_url=base_url, service_token=helpdesk_token, ca_file="",
            timeout_seconds=2, allow_insecure_test_url=True, correlation_id_factory=lambda: "module-helpdesk")
        capability_catalog = await adapter.list_recipe_capabilities()
        assert capability_catalog.schema_version == "endpoint_module_capability_catalog_v1"
        assert {item.capability for item in capability_catalog.items} == {
            "adapter.list", "dns.resolve", "network.ping", "route.get", "system.service_status", "tcp.connect",
        }
        session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
        ticket_id = str(uuid4())
        async with session_factory() as session:
            session.add(Ticket(ticket_id=ticket_id, device_id="helpdesk-module-device", endpoint_device_ref=str(device.id),
                title="Module acceptance", description="Module acceptance", status="in_progress", requester_id="module-requester"))
            await session.commit()
        from tools.service import ToolService
        from websocket import protocol as websocket_protocol
        async def _legacy_called(*_args, **_kwargs) -> None:
            raise AssertionError("Endpoint module execution must not use Helpdesk legacy dispatch")
        monkeypatch.setattr(ToolService, "run_tool", _legacy_called)
        monkeypatch.setattr(websocket_protocol, "send_ws_command", _legacy_called)
        monkeypatch.setattr(websocket_protocol, "enqueue_command_async", _legacy_called)
        facade = EndpointModuleOperationService(access_service=_Access(),
            device_resolver=StoredTicketEndpointModuleDeviceResolver(session_factory),
            store=SqlAlchemyEndpointModuleOperationStore(session_factory))
        request = EndpointModuleOperationRequest(ticket_id=ticket_id, module_key=_MODULE_KEY, module_version=_MODULE_VERSION,
            inputs={"target": "api.example.test", "port": 443}, idempotency_key="module-helpdesk-acceptance-0001")
        actor = SimpleNamespace(actor_id="module-acceptance", actor_role="support")
        local = await facade.create(actor=actor, request=request)
        assert await facade.create(actor=actor, request=request) == local
        clock = [datetime.now(UTC) + timedelta(minutes=1)]
        reconciler = EndpointModuleOperationReconciler(endpoint_port=adapter,
            store=SqlAlchemyEndpointModuleOperationReconcileStore(session_factory), mode="external", execution_mode="endpoint",
            owner="module-acceptance", now=lambda: clock[0])
        assert await reconciler.reconcile_once(limit=1) == 1
        async with websockets.connect(f"ws://127.0.0.1:{port}/agent/v1/connect", additional_headers={
            "Authorization": f"Bearer {_DEVICE_TOKEN}", "X-Forwarded-Proto": "https", "X-Forwarded-For": "127.0.0.1"}) as websocket:
            await websocket.send(json.dumps(_hello(str(device.id))))
            assert json.loads(await websocket.recv())["kind"] == "gateway_hello"
            _, commands = await _complete_module_recipe(websocket, device_id=str(device.id), sequence=2)
        assert [command["capability"] for command in commands] == ["dns.resolve", "network.ping", "tcp.connect"]
        clock[0] += timedelta(seconds=10)
        assert await reconciler.reconcile_once(limit=1) == 1
        assert await reconciler.reconcile_once(limit=1) == 0
        async with session_factory() as session:
            ticket = await session.get(Ticket, ticket_id)
            operation = await session.get(Operation, local.operation_id)
            link = (await session.execute(select(EndpointOperationLink).where(EndpointOperationLink.operation_id == local.operation_id))).scalar_one()
            evidence = list((await session.scalars(select(DiagnosticEvidence).where(DiagnosticEvidence.ticket_id == ticket_id))).all())
            outbox_count = await session.scalar(select(func.count()).select_from(DeviceOutbox).where(DeviceOutbox.operation_id == local.operation_id))
        async with provider() as session:
            remote_count = await session.scalar(select(func.count()).select_from(EndpointOperation).where(
                EndpointOperation.requested_by_service_client_id == helpdesk.id))
        assert ticket is not None and ticket.status == "in_progress"
        assert operation is not None and operation.status == "succeeded"
        assert link.endpoint_operation_ref is not None and link.safe_result_snapshot_json is not None
        assert len(evidence) == 1 and evidence[0].source_id == link.endpoint_operation_ref
        assert outbox_count == 0 and remote_count == 1
    finally:
        await _stop(server, task)
        await provider_database.close()
