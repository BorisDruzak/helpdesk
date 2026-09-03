from __future__ import annotations

import ast
from pathlib import Path

import pytest


pytestmark = pytest.mark.no_db


ROOT = Path(__file__).resolve().parents[2]
ENDPOINT_BFF_SOURCES = (
    ROOT / "server" / "web_api" / "endpoint_operation_handlers.py",
    ROOT / "server" / "diagnostics" / "providers" / "endpoint_platform.py",
    ROOT / "server" / "diagnostics" / "capability_registry.py",
    ROOT / "server" / "diagnostics" / "execution_router.py",
)
FORBIDDEN_IMPORT_PREFIXES = (
    "websocket.protocol",
    "websocket.agent_handler",
    "app.repos.device_outbox_repo",
    "tools.service",
)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    return {
        name
        for node in ast.walk(tree)
        for name in (
            [alias.name for alias in node.names]
            if isinstance(node, ast.Import)
            else [node.module]
            if isinstance(node, ast.ImportFrom) and node.module
            else []
        )
    }


def test_endpoint_bff_never_imports_legacy_dispatch_runtime() -> None:
    violations = {
        path.relative_to(ROOT).as_posix(): sorted(
            imported
            for imported in _imports(path)
            if any(imported == forbidden or imported.startswith(f"{forbidden}.") for forbidden in FORBIDDEN_IMPORT_PREFIXES)
        )
        for path in ENDPOINT_BFF_SOURCES
    }

    assert {path: imports for path, imports in violations.items() if imports} == {}


def test_endpoint_execution_mode_has_no_legacy_fallback() -> None:
    config = (ROOT / "server" / "config.py").read_text(encoding="utf-8")

    assert "ENDPOINT_DIAGNOSTIC_EXECUTION_MODE=legacy" not in config


def test_helpdesk_ships_only_browser_ui_websocket_transport() -> None:
    websocket_dir = ROOT / "server" / "websocket"
    legacy_sources = {
        path.name
        for path in websocket_dir.glob("*.py")
        if path.name not in {"__init__.py", "subscription_registry.py", "ui_handler.py", "ui_publisher.py"}
    }

    assert legacy_sources == set()


def test_support_workspace_has_no_legacy_tool_dispatch_runtime() -> None:
    support_handlers = ROOT / "server" / "web_api" / "support_handlers.py"
    source = support_handlers.read_text(encoding="utf-8-sig")

    assert "tools.service" not in _imports(support_handlers)
    assert "handle_web_support_run_tool" not in source
    assert "ToolExecutionService" not in source


def test_diagnostic_runtime_has_no_local_agent_tool_execution() -> None:
    for relative_path in (
        "server/diagnostics/capability_registry.py",
        "server/diagnostics/execution_router.py",
    ):
        source = (ROOT / relative_path).read_text(encoding="utf-8-sig")
        assert "ToolService" not in source
        assert ".run_tool(" not in source


def test_diagnostic_registry_has_no_agent_recipe_fallback() -> None:
    for relative_path in (
        "server/diagnostics/capability_registry.py",
        "server/diagnostics/handlers.py",
    ):
        source = (ROOT / relative_path).read_text(encoding="utf-8-sig")
        assert "AgentRecipe" not in source
        assert "agent_recipe_runner" not in source


def test_active_metadata_has_no_legacy_agent_rollout_or_recipe_models() -> None:
    source = (ROOT / "server" / "app" / "db" / "models.py").read_text(encoding="utf-8-sig")

    for model_name in (
        "RunnerRolloutPlan",
        "RunnerRolloutWave",
        "RunnerRolloutTarget",
        "RunnerRolloutEvent",
        "AgentRecipeVersion",
        "AgentRecipePrimitive",
        "AgentRecipeTestRun",
    ):
        assert f"class {model_name}" not in source


def test_readiness_has_no_agent_execution_or_recipe_runner_path() -> None:
    readiness_source = (ROOT / "server" / "diagnostics" / "readiness.py").read_text(encoding="utf-8-sig")
    dependencies_source = (ROOT / "server" / "app" / "repos" / "operation_dependencies_repo.py").read_text(
        encoding="utf-8-sig"
    )

    assert "def _agent_readiness" not in readiness_source
    assert "def _agent_recipe_readiness" not in readiness_source
    assert "agent_recipe_runner" not in readiness_source
    assert "agent_recipe" not in dependencies_source
