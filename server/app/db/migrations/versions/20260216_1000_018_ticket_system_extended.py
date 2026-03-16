"""ticket system: extend tickets, add queues/categories/SLA/worklogs/links/watchers

Revision ID: 018
Revises: 017
Create Date: 2026-02-16 10:00:00.000000

Целевая модель тикетной системы (Этап 1):
- Расширение tickets: type, priority, impact, urgency, requester/assignee/queue,
  category/service/subcategory, resolved_at/closed_at, SLA timers, tags, custom_fields,
  external_ref, resolution_code, root_cause, reopen_count, parent_ticket_id.
- Новые таблицы: ticket_queues, ticket_queue_members, ticket_categories,
  ticket_watchers, ticket_links, ticket_worklogs, ticket_sla_policies,
  ticket_sla_targets, ticket_priority_matrix, ticket_routing_rules.
- Seed: очереди (ServiceDesk L1, SysAdmins, Network, 1C, Security), базовые категории,
  default SLA policy.
- Backfill: open -> In Progress, closed -> Closed, priority=P3, impact=2, urgency=2,
  queue=ServiceDesk L1.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

revision: str = "018"
down_revision: Union[str, None] = "017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Справочники (создать до расширения tickets) ---

    op.create_table(
        "ticket_queues",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("is_triage", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.create_index("ix_ticket_queues_code", "ticket_queues", ["code"], unique=True)

    op.create_table(
        "ticket_categories",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("parent_id", sa.BigInteger(), nullable=True),
        sa.Column("level", sa.SmallInteger(), nullable=False),
    )
    op.create_index("ix_ticket_categories_parent_id", "ticket_categories", ["parent_id"])
    op.create_foreign_key(
        "fk_ticket_categories_parent",
        "ticket_categories",
        "ticket_categories",
        ["parent_id"],
        ["id"],
    )

    op.create_table(
        "ticket_sla_policies",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("timezone", sa.Text(), nullable=False, server_default="UTC"),
        sa.Column("business_hours_json", JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index(
        "ix_ticket_sla_policies_is_default",
        "ticket_sla_policies",
        ["is_default"],
        postgresql_where=sa.text("is_default = true"),
    )

    op.create_table(
        "ticket_sla_targets",
        sa.Column("policy_id", sa.BigInteger(), nullable=False),
        sa.Column("priority", sa.String(5), nullable=False),
        sa.Column("first_response_min", sa.Integer(), nullable=False),
        sa.Column("resolution_min", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("policy_id", "priority"),
        sa.ForeignKeyConstraint(["policy_id"], ["ticket_sla_policies.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "ticket_priority_matrix",
        sa.Column("policy_id", sa.BigInteger(), nullable=False),
        sa.Column("impact", sa.SmallInteger(), nullable=False),
        sa.Column("urgency", sa.SmallInteger(), nullable=False),
        sa.Column("priority", sa.String(5), nullable=False),
        sa.PrimaryKeyConstraint("policy_id", "impact", "urgency"),
        sa.ForeignKeyConstraint(["policy_id"], ["ticket_sla_policies.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "ticket_routing_rules",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("priority_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("condition_json", JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("target_queue_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["target_queue_id"],
            ["ticket_queues.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_ticket_routing_rules_priority", "ticket_routing_rules", ["priority_order"])

    op.create_table(
        "ticket_queue_members",
        sa.Column("queue_id", sa.BigInteger(), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=False),
        sa.Column("role_in_queue", sa.String(50), nullable=True),
        sa.PrimaryKeyConstraint("queue_id", "actor_id"),
        sa.ForeignKeyConstraint(["queue_id"], ["ticket_queues.id"], ondelete="CASCADE"),
    )

    # --- Расширение tickets ---

    op.add_column(
        "tickets",
        sa.Column("ticket_type", sa.String(20), nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column("priority", sa.String(5), nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column("impact", sa.SmallInteger(), nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column("urgency", sa.SmallInteger(), nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column("requester_id", sa.Text(), nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column("assignee_id", sa.Text(), nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column("queue_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column("category_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column("service_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column("subcategory_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column("resolved_at", TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column("closed_at", TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column("sla_policy_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column("first_response_due_at", TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column("resolution_due_at", TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column("first_response_at", TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column("resolution_at", TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column("first_response_breached_at", TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column("resolution_breached_at", TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column("sla_paused_at", TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column("sla_paused_seconds", sa.Integer(), nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column("asset_id", sa.Text(), nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column("tags", JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column("custom_fields", JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column("external_ref", sa.Text(), nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column("resolution_code", sa.Text(), nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column("root_cause", sa.Text(), nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column("reopen_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column("parent_ticket_id", sa.String(36), nullable=True),
    )

    op.create_foreign_key(
        "fk_tickets_queue",
        "tickets",
        "ticket_queues",
        ["queue_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_tickets_category",
        "tickets",
        "ticket_categories",
        ["category_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_tickets_service",
        "tickets",
        "ticket_categories",
        ["service_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_tickets_subcategory",
        "tickets",
        "ticket_categories",
        ["subcategory_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_tickets_sla_policy",
        "tickets",
        "ticket_sla_policies",
        ["sla_policy_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_tickets_parent",
        "tickets",
        "tickets",
        ["parent_ticket_id"],
        ["ticket_id"],
    )

    op.create_index(
        "ix_tickets_queue_status_priority",
        "tickets",
        ["queue_id", "status", "priority"],
    )
    op.create_index("ix_tickets_assignee_status", "tickets", ["assignee_id", "status"])
    op.create_index("ix_tickets_requester_created", "tickets", ["requester_id", "created_at"])
    op.create_index("ix_tickets_status_updated", "tickets", ["status", "updated_at"])
    op.create_index("ix_tickets_first_response_due", "tickets", ["first_response_due_at"])
    op.create_index("ix_tickets_resolution_due", "tickets", ["resolution_due_at"])

    # --- Таблицы связей тикетов ---

    op.create_table(
        "ticket_watchers",
        sa.Column("ticket_id", sa.String(36), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("ticket_id", "actor_id"),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.ticket_id"], ondelete="CASCADE"),
    )
    op.create_index("ix_ticket_watchers_actor_id", "ticket_watchers", ["actor_id"])

    op.create_table(
        "ticket_links",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("src_ticket_id", sa.String(36), nullable=False),
        sa.Column("dst_ticket_id", sa.String(36), nullable=False),
        sa.Column("link_type", sa.String(30), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["src_ticket_id"], ["tickets.ticket_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["dst_ticket_id"], ["tickets.ticket_id"], ondelete="CASCADE"),
    )
    op.create_index("ix_ticket_links_src", "ticket_links", ["src_ticket_id"])
    op.create_index("ix_ticket_links_dst", "ticket_links", ["dst_ticket_id"])
    op.create_index("ix_ticket_links_type", "ticket_links", ["link_type"])

    op.create_table(
        "ticket_worklogs",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("ticket_id", sa.String(36), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=False),
        sa.Column("spent_minutes", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.ticket_id"], ondelete="CASCADE"),
    )
    op.create_index("ix_ticket_worklogs_ticket_id", "ticket_worklogs", ["ticket_id"])

    # --- Seed: очереди ---

    op.execute("""
        INSERT INTO ticket_queues (code, name, is_triage, is_active)
        VALUES
            ('servicedesk_l1', 'ServiceDesk L1', true, true),
            ('sysadmins', 'SysAdmins', false, true),
            ('network', 'Network', false, true),
            ('1c', '1C', false, true),
            ('security', 'Security', false, true)
    """)

    # --- Seed: базовые категории (level 1=category, 2=service, 3=subcategory) ---

    op.execute("""
        INSERT INTO ticket_categories (code, name, parent_id, level)
        VALUES
            ('hardware', 'Оборудование', NULL, 1),
            ('software', 'ПО', NULL, 1),
            ('network', 'Сеть', NULL, 1),
            ('access', 'Доступы', NULL, 1),
            ('other', 'Прочее', NULL, 1)
    """)

    # --- Seed: default SLA policy (24x7, P1 15m/4h, P2 30m/8h, P3 2h/24h, P4 8h/72h) ---

    op.execute("""
        INSERT INTO ticket_sla_policies (name, timezone, business_hours_json, is_default)
        VALUES ('Default 24x7', 'UTC', NULL, true)
    """)

    op.execute("""
        INSERT INTO ticket_sla_targets (policy_id, priority, first_response_min, resolution_min)
        SELECT p.id, v.p, v.fr, v.res
        FROM ticket_sla_policies p
        CROSS JOIN (VALUES ('P1', 15, 240), ('P2', 30, 480), ('P3', 120, 1440), ('P4', 480, 4320)) AS v(p, fr, res)
        WHERE p.is_default = true
    """)

    op.execute("""
        INSERT INTO ticket_priority_matrix (policy_id, impact, urgency, priority)
        SELECT p.id, v.i, v.u, v.pri
        FROM ticket_sla_policies p
        CROSS JOIN (VALUES (1,1,'P4'),(1,2,'P4'),(1,3,'P3'),(2,1,'P4'),(2,2,'P3'),(2,3,'P2'),(3,1,'P3'),(3,2,'P2'),(3,3,'P1')) AS v(i,u,pri)
        WHERE p.is_default = true
    """)

    # --- Backfill старых тикетов ---

    op.execute("""
        UPDATE tickets
        SET
            status = CASE
                WHEN status = 'open' THEN 'In Progress'
                WHEN status = 'closed' THEN 'Closed'
                ELSE status
            END,
            ticket_type = COALESCE(ticket_type, 'request'),
            priority = COALESCE(priority, 'P3'),
            impact = COALESCE(impact, 2),
            urgency = COALESCE(urgency, 2),
            queue_id = (SELECT id FROM ticket_queues WHERE code = 'servicedesk_l1' LIMIT 1),
            sla_policy_id = (SELECT id FROM ticket_sla_policies WHERE is_default = true LIMIT 1),
            tags = COALESCE(tags, '[]'::jsonb),
            custom_fields = COALESCE(custom_fields, '{}'::jsonb),
            reopen_count = COALESCE(reopen_count, 0)
        WHERE queue_id IS NULL
    """)

    op.alter_column(
        "tickets",
        "ticket_type",
        existing_type=sa.String(20),
        server_default="request",
        nullable=False,
    )
    op.alter_column(
        "tickets",
        "priority",
        existing_type=sa.String(5),
        server_default="P3",
        nullable=False,
    )
    op.alter_column(
        "tickets",
        "reopen_count",
        existing_type=sa.Integer(),
        server_default="0",
        nullable=False,
    )
    op.alter_column(
        "tickets",
        "tags",
        existing_type=JSONB(astext_type=sa.Text()),
        server_default=sa.text("'[]'::jsonb"),
        nullable=False,
    )
    op.alter_column(
        "tickets",
        "custom_fields",
        existing_type=JSONB(astext_type=sa.Text()),
        server_default=sa.text("'{}'::jsonb"),
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column("tickets", "custom_fields", server_default=None, nullable=True)
    op.alter_column("tickets", "tags", server_default=None, nullable=True)
    op.alter_column("tickets", "reopen_count", server_default=None, nullable=True)
    op.alter_column("tickets", "priority", server_default=None, nullable=True)
    op.alter_column("tickets", "ticket_type", server_default=None, nullable=True)

    op.drop_index("ix_ticket_worklogs_ticket_id", table_name="ticket_worklogs")
    op.drop_table("ticket_worklogs")
    op.drop_index("ix_ticket_links_type", table_name="ticket_links")
    op.drop_index("ix_ticket_links_dst", table_name="ticket_links")
    op.drop_index("ix_ticket_links_src", table_name="ticket_links")
    op.drop_table("ticket_links")
    op.drop_index("ix_ticket_watchers_actor_id", table_name="ticket_watchers")
    op.drop_table("ticket_watchers")

    op.drop_index("ix_tickets_resolution_due", table_name="tickets")
    op.drop_index("ix_tickets_first_response_due", table_name="tickets")
    op.drop_index("ix_tickets_status_updated", table_name="tickets")
    op.drop_index("ix_tickets_requester_created", table_name="tickets")
    op.drop_index("ix_tickets_assignee_status", table_name="tickets")
    op.drop_index("ix_tickets_queue_status_priority", table_name="tickets")

    op.drop_constraint("fk_tickets_parent", "tickets", type_="foreignkey")
    op.drop_constraint("fk_tickets_sla_policy", "tickets", type_="foreignkey")
    op.drop_constraint("fk_tickets_subcategory", "tickets", type_="foreignkey")
    op.drop_constraint("fk_tickets_service", "tickets", type_="foreignkey")
    op.drop_constraint("fk_tickets_category", "tickets", type_="foreignkey")
    op.drop_constraint("fk_tickets_queue", "tickets", type_="foreignkey")

    for col in (
        "parent_ticket_id", "reopen_count", "root_cause", "resolution_code", "external_ref",
        "custom_fields", "tags", "asset_id", "sla_paused_seconds", "sla_paused_at",
        "resolution_breached_at", "first_response_breached_at", "resolution_at",
        "first_response_at", "resolution_due_at", "first_response_due_at", "sla_policy_id",
        "closed_at", "resolved_at", "subcategory_id", "service_id", "category_id",
        "queue_id", "assignee_id", "requester_id", "urgency", "impact", "priority", "ticket_type",
    ):
        op.drop_column("tickets", col)

    op.drop_index("ix_ticket_routing_rules_priority", table_name="ticket_routing_rules")
    op.drop_table("ticket_routing_rules")
    op.drop_table("ticket_priority_matrix")
    op.drop_table("ticket_sla_targets")
    op.drop_index("ix_ticket_sla_policies_is_default", table_name="ticket_sla_policies")
    op.drop_table("ticket_sla_policies")
    op.drop_constraint("fk_ticket_categories_parent", "ticket_categories", type_="foreignkey")
    op.drop_index("ix_ticket_categories_parent_id", table_name="ticket_categories")
    op.drop_table("ticket_categories")
    op.drop_table("ticket_queue_members")
    op.drop_index("ix_ticket_queues_code", table_name="ticket_queues")
    op.drop_table("ticket_queues")
