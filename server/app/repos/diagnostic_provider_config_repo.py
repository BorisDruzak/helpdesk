from __future__ import annotations

from datetime import datetime, timezone
import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    DiagnosticProvider,
    DiagnosticProviderAudit,
    DiagnosticProviderConfig,
    DiagnosticProviderCredentialRef,
)


def _uuid() -> str:
    return str(uuid.uuid4())


class DiagnosticProviderConfigRepo:
    """Persistence helpers for diagnostic provider configuration."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert_provider(
        self,
        *,
        provider_id: str,
        provider_type: str,
        title: str | None = None,
        description: str | None = None,
        source: str = "configured",
        status: str = "available",
        config_schema: dict[str, Any] | None = None,
        metadata_json: dict[str, Any] | None = None,
    ) -> DiagnosticProvider:
        item = await self.session.get(DiagnosticProvider, provider_id)
        if item is None:
            item = DiagnosticProvider(
                provider_id=provider_id,
                provider_type=provider_type,
                title=title or provider_id,
                description=description,
                source=source,
                status=status,
                config_schema=config_schema or {},
                metadata_json=metadata_json or {},
            )
            self.session.add(item)
        else:
            item.provider_type = provider_type
            item.title = title or item.title or provider_id
            item.description = description
            item.source = source
            item.status = status
            item.config_schema = config_schema or item.config_schema or {}
            item.metadata_json = metadata_json or item.metadata_json or {}
            item.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        return item

    async def get_config(self, provider_id: str) -> DiagnosticProviderConfig | None:
        return (
            await self.session.execute(
                select(DiagnosticProviderConfig).where(DiagnosticProviderConfig.provider_id == provider_id)
            )
        ).scalar_one_or_none()

    async def list_configs(self) -> list[DiagnosticProviderConfig]:
        result = await self.session.execute(
            select(DiagnosticProviderConfig).order_by(DiagnosticProviderConfig.provider_id.asc())
        )
        return list(result.scalars())

    async def upsert_config(
        self,
        *,
        provider_id: str,
        provider_type: str,
        integration_key: str | None,
        enabled: bool,
        status: str,
        config_json: dict[str, Any],
        redaction_json: dict[str, Any] | None = None,
        health_json: dict[str, Any] | None = None,
    ) -> tuple[DiagnosticProviderConfig, dict[str, Any] | None]:
        existing = await self.get_config(provider_id)
        before = self.config_to_dict(existing) if existing is not None else None
        if existing is None:
            existing = DiagnosticProviderConfig(
                id=_uuid(),
                provider_id=provider_id,
                provider_type=provider_type,
                integration_key=integration_key,
                enabled=enabled,
                status=status,
                config_json=config_json,
                redaction_json=redaction_json or {},
                health_json=health_json or {},
            )
            self.session.add(existing)
        else:
            existing.provider_type = provider_type
            existing.integration_key = integration_key
            existing.enabled = enabled
            existing.status = status
            existing.config_json = config_json
            existing.redaction_json = redaction_json or {}
            existing.health_json = health_json or existing.health_json or {}
            existing.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        return existing, before

    async def replace_credential_refs(
        self,
        provider_config_id: str,
        credential_refs: list[dict[str, Any]],
    ) -> list[DiagnosticProviderCredentialRef]:
        await self.session.execute(
            delete(DiagnosticProviderCredentialRef).where(
                DiagnosticProviderCredentialRef.provider_config_id == provider_config_id
            )
        )
        rows: list[DiagnosticProviderCredentialRef] = []
        for item in credential_refs:
            credential_key = str(item.get("credential_key") or "").strip()
            secret_ref = str(item.get("secret_ref") or "").strip()
            if not credential_key or not secret_ref:
                continue
            row = DiagnosticProviderCredentialRef(
                id=_uuid(),
                provider_config_id=provider_config_id,
                credential_key=credential_key,
                secret_ref=secret_ref,
                status=str(item.get("status") or "missing"),
                metadata_json=dict(item.get("metadata") or item.get("metadata_json") or {}),
            )
            self.session.add(row)
            rows.append(row)
        await self.session.flush()
        return rows

    async def list_credential_refs(self, provider_config_id: str) -> list[DiagnosticProviderCredentialRef]:
        result = await self.session.execute(
            select(DiagnosticProviderCredentialRef)
            .where(DiagnosticProviderCredentialRef.provider_config_id == provider_config_id)
            .order_by(DiagnosticProviderCredentialRef.credential_key.asc())
        )
        return list(result.scalars())

    async def add_audit(
        self,
        *,
        provider_id: str,
        provider_config_id: str | None,
        action: str,
        actor_id: str | None,
        actor_role: str | None,
        before_json: dict[str, Any] | None,
        after_json: dict[str, Any] | None,
    ) -> DiagnosticProviderAudit:
        row = DiagnosticProviderAudit(
            provider_id=provider_id,
            provider_config_id=provider_config_id,
            action=action,
            actor_id=actor_id,
            actor_role=actor_role,
            before_json=before_json,
            after_json=after_json,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    @staticmethod
    def config_to_dict(item: DiagnosticProviderConfig | None) -> dict[str, Any] | None:
        if item is None:
            return None
        return {
            "id": item.id,
            "provider_id": item.provider_id,
            "provider_type": item.provider_type,
            "integration_key": item.integration_key,
            "enabled": item.enabled,
            "status": item.status,
            "config": item.config_json or {},
            "health": item.health_json or {},
        }
