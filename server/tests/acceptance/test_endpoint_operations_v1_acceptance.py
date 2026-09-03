"""Cross-repository acceptance for the released Endpoint Operations v1 provider.

The imports below are deliberately test-only.  Helpdesk production code keeps
its Endpoint boundary at ``domain_ports.endpoint`` and never imports this
repository.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import os
import socket
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import aiohttp
import asyncpg
import pytest
import uvicorn
import websockets
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker


pytestmark = pytest.mark.manual

from app.db.models import (
    DiagnosticEvidence,
    DiagnosticSession,
    DiagnosticStep,
    EndpointOperationLink,
    Operation,
    Ticket,
)
from app.services.endpoint_device_reference_service import EndpointDeviceReferenceService
from app.services.endpoint_diagnostic_operation_service import (
    EndpointDiagnosticOperationRequest,
    EndpointDiagnosticOperationService,
    SqlAlchemyEndpointDiagnosticOperationStore,
)
from app.services.endpoint_operation_reconciler import (
    EndpointOperationReconciler,
    SqlAlchemyEndpointOperationReconcileStore,
)
from domain_ports.endpoint import EndpointDeviceRef, EndpointOperationCreateRequest
from endpoint_adapter.http import ExternalEndpointHttpAdapter
from scripts.validate_endpoint_contract_lock import validate as validate_contract_lock


_endpoint_root_value = os.environ.get("ENDPOINT_PLATFORM_REPO")
if not _endpoint_root_value:
    pytest.skip(
        "cross-repository acceptance requires ENDPOINT_PLATFORM_REPO",
        allow_module_level=True,
    )
_ENDPOINT_ROOT = Path(_endpoint_root_value).resolve()
try:
    validate_contract_lock(
        lock_path=Path(__file__).resolve().parents[3]
        / "integration"
        / "endpoint_contract.lock.json",
        provider_root=_ENDPOINT_ROOT,
    )
except ValueError as error:
    raise RuntimeError("cross-repository Endpoint provider lock validation failed") from error
if str(_ENDPOINT_ROOT) not in sys.path:
    sys.path.insert(0, str(_ENDPOINT_ROOT))

# Test-only provider imports.  This special acceptance test starts the real
# factory and uses its real routes; it never substitutes a JSON test server.
from endpoint_contracts import AgentResultV1, DeviceContextDiagnosticV1  # noqa: E402
from endpoint_server.auth.service_tokens import create_service_credential  # noqa: E402
from endpoint_server.config import Settings  # noqa: E402
from endpoint_server.db.models import (  # noqa: E402
    Device,
    DeviceCredential,
    EndpointOperation,
    ServiceClient,
)
from endpoint_server.enrollment.credentials import device_token_digest  # noqa: E402
from endpoint_server.db.session import AsyncSessionProvider  # noqa: E402
from endpoint_server.main import create_app  # noqa: E402


_DEVICE_TOKEN = "acceptance-device-token"
_DEVICE_PEPPER = b"acceptance-device-pepper"
_SERVICE_PEPPER = b"acceptance-service-pepper"


async def _issue_acceptance_service_token(
    provider: AsyncSessionProvider,
    *,
    service_client_id,
    credential_identifier: str,
) -> str:
    async with provider() as session:
        issued = await create_service_credential(
            session,
            service_client_id,
            _SERVICE_PEPPER,
            actor_kind="test",
            actor_identifier="helpdesk-endpoint-acceptance",
            request_id="endpoint-contract-acceptance",
            scopes=("devices.read", "operations.create", "operations.read"),
            credential_identifier=credential_identifier,
        )
    return issued.token


@dataclass
class _DisposableEndpointPostgres:
    database_url: str
    database_name: str
    admin_url: str
    provider: AsyncSessionProvider

    async def close(self) -> None:
        await self.provider.close()
        connection = await asyncpg.connect(self.admin_url)
        try:
            await connection.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                f"WHERE datname = '{self.database_name}' AND pid <> pg_backend_pid()"
            )
            await connection.execute(f'DROP DATABASE "{self.database_name}"')
        finally:
            await connection.close()


async def _disposable_endpoint_postgres(admin_database_url: str) -> _DisposableEndpointPostgres:
    """Create a loopback-only Endpoint PostgreSQL DB migrated through real head."""

    parsed = make_url(admin_database_url)
    if (
        parsed.get_backend_name() != "postgresql"
        or parsed.host not in {"127.0.0.1", "localhost", "::1"}
        or bool(parsed.query)
        or not parsed.username
        or not parsed.password
    ):
        raise ValueError("Endpoint acceptance requires a loopback PostgreSQL test admin URL")
    database_name = f"endpoint_acceptance_{uuid4().hex}"
    plain_admin_url = parsed.set(drivername="postgresql", query={}).render_as_string(
        hide_password=False
    )
    database_url = parsed.set(
        drivername="postgresql+asyncpg", database=database_name, query={}
    ).render_as_string(hide_password=False)
    connection = await asyncpg.connect(plain_admin_url)
    try:
        await connection.execute(f'CREATE DATABASE "{database_name}"')
    finally:
        await connection.close()
    environment = os.environ | {"DATABASE_URL": database_url}
    try:
        subprocess.run(
            [sys.executable, "-m", "alembic", "-c", str(_ENDPOINT_ROOT / "alembic.ini"), "upgrade", "head"],
            cwd=_ENDPOINT_ROOT,
            env=environment,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
    except subprocess.CalledProcessError as error:
        cleanup_connection = await asyncpg.connect(plain_admin_url)
        try:
            await cleanup_connection.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                f"WHERE datname = '{database_name}' AND pid <> pg_backend_pid()"
            )
            await cleanup_connection.execute(f'DROP DATABASE "{database_name}"')
        finally:
            await cleanup_connection.close()
        raise RuntimeError("Endpoint acceptance PostgreSQL migration failed") from error
    return _DisposableEndpointPostgres(
        database_url=database_url,
        database_name=database_name,
        admin_url=plain_admin_url,
        provider=AsyncSessionProvider(database_url),
    )


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


async def _start(app, port: int) -> tuple[uvicorn.Server, asyncio.Task[None]]:
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", lifespan="on")
    )
    task = asyncio.create_task(server.serve())
    for _ in range(100):
        if server.started:
            return server, task
        await asyncio.sleep(0.02)
    server.should_exit = True
    await task
    raise RuntimeError("Endpoint acceptance server did not start")


async def _stop(server: uvicorn.Server, task: asyncio.Task[None]) -> None:
    server.should_exit = True
    await asyncio.wait_for(task, timeout=5)


def _agent_hello(device_id: str) -> dict[str, object]:
    return {
        "schema_version": "gateway_ws_envelope_v1",
        "kind": "agent_hello",
        "sequence": 1,
        "payload": {
            "schema_version": "agent_hello_v1",
            "device_id": device_id,
            "agent_instance_id": str(uuid4()),
            "agent_version": "4.0.0",
            "launcher_version": "2.0.0",
            "platform": "linux_amd64",
            "boot_id": "acceptance-boot",
            "capabilities": ["context.diagnostic.collect"],
            "last_result_sequence": 0,
            "last_policy_revision": 0,
        },
    }


async def _complete_next_command(websocket, *, device_id: str, sequence: int) -> int:
    """Return after a real WSS command has been answered with a safe result."""

    await websocket.send(
        json.dumps(
            {
                "schema_version": "gateway_ws_envelope_v1",
                "kind": "heartbeat",
                "sequence": sequence,
                "payload": {
                    "schema_version": "agent_heartbeat_v1",
                    "device_id": device_id,
                    "platform": "linux",
                    "agent_version": "4.0.0",
                    "reported_at": datetime.now(UTC).isoformat(),
                },
            }
        )
    )
    while True:
        received = json.loads(await websocket.recv())
        if received["kind"] == "command":
            command = received["payload"]
            serialized_command = json.dumps(command, sort_keys=True).lower()
            forbidden_command_content = (
                "helpdesk",
                "ticket",
                "requester",
                "actor",
                "queue",
                "diagnostic_session",
                "caller_idempotency_key",
                "service credential",
                "service_credential",
                "authorization",
            )
            assert not any(value in serialized_command for value in forbidden_command_content)
            diagnostic = DeviceContextDiagnosticV1.model_validate(
                {
                    "schema_version": "device_context_v1",
                    "profile": "diagnostic_v1",
                    "collected_at": datetime.now(UTC),
                    "warnings": [],
                    "sections": {
                        "reason": command["parameters"]["reason"],
                        "processes": [{"name": "acceptance-safe-process", "state": "running"}],
                        "log_excerpt": "bounded acceptance result",
                    },
                }
            )
            result = AgentResultV1(
                schema_version="agent_result_v1",
                command_id=command["command_id"],
                device_id=device_id,
                status="succeeded",
                result_items=[diagnostic.model_dump(mode="json")],
                completed_at=datetime.now(UTC),
            )
            await websocket.send(
                json.dumps(
                    {
                        "schema_version": "gateway_ws_envelope_v1",
                        "kind": "command_result",
                        "sequence": sequence + 1,
                        "payload": result.model_dump(mode="json"),
                    }
                )
            )
            while True:
                acknowledgement = json.loads(await websocket.recv())
                if acknowledgement["kind"] == "result_ack":
                    return sequence + 2


@pytest.mark.asyncio
@pytest.mark.cross_repo_acceptance
async def test_real_endpoint_provider_adapter_and_gateway_wss_acceptance(
    tmp_path: Path, test_database_admin_url: str
) -> None:
    """Exercise Helpdesk's adapter against the actual Endpoint factory and WSS agent."""

    provider_database = await _disposable_endpoint_postgres(test_database_admin_url)
    provider = provider_database.provider
    async with provider() as session:
        client = ServiceClient(id=uuid4(), client_identifier="helpdesk-acceptance", display_name="Helpdesk acceptance")
        device = Device(id=uuid4(), device_identifier="acceptance-device", display_name="Acceptance device")
        session.add_all((client, device))
        await session.flush()
        session.add(
            DeviceCredential(
                id=uuid4(), device_id=device.id, credential_identifier="acceptance-device-credential",
                token_digest=device_token_digest(_DEVICE_TOKEN, _DEVICE_PEPPER), pending_token_digest=None,
                rotation_overlap_expires_at=None, expires_at=None, revoked_at=None,
            )
        )
        await session.commit()

    service_token = await _issue_acceptance_service_token(
        provider,
        service_client_id=client.id,
        credential_identifier="a" * 32,
    )

    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    settings = Settings(
        database_url=provider_database.database_url, public_base_url="https://endpoint.sosnadmin.local",
        device_token_pepper=_DEVICE_PEPPER, service_token_pepper=_SERVICE_PEPPER, session_secret=b"acceptance-session",
        allowed_agent_cidrs=(ipaddress.ip_network("127.0.0.0/8"),), allowed_admin_cidrs=(),
        trusted_proxy_cidrs=(ipaddress.ip_network("127.0.0.0/8"),), artifact_root=artifacts,
        endpoint_operations_api_enabled=True,
    )
    port = _free_port()
    server, task = await _start(create_app(settings, provider), port)
    base_url = f"http://127.0.0.1:{port}"
    adapter = ExternalEndpointHttpAdapter(
        base_url=base_url, service_token=service_token, ca_file="", timeout_seconds=2,
        allow_insecure_test_url=True, correlation_id_factory=lambda: "acceptance-correlation",
    )
    headers = {"Authorization": f"Bearer {service_token}", "X-Correlation-ID": "route-correlation"}
    request_body = {
        "schema_version": "endpoint_operation_create_v1", "capability": "context.diagnostic.collect",
        "parameters": {"reason": "Collect bounded diagnostic context"},
    }
    try:
        async with aiohttp.ClientSession() as http:
            unauthorized = await http.get(
                f"{base_url}/api/v1/devices/{device.id}",
                headers={"Authorization": "Bearer svc_" + "0" * 32 + "." + "A" * 43, "X-Correlation-ID": "route-correlation"},
            )
            assert unauthorized.status == 401
            device_response = await http.get(f"{base_url}/api/v1/devices/{device.id}", headers=headers)
            assert device_response.status == 200
            assert device_response.headers["X-Correlation-ID"] == "route-correlation"
            invalid_correlation = "invalid correlation value"
            invalid_response = await http.get(
                f"{base_url}/api/v1/devices/{device.id}",
                headers={"Authorization": f"Bearer {service_token}", "X-Correlation-ID": invalid_correlation},
            )
            assert invalid_response.status == 422
            assert invalid_response.headers.get("X-Correlation-ID") != invalid_correlation
            assert invalid_correlation not in await invalid_response.text()
            capabilities_response = await http.get(f"{base_url}/api/v1/devices/{device.id}/capabilities", headers=headers)
            assert capabilities_response.status == 200
            create_headers = headers | {"Idempotency-Key": "route-idempotency-0001"}
            created = await http.post(f"{base_url}/api/v1/devices/{device.id}/operations", headers=create_headers, json=request_body)
            replay = await http.post(f"{base_url}/api/v1/devices/{device.id}/operations", headers=create_headers, json=request_body)
            assert created.status == 201 and replay.status == 200
            created_body = await created.json()
            assert set(created_body["data"]) == {"operation", "result"}
            drift = await http.post(
                f"{base_url}/api/v1/devices/{device.id}/operations",
                headers=headers | {"Idempotency-Key": "route-idempotency-0002"},
                json=request_body | {"unexpected": True},
            )
            assert drift.status == 422

        assert (await adapter.read_device(EndpointDeviceRef(external_id=str(device.id)))).device.external_id == str(device.id)
        capabilities = await adapter.list_capabilities(EndpointDeviceRef(external_id=str(device.id)))
        assert capabilities.device.external_id == str(device.id)
        missing = await adapter.read_device(EndpointDeviceRef(external_id=str(uuid4())))
        assert missing.status == "not_found"
        adapter_created = await adapter.create_operation(
            EndpointDeviceRef(external_id=str(device.id)),
            EndpointOperationCreateRequest(
                schema_version="endpoint_operation_create_v1", capability="context.diagnostic.collect",
                parameters={},
            ),
            idempotency_key="adapter-idempotency-0001",
        )
        assert adapter_created.status == "queued"

        async with websockets.connect(
            f"ws://127.0.0.1:{port}/agent/v1/connect",
            additional_headers={"Authorization": f"Bearer {_DEVICE_TOKEN}", "X-Forwarded-Proto": "https", "X-Forwarded-For": "127.0.0.1"},
        ) as websocket:
            await websocket.send(json.dumps(_agent_hello(str(device.id))))
            assert json.loads(await websocket.recv())["kind"] == "gateway_hello"
            sequence = await _complete_next_command(websocket, device_id=str(device.id), sequence=2)
            await _complete_next_command(websocket, device_id=str(device.id), sequence=sequence)

        completed = await adapter.read_operation(adapter_created.operation)
        async with aiohttp.ClientSession() as http:
            raw_completed = await http.get(
                f"{base_url}/api/v1/operations/{adapter_created.operation.external_id}", headers=headers
            )
            raw_completed_body = await raw_completed.json()
        assert completed.status == "succeeded", json.dumps(raw_completed_body, sort_keys=True)
        assert completed.safe_result is not None
        assert completed.safe_result.processes[0].name == "acceptance-safe-process"
    finally:
        await _stop(server, task)
        await provider_database.close()


class _FacadeAccess:
    async def require_ticket_operation_access(self, *, actor: object, ticket_id: str) -> None:
        assert getattr(actor, "actor_id", None) == "support-acceptance"
        assert ticket_id


@pytest.mark.asyncio
@pytest.mark.cross_repo_acceptance
@pytest.mark.db_cleanup("observer_diagnostics")
async def test_helpdesk_facade_to_real_endpoint_gateway_creates_one_evidence(
    tmp_path: Path, test_database_admin_url: str, test_engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Full durable Helpdesk facade → provider → WSS → evidence vertical slice."""

    provider_database = await _disposable_endpoint_postgres(test_database_admin_url)
    provider = provider_database.provider
    async with provider() as session:
        client = ServiceClient(id=uuid4(), client_identifier="helpdesk-facade", display_name="Helpdesk facade")
        device = Device(id=uuid4(), device_identifier="facade-device", display_name="Facade device")
        session.add_all((client, device))
        await session.flush()
        session.add(
            DeviceCredential(
                id=uuid4(), device_id=device.id, credential_identifier="facade-device-credential",
                token_digest=device_token_digest(_DEVICE_TOKEN, _DEVICE_PEPPER), pending_token_digest=None,
                rotation_overlap_expires_at=None, expires_at=None, revoked_at=None,
            )
        )
        await session.commit()

    service_token = await _issue_acceptance_service_token(
        provider,
        service_client_id=client.id,
        credential_identifier="b" * 32,
    )
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    settings = Settings(
        database_url=provider_database.database_url, public_base_url="https://endpoint.sosnadmin.local",
        device_token_pepper=_DEVICE_PEPPER, service_token_pepper=_SERVICE_PEPPER, session_secret=b"facade-session",
        allowed_agent_cidrs=(ipaddress.ip_network("127.0.0.0/8"),), allowed_admin_cidrs=(),
        trusted_proxy_cidrs=(ipaddress.ip_network("127.0.0.0/8"),), artifact_root=artifacts,
        endpoint_operations_api_enabled=True,
    )
    port = _free_port()
    server, task = await _start(create_app(settings, provider), port)
    adapter = ExternalEndpointHttpAdapter(
        base_url=f"http://127.0.0.1:{port}", service_token=service_token, ca_file="",
        timeout_seconds=2, allow_insecure_test_url=True, correlation_id_factory=lambda: "facade-correlation",
    )
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid4())
    original_ticket_status = "in_progress"

    try:
        async with session_factory() as session:
            session.add(
                Ticket(
                    ticket_id=ticket_id,
                    device_id="helpdesk-local-device",
                    title="Endpoint acceptance",
                    description="Endpoint facade acceptance",
                    status=original_ticket_status,
                    requester_id="acceptance-requester",
                )
            )
            await session.commit()

        mapping = await EndpointDeviceReferenceService(adapter, session_factory).assign_verified_mapping(
            ticket_id=ticket_id, endpoint_device_ref=str(device.id)
        )
        assert mapping.status == "resolved"
        facade = EndpointDiagnosticOperationService(
            access_service=_FacadeAccess(),
            device_resolver=EndpointDeviceReferenceService(adapter, session_factory),
            store=SqlAlchemyEndpointDiagnosticOperationStore(session_factory),
        )
        actor = SimpleNamespace(actor_id="support-acceptance", actor_role="support")
        request = EndpointDiagnosticOperationRequest(ticket_id=ticket_id, idempotency_key="facade-caller-key-0001")
        local_operation = await facade.create(actor=actor, request=request)
        assert await facade.create(actor=actor, request=request) == local_operation

        clock = [datetime.now(UTC) + timedelta(minutes=1)]
        reconciler = EndpointOperationReconciler(
            endpoint_port=adapter,
            store=SqlAlchemyEndpointOperationReconcileStore(session_factory),
            mode="external",
            diagnostic_execution_mode="endpoint",
            owner="facade-acceptance",
            now=lambda: clock[0],
        )
        assert await reconciler.reconcile_once(limit=1) == 1
        async with websockets.connect(
            f"ws://127.0.0.1:{port}/agent/v1/connect",
            additional_headers={"Authorization": f"Bearer {_DEVICE_TOKEN}", "X-Forwarded-Proto": "https", "X-Forwarded-For": "127.0.0.1"},
        ) as websocket:
            await websocket.send(json.dumps(_agent_hello(str(device.id))))
            assert json.loads(await websocket.recv())["kind"] == "gateway_hello"
            await _complete_next_command(websocket, device_id=str(device.id), sequence=2)

        clock[0] += timedelta(seconds=10)
        assert await reconciler.reconcile_once(limit=1) == 1
        assert await reconciler.reconcile_once(limit=1) == 0
        async with session_factory() as session:
            ticket = await session.get(Ticket, ticket_id)
            operation = await session.get(Operation, local_operation.operation_id)
            link = (
                await session.execute(
                    select(EndpointOperationLink).where(
                        EndpointOperationLink.operation_id == local_operation.operation_id
                    )
                )
            ).scalar_one()
            diagnostic_step = await session.get(DiagnosticStep, link.diagnostic_step_id)
            diagnostic_session = await session.get(DiagnosticSession, link.diagnostic_session_id)
            evidence = list(
                (await session.execute(
                    select(DiagnosticEvidence).where(
                        DiagnosticEvidence.ticket_id == ticket_id,
                        DiagnosticEvidence.source_type == "endpoint_platform",
                    )
                )).scalars()
            )

        async with provider() as session:
            remote_operations = list(
                (await session.execute(
                    select(EndpointOperation).where(
                        EndpointOperation.requested_by_service_client_id == client.id,
                        EndpointOperation.idempotency_key == link.create_idempotency_key,
                    )
                )).scalars()
            )
        assert len(evidence) == 1
        assert ticket is not None and ticket.status == original_ticket_status
        assert operation is not None and operation.status == "succeeded"
        assert diagnostic_step is not None and diagnostic_step.status == "completed"
        assert diagnostic_session is not None and diagnostic_session.status == "completed"
        assert link.endpoint_operation_ref is not None
        assert link.safe_result_snapshot_json is not None
        assert link.last_error_code is None
        assert len(remote_operations) == 1
        assert remote_operations[0].id == UUID(link.endpoint_operation_ref)
        assert remote_operations[0].correlation is None
        assert evidence[0].source_type == "endpoint_platform"
        assert evidence[0].source_id == link.endpoint_operation_ref
        assert evidence[0].normalized_payload == link.safe_result_snapshot_json
        assert evidence[0].normalized_payload["processes"][0]["name"] == "acceptance-safe-process"
    finally:
        await _stop(server, task)
        await provider_database.close()
