import asyncio

from pc_agent.core.registry import ModuleRegistry
from pc_agent.modules.impl.inventory import (
    INVENTORY_COLLECT_OUTPUT_CONTRACT,
    INVENTORY_COLLECT_OUTPUT_SCHEMA,
    INVENTORY_COLLECT_PRESENTATION_SCHEMA,
    InventoryCollector,
)


def _collect() -> dict:
    return asyncio.run(InventoryCollector().collect())


def test_inventory_collect_returns_structured_snapshot():
    result = _collect()

    assert result["schema_version"] == "1.0"
    assert result["collected_at"]
    assert result["identity"]["hostname"]
    assert "current_user" in result["identity"]
    assert result["platform"]["os_name"]
    assert "memory_percent" in result["resources"]
    assert isinstance(result["resources"]["disks"], list)
    assert isinstance(result["network"]["interfaces"], list)
    assert isinstance(result["warnings"], list)


def test_inventory_collect_output_schema_exposes_path_picker_fields():
    props = INVENTORY_COLLECT_OUTPUT_SCHEMA["properties"]

    assert props["identity"]["properties"]["hostname"]["type"] == "string"
    assert props["identity"]["properties"]["current_user"]["type"] == "string"
    assert props["platform"]["properties"]["os_name"]["type"] == "string"
    assert props["resources"]["properties"]["cpu_percent"]["type"] == "number"
    disk_props = props["resources"]["properties"]["disks"]["items"]["properties"]
    assert disk_props["mount"]["type"] == "string"
    assert disk_props["used_percent"]["type"] == "number"
    iface_props = props["network"]["properties"]["interfaces"]["items"]["properties"]
    assert iface_props["name"]["type"] == "string"
    assert iface_props["ipv4"]["items"]["type"] == "string"
    assert props["printers"]["properties"]["default_printer"]["type"] == "string"
    app_props = props["software"]["properties"]["key_apps"]["items"]["properties"]
    assert app_props["name"]["type"] == "string"
    assert app_props["version"]["type"] == "string"


def test_inventory_collect_contract_and_presentation_schema_declare_device_card():
    assert INVENTORY_COLLECT_OUTPUT_CONTRACT["kind"] == "device.inventory.snapshot"
    assert INVENTORY_COLLECT_OUTPUT_CONTRACT["device_card"]["eligible"] is True
    assert "network" in INVENTORY_COLLECT_OUTPUT_CONTRACT["device_card"]["slots"]

    block_ids = {block.get("id") for block in INVENTORY_COLLECT_PRESENTATION_SCHEMA["blocks"]}
    assert {"identity", "resources", "os_agent", "disks", "network_interfaces"} <= block_ids
    assert INVENTORY_COLLECT_PRESENTATION_SCHEMA["fallback"]["show_raw_json"] is True


def test_inventory_collect_is_registered_with_schemas():
    registry = ModuleRegistry()
    registry.reset()
    try:
        registry.register(InventoryCollector())
        entry = next(item for item in registry.get_tools_flat() if item["tool"] == "inventory.collect")
    finally:
        registry.reset()

    spec = entry["spec"]
    assert spec["output_schema"] == INVENTORY_COLLECT_OUTPUT_SCHEMA
    assert spec["output_contract"]["kind"] == "device.inventory.snapshot"
    assert spec["presentation_schema"] == INVENTORY_COLLECT_PRESENTATION_SCHEMA


def test_inventory_collect_optional_collector_failure_adds_warning(monkeypatch):
    def fail_disks(self, warnings):
        raise RuntimeError("disk collector unavailable")

    monkeypatch.setattr(InventoryCollector, "_collect_disks", fail_disks)

    result = _collect()

    assert result["resources"]["disks"] == []
    assert any("disk collector unavailable" in item for item in result["warnings"])
