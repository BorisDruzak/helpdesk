from __future__ import annotations

import pytest

from inventory.service import _inventory_builtin_descriptor


@pytest.mark.no_db
def test_inventory_builtin_descriptor_supplies_schema_and_slots():
    descriptor = _inventory_builtin_descriptor("inventory.collect")

    assert descriptor is not None
    assert descriptor.presentation_schema["version"] == "1.0"
    assert descriptor.output_contract["kind"] == "device.inventory.snapshot"
    assert "identity" in descriptor.output_contract["device_card"]["slots"]


@pytest.mark.no_db
def test_inventory_builtin_descriptor_does_not_import_agent_implementation(monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "pc_agent.modules.impl.inventory", None)

    descriptor = _inventory_builtin_descriptor("inventory.collect")

    assert descriptor is not None
    assert descriptor.output_contract["kind"] == "device.inventory.snapshot"
