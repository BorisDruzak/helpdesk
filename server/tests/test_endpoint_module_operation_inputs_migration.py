from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa


pytestmark = pytest.mark.no_db
PATH = Path(__file__).resolve().parents[1] / "app" / "db" / "migrations" / "versions" / "20260826_140_endpoint_module_operation_inputs.py"


def _module() -> object:
    spec = importlib.util.spec_from_file_location("endpoint_module_operation_inputs", PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_module_operation_inputs_migration_is_forward_only_after_link_table() -> None:
    module = _module()

    assert module.revision == "140"
    assert module.down_revision == "139"
    with pytest.raises(RuntimeError, match="forward-only"):
        module.downgrade()


def test_module_operation_inputs_migration_adds_only_safe_replay_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _module()

    class _Recorder:
        def __init__(self) -> None:
            self.columns: list[tuple[str, sa.Column]] = []
            self.indexes: list[tuple[str, str, tuple[str, ...], dict[str, object]]] = []

        def add_column(self, table_name: str, column: sa.Column) -> None:
            self.columns.append((table_name, column))

        def create_index(self, name: str, table_name: str, columns: list[str], **kwargs: object) -> None:
            self.indexes.append((name, table_name, tuple(columns), kwargs))

    recorder = _Recorder()
    monkeypatch.setattr(module, "op", recorder)
    module.upgrade()

    assert [(table, column.name) for table, column in recorder.columns] == [
        ("endpoint_module_operation_links", "inputs_snapshot_json"),
        ("endpoint_module_operation_links", "caller_actor_id"),
        ("endpoint_module_operation_links", "caller_idempotency_key"),
    ]
    assert recorder.indexes[0][:3] == (
        "uq_endpoint_module_operation_links_caller_key",
        "endpoint_module_operation_links",
        ("caller_actor_id", "caller_idempotency_key"),
    )
    assert recorder.indexes[0][3]["unique"] is True
