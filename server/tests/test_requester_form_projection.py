"""Repeated requester projection must preserve the map's source questions."""
from copy import deepcopy

import pytest

from tickets.form_catalog import requester_safe_form_pack, validate_form_pack_schema
from tickets.form_defaults import build_default_ticket_form_pack
from tickets.request_scenario_conversion import convert_form

pytestmark = pytest.mark.no_db


@pytest.mark.parametrize("key", ["agent_binding_help", "profile_completion_help"])
def test_setup_help_source_requester_and_converted_map_have_the_same_fields(key):
    pack = validate_form_pack_schema(build_default_ticket_form_pack())
    original = next(form for form in pack["forms"] if form["key"] == key)
    projected = next(form for form in requester_safe_form_pack(pack)["forms"] if form["key"] == key)
    assert projected["fields"] == original["fields"]
    assert projected["priority_policy"] == {}
    assert validate_form_pack_schema(deepcopy(pack)) == pack
    definition = convert_form({"full_code": "setup." + key, "service_code": "setup", "public_title": original["title"],
                               "request_template_key": key}, original)
    assert [field.key for field in definition.blocks[0].fields] == [field["key"] for field in projected["fields"]]


def test_missing_priority_policy_keeps_legacy_required_processing_questions():
    raw = {"pack_key": "request_forms", "title": "Old", "version": "1", "forms": [
        {"key": "old", "title": "Old", "fields": [{"key": "detail", "label": "Detail", "type": "text"}]}]}
    form = validate_form_pack_schema(raw)["forms"][0]
    assert {"impact_scope", "work_continuity"} <= {field["key"] for field in form["fields"]}
    assert form["priority_policy"]
