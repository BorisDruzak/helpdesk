from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from customer_history.sources import RegistryHistorySource
from customer_history.context_builder import CustomerHistoryContextBuilder


pytestmark = pytest.mark.no_db


class _Rows:
    def __init__(self, rows):
        self.rows = rows

    def scalars(self):
        return self

    def all(self):
        return list(self.rows)


class _RegistryHistorySession:
    def __init__(self, bindings, sessions):
        self._results = [_Rows(bindings), _Rows(sessions)]

    async def execute(self, _statement):
        return self._results.pop(0)


def _binding(*, binding_id: str, device_id: str, relationship_type: str, source: str):
    return SimpleNamespace(
        binding_id=binding_id,
        device_id=device_id,
        relationship_type=relationship_type,
        status="active",
        source=source,
        confirmed_at=None,
        created_at=datetime(2026, 8, 10, 9, 0, tzinfo=timezone.utc),
    )


def _session(*, session_id: str, device_id: str):
    return SimpleNamespace(
        session_id=session_id,
        device_id=device_id,
        account_mode="confirmed_binding",
        verification_status="verified",
        warning_code=None,
        created_at=datetime(2026, 8, 10, 9, 0, tzinfo=timezone.utc),
    )


@pytest.mark.asyncio
async def test_registry_history_assigns_stable_redacted_event_refs_after_sorting() -> None:
    binding_a = _binding(
        binding_id="binding-private-a",
        device_id="device-aaaaaaaa-private",
        relationship_type="primary_user",
        source="manual",
    )
    binding_b = _binding(
        binding_id="binding-private-b",
        device_id="device-bbbbbbbb-private",
        relationship_type="shared_user",
        source="registration_claim",
    )
    account_session = _session(
        session_id="session-private-c",
        device_id="device-cccccccc-private",
    )

    first = await RegistryHistorySource(
        _RegistryHistorySession([binding_b, binding_a], [account_session])
    ).events_for_person("person-private")
    second = await RegistryHistorySource(
        _RegistryHistorySession([binding_a, binding_b], [account_session])
    ).events_for_person("person-private")

    first_signature = [(event.event_id, dict(event.safe_refs)) for event in first]
    second_signature = [(event.event_id, dict(event.safe_refs)) for event in second]

    assert first_signature == second_signature
    assert all(event_id.startswith("registry:") for event_id, _refs in first_signature)
    assert "binding-private" not in str(first_signature)
    assert "session-private" not in str(first_signature)
    assert all(refs.get("event_ref") == event_id for event_id, refs in first_signature)


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
        def __init__(self, _session):
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
