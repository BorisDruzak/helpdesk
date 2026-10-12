"""Transactional immutable intents and leases. No network calls in transactions."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL

from sqlalchemy import select, or_
from app.db.models import EndpointToolRun, EndpointOperationLink, Operation, Ticket, DiagnosticSession, DiagnosticStep
from app.repos.operations_repo import OperationsRepo
from domain_ports.endpoint_tools import ToolRunRequestV1
from domain_ports.endpoint import EndpointDeviceRef

TERMINAL = frozenset({"succeeded", "failed", "canceled", "expired"})
CAPABILITIES = {"module": "endpoint.module.recipe", "context_collection": "endpoint.context.collection", "diagnostic": "context.diagnostic.collect"}


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def tool_run_id(actor, ticket, key):
    return str(uuid5(NAMESPACE_URL, canonical_json(["helpdesk-tool-v1", actor, ticket, key])))


def remote_tool_key(kind, run_id):
    prefix = {"module": "helpdesk-endpoint-module", "context_collection": "helpdesk-endpoint-context", "diagnostic": "helpdesk-endpoint-operation"}[kind]
    return f"{prefix}:{run_id}"


class ToolRunConflict(ValueError): pass


@dataclass(frozen=True)
class ToolRunStoredV1:
    run_id: str
    ticket_id: str
    actor_id: str
    device_ref: str
    request: ToolRunRequestV1
    status: str
    remote_ref: str | None
    safe_result: dict | None
    error_code: str | None
    created_at: datetime
    batch_id: str | None
    attempt_count: int


@dataclass(frozen=True)
class ToolRunClaim:
    run: ToolRunStoredV1
    lease_token: str


@dataclass(frozen=True)
class ToolRunProjection:
    status: str
    remote_ref: str | None = None
    safe_result: dict | None = None
    error_code: str | None = None
    retry_seconds: float = 2


class EndpointToolRunsRepo:
    def __init__(self, session): self.session = session

    @staticmethod
    def _stored(marker, link):
        return ToolRunStoredV1(marker.run_id, marker.ticket_id, marker.actor_id, link.endpoint_device_ref,
            ToolRunRequestV1.model_validate(marker.request_snapshot_json), link.remote_status,
            link.endpoint_collection_ref if marker.execution_kind == "context_collection" else link.endpoint_operation_ref,
            link.safe_result_snapshot_json, link.last_error_code, marker.created_at, marker.batch_id, link.attempt_count)

    async def get_authorized_run(self, run_id, ticket_id):
        row = (await self.session.execute(select(EndpointToolRun, EndpointOperationLink)
            .join(EndpointOperationLink, EndpointOperationLink.operation_id == EndpointToolRun.run_id)
            .where(EndpointToolRun.run_id == run_id, EndpointToolRun.ticket_id == ticket_id))).one_or_none()
        return self._stored(*row) if row else None

    async def list_runs(self, ticket_id, *, batch_id=None, limit=30):
        query = select(EndpointToolRun, EndpointOperationLink).join(EndpointOperationLink, EndpointOperationLink.operation_id == EndpointToolRun.run_id).where(EndpointToolRun.ticket_id == ticket_id)
        if batch_id: query = query.where(EndpointToolRun.batch_id == batch_id)
        rows = (await self.session.execute(query.order_by(EndpointToolRun.created_at.desc(), EndpointToolRun.run_id).limit(limit))).all()
        return [self._stored(*row) for row in rows]

    async def create_pending(self, request, *, actor_id, ticket_id, device_ref, caller_key, batch_id=None, actor_role="support"):
        request = ToolRunRequestV1.model_validate(request)
        if not isinstance(caller_key, str) or not 1 <= len(caller_key) <= 128 or any(ord(c) < 33 or ord(c) > 126 for c in caller_key):
            raise ValueError("invalid caller key")
        if not actor_id or len(actor_id) > 128: raise ValueError("invalid actor")
        device_ref = EndpointDeviceRef(external_id=device_ref).external_id
        # Serialize intents for this ticket, including concurrent browser replay.
        ticket = await self.session.get(Ticket, ticket_id, with_for_update=True)
        if ticket is None: raise LookupError("ticket not found")
        run_id = tool_run_id(actor_id, ticket_id, caller_key)
        snapshot = request.model_dump(mode="json")
        digest = hashlib.sha256(canonical_json(snapshot).encode()).hexdigest()
        existing = await self.session.get(EndpointToolRun, run_id)
        if existing:
            stored = await self.get_authorized_run(run_id, ticket_id)
            if existing.request_sha256 != digest or stored.device_ref != device_ref or existing.batch_id != batch_id:
                raise ToolRunConflict("idempotency key belongs to another immutable request")
            return stored
        now = datetime.now(timezone.utc)
        await OperationsRepo(self.session).create_operation(run_id, ticket.device_id, "endpoint_operation", actor_role,
            str(uuid4()), ticket_id=ticket_id, tool_name=CAPABILITIES[request.kind], phase="endpoint_create_pending")
        session_id = batch_id or str(uuid5(NAMESPACE_URL, f"helpdesk-tool-session:{run_id}"))
        if await self.session.get(DiagnosticSession, session_id) is None:
            self.session.add(DiagnosticSession(id=session_id, ticket_id=ticket_id, status="in_progress",
                trigger_source="endpoint_tools", started_by_user_id=actor_id[:100], started_at=now))
            await self.session.flush()
        self.session.add(DiagnosticStep(id=run_id, session_id=session_id, ticket_id=ticket_id,
            step_type=request.kind, provider_id="endpoint_platform", capability_id=CAPABILITIES[request.kind],
            operation_id=run_id, status="pending"))
        await self.session.flush()
        marker = EndpointToolRun(run_id=run_id, actor_id=actor_id, ticket_id=ticket_id, caller_key=caller_key,
            execution_kind=request.kind, request_snapshot_json=snapshot, request_sha256=digest, batch_id=batch_id, created_at=now)
        link = EndpointOperationLink(link_id=str(uuid4()), operation_id=run_id, endpoint_device_ref=device_ref,
            capability_code=CAPABILITIES[request.kind], create_idempotency_key=remote_tool_key(request.kind, run_id),
            correlation_ref=f"helpdesk-tool:{run_id}", remote_status="create_pending", next_attempt_at=now,
            module_key=request.module_key, module_version=request.version,
            module_spec_sha256=hashlib.sha256(canonical_json(snapshot["recipe"]).encode()).hexdigest() if request.recipe else None,
            module_inputs_snapshot_json=request.inputs if request.kind == "module" else None,
            safe_module_snapshot_json=snapshot["recipe"], context_profile=request.profile)
        link.diagnostic_session_id, link.diagnostic_step_id = session_id, run_id
        self.session.add_all([marker, link])
        await self.session.flush()
        return self._stored(marker, link)

    async def claim_ready(self, *, owner, limit, now, lease_seconds=30):
        if now.tzinfo is None: raise ValueError("aware lease time required")
        rows = (await self.session.execute(select(EndpointToolRun, EndpointOperationLink)
            .join(EndpointOperationLink, EndpointOperationLink.operation_id == EndpointToolRun.run_id)
            .where(EndpointOperationLink.remote_status.notin_(tuple(TERMINAL)), EndpointOperationLink.next_attempt_at <= now,
                or_(EndpointOperationLink.lease_until.is_(None), EndpointOperationLink.lease_until <= now))
            .order_by(EndpointOperationLink.next_attempt_at, EndpointToolRun.run_id).limit(min(max(limit, 0), 100))
            .with_for_update(of=EndpointOperationLink, skip_locked=True))).all()
        claims = []
        for marker, link in rows:
            token = f"{owner[:80]}:{uuid4()}"
            link.lease_owner, link.lease_until = token, now + timedelta(seconds=lease_seconds)
            claims.append(ToolRunClaim(self._stored(marker, link), token))
        await self.session.flush()
        return claims

    async def commit_projection(self, claim, projection, *, now):
        if projection.status not in TERMINAL | {"create_pending", "queued", "delivered", "acknowledged", "running"}:
            raise ValueError("invalid projection status")
        link = (await self.session.execute(select(EndpointOperationLink).where(EndpointOperationLink.operation_id == claim.run.run_id).with_for_update())).scalar_one_or_none()
        if link is None or link.lease_owner != claim.lease_token or link.remote_status in TERMINAL: return False
        ref_field = "endpoint_collection_ref" if claim.run.request.kind == "context_collection" else "endpoint_operation_ref"
        old_ref = getattr(link, ref_field)
        if projection.remote_ref is not None:
            if old_ref not in (None, projection.remote_ref): raise ToolRunConflict("remote reference changed")
            if len(projection.remote_ref) > 128: raise ValueError("unbounded reference")
            if ref_field == "endpoint_collection_ref": UUID(projection.remote_ref)
            setattr(link, ref_field, projection.remote_ref)
        if projection.safe_result is not None:
            if len(canonical_json(projection.safe_result).encode()) > 1048576: raise ValueError("unbounded projection")
            # Remote codecs validate before this write. Keep the last accepted snapshot on TTL/not-found.
            link.safe_result_snapshot_json = projection.safe_result
        progress = {"create_pending": 0, "queued": 1, "delivered": 2, "acknowledged": 3, "running": 4}
        if projection.status not in TERMINAL and progress[projection.status] < progress.get(link.remote_status, 0):
            projection = ToolRunProjection(link.remote_status, projection.remote_ref, projection.safe_result, projection.error_code, projection.retry_seconds)
        link.remote_status, link.last_error_code = projection.status, projection.error_code
        link.next_attempt_at = now + timedelta(seconds=projection.retry_seconds)
        link.last_synced_at, link.lease_owner, link.lease_until = now, None, None
        if projection.error_code: link.attempt_count += 1
        operation = await self.session.get(Operation, claim.run.run_id, with_for_update=True)
        operation.status = {"create_pending": "queued", "queued": "queued", "delivered": "sent", "acknowledged": "accepted", "expired": "timed_out"}.get(projection.status, projection.status)
        operation.phase, operation.error_code = f"endpoint_{projection.status}", projection.error_code
        if projection.status in TERMINAL: operation.finished_at = now
        if link.diagnostic_step_id:
            step = await self.session.get(DiagnosticStep, link.diagnostic_step_id)
            if step is not None:
                step.status = "completed" if projection.status == "succeeded" else "failed" if projection.status in TERMINAL else "running" if projection.status == "running" else "pending"
                step.error_code, step.external_ref = projection.error_code, projection.remote_ref or old_ref
                if projection.status in TERMINAL: step.finished_at = now
        if link.diagnostic_session_id:
            # The current state is not autoflushed in every configured session.
            await self.session.flush()
            statuses = list((await self.session.execute(select(EndpointOperationLink.remote_status)
                .where(EndpointOperationLink.diagnostic_session_id == link.diagnostic_session_id))).scalars())
            if statuses and all(s in TERMINAL for s in statuses):
                diagnostic_session = await self.session.get(DiagnosticSession, link.diagnostic_session_id, with_for_update=True)
                diagnostic_session.status = "completed" if all(s == "succeeded" for s in statuses) else "partial" if "succeeded" in statuses else "failed"
                diagnostic_session.finished_at = now
        await self.session.flush()
        return True
