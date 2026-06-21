from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import ApprovalPolicy, HelpdeskPolicyAudit, Ticket, TicketApproval, TicketEvent, TicketQueue
from app.repos.helpdesk_policy_repo import HelpdeskPolicyRepo
from app.repos.ticket_events_repo import TicketEventsRepo
from tickets.approval_policy import process_approval_policy_timeouts
from tickets.create_flow import create_ticket_with_side_effects
from tickets.workflow_service import TicketWorkflowService


pytestmark = pytest.mark.db_cleanup("tickets")

def _template_context(approval_policy: dict) -> dict:
    return {
        "request_template": {
            "key": "access_request",
            "ticket_type": "access_request",
            "approval_policy": approval_policy,
        }
    }


async def _seed_ticket(
    test_engine,
    *,
    status: str = "waiting_on_approval",
    approval_policy: dict | None = None,
) -> str:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id=f"device-{ticket_id[:8]}",
                title="Нужен доступ к системе",
                description="Проверка политики согласования",
                status=status,
                requester_id="requester-approval",
                ticket_type="access_request",
                custom_fields=_template_context(
                    approval_policy
                    if approval_policy is not None
                    else {
                        "required": True,
                        "approval_mode": "any_one",
                        "statuses": {
                            "waiting_status": "waiting_on_approval",
                            "approved_transition": "in_progress",
                            "rejected_transition": "canceled",
                        },
                    }
                ),
            )
        )
        await session.commit()
    return ticket_id


async def _add_approval(test_engine, ticket_id: str, *, status: str) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(
            TicketApproval(
                ticket_id=ticket_id,
                approval_type="service_owner",
                approver_id="owner-1",
                status=status,
                reason="test approval",
                requested_by="support-test",
                requested_at=datetime.now(timezone.utc),
                decided_at=datetime.now(timezone.utc) if status in {"approved", "rejected"} else None,
            )
        )
        await session.commit()


async def _clear_approval_registry(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        await session.execute(delete(HelpdeskPolicyAudit).where(HelpdeskPolicyAudit.entity_type == "approval_policies"))
        await session.execute(delete(ApprovalPolicy))
        await session.commit()


async def _publish_approval_policy(test_engine, config: dict) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        repo = HelpdeskPolicyRepo(session)
        await repo.publish_policy(
            kind="approval",
            code="access_approval_runtime",
            title="Access approval runtime",
            scope_level="request_template",
            scope_ref="access_request",
            config=config,
            actor_id="admin-test",
            actor_role="admin",
        )
        await session.commit()


async def _transition_ticket(test_engine, ticket_id: str, *, from_status: str, to_status: str) -> dict:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        repo = TicketEventsRepo(session)
        workflow = TicketWorkflowService(session, repo)
        result = await workflow.apply_status_transition(
            ticket_id=ticket_id,
            from_status=from_status,
            to_status=to_status,
            actor_id="support-test",
            actor_role="support",
            reason="approval_policy_check",
            source="test",
        )
        await session.commit()
        return result


async def _transition_ticket_with_reason(
    test_engine,
    ticket_id: str,
    *,
    from_status: str,
    to_status: str,
    reason: str | None,
) -> dict:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        repo = TicketEventsRepo(session)
        workflow = TicketWorkflowService(session, repo)
        result = await workflow.apply_status_transition(
            ticket_id=ticket_id,
            from_status=from_status,
            to_status=to_status,
            actor_id="support-test",
            actor_role="support",
            reason=reason,
            source="test",
        )
        await session.commit()
        return result


@pytest.mark.asyncio
async def test_approval_policy_allows_entering_waiting_status(test_engine) -> None:
    ticket_id = await _seed_ticket(test_engine, status="new")

    result = await _transition_ticket(
        test_engine,
        ticket_id,
        from_status="new",
        to_status="waiting_on_approval",
    )

    assert result["applied"] is True
    assert result["updates"]["status"] == "waiting_on_approval"


@pytest.mark.asyncio
async def test_approval_policy_creates_request_when_entering_waiting_status(test_engine) -> None:
    ticket_id = await _seed_ticket(
        test_engine,
        status="new",
        approval_policy={
            "required": True,
            "approval_mode": "any_one",
            "approver_source": {
                "type": "explicit_user",
                "user_id": "service-owner-1",
            },
            "statuses": {
                "waiting_status": "waiting_on_approval",
                "approved_transition": "in_progress",
                "rejected_transition": "canceled",
            },
        },
    )

    result = await _transition_ticket(
        test_engine,
        ticket_id,
        from_status="new",
        to_status="waiting_on_approval",
    )

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        rows = await session.execute(select(TicketApproval).where(TicketApproval.ticket_id == ticket_id))
        approvals = rows.scalars().all()

    assert len(approvals) == 1
    assert approvals[0].approval_type == "explicit_user"
    assert approvals[0].approver_id == "service-owner-1"
    assert approvals[0].status == "requested"
    assert approvals[0].requested_by == "support-test"
    assert result["event_payload"]["approval_policy"]["requests_created"] == 1
    assert result["event_payload"]["approval_policy"]["approval_requests"][0]["approver_id"] == "service-owner-1"


@pytest.mark.asyncio
async def test_create_flow_enters_approval_waiting_before_queue_status(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    queue_code = f"approval_queue_{uuid.uuid4().hex[:8]}"
    async with session_maker() as session:
        queue = TicketQueue(
            code=queue_code,
            name="Approval Queue",
            is_triage=False,
            is_active=True,
            auto_assign_enabled=False,
        )
        session.add(queue)
        await session.flush()

        created = await create_ticket_with_side_effects(
            session,
            device_id=f"device-{uuid.uuid4().hex[:8]}",
            requester_id="requester-create-approval",
            title="Create flow approval wait",
            description="Approval-required ticket should not enter protected queue status first.",
            user_display_name="Requester",
            include_public_access=False,
            ticket_type="custom_live_access_type",
            extra_custom_fields={
                "request_template": {
                    "key": "custom_live_access",
                    "ticket_type": "custom_live_access_type",
                    "workflow_profile_id": "access_request",
                    "routing_policy": {"default_queue_id": queue.id},
                    "approval_policy": {
                        "required": True,
                        "approval_mode": "any_one",
                        "approver_source": {
                            "type": "explicit_user",
                            "user_id": "service-owner-1",
                        },
                        "protected_statuses": ["queued", "assigned", "in_progress", "resolved"],
                        "statuses": {
                            "waiting_status": "waiting_on_approval",
                            "approved_transition": "in_progress",
                            "rejected_transition": "canceled",
                        },
                    },
                }
            },
        )
        await session.commit()

        ticket = created["ticket"]
        approvals = (
            await session.execute(select(TicketApproval).where(TicketApproval.ticket_id == created["ticket_id"]))
        ).scalars().all()

    assert ticket.status == "waiting_on_approval"
    assert ticket.queue_id == queue.id
    assert len(approvals) == 1
    assert approvals[0].approver_id == "service-owner-1"


@pytest.mark.asyncio
async def test_approval_policy_creates_request_from_form_field_source(test_engine) -> None:
    ticket_id = str(uuid.uuid4())
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id=f"device-{ticket_id[:8]}",
                title="Form field approval",
                description="Owner is selected in the request form.",
                status="new",
                requester_id="requester-approval",
                ticket_type="access_request",
                custom_fields={
                    "request_template": {
                        "key": "access_request",
                        "ticket_type": "access_request",
                        "approval_policy": {
                            "required": True,
                            "approval_mode": "any_one",
                            "approver_source": {
                                "type": "form_field",
                                "field": "system_owner",
                            },
                            "statuses": {
                                "waiting_status": "waiting_on_approval",
                                "approved_transition": "in_progress",
                                "rejected_transition": "canceled",
                            },
                        },
                    },
                    "request_form_data": {
                        "system_owner": "owner-from-form",
                    },
                },
            )
        )
        await session.commit()

    result = await _transition_ticket(
        test_engine,
        ticket_id,
        from_status="new",
        to_status="waiting_on_approval",
    )

    async with session_maker() as session:
        rows = await session.execute(select(TicketApproval).where(TicketApproval.ticket_id == ticket_id))
        approvals = rows.scalars().all()

    assert len(approvals) == 1
    assert approvals[0].approval_type == "form_field"
    assert approvals[0].approver_id == "owner-from-form"
    assert result["event_payload"]["approval_policy"]["approval_requests"][0]["source"] == "form_field"


@pytest.mark.asyncio
async def test_approval_policy_uses_fallback_source_without_duplicate_requests(test_engine) -> None:
    ticket_id = str(uuid.uuid4())
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id=f"device-{ticket_id[:8]}",
                title="Fallback approval",
                description="Service owner is missing, requester manager should approve.",
                status="new",
                requester_id="requester-approval",
                ticket_type="access_request",
                custom_fields={
                    "request_template": {
                        "key": "access_request",
                        "ticket_type": "access_request",
                        "approval_policy": {
                            "required": True,
                            "approval_mode": "any_one",
                            "approver_source": {
                                "type": "service_owner",
                                "fallback": {
                                    "type": "requester_manager",
                                },
                            },
                            "statuses": {
                                "waiting_status": "waiting_on_approval",
                                "approved_transition": "in_progress",
                                "rejected_transition": "canceled",
                            },
                        },
                    },
                    "requester_profile": {
                        "manager_id": "manager-1",
                    },
                },
            )
        )
        await session.commit()

    first = await _transition_ticket(
        test_engine,
        ticket_id,
        from_status="new",
        to_status="waiting_on_approval",
    )
    second = await _transition_ticket(
        test_engine,
        ticket_id,
        from_status="waiting_on_approval",
        to_status="waiting_on_approval",
    )

    async with session_maker() as session:
        rows = await session.execute(select(TicketApproval).where(TicketApproval.ticket_id == ticket_id))
        approvals = rows.scalars().all()

    assert len(approvals) == 1
    assert approvals[0].approval_type == "requester_manager"
    assert approvals[0].approver_id == "manager-1"
    assert first["event_payload"]["approval_policy"]["requests_created"] == 1
    assert second["event_payload"]["approval_policy"]["requests_created"] == 0


@pytest.mark.asyncio
async def test_approval_policy_sequential_mode_creates_one_requested_step(test_engine) -> None:
    await _clear_approval_registry(test_engine)
    ticket_id = await _seed_ticket(
        test_engine,
        status="new",
        approval_policy={
            "required": True,
            "approval_mode": "sequential",
            "approver_source": {
                "type": "explicit_users",
                "user_ids": ["line-manager", "security-officer"],
            },
            "statuses": {
                "waiting_status": "waiting_on_approval",
                "approved_transition": "in_progress",
                "rejected_transition": "canceled",
            },
        },
    )

    result = await _transition_ticket(
        test_engine,
        ticket_id,
        from_status="new",
        to_status="waiting_on_approval",
    )

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        rows = await session.execute(
            select(TicketApproval)
            .where(TicketApproval.ticket_id == ticket_id)
            .order_by(TicketApproval.id.asc())
        )
        approvals = rows.scalars().all()

    assert [item.approver_id for item in approvals] == ["line-manager", "security-officer"]
    assert [item.status for item in approvals] == ["requested", "pending"]
    assert result["event_payload"]["approval_policy"]["approval_mode"] == "sequential"
    assert [item["status"] for item in result["event_payload"]["approval_policy"]["approval_requests"]] == [
        "requested",
        "pending",
    ]


@pytest.mark.asyncio
async def test_approval_policy_all_mode_requires_every_approval(test_engine) -> None:
    await _clear_approval_registry(test_engine)
    ticket_id = await _seed_ticket(
        test_engine,
        approval_policy={
            "required": True,
            "approval_mode": "all",
            "statuses": {
                "waiting_status": "waiting_on_approval",
                "approved_transition": "in_progress",
                "rejected_transition": "canceled",
            },
        },
    )
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add_all(
            [
                TicketApproval(
                    ticket_id=ticket_id,
                    approval_type="explicit_users",
                    approver_id="line-manager",
                    status="approved",
                    reason="test approval",
                    requested_by="support-test",
                    requested_at=datetime.now(timezone.utc),
                    decided_at=datetime.now(timezone.utc),
                ),
                TicketApproval(
                    ticket_id=ticket_id,
                    approval_type="explicit_users",
                    approver_id="security-officer",
                    status="requested",
                    reason="test approval",
                    requested_by="support-test",
                    requested_at=datetime.now(timezone.utc),
                ),
            ]
        )
        await session.commit()

    with pytest.raises(ValueError, match="all approvals"):
        await _transition_ticket(
            test_engine,
            ticket_id,
            from_status="waiting_on_approval",
            to_status="in_progress",
        )

    async with session_maker() as session:
        rows = await session.execute(select(TicketApproval).where(TicketApproval.ticket_id == ticket_id))
        for approval in rows.scalars().all():
            approval.status = "approved"
            approval.decided_at = datetime.now(timezone.utc)
        await session.commit()

    result = await _transition_ticket(
        test_engine,
        ticket_id,
        from_status="waiting_on_approval",
        to_status="in_progress",
    )

    assert result["updates"]["status"] == "in_progress"
    assert result["event_payload"]["approval_policy"]["approval_mode"] == "all"
    assert result["event_payload"]["approval_policy"]["approved_count"] == 2


@pytest.mark.asyncio
async def test_approval_policy_timeout_runtime_emits_reminder_escalation_and_timeout(test_engine) -> None:
    await _clear_approval_registry(test_engine)
    ticket_id = await _seed_ticket(
        test_engine,
        status="new",
        approval_policy={
            "required": True,
            "approval_mode": "any_one",
            "approver_source": {"type": "explicit_user", "user_id": "service-owner-1"},
            "timeout": {
                "due_in": "1h",
                "reminder_after": "30m",
                "escalate_after": "45m",
            },
            "statuses": {
                "waiting_status": "waiting_on_approval",
                "approved_transition": "in_progress",
                "rejected_transition": "canceled",
            },
        },
    )
    await _transition_ticket(
        test_engine,
        ticket_id,
        from_status="new",
        to_status="waiting_on_approval",
    )

    requested_at = datetime(2026, 5, 2, 10, 0, tzinfo=timezone.utc)
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        approval = (
            await session.execute(select(TicketApproval).where(TicketApproval.ticket_id == ticket_id))
        ).scalar_one()
        approval.requested_at = requested_at
        await session.commit()

    async with session_maker() as session:
        repo = TicketEventsRepo(session)
        assert await process_approval_policy_timeouts(session, repo, now=requested_at + timedelta(minutes=31)) == 1
        assert await process_approval_policy_timeouts(session, repo, now=requested_at + timedelta(minutes=46)) == 1
        assert await process_approval_policy_timeouts(session, repo, now=requested_at + timedelta(minutes=61)) == 1
        assert await process_approval_policy_timeouts(session, repo, now=requested_at + timedelta(minutes=62)) == 0
        await session.commit()

    async with session_maker() as session:
        event_rows = await session.execute(
            select(TicketEvent)
            .where(
                TicketEvent.ticket_id == ticket_id,
                TicketEvent.event_type.in_(
                    ["approval_reminder_due", "approval_escalated", "approval_timed_out"]
                ),
            )
            .order_by(TicketEvent.created_at.asc(), TicketEvent.id.asc())
        )
        events = event_rows.scalars().all()
        approval = (
            await session.execute(select(TicketApproval).where(TicketApproval.ticket_id == ticket_id))
        ).scalar_one()

    assert [event.event_type for event in events] == [
        "approval_reminder_due",
        "approval_escalated",
        "approval_timed_out",
    ]
    assert events[0].payload["approval_policy"]["timeout"]["reminder_after"] == "30m"
    assert events[1].payload["approval_policy"]["timeout"]["escalate_after"] == "45m"
    assert events[2].payload["due_at"] == (requested_at + timedelta(hours=1)).isoformat()
    assert approval.status == "timed_out"


@pytest.mark.asyncio
async def test_approval_policy_requires_comment_on_reject_transition(test_engine) -> None:
    await _clear_approval_registry(test_engine)
    ticket_id = await _seed_ticket(
        test_engine,
        approval_policy={
            "required": True,
            "approval_mode": "any_one",
            "require_comment_on_reject": True,
            "statuses": {
                "waiting_status": "waiting_on_approval",
                "approved_transition": "in_progress",
                "rejected_transition": "canceled",
            },
        },
    )

    with pytest.raises(ValueError, match="reject comment"):
        await _transition_ticket_with_reason(
            test_engine,
            ticket_id,
            from_status="waiting_on_approval",
            to_status="canceled",
            reason=None,
        )

    result = await _transition_ticket_with_reason(
        test_engine,
        ticket_id,
        from_status="waiting_on_approval",
        to_status="canceled",
        reason="Владелец сервиса отказал в доступе",
    )

    assert result["updates"]["status"] == "canceled"
    assert result["event_payload"]["approval_policy"]["require_comment_on_reject"] is True


@pytest.mark.asyncio
async def test_approval_policy_blocks_execution_without_approval(test_engine) -> None:
    ticket_id = await _seed_ticket(test_engine)

    with pytest.raises(ValueError, match="approval_policy"):
        await _transition_ticket(
            test_engine,
            ticket_id,
            from_status="waiting_on_approval",
            to_status="in_progress",
        )


@pytest.mark.asyncio
async def test_approval_policy_resolves_from_registry_during_transition(test_engine) -> None:
    await _clear_approval_registry(test_engine)
    await _publish_approval_policy(
        test_engine,
        {
            "required": True,
            "approval_mode": "any_one",
            "statuses": {
                "waiting_status": "waiting_on_approval",
                "approved_transition": "in_progress",
                "rejected_transition": "canceled",
            },
        },
    )
    ticket_id = await _seed_ticket(test_engine, approval_policy={})

    with pytest.raises(ValueError, match="approval_policy"):
        await _transition_ticket(
            test_engine,
            ticket_id,
            from_status="waiting_on_approval",
            to_status="in_progress",
        )


@pytest.mark.asyncio
async def test_approval_policy_blocks_execution_after_rejection(test_engine) -> None:
    ticket_id = await _seed_ticket(test_engine)
    await _add_approval(test_engine, ticket_id, status="rejected")

    with pytest.raises(ValueError, match="rejected"):
        await _transition_ticket(
            test_engine,
            ticket_id,
            from_status="waiting_on_approval",
            to_status="in_progress",
        )


@pytest.mark.asyncio
async def test_approval_policy_allows_execution_after_approval(test_engine) -> None:
    ticket_id = await _seed_ticket(test_engine)
    await _add_approval(test_engine, ticket_id, status="approved")

    result = await _transition_ticket(
        test_engine,
        ticket_id,
        from_status="waiting_on_approval",
        to_status="in_progress",
    )

    assert result["applied"] is True
    assert result["updates"]["status"] == "in_progress"
    assert result["event_payload"]["approval_policy"]["approved_count"] == 1
