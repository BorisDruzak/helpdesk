from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DiagnosticProviderConfig, DiagnosticProviderCredentialRef
from app.repos.diagnostic_provider_config_repo import DiagnosticProviderConfigRepo


SENSITIVE_KEY_PARTS = ("password", "secret", "token", "apikey", "api_key", "credential")
REDACTED = "***redacted***"


@dataclass(frozen=True)
class DiagnosticReadinessMaps:
    integration_configs: dict[str, Any]
    credential_keys: dict[str, bool]
    credential_refs: dict[str, Any]
    mappings: dict[str, Any]
    policy_flags: dict[str, bool]


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower().replace("-", "_")
    return any(part in lowered for part in SENSITIVE_KEY_PARTS)


def _redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: (REDACTED if _is_sensitive_key(str(key)) else _redact_value(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    return value


def _redaction_markers(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    markers: dict[str, Any] = {}
    for key, item in value.items():
        if _is_sensitive_key(str(key)):
            markers[key] = True
        elif isinstance(item, dict):
            nested = _redaction_markers(item)
            if nested:
                markers[key] = nested
    return markers


class DiagnosticProviderConfigService:
    """Admin-safe lifecycle for diagnostic provider integration config."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = DiagnosticProviderConfigRepo(session)

    async def upsert_provider_config(
        self,
        *,
        provider_id: str,
        provider_type: str,
        integration_key: str | None = None,
        enabled: bool = True,
        config: dict[str, Any] | None = None,
        credential_refs: list[dict[str, Any]] | None = None,
        health: dict[str, Any] | None = None,
        actor_id: str | None = None,
        actor_role: str | None = None,
    ) -> DiagnosticProviderConfig:
        clean_provider_id = str(provider_id or "").strip()
        if not clean_provider_id:
            raise ValueError("provider_id is required")
        clean_provider_type = str(provider_type or "").strip() or "server_connector"
        redacted_config = _redact_value(dict(config or {}))
        redaction_json = _redaction_markers(dict(config or {}))
        refs = list(credential_refs or [])
        status = self._derive_status(
            enabled=enabled,
            integration_key=integration_key,
            credential_refs=refs,
            health=health or {},
        )
        await self.repo.upsert_provider(
            provider_id=clean_provider_id,
            provider_type=clean_provider_type,
            title=clean_provider_id,
            source="configured",
            status="available" if enabled else "disabled",
        )
        item, before = await self.repo.upsert_config(
            provider_id=clean_provider_id,
            provider_type=clean_provider_type,
            integration_key=integration_key,
            enabled=enabled,
            status=status,
            config_json=redacted_config,
            redaction_json=redaction_json,
            health_json=health or {},
        )
        await self.repo.replace_credential_refs(item.id, refs)
        after = await self._serialize(item)
        await self.repo.add_audit(
            provider_id=clean_provider_id,
            provider_config_id=item.id,
            action="provider_config.upsert",
            actor_id=actor_id,
            actor_role=actor_role,
            before_json=before,
            after_json=after,
        )
        return item

    async def get_provider_config(self, provider_id: str) -> dict[str, Any] | None:
        item = await self.repo.get_config(provider_id)
        if item is None:
            return None
        return await self._serialize(item)

    async def list_provider_configs(self) -> list[dict[str, Any]]:
        return [await self._serialize(item) for item in await self.repo.list_configs()]

    async def build_readiness_maps(self) -> DiagnosticReadinessMaps:
        integration_configs: dict[str, Any] = {}
        credential_keys: dict[str, bool] = {}
        credential_refs: dict[str, Any] = {}
        mappings: dict[str, Any] = {}
        policy_flags: dict[str, bool] = {}
        for config in await self.repo.list_configs():
            if not config.enabled or config.status == "disabled":
                if config.integration_key:
                    policy_flags[f"{config.integration_key}.enabled"] = False
                    if config.integration_key == "zabbix":
                        policy_flags["monitoring.zabbix.enabled"] = False
                continue
            integration_key = config.integration_key or config.provider_id
            integration_configs[integration_key] = dict(config.config_json or {})
            refs = await self.repo.list_credential_refs(config.id)
            credential_keys[integration_key] = any(ref.status == "ready" for ref in refs)
            ready_ref = next((ref for ref in refs if ref.status == "ready" and ref.secret_ref), None)
            if ready_ref is not None:
                credential_refs[integration_key] = ready_ref.secret_ref
            config_mappings = (config.config_json or {}).get("mappings")
            if isinstance(config_mappings, dict):
                mappings.update(config_mappings)
            policy_flags[f"{integration_key}.enabled"] = True
            if integration_key == "zabbix":
                policy_flags["monitoring.zabbix.enabled"] = True
        return DiagnosticReadinessMaps(
            integration_configs=integration_configs,
            credential_keys=credential_keys,
            credential_refs=credential_refs,
            mappings=mappings,
            policy_flags=policy_flags,
        )

    async def _serialize(self, item: DiagnosticProviderConfig) -> dict[str, Any]:
        refs = await self.repo.list_credential_refs(item.id)
        return {
            "id": item.id,
            "provider_id": item.provider_id,
            "provider_type": item.provider_type,
            "integration_key": item.integration_key,
            "enabled": item.enabled,
            "status": item.status,
            "config": dict(item.config_json or {}),
            "redaction": dict(item.redaction_json or {}),
            "health": dict(item.health_json or {}),
            "credential_refs": [self._credential_ref_to_dict(ref) for ref in refs],
        }

    def _credential_ref_to_dict(self, item: DiagnosticProviderCredentialRef) -> dict[str, Any]:
        return {
            "id": item.id,
            "credential_key": item.credential_key,
            "secret_ref": REDACTED,
            "status": item.status,
            "metadata": dict(item.metadata_json or {}),
        }

    def _derive_status(
        self,
        *,
        enabled: bool,
        integration_key: str | None,
        credential_refs: list[dict[str, Any]],
        health: dict[str, Any],
    ) -> str:
        if not enabled:
            return "disabled"
        health_status = str(health.get("status") or "").strip().lower()
        if health_status in {"degraded", "unavailable", "failed"}:
            return "degraded"
        ready_credentials = any(str(item.get("status") or "").strip().lower() == "ready" for item in credential_refs)
        if integration_key == "zabbix" and not ready_credentials:
            return "credentials_missing"
        return "ready" if ready_credentials else "configured"
