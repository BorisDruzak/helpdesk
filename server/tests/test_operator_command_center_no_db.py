from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest

from support.operator_command_center import ApprovalBatchSource, DiagnosticBatchSource, build_operator_command_center_payload
from web_api.dto.support import SupportQueueTicketItem
from web_api.support_handlers import _build_ticket_item


def item(ticket_id: str, title: str, **overrides) -> SupportQueueTicketItem:
    data = {
        "ticket_id": ticket_id,
        "ticket_code": f"T-{ticket_id[-3:]}",
        "title": title,
        "status": "queued",
        "status_label": "В очереди",
        "requester_status": "accepted",
        "requester_status_label": "Принят",
        "public_status": "accepted",
        "public_status_label": "Принят",
        "next_action_owner": "support",
        "next_action_due_at": None,
        "status_reason": None,
        "queue_code": "support",
        "assignee_id": None,
        "requester_display_name": "Инициатор",
        "device_id": f"device-{ticket_id}",
        "created_at": "2026-05-19T09:00:00+00:00",
        "updated_at": "2026-05-19T09:30:00+00:00",
        "requires_operator_action": True,
        "unread_user_messages": 0,
    }
    data.update(overrides)
    return SupportQueueTicketItem(**data)


@pytest.mark.no_db
def test_command_center_aggregates_compact_ticket_signals_without_db():
    now = datetime(2026, 5, 19, 10, 0, tzinfo=timezone.utc)
    queue_item = item(
        "ticket-1",
        "VPN client error 720",
        priority="P2",
        next_action_owner="support",
        next_action_due_at="2026-05-19T09:55:00+00:00",
        unread_user_messages=2,
    )
    ticket_data = {
        "ticket_id": queue_item.ticket_id,
        "device_id": queue_item.device_id,
        "status": "in_progress",
        "service_code": "network",
        "first_response_due_at": "2026-05-19T10:30:00+00:00",
        "custom_fields": {"diagnostic_policy": {"recommended": True, "profile_code": "vpn", "reason": "VPN diagnostics"}},
        "evidence_required": True,
    }

    payload = build_operator_command_center_payload(
        [(ticket_data, queue_item)],
        operations_by_ticket={
            "ticket-1": SimpleNamespace(
                operation_id="op-1",
                status="failed",
                tool_name="vpn.diagnostics",
                error_message="Profile missing",
                queued_at=now - timedelta(minutes=3),
                finished_at=now - timedelta(minutes=2),
            )
        },
        devices_by_id={
            queue_item.device_id: SimpleNamespace(last_seen_at=now - timedelta(minutes=30)),
        },
        approvals_by_ticket={
            "ticket-1": ApprovalBatchSource(requested_count=1, current_approver="service-owner"),
        },
        diagnostics_by_ticket={
            "ticket-1": DiagnosticBatchSource(failed_session_count=1, latest_profile_code="vpn"),
        },
        scope="team",
        queue=None,
        assignee=None,
        query=None,
        limit_per_section=8,
        window_hours=24,
        sla_risk_minutes=120,
        ola_risk_minutes=60,
        generated_at=now,
    )

    assert payload.summary.new_unassigned_count == 1
    assert payload.summary.operator_action_count == 1
    assert payload.summary.unread_user_messages_count == 1
    assert payload.summary.sla_risk_count == 1
    assert payload.summary.failed_operation_count == 1
    assert payload.summary.pending_approval_count == 1
    assert payload.summary.agent_offline_active_count == 1
    assert payload.summary.diagnostics_recommended_count == 1
    assert payload.summary.closure_blocked_count == 1
    failed = next(section for section in payload.sections if section.key == "failed_operation")
    assert failed.items[0].operation.error_summary == "Profile missing"
    assert failed.items[0].href == "/app/tickets/ticket-1"
    approval = next(section for section in payload.sections if section.key == "pending_approval")
    assert "service-owner" in approval.items[0].reason
    diagnostics = next(section for section in payload.sections if section.key == "diagnostics_recommended")
    assert diagnostics.items[0].diagnostics.profile_code == "vpn"


@pytest.mark.no_db
def test_command_center_builds_deterministic_similar_spike_group():
    now = datetime(2026, 5, 19, 10, 0, tzinfo=timezone.utc)
    entries = []
    for index in range(3):
        queue_item = item(
            f"ticket-{index}",
            "Codex CC similar spike Directum 3577fba",
            updated_at=(now - timedelta(minutes=index)).isoformat(),
            requires_operator_action=False,
        )
        entries.append(({"ticket_id": queue_item.ticket_id, "status": "queued", "service_code": "network"}, queue_item))

    payload = build_operator_command_center_payload(
        entries,
        scope="team",
        queue=None,
        assignee=None,
        query=None,
        limit_per_section=8,
        window_hours=24,
        sla_risk_minutes=120,
        ola_risk_minutes=60,
        generated_at=now,
    )

    section = next(section for section in payload.sections if section.key == "similar_tickets_spike")
    assert section.count == 1
    assert section.items[0].similar_group.count == 3
    assert section.items[0].href.startswith("/app/tickets?search=")
    assert parse_qs(urlparse(section.items[0].href).query)["search"] == [
        "Codex CC similar spike Directum 3577fba"
    ]


@pytest.mark.no_db
def test_command_center_filters_by_query_before_counting_sections():
    now = datetime(2026, 5, 19, 10, 0, tzinfo=timezone.utc)
    vpn_item = item("ticket-vpn", "VPN client error 720", requires_operator_action=False)
    printer_item = item("ticket-prn", "Printer spooler failed", requires_operator_action=False)

    payload = build_operator_command_center_payload(
        [
            ({"ticket_id": vpn_item.ticket_id, "status": "queued", "service_code": "network"}, vpn_item),
            ({"ticket_id": printer_item.ticket_id, "status": "queued", "service_code": "workplace"}, printer_item),
        ],
        scope="team",
        queue=None,
        assignee=None,
        query="VPN",
        limit_per_section=8,
        window_hours=24,
        sla_risk_minutes=120,
        ola_risk_minutes=60,
        generated_at=now,
    )

    assert payload.filters.query == "VPN"
    assert payload.summary.new_unassigned_count == 1
    new_section = next(section for section in payload.sections if section.key == "new_unassigned")
    assert new_section.items[0].ticket_id == "ticket-vpn"


@pytest.mark.no_db
def test_command_center_uses_safe_display_fallbacks_for_junk_text():
    now = datetime(2026, 5, 19, 10, 0, tzinfo=timezone.utc)
    junk_item = item(
        "ticket-junk",
        "???",
        requester_display_name="ÐÐ½Ð¸ÑÐ¸Ð°ÑÐ¾Ñ",
        requires_operator_action=False,
    )

    payload = build_operator_command_center_payload(
        [({"ticket_id": junk_item.ticket_id, "status": "queued"}, junk_item)],
        scope="team",
        queue=None,
        assignee=None,
        query=None,
        limit_per_section=8,
        window_hours=24,
        sla_risk_minutes=120,
        ola_risk_minutes=60,
        generated_at=now,
    )

    new_section = next(section for section in payload.sections if section.key == "new_unassigned")
    assert new_section.items[0].title == "Без названия"
    assert new_section.items[0].requester_name == "Пользователь не указан"


@pytest.mark.no_db
def test_command_center_unread_uses_read_cursor_not_pending_reply_state():
    now = datetime(2026, 5, 19, 10, 0, tzinfo=timezone.utc)
    ticket_data = {
        "ticket_id": "ticket-read",
        "ticket_code": "T-READ",
        "title": "Requester reply was opened",
        "status": "queued",
        "next_action_owner": "support",
        "queue_code": "support",
        "requester_display_name": "Requester",
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "requires_operator_action": True,
        "support_pending_user_messages": 1,
        "support_unread_user_messages": 0,
    }
    queue_item = _build_ticket_item(ticket_data)

    payload = build_operator_command_center_payload(
        [(ticket_data, queue_item)],
        scope="team",
        queue=None,
        assignee=None,
        query=None,
        limit_per_section=8,
        window_hours=24,
        sla_risk_minutes=120,
        ola_risk_minutes=60,
        generated_at=now,
    )

    assert queue_item.unread_user_messages == 0
    assert payload.summary.unread_user_messages_count == 0
    assert payload.summary.operator_action_count == 1
