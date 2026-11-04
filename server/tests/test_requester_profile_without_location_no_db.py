from types import SimpleNamespace

import pytest

from registry.profile_schema_service import RequesterProfileSchemaService
from requester.identity_service import RequesterIdentityResolver

pytestmark = pytest.mark.no_db


def test_legacy_profile_schema_no_longer_requires_a_location():
    service = RequesterProfileSchemaService(None)
    schema = service.normalize_config({"field_overrides": {
        "location_id": {"visible": True, "required": True},
    }}, strict=False)
    location = next(field for field in schema["fields"] if field["key"] == "location_id")
    assert location["visible"] is False
    assert location["required"] is False
    assert next(field for field in schema["fields"] if field["key"] == "department_id")["label"] == "Отдел"
    person = SimpleNamespace(full_name="Иван Петров", department_id="dept-real", phone="1234", location_id=None, metadata_json={})
    assert service.completion_missing_fields(person, schema) == []


def test_fallback_profile_completion_is_ready_without_location():
    resolver = RequesterIdentityResolver(None)
    person = SimpleNamespace(full_name="Иван Петров", department_id="dept-real", phone="1234", location_id=None)
    result = resolver.build_profile_completion(person)
    assert result["complete"] is True
    assert not result["blocks"]["ticket_create"]
