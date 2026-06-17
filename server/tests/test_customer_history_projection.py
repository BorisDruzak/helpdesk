from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import (
    KnowledgeFeedbackEvent,
    Operation,
    ObserverTrace,
    RegistryPerson,
    RegistryPersonIdentity,
    Ticket,
    TicketEvent,
)
from customer_history.projection_service import CustomerHistoryProjectionService
from tests.conftest import TEST_UI_SUPPORT_TOKEN, TEST_UI_USER_PREFIX


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _seed_history_ticket(test_engine, *, login: str = "history-requester@example.test") -> tuple[str, str]:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    person_id = str(uuid.uuid4())
    ticket_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).replace(microsecond=0)
    async with session_maker() as session:
        person = RegistryPerson(
            person_id=person_id,
            display_name="History Requester",
            full_name="History Requester",
            email=login,
            source="manual",
            status="active",
        )
        session.add(person)
        session.add(
            RegistryPersonIdentity(
                person_id=person_id,
                provider="email",
                identifier=login,
                normalized_identifier=login,
                verified=True,
                source="test",
            )
        )
        ticket_context = {
            "schema": "ticket_context_v1",
            "created_at": now.isoformat(),
            "created_on_behalf": False,
            "creator": {"person_id": person_id, "display_name": "History Requester"},
            "affected": {"person_id": person_id, "display_name": "History Requester"},
            "on_behalf": {"enabled": False, "reason": None},
            "requester_context": {"profile": {"display_name": "History Requester"}},
            "target_device": {"device_id": "history-device", "agent_status": "offline", "hostname": "HISTORY-PC"},
            "diagnostic_target": {
                "device_id": "history-device",
                "source": "creator_primary_agent",
                "agent_status": "offline",
                "hostname": "HISTORY-PC",
            },
            "diagnostic_target_source": "creator_primary_agent",
            "form": {"key": "history_form", "title": "History form"},
            "policy_refs": {"routing_policy": "default"},
            "redaction": {"requester_hidden_fields": ["creator.person_id"]},
        }
        ticket = Ticket(
            ticket_id=ticket_id,
            ticket_code="T-HIST-001",
            device_id="history-device",
            title="History ticket",
            description="History description",
            status="in_progress",
            requester_id=login,
            requester_person_id=person_id,
            custom_fields={
                "ticket_context": ticket_context,
                "secret_token": "must-not-leak",
                "request_form": {"key": "history_form", "title": "History form"},
            },
        )
        session.add(ticket)
        session.add_all(
            [
                TicketEvent(
                    ticket_id=ticket_id,
                    device_id="history-device",
                    agent_seq=None,
                    event_type="ticket_context_resolved",
                    payload={
                        "schema": "ticket_context_v1",
                        "diagnostic_target_source": "creator_primary_agent",
                        "target_available": False,
                        "evidence_codes": ["target_agent_offline"],
                        "token": "must-not-leak",
                    },
                    created_at=now,
                ),
                TicketEvent(
                    ticket_id=ticket_id,
                    device_id="history-device",
                    agent_seq=None,
                    event_type="chat_message",
                    payload={"sender_role": "support", "visibility": "internal", "text": "Internal support note"},
                    created_at=now,
                ),
                TicketEvent(
                    ticket_id=ticket_id,
                    device_id="history-device",
                    agent_seq=None,
                    event_type="chat_message",
                    payload={"sender_role": "user", "visibility": "public", "text": "Requester public message"},
                    created_at=now,
                ),
            ]
        )
        await session.flush()
        session.add(
            KnowledgeFeedbackEvent(
                event_id=str(uuid.uuid4()),
                actor_id=login,
                actor_role="requester",
                ticket_id=ticket_id,
                source_surface="requester_portal",
                event_type="ticket_created_after_view",
                result="not_helpful",
                service_code="svc-history",
                metadata_json={
                    "knowledge_attempts": [
                        {
                            "item_id": "kb-visible",
                            "title": "Visible article",
                            "visibility_scope": "creator_visible",
                            "audience_scope": "creator",
                        },
                        {
                            "item_id": "kb-restricted",
                            "title": "Restricted article",
                            "visibility_scope": "support_only",
                            "audience_scope": "support",
                        },
                    ],
                    "session_id": "must-not-leak",
                },
                created_at=now,
            )
        )
        await session.commit()
    return ticket_id, person_id


@pytest.mark.asyncio
async def test_support_and_requester_history_use_role_specific_projection(test_client, test_engine):
    ticket_id, _person_id = await _seed_history_ticket(test_engine)

    support = await test_client.get(
        f"/api/web/support/tickets/{ticket_id}/history",
        headers=_headers(TEST_UI_SUPPORT_TOKEN),
    )
    support_payload = await support.json()
    assert support.status == 200, support_payload
    support_events = support_payload["data"]["events"]
    assert any(event["source"] == "ticket" and event["event_type"] == "ticket_created" for event in support_events)
    assert any(event["source"] == "knowledge" for event in support_events)
    assert "Internal support note" in str(support_payload)
    assert "must-not-leak" not in str(support_payload)

    requester = await test_client.get(
        f"/api/web/requester/tickets/{ticket_id}/history",
        headers=_headers(f"{TEST_UI_USER_PREFIX}history-requester@example.test"),
    )
    requester_payload = await requester.json()
    assert requester.status == 200, requester_payload
    assert "Requester public message" in str(requester_payload)
    assert "Internal support note" not in str(requester_payload)
    assert "kb-restricted" not in str(requester_payload)
    assert "person_id" not in str(requester_payload["data"]["events"])


@pytest.mark.asyncio
async def test_on_behalf_ticket_appears_for_creator_and_affected_with_relationship_projection(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    creator_id = str(uuid.uuid4())
    affected_id = str(uuid.uuid4())
    ticket_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).replace(microsecond=0)

    async with session_maker() as session:
        session.add_all(
            [
                RegistryPerson(
                    person_id=creator_id,
                    display_name="Creator Person",
                    full_name="Creator Person",
                    source="manual",
                    status="active",
                ),
                RegistryPerson(
                    person_id=affected_id,
                    display_name="Affected Person",
                    full_name="Affected Person",
                    source="manual",
                    status="active",
                ),
            ]
        )
        session.add(
            Ticket(
                ticket_id=ticket_id,
                ticket_code="T-HIST-OBH",
                device_id="affected-device",
                title="On behalf history",
                description="Creator opened this for affected",
                status="new",
                requester_id="creator@example.test",
                requester_person_id=creator_id,
                custom_fields={
                    "ticket_context": {
                        "schema": "ticket_context_v1",
                        "created_on_behalf": True,
                        "creator": {"person_id": creator_id, "display_name": "Creator Person"},
                        "affected": {"person_id": affected_id, "display_name": "Affected Person"},
                        "on_behalf": {"enabled": True, "reason": "PC is offline"},
                        "diagnostic_target": {
                            "device_id": "affected-device",
                            "source": "affected_person_primary_agent",
                            "agent_status": "offline",
                        },
                    }
                },
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()

        service = CustomerHistoryProjectionService(session)
        creator_history = await service.history_for_person(
            creator_id,
            actor_context={"actor_id": "support-test", "actor_role": "support"},
            limit=20,
        )
        affected_history = await service.history_for_person(
            affected_id,
            actor_context={"actor_id": "support-test", "actor_role": "support"},
            limit=20,
        )

    creator_ticket = next(event for event in creator_history["events"] if event.get("ticket_ref") == "T-HIST-OBH")
    affected_ticket = next(event for event in affected_history["events"] if event.get("ticket_ref") == "T-HIST-OBH")
    assert creator_ticket["payload"]["person_history_relationship"] == "creator"
    assert affected_ticket["payload"]["person_history_relationship"] == "affected"
    assert creator_ticket["payload"]["created_on_behalf"] is True
    assert affected_ticket["payload"]["created_on_behalf"] is True


@pytest.mark.asyncio
async def test_support_history_includes_compact_diagnostic_and_observer_summary(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    person_id = str(uuid.uuid4())
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())
    operation_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).replace(microsecond=0)

    async with session_maker() as session:
        session.add(
            RegistryPerson(
                person_id=person_id,
                display_name="Observed Person",
                full_name="Observed Person",
                source="manual",
                status="active",
            )
        )
        session.add(
            Ticket(
                ticket_id=ticket_id,
                ticket_code="T-HIST-OBS",
                device_id=device_id,
                title="Observed ticket",
                description="Diagnostics and observer should be compact",
                status="in_progress",
                requester_id="observed@example.test",
                requester_person_id=person_id,
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            Operation(
                operation_id=operation_id,
                device_id=device_id,
                ticket_id=ticket_id,
                kind="tool_call",
                tool_name="diag.logs.collect",
                actor_role="support",
                trace_id=trace_id,
                status="succeeded",
                queued_at=now,
                started_at=now,
                finished_at=now,
                result_summary="Collected logs",
            )
        )
        session.add(
            ObserverTrace(
                trace_id=trace_id,
                root_kind="ticket_operation",
                ticket_id=ticket_id,
                device_id=device_id,
                operation_id=operation_id,
                status="ok",
                started_at=now,
                finished_at=now,
                span_count=3,
                error_count=0,
                attrs_json={"title": "Diagnostic trace", "raw_request": "must-not-leak"},
            )
        )
        await session.commit()

        history = await CustomerHistoryProjectionService(session).history_for_ticket(
            ticket_id,
            actor_context={"actor_id": "support-test", "actor_role": "support"},
            limit=20,
        )

    assert any(event["source"] == "diagnostics" and event["summary"] == "Collected logs" for event in history["events"])
    observer_events = [event for event in history["events"] if event["source"] == "observer"]
    assert observer_events
    assert observer_events[0]["payload"]["status"] == "ok"
    assert observer_events[0]["payload"]["root_kind"] == "ticket_operation"
    assert observer_events[0]["refs"]["observer_ref"].startswith("trace:")
    assert "must-not-leak" not in str(history)
