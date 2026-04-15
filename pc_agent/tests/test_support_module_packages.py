import asyncio
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SERVER_ROOT = PROJECT_ROOT / "server"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

sys.modules.pop("utils", None)

_server_root_inserted = False
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))
    _server_root_inserted = True

from pc_agent.core.loader import DynamicModuleLoader
from pc_agent.core.module_manager import ModuleManager
from pc_agent.core.registry import ModuleRegistry
from scripts.register_support_modules import MODULE_SPECS
from utils.module_builder import build_module_package

if _server_root_inserted:
    try:
        sys.path.remove(str(SERVER_ROOT))
    except ValueError:
        pass


def _build_module_zip(spec: dict) -> bytes:
    zip_bytes, _summary = build_module_package(
        module_name=spec["module_name"],
        version=spec["version"],
        tool_name=spec.get("tool_name", ""),
        method_name=spec.get("method_name"),
        description=spec["description"],
        user_function_body=spec.get("user_function_body", ""),
        risk_level=spec.get("risk_level"),
        params_schema=spec.get("params_schema"),
        presets=spec.get("presets"),
        platforms=spec.get("platforms"),
        metadata=spec.get("metadata"),
        output_schema=spec.get("output_schema"),
        aliases=spec.get("aliases"),
        tools=spec.get("tools"),
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


async def _start_local_server():
    async def _handle_client(reader, writer):
        writer.write(b"hello")
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(_handle_client, "127.0.0.1", 0)
    socket_info = server.sockets[0].getsockname()
    return server, socket_info[1]


def test_network_basic_module_installs_and_runs_cross_platform_tools(tmp_path):
    spec = next(item for item in MODULE_SPECS if item["module_name"] == "network_basic")
    registry = _install_and_register(tmp_path, spec)
    try:
        async def _exercise_module():
            dns_result = await registry.call_tool("dns.resolve", hostname="localhost")
            ping_result = await registry.call_tool(
                "ping.host",
                target="127.0.0.1",
                count=1,
                timeout_ms=1000,
            )
            server, port = await _start_local_server()
            try:
                tcp_result = await registry.call_tool("tcp.connect", host="127.0.0.1", port=port, timeout_sec=2)
                route_result = await registry.call_tool("route.get", target="127.0.0.1", port=port, timeout_sec=2)
            finally:
                server.close()
                await server.wait_closed()
            adapters_result = await registry.call_tool("adapter.list")
            legacy_alias_result = await registry.call_tool(
                "network_basic.ping",
                target="127.0.0.1",
                count=1,
                timeout_ms=1000,
            )
            return dns_result, ping_result, tcp_result, route_result, adapters_result, legacy_alias_result

        dns_result, ping_result, tcp_result, route_result, adapters_result, legacy_alias_result = asyncio.run(
            _exercise_module()
        )
    finally:
        registry.reset()

    assert dns_result["ok"] is True
    assert dns_result["address_count"] >= 1
    assert dns_result["best_ip"]
    assert ping_result["ok"] is True
    assert ping_result["reachable"] is True
    assert tcp_result["ok"] is True
    assert tcp_result["reachable"] is True
    assert route_result["ok"] is True
    assert route_result["local_ip"]
    assert adapters_result["ok"] is True
    assert adapters_result["interface_count"] >= 1
    assert legacy_alias_result["reachable"] is True


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
