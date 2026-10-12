"""Resume immutable Endpoint runs without resubmitting accepted remote intents."""
import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

from pydantic import ValidationError
from app.repos.endpoint_tool_runs_repo import EndpointToolRunsRepo, ToolRunProjection, remote_tool_key
from domain_ports.endpoint import (
    EndpointDeviceRef, EndpointOperationRef, EndpointNotFound, EndpointUnavailable,
    EndpointUnauthorized, EndpointForbidden, EndpointOperationProjection,
    EndpointOperationCreateRequest, EndpointOperationCorrelation, EndpointDiagnosticParameters,
)
from domain_ports.endpoint_context import EndpointContextCollection, EndpointCollectionDetails
from domain_ports.endpoint_module_contracts_generated import ModuleOperationCreateV1, ModuleOperationV1, ModuleOperationDetailV1
from endpoint_adapter.modules_wire import validate_module_projection, validate_result_request

_LOG = logging.getLogger(__name__)


class EndpointToolReconciler:
    def __init__(self, *, endpoint_port, modules_port, session_factory, owner="helpdesk-tools"):
        self.endpoint, self.modules, self.sessions, self.owner = endpoint_port, modules_port, session_factory, owner

    async def run_once(self, limit=10, now=None):
        processed = 0
        for _ in range(max(0, min(limit, 100))):
            clock = now or datetime.now(timezone.utc)
            async with self.sessions() as session:
                async with session.begin():
                    claims = await EndpointToolRunsRepo(session).claim_ready(owner=self.owner, limit=1, now=clock)
            if not claims: break
            claim = claims[0]
            try:
                projection = await self.project(claim.run)
            except (ValueError, ValidationError):
                projection = ToolRunProjection("failed", error_code="endpoint_invalid_projection")
            except Exception:
                # Neither exception text nor raw provider response enters logs/evidence.
                _LOG.warning("endpoint_tool_reconcile_unexpected")
                projection = ToolRunProjection(claim.run.status, error_code="endpoint_unavailable", retry_seconds=min(300, 5 * 2 ** min(claim.run.attempt_count, 6)))
            async with self.sessions() as session:
                async with session.begin():
                    await EndpointToolRunsRepo(session).commit_projection(claim, projection, now=now or datetime.now(timezone.utc))
            processed += 1
        return processed

    def _failure(self, run, result):
        if isinstance(result, (EndpointUnavailable, EndpointUnauthorized, EndpointForbidden)):
            return ToolRunProjection(run.status, error_code=result.code, retry_seconds=60)
        code = "endpoint_result_expired" if isinstance(result, EndpointNotFound) and run.remote_ref else getattr(result, "code", "endpoint_invalid_projection")
        return ToolRunProjection("failed", error_code=code)

    async def project(self, run):
        device = EndpointDeviceRef(external_id=run.device_ref)
        request = run.request
        key = remote_tool_key(request.kind, run.run_id)
        if request.kind == "module":
            if run.remote_ref:
                result = await self.modules.read_module_operation(EndpointOperationRef(external_id=run.remote_ref))
                expected = ModuleOperationDetailV1
            else:
                result = await self.modules.create_module_operation(device,
                    ModuleOperationCreateV1(schema_version="endpoint_module_operation_create_v1", module_key=request.module_key, version=request.version, inputs=request.inputs),
                    idempotency_key=key, correlation_id=f"helpdesk-tool:{run.run_id}")
                expected = ModuleOperationV1
            if not isinstance(result, expected): return self._failure(run, result)
            if str(result.device_id) != run.device_ref or result.module_key != request.module_key or result.version != request.version or run.remote_ref and str(result.operation_id) != run.remote_ref:
                return ToolRunProjection("failed", error_code="endpoint_invalid_projection")
            validate_module_projection(result)
            if isinstance(result, ModuleOperationDetailV1):
                if [s.capability for s in result.steps] != [s.capability for s in request.recipe.steps]:
                    return ToolRunProjection("failed", error_code="endpoint_invalid_projection")
                try:
                    for step, recipe_step in zip(result.steps, request.recipe.steps):
                        validate_result_request(step, recipe_step, request.inputs)
                except ValueError:
                    return ToolRunProjection("failed", error_code="endpoint_invalid_projection")
                if result.status == "succeeded" and any(s.status != "succeeded" or s.safe_result is None for s in result.steps):
                    return ToolRunProjection("failed", remote_ref=str(result.operation_id), error_code="endpoint_result_expired")
                snapshot = result.model_dump(mode="json")
            else:
                snapshot = None
            # Creation acknowledges an intent; poll detail even if the returned parent is terminal.
            status = result.status if snapshot is not None else ("running" if result.status in {"succeeded", "failed", "expired", "canceled"} else result.status)
            return ToolRunProjection(status, str(result.operation_id), snapshot)
        if request.kind == "context_collection":
            if run.remote_ref:
                result = await self.endpoint.read_context_collection(UUID(run.remote_ref))
                if not isinstance(result, EndpointCollectionDetails): return self._failure(run, result)
                collection, snapshot = result.collection, result.snapshot
                if str(collection.id) != run.remote_ref: return ToolRunProjection("failed", error_code="endpoint_invalid_projection")
            else:
                collection = await self.endpoint.request_context_collection(device, request.profile, idempotency_key=key)
                if not isinstance(collection, EndpointContextCollection): return self._failure(run, collection)
                snapshot = None
            if str(collection.device_id) != run.device_ref or collection.profile != request.profile:
                return ToolRunProjection("failed", error_code="endpoint_invalid_projection")
            state = {"requested": "queued", "queued": "queued", "delivered": "delivered", "collecting": "running", "result_received": "running", "validated": "running", "completed": "succeeded", "failed": "failed", "expired": "expired"}[collection.status]
            if state == "succeeded" and snapshot is None:
                state = "running" if not run.remote_ref else "failed"
            error = "endpoint_result_expired" if collection.status == "completed" and run.remote_ref and snapshot is None else collection.failure_code
            return ToolRunProjection(state, str(collection.id), snapshot.model_dump(mode="json") if snapshot else None, error)
        if run.remote_ref:
            result = await self.endpoint.read_operation(EndpointOperationRef(external_id=run.remote_ref))
        else:
            result = await self.endpoint.create_operation(device, EndpointOperationCreateRequest(parameters=EndpointDiagnosticParameters(),
                correlation=EndpointOperationCorrelation(source_entity_id=run.ticket_id, request_id=UUID(run.run_id))), idempotency_key=key)
        if not isinstance(result, EndpointOperationProjection): return self._failure(run, result)
        if result.device.external_id != run.device_ref or run.remote_ref and result.operation.external_id != run.remote_ref:
            return ToolRunProjection("failed", error_code="endpoint_invalid_projection")
        if result.correlation is None or result.correlation.request_id != UUID(run.run_id) or result.correlation.source_entity_id != run.ticket_id:
            return ToolRunProjection("failed", error_code="endpoint_invalid_projection")
        status = result.status
        if status == "succeeded" and result.safe_result is None: status = "failed"
        return ToolRunProjection(status, result.operation.external_id, result.safe_result.model_dump(mode="json") if result.safe_result else None,
            "endpoint_result_expired" if result.status == "succeeded" and result.safe_result is None else None)


class EndpointToolReconcilerRunner:
    def __init__(self, reconciler, interval_seconds=2, batch_size=10):
        self.reconciler, self.interval, self.batch_size, self.task = reconciler, interval_seconds, batch_size, None

    def start(self):
        if self.task is None: self.task = asyncio.create_task(self._run())

    async def _run(self):
        while True:
            try: await self.reconciler.run_once(self.batch_size)
            except asyncio.CancelledError: raise
            except Exception: _LOG.warning("endpoint_tool_worker_iteration_failed")
            await asyncio.sleep(self.interval)

    async def stop(self):
        if self.task:
            self.task.cancel()
            try: await self.task
            except asyncio.CancelledError: pass
            self.task = None
