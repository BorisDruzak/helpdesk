"""Persistence for Helpdesk-owned Endpoint Module operation links only."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EndpointModuleOperationLink
from domain_ports.endpoint_modules import EndpointModuleRef, EndpointModuleVersionRef


class EndpointModuleOperationLinkConflict(ValueError):
    """An immutable module operation identity conflicts with an existing link."""


class EndpointModuleOperationLinksRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_operation_id(self, operation_id: str) -> EndpointModuleOperationLink | None:
        return (await self.session.execute(
            select(EndpointModuleOperationLink).where(EndpointModuleOperationLink.operation_id == operation_id)
        )).scalar_one_or_none()

    async def create_pending(
        self, *, operation_id: str, endpoint_device_ref: str, module_key: str, module_version: str,
        inputs: dict[str, str | int], create_idempotency_key: str, caller_actor_id: str | None = None,
        caller_idempotency_key: str | None = None, next_attempt_at: datetime,
    ) -> EndpointModuleOperationLink:
        module = EndpointModuleRef(module_key=module_key)
        version = EndpointModuleVersionRef(module=module, version=module_version)
        if not endpoint_device_ref or len(endpoint_device_ref) > 128:
            raise ValueError("endpoint device ref must be a bounded opaque value")
        if not create_idempotency_key or len(create_idempotency_key) > 128:
            raise ValueError("create idempotency key must be bounded")
        if bool(caller_actor_id) != bool(caller_idempotency_key):
            raise ValueError("caller idempotency identity must be complete")
        if next_attempt_at.tzinfo is None or next_attempt_at.utcoffset() is None:
            raise ValueError("next_attempt_at must be timezone-aware")
        values = {
            "link_id": str(uuid.uuid4()), "operation_id": operation_id,
            "endpoint_device_ref": endpoint_device_ref, "module_key": module.module_key,
            "module_version": version.version, "inputs_snapshot_json": dict(inputs),
            "create_idempotency_key": create_idempotency_key, "caller_actor_id": caller_actor_id,
            "caller_idempotency_key": caller_idempotency_key, "remote_status": "create_pending",
            "next_attempt_at": next_attempt_at,
        }
        statement = insert(EndpointModuleOperationLink).values(**values).on_conflict_do_nothing(
            index_elements=["create_idempotency_key"]
        ).returning(EndpointModuleOperationLink)
        try:
            async with self.session.begin_nested():
                created = (await self.session.execute(statement)).scalar_one_or_none()
        except IntegrityError:
            created = None
        if created is not None:
            return created
        existing = await self.get_by_operation_id(operation_id)
        if existing is not None and self._matches(existing, values):
            return existing
        raise EndpointModuleOperationLinkConflict("module operation link immutable identity conflicts")

    @staticmethod
    def _matches(link: EndpointModuleOperationLink, values: dict[str, object]) -> bool:
        return all(getattr(link, field) == values[field] for field in (
            "operation_id", "endpoint_device_ref", "module_key", "module_version",
            "inputs_snapshot_json", "create_idempotency_key", "caller_actor_id", "caller_idempotency_key",
        ))
