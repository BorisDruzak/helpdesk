"""Repository for runtime operation dependency links."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import OperationDependency


class OperationDependenciesRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_dependency(
        self,
        *,
        operation_id: str,
        dependency_type: str,
        dependency_key: str,
        provider_id: Optional[str] = None,
        module_name: Optional[str] = None,
        current_version: Optional[str] = None,
        target_version: Optional[str] = None,
        version_constraint: Optional[str] = None,
        status: str = "pending",
        reason: Optional[str] = None,
        reason_code: Optional[str] = None,
        timeout_at: Optional[datetime] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> OperationDependency:
        dependency = OperationDependency(
            id=str(uuid.uuid4()),
            operation_id=operation_id,
            dependency_type=dependency_type,
            dependency_key=dependency_key,
            provider_id=provider_id,
            module_name=module_name,
            current_version=current_version,
            target_version=target_version,
            version_constraint=version_constraint,
            status=status,
            reason=reason,
            reason_code=reason_code,
            timeout_at=timeout_at,
            metadata_json=metadata or {},
        )
        self.session.add(dependency)
        await self.session.flush()
        return dependency

    async def get_for_operation(self, operation_id: str) -> list[OperationDependency]:
        result = await self.session.execute(
            select(OperationDependency)
            .where(OperationDependency.operation_id == operation_id)
            .order_by(OperationDependency.created_at.asc())
        )
        return list(result.scalars().all())

    async def get_by_dependency_operation_id(self, dependency_operation_id: str) -> list[OperationDependency]:
        result = await self.session.execute(
            select(OperationDependency).where(
                OperationDependency.dependency_operation_id == dependency_operation_id
            )
        )
        return list(result.scalars().all())

    async def list_timed_out(self, *, limit: int = 100) -> list[OperationDependency]:
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(OperationDependency)
            .where(
                and_(
                    OperationDependency.status.in_(["pending", "installing"]),
                    OperationDependency.timeout_at.isnot(None),
                    OperationDependency.timeout_at < now,
                )
            )
            .order_by(OperationDependency.timeout_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update_dependency(
        self,
        dependency_id: str,
        *,
        status: Optional[str] = None,
        dependency_operation_id: Optional[str] = None,
        reason: Optional[str] = None,
        reason_code: Optional[str] = None,
        resolved: bool = False,
        metadata: Optional[dict[str, Any]] = None,
        increment_resume_attempts: bool = False,
    ) -> bool:
        values: dict[str, Any] = {}
        if status is not None:
            values["status"] = status
        if dependency_operation_id is not None:
            values["dependency_operation_id"] = dependency_operation_id
        if reason is not None:
            values["reason"] = reason
        if reason_code is not None:
            values["reason_code"] = reason_code
        if resolved:
            values["resolved_at"] = datetime.now(timezone.utc)
        if metadata is not None:
            values["metadata_json"] = metadata
        if increment_resume_attempts:
            values["resume_attempts"] = OperationDependency.resume_attempts + 1
        if not values:
            return True
        result = await self.session.execute(
            update(OperationDependency).where(OperationDependency.id == dependency_id).values(**values)
        )
        return result.rowcount > 0
