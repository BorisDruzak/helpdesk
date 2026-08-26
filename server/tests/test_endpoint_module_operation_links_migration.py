from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa


pytestmark = pytest.mark.no_db
SERVER_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = (
    SERVER_ROOT / "app" / "db" / "migrations" / "versions" / "20260826_139_endpoint_module_operation_links.py"
)


def _migration_module() -> object:
    spec = importlib.util.spec_from_file_location("endpoint_module_operation_links_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_module_operation_links_migration_is_forward_only_after_endpoint_operations() -> None:
    module = _migration_module()

    assert module.revision == "139"
    assert module.down_revision == "138"
    with pytest.raises(RuntimeError, match="forward-only"):
        module.downgrade()


def test_module_operation_links_migration_declares_separate_safe_local_linkage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _migration_module()

    class _Recorder:
        def __init__(self) -> None:
            self.tables: dict[str, list[object]] = {}
            self.indexes: list[tuple[str, str, tuple[str, ...]]] = []

        def create_table(self, table_name: str, *items: object) -> None:
            self.tables[table_name] = list(items)

        def create_index(self, name: str, table_name: str, columns: list[str], **_kwargs: object) -> None:
            self.indexes.append((name, table_name, tuple(columns)))

    recorder = _Recorder()
    monkeypatch.setattr(module, "op", recorder)
    module.upgrade()

    items = recorder.tables["endpoint_module_operation_links"]
    columns = {item.name for item in items if isinstance(item, sa.Column)}
    assert columns == {
        "link_id",
        "operation_id",
        "endpoint_operation_ref",
        "endpoint_device_ref",
        "module_key",
        "module_version",
        "create_idempotency_key",
        "remote_status",
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
    assert not {"recipe", "source", "command", "service_token", "authorization"} & columns
    assert {name for name, table, _ in recorder.indexes if table == "endpoint_module_operation_links"} == {
        "ix_endpoint_module_operation_links_ready",
        "ix_endpoint_module_operation_links_lease_until",
    }
