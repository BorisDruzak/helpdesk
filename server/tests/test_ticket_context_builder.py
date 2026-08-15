from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Device, RegistryDepartment, RegistryLocation, RegistryPerson, Ticket, TicketEvent
from registry.registration_service import RegistrationService
from tickets.create_flow import create_ticket_with_side_effects
from tickets.diagnostic_target import resolve_ticket_diagnostic_target
from tickets.ticket_context import (
    TicketContextBuilder,
    project_requester_ticket_context,
    project_support_ticket_context,
    validate_ticket_context_v1,
)
import domain_ports.registry_contracts as registry_contracts
from domain_ports import PersonRef


pytestmark = pytest.mark.db_cleanup("tickets")

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


class _NoRegistryOrmSession:
    async def get(self, *_args: object, **_kwargs: object) -> object:
        raise AssertionError("ticket participant reads must use RegistryPort")


class _TicketParticipantPort:
    def __init__(self, *, mismatch: bool = False) -> None:
        self._mismatch = mismatch

    async def ticket_participant(self, person: PersonRef):
        external_id = "registry-ref-other-person" if self._mismatch else person.external_id
        return registry_contracts.TicketParticipantProjection(
            person=PersonRef(external_id=external_id),
            display_name="Port Display",
            full_name="Port Full Name",
            email="port@example.test",
            department={"external_id": "registry-ref-department"},
            location={"external_id": "registry-ref-location"},
            source="local_authoritative",
        )


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_ticket_context_builder_reads_participants_only_through_registry_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def unresolved(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {
            "resolved": False,
            "reason_code": "primary_device_missing",
            "candidate_count": 0,
        }

    monkeypatch.setattr(
        "tickets.ticket_context.PrimaryAgentResolver.resolve_for_person",
        unresolved,
    )
    context = await TicketContextBuilder(
        _NoRegistryOrmSession(),
        registry_port=_TicketParticipantPort(),
    ).build(
        creator_person_id="registry-ref-person",
        creator_actor_id="support-login",
    )

    assert context["creator"] == {
        "person_id": "registry-ref-person",
        "display_name": "Port Display",
        "full_name": "Port Full Name",
        "email": "port@example.test",
        "department_id": "registry-ref-department",
        "location_id": "registry-ref-location",
        "actor_id": "support-login",
    }
    assert context["affected"]["person_id"] == "registry-ref-person"


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_ticket_context_fails_closed_when_participant_ref_does_not_match() -> None:
    with pytest.raises(ValueError, match="ticket participant Registry projection is invalid"):
        await TicketContextBuilder(
            _NoRegistryOrmSession(),
            registry_port=_TicketParticipantPort(mismatch=True),
        ).build(creator_person_id="registry-ref-person")


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
        await session.commit()

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
async def test_ticket_context_builder_emits_phase_b_canonical_sections(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = _new_id()

    async with session_maker() as session:
        session.add(_device(device_id, hostname="CANONICAL-TARGET"))
        creator = _person("Canonical Creator")
        session.add(creator)
        await session.flush()
        await RegistrationService(session).bind_person_to_device(
            device_id=device_id,
            person_id=creator.person_id,
            relationship_type="primary_user",
            reviewed_by="admin",
            reason="canonical context target",
        )
        await session.commit()

        requester_context = _requester_account(creator)
        context = await TicketContextBuilder(session, state=_State({device_id})).build(
            creator_person_id=creator.person_id,
            creator_actor_id="creator-login",
            requester_context=requester_context,
            form={"key": "hardware_help", "title": "Hardware help"},
            policy_refs={"routing_policy": "default_triage", "diagnostic_policy": "hardware_diag"},
        )
        await session.commit()

    assert validate_ticket_context_v1(context) == []
    assert context["schema"] == "ticket_context_v1"
    assert context["created_at"]
    assert context["on_behalf"] == {"enabled": False, "reason": None}
    assert context["requester_context"] == requester_context
    assert context["diagnostic_target"]["device_id"] == device_id
    assert context["diagnostic_target"]["source"] == "creator_primary_agent"
    assert context["form"] == {"key": "hardware_help", "title": "Hardware help"}
    assert context["policy_refs"] == {"routing_policy": "default_triage", "diagnostic_policy": "hardware_diag"}
    assert context["redaction"]["requester_hidden_fields"]

    requester_projection = project_requester_ticket_context(context, actor_context={"actor_id": "creator-login"})
    assert requester_projection["summary"]["affected"] == "Canonical Creator"
    assert requester_projection["diagnostic_target"]["label"] == "CANONICAL-TARGET"
    assert "creator" not in requester_projection
    assert "affected" not in requester_projection
    assert "policy_refs" not in requester_projection
    assert "diagnostic_target_source" not in str(requester_projection)
    assert "person_id" not in str(requester_projection)
    assert device_id not in str(requester_projection)

    support_projection = project_support_ticket_context(context, actor_context={"actor_id": "support-test"})
    assert support_projection["creator"]["person_id"] == creator.person_id
    assert support_projection["affected"]["person_id"] == creator.person_id
    assert support_projection["diagnostic_target"]["device_id"] == device_id
    assert support_projection["diagnostic_target"]["source"] == "creator_primary_agent"


@pytest.mark.no_db
def test_validate_ticket_context_v1_reports_missing_required_sections():
    errors = validate_ticket_context_v1(
        {
            "schema": "ticket_context_v1",
            "creator": {"person_id": "creator"},
        }
    )

    assert "created_at is required" in errors
    assert "affected.person_id is required" in errors
    assert "diagnostic_target section is required" in errors
    assert "requester_context section is required" in errors


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
        await session.commit()

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
        await session.commit()

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
        await session.commit()

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
        await session.commit()

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


@pytest.mark.no_db
def test_resolve_ticket_diagnostic_target_prefers_context_target_over_stale_flat_alias():
    ticket = SimpleNamespace(
        device_id="legacy-device",
        custom_fields={
            "target_device_id": "stale-flat-device",
            "diagnostic_target_source": "creator_primary_agent",
            "ticket_context": {
                "schema": "ticket_context_v1",
                "created_on_behalf": True,
                "creator": {"person_id": "creator-person"},
                "affected": {"person_id": "affected-person", "display_name": "Affected Person"},
                "target_device": {"device_id": "canonical-context-device", "agent_status": "online"},
                "diagnostic_target": {
                    "device_id": "canonical-context-device",
                    "source": "affected_user_primary_agent",
                    "agent_status": "online",
                },
                "diagnostic_target_source": "affected_user_primary_agent",
            },
        },
    )

    target = resolve_ticket_diagnostic_target(ticket)

    assert target.dispatch_device_id == "canonical-context-device"
    assert target.source == "affected_user_primary_agent"
    assert target.created_on_behalf is True
    assert target.affected_person_id == "affected-person"


@pytest.mark.asyncio
async def test_create_flow_writes_ticket_context_resolved_event(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    target_device_id = _new_id()

    async with session_maker() as session:
        session.add(_device(target_device_id, hostname="EVENT-TARGET"))
        creator = _person("Event Creator")
        session.add(creator)
        await session.flush()
        await RegistrationService(session).bind_person_to_device(
            device_id=target_device_id,
            person_id=creator.person_id,
            relationship_type="primary_user",
            reviewed_by="admin",
            reason="event target",
        )
        await session.commit()

        result = await create_ticket_with_side_effects(
            session,
            device_id=_new_id(),
            requester_id="creator-login",
            title="Need event",
            description="Ticket context event should be written",
            user_display_name=creator.display_name,
            requester_account=_requester_account(creator),
            state=_State({target_device_id}),
        )
        events = (
            await session.execute(
                TicketEvent.__table__.select().where(
                    TicketEvent.ticket_id == result["ticket_id"],
                    TicketEvent.event_type == "ticket_context_resolved",
                )
            )
        ).all()
        await session.commit()

    assert len(events) == 1
    payload = events[0]._mapping["payload"]
    assert payload["schema"] == "ticket_context_v1"
    assert payload["created_on_behalf"] is False
    assert payload["diagnostic_target_source"] == "creator_primary_agent"
    assert payload["target_available"] is True
    assert payload["evidence_codes"] == []
