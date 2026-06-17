from __future__ import annotations

from pathlib import Path
import importlib.util
import sys


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "reset_test_data.py"
SPEC = importlib.util.spec_from_file_location("reset_test_data", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
reset_test_data = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = reset_test_data
SPEC.loader.exec_module(reset_test_data)


def test_clear_profile_preserves_forms_catalog_and_config() -> None:
    actual_tables = {
        "ticket_form_packs",
        "form_builder_drafts",
        "form_schemas",
        "form_fields",
        "form_conditions",
        "request_templates",
        "helpdesk_services",
        "helpdesk_service_offerings",
        "helpdesk_service_catalog_audit",
        "request_studio_publish_tokens",
        "ticket_queues",
        "ticket_sla_policies",
        "modules",
        "agent_builds",
        "ui_users",
        "tickets",
        "ticket_events",
        "knowledge_items",
        "knowledge_spaces",
        "registry_people",
        "device_events",
        "devices",
    }

    clear_tables = reset_test_data.build_clear_tables(actual_tables)

    assert "tickets" in clear_tables
    assert "ticket_events" in clear_tables
    assert "knowledge_items" in clear_tables
    assert "registry_people" in clear_tables
    assert "device_events" in clear_tables
    assert "devices" in clear_tables
    assert "ticket_form_packs" not in clear_tables
    assert "form_builder_drafts" not in clear_tables
    assert "form_schemas" not in clear_tables
    assert "request_templates" not in clear_tables
    assert "helpdesk_services" not in clear_tables
    assert "ticket_queues" not in clear_tables
    assert "modules" not in clear_tables
    assert "agent_builds" not in clear_tables
    assert "ui_users" not in clear_tables


def test_delete_order_places_children_before_parents() -> None:
    clear_tables = {"tickets", "ticket_events", "operations", "consent_decisions"}
    foreign_keys = [
        reset_test_data.ForeignKeyRef("ticket_events", "tickets", "CASCADE"),
        reset_test_data.ForeignKeyRef("operations", "tickets", "CASCADE"),
        reset_test_data.ForeignKeyRef("consent_decisions", "operations", "CASCADE"),
    ]

    order = reset_test_data.build_delete_order(clear_tables, foreign_keys)

    assert order.index("ticket_events") < order.index("tickets")
    assert order.index("operations") < order.index("tickets")
    assert order.index("consent_decisions") < order.index("operations")
