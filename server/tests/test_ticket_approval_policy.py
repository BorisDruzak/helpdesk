from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Ticket, TicketApproval
from app.repos.ticket_events_repo import TicketEventsRepo
from tickets.workflow_service import TicketWorkflowService


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
