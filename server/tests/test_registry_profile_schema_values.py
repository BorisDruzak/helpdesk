from types import SimpleNamespace

import pytest

from registry.profile_schema_service import (
    CUSTOM_STORAGE_PREFIX,
    ProfileSchemaValidationError,
    RequesterProfileSchemaService,
    default_profile_schema,
)

pytestmark = pytest.mark.no_db


def schema_for(kind, **extra):
    return RequesterProfileSchemaService(None).normalize_config({"custom_fields": [{
        "key": "test_value", "label": "Test value", "type": kind,
        "storage_target": CUSTOM_STORAGE_PREFIX + "test_value", **extra,
    }]}, strict=True)


def test_default_contact_options_and_required_minimum():
    schema = default_profile_schema()
    field = next(f for f in schema["fields"] if f["key"] == "preferred_contact_method")
    assert [o["value"] for o in field["options"]] == ["phone", "chat", "email"]
    assert {f["key"] for f in schema["fields"] if f["required"]} == {
        "full_name", "department_id", "location_id", "phone",
    }


@pytest.mark.parametrize("kind,value,expected", [
    ("text", " text ", "text"), ("textarea", "one\ntwo", "one\ntwo"),
    ("phone", "123", "123"), ("phone", "+7 (343) 123-45-67 доб. 12", "+7 (343) 123-45-67 доб. 12"),
    ("email", "user@example.test", "user@example.test"),
    ("url", "https://example.test/path", "https://example.test/path"),
    ("number", "12.5", 12.5), ("number", 0, 0),
    ("date", "2024-02-29", "2024-02-29"), ("checkbox", False, False),
])
def test_typed_values_roundtrip(kind, value, expected):
    service = RequesterProfileSchemaService(None)
    schema = schema_for(kind, required=True)
    details, values = service.validate_profile_payload(schema, {"custom_fields": {"test_value": value}})
    assert details == {}
    assert values == {"test_value": expected}
    assert type(values["test_value"]) is type(expected)
    person = SimpleNamespace(full_name="Test", department_id="d", location_id="l", phone="123",
                             metadata_json={"profile_custom_fields": values})
    assert service.completion_missing_fields(person, schema) == []


@pytest.mark.parametrize("kind,value", [
    ("text", {"value": "x"}), ("text", ["x"]), ("text", True),
    ("phone", "no phone"), ("email", "not-an-email"), ("email", "a@b\ncc@example.test"),
    ("url", "javascript:alert(1)"), ("url", "https://user:pass@example.test"),
    ("url", "https:///missing"), ("number", "nan"), ("number", True),
    ("number", "12oops"), ("date", "2025-02-29"), ("date", "20240101"),
    ("checkbox", "false"), ("checkbox", "true"), ("checkbox", 1),
])
def test_invalid_values_are_rejected_without_coercion(kind, value):
    details, values = RequesterProfileSchemaService(None).validate_profile_payload(
        schema_for(kind), {"custom_fields": {"test_value": value}})
    assert "custom_fields.test_value" in details
    assert "test_value" not in values


def test_length_and_pattern_are_enforced_without_truncation():
    service = RequesterProfileSchemaService(None)
    schema = schema_for("text", validation={"min_length": 2, "max_length": 4, "pattern": "[A-Z]+"})
    for value in ("A", "ABCDE", "ab"):
        assert service.validate_profile_payload(schema, {"custom_fields": {"test_value": value}})[0]
    assert service.validate_profile_payload(schema, {"custom_fields": {"test_value": "AB"}}) == ({}, {"test_value": "AB"})


@pytest.mark.parametrize("pattern", ["(a+)+$", "a*a*a*", "(?=a)a", "[", "a|b", "a{1,100000}"])
def test_schema_rejects_unsafe_or_unsupported_patterns(pattern):
    with pytest.raises(ProfileSchemaValidationError):
        schema_for("text", validation={"pattern": pattern})


@pytest.mark.parametrize("options", [[], ["a", "a"], [{"value": "a", "label": "A"}, {"value": "a", "label": "B"}], [{"value": "", "label": "A"}]])
def test_select_schema_requires_unique_nonempty_options(options):
    with pytest.raises(ProfileSchemaValidationError):
        schema_for("select", options=options)


def test_select_rejects_unknown_values_and_allows_explicit_clearing():
    service = RequesterProfileSchemaService(None)
    schema = schema_for("select", options=[{"value": "a", "label": "A"}])
    assert service.validate_profile_payload(schema, {"custom_fields": {"test_value": "other"}})[0]
    assert service.validate_profile_payload(schema, {"custom_fields": {"test_value": ""}}) == ({}, {"test_value": None})


def test_existing_invalid_values_are_preserved_and_reported_without_blocking_completion():
    service = RequesterProfileSchemaService(None)
    schema = schema_for("checkbox", required=True)
    person = SimpleNamespace(full_name="Test", department_id="d", location_id="l", phone="123",
                             metadata_json={"profile_custom_fields": {"test_value": "false", "retired": "keep"}})
    assert service.profile_custom_fields(person.metadata_json, schema) == {"test_value": "false"}
    assert service.profile_value_issues(person.metadata_json, schema)[0]["key"] == "test_value"
    assert person.metadata_json["profile_custom_fields"]["retired"] == "keep"
    assert service.completion_missing_fields(person, schema) == []


def test_schema_edits_preserve_used_fields_options_and_types():
    service = RequesterProfileSchemaService(None)
    before = schema_for("select", options=["old", "new"])
    metadata = [{"profile_custom_fields": {"test_value": "old"}}]
    for after in (schema_for("select", options=["new"]), schema_for("text"), default_profile_schema()):
        assert "test_value" in service.schema_change_issues(before, after, metadata)
    renamed = schema_for("select", options=[{"value": "old", "label": "Renamed"}, "new"])
    assert service.schema_change_issues(before, renamed, metadata) == {}


def test_custom_field_payload_must_be_an_object():
    details, _ = RequesterProfileSchemaService(None).validate_profile_payload(schema_for("text"), {"custom_fields": ["invalid"]})
    assert "custom_fields" in details


def test_builtin_values_cannot_be_silently_truncated_by_profile_write_limits():
    details, _ = RequesterProfileSchemaService(None).validate_profile_payload(default_profile_schema(), {"full_name": "a" * 241, "phone": "1" * 81})
    assert "full_name" in details
    assert "phone" in details
