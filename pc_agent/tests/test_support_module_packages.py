import asyncio
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SERVER_ROOT = PROJECT_ROOT / "server"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

sys.modules.pop("utils", None)

from pc_agent.core.loader import DynamicModuleLoader
from pc_agent.core.module_manager import ModuleManager
from pc_agent.core.registry import ModuleRegistry
from scripts.register_support_modules import MODULE_SPECS
from utils.module_builder import build_module_package


def _build_module_zip(spec: dict) -> bytes:
    zip_bytes, _summary = build_module_package(
        module_name=spec["module_name"],
        version=spec["version"],
        tool_name=spec["tool_name"],
        method_name=spec.get("method_name"),
        description=spec["description"],
        user_function_body=spec["user_function_body"],
        risk_level=spec.get("risk_level"),
        params_schema=spec.get("params_schema"),
        presets=spec.get("presets"),
        platforms=spec.get("platforms"),
        metadata=spec.get("metadata"),
        requirements=spec.get("requirements"),
        optional_requirements=spec.get("optional_requirements"),
        min_agent_version=spec.get("min_agent_version"),
    )
    return zip_bytes


def _install_and_register(tmp_path: Path, spec: dict) -> ModuleRegistry:
    data_root = tmp_path / "data"
    manager = ModuleManager(data_dir=str(data_root), temp_dir=str(data_root / "temp"))
    zip_bytes = _build_module_zip(spec)
    result = manager.install_zip_bytes(zip_bytes)
    active_path = manager.activate(spec["module_name"], spec["version"])

    loader = DynamicModuleLoader(data_root=data_root)
    registry = ModuleRegistry()
    registry.reset()
    instance = loader.load_module_from_path(
        spec["module_name"],
        active_path,
        entrypoint=result["manifest"].get("entrypoint", "module:register"),
    )
    registry.register(instance)
    return registry


def test_network_ping_module_installs_and_replies(tmp_path):
    spec = next(item for item in MODULE_SPECS if item["module_name"] == "network_ping")
    registry = _install_and_register(tmp_path, spec)
    try:
        result = asyncio.run(
            registry.call_tool(
                "network_ping.ping",
                host="127.0.0.1",
                count=1,
                timeout_ms=1000,
            )
        )
    finally:
        registry.reset()

    assert result["ok"] is True
    assert result["reachable"] is True
    assert result["host"] == "127.0.0.1"
    assert result["command"]
    assert isinstance(result["summary"], str)


def test_fsnav_module_installs_and_navigates(tmp_path):
    spec = next(item for item in MODULE_SPECS if item["module_name"] == "fsnav")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "docs").mkdir()
    (workspace / "readme.txt").write_text("hello", encoding="utf-8")

    registry = _install_and_register(tmp_path, spec)
    try:
        pwd_result = asyncio.run(
            registry.call_tool(
                "fsnav.navigate",
                action="pwd",
                cwd=str(workspace),
            )
        )
        ls_result = asyncio.run(
            registry.call_tool(
                "fsnav.navigate",
                action="ls",
                cwd=str(workspace),
                limit=20,
            )
        )
        stat_result = asyncio.run(
            registry.call_tool(
                "fsnav.navigate",
                action="stat",
                cwd=str(workspace),
                path="readme.txt",
            )
        )
    finally:
        registry.reset()

    assert pwd_result["ok"] is True
    assert Path(pwd_result["cwd"]) == workspace.resolve()
    assert ls_result["ok"] is True
    assert {entry["name"] for entry in ls_result["entries"]} == {"docs", "readme.txt"}
    assert ls_result["returned_count"] == 2
    assert stat_result["ok"] is True
    assert stat_result["entry"]["name"] == "readme.txt"
    assert stat_result["entry"]["is_dir"] is False
