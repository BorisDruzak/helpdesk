from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa


SERVER_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = SERVER_ROOT / "app" / "db" / "migrations" / "versions" / "20260817_135_endpoint_operation_links.py"
CORRELATION_MIGRATION_PATH = (
    SERVER_ROOT / "app" / "db" / "migrations" / "versions" / "20260817_136_endpoint_operation_correlation_ref.py"
)
CALLER_IDEMPOTENCY_MIGRATION_PATH = (
    SERVER_ROOT / "app" / "db" / "migrations" / "versions" / "20260820_137_endpoint_caller_idempotency.py"
)


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


@pytest.mark.no_db
def test_endpoint_operation_correlation_migration_is_forward_only_and_additive(monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "endpoint_operation_correlation_migration", CORRELATION_MIGRATION_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class _Recorder:
        def __init__(self) -> None:
            self.columns: list[tuple[str, sa.Column]] = []

        def add_column(self, table_name: str, column: sa.Column) -> None:
            self.columns.append((table_name, column))

    recorder = _Recorder()
    monkeypatch.setattr(module, "op", recorder)
    module.upgrade()

    assert module.revision == "136"
    assert module.down_revision == "135"
    assert [(table, column.name) for table, column in recorder.columns] == [
        ("endpoint_operation_links", "correlation_ref")
    ]
    column = recorder.columns[0][1]
    assert isinstance(column.type, sa.String)
    assert column.type.length == 128
    assert column.nullable is True
    with pytest.raises(RuntimeError, match="forward-only"):
        module.downgrade()


@pytest.mark.no_db
def test_endpoint_caller_idempotency_migration_is_actor_scoped_and_forward_only(monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "endpoint_caller_idempotency_migration", CALLER_IDEMPOTENCY_MIGRATION_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class _Recorder:
        def __init__(self) -> None:
            self.columns: list[tuple[str, sa.Column]] = []
            self.indexes: list[tuple[str, str, tuple[str, ...], dict]] = []

        def add_column(self, table_name: str, column: sa.Column) -> None:
            self.columns.append((table_name, column))

        def create_index(self, name: str, table_name: str, columns: list[str], **kwargs) -> None:
            self.indexes.append((name, table_name, tuple(columns), kwargs))

    recorder = _Recorder()
    monkeypatch.setattr(module, "op", recorder)
    module.upgrade()

    assert module.revision == "137"
    assert module.down_revision == "136"
    assert [(table, column.name) for table, column in recorder.columns] == [
        ("endpoint_operation_links", "caller_actor_id"),
        ("endpoint_operation_links", "caller_idempotency_key"),
    ]
    assert recorder.indexes[0][:3] == (
        "uq_endpoint_operation_links_caller_key",
        "endpoint_operation_links",
        ("caller_actor_id", "caller_idempotency_key"),
    )
    assert recorder.indexes[0][3]["unique"] is True
    with pytest.raises(RuntimeError, match="forward-only"):
        module.downgrade()
