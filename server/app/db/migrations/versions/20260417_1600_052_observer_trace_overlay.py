"""observer trace overlay tables

Revision ID: 052
Revises: 051
Create Date: 2026-04-17 16:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "052"
down_revision: Union[str, None] = "051"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "observer_traces",
        sa.Column("trace_id", sa.String(length=36), nullable=False),
        sa.Column("root_span_id", sa.String(length=36), nullable=True),
        sa.Column("root_kind", sa.String(length=64), nullable=True),
        sa.Column("ticket_id", sa.String(length=36), nullable=True),
        sa.Column("device_id", sa.String(length=36), nullable=True),
        sa.Column("operation_id", sa.String(length=36), nullable=True),
        sa.Column("job_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="running"),
        sa.Column("started_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("finished_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("span_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attrs_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("trace_id"),
    )
    op.create_index("ix_observer_traces_root_kind", "observer_traces", ["root_kind"])
    op.create_index("ix_observer_traces_ticket_id", "observer_traces", ["ticket_id"])
    op.create_index("ix_observer_traces_device_id", "observer_traces", ["device_id"])
    op.create_index("ix_observer_traces_operation_id", "observer_traces", ["operation_id"])
    op.create_index("ix_observer_traces_job_id", "observer_traces", ["job_id"])
    op.create_index("ix_observer_traces_started_at", "observer_traces", ["started_at"])
    op.create_index("ix_observer_traces_status_started_at", "observer_traces", ["status", "started_at"])

    op.create_table(
        "observer_spans",
        sa.Column("span_id", sa.String(length=36), nullable=False),
        sa.Column("trace_id", sa.String(length=36), nullable=False),
        sa.Column("parent_span_id", sa.String(length=36), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_ref", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False, server_default="internal"),
        sa.Column("component", sa.String(length=64), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=True),
        sa.Column("module_name", sa.String(length=128), nullable=True),
        sa.Column("tool_name", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="ok"),
        sa.Column("started_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("finished_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("attrs_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["trace_id"], ["observer_traces.trace_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("span_id"),
        sa.UniqueConstraint("trace_id", "source_type", "source_ref", name="uq_observer_spans_trace_source"),
    )
    op.create_index("ix_observer_spans_trace_id", "observer_spans", ["trace_id"])
    op.create_index("ix_observer_spans_parent_span_id", "observer_spans", ["parent_span_id"])
    op.create_index("ix_observer_spans_component", "observer_spans", ["component"])
    op.create_index("ix_observer_spans_module_name", "observer_spans", ["module_name"])
    op.create_index("ix_observer_spans_started_at", "observer_spans", ["started_at"])
    op.create_index("ix_observer_spans_trace_parent", "observer_spans", ["trace_id", "parent_span_id"])
    op.create_index("ix_observer_spans_status_started_at", "observer_spans", ["status", "started_at"])

    op.create_table(
        "observer_span_links",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("span_id", sa.String(length=36), nullable=False),
        sa.Column("linked_trace_id", sa.String(length=36), nullable=True),
        sa.Column("linked_span_id", sa.String(length=36), nullable=True),
        sa.Column("reason", sa.String(length=64), nullable=False),
        sa.Column("attrs_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["span_id"], ["observer_spans.span_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "span_id",
            "linked_trace_id",
            "linked_span_id",
            "reason",
            name="uq_observer_span_links_target_reason",
        ),
    )
    op.create_index("ix_observer_span_links_span_id", "observer_span_links", ["span_id"])
    op.create_index("ix_observer_span_links_linked_trace_id", "observer_span_links", ["linked_trace_id"])
    op.create_index("ix_observer_span_links_linked_span_id", "observer_span_links", ["linked_span_id"])

    op.create_table(
        "observer_error_signatures",
        sa.Column("error_signature", sa.String(length=160), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("component", sa.String(length=64), nullable=True),
        sa.Column("module_name", sa.String(length=128), nullable=True),
        sa.Column("tool_name", sa.Text(), nullable=True),
        sa.Column("error_kind", sa.String(length=64), nullable=True),
        sa.Column("exception_type", sa.String(length=128), nullable=True),
        sa.Column("failure_stage", sa.String(length=64), nullable=True),
        sa.Column("message_sample", sa.Text(), nullable=True),
        sa.Column("first_seen_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("last_seen_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("occurrences_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("affected_devices_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attrs_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.PrimaryKeyConstraint("error_signature"),
    )
    op.create_index("ix_observer_error_signatures_component", "observer_error_signatures", ["component"])
    op.create_index("ix_observer_error_signatures_module_name", "observer_error_signatures", ["module_name"])
    op.create_index("ix_observer_error_signatures_error_kind", "observer_error_signatures", ["error_kind"])
    op.create_index("ix_observer_error_signatures_last_seen_at", "observer_error_signatures", ["last_seen_at"])
    op.create_index("ix_observer_error_signatures_component_seen", "observer_error_signatures", ["component", "last_seen_at"])
    op.create_index("ix_observer_error_signatures_module_seen", "observer_error_signatures", ["module_name", "last_seen_at"])

    op.create_table(
        "observer_error_occurrences",
        sa.Column("occurrence_id", sa.BigInteger(), nullable=False),
        sa.Column("trace_id", sa.String(length=36), nullable=False),
        sa.Column("span_id", sa.String(length=36), nullable=True),
        sa.Column("error_signature", sa.String(length=160), nullable=False),
        sa.Column("device_id", sa.String(length=36), nullable=True),
        sa.Column("ticket_id", sa.String(length=36), nullable=True),
        sa.Column("operation_id", sa.String(length=36), nullable=True),
        sa.Column("component", sa.String(length=64), nullable=True),
        sa.Column("module_name", sa.String(length=128), nullable=True),
        sa.Column("tool_name", sa.Text(), nullable=True),
        sa.Column("error_kind", sa.String(length=64), nullable=True),
        sa.Column("exception_type", sa.String(length=128), nullable=True),
        sa.Column("failure_stage", sa.String(length=64), nullable=True),
        sa.Column("severity", sa.String(length=16), nullable=False, server_default="error"),
        sa.Column("message_norm", sa.Text(), nullable=True),
        sa.Column("stack_hash", sa.String(length=64), nullable=True),
        sa.Column("attrs_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["trace_id"], ["observer_traces.trace_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["span_id"], ["observer_spans.span_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["error_signature"], ["observer_error_signatures.error_signature"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("occurrence_id"),
    )
    op.create_index("ix_observer_error_occurrences_trace_id", "observer_error_occurrences", ["trace_id"])
    op.create_index("ix_observer_error_occurrences_span_id", "observer_error_occurrences", ["span_id"])
    op.create_index("ix_observer_error_occurrences_error_signature", "observer_error_occurrences", ["error_signature"])
    op.create_index("ix_observer_error_occurrences_device_id", "observer_error_occurrences", ["device_id"])
    op.create_index("ix_observer_error_occurrences_ticket_id", "observer_error_occurrences", ["ticket_id"])
    op.create_index("ix_observer_error_occurrences_operation_id", "observer_error_occurrences", ["operation_id"])
    op.create_index("ix_observer_error_occurrences_component", "observer_error_occurrences", ["component"])
    op.create_index("ix_observer_error_occurrences_module_name", "observer_error_occurrences", ["module_name"])
    op.create_index("ix_observer_error_occurrences_created_at", "observer_error_occurrences", ["created_at"])
    op.create_index(
        "ix_observer_error_occurrences_signature_created",
        "observer_error_occurrences",
        ["error_signature", "created_at"],
    )
    op.create_index(
        "ix_observer_error_occurrences_trace_created",
        "observer_error_occurrences",
        ["trace_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_observer_error_occurrences_trace_created", table_name="observer_error_occurrences")
    op.drop_index("ix_observer_error_occurrences_signature_created", table_name="observer_error_occurrences")
    op.drop_index("ix_observer_error_occurrences_created_at", table_name="observer_error_occurrences")
    op.drop_index("ix_observer_error_occurrences_module_name", table_name="observer_error_occurrences")
    op.drop_index("ix_observer_error_occurrences_component", table_name="observer_error_occurrences")
    op.drop_index("ix_observer_error_occurrences_operation_id", table_name="observer_error_occurrences")
    op.drop_index("ix_observer_error_occurrences_ticket_id", table_name="observer_error_occurrences")
    op.drop_index("ix_observer_error_occurrences_device_id", table_name="observer_error_occurrences")
    op.drop_index("ix_observer_error_occurrences_error_signature", table_name="observer_error_occurrences")
    op.drop_index("ix_observer_error_occurrences_span_id", table_name="observer_error_occurrences")
    op.drop_index("ix_observer_error_occurrences_trace_id", table_name="observer_error_occurrences")
    op.drop_table("observer_error_occurrences")

    op.drop_index("ix_observer_error_signatures_module_seen", table_name="observer_error_signatures")
    op.drop_index("ix_observer_error_signatures_component_seen", table_name="observer_error_signatures")
    op.drop_index("ix_observer_error_signatures_last_seen_at", table_name="observer_error_signatures")
    op.drop_index("ix_observer_error_signatures_error_kind", table_name="observer_error_signatures")
    op.drop_index("ix_observer_error_signatures_module_name", table_name="observer_error_signatures")
    op.drop_index("ix_observer_error_signatures_component", table_name="observer_error_signatures")
    op.drop_table("observer_error_signatures")

    op.drop_index("ix_observer_span_links_linked_span_id", table_name="observer_span_links")
    op.drop_index("ix_observer_span_links_linked_trace_id", table_name="observer_span_links")
    op.drop_index("ix_observer_span_links_span_id", table_name="observer_span_links")
    op.drop_table("observer_span_links")

    op.drop_index("ix_observer_spans_status_started_at", table_name="observer_spans")
    op.drop_index("ix_observer_spans_trace_parent", table_name="observer_spans")
    op.drop_index("ix_observer_spans_started_at", table_name="observer_spans")
    op.drop_index("ix_observer_spans_module_name", table_name="observer_spans")
    op.drop_index("ix_observer_spans_component", table_name="observer_spans")
    op.drop_index("ix_observer_spans_parent_span_id", table_name="observer_spans")
    op.drop_index("ix_observer_spans_trace_id", table_name="observer_spans")
    op.drop_table("observer_spans")

    op.drop_index("ix_observer_traces_status_started_at", table_name="observer_traces")
    op.drop_index("ix_observer_traces_started_at", table_name="observer_traces")
    op.drop_index("ix_observer_traces_job_id", table_name="observer_traces")
    op.drop_index("ix_observer_traces_operation_id", table_name="observer_traces")
    op.drop_index("ix_observer_traces_device_id", table_name="observer_traces")
    op.drop_index("ix_observer_traces_ticket_id", table_name="observer_traces")
    op.drop_index("ix_observer_traces_root_kind", table_name="observer_traces")
    op.drop_table("observer_traces")
