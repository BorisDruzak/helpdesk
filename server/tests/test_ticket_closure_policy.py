from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import ClosurePolicy, HelpdeskPolicyAudit, Ticket, TicketEvidenceItem
from app.repos.helpdesk_policy_repo import HelpdeskPolicyRepo
from app.repos.ticket_events_repo import TicketEventsRepo
from tickets.workflow_service import TicketWorkflowService


def _template_context(closure_policy: dict) -> dict:
    return {
        "request_template": {
            "key": "website_unavailable",
            "ticket_type": "incident",
            "closure_policy": closure_policy,
        }
    }


async def _seed_ticket(test_engine, *, closure_policy: dict, priority_class: str = "P2") -> str:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    legacy_priority = {"P0": "P1", "P1": "P2", "P2": "P3", "P3": "P4"}[priority_class]
    async with session_maker() as session:
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id=f"device-{ticket_id[:8]}",
                title="Не открывается сайт",
                description="Проверка политики закрытия",
                status="in_progress",
                requester_id="requester-closure",
                ticket_type="incident",
                priority=legacy_priority,
                custom_fields={
                    **_template_context(closure_policy),
                    "priority_class": priority_class,
                },
            )
        )
        await session.commit()
    return ticket_id


async def _clear_closure_registry(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        await session.execute(delete(HelpdeskPolicyAudit).where(HelpdeskPolicyAudit.entity_type == "closure_policies"))
        await session.execute(delete(ClosurePolicy))
        await session.commit()


async def _publish_closure_policy(test_engine, config: dict) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        repo = HelpdeskPolicyRepo(session)
        await repo.publish_policy(
            kind="closure",
            code="website_closure_runtime",
            title="Website closure runtime",
            scope_level="request_template",
            scope_ref="website_unavailable",
            config=config,
            actor_id="admin-test",
            actor_role="admin",
        )
        await session.commit()


async def _resolve_ticket(
    test_engine,
    ticket_id: str,
    *,
    resolution_code: str | None = None,
    resolution_summary: str | None = None,
) -> dict:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        repo = TicketEventsRepo(session)
        workflow = TicketWorkflowService(session, repo)
        result = await workflow.apply_status_transition(
            ticket_id=ticket_id,
            from_status="in_progress",
            to_status="resolved",
            actor_id="support-test",
            actor_role="support",
            reason="resolution_attempt",
            resolution_code=resolution_code,
            resolution_summary=resolution_summary,
            source="test",
        )
        await session.commit()
        return result


@pytest.mark.asyncio
async def test_closure_policy_requires_resolution_code(test_engine) -> None:
    ticket_id = await _seed_ticket(
        test_engine,
        closure_policy={"require_resolution_code": True},
    )

    with pytest.raises(ValueError, match="resolution_code"):
        await _resolve_ticket(test_engine, ticket_id)


@pytest.mark.asyncio
async def test_closure_policy_resolves_from_registry_during_transition(test_engine) -> None:
    await _clear_closure_registry(test_engine)
    await _publish_closure_policy(test_engine, {"require_resolution_code": True})
    ticket_id = await _seed_ticket(test_engine, closure_policy={})

    with pytest.raises(ValueError, match="resolution_code"):
        await _resolve_ticket(test_engine, ticket_id)


@pytest.mark.asyncio
async def test_closure_policy_requires_public_summary(test_engine) -> None:
    ticket_id = await _seed_ticket(
        test_engine,
        closure_policy={"require_public_summary": True},
    )

    with pytest.raises(ValueError, match="resolution_summary"):
        await _resolve_ticket(test_engine, ticket_id, resolution_code="fixed_remote")


@pytest.mark.asyncio
async def test_closure_policy_requires_evidence_for_priority(test_engine) -> None:
    ticket_id = await _seed_ticket(
        test_engine,
        priority_class="P0",
        closure_policy={
            "require_resolution_code": True,
            "require_public_summary": True,
            "require_evidence_for_priorities": ["P0", "P1"],
        },
    )

    with pytest.raises(ValueError, match="evidence"):
        await _resolve_ticket(
            test_engine,
            ticket_id,
            resolution_code="fixed_remote",
            resolution_summary="DNS switched to reserve resolver.",
        )


@pytest.mark.asyncio
async def test_closure_policy_allows_resolution_when_requirements_are_met(test_engine) -> None:
    ticket_id = await _seed_ticket(
        test_engine,
        priority_class="P0",
        closure_policy={
            "require_resolution_code": True,
            "require_public_summary": True,
            "require_evidence_for_priorities": ["P0", "P1"],
        },
    )
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(
            TicketEvidenceItem(
                ticket_id=ticket_id,
                evidence_type="diagnostic_result",
                title="DNS check passed",
                summary="Resolver returned an address after the fix.",
                source_ref="operation:test",
                visibility="internal",
                created_by="support-test",
            )
        )
        await session.commit()

    result = await _resolve_ticket(
        test_engine,
        ticket_id,
        resolution_code="fixed_remote",
        resolution_summary="DNS switched to reserve resolver.",
    )

    assert result["applied"] is True
    assert result["updates"]["status"] == "resolved"
    assert result["updates"]["resolution_code"] == "fixed_remote"
    assert result["updates"]["resolution_summary"] == "DNS switched to reserve resolver."
