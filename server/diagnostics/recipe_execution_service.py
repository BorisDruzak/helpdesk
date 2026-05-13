from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Device, DeviceModule, Ticket
from app.repos import OperationDependenciesRepo, OperationsRepo, TicketEventsRepo
from app.repos.device_outbox_repo import DeviceOutboxRepo
from app.services.operation_service import OperationService
from diagnostics.agent_recipes_repo import AgentRecipeRepo, ResolvedAgentRecipe
from diagnostics.readiness import CapabilityReadinessService, ReadinessContext
from diagnostics.runtime_dependencies import (
    RUNNER_READINESS_STATUSES,
    RUNNER_WAITING_PHASES,
    RecipeRunnerDependencyProvider,
    RuntimeDependencyWorkflow,
    installed_runner_from_modules,
)


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
        actor_role = self._actor_role(actor)
        if readiness is None:
            readiness_dict = {}
            return {
                "status": "error",
                "error_code": "CAPABILITY_NOT_READY",
                "readiness": "unknown",
                "reason_code": "CAPABILITY_NOT_READY",
                "message": "Recipe capability is not ready",
                "capability_id": capability_id,
                "ticket_id": ticket_id,
                "device_id": device_id,
            }
        if readiness.readiness in RUNNER_READINESS_STATUSES:
            return await self._start_waiting_for_runner(
                resolved=resolved,
                ticket_id=ticket_id,
                device_id=device_id,
                params=params,
                actor_role=actor_role,
                readiness=readiness,
                idempotency_key=idempotency_key,
                timeout_ms=timeout_ms,
            )
        if readiness.readiness != "available":
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
        await self._enqueue_run_recipe(
            resolved,
            operation_id=operation_id,
            trace_id=operation.trace_id,
            ticket_id=ticket_id,
            runtime_params=params or {},
            actor_role=actor_role,
            device_id=device_id,
        )
        await OperationsRepo(self.session).update_phase(operation_id, "running_recipe")
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

    async def resume_after_dependency(self, operation_id: str) -> dict[str, Any]:
        operation = await OperationsRepo(self.session).get_by_operation_id(operation_id)
        if operation is None or operation.kind != "agent_recipe":
            return {"status": "ignored", "reason": "operation_not_agent_recipe"}
        if operation.status in {"succeeded", "failed", "timed_out", "canceled", "denied"}:
            return {"status": "ignored", "reason": "operation_terminal"}
        if operation.phase not in RUNNER_WAITING_PHASES:
            return {"status": "ignored", "reason": "operation_not_waiting_dependency"}
        dependencies = await OperationDependenciesRepo(self.session).get_for_operation(operation.operation_id)
        runner_dep = next((dep for dep in dependencies if dep.dependency_type == "runner"), None)
        if runner_dep is None:
            return {"status": "ignored", "reason": "dependency_missing"}
        await OperationDependenciesRepo(self.session).update_dependency(
            runner_dep.id,
            increment_resume_attempts=True,
        )
        capability_id = str(operation.tool_name or "")
        resolved = await self.repo.get_recipe_capability(capability_id)
        if resolved is None:
            await self._fail_operation(operation.operation_id, "AGENT_RECIPE_NOT_FOUND", "Recipe capability no longer exists.")
            return {"status": "failed", "error_code": "AGENT_RECIPE_NOT_FOUND"}
        readiness = await self.get_recipe_readiness(
            ticket_id=operation.ticket_id,
            device_id=operation.device_id,
            capability_id=capability_id,
        )
        if readiness and readiness.readiness == "available":
            metadata = dict(runner_dep.metadata_json or {})
            await OperationDependenciesRepo(self.session).update_dependency(
                runner_dep.id,
                status="ready",
                resolved=True,
            )
            await OperationsRepo(self.session).update_phase(operation.operation_id, "sending_run_recipe")
            await self._enqueue_run_recipe(
                resolved,
                operation_id=operation.operation_id,
                trace_id=operation.trace_id,
                ticket_id=str(operation.ticket_id or ""),
                runtime_params=dict(metadata.get("runtime_params") or {}),
                actor_role=operation.actor_role,
                device_id=operation.device_id,
            )
            await OperationsRepo(self.session).update_phase(operation.operation_id, "running_recipe")
            await self._ticket_event(
                ticket_id=str(operation.ticket_id or ""),
                device_id=operation.device_id,
                operation_id=operation.operation_id,
                trace_id=operation.trace_id,
                message="Agent Recipe Runner установлен. Запускаем проверку.",
                code="RUNNER_READY",
            )
            return {"status": "resumed", "operation_id": operation.operation_id, "readiness": "available"}
        if runner_dep.timeout_at and runner_dep.timeout_at < datetime.now(timezone.utc):
            await OperationDependenciesRepo(self.session).update_dependency(
                runner_dep.id,
                status="timed_out",
                reason="Runner dependency timed out.",
                reason_code="RUNNER_INSTALL_TIMEOUT",
                resolved=True,
            )
            await OperationService(self.session).mark_timed_out(
                operation.operation_id,
                error_message="Agent Recipe Runner dependency timed out.",
            )
            await OperationsRepo(self.session).update_phase(operation.operation_id, "failed")
            await self._ticket_event(
                ticket_id=str(operation.ticket_id or ""),
                device_id=operation.device_id,
                operation_id=operation.operation_id,
                trace_id=operation.trace_id,
                message="Не удалось установить Agent Recipe Runner: таймаут.",
                code="RUNNER_INSTALL_TIMEOUT",
            )
            return {"status": "timed_out", "operation_id": operation.operation_id}
        return {
            "status": "waiting",
            "operation_id": operation.operation_id,
            "readiness": readiness.readiness if readiness else "unknown",
            "reason_code": readiness.reason_code if readiness else "UNKNOWN",
        }

    async def resume_waiting_dependencies_for_device(self, device_id: str) -> list[dict[str, Any]]:
        await RuntimeDependencyWorkflow(self.session, state=self.state).fail_timed_out_dependencies()
        deps = await OperationDependenciesRepo(self.session).list_waiting_runner_dependencies_for_device(device_id=device_id)
        results: list[dict[str, Any]] = []
        for dep in deps:
            results.append(await self.resume_after_dependency(dep.operation_id))
        return results

    async def notify_dependency_operation_terminal(
        self,
        dependency_operation_id: str,
        terminal_status: str,
        payload: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        deps = await OperationDependenciesRepo(self.session).get_by_dependency_operation_id(dependency_operation_id)
        results: list[dict[str, Any]] = []
        for dep in deps:
            if terminal_status == "succeeded":
                await OperationDependenciesRepo(self.session).update_dependency(dep.id, status="installing")
                results.append(await self.resume_after_dependency(dep.operation_id))
                continue
            reason = ((payload or {}).get("error") or {}).get("message") if isinstance(payload, dict) else None
            await OperationDependenciesRepo(self.session).update_dependency(
                dep.id,
                status="failed",
                reason=reason or "Runner install/upgrade operation failed.",
                reason_code="RUNNER_INSTALL_FAILED",
                resolved=True,
            )
            await self._fail_operation(dep.operation_id, "RUNNER_INSTALL_FAILED", reason or "Agent Recipe Runner install failed.")
            results.append({"status": "failed", "operation_id": dep.operation_id})
        return results

    async def _start_waiting_for_runner(
        self,
        *,
        resolved: ResolvedAgentRecipe,
        ticket_id: str,
        device_id: str,
        params: dict[str, Any],
        actor_role: str,
        readiness: Any,
        idempotency_key: Optional[str],
        timeout_ms: Optional[int],
    ) -> dict[str, Any]:
        modules = list((await self.session.execute(select(DeviceModule).where(DeviceModule.device_id == device_id))).scalars())
        device = await self.session.get(Device, device_id)
        runner = installed_runner_from_modules(modules, resolved.recipe_version.runner_provider_id)
        plan_result = await RecipeRunnerDependencyProvider(self.session, state=self.state).build_plan(
            resolved=resolved,
            readiness=readiness,
            device_id=device_id,
            actor_role=actor_role,
            installed_runner=runner,
            device_platform=_device_platform(device),
        )
        if plan_result.get("status") != "ok":
            return {
                "status": "error",
                "error_code": plan_result.get("error_code") or "RUNNER_DEPENDENCY_UNAVAILABLE",
                "message": plan_result.get("message") or "Runner dependency cannot be installed automatically.",
                "capability_id": resolved.capability.capability_id,
                "ticket_id": ticket_id,
                "device_id": device_id,
                "readiness": readiness.readiness,
                "reason_code": readiness.reason_code,
            }

        operation_id = idempotency_key if idempotency_key and self._looks_uuid(idempotency_key) else str(uuid.uuid4())
        operation = await OperationService(self.session).enqueue_operation(
            operation_id=operation_id,
            device_id=device_id,
            kind="agent_recipe",
            actor_role=actor_role,
            ticket_id=ticket_id,
            tool_name=resolved.capability.capability_id,
            command_name="run_recipe",
            timeout_override_sec=int(timeout_ms / 1000) if timeout_ms else None,
            max_retries=3,
            initial_phase="waiting_dependency",
        )
        dependency = await RuntimeDependencyWorkflow(self.session, state=self.state).create_runner_dependency(
            parent_operation=operation,
            plan=plan_result["plan"],
            actor_role=actor_role,
            runtime_params=params or {},
        )
        action_label = "обновление" if dependency.get("action") == "upgrade_runner" else "установка"
        await self._ticket_event(
            ticket_id=ticket_id,
            device_id=device_id,
            operation_id=operation.operation_id,
            trace_id=operation.trace_id,
            message=f"Для проверки требуется Agent Recipe Runner. Запланирована {action_label} версии {dependency.get('target_version')}.",
            code="RUNNER_DEPENDENCY_SCHEDULED",
            details={"dependency": dependency},
        )
        return {
            "status": "waiting_dependency",
            "phase": "installing_runner",
            "capability_id": resolved.capability.capability_id,
            "execution_target": "agent_recipe",
            "execution_kind": "operation",
            "operation_id": operation.operation_id,
            "poll_url": f"/api/operations/{operation.operation_id}",
            "ticket_id": ticket_id,
            "device_id": device_id,
            "readiness": readiness.readiness,
            "reason_code": readiness.reason_code,
            "dependency": dependency,
        }

    async def _enqueue_run_recipe(
        self,
        resolved: ResolvedAgentRecipe,
        *,
        operation_id: str,
        trace_id: str,
        ticket_id: str,
        runtime_params: dict[str, Any],
        actor_role: str,
        device_id: str,
    ) -> None:
        outbox_repo = DeviceOutboxRepo(self.session)
        existing = await outbox_repo.get_command_by_id(operation_id)
        if existing is not None:
            return
        command_payload = self._command_payload(
            resolved,
            operation_id=operation_id,
            trace_id=trace_id,
            ticket_id=ticket_id,
            runtime_params=runtime_params or {},
        )
        await outbox_repo.enqueue_command(
            device_id=device_id,
            command_id=operation_id,
            command="run_recipe",
            params=command_payload,
            request_id=operation_id,
            trace_id=trace_id,
            actor_role=actor_role,
            operation_id=operation_id,
        )

    async def _fail_operation(self, operation_id: str, error_code: str, error_message: str) -> None:
        operation = await OperationsRepo(self.session).get_by_operation_id(operation_id)
        await OperationService(self.session).mark_failed(
            operation_id,
            error_code=error_code,
            error_message=error_message,
        )
        await OperationsRepo(self.session).update_phase(operation_id, "failed")
        if operation is not None:
            await self._ticket_event(
                ticket_id=str(operation.ticket_id or ""),
                device_id=operation.device_id,
                operation_id=operation.operation_id,
                trace_id=operation.trace_id,
                message=f"Не удалось установить Agent Recipe Runner: {error_message}",
                code=error_code,
            )

    async def _ticket_event(
        self,
        *,
        ticket_id: str,
        device_id: str,
        operation_id: str,
        trace_id: str,
        message: str,
        code: str,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        if not ticket_id:
            return
        try:
            await TicketEventsRepo(self.session).add_event(
                ticket_id=ticket_id,
                device_id=device_id,
                agent_seq=None,
                event_type="diagnostic_dependency",
                payload={"message": message, "code": code, **(details or {})},
                trace_id=trace_id,
                operation_id=operation_id,
            )
        except Exception as exc:
            # Dependency events are observational; never fail the execution path because of timeline write issues.
            import logging

            logging.getLogger(__name__).debug("Failed to write diagnostic dependency event: %s", exc)

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
