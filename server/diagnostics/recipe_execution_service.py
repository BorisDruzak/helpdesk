from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Device, DeviceModule, Ticket
from app.repos.device_outbox_repo import DeviceOutboxRepo
from app.services.operation_service import OperationService
from diagnostics.agent_recipes_repo import AgentRecipeRepo, ResolvedAgentRecipe
from diagnostics.readiness import CapabilityReadinessService, ReadinessContext


def _device_platform(device: Any) -> Optional[str]:
    raw = str(getattr(device, "os", "") or "").strip().lower()
    if raw in {"windows", "win", "win32"}:
        return "win32"
    if raw.startswith("linux") or raw == "linux":
        return "linux"
    if raw in {"mac", "macos", "darwin"}:
        return "darwin"
    return raw or None


def _installed_module_map(rows: list[DeviceModule]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        current = result.get(row.module_name)
        item = {
            "version": row.version,
            "active": bool(row.active),
            "installed": bool(row.installed),
            "state": row.state,
        }
        if current is None or item["active"]:
            result[row.module_name] = item
    return result


class RecipeExecutionService:
    def __init__(self, session: AsyncSession, *, state: Any = None):
        self.session = session
        self.state = state
        self.repo = AgentRecipeRepo(session)

    async def get_recipe_capability(self, capability_id: str, version: Optional[str] = None) -> Optional[ResolvedAgentRecipe]:
        return await self.repo.get_recipe_capability(capability_id, version=version)

    async def get_recipe_readiness(
        self,
        *,
        ticket_id: Optional[str],
        device_id: Optional[str],
        capability_id: str,
    ):
        resolved = await self.repo.get_recipe_capability(capability_id)
        if resolved is None:
            return None
        device = await self.session.get(Device, device_id) if device_id else None
        modules = []
        if device_id:
            modules = list((await self.session.execute(select(DeviceModule).where(DeviceModule.device_id == device_id))).scalars())
        installed = _installed_module_map(modules)
        primitive_supported = None
        runner = installed.get(resolved.recipe_version.runner_provider_id)
        if runner and runner.get("version"):
            primitive_supported = await self.repo.primitive_supported(
                runner_provider_id=resolved.recipe_version.runner_provider_id,
                runner_version=str(runner.get("version")),
                primitive_id=resolved.recipe_version.primitive_id,
            )
        primitive_key = f"{resolved.recipe_version.runner_provider_id}:{resolved.recipe_version.primitive_id}"
        dependency_status = {primitive_key: primitive_supported} if primitive_supported is not None else {}
        return await CapabilityReadinessService(state=self.state).get_readiness(
            resolved.descriptor(),
            ReadinessContext(
                ticket_id=ticket_id,
                device_id=device_id,
                device_platform=_device_platform(device),
                installed_modules=installed,
                dependency_status=dependency_status,
            ),
        )

    async def run_recipe_capability(
        self,
        *,
        ticket_id: str,
        device_id: str,
        capability_id: str,
        params: dict[str, Any],
        actor: Any,
        idempotency_key: Optional[str] = None,
        timeout_ms: Optional[int] = None,
    ) -> dict[str, Any]:
        resolved = await self.repo.get_recipe_capability(capability_id)
        if resolved is None:
            return {"status": "error", "error_code": "AGENT_RECIPE_NOT_FOUND", "capability_id": capability_id}
        ticket = await self.session.get(Ticket, ticket_id)
        if ticket is None:
            return {"status": "error", "error_code": "TICKET_NOT_FOUND", "ticket_id": ticket_id}
        if not device_id:
            device_id = str(getattr(ticket, "device_id", "") or "")
        if not device_id:
            return {"status": "error", "error_code": "DEVICE_REQUIRED", "ticket_id": ticket_id}

        readiness = await self.get_recipe_readiness(ticket_id=ticket_id, device_id=device_id, capability_id=capability_id)
        if readiness is None or readiness.readiness != "available":
            readiness_dict = readiness.to_dict() if readiness is not None else {}
            return {
                "status": "error",
                "error_code": "CAPABILITY_NOT_READY",
                "readiness": readiness_dict.get("readiness", "unknown"),
                "reason_code": readiness_dict.get("reason_code", "CAPABILITY_NOT_READY"),
                "message": readiness_dict.get("reason") or "Recipe capability is not ready",
                "capability_id": capability_id,
                "ticket_id": ticket_id,
                "device_id": device_id,
            }

        operation_id = idempotency_key if idempotency_key and self._looks_uuid(idempotency_key) else str(uuid.uuid4())
        actor_role = self._actor_role(actor)
        operation = await OperationService(self.session).enqueue_operation(
            operation_id=operation_id,
            device_id=device_id,
            kind="agent_recipe",
            actor_role=actor_role,
            ticket_id=ticket_id,
            tool_name=capability_id,
            command_name="run_recipe",
            timeout_override_sec=int(timeout_ms / 1000) if timeout_ms else None,
            max_retries=3,
        )
        command_payload = self._command_payload(
            resolved,
            operation_id=operation_id,
            trace_id=operation.trace_id,
            ticket_id=ticket_id,
            runtime_params=params or {},
        )
        await DeviceOutboxRepo(self.session).enqueue_command(
            device_id=device_id,
            command_id=operation_id,
            command="run_recipe",
            params=command_payload,
            request_id=operation_id,
            trace_id=operation.trace_id,
            actor_role=actor_role,
            operation_id=operation_id,
        )
        return {
            "status": "queued",
            "capability_id": capability_id,
            "execution_target": "agent_recipe",
            "execution_kind": "operation",
            "operation_id": operation_id,
            "poll_url": f"/api/operations/{operation_id}",
            "command": "run_recipe",
            "ticket_id": ticket_id,
            "device_id": device_id,
            "readiness": readiness.readiness,
        }

    def _command_payload(
        self,
        resolved: ResolvedAgentRecipe,
        *,
        operation_id: str,
        trace_id: str,
        ticket_id: str,
        runtime_params: dict[str, Any],
    ) -> dict[str, Any]:
        recipe = resolved.recipe_version
        return {
            "type": "run_recipe",
            "operation_id": operation_id,
            "trace_id": trace_id,
            "ticket_id": ticket_id,
            "capability_id": resolved.capability.capability_id,
            "capability_version_id": resolved.capability_version.id,
            "recipe_version_id": recipe.id,
            "runner_provider_id": recipe.runner_provider_id,
            "min_runner_version": recipe.min_runner_version,
            "primitive_id": recipe.primitive_id,
            "primitive_version": recipe.primitive_version,
            "recipe": {
                "recipe_schema_version": recipe.recipe_schema_version,
                "platforms": list(recipe.platforms_json or []),
                "platform_variants": dict(recipe.platform_variants_json or {}),
                **dict(recipe.recipe_json or {}),
            },
            "runtime_params": dict(runtime_params or {}),
            "resource_limits": dict(recipe.resource_limits_json or {}),
            "redaction": dict(recipe.redaction_json or {}),
            "queued_at": datetime.now(timezone.utc).isoformat(),
        }

    def _actor_role(self, actor: Any) -> str:
        if isinstance(actor, dict):
            return str(actor.get("actor_role") or actor.get("role") or "user")
        return str(getattr(actor, "actor_role", None) or "user")

    def _looks_uuid(self, value: str) -> bool:
        try:
            uuid.UUID(str(value))
            return True
        except Exception:
            return False
