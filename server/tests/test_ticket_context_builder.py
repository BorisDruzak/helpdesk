from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Device, RegistryDepartment, RegistryLocation, RegistryPerson, Ticket
from registry.registration_service import RegistrationService
from tickets.create_flow import create_ticket_with_side_effects
from tickets.ticket_context import TicketContextBuilder


def _new_id() -> str:
    return str(uuid.uuid4())


def _device(device_id: str, *, hostname: str, agent_version: str = "3.1.70") -> Device:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    return Device(
        device_id=device_id,
        protocol_version="ws_ticket_v3",
        agent_version=agent_version,
        hostname=hostname,
        os="Windows 11",
        capabilities={"protocol_v3": True},
        device_metadata={"machine_id": device_id, "secret_hint": "must-not-leak"},
        first_seen_at=now,
        last_seen_at=now,
        last_handshake_at=now,
    )


def _person(
    display_name: str,
    *,
    department_id: str | None = None,
    location_id: str | None = None,
) -> RegistryPerson:
    return RegistryPerson(
        person_id=_new_id(),
        display_name=display_name,
        full_name=display_name,
        email=f"{display_name.lower().replace(' ', '.')}@example.test",
        department_id=department_id,
        location_id=location_id,
        source="manual",
        status="active",
    )


def _org_context(session, marker: str) -> tuple[str, str]:
    suffix = uuid.uuid4().hex[:8]
    department_id = _new_id()
    location_id = _new_id()
    session.add_all(
        [
            RegistryDepartment(
                department_id=department_id,
                code=f"ticket-context-{marker}-{suffix}",
                name=f"Ticket context {marker}",
                status="active",
                source="test",
                metadata_json={},
            ),
            RegistryLocation(
                location_id=location_id,
                building=f"Ticket context {marker}",
                floor="1",
                room=suffix,
                display_name=f"Ticket context {marker} / {suffix}",
                status="active",
                source="test",
                metadata_json={},
            ),
        ]
    )
    return department_id, location_id


class _State:
    def __init__(self, online_device_ids: set[str]):
        self._online_device_ids = online_device_ids

    def is_agent_online(self, device_id: str) -> bool:
        return device_id in self._online_device_ids


def _requester_account(person: RegistryPerson) -> dict[str, str]:
    return {
        "account_mode": "browser_no_device",
        "person_id": person.person_id,
        "display_name": person.display_name,
        "email": person.email or "",
        "validation": "web_requester_identity_resolved",
    }


@pytest.mark.asyncio
async def test_ticket_context_builder_resolves_normal_creator_primary_agent(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = _new_id()

    async with session_maker() as session:
        session.add(_device(device_id, hostname="CREATOR-PRIMARY", agent_version="3.1.71"))
        department_id, location_id = _org_context(session, "creator")
        creator = _person("Creator Owner", department_id=department_id, location_id=location_id)
        session.add(creator)
        await session.flush()
        binding = await RegistrationService(session).bind_person_to_device(
            device_id=device_id,
            person_id=creator.person_id,
            relationship_type="primary_user",
            reviewed_by="admin",
            reason="creator primary diagnostic target",
        )

        context = await TicketContextBuilder(session, state=_State({device_id})).build(
            creator_person_id=creator.person_id,
            creator_actor_id="creator-login",
        )
        await session.commit()

    assert context["schema"] == "ticket_context_v1"
    assert context["created_on_behalf"] is False
    assert context["creator"]["person_id"] == creator.person_id
    assert context["creator"]["actor_id"] == "creator-login"
    assert context["affected"]["person_id"] == creator.person_id
    assert context["affected"]["display_name"] == "Creator Owner"
    assert context["affected"]["department_id"] == creator.department_id
    assert context["affected"]["location_id"] == creator.location_id
    assert context["target_device"]["device_id"] == device_id
    assert context["target_device"]["binding_id"] == binding["binding"]["binding_id"]
    assert context["target_device"]["agent_status"] == "online"
    assert context["target_device"]["hostname"] == "CREATOR-PRIMARY"
    assert context["target_device"]["agent_version"] == "3.1.71"
    assert context["diagnostic_target_source"] == "creator_primary_agent"
    assert "capabilities" not in str(context)
    assert "secret_hint" not in str(context)


@pytest.mark.asyncio
async def test_ticket_context_builder_resolves_on_behalf_affected_primary_agent(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    affected_device_id = _new_id()

    async with session_maker() as session:
        session.add(_device(affected_device_id, hostname="AFFECTED-PRIMARY"))
        creator = _person("Support Creator")
        department_id, location_id = _org_context(session, "affected")
        affected = _person("Affected Person", department_id=department_id, location_id=location_id)
        session.add_all([creator, affected])
        await session.flush()
        binding = await RegistrationService(session).bind_person_to_device(
            device_id=affected_device_id,
            person_id=affected.person_id,
            relationship_type="primary_user",
            reviewed_by="admin",
            reason="affected primary diagnostic target",
        )

        context = await TicketContextBuilder(session, state=_State(set())).build(
            creator_person_id=creator.person_id,
            creator_actor_id="support-login",
            affected_person_id=affected.person_id,
            on_behalf_reason="phone call",
        )
        await session.commit()

    assert context["created_on_behalf"] is True
    assert context["creator"]["person_id"] == creator.person_id
    assert context["affected"]["person_id"] == affected.person_id
    assert context["affected"]["department_id"] == affected.department_id
    assert context["affected"]["location_id"] == affected.location_id
    assert context["target_device"]["device_id"] == affected_device_id
    assert context["target_device"]["binding_id"] == binding["binding"]["binding_id"]
    assert context["target_device"]["agent_status"] == "offline"
    assert context["diagnostic_target_source"] == "affected_user_primary_agent"
    assert context["on_behalf_reason"] == "phone call"


@pytest.mark.asyncio
async def test_ticket_context_builder_records_missing_primary_agent(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)

    async with session_maker() as session:
        creator = _person("No Agent Creator")
        session.add(creator)
        await session.flush()

        context = await TicketContextBuilder(session, state=_State(set())).build(
            creator_person_id=creator.person_id,
            creator_actor_id="creator-login",
        )
        await session.commit()

    assert context["created_on_behalf"] is False
    assert context["diagnostic_target_source"] == "no_primary_agent"
    assert context["target_device"] == {
        "device_id": None,
        "binding_id": None,
        "agent_status": "missing",
        "reason_code": "primary_device_missing",
        "candidate_count": 0,
    }


@pytest.mark.asyncio
async def test_create_flow_stores_ticket_context_without_trusting_current_device(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    target_device_id = _new_id()
    current_device_id = _new_id()

    async with session_maker() as session:
        session.add_all(
            [
                _device(target_device_id, hostname="PRIMARY-TARGET"),
                _device(current_device_id, hostname="CURRENT-BROWSER-SCOPE"),
            ]
        )
        creator = _person("Browser Creator")
        session.add(creator)
        await session.flush()
        await RegistrationService(session).bind_person_to_device(
            device_id=target_device_id,
            person_id=creator.person_id,
            relationship_type="primary_user",
            reviewed_by="admin",
            reason="creator primary diagnostic target",
        )

        result = await create_ticket_with_side_effects(
            session,
            device_id=current_device_id,
            requester_id="creator-login",
            title="Need help",
            description="Requester issue",
            user_display_name=creator.display_name,
            requester_account=_requester_account(creator),
            state=_State({target_device_id}),
        )
        ticket = await session.get(Ticket, result["ticket_id"])
        await session.commit()

    assert ticket is not None
    custom_fields = ticket.custom_fields or {}
    assert ticket.device_id == current_device_id
    assert ticket.requester_person_id == creator.person_id
    assert custom_fields["created_on_behalf"] is False
    assert custom_fields["creator_person_id"] == creator.person_id
    assert custom_fields["affected_person_id"] == creator.person_id
    assert custom_fields["target_device_id"] == target_device_id
    assert custom_fields["target_agent_status"] == "online"
    assert custom_fields["diagnostic_target_source"] == "creator_primary_agent"
    assert custom_fields["ticket_context"]["target_device"]["device_id"] == target_device_id
    assert custom_fields["requester_account_context"]["person_id"] == creator.person_id
    assert "secret_hint" not in str(custom_fields["ticket_context"])


@pytest.mark.asyncio
async def test_create_flow_stores_on_behalf_affected_target_context(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    current_device_id = _new_id()
    affected_device_id = _new_id()

    async with session_maker() as session:
        session.add_all(
            [
                _device(current_device_id, hostname="SUPPORT-CURRENT"),
                _device(affected_device_id, hostname="AFFECTED-TARGET"),
            ]
        )
        creator = _person("Helpdesk Creator")
        affected = _person("Remote Affected")
        session.add_all([creator, affected])
        await session.flush()
        await RegistrationService(session).bind_person_to_device(
            device_id=affected_device_id,
            person_id=affected.person_id,
            relationship_type="primary_user",
            reviewed_by="admin",
            reason="affected primary diagnostic target",
        )

        result = await create_ticket_with_side_effects(
            session,
            device_id=current_device_id,
            requester_id="support-login",
            title="On behalf request",
            description="Affected user issue",
            user_display_name=creator.display_name,
            requester_account=_requester_account(creator),
            ticket_context={
                "affected_person_id": affected.person_id,
                "on_behalf_reason": "support phone intake",
                "target_device_id": current_device_id,
            },
            state=_State({affected_device_id}),
        )
        ticket = await session.get(Ticket, result["ticket_id"])
        await session.commit()

    assert ticket is not None
    custom_fields = ticket.custom_fields or {}
    assert ticket.device_id == current_device_id
    assert custom_fields["created_on_behalf"] is True
    assert custom_fields["creator_person_id"] == creator.person_id
    assert custom_fields["affected_person_id"] == affected.person_id
    assert custom_fields["target_device_id"] == affected_device_id
    assert custom_fields["target_agent_status"] == "online"
    assert custom_fields["diagnostic_target_source"] == "affected_user_primary_agent"
    assert custom_fields["on_behalf_reason"] == "support phone intake"
    assert custom_fields["ticket_context"]["target_device"]["device_id"] == affected_device_id
