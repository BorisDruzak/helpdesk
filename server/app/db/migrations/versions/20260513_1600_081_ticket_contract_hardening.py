"""ticket contract hardening

Revision ID: 081
Revises: 080
Create Date: 2026-05-13 16:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "081"
down_revision: Union[str, None] = "080"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CANONICAL_STATUS_SQL = (
    "'new', 'queued', 'assigned', 'in_progress', "
    "'waiting_on_user', 'waiting_on_internal_team', 'waiting_on_vendor', "
    "'waiting_on_approval', 'scheduled', 'resolved', 'closed', 'canceled'"
)


def upgrade() -> None:
    # Legacy backfill: triaged was historically a queue/assignment marker, not active work.
    op.execute(
        """
        UPDATE tickets
        SET status = CASE
            WHEN lower(btrim(status)) = 'triaged'
                 AND NULLIF(btrim(COALESCE(assignee_id, '')), '') IS NOT NULL
                THEN 'assigned'
            WHEN lower(btrim(status)) = 'triaged'
                THEN 'queued'
            WHEN lower(btrim(status)) IN ('in progress', 'in-progress', 'open')
                THEN 'in_progress'
            WHEN lower(btrim(status)) IN ('waiting on user', 'waiting-for-user', 'waiting_user')
                THEN 'waiting_on_user'
            WHEN lower(btrim(status)) IN ('waiting on internal team', 'waiting_internal')
                THEN 'waiting_on_internal_team'
            WHEN lower(btrim(status)) IN ('waiting on vendor', 'waiting_vendor')
                THEN 'waiting_on_vendor'
            WHEN lower(btrim(status)) IN ('waiting on approval', 'waiting_approval')
                THEN 'waiting_on_approval'
            WHEN lower(btrim(status)) = 'cancelled'
                THEN 'canceled'
            WHEN lower(btrim(status)) IN ('queue', 'queued')
                THEN 'queued'
            WHEN lower(btrim(status)) IN ('new ticket', 'new_request', 'newrequest')
                THEN 'new'
            ELSE status
        END
        WHERE status IS NOT NULL
        """
    )

    # Prefer stable device-bound requester identity for legacy rows; use ticket namespace only as last resort.
    op.execute(
        """
        UPDATE tickets
        SET requester_id = CASE
            WHEN NULLIF(btrim(COALESCE(device_id, '')), '') IS NOT NULL
                THEN 'device:' || btrim(device_id)
            ELSE 'legacy:' || ticket_id
        END
        WHERE NULLIF(btrim(COALESCE(requester_id, '')), '') IS NULL
        """
    )

    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM tickets
                WHERE status NOT IN ({CANONICAL_STATUS_SQL})
            ) THEN
                RAISE EXCEPTION 'tickets.status contains non-canonical values';
            END IF;
            IF EXISTS (
                SELECT 1
                FROM tickets
                WHERE NULLIF(btrim(COALESCE(requester_id, '')), '') IS NULL
            ) THEN
                RAISE EXCEPTION 'tickets.requester_id contains null or blank values';
            END IF;
        END $$;
        """
    )

    op.alter_column(
        "tickets",
        "requester_id",
        existing_type=sa.Text(),
        nullable=False,
    )
    op.create_check_constraint(
        "ck_tickets_status_canonical",
        "tickets",
        f"status IN ({CANONICAL_STATUS_SQL})",
    )
    op.create_check_constraint(
        "ck_tickets_requester_id_non_empty",
        "tickets",
        "btrim(requester_id) <> ''",
    )
    op.create_check_constraint(
        "ck_tickets_sla_priority_present",
        "tickets",
        "sla_policy_id IS NULL OR priority IS NOT NULL",
    )
    op.create_index(
        "ix_ticket_events_ticket_created_id",
        "ticket_events",
        ["ticket_id", "created_at", "id"],
    )
    op.create_index(
        "ix_ticket_events_ticket_type_created_id",
        "ticket_events",
        ["ticket_id", "event_type", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_ticket_events_ticket_type_created_id", table_name="ticket_events")
    op.drop_index("ix_ticket_events_ticket_created_id", table_name="ticket_events")
    op.drop_constraint("ck_tickets_sla_priority_present", "tickets", type_="check")
    op.drop_constraint("ck_tickets_requester_id_non_empty", "tickets", type_="check")
    op.drop_constraint("ck_tickets_status_canonical", "tickets", type_="check")
    op.alter_column(
        "tickets",
        "requester_id",
        existing_type=sa.Text(),
        nullable=True,
    )
