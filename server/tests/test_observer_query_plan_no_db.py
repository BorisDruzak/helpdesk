from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from app.db.models import ObserverErrorOccurrence, ObserverSpan, ObserverTrace


pytestmark = pytest.mark.no_db

SERVER_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = SERVER_ROOT / "app" / "db" / "migrations" / "versions" / "20260624_128_observer_query_plan_indexes.py"

REQUIRED_MODEL_INDEXES: dict[str, dict[str, tuple[str, ...]]] = {
    ObserverTrace.__tablename__: {
        "ix_observer_traces_status_started_at": ("status", "started_at"),
        "ix_observer_traces_root_kind_started_at": ("root_kind", "started_at"),
        "ix_observer_traces_ticket_started_at": ("ticket_id", "started_at"),
        "ix_observer_traces_device_started_at": ("device_id", "started_at"),
        "ix_observer_traces_operation_started_at": ("operation_id", "started_at"),
        "ix_observer_traces_job_started_at": ("job_id", "started_at"),
    },
    ObserverSpan.__tablename__: {
        "ix_observer_spans_trace_started": ("trace_id", "started_at"),
        "ix_observer_spans_trace_tool": ("trace_id", "tool_name"),
        "ix_observer_spans_trace_module": ("trace_id", "module_name"),
        "ix_observer_spans_trace_event": ("trace_id", "event_type"),
    },
    ObserverErrorOccurrence.__tablename__: {
        "ix_observer_error_occurrences_trace_created": ("trace_id", "created_at"),
        "ix_observer_error_occurrences_trace_kind": ("trace_id", "error_kind"),
        "ix_observer_error_occurrences_trace_signature": ("trace_id", "error_signature"),
        "ix_observer_error_occurrences_ticket_signature_created": (
            "ticket_id",
            "error_signature",
            "created_at",
        ),
    },
}

NEW_QUERY_PLAN_INDEXES: dict[str, tuple[str, tuple[str, ...]]] = {
    index_name: (table_name, columns)
    for table_name, indexes in REQUIRED_MODEL_INDEXES.items()
    for index_name, columns in indexes.items()
    if index_name
    not in {
        "ix_observer_traces_status_started_at",
        "ix_observer_error_occurrences_trace_created",
    }
}


def _table_index_columns(model: type) -> dict[str, tuple[str, ...]]:
    return {index.name or "": tuple(column.name for column in index.columns) for index in model.__table__.indexes}


def _load_query_plan_migration():
    assert MIGRATION_PATH.exists(), f"missing Observer query-plan migration: {MIGRATION_PATH.name}"
    spec = importlib.util.spec_from_file_location("observer_query_plan_indexes_migration", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_observer_volume_paths_have_composite_indexes_in_model_metadata() -> None:
    model_indexes = {
        ObserverTrace.__tablename__: _table_index_columns(ObserverTrace),
        ObserverSpan.__tablename__: _table_index_columns(ObserverSpan),
        ObserverErrorOccurrence.__tablename__: _table_index_columns(ObserverErrorOccurrence),
    }

    missing: list[str] = []
    mismatched: list[str] = []
    for table_name, required_indexes in REQUIRED_MODEL_INDEXES.items():
        for index_name, required_columns in required_indexes.items():
            actual_columns = model_indexes[table_name].get(index_name)
            if actual_columns is None:
                missing.append(f"{table_name}.{index_name}{required_columns}")
            elif actual_columns != required_columns:
                mismatched.append(f"{table_name}.{index_name}: expected {required_columns}, got {actual_columns}")

    assert not missing and not mismatched, {"missing": missing, "mismatched": mismatched}


def test_observer_query_plan_migration_creates_required_indexes(monkeypatch: pytest.MonkeyPatch) -> None:
    migration = _load_query_plan_migration()
    created: list[tuple[str, str, tuple[str, ...]]] = []

    class FakeOp:
        @staticmethod
        def create_index(index_name: str, table_name: str, columns: list[str], unique: bool = False) -> None:
            assert unique is False
            created.append((index_name, table_name, tuple(columns)))

    monkeypatch.setattr(migration, "op", FakeOp)
    monkeypatch.setattr(migration, "_has_index", lambda table_name, index_name: False)

    migration.upgrade()

    created_by_name = {index_name: (table_name, columns) for index_name, table_name, columns in created}
    assert created_by_name == NEW_QUERY_PLAN_INDEXES
