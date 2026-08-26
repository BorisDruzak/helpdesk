from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa


pytestmark = pytest.mark.no_db
PATH = Path(__file__).resolve().parents[1] / "app" / "db" / "migrations" / "versions" / "20260826_142_unify_endpoint_module_operation_links.py"


def _module() -> object:
    spec = importlib.util.spec_from_file_location("endpoint_module_link_unification", PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_module_link_unification_is_forward_only() -> None:
    module = _module()

    assert module.revision == "142"
    assert module.down_revision == "141"
    with pytest.raises(RuntimeError, match="forward-only"):
        module.downgrade()


def test_module_link_unification_extends_existing_facade_link_and_removes_staging_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()

    class _Recorder:
        def __init__(self) -> None:
            self.columns: list[tuple[str, sa.Column]] = []
            self.dropped_constraints: list[tuple[str, str]] = []
            self.created_constraints: list[tuple[str, str, str]] = []
            self.dropped_tables: list[str] = []

        def add_column(self, table: str, column: sa.Column) -> None:
            self.columns.append((table, column))

        def drop_constraint(self, name: str, table: str, **_kwargs: object) -> None:
            self.dropped_constraints.append((name, table))

        def create_check_constraint(self, name: str, table: str, condition: str) -> None:
            self.created_constraints.append((name, table, condition))

        def drop_table(self, table: str) -> None:
            self.dropped_tables.append(table)

    recorder = _Recorder()
    monkeypatch.setattr(module, "op", recorder)
    module.upgrade()

    assert {table for table, _column in recorder.columns} == {"endpoint_operation_links"}
    assert {column.name for _table, column in recorder.columns} == {
        "module_key", "module_version", "module_spec_sha256", "module_inputs_snapshot_json",
        "safe_module_snapshot_json",
    }
    assert recorder.dropped_tables == ["endpoint_module_operation_links"]
