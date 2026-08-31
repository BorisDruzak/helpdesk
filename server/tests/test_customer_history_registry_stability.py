from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from customer_history.context_builder import CustomerHistoryContextBuilder
from customer_history.sources import RegistryHistorySource
from domain_ports.registry_contracts import (
    ActorRef,
    DeviceRef,
    PersonRef,
    RegistryHistoryEventProjection,
    RegistryReadActor,
    RequesterHistoryProjection,
    RequesterRef,
)


pytestmark = pytest.mark.no_db


class _RequesterHistoryPort:
    def __init__(self, outcome: RequesterHistoryProjection):
        self.outcome = outcome

    async def requester_history(self, *_args, **_kwargs) -> RequesterHistoryProjection:
        return self.outcome


@pytest.mark.asyncio
async def test_registry_history_assigns_stable_redacted_event_refs_after_sorting() -> None:
    person = PersonRef(external_id="person-private")
    actor = RegistryReadActor(actor=ActorRef(external_id="support-private"), role="support")
    binding_a = RegistryHistoryEventProjection(
        event_type="device_binding",
        occurred_at=datetime(2026, 8, 10, 9, 0, tzinfo=timezone.utc),
        device=DeviceRef(external_id="device-aaaaaaaa-private"),
        relationship_type="primary_user",
        status="active",
        source="local_authoritative",
    )
    binding_b = RegistryHistoryEventProjection(
        event_type="device_binding",
        occurred_at=datetime(2026, 8, 10, 9, 0, tzinfo=timezone.utc),
        device=DeviceRef(external_id="device-bbbbbbbb-private"),
        relationship_type="shared_user",
        status="active",
        source="external_authoritative",
    )

    async def project(items: tuple[RegistryHistoryEventProjection, ...]):
        return await RegistryHistorySource(
            registry_port=_RequesterHistoryPort(
                RequesterHistoryProjection(
                    requester=RequesterRef(external_id=person.external_id),
                    items=items,
                    source="external_authoritative",
                )
            )
        ).events_for_person(person, actor=actor, limit=20)

    first = await project((binding_b, binding_a))
    second = await project((binding_a, binding_b))

    first_signature = {(event.event_id, tuple(sorted(event.safe_refs.items()))) for event in first.events}
    second_signature = {(event.event_id, tuple(sorted(event.safe_refs.items()))) for event in second.events}

    assert first_signature == second_signature
    assert len(first_signature) == 2
    assert all(event_id.startswith("registry:") for event_id, _refs in first_signature)
    assert "person-private" not in str(first_signature)
    assert "device-aaaaaaaa-private" not in str(first_signature)
    assert all(dict(refs).get("event_ref") == event_id for event_id, refs in first_signature)


@pytest.mark.asyncio
async def test_ticket_context_pack_keeps_distinct_registry_devices_and_dedupes_true_duplicates(monkeypatch) -> None:
    current_event = {
        "ticket_ref": "T-CTX-CURRENT",
        "source": "ticket",
        "event_type": "ticket_created",
        "occurred_at": "2026-08-10T09:00:00+00:00",
        "summary": "Current ticket",
    }
    registry_event_a = {
        "ticket_ref": "T-CTX-OLDER",
        "source": "registry",
        "event_type": "device_binding",
        "occurred_at": "2026-08-10T08:00:00+00:00",
        "summary": "primary_user:active",
        "refs": {"device_ref": "device:aaaaaaaa", "event_ref": "registry:device_binding:001"},
    }
    registry_event_b = {
        **registry_event_a,
        "refs": {"device_ref": "device:bbbbbbbb", "event_ref": "registry:device_binding:002"},
    }

    class _ProjectionService:
        def __init__(self, _session, *, registry_port=None):
            pass

        async def history_for_ticket(self, *_args, **_kwargs):
            return {
                "ticket_ref": "T-CTX-CURRENT",
                "events": [current_event],
                "sources": ["ticket"],
                "redaction_report": {"removed_count": 0},
            }

        async def _ticket(self, _ticket_id):
            return SimpleNamespace(requester_person_id="person-1", requester_id=None, custom_fields={})

        async def history_for_person(self, *_args, **_kwargs):
            return {
                "events": [registry_event_a, registry_event_b, dict(registry_event_a)],
                "sources": ["registry"],
                "redaction_report": {"removed_count": 0},
            }

    monkeypatch.setattr("customer_history.context_builder.CustomerHistoryProjectionService", _ProjectionService)

    result = await CustomerHistoryContextBuilder(object()).build_ticket_context_pack(
        "ticket-1",
        actor_context={"actor_id": "support-test", "actor_role": "support"},
        limit=10,
    )

    registry_events = [event for event in result["events"] if event.get("source") == "registry"]
    assert {event["refs"]["device_ref"] for event in registry_events} == {
        "device:aaaaaaaa",
        "device:bbbbbbbb",
    }
    assert len(registry_events) == 2
