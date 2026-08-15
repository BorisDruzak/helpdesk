from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import (
    Device,
    DeviceUserBinding,
    Operation,
    ObserverTrace,
    RegistryPerson,
    RegistryPersonIdentity,
    Ticket,
    TicketEvent,
)
from customer_history.projection_service import CustomerHistoryProjectionService
from tests.conftest import TEST_UI_SUPPORT_TOKEN, TEST_UI_USER_PREFIX

pytestmark = pytest.mark.db_cleanup("full")


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _seed_history_ticket(
    test_engine,
    *,
    login: str = "history-requester@example.test",
    device_id: str = "history-device",
    ticket_code: str = "T-HIST-001",
) -> tuple[str, str]:
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
        session.add(
            RegistryPersonIdentity(
                person_id=person_id,
                provider="ui_login",
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
            "target_device": {"device_id": device_id, "agent_status": "offline", "hostname": "HISTORY-PC"},
            "diagnostic_target": {
                "device_id": device_id,
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
            ticket_code=ticket_code,
            device_id=device_id,
            title="History ticket",
            description="History description",
            status="in_progress",
            requester_id=login,
            requester_person_id=person_id,
            custom_fields={
                "ticket_context": ticket_context,
                "secret_token": "must-not-leak",
                "request_form": {"key": "history_form", "title": "History form"},
                "knowledge_attempts": [
                    {
                        "item_id": "kb-visible",
                        "title": "Visible article",
                        "visibility_scope": "creator_visible",
                        "audience_scope": "creator",
                        "result": "not_helpful",
                        "surface": "requester_portal",
                        "occurred_at": now.isoformat(),
                    },
                    {
                        "item_id": "kb-restricted",
                        "title": "Restricted article",
                        "visibility_scope": "support_only",
                        "audience_scope": "support",
                        "result": "viewed",
                        "surface": "requester_portal",
                        "occurred_at": now.isoformat(),
                    },
                ],
            },
        )
        session.add(ticket)
        session.add(
            Device(
                device_id=device_id,
                protocol_version="ws_ticket_v3",
                agent_version="test",
                hostname="HISTORY-PC",
                os="Windows",
                capabilities={},
            )
        )
        await session.flush()
        session.add(
            DeviceUserBinding(
                device_id=device_id,
                person_id=person_id,
                relationship_type="primary_user",
                status="active",
                source="test",
                created_at=now,
            )
        )
        session.add_all(
            [
                TicketEvent(
                    ticket_id=ticket_id,
                    device_id=device_id,
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
                    device_id=device_id,
                    agent_seq=None,
                    event_type="chat_message",
                    payload={"sender_role": "support", "visibility": "internal", "text": "Internal support note"},
                    created_at=now,
                ),
                TicketEvent(
                    ticket_id=ticket_id,
                    device_id=device_id,
                    agent_seq=None,
                    event_type="chat_message",
                    payload={"sender_role": "user", "visibility": "public", "text": "Requester public message"},
                    created_at=now,
                ),
            ]
        )
        await session.flush()
        await session.commit()
    return ticket_id, person_id


@pytest.mark.asyncio
async def test_support_and_requester_history_use_role_specific_projection(test_client, test_engine):
    ticket_id, person_id = await _seed_history_ticket(test_engine)

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

    support_person = await test_client.get(
        f"/api/web/support/people/{person_id}/history",
        headers=_headers(TEST_UI_SUPPORT_TOKEN),
    )
    support_person_payload = await support_person.json()
    assert support_person.status == 200, support_person_payload
    assert support_person_payload["data"]["source_states"]["registry"] == {
        "status": "available",
        "source": "local_authoritative",
    }
    assert any(
        event["source"] == "registry" and event["event_type"] == "device_binding"
        for event in support_person_payload["data"]["events"]
    )

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
async def test_requester_history_ignores_user_supplied_history_subject(test_client, test_engine):
    own_ticket_id, _own_person_id = await _seed_history_ticket(
        test_engine,
        login="history-owned@example.test",
    )
    other_ticket_id, other_person_id = await _seed_history_ticket(
        test_engine,
        login="history-other@example.test",
        device_id=str(uuid.uuid4()),
        ticket_code="T-HIST-002",
    )
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        own_ticket = await session.get(Ticket, own_ticket_id)
        other_ticket = await session.get(Ticket, other_ticket_id)
        assert own_ticket is not None and other_ticket is not None
        own_ticket.requester_external_ref = str(_own_person_id)
        own_ticket.requester_snapshot_json = _neutral_requester_snapshot(str(_own_person_id))
        other_ticket.requester_external_ref = str(other_person_id)
        other_ticket.requester_snapshot_json = _neutral_requester_snapshot(str(other_person_id))
        await session.commit()

    response = await test_client.get(
        (
            "/api/web/requester/history"
            f"?person_id={other_person_id}&requester_external_ref={other_person_id}"
        ),
        headers=_headers(f"{TEST_UI_USER_PREFIX}history-owned@example.test"),
    )
    payload = await response.json()

    assert response.status == 200, payload
    ticket_refs = {
        event.get("ticket_ref")
        for event in payload["data"]["events"]
        if event.get("source") == "ticket" and event.get("event_type") == "ticket_created"
    }
    assert own_ticket.ticket_code in ticket_refs
    assert other_ticket.ticket_code not in ticket_refs


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


def _neutral_requester_snapshot(external_ref: str) -> dict[str, object]:
    return {
        "person": {"external_id": external_ref},
        "display_name": "Neutral requester",
    }


@pytest.mark.asyncio
async def test_person_history_matches_only_exact_valid_neutral_ref_or_legacy_person_scope(test_engine):
    """Opaque refs are exact; requester_id is never a person-history alias."""

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    subject_ref = "Requester/Exact-Case"
    now = datetime.now(timezone.utc).replace(microsecond=0)
    async with session_maker() as session:
        session.add_all(
            [
                Ticket(
                    ticket_id=str(uuid.uuid4()),
                    ticket_code="T-HIST-N-EXACT",
                    title="exact neutral",
                    description="exact neutral",
                    status="new",
                    requester_id="unrelated-login",
                    requester_external_ref=subject_ref,
                    requester_snapshot_json=_neutral_requester_snapshot(subject_ref),
                    created_at=now,
                    updated_at=now,
                ),
                Ticket(
                    ticket_id=str(uuid.uuid4()),
                    ticket_code="T-HIST-N-CASE",
                    title="case collision",
                    description="case collision",
                    status="new",
                    requester_id="unrelated-login",
                    requester_external_ref=subject_ref.lower(),
                    requester_snapshot_json=_neutral_requester_snapshot(subject_ref.lower()),
                    created_at=now,
                    updated_at=now,
                ),
                Ticket(
                    ticket_id=str(uuid.uuid4()),
                    ticket_code="T-HIST-N-TRIM",
                    title="trim collision",
                    description="trim collision",
                    status="new",
                    requester_id="unrelated-login",
                    requester_external_ref=f" {subject_ref}",
                    requester_snapshot_json=_neutral_requester_snapshot(f" {subject_ref}"),
                    created_at=now,
                    updated_at=now,
                ),
                Ticket(
                    ticket_id=str(uuid.uuid4()),
                    ticket_code="T-HIST-RID-COLL",
                    title="requester id collision",
                    description="requester id collision",
                    status="new",
                    requester_id=subject_ref,
                    created_at=now,
                    updated_at=now,
                ),
                Ticket(
                    ticket_id=str(uuid.uuid4()),
                    ticket_code="T-HIST-N-BAD",
                    title="malformed neutral",
                    description="malformed neutral",
                    status="new",
                    requester_id="unrelated-login",
                    requester_external_ref=subject_ref,
                    requester_snapshot_json=_neutral_requester_snapshot("different-requester"),
                    requester_person_id=subject_ref,
                    created_at=now,
                    updated_at=now,
                ),
                Ticket(
                    ticket_id=str(uuid.uuid4()),
                    ticket_code="T-HIST-L-PERSON",
                    title="legacy person",
                    description="legacy person",
                    status="new",
                    requester_id="unrelated-login",
                    requester_person_id=subject_ref,
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        await session.commit()

        history = await CustomerHistoryProjectionService(session).history_for_person(
            subject_ref,
            actor_context={"actor_id": "support-test", "actor_role": "support"},
            limit=50,
        )

    ticket_refs = {
        event["ticket_ref"]
        for event in history["events"]
        if event["source"] == "ticket" and event["event_type"] == "ticket_created"
    }
    assert ticket_refs == {"T-HIST-N-EXACT", "T-HIST-L-PERSON"}


@pytest.mark.asyncio
async def test_support_person_history_preserves_percent_encoded_opaque_ref_whitespace(
    test_client,
    test_engine,
):
    raw_ref = " requester ref "
    trimmed_ref = raw_ref.strip()
    now = datetime.now(timezone.utc).replace(microsecond=0)
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add_all(
            [
                Ticket(
                    ticket_id=str(uuid.uuid4()),
                    ticket_code="T-HIST-RAW-REF",
                    title="raw opaque ref",
                    description="raw opaque ref",
                    status="new",
                    requester_id="unrelated-login",
                    requester_external_ref=raw_ref,
                    requester_snapshot_json=_neutral_requester_snapshot(raw_ref),
                    created_at=now,
                    updated_at=now,
                ),
                Ticket(
                    ticket_id=str(uuid.uuid4()),
                    ticket_code="T-HIST-TRIM-REF",
                    title="trimmed opaque ref",
                    description="trimmed opaque ref",
                    status="new",
                    requester_id="unrelated-login",
                    requester_external_ref=trimmed_ref,
                    requester_snapshot_json=_neutral_requester_snapshot(trimmed_ref),
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        await session.commit()

    response = await test_client.get(
        "/api/web/support/people/%20requester%20ref%20/history",
        headers=_headers(TEST_UI_SUPPORT_TOKEN),
    )
    payload = await response.json()

    assert response.status == 200, payload
    ticket_refs = {
        event["ticket_ref"]
        for event in payload["data"]["events"]
        if event["source"] == "ticket" and event["event_type"] == "ticket_created"
    }
    assert ticket_refs == {"T-HIST-RAW-REF"}


@pytest.mark.asyncio
async def test_person_history_uses_creator_and_affected_aliases_only_for_legacy_rows(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    alias_ref = "legacy-history-alias"
    neutral_ref = "neutral-history-ref"
    now = datetime.now(timezone.utc).replace(microsecond=0)
    alias_context = {
        "ticket_context": {
            "created_on_behalf": True,
            "creator": {"person_id": alias_ref, "display_name": "Legacy creator"},
            "affected": {"person_id": alias_ref, "display_name": "Legacy affected"},
        }
    }
    async with session_maker() as session:
        session.add_all(
            [
                Ticket(
                    ticket_id=str(uuid.uuid4()),
                    ticket_code="T-HIST-L-ALIAS",
                    title="legacy aliases",
                    description="legacy aliases",
                    status="new",
                    requester_id="legacy-login",
                    requester_person_id="other-legacy-person",
                    custom_fields=alias_context,
                    created_at=now,
                    updated_at=now,
                ),
                Ticket(
                    ticket_id=str(uuid.uuid4()),
                    ticket_code="T-HIST-N-ALIAS",
                    title="neutral aliases must not match",
                    description="neutral aliases must not match",
                    status="new",
                    requester_id="neutral-login",
                    requester_external_ref=neutral_ref,
                    requester_snapshot_json=_neutral_requester_snapshot(neutral_ref),
                    custom_fields=alias_context,
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        await session.commit()
        history = await CustomerHistoryProjectionService(session).history_for_person(
            alias_ref,
            actor_context={"actor_id": "support-test", "actor_role": "support"},
            limit=50,
        )

    created = [
        event
        for event in history["events"]
        if event["source"] == "ticket" and event["event_type"] == "ticket_created"
    ]
    assert [event["ticket_ref"] for event in created] == ["T-HIST-L-ALIAS"]
    assert created[0]["payload"]["person_history_relationship"] == "creator_and_affected"


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
