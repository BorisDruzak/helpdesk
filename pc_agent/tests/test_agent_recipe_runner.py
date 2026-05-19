import asyncio
import sys
import tempfile
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if "loguru" not in sys.modules:
    loguru_module = types.ModuleType("loguru")

    class _LoggerStub:
        def __getattr__(self, _name):
            def _noop(*_args, **_kwargs):
                return None
            return _noop

    loguru_module.logger = _LoggerStub()
    sys.modules["loguru"] = loguru_module

from pc_agent.core.loader import DynamicModuleLoader
from pc_agent.core.module_manager import ModuleManager
from pc_agent.core.orchestrator import AgentOrchestrator
from pc_agent.core.recipe_runner_bridge import RecipeRunnerBridge
from pc_agent.config.config_loader import ConfigLoader, init_config
from pc_agent.modules_packages.agent_recipe_runner.module import AgentRecipeRunnerModule


RUNNER_MODULE = """
from pc_agent.modules.base_module import BaseCollector

MODULE_VERSION = "1.0.0"

class AgentRecipeRunnerModule(BaseCollector):
    @property
    def name(self):
        return "agent_recipe_runner"

    def version(self):
        return MODULE_VERSION

    async def collect(self):
        return {"runner": "ok"}

    def describe_primitives(self):
        return [
            {"primitive_id": "file.exists", "primitive_version": "1.0", "platforms": ["win32", "linux"]}
        ]

    def validate_recipe(self, recipe_payload, platform_context):
        return {"status": "passed"}

    async def run_recipe(self, recipe_payload, runtime_context):
        return {
            "status": "success",
            "data": {"observations": {"exists": True}, "result": {"exists": True}, "artifacts": []},
            "error": None,
            "meta": {"timestamp_iso": "2026-05-13T00:00:00+00:00", "duration_ms": 1, "module_versions": {"agent_recipe_runner": MODULE_VERSION}},
        }

def register():
    return AgentRecipeRunnerModule()
"""


def _write_runner(root: Path, version: str = "1.0.0") -> None:
    store = root / "modules_store"
    module_dir = store / "agent_recipe_runner" / version
    module_dir.mkdir(parents=True)
    (module_dir / "manifest.json").write_text(
        '{"module_name":"agent_recipe_runner","module_version":"%s","entrypoint":"module:register"}' % version,
        encoding="utf-8",
    )
    (module_dir / "module.py").write_text(RUNNER_MODULE.replace('MODULE_VERSION = "1.0.0"', f'MODULE_VERSION = "{version}"'), encoding="utf-8")
    (store / "agent_recipe_runner" / "current.json").write_text('{"version":"%s"}' % version, encoding="utf-8")


class RecipeRunnerBridgeTests(unittest.TestCase):
    def test_builtin_runner_primitives_expose_presentation_schema(self):
        runner = AgentRecipeRunnerModule()
        primitives = {item["primitive_id"]: item for item in runner.describe_primitives()}

        for primitive_id in (
            "dns.resolve",
            "tcp.connect",
            "http.request",
            "file.exists",
            "process.exists",
            "service.status",
            "systemd.service.status",
        ):
            with self.subTest(primitive_id=primitive_id):
                schema = primitives[primitive_id].get("presentation_schema")
                self.assertIsInstance(schema, dict)
                self.assertEqual(schema.get("version"), "1.0")
                self.assertEqual(schema.get("kind"), "tool_result")
                self.assertTrue(schema.get("blocks"))

    def test_missing_runner_returns_structured_error(self):
        with tempfile.TemporaryDirectory() as td:
            bridge = RecipeRunnerBridge(ModuleManager(str(Path(td)), str(Path(td) / "tmp")), DynamicModuleLoader(Path(td)))
            result = asyncio.run(
                bridge.run_recipe(
                    {
                        "min_runner_version": "1.0.0",
                        "primitive_id": "file.exists",
                        "recipe": {"params": {"path": "C:/temp/example.txt"}},
                    },
                    {"request_id": "req-1", "platform": "win32"},
                )
            )
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "RUNNER_NOT_INSTALLED")

    def test_outdated_runner_returns_structured_error(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_runner(root, "0.9.0")
            bridge = RecipeRunnerBridge(ModuleManager(str(root), str(root / "tmp")), DynamicModuleLoader(root))
            result = asyncio.run(
                bridge.run_recipe(
                    {"min_runner_version": "1.0.0", "primitive_id": "file.exists", "recipe": {"params": {}}},
                    {"request_id": "req-1", "platform": "win32"},
                )
            )
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "RUNNER_OUTDATED")

    def test_delegates_to_active_runner(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_runner(root, "1.0.0")
            bridge = RecipeRunnerBridge(ModuleManager(str(root), str(root / "tmp")), DynamicModuleLoader(root))
            result = asyncio.run(
                bridge.run_recipe(
                    {"min_runner_version": "1.0.0", "primitive_id": "file.exists", "recipe": {"params": {}}},
                    {"request_id": "req-1", "platform": "linux"},
                )
            )
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["data"]["observations"]["exists"], True)
        self.assertEqual(result["meta"]["module_versions"]["agent_recipe_runner"], "1.0.0")

    def test_orchestrator_run_recipe_wraps_bridge_dict_as_tool_response(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_runner(root, "1.0.0")
            ConfigLoader._instance = None
            ConfigLoader._config = None
            init_config(root)
            orchestrator = AgentOrchestrator(data_root=root, agent_uuid="device-1")
            result = asyncio.run(
                orchestrator.handle_command(
                    {
                        "cmd": "run_recipe",
                        "request_id": "req-1",
                        "device_id": "device-1",
                        "ticket_id": "ticket-1",
                        "operation_id": "req-1",
                        "trace_id": "trace-1",
                        "min_runner_version": "1.0.0",
                        "primitive_id": "file.exists",
                        "recipe": {"params": {"path": "/tmp/example"}},
                    }
                )
            )
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["meta"]["request_id"], "req-1")
        self.assertEqual(result["data"]["observations"]["exists"], True)
