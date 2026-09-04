import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Change, ChangeApproval, Operation, RemoteAccessSession, Ticket, TicketApproval
from tests.conftest import TEST_UI_ADMIN_TOKEN, TEST_UI_SUPPORT_TOKEN, TEST_UI_USER_PREFIX

pytestmark = pytest.mark.db_cleanup("full")


def _admin_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_UI_ADMIN_TOKEN}"}


def _support_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_UI_SUPPORT_TOKEN}"}


def _requester_headers(actor_id: str = "requester-approvals-denied") -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_UI_USER_PREFIX}{actor_id}"}


async def _seed_approval_center(session, *, now: datetime) -> dict[str, str]:
    ticket_id = str(uuid.uuid4())
    closure_ticket_id = str(uuid.uuid4())
    change_id = str(uuid.uuid4())
    operation_id = str(uuid.uuid4())
    remote_session_id = str(uuid.uuid4())
    device_id = f"device-approval-{uuid.uuid4().hex[:8]}"

    session.add(
        Ticket(
            ticket_id=ticket_id,
            ticket_code="T-APPROVAL-1",
            device_id=device_id,
            title="Нужен доступ к Directum",
            description="Запрос доступа",
            status="waiting_on_approval",
            priority="P2",
            requester_id="requester-1",
            assignee_id="support-1",
            queue_id=None,
            service_code="directum",
            offering_code="directum.access",
            resolution_due_at=now + timedelta(hours=2),
        )
    )
    session.add(
        TicketApproval(
            ticket_id=ticket_id,
            approval_type="manager",
            approver_id="manager-1",
            status="requested",
            reason="Требуется согласование владельца услуги",
            requested_by="support-1",
            requested_at=now - timedelta(minutes=20),
        )
    )
    session.add(
        Ticket(
            ticket_id=closure_ticket_id,
            ticket_code="T-CLOSURE-1",
            device_id=device_id,
            title="Закрытие требует подтверждения",
            description="Паспорт решения",
            status="resolved",
            priority="P3",
            requester_id="requester-2",
            assignee_id="support-1",
            queue_id=None,
        )
    )
    session.add(
        TicketApproval(
            ticket_id=closure_ticket_id,
            approval_type="closure",
            approver_id="qa-1",
            status="requested",
            reason="Нужно подтверждение закрытия",
            requested_by="support-1",
            requested_at=now - timedelta(minutes=10),
        )
    )
    session.add(
        Change(
            change_id=change_id,
            change_key="CHG-APPROVAL",
            title="Обновить Directum",
            description="Плановое обновление",
            status="awaiting_approval",
            risk_level="critical",
            impact_level="high",
            priority="high",
            service_code="directum",
            offering_code="directum.core",
            assignee_actor_id="support-1",
            queue_id=None,
            requested_by_actor_id="owner-1",
            planned_start_at=now + timedelta(hours=4),
            planned_end_at=now + timedelta(hours=5),
        )
    )
    session.add(
        ChangeApproval(
            approval_id=str(uuid.uuid4()),
            change_id=change_id,
            approval_stage="cab",
            approver_actor_id="cab-1",
            approver_group="CAB",
            status="pending",
            requested_at=now - timedelta(hours=1),
            due_at=now - timedelta(minutes=1),
        )
    )
    session.add(
        Operation(
            operation_id=operation_id,
            device_id=device_id,
            ticket_id=ticket_id,
            kind="tool",
            tool_name="powershell.exec",
            actor_role="support",
            trace_id=str(uuid.uuid4()),
            status="waiting_consent",
            queued_at=now - timedelta(minutes=8),
            deadline_at=now + timedelta(minutes=30),
            error_message="secret=must-not-leak",
        )
    )
    session.add(
        RemoteAccessSession(
            id=remote_session_id,
            ticket_id=ticket_id,
            device_id=device_id,
            operator_id="support-1",
            requester_id="requester-1",
            mode="view_only",
            status="waiting_consent",
            reason="Нужно визуально проверить ошибку",
            consent_required=True,
            consent_status="pending",
            requested_at=now - timedelta(minutes=5),
            expires_at=now + timedelta(minutes=15),
            signaling_token_hash="secret-signaling-hash",
            operator_token_hash="secret-operator-hash",
            agent_token_hash="secret-agent-hash",
            ice_config={"turn": "secret-turn"},
        )
    )
    await session.commit()
    return {
        "ticket_id": ticket_id,
        "closure_ticket_id": closure_ticket_id,
        "change_id": change_id,
        "operation_id": operation_id,
        "remote_session_id": remote_session_id,
    }


@pytest.mark.asyncio
async def test_approval_consent_center_rejects_requester_role(test_client):
    response = await test_client.get("/api/web/support/approvals", headers=_requester_headers())

    assert response.status == 403


@pytest.mark.asyncio
async def test_approval_consent_center_returns_typed_real_sources(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    async with session_maker() as session:
        ids = await _seed_approval_center(session, now=now)

    response = await test_client.get("/api/web/support/approvals?status=pending&scope=all", headers=_admin_headers())

    assert response.status == 200
    payload = await response.json()
    assert payload["status"] == "success"
    data = payload["data"]
    assert data["generated_at"]
    assert data["scope"] == "all"
    assert data["summary"]["ticket_approvals_count"] == 1
    assert data["summary"]["change_approvals_count"] == 1
    assert data["summary"]["risky_tool_consents_count"] == 1
    assert data["summary"]["remote_assist_consents_count"] == 0
    assert data["summary"]["closure_approvals_count"] == 1
    assert data["summary"]["policy_overrides_count"] == 0
    assert {section["key"] for section in data["sections"]} >= {
        "waiting_me",
        "waiting_user",
        "overdue",
        "high_risk",
        "ticket_approvals",
        "change_approvals",
        "risky_tool_consents",
        "closure_approvals",
        "policy_overrides",
    }
    kinds = {item["kind"] for item in data["items"]}
    assert {
        "ticket_approval",
        "change_approval",
        "risky_tool_consent",
        "closure_approval",
    } <= kinds
    ticket_item = next(item for item in data["items"] if item["kind"] == "ticket_approval")
    assert ticket_item["actions"][0]["href"] == f"/app/tickets/{ids['ticket_id']}"
    change_item = next(item for item in data["items"] if item["kind"] == "change_approval")
    assert change_item["actions"][0]["href"] == f"/app/admin/changes?change={ids['change_id']}"

    serialized = str(data)
    assert "secret-signaling-hash" not in serialized
    assert "secret-turn" not in serialized
    assert "must-not-leak" not in serialized


@pytest.mark.asyncio
async def test_approval_consent_center_filters_kind_status_and_risk(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    async with session_maker() as session:
        await _seed_approval_center(session, now=now)

    response = await test_client.get(
        "/api/web/support/approvals?kind=pending_consent&risk=high&status=pending",
        headers=_support_headers(),
    )

    assert response.status == 200
    data = (await response.json())["data"]
    assert data["scope"] == "team"
    assert data["items"]
    assert {item["kind"] for item in data["items"]} <= {"risky_tool_consent"}
    assert {item["risk"] for item in data["items"]} == {"high"}


@pytest.mark.asyncio
async def test_approval_consent_center_support_scope_all_falls_back_to_team(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    async with session_maker() as session:
        await _seed_approval_center(session, now=now)

    response = await test_client.get("/api/web/support/approvals?scope=all", headers=_support_headers())

    assert response.status == 200
    data = (await response.json())["data"]
    assert data["scope"] == "team"
