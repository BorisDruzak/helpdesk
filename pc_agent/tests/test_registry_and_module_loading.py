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

from core.registry import ModuleRegistry, exposed_tool
from core.loader import DynamicModuleLoader
from modules import ModuleFactory
from modules.impl.input import InputCollector


CUSTOM_MODULE_TEMPLATE = """
from typing import Dict, Any
from modules.base_module import BaseCollector
from core.registry import exposed_tool


class CustomCollector(BaseCollector):
    @property
    def name(self) -> str:
        return "custom"

    async def collect(self) -> Dict[str, Any]:
        return {"kind": "default"}

    @exposed_tool(
        name="alias_tool",
        description="Alias tool for tests",
        risk_level="safe_readonly",
    )
    async def real_method(self) -> Dict[str, Any]:
        return {"kind": "alias"}
"""


class RegistryAliasTests(unittest.TestCase):
    def setUp(self):
        self.registry = ModuleRegistry()
        self.registry.reset()

    def tearDown(self):
        self.registry.reset()

    def test_input_alias_tool_uses_real_collect_method(self):
        self.registry.register(InputCollector())

        tool_info = self.registry.get_tool("input.collect_input_activity")
        self.assertIsNotNone(tool_info)
        self.assertEqual(tool_info["method_name"], "collect")

        result = asyncio.run(self.registry.call_tool("input.collect_input_activity"))
        self.assertIn("total_events", result)

    def test_custom_alias_resolves_real_method(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "custom.py").write_text(CUSTOM_MODULE_TEMPLATE, encoding="utf-8")
            module = ModuleFactory.create_modules(["custom"], extra_paths=[str(root)])[0]

            self.registry.register(module)

            tool_info = self.registry.get_tool("custom.alias_tool")
            self.assertIsNotNone(tool_info)
            self.assertEqual(tool_info["method_name"], "real_method")

    def test_semantic_tool_name_keeps_legacy_alias(self):
        class SemanticCollector:
            @property
            def name(self) -> str:
                return "network_basic"

            @exposed_tool(
                name="dns.resolve",
                aliases=["resolve_dns"],
                description="Resolve hostname",
                risk_level="safe_readonly",
                output_schema={"type": "object", "properties": {"ip": {"type": "string"}}},
                metadata_scopes=["network.read"],
            )
            async def resolve_impl(self):
                return {"ip": "127.0.0.1"}

        self.registry.register(SemanticCollector())

        canonical = self.registry.get_tool("dns.resolve")
        legacy = self.registry.get_tool("network_basic.resolve")
        explicit_alias = self.registry.get_tool("network_basic.resolve_dns")
        tools_flat = self.registry.get_tools_flat()

        self.assertIsNotNone(canonical)
        self.assertIsNotNone(legacy)
        self.assertIsNotNone(explicit_alias)
        self.assertEqual(canonical["method_name"], "resolve_impl")
        self.assertEqual(legacy["method_name"], "resolve_impl")
        self.assertEqual(explicit_alias["method_name"], "resolve_impl")
        flat_entry = next(item for item in tools_flat if item["tool"] == "dns.resolve")
        self.assertIn("network_basic.resolve", flat_entry["aliases"])
        self.assertIn("network_basic.resolve_dns", flat_entry["aliases"])
        self.assertEqual(flat_entry["spec"]["output_schema"]["type"], "object")


class ModuleFactoryExtraPathsTests(unittest.TestCase):
    def _write_module(self, root: Path, filename: str, content: str = CUSTOM_MODULE_TEMPLATE) -> None:
        (root / filename).write_text(content, encoding="utf-8")

    def test_extra_paths_prefers_regular_module_name(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_module(root, "custom.py")
            self._write_module(
                root,
                "test_custom.py",
                CUSTOM_MODULE_TEMPLATE.replace('"kind": "alias"', '"kind": "legacy"'),
            )

            modules = ModuleFactory.create_modules(["custom"], extra_paths=[str(root)])

            self.assertEqual(len(modules), 1)
            registry = ModuleRegistry()
            registry.reset()
            registry.register(modules[0])
            result = asyncio.run(registry.call_tool("custom.alias_tool"))
            self.assertEqual(result["kind"], "alias")

    def test_extra_paths_falls_back_to_legacy_test_prefix(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_module(root, "test_custom.py")

            modules = ModuleFactory.create_modules(["custom"], extra_paths=[str(root)])

            self.assertEqual(len(modules), 1)
            self.assertEqual(modules[0].name, "custom")


class DynamicModuleLoaderTests(unittest.TestCase):
    def _write_package_module(self, root: Path, method_name: str, version: str) -> None:
        (root / "module.py").write_text(
            f"""
from typing import Dict, Any
from modules.base_module import BaseCollector
from core.registry import exposed_tool


class DemoCollector(BaseCollector):
    @property
    def name(self) -> str:
        return "demo"

    async def collect(self) -> Dict[str, Any]:
        return {{"version": "{version}"}}

    @exposed_tool(
        name="report_status",
        description="Report status",
        risk_level="safe_readonly",
    )
    async def {method_name}(self) -> Dict[str, Any]:
        return {{"version": "{version}", "method": "{method_name}"}}


def register():
    return DemoCollector()
""".strip(),
            encoding="utf-8",
        )

    def test_loader_reloads_new_version_without_stale_runtime(self):
        loader = DynamicModuleLoader()

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            v1 = root / "1.0.0"
            v2 = root / "1.1.0"
            v1.mkdir()
            v2.mkdir()
            self._write_package_module(v1, "impl_status", "1.0.0")
            self._write_package_module(v2, "impl_status_v110", "1.1.0")

            instance_v1 = loader.load_module_from_path("demo", v1, entrypoint="module:register")
            result_v1 = asyncio.run(instance_v1.impl_status())
            self.assertEqual(result_v1["version"], "1.0.0")

            instance_v2 = loader.load_module_from_path("demo", v2, entrypoint="module:register")
            result_v2 = asyncio.run(instance_v2.impl_status_v110())
            self.assertEqual(result_v2["version"], "1.1.0")
            self.assertEqual(result_v2["method"], "impl_status_v110")
