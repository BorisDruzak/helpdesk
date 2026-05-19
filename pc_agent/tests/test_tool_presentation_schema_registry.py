import unittest

from pc_agent.core.registry import ModuleRegistry, exposed_tool


PRESENTATION_SCHEMA = {
    "version": "1.0",
    "kind": "tool_result",
    "title": "Demo",
    "blocks": [
        {
            "type": "field_grid",
            "id": "identity",
            "title": "Identity",
            "fields": [{"path": "hostname", "label": "Host"}],
        }
    ],
    "fallback": {"show_raw_json": True},
}


class PresentationCollector:
    @property
    def name(self) -> str:
        return "presentation_demo"

    @exposed_tool(
        name="collect",
        description="Collect demo output",
        output_schema={"type": "object", "properties": {"hostname": {"type": "string"}}},
        output_contract={"status_path": "status"},
        presentation_schema=PRESENTATION_SCHEMA,
    )
    async def collect(self):
        return {"hostname": "pc-1", "status": "ok"}

    @exposed_tool(name="plain", description="Plain tool")
    async def plain(self):
        return {"ok": True}


class ToolPresentationSchemaRegistryTests(unittest.TestCase):
    def setUp(self):
        self.registry = ModuleRegistry()
        self.registry.reset()

    def tearDown(self):
        self.registry.reset()

    def test_exposed_tool_presentation_schema_is_in_manifest(self):
        self.registry.register(PresentationCollector())

        method_info = self.registry.get_all()["presentation_demo"]["methods"]["collect"]

        self.assertEqual(method_info["presentation_schema"], PRESENTATION_SCHEMA)
        self.assertEqual(method_info["output_schema"]["type"], "object")
        self.assertEqual(method_info["output_contract"]["status_path"], "status")

    def test_get_tools_flat_includes_presentation_schema_in_spec(self):
        self.registry.register(PresentationCollector())

        flat_entry = next(item for item in self.registry.get_tools_flat() if item["tool"] == "presentation_demo.collect")

        self.assertEqual(flat_entry["spec"]["presentation_schema"], PRESENTATION_SCHEMA)

    def test_tool_without_presentation_schema_gets_empty_dict(self):
        self.registry.register(PresentationCollector())

        plain_entry = next(item for item in self.registry.get_tools_flat() if item["tool"] == "presentation_demo.plain")

        self.assertEqual(plain_entry["spec"]["presentation_schema"], {})


if __name__ == "__main__":
    unittest.main()
