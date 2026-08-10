from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from app.db.models import RegistryPerson, Ticket, UserConsentRequest
from app.repos.ticket_events_repo import TicketEventsRepo
from app.repos.user_consent_repo import UserConsentRepo
from domain_ports.registry import (
    BindingRef,
    DeviceRef,
    PersonRef,
    RequesterRef,
    RequesterSnapshot,
)


pytestmark = pytest.mark.no_db


class RecordingSession:
    def __init__(self) -> None:
        self.rows: list[object] = []

    def add(self, row: object) -> None:
        self.rows.append(row)

    async def flush(self) -> None:
        return None

    async def refresh(self, row: object) -> None:
        return None


def test_snapshot_contains_only_safe_opaque_data() -> None:
    snapshot = RequesterSnapshot(
        person=PersonRef(external_id="registry-ref-opaque-1"),
        display_name="Иван",
    )

    assert snapshot.model_dump(mode="json") == {
        "person": {"external_id": "registry-ref-opaque-1"},
        "display_name": "Иван",
    }
    assert "email" not in snapshot.model_dump(mode="json")


def test_refs_are_immutable_and_opaque() -> None:
    refs = (
        PersonRef(external_id="person:opaque/1"),
        DeviceRef(external_id="device:opaque/1"),
        BindingRef(external_id="binding:opaque/1"),
        RequesterRef(external_id="requester:opaque/1"),
    )

    for ref in refs:
        with pytest.raises((FrozenInstanceError, TypeError, ValueError)):
            ref.external_id = "changed"  # type: ignore[misc]

    assert RequesterRef(external_id="  case-sensitive opaque ref  ").external_id == "  case-sensitive opaque ref  "


def test_snapshot_rejects_local_profile_and_secret_fields() -> None:
    with pytest.raises(ValueError):
        RequesterSnapshot(
            person=PersonRef(external_id="registry-ref-opaque-1"),
            display_name="Иван",
            email="ivan@example.test",  # type: ignore[call-arg]
        )

    with pytest.raises(ValueError):
        RequesterSnapshot(
            person=PersonRef(external_id="registry-ref-opaque-1"),
            display_name="Иван",
            profile={"department": "Support"},  # type: ignore[call-arg]
        )

    with pytest.raises(ValueError):
        PersonRef(external_id="registry-ref-opaque-1", access_token="secret")  # type: ignore[call-arg]


def test_models_define_nullable_neutral_requester_columns_without_registry_foreign_keys() -> None:
    for model in (Ticket, UserConsentRequest):
        external_ref = model.__table__.c.requester_external_ref
        snapshot = model.__table__.c.requester_snapshot_json

        assert external_ref.nullable is True
        assert snapshot.nullable is True
        assert not external_ref.foreign_keys
        assert not snapshot.foreign_keys


@pytest.mark.asyncio
async def test_ticket_repo_persists_only_validated_requester_values() -> None:
    session = RecordingSession()
    requester_ref = RequesterRef(external_id="registry-ref-opaque-1")
    snapshot = RequesterSnapshot(
        person=PersonRef(external_id="registry-ref-opaque-1"),
        display_name="Иван",
    )

    ticket = await TicketEventsRepo(session).create_ticket(  # type: ignore[arg-type]
        ticket_id="ticket-requester-ref",
        device_id=None,
        title="Requester reference",
        description="Neutral data only",
        requester_id="requester",
        requester_ref=requester_ref,
        requester_snapshot=snapshot,
    )

    assert session.rows == [ticket]
    assert ticket.requester_external_ref == "registry-ref-opaque-1"
    assert ticket.requester_snapshot_json == {
        "person": {"external_id": "registry-ref-opaque-1"},
        "display_name": "Иван",
    }


@pytest.mark.asyncio
async def test_consent_repo_rejects_mutable_requester_payloads() -> None:
    session = RecordingSession()

    with pytest.raises(TypeError, match="RequesterRef"):
        await UserConsentRepo(session).create(  # type: ignore[arg-type]
            subject_type="operation",
            subject_id="operation-requester-ref",
            title="Consent",
            requester_ref={"external_id": "registry-ref-opaque-1"},
        )

    local_person = RegistryPerson(
        person_id="legacy-local-person-id",
        display_name="Иван",
        email="ivan@example.test",
        source="test",
    )
    with pytest.raises(TypeError, match="RequesterRef"):
        await UserConsentRepo(session).create(  # type: ignore[arg-type]
            subject_type="operation",
            subject_id="operation-local-orm-payload",
            title="Consent",
            requester_ref=local_person,
        )

    assert session.rows == []
