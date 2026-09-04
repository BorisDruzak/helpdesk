from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Device, DeviceUserBinding
from app.repos.registration_repo import RegistrationRepo
from app.repos.registry_repo import RegistryRepo
from registry.policy_service import RegistryPolicyService


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _clean(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


class PrimaryAgentResolver:
    """Resolve a person's diagnostic target without exposing agent secrets."""

    def __init__(self, session: AsyncSession, *, state: Any | None = None):
        self.session = session
        self.state = state
        self.registration_repo = RegistrationRepo(session)
        self.registry_repo = RegistryRepo(session)

    async def resolve_for_person(self, person_id: str) -> dict[str, Any]:
        normalized_person_id = _clean(person_id)
        if not normalized_person_id:
            return {
                "resolved": False,
                "person_id": None,
                "reason_code": "person_missing",
                "candidate_count": 0,
            }

        bindings = [
            binding
            for binding in await self.registration_repo.list_bindings_for_person(
                normalized_person_id,
                active_only=True,
            )
            if str(getattr(binding, "status", "") or "") == "active"
        ]
        primary_bindings = [
            binding
            for binding in bindings
            if str(getattr(binding, "relationship_type", "") or "") == "primary_user"
        ]
        if len(primary_bindings) == 1:
            return await self._target_payload(
                primary_bindings[0],
                reason_code="primary_binding",
                source="primary_user_binding",
            )
        if len(primary_bindings) > 1:
            return self._ambiguous(
                normalized_person_id,
                primary_bindings,
                reason_code="ambiguous_primary_device",
            )

        allow_fallback = await self._allow_single_active_fallback()
        if not allow_fallback:
            return {
                "resolved": False,
                "person_id": normalized_person_id,
                "reason_code": "primary_device_missing",
                "candidate_count": len(bindings),
            }
        if len(bindings) == 1:
            return await self._target_payload(
                bindings[0],
                reason_code="single_active_binding",
                source="single_active_binding_fallback",
            )
        if len(bindings) > 1:
            return self._ambiguous(
                normalized_person_id,
                bindings,
                reason_code="ambiguous_primary_device",
            )
        return {
            "resolved": False,
            "person_id": normalized_person_id,
            "reason_code": "primary_device_missing",
            "candidate_count": 0,
        }

    async def _allow_single_active_fallback(self) -> bool:
        policies = await RegistryPolicyService(self.session).get_policies()
        diagnostic_target = (
            policies.get("diagnostic_target")
            if isinstance(policies.get("diagnostic_target"), dict)
            else {}
        )
        return bool(diagnostic_target.get("allow_single_active_binding_fallback", False))

    def _connection_state(self, device_id: str) -> tuple[bool | None, str]:
        del device_id
        return None, "unknown"

    async def _target_payload(
        self,
        binding: DeviceUserBinding,
        *,
        reason_code: str,
        source: str,
    ) -> dict[str, Any]:
        device = await self.session.get(Device, binding.device_id)
        asset = await self.registry_repo.get_asset_by_device_id(binding.device_id)
        online, connection_state = self._connection_state(binding.device_id)
        asset_discovery = asset.discovery_payload if asset is not None and isinstance(asset.discovery_payload, dict) else {}
        return {
            "resolved": True,
            "reason_code": reason_code,
            "source": source,
            "person_id": binding.person_id,
            "device_id": binding.device_id,
            "binding_id": binding.binding_id,
            "asset_id": binding.asset_id or getattr(asset, "asset_id", None),
            "relationship_type": binding.relationship_type,
            "hostname": _clean(getattr(device, "hostname", None)) or _clean(getattr(asset, "hostname", None)),
            "online": online,
            "connection_state": connection_state,
            "last_seen_at": _iso(
                getattr(device, "last_seen_at", None)
                or getattr(binding, "last_seen_at", None)
                or getattr(asset, "last_seen_at", None)
            ),
            "last_handshake_at": _iso(getattr(device, "last_handshake_at", None)),
            "agent_version": _clean(getattr(device, "agent_version", None)) or _clean(asset_discovery.get("agent_version")),
        }

    def _ambiguous(self, person_id: str, bindings: list[DeviceUserBinding], *, reason_code: str) -> dict[str, Any]:
        return {
            "resolved": False,
            "person_id": person_id,
            "reason_code": reason_code,
            "candidate_count": len(bindings),
            "candidates": [
                {
                    "device_id": binding.device_id,
                    "binding_id": binding.binding_id,
                    "relationship_type": binding.relationship_type,
                }
                for binding in bindings
            ],
        }
