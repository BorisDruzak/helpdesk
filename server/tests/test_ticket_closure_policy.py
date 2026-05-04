from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import (
    ClosurePolicy,
    HelpdeskPolicyAudit,
    ReportingPolicy,
    Ticket,
    TicketActionLog,
    TicketApproval,
    TicketEvidenceItem,
)
from app.repos.helpdesk_policy_repo import HelpdeskPolicyRepo
from app.repos.ticket_events_repo import TicketEventsRepo
from app.services.ticket_auto_close_watchdog import TicketAutoCloseWatchdog
from tickets.workflow_service import TicketWorkflowService
from tickets.passport_service import TicketPassportService
from tickets.closure_policy import build_closure_requirements


def _template_context(closure_policy: dict, *, approval_policy: dict | None = None) -> dict:
    return {
        "request_template": {
            "key": "website_unavailable",
            "ticket_type": "incident",
            "closure_policy": closure_policy,
            **({"approval_policy": approval_policy} if approval_policy is not None else {}),
        }
    }


async def _seed_ticket(
    test_engine,
    *,
    closure_policy: dict,
    priority_class: str = "P2",
    approval_policy: dict | None = None,
) -> str:
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
                    **_template_context(closure_policy, approval_policy=approval_policy),
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
        await session.execute(delete(HelpdeskPolicyAudit).where(HelpdeskPolicyAudit.entity_type == "reporting_policies"))
        await session.execute(delete(ClosurePolicy))
        await session.execute(delete(ReportingPolicy))
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


async def _clear_reporting_registry(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        await session.execute(delete(HelpdeskPolicyAudit).where(HelpdeskPolicyAudit.entity_type == "reporting_policies"))
        await session.execute(delete(ReportingPolicy))
        await session.commit()


async def _publish_reporting_policy(test_engine, config: dict) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        repo = HelpdeskPolicyRepo(session)
        await repo.publish_policy(
            kind="reporting",
            code="website_reporting_runtime",
            title="Website reporting runtime",
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
    requester_resolution_summary: str | None = None,
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
            requester_resolution_summary=requester_resolution_summary,
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
async def test_closure_policy_rejects_rejected_evidence_for_priority(test_engine) -> None:
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
                title="Rejected check",
                summary="Operator rejected this proof.",
                source_ref="operation:rejected",
                visibility="internal",
                verification_status="rejected",
                created_by="support-test",
            )
        )
        await session.commit()

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


@pytest.mark.asyncio
async def test_closure_policy_supports_nested_summary_and_resolution_code_whitelist(test_engine) -> None:
    ticket_id = await _seed_ticket(
        test_engine,
        closure_policy={
            "before_resolved": {
                "require_resolution_code": True,
                "require_public_summary": True,
                "require_internal_summary": True,
            },
            "allowed_resolution_codes": ["fixed_remote", "workaround_provided"],
        },
    )

    with pytest.raises(ValueError, match="allowed_resolution_codes"):
        await _resolve_ticket(
            test_engine,
            ticket_id,
            resolution_code="done",
            resolution_summary="Internal fix details",
            requester_resolution_summary="Сайт снова открывается.",
        )

    with pytest.raises(ValueError, match="internal_summary"):
        await _resolve_ticket(
            test_engine,
            ticket_id,
            resolution_code="fixed_remote",
            requester_resolution_summary="Сайт снова открывается.",
        )

    result = await _resolve_ticket(
        test_engine,
        ticket_id,
        resolution_code="fixed_remote",
        resolution_summary="DNS switched to reserve resolver.",
        requester_resolution_summary="Сайт снова открывается.",
    )

    assert result["event_payload"]["closure_policy"]["policy"]["before_resolved"]["require_internal_summary"] is True
    assert result["event_payload"]["closure_policy"]["policy"]["allowed_resolution_codes"] == [
        "fixed_remote",
        "workaround_provided",
    ]


@pytest.mark.asyncio
async def test_closure_policy_requires_operation_log_when_module_was_used(test_engine) -> None:
    ticket_id = await _seed_ticket(
        test_engine,
        closure_policy={
            "before_resolved": {
                "require_resolution_code": True,
                "require_public_summary": True,
            },
            "evidence": {"require_operation_log_if_module_used": True},
        },
    )
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        repo = TicketEventsRepo(session)
        ticket = await repo.get_ticket(ticket_id)
        await repo.add_event(
            ticket_id=ticket_id,
            device_id=ticket.device_id,
            agent_seq=None,
            event_type="tool_call_started",
            payload={"event": "tool_call_started", "tool_name": "dns.resolve"},
            operation_id=str(uuid.uuid4()),
        )
        await session.commit()

    with pytest.raises(ValueError, match="operation_log"):
        await _resolve_ticket(
            test_engine,
            ticket_id,
            resolution_code="fixed_remote",
            requester_resolution_summary="Сайт снова открывается.",
        )

    async with session_maker() as session:
        session.add(
            TicketActionLog(
                ticket_id=ticket_id,
                action_type="diagnostic_operation",
                title="dns.resolve",
                summary="Diagnostic module ran before closure.",
                actor_id="support-test",
                operation_id=str(uuid.uuid4()),
            )
        )
        await session.commit()

    result = await _resolve_ticket(
        test_engine,
        ticket_id,
        resolution_code="fixed_remote",
        requester_resolution_summary="Сайт снова открывается.",
    )

    assert result["event_payload"]["closure_policy"]["operation_log_required"] is True


@pytest.mark.asyncio
async def test_closure_policy_requires_approved_approval_when_policy_was_used(test_engine) -> None:
    ticket_id = await _seed_ticket(
        test_engine,
        closure_policy={
            "before_resolved": {
                "require_resolution_code": True,
                "require_public_summary": True,
            },
            "evidence": {"require_approval_if_approval_policy_used": True},
        },
        approval_policy={"required": True, "approval_mode": "any_one"},
    )

    with pytest.raises(ValueError, match="approved approval"):
        await _resolve_ticket(
            test_engine,
            ticket_id,
            resolution_code="fixed_remote",
            requester_resolution_summary="Сайт снова открывается.",
        )

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(
            TicketApproval(
                ticket_id=ticket_id,
                approval_type="service_owner",
                approver_id="owner-1",
                status="approved",
                requested_by="support-test",
            )
        )
        await session.commit()

    result = await _resolve_ticket(
        test_engine,
        ticket_id,
        resolution_code="fixed_remote",
        requester_resolution_summary="Сайт снова открывается.",
    )

    assert result["event_payload"]["closure_policy"]["approval_evidence_required"] is True


@pytest.mark.asyncio
async def test_closure_policy_records_requester_confirmation_metadata(test_engine) -> None:
    ticket_id = await _seed_ticket(
        test_engine,
        closure_policy={
            "before_resolved": {
                "require_resolution_code": True,
                "require_public_summary": True,
            },
            "requester_confirmation": {
                "required": True,
                "auto_close_after_days": 3,
                "reopen_on_negative_feedback": True,
            },
        },
    )

    result = await _resolve_ticket(
        test_engine,
        ticket_id,
        resolution_code="fixed_remote",
        requester_resolution_summary="Сайт снова открывается.",
    )

    confirmation = result["event_payload"]["closure_policy"]["requester_confirmation"]
    assert confirmation == {
        "required": True,
        "auto_close_after_days": 3,
        "reopen_on_negative_feedback": True,
    }
    assert result["updates"]["custom_fields"]["resolution_confirmation_policy"] == confirmation


@pytest.mark.asyncio
async def test_closure_policy_auto_close_uses_policy_days(test_engine) -> None:
    ticket_id = await _seed_ticket(
        test_engine,
        closure_policy={
            "before_resolved": {
                "require_resolution_code": True,
                "require_public_summary": True,
            },
            "requester_confirmation": {
                "required": True,
                "auto_close_after_days": 1,
                "reopen_on_negative_feedback": True,
            },
        },
    )

    await _resolve_ticket(
        test_engine,
        ticket_id,
        resolution_code="fixed_remote",
        requester_resolution_summary="Сайт снова открывается.",
    )

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        ticket.resolved_at = datetime.now(timezone.utc) - timedelta(days=2)
        custom_fields = dict(ticket.custom_fields or {})
        custom_fields["resolution_confirmation"] = {
            "pending": True,
            "request_id": str(uuid.uuid4()),
        }
        custom_fields["resolution_confirmation_pending"] = True
        ticket.custom_fields = custom_fields
        await session.commit()

    watchdog = TicketAutoCloseWatchdog(session_factory=session_maker)
    closed_count = await watchdog.process_once(now=datetime.now(timezone.utc), limit=10)

    assert closed_count == 1
    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        assert ticket.status == "closed"
        confirmation = (ticket.custom_fields or {}).get("resolution_confirmation") or {}
        assert confirmation.get("pending") is False
        assert confirmation.get("responded_option_id") == "auto_close"


@pytest.mark.asyncio
async def test_closure_requires_official_passport_only_when_reporting_policy_requires_it(test_engine) -> None:
    await _clear_reporting_registry(test_engine)
    await _publish_reporting_policy(
        test_engine,
        {
            "required_sections": ["problem", "evidence", "user_result"],
            "require_official_passport": True,
        },
    )
    ticket_id = await _seed_ticket(
        test_engine,
        closure_policy={
            "before_resolved": {
                "require_resolution_code": True,
                "require_public_summary": True,
            }
        },
    )

    with pytest.raises(ValueError, match="official passport"):
        await _resolve_ticket(
            test_engine,
            ticket_id,
            resolution_code="fixed_remote",
            requester_resolution_summary="Сайт снова открывается.",
        )

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        await TicketPassportService(session).generate(ticket_id, actor_id="op1", mode="create")
        await session.commit()

    with pytest.raises(ValueError, match="passport missing required facts"):
        await _resolve_ticket(
            test_engine,
            ticket_id,
            resolution_code="fixed_remote",
            requester_resolution_summary="Сайт снова открывается.",
        )

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        ticket.requester_resolution_summary = "Сайт снова открывается."
        session.add(
            TicketEvidenceItem(
                ticket_id=ticket_id,
                evidence_type="diagnostic_result",
                title="HTTP check",
                summary="HTTP 200 OK",
                source_ref="operation:test",
                visibility="internal",
                created_by="support-test",
            )
        )
        await TicketPassportService(session).generate(ticket_id, actor_id="op1", mode="refresh")
        await session.commit()

    result = await _resolve_ticket(
        test_engine,
        ticket_id,
        resolution_code="fixed_remote",
        requester_resolution_summary="Сайт снова открывается.",
    )

    assert result["applied"] is True
    assert result["event_payload"]["closure_policy"]["official_passport_required"] is True


@pytest.mark.asyncio
async def test_closure_passport_accepts_transition_summary_for_user_result(test_engine) -> None:
    await _clear_reporting_registry(test_engine)
    await _publish_reporting_policy(
        test_engine,
        {
            "required_sections": ["problem", "evidence", "user_result"],
            "require_official_passport": True,
        },
    )
    ticket_id = await _seed_ticket(
        test_engine,
        closure_policy={
            "before_resolved": {
                "require_resolution_code": True,
                "require_public_summary": True,
            }
        },
    )

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(
            TicketEvidenceItem(
                ticket_id=ticket_id,
                evidence_type="diagnostic_result",
                title="HTTP check",
                summary="HTTP 200 OK",
                source_ref="operation:test",
                visibility="internal",
                created_by="support-test",
            )
        )
        payload = await TicketPassportService(session).generate(ticket_id, actor_id="op1", mode="create")
        await session.commit()

    missing_by_key = {item["required_fact"]: item for item in payload["requirements"]["missing_facts"]}
    assert set(missing_by_key) == {"user_result"}

    result = await _resolve_ticket(
        test_engine,
        ticket_id,
        resolution_code="fixed_remote",
        requester_resolution_summary="Website is available again.",
    )

    assert result["applied"] is True
    assert result["event_payload"]["closure_policy"]["official_passport_required"] is True


@pytest.mark.asyncio
async def test_closure_passport_allows_non_applicable_reporting_sections(test_engine) -> None:
    await _clear_reporting_registry(test_engine)
    await _publish_reporting_policy(
        test_engine,
        {
            "required_sections": ["problem", "automated_checks", "approvals", "evidence", "user_result"],
            "require_official_passport": True,
        },
    )
    ticket_id = await _seed_ticket(
        test_engine,
        closure_policy={
            "before_resolved": {
                "require_resolution_code": True,
                "require_public_summary": True,
            },
            "evidence": {
                "require_operation_log_if_module_used": True,
                "require_approval_if_approval_policy_used": True,
            },
        },
    )

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(
            TicketEvidenceItem(
                ticket_id=ticket_id,
                evidence_type="diagnostic_result",
                title="Manual browser check",
                summary="Live UI check passed",
                source_ref="stage17:browser",
                visibility="internal",
                created_by="support-test",
            )
        )
        payload = await TicketPassportService(session).generate(ticket_id, actor_id="op1", mode="create")
        await session.commit()

    missing_by_key = {item["required_fact"]: item for item in payload["requirements"]["missing_facts"]}
    assert {"approvals", "user_result"}.issubset(missing_by_key)
    assert "automated_checks" not in missing_by_key

    result = await _resolve_ticket(
        test_engine,
        ticket_id,
        resolution_code="fixed_remote",
        requester_resolution_summary="Website is available again.",
    )

    assert result["applied"] is True
    assert result["event_payload"]["closure_policy"]["official_passport_required"] is True


@pytest.mark.asyncio
async def test_closure_requirements_include_official_passport_missing_facts(test_engine) -> None:
    await _clear_reporting_registry(test_engine)
    await _publish_reporting_policy(
        test_engine,
        {
            "required_sections": ["problem", "evidence", "user_result"],
            "require_official_passport": True,
        },
    )
    ticket_id = await _seed_ticket(
        test_engine,
        closure_policy={
            "before_resolved": {
                "require_resolution_code": True,
                "require_public_summary": True,
            },
        },
    )

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        await TicketPassportService(session).generate(ticket_id, actor_id="op1", mode="create")
        requirements = await build_closure_requirements(session, ticket)

    by_key = {item["key"]: item for item in requirements}
    assert by_key["passport_missing:evidence"]["met"] is False
    assert by_key["passport_missing:evidence"]["fact_key"] == "evidence"
    assert by_key["passport_missing:evidence"]["recommended_actions"]
    assert by_key["passport_missing:user_result"]["met"] is False
    assert by_key["passport_missing:user_result"]["fact_key"] == "user_result"


@pytest.mark.asyncio
async def test_closure_does_not_require_passport_when_reporting_policy_does_not_require_it(test_engine) -> None:
    await _clear_reporting_registry(test_engine)
    await _publish_reporting_policy(
        test_engine,
        {
            "required_sections": ["problem", "evidence", "user_result"],
            "require_official_passport": False,
        },
    )
    ticket_id = await _seed_ticket(
        test_engine,
        closure_policy={
            "before_resolved": {
                "require_resolution_code": True,
                "require_public_summary": True,
            }
        },
    )

    result = await _resolve_ticket(
        test_engine,
        ticket_id,
        resolution_code="fixed_remote",
        requester_resolution_summary="Сайт снова открывается.",
    )

    assert result["applied"] is True
