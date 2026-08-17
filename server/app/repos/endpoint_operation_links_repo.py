"""Persistence helpers for safe Endpoint operation linkage only."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import TypeAdapter

from app.db.models import EndpointOperationLink
from domain_ports.endpoint import EndpointDeviceRef, OpaqueEndpointRef


_OPAQUE_ENDPOINT_REF = TypeAdapter(OpaqueEndpointRef)


class EndpointOperationLinkConflict(ValueError):
    """A caller attempted to reuse an idempotency key for another operation."""


class EndpointOperationLinksRepo:
    """Exact link storage; this repository performs neither HTTP nor dispatch."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_operation_id(self, operation_id: str) -> EndpointOperationLink | None:
        result = await self.session.execute(
            select(EndpointOperationLink).where(EndpointOperationLink.operation_id == operation_id)
        )
        return result.scalar_one_or_none()

    async def get_by_idempotency_key(self, key: str) -> EndpointOperationLink | None:
        result = await self.session.execute(
            select(EndpointOperationLink).where(EndpointOperationLink.create_idempotency_key == key)
        )
        return result.scalar_one_or_none()

    async def get_by_endpoint_operation_ref(self, ref: str) -> EndpointOperationLink | None:
        result = await self.session.execute(
            select(EndpointOperationLink).where(EndpointOperationLink.endpoint_operation_ref == ref)
        )
        return result.scalar_one_or_none()

    async def create_pending(
        self,
        *,
        operation_id: str,
        endpoint_device_ref: str,
        create_idempotency_key: str,
        next_attempt_at: datetime,
        diagnostic_session_id: str | None = None,
        diagnostic_step_id: str | None = None,
    ) -> EndpointOperationLink:
        """Create once, or return the exact matching idempotent link."""

        device_ref = EndpointDeviceRef(external_id=endpoint_device_ref).external_id
        idempotency_key = _OPAQUE_ENDPOINT_REF.validate_python(create_idempotency_key)
        if next_attempt_at.tzinfo is None or next_attempt_at.utcoffset() is None:
            raise ValueError("next_attempt_at must be timezone-aware")
        existing_by_operation = await self.get_by_operation_id(operation_id)
        existing_by_key = await self.get_by_idempotency_key(idempotency_key)
        if existing_by_operation is not None:
            if existing_by_operation.create_idempotency_key != create_idempotency_key:
                raise EndpointOperationLinkConflict("operation link already has another idempotency key")
            return existing_by_operation
        if existing_by_key is not None:
            if existing_by_key.operation_id != operation_id:
                raise EndpointOperationLinkConflict("idempotency key already belongs to another operation")
            return existing_by_key

        link = EndpointOperationLink(
            link_id=str(uuid.uuid4()),
            operation_id=operation_id,
            endpoint_device_ref=device_ref,
            capability_code="context.diagnostic.collect",
            create_idempotency_key=idempotency_key,
            remote_status="create_pending",
            diagnostic_session_id=diagnostic_session_id,
            diagnostic_step_id=diagnostic_step_id,
            next_attempt_at=next_attempt_at,
        )
        self.session.add(link)
        await self.session.flush()
        return link
