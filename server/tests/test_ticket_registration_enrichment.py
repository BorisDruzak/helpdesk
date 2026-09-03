from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Device, DeviceRegistrationClaim, RegistryPerson, Ticket
from registry.registration_service import RegistrationService
from tests.conftest import TEST_AGENT_PREFIX
from tickets.create_flow import create_ticket_with_side_effects
from tickets.ticket_context import TicketContextBuilder


pytestmark = pytest.mark.db_cleanup("tickets")

def _device(device_id: str) -> Device:
    now = datetime.now(timezone.utc)
    return Device(
        device_id=device_id,
        protocol_version="ws_ticket_v3",
        agent_version="3.1.59",
        hostname="ticket-reg",
        os="Windows",
        capabilities={},
        device_metadata={},
        first_seen_at=now,
        last_seen_at=now,
        last_handshake_at=now,
    )


async def _commit_registry_prerequisites(session) -> None:
    """Expose Registry setup to adapter-owned read sessions before ticket create."""

    await session.commit()


@pytest.mark.asyncio
async def test_ticket_with_active_binding_gets_requester_context_and_asset(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_device(device_id))
        service = RegistrationService(session)
        result = await service.submit_agent_profile_claim(
            device_id=device_id,
            requester_id="ticket-active",
            display_name="Ticket Active",
            profile={"full_name": "Ticket Active", "email": "ticket-active@example.test", "user_confirmed": True},
        )
        approved = await service.approve_claim(result["registration"]["claim_id"], reviewed_by="admin")
        await _commit_registry_prerequisites(session)
        created = await create_ticket_with_side_effects(
            session,
            device_id=device_id,
            requester_id="ticket-active",
            title="Need help",
            description="Need help",
            user_display_name="Ticket Active",
        )
        await session.commit()

    async with session_maker() as session:
        ticket = await session.get(Ticket, created["ticket_id"])

    assert ticket.requester_person_id == approved["binding"]["person_id"]
    assert ticket.requester_binding_id == approved["binding"]["binding_id"]
    assert ticket.requester_external_ref == approved["binding"]["person_id"]
    assert ticket.requester_snapshot_json == {
        "person": {"external_id": approved["binding"]["person_id"]},
        "display_name": "Ticket Active",
    }
    assert ticket.requester_registration_status == "admin_confirmed"
    assert ticket.asset_id is None
    assert ticket.requester_account_mode == "agent_legacy_or_device_only"
    assert ticket.custom_fields["requester_account_context"]["account_mode"] == "agent_legacy_or_device_only"
    assert ticket.custom_fields["requester_account_context"]["context_scope"] == "limited"
    assert ticket.custom_fields["requester_account_context"]["profile_completion_evidence"] is False
    assert ticket.custom_fields["ticket_context"]["requester_context"]["account_mode"] == "agent_legacy_or_device_only"
    assert ticket.custom_fields["ticket_context"]["requester_context"]["context_scope"] == "limited"
    assert "profile_completion" not in ticket.custom_fields["ticket_context"]["requester_context"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_display_name",
    ["   ", "X" * 257],
    ids=["blank", "overlong"],
)
async def test_verified_requester_with_invalid_snapshot_does_not_create_legacy_only_ticket(
    test_engine,
    invalid_display_name: str,
):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    title = f"Invalid requester snapshot {len(invalid_display_name)}"

    async with session_maker() as session:
        session.add(_device(device_id))
        service = RegistrationService(session)
        result = await service.submit_agent_profile_claim(
            device_id=device_id,
            requester_id="ticket-invalid-snapshot",
            display_name="Valid Before Approval",
            profile={
                "full_name": "Valid Before Approval",
                "email": "ticket-invalid-snapshot@example.test",
                "user_confirmed": True,
            },
        )
        approved = await service.approve_claim(
            result["registration"]["claim_id"],
            reviewed_by="admin",
        )
        person = await session.get(RegistryPerson, approved["person"]["person_id"])
        assert person is not None
        person.display_name = invalid_display_name
        person.full_name = invalid_display_name
        await session.flush()
        await _commit_registry_prerequisites(session)

        with pytest.raises(ValueError):
            await create_ticket_with_side_effects(
                session,
                device_id=device_id,
                requester_id="ticket-invalid-snapshot",
                title=title,
                description="Must fail instead of writing legacy-only requester scope",
                user_display_name="Payload display must not be used",
            )

        stored = await session.scalar(select(Ticket).where(Ticket.title == title))
        assert stored is None


@pytest.mark.asyncio
async def test_stale_verified_requester_does_not_create_legacy_only_ticket(
    test_engine,
    monkeypatch,
):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    title = "Stale verified requester"

    async with session_maker() as session:
        session.add(_device(device_id))
        service = RegistrationService(session)
        result = await service.submit_agent_profile_claim(
            device_id=device_id,
            requester_id="ticket-stale-verified-person",
            display_name="Stale Verified Person",
            profile={
                "full_name": "Stale Verified Person",
                "email": "ticket-stale-verified-person@example.test",
                "user_confirmed": True,
            },
        )
        await service.approve_claim(
            result["registration"]["claim_id"],
            reviewed_by="admin",
        )
        await _commit_registry_prerequisites(session)

        async def _missing_verified_person(_builder, _person_id):
            return None, None

        monkeypatch.setattr(
            TicketContextBuilder,
            "requester_reference_snapshot",
            _missing_verified_person,
        )

        with pytest.raises(ValueError, match="complete requester reference snapshot"):
            await create_ticket_with_side_effects(
                session,
                device_id=device_id,
                requester_id="ticket-stale-verified-person",
                title=title,
                description="Must fail when the verified person disappears",
                user_display_name="Payload display must not be used",
            )

        stored = await session.scalar(select(Ticket).where(Ticket.title == title))
        assert stored is None


@pytest.mark.asyncio
async def test_ticket_with_active_binding_ignores_conflicting_requester_profile(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_device(device_id))
        service = RegistrationService(session)
        result = await service.submit_agent_profile_claim(
            device_id=device_id,
            requester_id="ticket-active-profile",
            display_name="Ticket Active Profile",
            profile={"full_name": "Ticket Active Profile", "email": "ticket-active-profile@example.test", "user_confirmed": True},
        )
        approved = await service.approve_claim(result["registration"]["claim_id"], reviewed_by="admin")
        await _commit_registry_prerequisites(session)
        created = await create_ticket_with_side_effects(
            session,
            device_id=device_id,
            requester_id="different-requester",
            title="Need help",
            description="Need help",
            user_display_name="Different Requester",
            requester_profile={"full_name": "Different Requester", "email": "different-requester@example.test"},
        )
        await session.commit()

    async with session_maker() as session:
        ticket = await session.get(Ticket, created["ticket_id"])
        claims = (
            await session.execute(select(DeviceRegistrationClaim).where(DeviceRegistrationClaim.device_id == device_id))
        ).scalars().all()

    assert ticket.requester_person_id == approved["binding"]["person_id"]
    assert ticket.requester_binding_id == approved["binding"]["binding_id"]
    assert ticket.requester_external_ref == approved["binding"]["person_id"]
    assert ticket.requester_snapshot_json == {
        "person": {"external_id": approved["binding"]["person_id"]},
        "display_name": "Ticket Active Profile",
    }
    assert ticket.requester_registration_status == "admin_confirmed"
    assert ticket.asset_id is None
    assert len(claims) == 1
    assert claims[0].status == "approved"


@pytest.mark.asyncio
async def test_ticket_with_requester_profile_creates_claim_and_pending_status(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_device(device_id))
        await _commit_registry_prerequisites(session)
        created = await create_ticket_with_side_effects(
            session,
            device_id=device_id,
            requester_id="ticket-pending",
            title="Need help",
            description="Need help",
            user_display_name="Ticket Pending",
            requester_profile={"full_name": "Ticket Pending", "email": "ticket-pending@example.test"},
        )
        await session.commit()

    async with session_maker() as session:
        ticket = await session.get(Ticket, created["ticket_id"])
        claim = (
            await session.execute(select(DeviceRegistrationClaim).where(DeviceRegistrationClaim.device_id == device_id))
        ).scalar_one()

    assert claim.status == "pending_user_confirmation"
    assert ticket.requester_person_id is None
    assert ticket.requester_binding_id is None
    assert ticket.requester_registration_status == "self_reported"
    assert ticket.requester_account_mode == "agent_legacy_or_device_only"
    assert ticket.custom_fields["requester_account_context"]["account_mode"] == "agent_legacy_or_device_only"
    assert ticket.custom_fields["requester_account_context"]["context_scope"] == "limited"
    assert ticket.custom_fields["requester_account_context"]["profile_completion_evidence"] is False
    assert "ticket_context" not in ticket.custom_fields
    assert "pending_claim" not in ticket.custom_fields["requester_registration"]
    assert ticket.custom_fields["requester_registration"]["requires_user_action"] is True


@pytest.mark.asyncio
async def test_ticket_with_conflict_claim_does_not_assign_requester_person(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_device(device_id))
        service = RegistrationService(session)
        first = await service.submit_agent_profile_claim(
            device_id=device_id,
            requester_id="first-ticket",
            display_name="First Ticket",
            profile={"full_name": "First Ticket", "email": "first-ticket@example.test", "user_confirmed": True},
        )
        approved = await service.approve_claim(first["registration"]["claim_id"], reviewed_by="admin")
        conflict = await service.submit_agent_profile_claim(
            device_id=device_id,
            requester_id="second-ticket",
            display_name="Second Ticket",
            profile={"full_name": "Second Ticket", "email": "second-ticket@example.test", "user_confirmed": True},
        )
        await service.revoke_binding(approved["binding"]["binding_id"], revoked_by="admin", reason="test conflict without active")
        await _commit_registry_prerequisites(session)
        created = await create_ticket_with_side_effects(
            session,
            device_id=device_id,
            requester_id="second-ticket",
            title="Need help",
            description="Need help",
            user_display_name="Second Ticket",
        )
        await session.commit()

    async with session_maker() as session:
        ticket = await session.get(Ticket, created["ticket_id"])

    assert ticket.requester_person_id is None
    assert ticket.requester_binding_id is None
    assert ticket.requester_registration_status == "conflict"
    assert ticket.custom_fields["requester_registration"]["status"] == "conflict"
    assert "pending_claim" not in ticket.custom_fields["requester_registration"]
    assert ticket.custom_fields["requester_registration"]["requires_admin_action"] is True
