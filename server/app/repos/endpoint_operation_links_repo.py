"""Persistence helpers for safe Endpoint operation linkage only."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
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
        values = {
            "link_id": str(uuid.uuid4()),
            "operation_id": operation_id,
            "endpoint_device_ref": device_ref,
            "capability_code": "context.diagnostic.collect",
            "create_idempotency_key": idempotency_key,
            "remote_status": "create_pending",
            "diagnostic_session_id": diagnostic_session_id,
            "diagnostic_step_id": diagnostic_step_id,
            "next_attempt_at": next_attempt_at,
        }
        statement = (
            insert(EndpointOperationLink)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["create_idempotency_key"])
            .returning(EndpointOperationLink)
        )
        try:
            async with self.session.begin_nested():
                created = (await self.session.execute(statement)).scalar_one_or_none()
        except IntegrityError as exc:
            if self._constraint_name(exc) != "uq_endpoint_operation_links_operation_id":
                raise
            created = None
        if created is not None:
            return created

        existing_by_operation = await self.get_by_operation_id(operation_id)
        existing_by_key = await self.get_by_idempotency_key(idempotency_key)
        for existing in (existing_by_operation, existing_by_key):
            if existing is not None and self._matches_immutable_identity(
                existing,
                operation_id=operation_id,
                endpoint_device_ref=device_ref,
                create_idempotency_key=idempotency_key,
            ):
                return existing
        raise EndpointOperationLinkConflict(
            "Endpoint operation link immutable identity conflicts with an existing link"
        )

    @staticmethod
    def _matches_immutable_identity(
        link: EndpointOperationLink,
        *,
        operation_id: str,
        endpoint_device_ref: str,
        create_idempotency_key: str,
    ) -> bool:
        return (
            link.operation_id == operation_id
            and link.endpoint_device_ref == endpoint_device_ref
            and link.capability_code == "context.diagnostic.collect"
            and link.create_idempotency_key == create_idempotency_key
        )

    @staticmethod
    def _constraint_name(exc: IntegrityError) -> str | None:
        diagnostics = getattr(getattr(exc, "orig", None), "diag", None)
        return getattr(diagnostics, "constraint_name", None)
