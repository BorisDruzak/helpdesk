"""Add Observer query-plan indexes for volume paths.

Revision ID: 128
Revises: 127
Create Date: 2026-06-24 17:40:00
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "128"
down_revision: Union[str, None] = "127"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OBSERVER_QUERY_PLAN_INDEXES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("ix_observer_traces_root_kind_started_at", "observer_traces", ("root_kind", "started_at")),
    ("ix_observer_traces_ticket_started_at", "observer_traces", ("ticket_id", "started_at")),
    ("ix_observer_traces_device_started_at", "observer_traces", ("device_id", "started_at")),
    ("ix_observer_traces_operation_started_at", "observer_traces", ("operation_id", "started_at")),
    ("ix_observer_traces_job_started_at", "observer_traces", ("job_id", "started_at")),
    ("ix_observer_spans_trace_started", "observer_spans", ("trace_id", "started_at")),
    ("ix_observer_spans_trace_tool", "observer_spans", ("trace_id", "tool_name")),
    ("ix_observer_spans_trace_module", "observer_spans", ("trace_id", "module_name")),
    ("ix_observer_spans_trace_event", "observer_spans", ("trace_id", "event_type")),
    ("ix_observer_error_occurrences_trace_kind", "observer_error_occurrences", ("trace_id", "error_kind")),
    ("ix_observer_error_occurrences_trace_signature", "observer_error_occurrences", ("trace_id", "error_signature")),
    (
        "ix_observer_error_occurrences_ticket_signature_created",
        "observer_error_occurrences",
        ("ticket_id", "error_signature", "created_at"),
    ),
)


def _has_index(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return False
    return any(str(index.get("name") or "") == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    for index_name, table_name, columns in OBSERVER_QUERY_PLAN_INDEXES:
        if not _has_index(table_name, index_name):
            op.create_index(index_name, table_name, list(columns), unique=False)


def downgrade() -> None:
    for index_name, table_name, _columns in reversed(OBSERVER_QUERY_PLAN_INDEXES):
        if _has_index(table_name, index_name):
            op.drop_index(index_name, table_name=table_name)
