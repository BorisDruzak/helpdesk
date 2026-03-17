"""
SQLAlchemy database models.
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column
import sqlalchemy as sa
from app.db.base import Base


class Ticket(Base):
    """
    Ticket model for Protocol V3 (расширенная тикетная система).
    
    Represents a support ticket bound to a specific device.
    Статусы: new, triaged, in_progress, waiting_on_user, waiting_on_vendor, resolved, closed.
    Совместимость: soft-нормализация принимает legacy значения.
    """
    __tablename__ = "tickets"
    
    ticket_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    ticket_code: Mapped[str] = mapped_column(
        String(20), nullable=False, unique=True,
        server_default=sa.text("'T-' || lpad(nextval('ticket_code_seq')::text, 6, '0')"),
    )
    device_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
    # Расширенная модель (миграция 018)
    ticket_type: Mapped[str] = mapped_column(String(20), nullable=False, server_default="request")
    priority: Mapped[str] = mapped_column(String(5), nullable=False, server_default="P3")
    impact: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    urgency: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    importance: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    urgency_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    importance_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    requester_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assignee_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    queue_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    category_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    service_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    subcategory_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    sla_policy_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    first_response_due_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    resolution_due_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    first_response_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    resolution_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    first_response_breached_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    resolution_breached_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    sla_paused_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    sla_paused_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Stage 11: OLA (queue-level)
    ola_queue_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    ola_started_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    ola_ack_due_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    ola_ack_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    ola_ack_breached_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    ola_processing_due_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    ola_processing_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    ola_processing_breached_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    ola_paused_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    ola_paused_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    asset_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'[]'::jsonb"))
    custom_fields: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    external_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolution_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    root_cause: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reopen_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    parent_ticket_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    # Stage 10.2: ручной порядок в очереди (отдельно от priority/SLA)
    manual_rank: Mapped[Optional[int]] = mapped_column(sa.BigInteger, nullable=True)
    manual_rank_updated_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    manual_rank_updated_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Скрытие из веб-очереди (только для закрытых): в БД остаётся, в список не попадает
    archived_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    
    __table_args__ = (
        Index("ix_tickets_device_id_status", "device_id", "status"),
        Index("ix_tickets_queue_status_priority", "queue_id", "status", "priority"),
        Index("ix_tickets_assignee_status", "assignee_id", "status"),
        Index("ix_tickets_requester_created", "requester_id", "created_at"),
        Index("ix_tickets_status_updated", "status", "updated_at"),
        Index("ix_tickets_first_response_due", "first_response_due_at"),
        Index("ix_tickets_resolution_due", "resolution_due_at"),
        Index("ix_tickets_ola_queue_id", "ola_queue_id"),
        Index("ix_tickets_ola_ack_due_at", "ola_ack_due_at"),
        Index("ix_tickets_ola_ack_breached_at", "ola_ack_breached_at"),
        Index("ix_tickets_ola_processing_due_at", "ola_processing_due_at"),
        Index("ix_tickets_ola_processing_breached_at", "ola_processing_breached_at"),
        Index("ix_tickets_queue_manual_rank", "queue_id", "manual_rank"),
        Index("ix_tickets_queue_open_sort", "queue_id", "status", "priority", "created_at"),
    )
    
    def __repr__(self) -> str:
        return (
            f"<Ticket(ticket_id={self.ticket_id!r}, device_id={self.device_id!r}, "
            f"status={self.status!r})>"
        )


class TicketEvent(Base):
    """
    Ticket event model for Protocol V3.
    
    Stores all events for tickets with deduplication support.
    Ordered by agent_seq per-ticket.
    """
    __tablename__ = "ticket_events"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    device_id: Mapped[str] = mapped_column(String(36), nullable=False)
    # КРИТИЧНО: agent_seq nullable для server-originated событий (support/user messages)
    # Agent-originated события имеют agent_seq (монотонный, от агента)
    # Server-originated события имеют agent_seq = NULL
    agent_seq: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    trace_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    event_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    operation_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    
    __table_args__ = (
        # КРИТИЧНО: Частичный UNIQUE constraint создается в миграции 005 через raw SQL
        # (SQLAlchemy не поддерживает postgresql_where для UniqueConstraint в моделях)
        # Constraint: uq_ticket_events_device_ticket_seq UNIQUE (device_id, ticket_id, agent_seq) WHERE agent_seq IS NOT NULL
        # Server events (agent_seq = NULL) дедуплицируются через логику по message_id в TicketEventsRepo
        # Composite index для эффективного получения событий с сортировкой
        Index("ix_ticket_events_ticket_id_agent_seq", "ticket_id", "agent_seq"),
        # Index для фильтрации по типу событий
        Index("ix_ticket_events_ticket_type_seq", "ticket_id", "event_type", "agent_seq"),
        Index("ix_ticket_events_trace_id", "trace_id"),
    )
    
    def __repr__(self) -> str:
        return (
            f"<TicketEvent(id={self.id}, ticket_id={self.ticket_id!r}, "
            f"event_type={self.event_type!r}, agent_seq={self.agent_seq})>"
        )


class TicketQueue(Base):
    """Очередь тикетов (ServiceDesk L1, SysAdmins, Network, 1C, Security и т.д.)."""
    __tablename__ = "ticket_queues"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    is_triage: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class TicketCategory(Base):
    """Иерархия категорий (level 1=category, 2=service, 3=subcategory)."""
    __tablename__ = "ticket_categories"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    parent_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    level: Mapped[int] = mapped_column(SmallInteger, nullable=False)


class TicketBusinessCalendar(Base):
    """Stage 11: Бизнес-календарь (рабочие часы, праздники) для SLA."""
    __tablename__ = "ticket_business_calendars"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, server_default="UTC")
    weekly_hours_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    holidays_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class TicketSlaPolicy(Base):
    """Политика SLA (24x7 или business hours). Stage 9: is_active. Stage 11: calendar_id."""
    __tablename__ = "ticket_sla_policies"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    timezone: Mapped[str] = mapped_column(Text, nullable=False, server_default="UTC")
    business_hours_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    calendar_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        sa.ForeignKey("ticket_business_calendars.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))


class TicketSlaTarget(Base):
    """Цели SLA по приоритету (FRT и Resolution в минутах)."""
    __tablename__ = "ticket_sla_targets"
    policy_id: Mapped[int] = mapped_column(BigInteger, sa.ForeignKey("ticket_sla_policies.id", ondelete="CASCADE"), primary_key=True)
    priority: Mapped[str] = mapped_column(String(5), primary_key=True)
    first_response_min: Mapped[int] = mapped_column(Integer, nullable=False)
    resolution_min: Mapped[int] = mapped_column(Integer, nullable=False)


class TicketPriorityMatrix(Base):
    """Матрица impact × urgency -> priority для политики."""
    __tablename__ = "ticket_priority_matrix"
    policy_id: Mapped[int] = mapped_column(BigInteger, sa.ForeignKey("ticket_sla_policies.id", ondelete="CASCADE"), primary_key=True)
    impact: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    urgency: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    priority: Mapped[str] = mapped_column(String(5), nullable=False)


class TicketRoutingRule(Base):
    """Правило маршрутизации тикетов в очередь."""
    __tablename__ = "ticket_routing_rules"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    priority_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    condition_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    target_queue_id: Mapped[int] = mapped_column(BigInteger, sa.ForeignKey("ticket_queues.id", ondelete="CASCADE"), nullable=False)


class TicketQueueMember(Base):
    """Участник очереди (actor_id + роль в очереди)."""
    __tablename__ = "ticket_queue_members"
    queue_id: Mapped[int] = mapped_column(BigInteger, sa.ForeignKey("ticket_queues.id", ondelete="CASCADE"), primary_key=True)
    actor_id: Mapped[str] = mapped_column(Text, primary_key=True)
    role_in_queue: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)


class TicketQueueOlaTarget(Base):
    """Stage 11: OLA-цели по очереди и приоритету (ack_min, processing_min)."""
    __tablename__ = "ticket_queue_ola_targets"
    queue_id: Mapped[int] = mapped_column(BigInteger, sa.ForeignKey("ticket_queues.id", ondelete="CASCADE"), primary_key=True)
    priority: Mapped[str] = mapped_column(String(5), primary_key=True)
    ack_min: Mapped[int] = mapped_column(Integer, nullable=False)
    processing_min: Mapped[int] = mapped_column(Integer, nullable=False)


class TicketWatcher(Base):
    """Наблюдатель тикета."""
    __tablename__ = "ticket_watchers"
    ticket_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"), primary_key=True)
    actor_id: Mapped[str] = mapped_column(Text, primary_key=True)


class TicketLink(Base):
    """Связь тикетов (duplicate, related, parent-child)."""
    __tablename__ = "ticket_links"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    src_ticket_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"), nullable=False)
    dst_ticket_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"), nullable=False)
    link_type: Mapped[str] = mapped_column(String(30), nullable=False)
    created_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class TicketResolutionCode(Base):
    """Справочник кодов резолюции (Stage 5)."""
    __tablename__ = "ticket_resolution_codes"
    code: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sa.text("0"))


class TicketKbLink(Base):
    """Ссылка на статью базы знаний по тикету (Stage 5)."""
    __tablename__ = "ticket_kb_links"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"), nullable=False)
    article_ref: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class TicketWorklog(Base):
    """Трудозатраты по тикету (минуты + заметка)."""
    __tablename__ = "ticket_worklogs"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"), nullable=False)
    actor_id: Mapped[str] = mapped_column(Text, nullable=False)
    spent_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class TicketNotification(Base):
    """In-app уведомление по тикету (Stage 6). Доставка через WS/API."""
    __tablename__ = "ticket_notifications"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    actor_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    ticket_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    read_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_ticket_notifications_actor_read_created", "actor_id", "is_read", "created_at"),
        Index("ix_ticket_notifications_ticket_created", "ticket_id", "created_at"),
    )


class TicketNotificationPref(Base):
    """Stage 8: Настройки уведомлений пользователя (mute_internal, muted_event_types, suppress_self)."""
    __tablename__ = "ticket_notification_prefs"
    actor_id: Mapped[str] = mapped_column(Text, primary_key=True)
    mute_internal: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    muted_event_types: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'[]'::jsonb"))
    suppress_self: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class Problem(Base):
    """Stage 7: ITSM Problem. FSM: New -> Investigating -> Mitigated -> Resolved -> Closed."""
    __tablename__ = "problems"
    problem_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="New")
    priority: Mapped[str] = mapped_column(String(5), nullable=False, server_default="P3")
    owner_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    root_cause: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    workaround: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    kb_article_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_problems_status_priority_updated", "status", "priority", "updated_at"),
        Index("ix_problems_owner_status", "owner_id", "status"),
    )


class ProblemTicketLink(Base):
    """Stage 7: Связь problem <-> ticket."""
    __tablename__ = "problem_ticket_links"
    problem_id: Mapped[str] = mapped_column(
        String(36), sa.ForeignKey("problems.problem_id", ondelete="CASCADE"), primary_key=True
    )
    ticket_id: Mapped[str] = mapped_column(
        String(36), sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"), primary_key=True
    )
    linked_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    linked_by: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (Index("ix_problem_ticket_links_ticket_id", "ticket_id"),)


class TicketAdminAudit(Base):
    """Stage 9: Аудит изменений admin-config (очереди, routing rules, SLA policies)."""
    __tablename__ = "ticket_admin_audit"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    actor_id: Mapped[str] = mapped_column(Text, nullable=False)
    actor_role: Mapped[str] = mapped_column(String(20), nullable=False)
    before_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    after_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_ticket_admin_audit_entity_type_entity_id_created_at", "entity_type", "entity_id", "created_at"),
        Index("ix_ticket_admin_audit_actor_id_created_at", "actor_id", "created_at"),
        Index("ix_ticket_admin_audit_created_at", "created_at"),
    )


class TicketChangeLink(Base):
    """Stage 7: Связь тикета с Change (внешняя система)."""
    __tablename__ = "ticket_change_links"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(
        String(36), sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"), nullable=False
    )
    change_ref: Mapped[str] = mapped_column(Text, nullable=False)
    change_system: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_ticket_change_links_ticket_id", "ticket_id"),
        sa.UniqueConstraint("ticket_id", "change_ref", "change_system", name="uq_ticket_change_links_ticket_ref_system"),
    )


class DeviceEvent(Base):
    """
    Device event model for Protocol V3.
    
    Stores events for devices without ticket binding.
    Ordered by device_seq per-device.
    """
    __tablename__ = "device_events"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    device_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    trace_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    event_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    operation_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    
    __table_args__ = (
        # КРИТИЧНО: dedupe по (device_id, device_seq)
        sa.UniqueConstraint(
            "device_id", "device_seq",
            name="uq_device_events_device_seq"
        ),
        Index("ix_device_events_device_id_device_seq", "device_id", "device_seq"),
        Index("ix_device_events_trace_id", "trace_id"),
    )
    
    def __repr__(self) -> str:
        return (
            f"<DeviceEvent(id={self.id}, device_id={self.device_id!r}, "
            f"event_type={self.event_type!r}, device_seq={self.device_seq})>"
        )


class JobEvent(Base):
    """
    Job event model for persistent storage of chat/job events.
    
    Stores all events from agents with deduplication support.
    """
    
    __tablename__ = "job_events"
    
    # Primary key
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    
    # Job identification
    job_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    
    # Sequence number (nullable for lifecycle events)
    seq: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Timestamp (event time from payload or current time)
    ts: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    
    # Event type (chat_message, chat_started, tool_call_started, etc.)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Message ID (for deduplication of chat_message events)
    message_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Full event payload as JSONB
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    
    # Table constraints and indexes
    __table_args__ = (
        # Composite index for efficient seq-based queries
        Index("ix_job_events_job_id_seq", "job_id", "seq"),
        # Index for timestamp-based queries
        Index("ix_job_events_job_id_ts", "job_id", "ts"),
        # Unique constraint for message deduplication
        sa.Index(
            "uq_job_events_job_id_message_id_not_null",
            "job_id",
            "message_id",
            unique=True,
            postgresql_where=sa.text("message_id IS NOT NULL"),
        ),
    )
    
    def __repr__(self) -> str:
        return (
            f"<JobEvent(id={self.id}, job_id={self.job_id!r}, "
            f"event_type={self.event_type!r}, seq={self.seq}, "
            f"message_id={self.message_id!r})>"
        )


class Device(Base):
    """
    Device registry model.
    
    Tracks all devices that have connected to the server with metadata,
    toolset information, and last activity timestamps.
    """
    __tablename__ = "devices"
    
    device_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    
    # Timestamps
    first_seen_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    last_handshake_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    last_toolset_refresh_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True
    )
    last_tools_changed_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True
    )
    
    # Agent metadata
    protocol_version: Mapped[str] = mapped_column(Text, nullable=False)
    agent_version: Mapped[str] = mapped_column(Text, nullable=False)
    hostname: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    os: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Capabilities and tools
    capabilities: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    tools_version: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Toolset tracking
    current_toolset_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    current_toolset_snapshot_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True
    )
    
    # Additional metadata (modules, etc.)
    # Note: named 'device_metadata' to avoid conflict with SQLAlchemy's reserved 'metadata' attribute
    device_metadata: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    
    __table_args__ = (
        Index("ix_devices_last_seen_at", "last_seen_at"),
        Index("ix_devices_agent_version", "agent_version"),
        Index("ix_devices_last_toolset_refresh_at", "last_toolset_refresh_at"),
    )
    
    def __repr__(self) -> str:
        return (
            f"<Device(device_id={self.device_id!r}, agent_version={self.agent_version!r}, "
            f"toolset_hash={self.current_toolset_hash!r})>"
        )


class DeviceConfig(Base):
    """
    Device configuration model.
    
    Stores desired and applied configurations for devices using revision-based tracking.
    """
    __tablename__ = "device_config"
    
    device_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    
    # Desired configuration
    desired_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    desired_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    
    # Applied configuration
    applied_revision: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    applied_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True
    )
    last_apply_status: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_apply_error: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    
    # Metadata
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
    
    def __repr__(self) -> str:
        return (
            f"<DeviceConfig(device_id={self.device_id!r}, "
            f"desired_revision={self.desired_revision}, "
            f"applied_revision={self.applied_revision})>"
        )


class DeviceToolsetSnapshot(Base):
    """
    Device toolset snapshot model.
    
    Stores snapshots of tool lists from devices for tracking changes over time.
    UNIQUE constraint on (device_id, toolset_hash) prevents duplicates.
    """
    __tablename__ = "device_toolset_snapshots"
    
    snapshot_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True
    )
    device_id: Mapped[str] = mapped_column(String(36), nullable=False)
    
    # Snapshot metadata
    captured_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    agent_version: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Toolset data
    toolset_hash: Mapped[str] = mapped_column(Text, nullable=False)
    toolset_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    tool_count: Mapped[int] = mapped_column(Integer, nullable=False)
    
    __table_args__ = (
        # КРИТИЧНО: UNIQUE constraint для предотвращения дубликатов
        sa.UniqueConstraint(
            "device_id", "toolset_hash",
            name="uq_device_toolset_snapshots_device_hash"
        ),
        Index("ix_toolset_snapshots_device_captured", "device_id", "captured_at"),
        Index("ix_toolset_snapshots_device_hash", "device_id", "toolset_hash"),
    )
    
    def __repr__(self) -> str:
        return (
            f"<DeviceToolsetSnapshot(snapshot_id={self.snapshot_id}, "
            f"device_id={self.device_id!r}, toolset_hash={self.toolset_hash!r}, "
            f"tool_count={self.tool_count})>"
        )


class DeviceOutbox(Base):
    """
    Device outbox model for Protocol V3.
    
    Server-side outbox for reliable command delivery to devices.
    Commands are persisted before sending and lifecycle-tracked.
    """
    __tablename__ = "device_outbox"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    command_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    command: Mapped[str] = mapped_column(Text, nullable=False)
    params: Mapped[dict] = mapped_column(JSONB, nullable=False)
    
    # Lifecycle tracking
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True
    )  # pending, sent, delivered, failed
    
    # Metadata
    request_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    operation_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    actor_role: Mapped[str] = mapped_column(String(20), nullable=False, default="user")
    
    # Retry tracking
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True
    )
    delivered_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True
    )
    failed_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True
    )
    
    # Error tracking
    error_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    __table_args__ = (
        Index("ix_device_outbox_device_id_status", "device_id", "status"),
        Index("ix_device_outbox_command_id_status", "command_id", "status"),
        Index("ix_device_outbox_created_at", "created_at"),
    )
    
    def __repr__(self) -> str:
        return (
            f"<DeviceOutbox(id={self.id}, device_id={self.device_id!r}, "
            f"command_id={self.command_id!r}, command={self.command!r}, "
            f"status={self.status!r})>"
        )


class Operation(Base):
    """
    Operation model for tracking end-to-end command/tool execution lifecycle.
    
    Operations materialize operation state from events for efficient querying.
    All operations updates are transactional with corresponding events.
    """
    __tablename__ = "operations"
    
    operation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    device_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    ticket_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    job_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    tool_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Для kind=command (list_tools и др.): имя команды для метрик (Этап 5)
    command_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    actor_role: Mapped[str] = mapped_column(String(20), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    
    # Status: queued, sent, accepted, running, waiting_consent, succeeded, failed, denied, timed_out, cancel_requested, canceled
    # denied - терминальный статус для denied consent, отдельно от failed
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    
    # SLA tracking
    deadline_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
        index=True
    )
    # Переопределение таймаута для шага playbook (Этап 5)
    timeout_override_sec: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Связь с playbook_run для наблюдаемости (Этап 5)
    playbook_run_id: Mapped[Optional[int]] = mapped_column(
        sa.BigInteger, sa.ForeignKey("playbook_run.id", ondelete="SET NULL"), nullable=True
    )
    
    # Lifecycle timestamps
    queued_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        # КРИТИЧНО: Не используем default=lambda, так как он может вычисляться при импорте модуля
        # В OperationsRepo.create_operation явно устанавливается queued_at=datetime.now(timezone.utc)
        # Это гарантирует правильное UTC время при создании операции
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True
    )
    accepted_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True
    )
    
    # Retry tracking
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    
    # Result tracking
    error_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result_event_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    
    # Cancel tracking
    status_before_cancel: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cancel_target_operation_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    active_cancel_operation_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    cancel_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cancel_requested_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    canceled_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    
    __table_args__ = (
        Index("ix_operations_status_queued_at", "status", "queued_at"),
        Index("ix_operations_device_id_status", "device_id", "status"),
        Index("ix_operations_deadline_at", "deadline_at"),
        Index("ix_operations_cancel_target", "cancel_target_operation_id"),
        Index("ix_operations_active_cancel", "active_cancel_operation_id"),
    )
    
    def __repr__(self) -> str:
        return (
            f"<Operation(operation_id={self.operation_id!r}, device_id={self.device_id!r}, "
            f"kind={self.kind!r}, status={self.status!r})>"
        )


class Module(Base):
    """
    Server-side registry of module artifacts.
    
    Stores metadata about uploaded module ZIP files.
    """
    __tablename__ = "modules"
    
    module_name: Mapped[str] = mapped_column(String(100), primary_key=True)
    version: Mapped[str] = mapped_column(String(50), primary_key=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)  # Relative to MODULES_STORAGE_DIR
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    uploaded_by: Mapped[str] = mapped_column(String(20), nullable=False, default="admin")  # actor_role
    manifest_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    validation_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    manifest_summary: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)  # manifest summary (renamed from metadata to avoid conflict with SQLAlchemy Base.metadata)
    
    __table_args__ = (
        Index("ix_modules_sha256", "sha256"),
        Index("ix_modules_created_at", "created_at"),
    )
    
    def __repr__(self) -> str:
        return (
            f"<Module(module_name={self.module_name!r}, version={self.version!r}, "
            f"sha256={self.sha256[:16]}..., size={self.size})>"
        )


class AgentBuild(Base):
    """
    Server-side registry of agent build artifacts (self-update packages).

    Stores metadata about uploaded agent ZIP packages.
    Composite PK: (target, channel, version).
    """
    __tablename__ = "agent_builds"

    target: Mapped[str] = mapped_column(String(50), primary_key=True)  # e.g. windows_amd64
    channel: Mapped[str] = mapped_column(String(20), primary_key=True, default="stable")  # stable|beta|dev
    version: Mapped[str] = mapped_column(String(50), primary_key=True)

    sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)  # Relative to AGENT_BUILDS_STORAGE_DIR
    artifact_filename: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # e.g. pc_agent-windows_amd64-3.1.0.zip
    archive_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # zip | tar.gz
    mime_type: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)  # application/zip | application/gzip

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    uploaded_by: Mapped[str] = mapped_column(String(20), nullable=False, default="admin")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_agent_builds_sha256", "sha256"),
        Index("ix_agent_builds_created_at", "created_at"),
        Index("ix_agent_builds_target_channel_created_at", "target", "channel", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<AgentBuild(target={self.target!r}, channel={self.channel!r}, "
            f"version={self.version!r}, sha256={self.sha256[:16]}..., size={self.size})>"
        )


class DeviceModule(Base):
    """
    Server-side registry of installed modules on devices (actual state).
    
    Tracks which modules are installed/active on each device.
    source: handshake|command_result|event
    last_seen_at: последнее подтверждение реального наличия от агента
    """
    __tablename__ = "device_modules"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    module_name: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    
    installed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    
    installed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    activated_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    last_updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
    # Новые поля (миграция 037)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
        comment="Время последнего подтверждения реального наличия модуля (от агента)"
    )
    source: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Источник обновления: handshake|command_result|event"
    )
    
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="installed", index=True)  # installing|installed|activating|active|failed|missing|removed
    last_error_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    last_error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    __table_args__ = (
        UniqueConstraint("device_id", "module_name", "version", name="uq_device_modules_device_name_version"),
        Index("ix_device_modules_device_active", "device_id", "active"),
        Index("ix_device_modules_device_state", "device_id", "state"),
        Index("ix_device_modules_module_name", "module_name"),
    )
    
    def __repr__(self) -> str:
        return (
            f"<DeviceModule(id={self.id}, device_id={self.device_id!r}, "
            f"module_name={self.module_name!r}, version={self.version!r}, "
            f"installed={self.installed}, active={self.active}, state={self.state!r})>"
        )


class DeviceDesiredModule(Base):
    """
    Желаемое состояние модулей на устройствах (desired state).
    
    Server-first источник истины для reconcile engine.
    state: installed | absent
    reason: manual | run_tool | policy | reconcile
    """
    __tablename__ = "device_desired_modules"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(36), nullable=False)
    module_name: Mapped[str] = mapped_column(String(100), nullable=False)
    # desired_version: None означает "absent" (желаем удалить)
    desired_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    desired_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    state: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="installed",
        comment="Желаемое состояние: installed|absent"
    )
    reason: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="manual",
        comment="Причина изменения: manual|run_tool|policy|reconcile"
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
    updated_by: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Кто изменил (actor_role или имя пользователя)"
    )
    
    __table_args__ = (
        UniqueConstraint("device_id", "module_name", name="uq_device_desired_modules_device_module"),
        Index("ix_device_desired_modules_device_id", "device_id"),
        Index("ix_device_desired_modules_state", "state"),
        Index("ix_device_desired_modules_device_state", "device_id", "state"),
    )
    
    def __repr__(self) -> str:
        return (
            f"<DeviceDesiredModule(id={self.id}, device_id={self.device_id!r}, "
            f"module_name={self.module_name!r}, desired_version={self.desired_version!r}, "
            f"state={self.state!r}, reason={self.reason!r})>"
        )


class AgentToken(Base):
    """
    Agent token model for authentication.
    
    Stores SHA256 hashes of tokens (not raw tokens) for security.
    Supports token rotation with grace period.
    """
    __tablename__ = "agent_tokens"
    
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)  # SHA256 hash
    token_prefix: Mapped[str] = mapped_column(String(8), nullable=False)  # First 8 chars for logs
    device_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    
    # Token rotation support
    replaced_by_token_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        # Foreign key to self for rotation tracking
    )
    rotated_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    
    last_used_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    
    __table_args__ = (
        Index("ix_agent_tokens_device_id", "device_id"),
        # Partial index for active tokens (not revoked)
        Index("ix_agent_tokens_active", "device_id", "revoked_at", postgresql_where=sa.text("revoked_at IS NULL")),
        Index("ix_agent_tokens_prefix", "token_prefix"),  # For log lookups
    )
    
    def __repr__(self) -> str:
        return (
            f"<AgentToken(token_hash={self.token_hash[:16]}..., "
            f"device_id={self.device_id!r}, revoked_at={self.revoked_at})>"
        )


class UiToken(Base):
    """
    UI token model for authentication.
    
    Stores SHA256 hashes of tokens (not raw tokens) for security.
    Supports token rotation with grace period.
    """
    __tablename__ = "ui_tokens"
    
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)  # SHA256 hash
    token_prefix: Mapped[str] = mapped_column(String(8), nullable=False)  # First 8 chars for logs
    user_login: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    actor_role: Mapped[str] = mapped_column(String(20), nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    
    # Token rotation support
    replaced_by_token_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        # Foreign key to self for rotation tracking
    )
    rotated_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    
    last_used_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    
    __table_args__ = (
        Index("ix_ui_tokens_user_login", "user_login"),
        # Partial index for active tokens (not revoked)
        Index("ix_ui_tokens_active", "user_login", "revoked_at", postgresql_where=sa.text("revoked_at IS NULL")),
        Index("ix_ui_tokens_prefix", "token_prefix"),  # For log lookups
    )
    
    def __repr__(self) -> str:
        return (
            f"<UiToken(token_hash={self.token_hash[:16]}..., "
            f"user_login={self.user_login!r}, actor_role={self.actor_role!r}, "
            f"revoked_at={self.revoked_at})>"
        )


class UiUser(Base):
    """Stage 10: UI пользователь (логин, хеш пароля, роль). Управление из БД."""
    __tablename__ = "ui_users"
    user_login: Mapped[str] = mapped_column(String(100), primary_key=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(20), nullable=False, server_default="admin")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    failed_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sa.text("0"))
    locked_until: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    last_ticket_assigned_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_ui_users_is_active", "is_active"),
        Index("ix_ui_users_actor_role", "actor_role"),
        Index("ix_ui_users_locked_until", "locked_until"),
    )


class UiUserAudit(Base):
    """Stage 10: Журнал действий по UI пользователям (создание, смена пароля, деактивация и т.д.)."""
    __tablename__ = "ui_user_audit"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_login: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    details_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_ui_user_audit_user_login_created_at", "user_login", "created_at"),
        Index("ix_ui_user_audit_created_at", "created_at"),
    )


class AuthSession(Base):
    """
    Auth session model for Phase 2 (session-based authentication).
    
    Prepared for future implementation of session-based auth for UI.
    """
    __tablename__ = "auth_sessions"
    
    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_login: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    actor_role: Mapped[str] = mapped_column(String(20), nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    
    # Session metadata
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)  # IPv6 support
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    __table_args__ = (
        Index("ix_auth_sessions_user_login", "user_login"),
        Index("ix_auth_sessions_expires_at", "expires_at"),
    )


class TicketPublicSession(Base):
    """Short-lived public web session for a specific ticket."""
    __tablename__ = "ticket_public_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    token_prefix: Mapped[str] = mapped_column(String(8), nullable=False)
    ticket_id: Mapped[str] = mapped_column(
        String(36),
        sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_id: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_ticket_public_sessions_ticket_id", "ticket_id"),
        Index("ix_ticket_public_sessions_expires_at", "expires_at"),
        Index(
            "ix_ticket_public_sessions_active",
            "ticket_id",
            "revoked_at",
            postgresql_where=sa.text("revoked_at IS NULL"),
        ),
    )
    
    def __repr__(self) -> str:
        return (
            f"<AuthSession(session_id={self.session_id[:16]}..., "
            f"user_login={self.user_login!r}, expires_at={self.expires_at})>"
        )


class ConsentDecision(Base):
    """
    Consent decision model for tracking approve/deny decisions.
    
    Stores decisions for operations that require consent (waiting_consent status).
    """
    __tablename__ = "consent_decisions"
    
    operation_id: Mapped[str] = mapped_column(
        String(36),
        sa.ForeignKey("operations.operation_id", ondelete="CASCADE"),
        primary_key=True
    )
    decision: Mapped[str] = mapped_column(String(10), nullable=False)  # 'approved' or 'denied'
    decided_by: Mapped[str] = mapped_column(String(100), nullable=False)  # actor_role or user_login
    decided_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    __table_args__ = (
        sa.CheckConstraint(
            "decision IN ('approved', 'denied')",
            name="ck_consent_decisions_decision"
        ),
        Index("ix_consent_decisions_decided_at", "decided_at"),
    )
    
    def __repr__(self) -> str:
        return (
            f"<ConsentDecision(operation_id={self.operation_id!r}, "
            f"decision={self.decision!r}, decided_by={self.decided_by!r})>"
        )


class DownloadAudit(Base):
    """
    Download audit model for tracking module downloads.
    
    Stores audit logs for all module download requests with token information.
    КРИТИЧНО: Сохраняется token_hash (SHA256), не raw token.
    """
    __tablename__ = "download_audit"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA256 hash
    token_prefix: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)  # First 8 chars for logs
    module_name: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    downloaded_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)  # IPv6 support
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    __table_args__ = (
        Index("ix_download_audit_token_hash", "token_hash"),
        Index("ix_download_audit_module", "module_name", "version"),
        Index("ix_download_audit_downloaded_at", "downloaded_at"),
    )
    
    def __repr__(self) -> str:
        return (
            f"<DownloadAudit(id={self.id}, module_name={self.module_name!r}, "
            f"version={self.version!r}, downloaded_at={self.downloaded_at})>"
        )


class AgentBuildDownloadAudit(Base):
    """
    Download audit model for tracking agent build downloads.

    КРИТИЧНО: Сохраняется token_hash (SHA256), не raw token.
    """
    __tablename__ = "agent_build_download_audit"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    token_prefix: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)

    target: Mapped[str] = mapped_column(String(50), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)

    downloaded_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_agent_build_dl_audit_token_hash", "token_hash"),
        Index("ix_agent_build_dl_audit_build", "target", "channel", "version"),
        Index("ix_agent_build_dl_audit_downloaded_at", "downloaded_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<AgentBuildDownloadAudit(id={self.id}, target={self.target!r}, "
            f"channel={self.channel!r}, version={self.version!r})>"
        )


class Artifact(Base):
    """
    Артефакт (файл), загруженный агентом: скриншоты, запись экрана.
    
    Метаданные хранятся в БД, файл — на диске (storage_path относительно UPLOAD_DIR).
    """
    __tablename__ = "artifacts"
    
    artifact_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    original_name: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    device_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    ticket_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    operation_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    
    __table_args__ = (
        Index("ix_artifacts_sha256", "sha256"),
    )
    
    def __repr__(self) -> str:
        return (
            f"<Artifact(artifact_id={self.artifact_id!r}, kind={self.kind!r}, "
            f"device_id={self.device_id!r}, size_bytes={self.size_bytes})>"
        )


# --- Playbook Engine (см. docs/PLAYBOOK_ENGINE_DESIGN.md) ---


class Playbook(Base):
    """Плейбук: ключ, имя, домен, владелец, архивный флаг."""
    __tablename__ = "playbook"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    owner: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class PlaybookVersion(Base):
    """Версия плейбука: manifest, статус, даты публикации."""
    __tablename__ = "playbook_version"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    playbook_id: Mapped[int] = mapped_column(
        BigInteger, sa.ForeignKey("playbook.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    manifest_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    __table_args__ = (UniqueConstraint("playbook_id", "version", name="uq_playbook_version_playbook_version"),)


class PlaybookStep(Base):
    """Шаг плейбука: tool, params template, if_expr, timeout, retry, parallel_group."""
    __tablename__ = "playbook_step"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    playbook_version_id: Mapped[int] = mapped_column(
        BigInteger, sa.ForeignKey("playbook_version.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_key: Mapped[str] = mapped_column(String(64), nullable=False)
    order_no: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False, default="run_tool")
    tool: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    params_template_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    if_expr: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timeout_sec: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    retry_policy_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    continue_on_error: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    parallel_group: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    __table_args__ = (Index("ix_playbook_step_order", "playbook_version_id", "order_no"),)


class PlaybookRun(Base):
    """Запуск плейбука на устройстве: статус, scheduled/started/finished, trigger, context."""
    __tablename__ = "playbook_run"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    playbook_version_id: Mapped[int] = mapped_column(
        BigInteger, sa.ForeignKey("playbook_version.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    device_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", index=True)
    scheduled_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    trigger_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    context_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Этап 6: идемпотентность при повторном POST (один ключ — один run)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, unique=True)

    __table_args__ = (
        Index("ix_playbook_run_scheduled_at", "scheduled_at"),
        Index("ix_playbook_run_status_scheduled_at", "status", "scheduled_at"),
    )


class PlaybookStepRun(Base):
    """Исполнение шага плейбука: attempt, status, operation_id, input/output/error, trace_id."""
    __tablename__ = "playbook_step_run"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    playbook_run_id: Mapped[int] = mapped_column(
        BigInteger, sa.ForeignKey("playbook_run.id", ondelete="CASCADE"), nullable=False, index=True
    )
    playbook_step_id: Mapped[int] = mapped_column(
        BigInteger, sa.ForeignKey("playbook_step.id", ondelete="RESTRICT"), nullable=False
    )
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    operation_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    input_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    output_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    error_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
