from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


pytestmark = pytest.mark.no_db
PATH = Path(__file__).resolve().parents[1] / "app" / "db" / "migrations" / "versions" / "20260826_141_nullable_endpoint_module_operation_device.py"


def test_module_operation_nullable_device_migration_expands_only_endpoint_facade_exception() -> None:
    spec = importlib.util.spec_from_file_location("endpoint_module_nullable_device", PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.revision == "141"
    assert module.down_revision == "140"
    with pytest.raises(RuntimeError, match="forward-only"):
        module.downgrade()


def test_module_operation_nullable_device_migration_uses_postgresql_safe_constraint_name() -> None:
    spec = importlib.util.spec_from_file_location("endpoint_module_nullable_device", PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class _Operations:
        def __init__(self) -> None:
            self.created: list[tuple[str, str, str]] = []

        def drop_constraint(self, *_args: object, **_kwargs: object) -> None:
            return None

        def create_check_constraint(self, name: str, table: str, condition: str) -> None:
            self.created.append((name, table, condition))

    operations = _Operations()
    module.op = operations
    module.upgrade()

    name, table, condition = operations.created[0]
    assert len(name) <= 63
    assert table == "operations"
    assert condition == "kind IN ('endpoint_operation', 'endpoint_module_operation') OR device_id IS NOT NULL"
