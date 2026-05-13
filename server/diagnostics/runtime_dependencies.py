from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import config
from app.db.models import Device, DeviceModule, Operation
from app.repos import ModuleRolloutRepo, ModulesRepo, OperationDependenciesRepo, OperationsRepo
from diagnostics.agent_recipes_repo import AgentRecipeRepo, ResolvedAgentRecipe
from utils.module_manifest import get_module_manifest
from utils.versioning import compare_versions, version_key


RUNNER_DEPENDENCY_KEY = "agent_recipe_runner"
RUNNER_WAITING_PHASES = {"waiting_dependency", "installing_dependency"}
RUNNER_READINESS_STATUSES = {"runner_not_installed", "runner_install_required", "runner_outdated", "primitive_not_supported"}
_RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


@dataclass(frozen=True)
class RunnerDependencyPlan:
    action: str
    module_name: str
    current_version: Optional[str]
    target_version: str
    version_constraint: str
    timeout_sec: int
    module_sha256: str
    reason: str
    reason_code: str


class RunnerVersionResolver:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def resolve_required_runner(
        self,
        *,
        resolved: ResolvedAgentRecipe,
        device_platform: Optional[str],
        installed_runner: Optional[dict[str, Any]],
    ) -> dict[str, Any]:
        recipe = resolved.recipe_version
        module_name = recipe.runner_provider_id or RUNNER_DEPENDENCY_KEY
        min_version = str(recipe.min_runner_version or "").strip()
        constraint = self._version_constraint(resolved)
        current_version = str((installed_runner or {}).get("version") or "").strip() or None
        current_active = bool((installed_runner or {}).get("active")) and bool((installed_runner or {}).get("installed"))
        if current_version and current_active and self._satisfies(current_version, min_version, constraint):
            return {
                "status": "satisfied",
                "module_name": module_name,
                "current_version": current_version,
                "version_constraint": constraint,
            }

        assignment = await ModuleRolloutRepo(self.session).get_assignment(module_name)
        preferred_version = str((assignment or {}).get("version") or "").strip()
        if not preferred_version:
            return {
                "status": "error",
                "error_code": "NO_PREFERRED_RUNNER_VERSION",
                "message": f"Preferred version for {module_name} is not configured.",
                "module_name": module_name,
                "current_version": current_version,
                "version_constraint": constraint,
            }
        module = await ModulesRepo(self.session).get_module(module_name, preferred_version)
        if module is None:
            return {
                "status": "error",
                "error_code": "PREFERRED_RUNNER_VERSION_NOT_FOUND",
                "message": f"Preferred runner {module_name}@{preferred_version} is not present in module registry.",
                "module_name": module_name,
                "current_version": current_version,
                "version_constraint": constraint,
            }
        if not self._satisfies(preferred_version, min_version, constraint):
            return {
                "status": "error",
                "error_code": "NO_COMPATIBLE_RUNNER_VERSION",
                "message": f"Preferred runner {module_name}@{preferred_version} does not satisfy {constraint}.",
                "module_name": module_name,
                "current_version": current_version,
                "target_version": preferred_version,
                "version_constraint": constraint,
            }
        manifest = get_module_manifest(module)
        platform_error = self._platform_error(manifest, device_platform)
        if platform_error:
            return {
                "status": "error",
                "error_code": "RUNNER_PLATFORM_MISMATCH",
                "message": platform_error,
                "module_name": module_name,
                "current_version": current_version,
                "target_version": preferred_version,
                "version_constraint": constraint,
            }
        security_error = self._security_error(manifest)
        if security_error:
            return {
                "status": "error",
                "error_code": "RUNNER_MODULE_NOT_PROTECTED",
                "message": security_error,
                "module_name": module_name,
                "current_version": current_version,
                "target_version": preferred_version,
                "version_constraint": constraint,
            }
        primitive_supported = await AgentRecipeRepo(self.session).primitive_supported(
            runner_provider_id=module_name,
            runner_version=preferred_version,
            primitive_id=recipe.primitive_id,
        )
        if not primitive_supported:
            return {
                "status": "error",
                "error_code": "NO_COMPATIBLE_RUNNER_VERSION",
                "message": f"Preferred runner {module_name}@{preferred_version} does not support primitive {recipe.primitive_id}.",
                "module_name": module_name,
                "current_version": current_version,
                "target_version": preferred_version,
                "version_constraint": constraint,
            }
        action = "install_runner" if not current_version else "upgrade_runner"
        return {
            "status": "ok",
            "action": action,
            "module_name": module_name,
            "current_version": current_version,
            "target_version": preferred_version,
            "version_constraint": constraint,
            "module": module,
        }

    def _version_constraint(self, resolved: ResolvedAgentRecipe) -> str:
        recipe = resolved.recipe_version
        deployment = dict(resolved.capability_version.deployment_json or {})
        explicit = str(deployment.get("runner_version_constraint") or "").strip()
        if explicit:
            return explicit
        min_version = str(recipe.min_runner_version or "").strip()
        return f">={min_version}" if min_version else ">=0.0.0"

    def _satisfies(self, version: str, min_version: str, constraint: str) -> bool:
        if min_version and compare_versions(version, min_version) < 0:
            return False
        for token in str(constraint or "").replace(",", " ").split():
            token = token.strip()
            if not token:
                continue
            if token.startswith(">="):
                if compare_versions(version, token[2:]) < 0:
                    return False
            elif token.startswith(">"):
                if compare_versions(version, token[1:]) <= 0:
                    return False
            elif token.startswith("<="):
                if compare_versions(version, token[2:]) > 0:
                    return False
            elif token.startswith("<"):
                if compare_versions(version, token[1:]) >= 0:
                    return False
            elif token.startswith("==") and compare_versions(version, token[2:]) != 0:
                return False
        return version_key(version).valid

    def _platform_error(self, manifest: dict[str, Any], device_platform: Optional[str]) -> Optional[str]:
        platforms = [str(item).lower() for item in (manifest.get("platforms") or ["any"])]
        if "darwin" in platforms or "macos" in platforms or "mac" in platforms:
            return "Agent Recipe Runner must not advertise macOS support."
        if not device_platform or "any" in platforms:
            return None
        if device_platform not in platforms:
            return f"Runner does not support device platform {device_platform}; platforms={platforms}."
        return None

    def _security_error(self, manifest: dict[str, Any]) -> Optional[str]:
        owner_scope = str(manifest.get("owner_scope") or "").lower()
        if owner_scope not in {"core", "platform"}:
            return f"Runner owner_scope must be core/platform, got {owner_scope!r}."
        if not (manifest.get("system_module") is True or manifest.get("protected") is True):
            return "Runner manifest must be system_module=true or protected=true."
        return None


class RecipeRunnerDependencyProvider:
    def __init__(self, session: AsyncSession, *, state: Any = None):
        self.session = session
        self.state = state
        self.resolver = RunnerVersionResolver(session)

    async def build_plan(
        self,
        *,
        resolved: ResolvedAgentRecipe,
        readiness: Any,
        device_id: str,
        actor_role: str,
        installed_runner: Optional[dict[str, Any]],
        device_platform: Optional[str],
    ) -> dict[str, Any]:
        action = self._readiness_action(readiness)
        policy_error = self._policy_error(resolved=resolved, action=action, actor_role=actor_role)
        if policy_error:
            return policy_error
        selected = await self.resolver.resolve_required_runner(
            resolved=resolved,
            device_platform=device_platform,
            installed_runner=installed_runner,
        )
        if selected.get("status") != "ok":
            return selected
        module = selected["module"]
        timeout_sec = (
            config.AGENT_RECIPE_RUNNER_AUTO_INSTALL_TIMEOUT_SEC
            if selected["action"] == "install_runner"
            else config.AGENT_RECIPE_RUNNER_AUTO_UPGRADE_TIMEOUT_SEC
        )
        return {
            "status": "ok",
            "plan": RunnerDependencyPlan(
                action=selected["action"],
                module_name=selected["module_name"],
                current_version=selected.get("current_version"),
                target_version=selected["target_version"],
                version_constraint=selected["version_constraint"],
                timeout_sec=timeout_sec,
                module_sha256=module.sha256,
                reason="Agent Recipe Runner is required before this recipe can run.",
                reason_code=str(getattr(readiness, "reason_code", None) or selected["action"]).upper(),
            ),
        }

    async def install_or_upgrade_runner(
        self,
        *,
        parent_operation: Operation,
        plan: RunnerDependencyPlan,
        actor_role: str,
    ) -> dict[str, Any]:
        from modules.reconcile import reconcile_device, set_desired_installed

        await set_desired_installed(
            device_id=parent_operation.device_id,
            module_name=plan.module_name,
            desired_version=plan.target_version,
            desired_sha256=plan.module_sha256,
            reason="agent_recipe",
            updated_by=actor_role,
            session=self.session,
        )
        stats = await reconcile_device(
            parent_operation.device_id,
            self.state,
            session=self.session,
            reason="agent_recipe_dependency",
        )
        operation_id = None
        for item in stats.get("operations") or []:
            if (
                item.get("command") == "install_module_package"
                and item.get("module_name") == plan.module_name
                and item.get("module_version") == plan.target_version
            ):
                operation_id = item.get("operation_id")
                break
        return {"status": "installing" if operation_id else "pending", "operation_id": operation_id, "reconcile": stats}

    def _readiness_action(self, readiness: Any) -> str:
        actions = list(getattr(readiness, "actions", None) or [])
        if "upgrade_runner" in actions:
            return "upgrade_runner"
        return "install_runner"

    def _policy_error(self, *, resolved: ResolvedAgentRecipe, action: str, actor_role: str) -> Optional[dict[str, Any]]:
        descriptor = resolved.descriptor()
        if descriptor.tool_kind != "diagnostic" or descriptor.side_effects:
            return {
                "status": "error",
                "error_code": "RUNNER_AUTO_INSTALL_DISABLED",
                "message": "Runner auto-install is allowed only for read-only diagnostic recipes.",
            }
        max_risk = _RISK_ORDER.get(config.AGENT_RECIPE_RUNNER_AUTO_MAX_RISK, 0)
        if _RISK_ORDER.get(str(descriptor.risk_level or "low").lower(), 99) > max_risk:
            return {
                "status": "error",
                "error_code": "RUNNER_AUTO_INSTALL_DISABLED",
                "message": f"Recipe risk {descriptor.risk_level} exceeds auto-install policy.",
            }
        if action == "upgrade_runner":
            if not config.AGENT_RECIPE_RUNNER_AUTO_UPGRADE_ENABLED:
                return {"status": "error", "error_code": "RUNNER_AUTO_UPGRADE_DISABLED", "message": "Runner auto-upgrade is disabled."}
            if actor_role not in config.AGENT_RECIPE_RUNNER_AUTO_UPGRADE_ROLES:
                return {"status": "error", "error_code": "PERMISSION_DENIED", "message": "Actor role cannot auto-upgrade runner."}
        else:
            if not config.AGENT_RECIPE_RUNNER_AUTO_INSTALL_ENABLED:
                return {"status": "error", "error_code": "RUNNER_AUTO_INSTALL_DISABLED", "message": "Runner auto-install is disabled."}
            if actor_role not in config.AGENT_RECIPE_RUNNER_AUTO_INSTALL_ROLES:
                return {"status": "error", "error_code": "PERMISSION_DENIED", "message": "Actor role cannot auto-install runner."}
        return None


class RuntimeDependencyWorkflow:
    def __init__(self, session: AsyncSession, *, state: Any = None):
        self.session = session
        self.state = state
        self.dependencies = OperationDependenciesRepo(session)

    async def create_runner_dependency(
        self,
        *,
        parent_operation: Operation,
        plan: RunnerDependencyPlan,
        actor_role: str,
        runtime_params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        dependency = await self.dependencies.create_dependency(
            operation_id=parent_operation.operation_id,
            dependency_type="runner",
            dependency_key=RUNNER_DEPENDENCY_KEY,
            provider_id=plan.module_name,
            module_name=plan.module_name,
            current_version=plan.current_version,
            target_version=plan.target_version,
            version_constraint=plan.version_constraint,
            status="pending",
            reason=plan.reason,
            reason_code=plan.reason_code,
            timeout_at=datetime.now(timezone.utc) + timedelta(seconds=plan.timeout_sec),
            metadata={"action": plan.action, "runtime_params": dict(runtime_params or {})},
        )
        install_result = await RecipeRunnerDependencyProvider(self.session, state=self.state).install_or_upgrade_runner(
            parent_operation=parent_operation,
            plan=plan,
            actor_role=actor_role,
        )
        metadata = dict(dependency.metadata_json or {})
        metadata["reconcile"] = install_result.get("reconcile")
        if install_result.get("operation_id"):
            metadata["dependency_operation_id"] = install_result["operation_id"]
        await self.dependencies.update_dependency(
            dependency.id,
            status=install_result.get("status") or "pending",
            dependency_operation_id=install_result.get("operation_id"),
            metadata=metadata,
        )
        await OperationsRepo(self.session).update_phase(parent_operation.operation_id, "installing_dependency")
        return {
            "type": "runner",
            "action": plan.action,
            "module_name": plan.module_name,
            "required_version": plan.version_constraint,
            "target_version": plan.target_version,
            "dependency_operation_id": install_result.get("operation_id"),
            "status": install_result.get("status") or "pending",
        }

    async def fail_timed_out_dependencies(self) -> list[str]:
        timed_out = await self.dependencies.list_timed_out()
        failed: list[str] = []
        op_service = None
        for dep in timed_out:
            await self.dependencies.update_dependency(
                dep.id,
                status="timed_out",
                reason="Runner dependency timed out.",
                reason_code="RUNNER_INSTALL_TIMEOUT",
                resolved=True,
            )
            if op_service is None:
                from app.services.operation_service import OperationService

                op_service = OperationService(self.session)
            await op_service.mark_timed_out(
                dep.operation_id,
                error_message="Agent Recipe Runner dependency timed out.",
            )
            await OperationsRepo(self.session).update_phase(dep.operation_id, "failed")
            failed.append(dep.operation_id)
        return failed


def installed_runner_from_modules(rows: list[DeviceModule], module_name: str = RUNNER_DEPENDENCY_KEY) -> Optional[dict[str, Any]]:
    selected: Optional[dict[str, Any]] = None
    for row in rows:
        if row.module_name != module_name:
            continue
        item = {
            "version": row.version,
            "active": bool(row.active),
            "installed": bool(row.installed),
            "state": row.state,
        }
        if selected is None or item["active"]:
            selected = item
    return selected
