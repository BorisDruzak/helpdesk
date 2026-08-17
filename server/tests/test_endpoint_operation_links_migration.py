from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa


SERVER_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = SERVER_ROOT / "app" / "db" / "migrations" / "versions" / "20260817_135_endpoint_operation_links.py"


@pytest.mark.no_db
def test_endpoint_operation_links_migration_is_forward_after_revision_134():
    spec = importlib.util.spec_from_file_location("endpoint_operation_links_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.revision == "135"
    assert module.down_revision == "134"
    assert module.downgrade.__doc__ is not None


@pytest.mark.no_db
def test_endpoint_operation_links_migration_declares_only_additive_safe_schema(monkeypatch):
    spec = importlib.util.spec_from_file_location("endpoint_operation_links_migration_schema", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class _Recorder:
        def __init__(self) -> None:
            self.added_columns: list[tuple[str, str]] = []
            self.tables: dict[str, list[object]] = {}
            self.indexes: list[tuple[str, str, tuple[str, ...]]] = []

        def add_column(self, table_name: str, column: sa.Column) -> None:
            self.added_columns.append((table_name, column.name))

        def create_table(self, table_name: str, *items: object) -> None:
            self.tables[table_name] = list(items)

        def create_index(self, name: str, table_name: str, columns: list[str], **_kwargs) -> None:
            self.indexes.append((name, table_name, tuple(columns)))

    recorder = _Recorder()
    monkeypatch.setattr(module, "op", recorder)
    module.upgrade()

    assert recorder.added_columns == [
        ("tickets", "endpoint_device_ref"),
        ("tickets", "endpoint_device_snapshot_json"),
    ]
    assert {name for name, table, _ in recorder.indexes if table == "tickets"} == {
        "ix_tickets_endpoint_device_ref"
    }
    items = recorder.tables["endpoint_operation_links"]
    columns = {item.name for item in items if isinstance(item, sa.Column)}
    assert columns == {
        "link_id",
        "operation_id",
        "endpoint_operation_ref",
        "endpoint_device_ref",
        "capability_code",
        "create_idempotency_key",
        "remote_status",
        "diagnostic_session_id",
        "diagnostic_step_id",
        "safe_result_snapshot_json",
        "last_error_code",
        "attempt_count",
        "next_attempt_at",
        "lease_owner",
        "lease_until",
        "last_synced_at",
        "created_at",
        "updated_at",
    }
    assert {name for name, table, _ in recorder.indexes if table == "endpoint_operation_links"} == {
        "ix_endpoint_operation_links_ready",
        "ix_endpoint_operation_links_lease_until",
    }
