from __future__ import annotations

import inspect
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from pc_agent.core.loader import DynamicModuleLoader
from pc_agent.core.module_manager import ModuleManager


RUNNER_PROVIDER_ID = "agent_recipe_runner"


class RecipeRunnerBridge:
    """Stable agent-core bridge to the protected managed recipe runner module."""

    def __init__(
        self,
        module_manager: ModuleManager,
        loader: DynamicModuleLoader,
        *,
        runner_provider_id: str = RUNNER_PROVIDER_ID,
    ) -> None:
        self.module_manager = module_manager
        self.loader = loader
        self.runner_provider_id = runner_provider_id

    async def describe_primitives(self) -> dict[str, Any]:
        runner, version, error = self._load_runner(min_runner_version="0.0.0")
        if error is not None:
            return error
        primitives = await self._maybe_await(runner.describe_primitives())
        return self._success({"primitives": list(primitives or []), "runner_version": version}, version)

    async def validate_recipe(self, recipe_payload: dict[str, Any], platform_context: dict[str, Any]) -> dict[str, Any]:
        runner, version, error = self._load_runner(
            min_runner_version=str(recipe_payload.get("min_runner_version") or "0.0.0")
        )
        if error is not None:
            return error
        primitive_error = await self._primitive_error(runner, recipe_payload, version)
        if primitive_error is not None:
            return primitive_error
        result = await self._maybe_await(runner.validate_recipe(recipe_payload, platform_context))
        return self._success({"validation": result or {"status": "passed"}, "runner_version": version}, version)

    async def run_recipe(self, recipe_payload: dict[str, Any], runtime_context: dict[str, Any]) -> dict[str, Any]:
        min_runner_version = str(recipe_payload.get("min_runner_version") or "0.0.0")
        runner, version, error = self._load_runner(min_runner_version=min_runner_version)
        if error is not None:
            return error
        primitive_error = await self._primitive_error(runner, recipe_payload, version)
        if primitive_error is not None:
            return primitive_error
        validation = await self._maybe_await(runner.validate_recipe(recipe_payload, runtime_context))
        if isinstance(validation, dict) and validation.get("status") in {"failed", "error"}:
            return self._error("INVALID_RECIPE", validation.get("message") or "Recipe validation failed", version)
        result = await self._maybe_await(runner.run_recipe(recipe_payload, runtime_context))
        if isinstance(result, dict):
            result.setdefault("meta", {})
            result["meta"].setdefault("timestamp_iso", datetime.now(timezone.utc).isoformat())
            result["meta"].setdefault("module_versions", {})
            result["meta"]["module_versions"].setdefault(self.runner_provider_id, version)
            result.setdefault("data", {})
            if isinstance(result["data"], dict):
                result["data"].setdefault(
                    "recipe_result",
                    {
                        "capability_id": recipe_payload.get("capability_id"),
                        "recipe_version_id": recipe_payload.get("recipe_version_id"),
                        "primitive_id": recipe_payload.get("primitive_id"),
                        "runner_version": version,
                    },
                )
            return result
        return self._error("INVALID_RUNNER_RESULT", "Runner returned invalid result payload", version)

    async def _primitive_error(self, runner: Any, recipe_payload: dict[str, Any], runner_version: str) -> Optional[dict[str, Any]]:
        primitive_id = str(recipe_payload.get("primitive_id") or "").strip()
        if not primitive_id:
            return self._error("INVALID_RECIPE", "primitive_id is required", runner_version)
        primitives = await self._maybe_await(runner.describe_primitives())
        supported = {
            str(item.get("primitive_id") or "").strip()
            for item in primitives or []
            if isinstance(item, dict)
        }
        if primitive_id not in supported:
            return self._error("PRIMITIVE_NOT_SUPPORTED", f"Primitive '{primitive_id}' is not supported", runner_version)
        return None

    def _load_runner(self, *, min_runner_version: str) -> tuple[Any | None, str | None, dict[str, Any] | None]:
        active_path = self.module_manager.get_active_path(self.runner_provider_id)
        if active_path is None:
            return None, None, self._error("RUNNER_NOT_INSTALLED", "Agent Recipe Runner is not installed", None)
        manifest = self._read_manifest(active_path)
        if str(manifest.get("module_name") or self.runner_provider_id) != self.runner_provider_id:
            return None, None, self._error("RUNNER_INVALID", "Active runner module identity is invalid", None)
        entrypoint = str(manifest.get("entrypoint") or "module:register")
        runner = self.loader.load_module_from_path(self.runner_provider_id, active_path, entrypoint=entrypoint)
        version = str(getattr(runner, "version", lambda: manifest.get("module_version") or "0.0.0")())
        if self._compare_versions(version, min_runner_version) < 0:
            return None, version, self._error(
                "RUNNER_OUTDATED",
                f"Agent Recipe Runner {version} is below required {min_runner_version}",
                version,
            )
        for method_name in ("describe_primitives", "validate_recipe", "run_recipe"):
            if not callable(getattr(runner, method_name, None)):
                return None, version, self._error("RUNNER_INVALID", f"Runner missing {method_name}", version)
        return runner, version, None

    def _read_manifest(self, active_path: Path) -> dict[str, Any]:
        try:
            return json.loads((active_path / "manifest.json").read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning(f"[agent_recipe] failed to read runner manifest: {exc}")
            return {}

    async def _maybe_await(self, value: Any) -> Any:
        if inspect.isawaitable(value):
            return await value
        return value

    def _success(self, observations: dict[str, Any], runner_version: Optional[str]) -> dict[str, Any]:
        return {
            "status": "success",
            "data": {"observations": observations, "result": observations, "artifacts": []},
            "error": None,
            "meta": {
                "timestamp_iso": datetime.now(timezone.utc).isoformat(),
                "module_versions": {self.runner_provider_id: runner_version or "unknown"},
            },
        }

    def _error(self, code: str, message: str, runner_version: Optional[str]) -> dict[str, Any]:
        return {
            "status": "error",
            "data": {},
            "error": {"code": code, "message": message, "retriable": code in {"RUNNER_NOT_INSTALLED", "RUNNER_OUTDATED"}},
            "meta": {
                "timestamp_iso": datetime.now(timezone.utc).isoformat(),
                "module_versions": {self.runner_provider_id: runner_version} if runner_version else {},
            },
        }

    def _compare_versions(self, left: str, right: str) -> int:
        left_key = self._version_key(left)
        right_key = self._version_key(right)
        if left_key < right_key:
            return -1
        if left_key > right_key:
            return 1
        return 0

    def _version_key(self, value: str) -> tuple[int, int, int]:
        match = re.match(r"^(\d+)\.(\d+)\.(\d+)", str(value or "").strip())
        if not match:
            return (0, 0, 0)
        return tuple(int(part) for part in match.groups())
