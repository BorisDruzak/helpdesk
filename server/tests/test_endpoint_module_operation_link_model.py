from __future__ import annotations

import pytest

from app.db.models import EndpointModuleOperationLink


pytestmark = pytest.mark.no_db


def test_module_operation_link_model_keeps_only_local_lifecycle_and_safe_evidence_fields() -> None:
    columns = set(EndpointModuleOperationLink.__table__.columns.keys())
    foreign_keys = {
        foreign_key.target_fullname
        for foreign_key in EndpointModuleOperationLink.__table__.foreign_keys
    }

    assert {
        "operation_id",
        "endpoint_operation_ref",
        "endpoint_device_ref",
        "module_key",
        "module_version",
        "safe_result_snapshot_json",
    } <= columns
    assert not {"recipe", "source", "command", "service_token", "authorization"} & columns
    assert foreign_keys == {"operations.operation_id"}
