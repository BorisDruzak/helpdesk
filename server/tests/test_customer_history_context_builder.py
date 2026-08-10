from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import RegistryPerson, Ticket, TicketEvent
from domain_ports import (
    ActorRef,
    DeviceRef,
    RegistryHistoryEventProjection,
    RegistryReadActor,
    RequesterHistoryProjection,
    RequesterRef,
)
from customer_history.context_builder import CustomerHistoryContextBuilder

pytestmark = pytest.mark.db_cleanup("full")


class _ContextRegistryPort:
    def __init__(self, items: tuple[RegistryHistoryEventProjection, ...]) -> None:
        self.items = items

    async def requester_history(
        self,
        person,
        *,
        actor,
        limit: int = 50,
    ) -> RequesterHistoryProjection:
        del actor, limit
        return RequesterHistoryProjection(
            requester=RequesterRef(external_id=person.external_id),
            source="external_authoritative",
            items=self.items,
        )


@pytest.mark.asyncio
async def test_ticket_context_pack_is_bounded_deterministic_and_redacted(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    person_id = str(uuid.uuid4())
    base = datetime.now(timezone.utc).replace(microsecond=0)
    async with session_maker() as session:
        session.add(
            RegistryPerson(
                person_id=person_id,
                display_name="Context Pack Person",
                full_name="Context Pack Person",
                source="manual",
                status="active",
            )
        )
        session.add(
            Ticket(
                ticket_id=ticket_id,
                ticket_code="T-CTX-001",
                device_id="context-device",
                title="Context pack ticket",
                description="Context pack description",
                status="new",
                requester_id="context@example.test",
                requester_person_id=person_id,
                custom_fields={"ticket_context": {"schema": "ticket_context_v1", "policy_refs": {"routing": "raw"}}},
            )
        )
        for index in range(12):
            session.add(
                TicketEvent(
                    ticket_id=ticket_id,
                    device_id="context-device",
                    agent_seq=None,
                    event_type="chat_message" if index % 2 else "status_changed",
                    payload={
                        "visibility": "public",
                        "text": f"History item {index}",
                        "token": f"raw-token-{index}",
                        "trace_id": f"trace-{index}",
                    },
                    created_at=base + timedelta(seconds=index),
                )
            )
        await session.commit()

        first = await CustomerHistoryContextBuilder(session).build_ticket_context_pack(
            ticket_id,
            actor_context={"actor_id": "support-test", "actor_role": "support"},
            mode="llm_preview",
            limit=6,
        )
        second = await CustomerHistoryContextBuilder(session).build_ticket_context_pack(
            ticket_id,
            actor_context={"actor_id": "support-test", "actor_role": "support"},
            mode="llm_preview",
            limit=6,
        )

    assert first == second
    assert first["mode"] == "llm_preview"
    assert first["preview_only"] is True
    assert first["llm_api_called"] is False
    assert first["ticket_ref"] == "T-CTX-001"
    assert len(first["events"]) <= 6
    assert first["events"][0]["event_type"] == "ticket_created"
    assert "raw-token" not in str(first)
    assert "trace-" not in str(first)
    assert first["redaction_report"]["removed_count"] >= 1


@pytest.mark.asyncio
async def test_ticket_context_pack_redacts_legacy_knowledge_identifiers_and_content(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    creator_id = str(uuid.uuid4())
    affected_id = str(uuid.uuid4())
    base = datetime.now(timezone.utc).replace(microsecond=0)
    async with session_maker() as session:
        session.add_all(
            [
                RegistryPerson(
                    person_id=creator_id,
                    display_name="Creator Context Person",
                    full_name="Creator Context Person",
                    source="manual",
                    status="active",
                ),
                RegistryPerson(
                    person_id=affected_id,
                    display_name="Affected Context Person",
                    full_name="Affected Context Person",
                    source="manual",
                    status="active",
                ),
            ]
        )
        session.add(
            Ticket(
                ticket_id=ticket_id,
                ticket_code="T-CTX-KB",
                device_id="affected-context-device",
                title="Context pack on behalf",
                description="Creator should not receive affected-only KB",
                status="new",
                requester_id="creator-context@example.test",
                requester_person_id=creator_id,
                custom_fields={
                    "ticket_context": {
                        "schema": "ticket_context_v1",
                        "created_on_behalf": True,
                        "creator": {"person_id": creator_id, "display_name": "Creator Context Person"},
                        "affected": {"person_id": affected_id, "display_name": "Affected Context Person"},
                        "on_behalf": {"enabled": True, "reason": "Affected employee cannot log in"},
                    },
                    "knowledge_attempts": [
                        {
                            "item_id": "kb-creator-safe",
                            "title": "Creator visible article",
                            "body": "Private article body",
                            "result": "viewed",
                            "surface": "requester_portal",
                            "visibility_scope": "creator_visible",
                            "audience_scope": "creator",
                            "occurred_at": base.isoformat(),
                        }
                    ],
                },
                created_at=base,
                updated_at=base,
            )
        )
        await session.commit()

        context_pack = await CustomerHistoryContextBuilder(session).build_ticket_context_pack(
            ticket_id,
            actor_context={
                "actor_id": "creator-context@example.test",
                "actor_role": "requester",
                "person_id": creator_id,
            },
            mode="llm_preview",
            limit=20,
        )

    serialized = str(context_pack)
    assert "legacy_knowledge_attempts" in serialized
    assert "viewed" in serialized
    assert "Creator visible article" not in serialized
    assert "Private article body" not in serialized
    assert "kb-creator-safe" not in serialized


@pytest.mark.asyncio
async def test_person_history_filters_events_by_since_window(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    person_id = str(uuid.uuid4())
    old_ticket_id = str(uuid.uuid4())
    recent_ticket_id = str(uuid.uuid4())
    base = datetime.now(timezone.utc).replace(microsecond=0)
    async with session_maker() as session:
        session.add(
            RegistryPerson(
                person_id=person_id,
                display_name="Window Person",
                full_name="Window Person",
                source="manual",
                status="active",
            )
        )
        session.add_all(
            [
                Ticket(
                    ticket_id=old_ticket_id,
                    ticket_code="T-CTX-OLD",
                    device_id="window-old-device",
                    title="Old history item",
                    description="Outside the requested history window",
                    status="closed",
                    requester_id="window@example.test",
                    requester_person_id=person_id,
                    created_at=base - timedelta(days=30),
                    updated_at=base - timedelta(days=30),
                ),
                Ticket(
                    ticket_id=recent_ticket_id,
                    ticket_code="T-CTX-RECENT",
                    device_id="window-recent-device",
                    title="Recent history item",
                    description="Inside the requested history window",
                    status="new",
                    requester_id="window@example.test",
                    requester_person_id=person_id,
                    created_at=base,
                    updated_at=base,
                ),
            ]
        )
        await session.commit()

        history = await CustomerHistoryContextBuilder(session).build_person_history(
            person_id,
            actor_context={"actor_id": "support-test", "actor_role": "support"},
            filters={"since": (base - timedelta(days=1)).isoformat(), "limit": 20},
        )

    serialized = str(history)
    assert "T-CTX-RECENT" in serialized
    assert "T-CTX-OLD" not in serialized


@pytest.mark.asyncio
async def test_ticket_context_pack_appends_related_recent_history_after_current_ticket(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    person_id = str(uuid.uuid4())
    current_ticket_id = str(uuid.uuid4())
    related_ticket_id = str(uuid.uuid4())
    base = datetime.now(timezone.utc).replace(microsecond=0)
    async with session_maker() as session:
        session.add(
            RegistryPerson(
                person_id=person_id,
                display_name="Related History Person",
                full_name="Related History Person",
                source="manual",
                status="active",
            )
        )
        session.add_all(
            [
                Ticket(
                    ticket_id=related_ticket_id,
                    ticket_code="T-CTX-RELATED",
                    device_id="related-history-device",
                    title="Earlier related issue",
                    description="Related context should follow the current ticket",
                    status="resolved",
                    requester_id="related@example.test",
                    requester_person_id=person_id,
                    created_at=base - timedelta(days=2),
                    updated_at=base - timedelta(days=2),
                ),
                Ticket(
                    ticket_id=current_ticket_id,
                    ticket_code="T-CTX-CURRENT",
                    device_id="current-history-device",
                    title="Current issue",
                    description="Current ticket remains first",
                    status="new",
                    requester_id="related@example.test",
                    requester_person_id=person_id,
                    created_at=base,
                    updated_at=base,
                ),
            ]
        )
        await session.commit()

        context_pack = await CustomerHistoryContextBuilder(session).build_ticket_context_pack(
            current_ticket_id,
            actor_context={"actor_id": "support-test", "actor_role": "support"},
            mode="llm_preview",
            limit=10,
        )

    assert context_pack["events"][0]["ticket_ref"] == "T-CTX-CURRENT"
    assert any(event.get("ticket_ref") == "T-CTX-RELATED" for event in context_pack["events"][1:])


@pytest.mark.asyncio
async def test_ticket_context_pack_keeps_registry_events_with_colliding_device_ref_prefixes(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    person_id = str(uuid.uuid4())
    occurred_at = datetime.now(timezone.utc).replace(microsecond=0)
    async with session_maker() as session:
        session.add(
            RegistryPerson(
                person_id=person_id,
                display_name="Collision Context Person",
                full_name="Collision Context Person",
                source="manual",
                status="active",
            )
        )
        session.add(
            Ticket(
                ticket_id=ticket_id,
                ticket_code="T-CTX-REG-COLLIDE",
                title="Registry context collision",
                description="Two Registry bindings must remain distinct",
                status="new",
                requester_id=person_id,
                requester_person_id=person_id,
            )
        )
        await session.commit()

        port = _ContextRegistryPort(
            (
                RegistryHistoryEventProjection(
                    event_type="device_binding",
                    occurred_at=occurred_at,
                    device=DeviceRef(external_id="device-prefix-collision-a"),
                    relationship_type="primary_user",
                    status="active",
                    source="external_authoritative",
                ),
                RegistryHistoryEventProjection(
                    event_type="device_binding",
                    occurred_at=occurred_at,
                    device=DeviceRef(external_id="device-prefix-collision-b"),
                    relationship_type="primary_user",
                    status="active",
                    source="external_authoritative",
                ),
            )
        )
        context_pack = await CustomerHistoryContextBuilder(
            session,
            registry_port=port,  # type: ignore[arg-type]
        ).build_ticket_context_pack(
            ticket_id,
            actor_context={"actor_id": "support-test", "actor_role": "support"},
            registry_actor=RegistryReadActor(
                actor=ActorRef(external_id="support-test"),
                role="support",
            ),
            limit=10,
        )

    registry_events = [event for event in context_pack["events"] if event["source"] == "registry"]
    assert len(registry_events) == 2
    assert {event["refs"]["device_ref"] for event in registry_events} == {"device:device-p"}
    assert len({event["refs"]["event_ref"] for event in registry_events}) == 2
    assert "device-prefix-collision-a" not in str(context_pack)
    assert "device-prefix-collision-b" not in str(context_pack)
