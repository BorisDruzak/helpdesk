from datetime import datetime, timezone
import importlib.util
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest

pytestmark = pytest.mark.no_db


@pytest.mark.asyncio
async def test_reconcile_resume_does_not_resubmit_module():
    assert importlib.util.find_spec("app.services.endpoint_tool_reconciler") is not None
    from app.services.endpoint_tool_reconciler import EndpointToolReconciler
    from domain_ports.endpoint import EndpointNotFound
    modules = SimpleNamespace(create_module_operation=AsyncMock(), read_module_operation=AsyncMock(return_value=EndpointNotFound()))
    worker = EndpointToolReconciler(endpoint_port=None, modules_port=modules, session_factory=None)
    run = SimpleNamespace(run_id=str(uuid4()), ticket_id=str(uuid4()), device_ref=str(uuid4()),
        request=SimpleNamespace(kind="module"), remote_ref=str(uuid4()), status="running", attempt_count=0)
    projection = await worker.project(run)
    modules.create_module_operation.assert_not_awaited()
    assert projection.status == "failed" and projection.error_code == "endpoint_result_expired"


@pytest.mark.asyncio
async def test_context_identity_mismatch_is_not_committed_as_success():
    from app.services.endpoint_tool_reconciler import EndpointToolReconciler
    from domain_ports.endpoint_context import EndpointCollectionDetails, EndpointContextCollection
    from domain_ports.endpoint_tools import ToolRunRequestV1
    collection = EndpointContextCollection(id=uuid4(), device_id=uuid4(), profile="network_v1", status="completed",
        requested_at=datetime.now(timezone.utc), result_received_at=None, completed_at=None, failure_code=None)
    endpoint = SimpleNamespace(read_context_collection=AsyncMock(return_value=EndpointCollectionDetails(collection=collection, snapshot=None)))
    worker = EndpointToolReconciler(endpoint_port=endpoint, modules_port=None, session_factory=None)
    run = SimpleNamespace(run_id=str(uuid4()), device_ref=str(uuid4()), request=ToolRunRequestV1(kind="context_collection", profile="inventory_v1"), remote_ref=str(collection.id))
    result = await worker.project(run)
    assert result.status == "failed" and result.safe_result is None


def test_legacy_claim_predicate_excludes_new_ownership_and_module_residue():
    from app.services.endpoint_operation_reconciler import legacy_endpoint_claim_predicates
    predicates = " ".join(str(p) for p in legacy_endpoint_claim_predicates())
    assert "endpoint_tool_runs" in predicates and "NOT" in predicates
    assert "capability_code" in predicates


@pytest.mark.asyncio
async def test_module_result_for_another_target_is_rejected():
    from app.services.endpoint_tool_reconciler import EndpointToolReconciler
    from domain_ports.endpoint_module_contracts_generated import ModuleOperationDetailV1,EndpointRecipeModuleSpecV1
    from domain_ports.endpoint_tools import ToolRunRequestV1
    from tests.test_endpoint_modules_adapter import operation_payload,DEVICE
    payload=operation_payload()
    recipe=EndpointRecipeModuleSpecV1(schema_version="endpoint_recipe_module_v1",module_key="network.dns",supported_platforms=["windows_amd64"],
        inputs=[{"name":"host","value_type":"string"}],steps=[{"step_id":"dns","capability":"dns.resolve","parameters":{"target":{"kind":"input","name":"host"},"family":{"kind":"literal","value":"ipv4"}}}])
    request=ToolRunRequestV1(kind="module",module_key="network.dns",version="1.0.0",recipe=recipe,inputs={"host":"expected.example.test"})
    modules=SimpleNamespace(read_module_operation=AsyncMock(return_value=ModuleOperationDetailV1.model_validate(payload)))
    worker=EndpointToolReconciler(endpoint_port=None,modules_port=modules,session_factory=None)
    run=SimpleNamespace(run_id=str(uuid4()),device_ref=DEVICE,remote_ref=DEVICE,request=request)
    result=await worker.project(run)
    assert result.status=="failed" and result.safe_result is None


@pytest.mark.asyncio
async def test_terminal_context_without_snapshot_remains_incomplete():
    from app.services.endpoint_tool_reconciler import EndpointToolReconciler
    from domain_ports.endpoint_context import EndpointContextCollection
    from domain_ports.endpoint_tools import ToolRunRequestV1
    device = uuid4()
    collection = EndpointContextCollection(id=uuid4(), device_id=device, profile="inventory_v1", status="completed",
        requested_at=datetime.now(timezone.utc), result_received_at=None, completed_at=None, failure_code=None)
    endpoint = SimpleNamespace(request_context_collection=AsyncMock(return_value=collection))
    worker = EndpointToolReconciler(endpoint_port=endpoint, modules_port=None, session_factory=None)
    run = SimpleNamespace(run_id=str(uuid4()), device_ref=str(device), request=ToolRunRequestV1(kind="context_collection", profile="inventory_v1"), remote_ref=None)
    result = await worker.project(run)
    assert result.status == "running" and result.remote_ref == str(collection.id) and result.safe_result is None


@pytest.mark.asyncio
async def test_creation_acceptance_is_not_module_completion():
    from app.services.endpoint_tool_reconciler import EndpointToolReconciler
    from domain_ports.endpoint_module_contracts_generated import ModuleOperationV1
    device = uuid4()
    now = datetime.now(timezone.utc)
    result = ModuleOperationV1(schema_version="endpoint_module_operation_v1", operation_id=uuid4(), device_id=device,
        module_key="test.dns", version="1.0.0", status="succeeded", created_at=now, deadline_at=now)
    modules = SimpleNamespace(create_module_operation=AsyncMock(return_value=result))
    worker = EndpointToolReconciler(endpoint_port=None, modules_port=modules, session_factory=None)
    run = SimpleNamespace(run_id=str(uuid4()), device_ref=str(device), request=SimpleNamespace(kind="module", module_key="test.dns", version="1.0.0", inputs={}), remote_ref=None)
    projection = await worker.project(run)
    assert projection.status == "running" and projection.safe_result is None
