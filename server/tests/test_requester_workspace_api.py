from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import (
    Artifact,
    Device,
    DeviceUserBinding,
    KnowledgeFeedbackEvent,
    RegistryAdminEvent,
    RegistryAdminPolicy,
    RegistryAsset,
    RegistryDepartment,
    RegistryLocation,
    RegistryPerson,
    RegistryPersonIdentity,
    RequestTemplate,
    Ticket,
    TicketEvent,
    TicketFeedback,
    TicketQueue,
    TicketReopenEvent,
)
from app.repos.service_catalog_repo import ServiceCatalogRepo
from app.repos.ticket_form_packs_repo import TicketFormPacksRepo
from customer_history.projection_service import CustomerHistoryProjectionService
from registry.registration_service import RegistrationService
from tests.conftest import TEST_AGENT_PREFIX, TEST_UI_ADMIN_TOKEN, TEST_UI_USER_PREFIX
from tickets.create_flow import build_default_priority_payload, create_ticket_with_side_effects


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _admin_headers() -> dict[str, str]:
    return _headers(TEST_UI_ADMIN_TOKEN)


def _device(device_id: str, hostname: str = "requester-device") -> Device:
    now = datetime.now(timezone.utc)
    return Device(
        device_id=device_id,
        protocol_version="ws_ticket_v3",
        agent_version="3.1.61",
        hostname=hostname,
        os="Windows",
        capabilities={},
        device_metadata={},
        first_seen_at=now,
        last_seen_at=now,
        last_handshake_at=now,
    )


async def _seed_profile_context(session, person: RegistryPerson, *, marker: str) -> None:
    suffix = uuid.uuid4().hex[:8]
    department_id = str(uuid.uuid4())
    location_id = str(uuid.uuid4())
    session.add(
        RegistryDepartment(
            department_id=department_id,
            code=f"dept-{marker[:16]}-{suffix}",
            name=f"Department {marker}",
            status="active",
            source="test",
            metadata_json={},
        )
    )
    session.add(
        RegistryLocation(
            location_id=location_id,
            building=f"Building {marker[:8]} {suffix}",
            floor="1",
            room="101",
            display_name=f"Building {marker[:8]} {suffix} / 101",
            status="active",
            source="test",
            metadata_json={},
        )
    )
    person.department_id = department_id
    person.location_id = location_id
    person.phone = person.phone or "1001"


async def _approved_binding(session, *, device_id: str, login: str):
    service = RegistrationService(session)
    claim = await service.submit_agent_profile_claim(
        device_id=device_id,
        requester_id=login,
        display_name=f"Requester {login}",
        profile={"full_name": f"Requester {login}", "email": login, "login": login, "user_confirmed": True},
    )
    approved = await service.approve_claim(claim["registration"]["claim_id"], reviewed_by="admin")
    person = await session.get(RegistryPerson, approved["person"]["person_id"])
    assert person is not None
    await _seed_profile_context(session, person, marker=login.replace("@", "-")[:32])
    return approved


async def _person_for_login(session, *, login: str) -> RegistryPerson:
    person = RegistryPerson(
        person_id=str(uuid.uuid4()),
        display_name=f"Requester {login}",
        full_name=f"Requester {login}",
        email=login,
        source="manual",
        status="active",
    )
    await _seed_profile_context(session, person, marker=login.replace("@", "-")[:32])
    session.add(person)
    session.add(
        RegistryPersonIdentity(
            person_id=person.person_id,
            provider="ui_login",
            identifier=login,
            normalized_identifier=login,
            verified=True,
            source="test",
        )
    )
    return person


async def _publish_on_behalf_form(
    session,
    *,
    template_code: str,
    version: str,
    allowed_scope: str = "same_department_or_privileged",
    reason_required: bool = True,
) -> None:
    forms_repo = TicketFormPacksRepo(session)
    await forms_repo.upsert_pack(
        pack_key="request_forms",
        version=version,
        schema_json={
            "pack_key": "request_forms",
            "version": version,
            "forms": [
                {
                    "key": template_code,
                    "request_template_key": template_code,
                    "title": "On behalf incident",
                    "request_kind": "incident",
                    "ticket_type": "incident",
                    "on_behalf_policy": {
                        "allowed": True,
                        "reason_required": reason_required,
                        "affected_person_required": True,
                        "allowed_scope": allowed_scope,
                        "diagnostic_target": "affected_person_primary_agent",
                        "knowledge_visibility": "creator_only",
                        "support_visibility": "creator_and_affected",
                        "no_primary_agent_behavior": "allow_ticket_no_diagnostics",
                    },
                    "fields": [
                        {"key": "summary", "label": "Summary", "type": "text", "required": False},
                    ],
                }
            ],
        },
        created_by="test",
    )
    await forms_repo.set_preferred(pack_key="request_forms", version=version, updated_by="test")


async def _publish_availability_forms(
    session,
    *,
    emergency_key: str,
    normal_key: str,
    version: str,
    routed_queue_id: int | None = None,
) -> None:
    routing_policy = (
        {
            "default_queue_id": routed_queue_id,
        }
        if routed_queue_id is not None
        else {}
    )
    forms_repo = TicketFormPacksRepo(session)
    await forms_repo.upsert_pack(
        pack_key="request_forms",
        version=version,
        schema_json={
            "pack_key": "request_forms",
            "version": version,
            "forms": [
                {
                    "key": emergency_key,
                    "request_template_key": emergency_key,
                    "title": "Emergency access",
                    "request_kind": "incident",
                    "ticket_type": "incident",
                    "availability_policy": {
                        "available_without_completed_profile": True,
                        "available_without_agent_binding": True,
                        "requires_manual_triage": True,
                        "contact_required": True,
                    },
                    "routing_policy": routing_policy,
                    "playbook_triggers": [
                        {
                            "event": "ticket_created",
                            "playbook_key": f"emergency_diag_{emergency_key}",
                            "module_kind": "diagnostic",
                            "enabled": True,
                        }
                    ],
                    "fields": [
                        {"key": "contact_phone", "label": "Contact phone", "type": "phone", "required": True},
                        {"key": "summary", "label": "Summary", "type": "text", "required": False},
                    ],
                },
                {
                    "key": normal_key,
                    "request_template_key": normal_key,
                    "title": "Normal request",
                    "request_kind": "request",
                    "ticket_type": "request",
                    "fields": [
                        {"key": "summary", "label": "Summary", "type": "text", "required": False},
                    ],
                },
            ],
        },
        created_by="test",
    )
    await forms_repo.set_preferred(pack_key="request_forms", version=version, updated_by="test")


@pytest.mark.asyncio
async def test_requester_profile_returns_safe_identities_and_devices(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    login = "requester-profile-owner@example.test"
    async with session_maker() as session:
        session.add(_device(device_id, "profile-owned-device"))
        approved = await _approved_binding(session, device_id=device_id, login=login)
        person = await session.get(RegistryPerson, approved["person"]["person_id"])
        assert person is not None
        person.phone = "+7 000 111-22-33"
        session.add(
            RegistryPersonIdentity(
                person_id=person.person_id,
                provider="employee_id",
                identifier="EMP-42",
                normalized_identifier="emp-42",
                verified=True,
                source="hr",
                metadata_json={"raw_token": "must-not-leak-profile"},
            )
        )
        await session.commit()

    response = await test_client.get(
        "/api/web/requester/profile",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}"),
    )
    payload = await response.json()

    assert response.status == 200, payload
    data = payload["data"]
    assert data["profile"]["person_id"] == approved["person"]["person_id"]
    assert data["profile"]["email"] == login
    assert data["profile"]["phone"] == "+7 000 111-22-33"
    assert data["profile_policy"]["editable"] is True
    assert data["profile_policy"]["change_request_required"] is False
    assert data["devices"][0]["device_id"] == device_id
    identities = {(item["provider"], item["identifier"]) for item in data["identities"]}
    assert ("ui_login", login) in identities
    assert ("employee_id", "EMP-42") in identities
    assert all("normalized_identifier" not in item for item in data["identities"])
    assert "metadata_json" not in str(payload)
    assert "must-not-leak-profile" not in str(payload)

    anonymous_profile = await test_client.get(
        "/api/web/requester/profile",
        headers=_headers(f"{TEST_UI_USER_PREFIX}requester-profile-missing@example.test"),
    )
    anonymous_payload = await anonymous_profile.json()
    assert anonymous_profile.status == 200, anonymous_payload
    assert anonymous_payload["data"]["profile"] is None
    assert anonymous_payload["data"]["identities"] == []
    assert anonymous_payload["data"]["devices"] == []

    agent_denied = await test_client.get(
        "/api/web/requester/profile",
        headers=_headers(f"{TEST_AGENT_PREFIX}{device_id}"),
    )
    assert agent_denied.status == 403


@pytest.mark.asyncio
async def test_requester_bootstrap_reports_profile_completion_gate_for_new_user(test_client):
    response = await test_client.get(
        "/api/web/requester/bootstrap",
        headers=_headers(f"{TEST_UI_USER_PREFIX}requester-profile-new@example.test"),
    )
    payload = await response.json()

    assert response.status == 200, payload
    completion = payload["data"]["profile_completion"]
    assert payload["data"]["profile"] is None
    assert completion["complete"] is False
    assert completion["status"] == "required"
    assert completion["setup_path"] == "/app/requester/profile/setup"
    assert {item["key"] for item in completion["missing_fields"]} == {
        "full_name",
        "department_id",
        "location_id",
        "phone",
    }
    assert completion["blocks"]["ticket_create"] is True
    assert completion["blocks"]["ticket_preview"] is True
    assert completion["blocks"]["device_binding_confirmation"] is False
    assert payload["data"]["feature_flags"]["requester_ticket_create"] is False


@pytest.mark.asyncio
async def test_requester_can_create_own_profile_with_registry_pickers(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    department_id = str(uuid.uuid4())
    location_id = str(uuid.uuid4())
    login = "requester-profile-setup@example.test"
    async with session_maker() as session:
        session.add(
            RegistryDepartment(
                department_id=department_id,
                code="it",
                name="ИТ",
                status="active",
                source="test",
                metadata_json={},
            )
        )
        session.add(
            RegistryLocation(
                location_id=location_id,
                building="Офис 7",
                floor="7",
                room="701",
                display_name="Офис 7 / 701",
                status="active",
                source="test",
                metadata_json={},
            )
        )
        await session.commit()

    response = await test_client.put(
        "/api/web/requester/profile",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}"),
        json={
            "full_name": "Иван Петров",
            "department_id": department_id,
            "location_id": location_id,
            "phone": "1234",
            "position": "Инженер",
            "workplace_label": "7 этаж / 701",
            "preferred_contact_method": "phone",
        },
    )
    payload = await response.json()

    assert response.status == 200, payload
    assert payload["data"]["profile"]["full_name"] == "Иван Петров"
    assert payload["data"]["profile"]["department_id"] == department_id
    assert payload["data"]["profile"]["location_id"] == location_id
    assert payload["data"]["profile"]["position"] == "Инженер"
    assert payload["data"]["profile_completion"]["complete"] is True
    assert payload["data"]["profile_policy"]["editable"] is True

    async with session_maker() as session:
        identity = await session.scalar(
            select(RegistryPersonIdentity).where(
                RegistryPersonIdentity.provider == "ui_login",
                RegistryPersonIdentity.normalized_identifier == login,
            )
        )
        assert identity is not None
        person = await session.get(RegistryPerson, identity.person_id)
        assert person is not None
        assert person.full_name == "Иван Петров"
        assert person.department_id == department_id
        assert person.location_id == location_id
        assert person.metadata_json["profile_updated_from"] == "requester_web"


@pytest.mark.asyncio
async def test_admin_profile_schema_enforces_system_fields_and_audits_update(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)

    initial = await test_client.get("/api/web/admin/registry/profile-schema", headers=_admin_headers())
    initial_payload = await initial.json()
    assert initial.status == 200, initial_payload
    default_fields = {field["key"]: field for field in initial_payload["data"]["schema"]["fields"]}
    assert default_fields["full_name"]["system"] is True
    assert default_fields["full_name"]["can_delete"] is False
    assert default_fields["department_id"]["storage_target"] == "registry_people.department_id"

    invalid = await test_client.put(
        "/api/web/admin/registry/profile-schema",
        headers=_admin_headers(),
        json={"field_overrides": {"full_name": {"visible": False}}},
    )
    invalid_payload = await invalid.json()
    assert invalid.status == 400, invalid_payload
    assert invalid_payload["error_code"] == "VALIDATION_ERROR"
    assert "full_name" in invalid_payload["details"]

    response = await test_client.put(
        "/api/web/admin/registry/profile-schema",
        headers=_admin_headers(),
        json={
            "field_overrides": {
                "position": {
                    "visible": True,
                    "required": True,
                    "help_text": "Укажите рабочую должность для маршрутизации заявок.",
                }
            },
            "custom_fields": [
                {
                    "key": "cost_center",
                    "label": "Центр затрат",
                    "type": "text",
                    "visible": True,
                    "required": True,
                    "help_text": "Код подразделения для отчетности.",
                    "validation": {"max_length": 32},
                    "storage_target": "registry_people.metadata_json.profile_custom_fields.cost_center",
                }
            ],
            "reason": "R6 profile schema test",
        },
    )
    payload = await response.json()
    assert response.status == 200, payload
    schema = payload["data"]["schema"]
    fields = {field["key"]: field for field in schema["fields"]}
    assert fields["position"]["required"] is True
    assert fields["position"]["target_kind"] == "registry_person_metadata"
    assert fields["cost_center"]["custom"] is True
    assert fields["cost_center"]["audit_behavior"] == "profile_custom_field_change"
    assert fields["cost_center"]["storage_target"] == "registry_people.metadata_json.profile_custom_fields.cost_center"

    async with session_maker() as session:
        policy = await session.get(RegistryAdminPolicy, "requester_profile_schema")
        assert policy is not None
        assert policy.config_json["custom_fields"][0]["key"] == "cost_center"
        event_count = await session.scalar(
            select(func.count())
            .select_from(RegistryAdminEvent)
            .where(RegistryAdminEvent.event_type == "profile_schema_updated")
        )
        assert event_count == 1


@pytest.mark.asyncio
async def test_admin_profile_schema_rejects_uncontrolled_custom_fields(test_client):
    response = await test_client.put(
        "/api/web/admin/registry/profile-schema",
        headers=_admin_headers(),
        json={
            "custom_fields": [
                {
                    "key": "full_name",
                    "label": "Duplicate system field",
                    "type": "text",
                    "storage_target": "registry_people.metadata_json.profile_custom_fields.full_name",
                },
                {
                    "key": "unsafe_notes",
                    "label": "Unsafe target",
                    "type": "text",
                    "storage_target": "registry_people.raw_sql.unsafe_notes",
                },
            ],
        },
    )
    payload = await response.json()

    assert response.status == 400, payload
    assert payload["error_code"] == "VALIDATION_ERROR"
    assert "custom_fields.0.key" in payload["details"]
    assert "custom_fields.1.storage_target" in payload["details"]


@pytest.mark.asyncio
async def test_requester_profile_schema_required_custom_fields_are_enforced(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    department_id = str(uuid.uuid4())
    location_id = str(uuid.uuid4())
    login = "requester-profile-schema-required@example.test"
    async with session_maker() as session:
        session.add(
            RegistryDepartment(
                department_id=department_id,
                code="schema-dept",
                name="Profile Schema Department",
                status="active",
                source="test",
                metadata_json={},
            )
        )
        session.add(
            RegistryLocation(
                location_id=location_id,
                building="Profile Schema Office",
                floor="2",
                room="201",
                display_name="Profile Schema Office / 201",
                status="active",
                source="test",
                metadata_json={},
            )
        )
        await session.commit()

    configured = await test_client.put(
        "/api/web/admin/registry/profile-schema",
        headers=_admin_headers(),
        json={
            "custom_fields": [
                {
                    "key": "cost_center",
                    "label": "Центр затрат",
                    "type": "text",
                    "visible": True,
                    "required": True,
                    "storage_target": "registry_people.metadata_json.profile_custom_fields.cost_center",
                }
            ],
            "reason": "R6 required custom field test",
        },
    )
    assert configured.status == 200, await configured.text()

    missing = await test_client.put(
        "/api/web/requester/profile",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}"),
        json={
            "full_name": "Requester With Required Custom Field",
            "department_id": department_id,
            "location_id": location_id,
            "phone": "1001",
            "custom_fields": {},
        },
    )
    missing_payload = await missing.json()
    assert missing.status == 400, missing_payload
    assert missing_payload["details"]["custom_fields.cost_center"] == "Заполните поле: Центр затрат."

    profile = await test_client.get(
        "/api/web/requester/profile",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}"),
    )
    profile_payload = await profile.json()
    assert profile.status == 200, profile_payload
    assert any(
        item["key"] == "cost_center"
        for item in profile_payload["data"]["profile_completion"]["missing_fields"]
    )
    schema_fields = {field["key"]: field for field in profile_payload["data"]["profile_schema"]["fields"]}
    assert schema_fields["cost_center"]["required"] is True
    assert schema_fields["cost_center"]["custom"] is True

    saved = await test_client.put(
        "/api/web/requester/profile",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}"),
        json={
            "full_name": "Requester With Required Custom Field",
            "department_id": department_id,
            "location_id": location_id,
            "phone": "1001",
            "custom_fields": {"cost_center": "CC-42"},
        },
    )
    saved_payload = await saved.json()
    assert saved.status == 200, saved_payload
    assert saved_payload["data"]["profile"]["custom_fields"]["cost_center"] == "CC-42"
    assert saved_payload["data"]["profile_completion"]["complete"] is True

    async with session_maker() as session:
        person = await session.scalar(
            select(RegistryPerson)
            .join(RegistryPersonIdentity, RegistryPersonIdentity.person_id == RegistryPerson.person_id)
            .where(RegistryPersonIdentity.provider == "ui_login")
            .where(RegistryPersonIdentity.normalized_identifier == login)
        )
        assert person is not None
        assert person.metadata_json["profile_custom_fields"]["cost_center"] == "CC-42"


@pytest.mark.asyncio
async def test_requester_profile_update_rejects_other_person_and_invalid_registry_values(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    login = "requester-profile-owner-guard@example.test"
    other_login = "requester-profile-other@example.test"
    async with session_maker() as session:
        owner = await _person_for_login(session, login=login)
        other = await _person_for_login(session, login=other_login)
        await session.commit()

    other_response = await test_client.put(
        "/api/web/requester/profile",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}"),
        json={
            "person_id": other.person_id,
            "full_name": "Чужой профиль",
            "department_id": "missing-dept",
            "location_id": "missing-loc",
            "phone": "1234",
        },
    )
    other_payload = await other_response.json()
    assert other_response.status == 403, other_payload
    assert other_payload["error_code"] == "REQUESTER_PROFILE_FORBIDDEN"

    invalid_response = await test_client.put(
        "/api/web/requester/profile",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}"),
        json={
            "person_id": owner.person_id,
            "full_name": "Владелец профиля",
            "department_id": "missing-dept",
            "location_id": "missing-loc",
            "phone": "1234",
        },
    )
    invalid_payload = await invalid_response.json()
    assert invalid_response.status == 400, invalid_payload
    assert invalid_payload["error_code"] == "VALIDATION_ERROR"
    assert invalid_payload["details"]["department_id"] == "Выберите подразделение из справочника."


@pytest.mark.asyncio
async def test_requester_ticket_create_is_blocked_until_profile_complete(test_client):
    response = await test_client.post(
        "/api/web/requester/tickets",
        headers=_headers(f"{TEST_UI_USER_PREFIX}requester-profile-blocked@example.test"),
        json={"title": "Blocked", "description": "Cannot create yet"},
    )
    payload = await response.json()

    assert response.status == 403, payload
    assert payload["error_code"] == "REQUESTER_PROFILE_INCOMPLETE"
    assert payload["details"]["setup_path"] == "/app/requester/profile/setup"


@pytest.mark.asyncio
async def test_incomplete_profile_can_create_only_allowed_emergency_form(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    suffix = uuid.uuid4().hex[:8]
    emergency_key = f"emergency_login_{suffix}"
    normal_key = f"normal_request_{suffix}"
    login = f"requester-emergency-incomplete-{suffix}@example.test"
    async with session_maker() as session:
        triage_queue = TicketQueue(code="servicedesk_l1", name="ServiceDesk L1", is_triage=True, is_active=True)
        routed_queue = TicketQueue(code=f"non_triage_{suffix}", name="Non triage", is_triage=False, is_active=True)
        session.add_all([triage_queue, routed_queue])
        await session.flush()
        await _publish_availability_forms(
            session,
            emergency_key=emergency_key,
            normal_key=normal_key,
            version=f"availability-{suffix}",
            routed_queue_id=routed_queue.id,
        )
        await session.commit()

    missing_contact = await test_client.post(
        "/api/web/requester/tickets",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}"),
        json={
            "title": "Cannot login",
            "description": "Need urgent access help",
            "form_key": emergency_key,
            "request_template_key": emergency_key,
            "form_payload": {"summary": "No contact yet"},
        },
    )
    missing_contact_payload = await missing_contact.json()
    assert missing_contact.status == 400, missing_contact_payload
    assert missing_contact_payload["error_code"] == "REQUESTER_CONTACT_REQUIRED"

    normal = await test_client.post(
        "/api/web/requester/tickets",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}"),
        json={
            "title": "Normal request",
            "description": "Should still require profile",
            "form_key": normal_key,
            "request_template_key": normal_key,
            "form_payload": {"summary": "Normal"},
        },
    )
    normal_payload = await normal.json()
    assert normal.status == 403, normal_payload
    assert normal_payload["error_code"] == "REQUESTER_PROFILE_INCOMPLETE"

    created = await test_client.post(
        "/api/web/requester/tickets",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}"),
        json={
            "title": "Cannot login",
            "description": "Need urgent access help",
            "form_key": emergency_key,
            "request_template_key": emergency_key,
            "form_payload": {"contact_phone": "+7 000 123-45-67", "summary": "Cannot sign in"},
        },
    )
    created_payload = await created.json()
    assert created.status == 200, created_payload

    async with session_maker() as session:
        ticket = await session.get(Ticket, created_payload["data"]["ticket_id"])
        triage_queue = (await session.execute(select(TicketQueue).where(TicketQueue.code == "servicedesk_l1"))).scalar_one()
        events = (
            await session.execute(
                select(TicketEvent).where(
                    TicketEvent.ticket_id == created_payload["data"]["ticket_id"],
                    TicketEvent.event_type == "diagnostic_autorun_skipped",
                )
            )
        ).scalars().all()

    assert ticket is not None
    assert ticket.queue_id == triage_queue.id
    assert ticket.requester_registration_status == "no_device"
    custom_fields = ticket.custom_fields or {}
    assert custom_fields["requires_manual_triage"] is True
    assert custom_fields["manual_triage_reason"] == "request_form_availability_policy"
    assert custom_fields["request_form_availability"]["available_without_completed_profile"] is True
    assert custom_fields["request_form_availability"]["available_without_agent_binding"] is True
    assert custom_fields["request_form_availability"]["contact_required"] is True
    assert custom_fields["diagnostic_target_source"] == "no_primary_agent"
    assert custom_fields["target_agent_status"] == "missing"
    assert custom_fields["diagnostics"]["autorun_suppressed"] is True
    assert custom_fields["diagnostics"]["last_autorun_skip_reason"] == "manual_triage_required"
    assert events
    assert events[0].payload["reason"] == "target_device_missing"


@pytest.mark.asyncio
async def test_no_agent_user_cannot_create_normal_form_without_agent_binding(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    suffix = uuid.uuid4().hex[:8]
    emergency_key = f"emergency_no_agent_{suffix}"
    normal_key = f"normal_no_agent_{suffix}"
    login = f"requester-no-agent-{suffix}@example.test"
    async with session_maker() as session:
        session.add(TicketQueue(code="servicedesk_l1", name="ServiceDesk L1", is_triage=True, is_active=True))
        await _publish_availability_forms(
            session,
            emergency_key=emergency_key,
            normal_key=normal_key,
            version=f"availability-no-agent-{suffix}",
        )
        await _person_for_login(session, login=login)
        await session.commit()

    normal = await test_client.post(
        "/api/web/requester/tickets",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}"),
        json={
            "title": "Normal request",
            "description": "Should require an agent binding",
            "form_key": normal_key,
            "request_template_key": normal_key,
            "form_payload": {"summary": "Normal"},
        },
    )
    normal_payload = await normal.json()
    assert normal.status == 403, normal_payload
    assert normal_payload["error_code"] == "REQUESTER_AGENT_REQUIRED"

    emergency = await test_client.post(
        "/api/web/requester/tickets",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}"),
        json={
            "title": "No agent emergency",
            "description": "PC will not start",
            "form_key": emergency_key,
            "request_template_key": emergency_key,
            "form_payload": {"contact_phone": "+7 000 777-77-77", "summary": "PC will not start"},
        },
    )
    emergency_payload = await emergency.json()
    assert emergency.status == 200, emergency_payload


@pytest.mark.asyncio
async def test_profile_completion_required_flag_can_disable_no_device_create_gate(test_client, monkeypatch):
    import requester.identity_service as identity_service_module

    config_proxy = getattr(identity_service_module, "config_module", SimpleNamespace())
    monkeypatch.setattr(config_proxy, "PROFILE_COMPLETION_REQUIRED", False, raising=False)
    monkeypatch.setattr(identity_service_module, "config_module", config_proxy, raising=False)

    login = "requester-profile-rollout-override@example.test"
    headers = _headers(f"{TEST_UI_USER_PREFIX}{login}")

    bootstrap_response = await test_client.get("/api/web/requester/bootstrap", headers=headers)
    bootstrap_payload = await bootstrap_response.json()
    assert bootstrap_response.status == 200, bootstrap_payload
    completion = bootstrap_payload["data"]["profile_completion"]
    assert completion["complete"] is False
    assert completion["required"] is False
    assert completion["status"] == "optional"
    assert completion["missing_fields"]
    assert completion["blocks"]["ticket_create"] is False
    assert bootstrap_payload["data"]["feature_flags"]["requester_no_device_create"] is True

    preview_response = await test_client.post(
        "/api/web/requester/tickets/preview",
        headers=headers,
        json={"title": "Preview without profile", "description": "Rollout override preview"},
    )
    preview_payload = await preview_response.json()
    assert preview_response.status == 200, preview_payload

    create_response = await test_client.post(
        "/api/web/requester/tickets",
        headers=headers,
        json={"title": "Override ticket", "description": "Rollout override ticket"},
    )
    create_payload = await create_response.json()
    assert create_response.status == 200, create_payload
    assert create_payload["data"]["ticket_id"]


@pytest.mark.asyncio
async def test_existing_pending_agent_claim_is_visible_to_requester_and_admin(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    login = "requester-legacy-pending-claim@example.test"

    async with session_maker() as session:
        session.add(_device(device_id, "legacy-pending-device"))
        claim = await RegistrationService(session).submit_agent_profile_claim(
            device_id=device_id,
            requester_id=login,
            display_name="Legacy Pending User",
            profile={"full_name": "Legacy Pending User", "email": login, "login": login, "user_confirmed": True},
        )
        claim_id = claim["registration"]["claim_id"]
        await session.commit()

    requester_response = await test_client.get(
        "/api/web/requester/bootstrap",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}"),
    )
    requester_payload = await requester_response.json()
    assert requester_response.status == 200, requester_payload
    requester_claims = requester_payload["data"]["pending_registration_claims"]
    assert any(item["claim_id"] == claim_id and item["device_id"] == device_id for item in requester_claims)

    admin_response = await test_client.get("/api/web/admin/registry", headers=_admin_headers())
    admin_payload = await admin_response.json()
    assert admin_response.status == 200, admin_payload
    admin_claims = admin_payload["data"]["registration_claims"]
    assert any(item["claim_id"] == claim_id and item["device_id"] == device_id for item in admin_claims)


@pytest.mark.asyncio
async def test_requester_workspace_bootstrap_lists_owned_device_and_ticket(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    login = "requester-owner@example.test"
    async with session_maker() as session:
        session.add(_device(device_id))
        approved = await _approved_binding(session, device_id=device_id, login=login)
        session_payload = await create_ticket_with_side_effects(
            session,
            device_id=device_id,
            requester_id=login,
            title="Existing requester ticket",
            description="Visible through requester workspace",
            user_display_name="Requester Owner",
            requester_profile={"full_name": "Requester Owner", "email": login},
            normalized_priority=build_default_priority_payload({}),
            requester_account={
                "account_mode": "confirmed_binding",
                "person_id": approved["person"]["person_id"],
                "binding_id": approved["binding"]["binding_id"],
            },
            include_public_access=True,
        )
        await session.commit()

    response = await test_client.get(
        "/api/web/requester/bootstrap",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}"),
    )
    payload = await response.json()

    assert response.status == 200, payload
    assert payload["data"]["profile"]["person_id"] == approved["person"]["person_id"]
    assert payload["data"]["devices"][0]["device_id"] == device_id
    assert payload["data"]["open_ticket_count"] >= 1

    tickets = await test_client.get(
        "/api/web/requester/tickets",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}"),
    )
    tickets_payload = await tickets.json()
    assert tickets.status == 200, tickets_payload
    assert session_payload["ticket_id"] in {item["ticket_id"] for item in tickets_payload["data"]["tickets"]}


@pytest.mark.asyncio
async def test_requester_shared_device_tickets_stay_scoped_to_person_and_binding(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    primary_login = "requester-shared-primary@example.test"
    shared_login = "requester-shared-secondary@example.test"
    async with session_maker() as session:
        session.add(_device(device_id, "shared-privacy-device"))
        primary = await _approved_binding(session, device_id=device_id, login=primary_login)
        shared_person = await _person_for_login(session, login=shared_login)
        await session.flush()
        shared_binding = DeviceUserBinding(
            binding_id=str(uuid.uuid4()),
            device_id=device_id,
            person_id=shared_person.person_id,
            relationship_type="shared_user",
            status="active",
            source="test",
            confirmed_at=datetime.now(timezone.utc),
        )
        session.add(shared_binding)
        primary_ticket = await create_ticket_with_side_effects(
            session,
            device_id=device_id,
            requester_id=primary_login,
            title="Primary shared device ticket",
            description="Visible only to the primary requester",
            user_display_name="Requester Shared Primary",
            requester_profile={"full_name": "Requester Shared Primary", "email": primary_login},
            normalized_priority=build_default_priority_payload({}),
            requester_account={
                "account_mode": "confirmed_binding",
                "person_id": primary["person"]["person_id"],
                "binding_id": primary["binding"]["binding_id"],
                "validation": "web_requester_identity_resolved",
            },
            include_public_access=True,
        )
        shared_ticket = await create_ticket_with_side_effects(
            session,
            device_id=device_id,
            requester_id=shared_login,
            title="Secondary shared device ticket",
            description="Visible only to the shared requester",
            user_display_name="Requester Shared Secondary",
            requester_profile={"full_name": "Requester Shared Secondary", "email": shared_login},
            normalized_priority=build_default_priority_payload({}),
            requester_account={
                "account_mode": "confirmed_binding",
                "person_id": shared_person.person_id,
                "binding_id": shared_binding.binding_id,
                "validation": "web_requester_identity_resolved",
            },
            include_public_access=True,
        )
        await session.commit()

    primary_headers = _headers(f"{TEST_UI_USER_PREFIX}{primary_login}")
    shared_headers = _headers(f"{TEST_UI_USER_PREFIX}{shared_login}")
    primary_ticket_id = primary_ticket["ticket_id"]
    shared_ticket_id = shared_ticket["ticket_id"]

    primary_list = await test_client.get("/api/web/requester/tickets", headers=primary_headers)
    primary_payload = await primary_list.json()
    assert primary_list.status == 200, primary_payload
    primary_ids = {item["ticket_id"] for item in primary_payload["data"]["tickets"]}
    assert primary_ticket_id in primary_ids
    assert shared_ticket_id not in primary_ids

    shared_list = await test_client.get("/api/web/requester/tickets", headers=shared_headers)
    shared_payload = await shared_list.json()
    assert shared_list.status == 200, shared_payload
    shared_ids = {item["ticket_id"] for item in shared_payload["data"]["tickets"]}
    assert shared_ticket_id in shared_ids
    assert primary_ticket_id not in shared_ids

    shared_bootstrap = await test_client.get("/api/web/requester/bootstrap", headers=shared_headers)
    shared_bootstrap_payload = await shared_bootstrap.json()
    assert shared_bootstrap.status == 200, shared_bootstrap_payload
    assert shared_bootstrap_payload["data"]["devices"][0]["device_id"] == device_id
    assert shared_bootstrap_payload["data"]["active_bindings"][0]["relationship_type"] == "shared_user"
    shared_bootstrap_ticket_ids = {
        item["ticket_id"] for item in shared_bootstrap_payload["data"]["recent_tickets"]
    }
    assert shared_ticket_id in shared_bootstrap_ticket_ids
    assert primary_ticket_id not in shared_bootstrap_ticket_ids

    shared_device = await test_client.get(
        f"/api/web/requester/devices/{device_id}",
        headers=shared_headers,
    )
    shared_device_payload = await shared_device.json()
    assert shared_device.status == 200, shared_device_payload
    assert shared_device_payload["data"]["device"]["relationship_type"] == "shared_user"
    assert shared_device_payload["data"]["device"]["open_ticket_count"] == 1
    shared_recent_ids = {item["ticket_id"] for item in shared_device_payload["data"]["recent_tickets"]}
    assert shared_ticket_id in shared_recent_ids
    assert primary_ticket_id not in shared_recent_ids

    primary_detail = await test_client.get(
        f"/api/web/requester/tickets/{shared_ticket_id}",
        headers=primary_headers,
    )
    primary_detail_payload = await primary_detail.json()
    assert primary_detail.status == 404, primary_detail_payload
    assert primary_detail_payload["error_code"] == "NOT_FOUND"

    shared_detail = await test_client.get(
        f"/api/web/requester/tickets/{primary_ticket_id}",
        headers=shared_headers,
    )
    shared_detail_payload = await shared_detail.json()
    assert shared_detail.status == 404, shared_detail_payload
    assert shared_detail_payload["error_code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_requester_can_create_ticket_for_owned_device_and_not_foreign_device(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    owned_device_id = str(uuid.uuid4())
    foreign_device_id = str(uuid.uuid4())
    login = "requester-create@example.test"
    async with session_maker() as session:
        session.add_all([_device(owned_device_id, "owned-device"), _device(foreign_device_id, "foreign-device")])
        approved = await _approved_binding(session, device_id=owned_device_id, login=login)
        await session.commit()

    body = {
        "device_id": owned_device_id,
        "title": "Requester workspace live ticket",
        "description": "Created from authenticated requester workspace",
        "user_display_name": "Requester Create",
    }
    created = await test_client.post(
        "/api/web/requester/tickets",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}"),
        json=body,
    )
    created_payload = await created.json()
    assert created.status == 200, created_payload
    assert created_payload["data"]["ticket"]["ticket_id"]
    async with session_maker() as session:
        ticket = await session.get(Ticket, created_payload["data"]["ticket"]["ticket_id"])
        assert ticket is not None
        assert ticket.device_id == owned_device_id
        assert ticket.requester_person_id == approved["person"]["person_id"]
        assert ticket.requester_binding_id == approved["binding"]["binding_id"]
        event_rows = (
            await session.execute(
                select(TicketEvent).where(
                    TicketEvent.ticket_id == ticket.ticket_id,
                    TicketEvent.event_type.in_(
                        [
                            "customer_history_ticket_created",
                            "requester_ticket_create_audit",
                        ]
                    ),
                )
            )
        ).scalars().all()
        events_by_type = {row.event_type: row for row in event_rows}
        assert set(events_by_type) == {
            "customer_history_ticket_created",
            "requester_ticket_create_audit",
        }
        history_payload = events_by_type["customer_history_ticket_created"].payload
        assert history_payload["source"] == "requester_ticket_create"
        assert history_payload["history_event_type"] == "ticket_created"
        assert history_payload["requester_account_mode"] == "confirmed_binding"
        assert history_payload["has_ticket_context"] is True
        assert history_payload["created_on_behalf"] is False
        assert history_payload["has_request_form_snapshot"] is False
        assert history_payload["has_policy_snapshot"] is False

        audit_payload = events_by_type["requester_ticket_create_audit"].payload
        assert audit_payload["source"] == "requester_ticket_create"
        assert audit_payload["visibility"] == "internal"
        assert audit_payload["requester_account_mode"] == "confirmed_binding"
        assert audit_payload["request_context"] == "authenticated_requester_workspace"
        assert audit_payload["has_ticket_context"] is True
        assert audit_payload["has_request_form_snapshot"] is False
        assert audit_payload["has_policy_snapshot"] is False
        assert login not in str(history_payload)
        assert owned_device_id not in str(history_payload)
        assert body["title"] not in str(history_payload)
        assert body["description"] not in str(history_payload)
        assert login not in str(audit_payload)
        assert owned_device_id not in str(audit_payload)
        assert body["title"] not in str(audit_payload)
        assert body["description"] not in str(audit_payload)

        support_history = await CustomerHistoryProjectionService(session).history_for_ticket(
            ticket.ticket_id,
            role="support",
            limit=20,
        )
        requester_history = await CustomerHistoryProjectionService(session).history_for_ticket(
            ticket.ticket_id,
            role="requester",
            limit=20,
        )
        assert any(
            event["event_type"] == "customer_history_ticket_created"
            for event in support_history["events"]
        )
        assert any(
            event["event_type"] == "customer_history_ticket_created"
            for event in requester_history["events"]
        )
        assert any(
            event["event_type"] == "requester_ticket_create_audit"
            for event in support_history["events"]
        )
        assert not any(
            event["event_type"] == "requester_ticket_create_audit"
            for event in requester_history["events"]
        )

    denied = await test_client.post(
        "/api/web/requester/tickets",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}"),
        json={**body, "device_id": foreign_device_id},
    )
    denied_payload = await denied.json()
    assert denied.status == 403
    assert denied_payload["error_code"] == "REQUESTER_DEVICE_FORBIDDEN"

    agent_denied = await test_client.get(
        "/api/web/requester/bootstrap",
        headers=_headers(f"{TEST_AGENT_PREFIX}{owned_device_id}"),
    )
    assert agent_denied.status == 403


@pytest.mark.asyncio
async def test_requester_device_detail_is_owned_only_and_safe(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    owned_device_id = str(uuid.uuid4())
    foreign_device_id = str(uuid.uuid4())
    owner_login = "requester-device-detail-owner@example.test"
    foreign_login = "requester-device-detail-foreign@example.test"
    async with session_maker() as session:
        session.add_all([
            _device(owned_device_id, "owned-detail-device"),
            _device(foreign_device_id, "foreign-detail-device"),
        ])
        session.add(
            RegistryAsset(
                asset_id=str(uuid.uuid4()),
                asset_type="pc",
                name="Owned detail asset",
                hostname="owned-detail-asset",
                device_id=owned_device_id,
                source="test",
                status="active",
                discovery_payload={"raw_token": "must-not-leak", "os": "Windows 11"},
            )
        )
        approved = await _approved_binding(session, device_id=owned_device_id, login=owner_login)
        await _approved_binding(session, device_id=foreign_device_id, login=foreign_login)
        created = await create_ticket_with_side_effects(
            session,
            device_id=owned_device_id,
            requester_id=owner_login,
            title="Owned device detail ticket",
            description="Visible from the requester device detail",
            user_display_name="Requester Device Detail",
            requester_profile={"full_name": "Requester Device Detail", "email": owner_login},
            normalized_priority=build_default_priority_payload({}),
            requester_account={
                "account_mode": "confirmed_binding",
                "person_id": approved["person"]["person_id"],
                "binding_id": approved["binding"]["binding_id"],
            },
            include_public_access=True,
        )
        await session.commit()

    detail = await test_client.get(
        f"/api/web/requester/devices/{owned_device_id}",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{owner_login}"),
    )
    payload = await detail.json()
    assert detail.status == 200, payload
    device = payload["data"]["device"]
    assert device["device_id"] == owned_device_id
    assert device["binding_id"] == approved["binding"]["binding_id"]
    assert device["relationship_type"] == "primary_user"
    assert device["binding_status"] == "active"
    assert device["hostname"] == "owned-detail-device"
    assert device["asset_name"] == "Owned detail asset"
    assert device["open_ticket_count"] == 1
    assert device["available_actions"]["create_ticket"] is True
    assert created["ticket_id"] in {item["ticket_id"] for item in payload["data"]["recent_tickets"]}
    assert "must-not-leak" not in str(payload)
    assert "raw_token" not in str(payload)

    denied = await test_client.get(
        f"/api/web/requester/devices/{owned_device_id}",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{foreign_login}"),
    )
    denied_payload = await denied.json()
    assert denied.status == 404, denied_payload
    assert denied_payload["error_code"] == "NOT_FOUND"

    agent_denied = await test_client.get(
        f"/api/web/requester/devices/{owned_device_id}",
        headers=_headers(f"{TEST_AGENT_PREFIX}{owned_device_id}"),
    )
    assert agent_denied.status == 403


@pytest.mark.asyncio
async def test_requester_can_create_no_device_ticket_and_preview_without_device(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    foreign_device_id = str(uuid.uuid4())
    login = "requester-no-device@example.test"
    async with session_maker() as session:
        session.add(_device(foreign_device_id, "foreign-device"))
        person = await _person_for_login(session, login=login)
        await session.commit()

    bootstrap = await test_client.get(
        "/api/web/requester/bootstrap",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}"),
    )
    bootstrap_payload = await bootstrap.json()
    assert bootstrap.status == 200, bootstrap_payload
    assert bootstrap_payload["data"]["profile"]["person_id"] == person.person_id
    assert bootstrap_payload["data"]["devices"] == []
    assert bootstrap_payload["data"]["feature_flags"]["requester_no_device_create"] is True
    assert bootstrap_payload["data"]["policies"]["device_selection_required"] is False

    preview = await test_client.post(
        "/api/web/requester/tickets/preview",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}"),
        json={"description": "Need help without registered device"},
    )
    preview_payload = await preview.json()
    assert preview.status == 200, preview_payload
    assert preview_payload["data"]["ok"] is True
    assert preview_payload["data"]["would_create_ticket"] is False

    created = await test_client.post(
        "/api/web/requester/tickets",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}"),
        json={
            "title": "No device requester ticket",
            "description": "Need help without registered device",
            "user_display_name": "Requester No Device",
        },
    )
    created_payload = await created.json()
    assert created.status == 200, created_payload
    ticket_id = created_payload["data"]["ticket_id"]

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)

    assert ticket is not None
    assert ticket.device_id
    assert ticket.device_id != foreign_device_id
    assert ticket.requester_id == login
    assert ticket.requester_person_id == person.person_id
    assert ticket.requester_binding_id is None
    assert ticket.requester_registration_status == "no_device"
    assert ticket.requester_account_mode == "browser_no_device"
    custom_fields = ticket.custom_fields or {}
    assert custom_fields["request_context"] == "no_device"
    assert custom_fields["requester_account_context"]["account_mode"] == "browser_no_device"
    assert custom_fields["requester_account_context"]["validation"] == "web_requester_identity_resolved"
    assert custom_fields["requester_registration"]["status"] == "no_device"
    assert custom_fields["requester_department_id"] == person.department_id
    assert custom_fields["requester_location_id"] == person.location_id
    assert custom_fields["requester_account_mode"] == "browser_no_device"
    assert custom_fields["requester_context_snapshot"]["profile"]["person_id"] == person.person_id
    assert custom_fields["requester_context_snapshot"]["profile"]["department_id"] == person.department_id
    assert custom_fields["requester_context_snapshot"]["form_prefill"]["department_id"] == person.department_id
    assert custom_fields["requester_context_snapshot"]["account"]["account_mode"] == "browser_no_device"

    listed = await test_client.get(
        "/api/web/requester/tickets",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}"),
    )
    listed_payload = await listed.json()
    assert listed.status == 200, listed_payload
    assert ticket_id in {item["ticket_id"] for item in listed_payload["data"]["tickets"]}

    denied = await test_client.post(
        "/api/web/requester/tickets",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}"),
        json={
            "device_id": foreign_device_id,
            "title": "Foreign requester ticket",
            "description": "Should still be rejected",
        },
    )
    denied_payload = await denied.json()
    assert denied.status == 403, denied_payload
    assert denied_payload["error_code"] == "REQUESTER_DEVICE_FORBIDDEN"


@pytest.mark.asyncio
async def test_requester_create_ticket_accepts_catalog_form_payload(test_client, test_engine):
    suffix = uuid.uuid4().hex[:8]
    service_code = f"requester_workspace_{suffix}"
    template_code = f"requester_laptop_{suffix}"
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    login = "requester-catalog-create@example.test"
    async with session_maker() as session:
        queue = TicketQueue(code=f"requester_queue_{suffix}", name="Requester queue", is_active=True)
        department_queue = TicketQueue(code=f"requester_dept_queue_{suffix}", name="Requester department queue", is_active=True)
        session.add_all([_device(device_id, "catalog-owned-device"), queue, department_queue])
        await session.flush()
        forms_repo = TicketFormPacksRepo(session)
        await forms_repo.upsert_pack(
            pack_key="request_forms",
            version=f"test-{suffix}",
            schema_json={
                "pack_key": "request_forms",
                "version": f"test-{suffix}",
                "forms": [
                    {
                        "key": template_code,
                        "request_template_key": template_code,
                        "title": "Laptop incident",
                        "request_kind": "incident",
                        "ticket_type": "incident",
                        "routing_policy": {
                            "rules": [
                                {
                                    "when": {
                                        "field": "custom_fields.requester_device_id",
                                        "op": "eq",
                                        "value": device_id,
                                    },
                                    "then": {"queue_id": department_queue.id},
                                }
                            ],
                            "fallback": {"queue_id": queue.id},
                        },
                        "fields": [
                            {"key": "summary", "label": "Summary", "type": "text", "required": True},
                        ],
                    }
                ],
            },
            created_by="test",
        )
        await forms_repo.set_preferred(pack_key="request_forms", version=f"test-{suffix}", updated_by="test")
        approved = await _approved_binding(session, device_id=device_id, login=login)
        person = await session.get(RegistryPerson, approved["person"]["person_id"])
        assert person is not None
        session.add(
            RequestTemplate(
                template_code=template_code,
                version="1",
                public_title="Laptop incident",
                ticket_type="incident",
                config_json={
                    "routing_policy": {
                        "rules": [
                            {
                                "when": {
                                    "field": "custom_fields.requester_department_id",
                                    "op": "eq",
                                    "value": person.department_id,
                                },
                                "then": {"queue_id": department_queue.id},
                            }
                        ],
                        "fallback": {"queue_id": queue.id},
                    },
                    "no_sla": True,
                },
                is_active=True,
                published_at=datetime.now(timezone.utc),
            )
        )
        repo = ServiceCatalogRepo(session)
        await repo.upsert_service_draft(
            {
                "code": service_code,
                "public_title": "Requester workplace",
                "short_description": "Requester workplace support",
                "visibility": "public",
                "owner_queue_id": queue.id,
                "default_queue_id": queue.id,
                "business_criticality": "medium",
                "reporting_category": "requester_workplace",
            },
            actor_id="test",
            actor_role="admin",
        )
        offering = await repo.upsert_offering_draft(
            {
                "service_code": service_code,
                "code": "laptop_broken",
                "public_title": "Laptop broken",
                "short_description": "Laptop does not start",
                "request_type": "incident",
                "request_template_key": template_code,
                "visibility": "public",
                "reporting_category": "requester_incidents",
            },
            actor_id="test",
            actor_role="admin",
        )
        await repo.publish_service(service_code, actor_id="test", actor_role="admin")
        await repo.publish_offering(offering["full_code"], actor_id="test", actor_role="admin")
        await session.commit()

    created = await test_client.post(
        "/api/web/requester/tickets",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}"),
        json={
            "device_id": device_id,
            "title": "Laptop broken from requester workspace",
            "description": "Laptop does not boot",
            "user_display_name": "Requester Catalog",
            "service_code": service_code,
            "offering_code": "laptop_broken",
            "request_template_key": template_code,
            "form_key": template_code,
            "form_payload": {"summary": "No boot"},
            "ticket_type": "incident",
            "knowledge_attempts": [
                {
                    "item_id": "kb-requester-1",
                    "version_id": "kb-version-1",
                    "result": "not_helpful",
                    "surface": "requester_portal",
                    "visibility_scope": "creator_visible",
                    "audience_scope": "creator",
                    "timestamp": "2026-06-08T08:00:00Z",
                }
            ],
        },
    )
    payload = await created.json()
    assert created.status == 200, payload

    async with session_maker() as session:
        ticket = await session.get(Ticket, payload["data"]["ticket_id"])

    assert ticket is not None
    assert ticket.device_id == device_id
    assert ticket.requester_person_id == approved["person"]["person_id"]
    assert ticket.requester_binding_id == approved["binding"]["binding_id"]
    assert ticket.service_code == service_code
    assert ticket.offering_code == f"{service_code}.laptop_broken"
    assert ticket.ticket_type == "incident"
    assert ticket.request_type == "incident"
    assert ticket.reporting_category == "requester_incidents"
    assert ticket.queue_id == department_queue.id
    custom_fields = ticket.custom_fields or {}
    assert custom_fields["request_context"] == "authenticated_requester_workspace"
    assert custom_fields["requester_context_snapshot"]["profile"]["person_id"] == approved["person"]["person_id"]
    assert custom_fields["requester_context_snapshot"]["device"]["device_id"] == device_id
    assert custom_fields["requester_device_id"] == device_id
    assert custom_fields["requester_asset_id"] == approved["binding"]["asset_id"]
    assert custom_fields["requester_binding_id"] == approved["binding"]["binding_id"]
    assert custom_fields["routing_decision"]["source"] == "request_template.routing_policy"
    assert custom_fields["request_form_data"] == {"summary": "No boot"}
    assert custom_fields["service_catalog"]["service_code"] == service_code
    assert custom_fields["service_catalog"]["offering_full_code"] == f"{service_code}.laptop_broken"
    assert custom_fields["knowledge_attempts"] == [
        {
            "item_id": "kb-requester-1",
            "version_id": "kb-version-1",
            "result": "not_helpful",
            "surface": "requester_portal",
            "visibility_scope": "creator_visible",
            "audience_scope": "creator",
            "occurred_at": "2026-06-08T08:00:00Z",
        }
    ]
    async with session_maker() as session:
        feedback_event = (
            await session.execute(
                select(KnowledgeFeedbackEvent).where(KnowledgeFeedbackEvent.ticket_id == payload["data"]["ticket_id"])
            )
        ).scalar_one()
    assert feedback_event.event_type == "ticket_created_after_view"
    assert feedback_event.metadata_json["knowledge_attempts"][0]["item_id"] == "kb-requester-1"


@pytest.mark.asyncio
async def test_requester_preview_ticket_accepts_catalog_form_payload(test_client, test_engine):
    suffix = uuid.uuid4().hex[:8]
    service_code = f"requester_preview_{suffix}"
    template_code = f"requester_preview_laptop_{suffix}"
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    login = "requester-preview@example.test"
    async with session_maker() as session:
        queue = TicketQueue(code=f"requester_preview_queue_{suffix}", name="Requester preview queue", is_active=True)
        session.add_all([_device(device_id, "preview-owned-device"), queue])
        await session.flush()
        forms_repo = TicketFormPacksRepo(session)
        await forms_repo.upsert_pack(
            pack_key="request_forms",
            version=f"test-{suffix}",
            schema_json={
                "pack_key": "request_forms",
                "version": f"test-{suffix}",
                "forms": [
                    {
                        "key": template_code,
                        "request_template_key": template_code,
                        "title": "Laptop preview incident",
                        "request_kind": "incident",
                        "ticket_type": "incident",
                        "fields": [
                            {"key": "summary", "label": "Summary", "type": "text", "required": True},
                        ],
                    }
                ],
            },
            created_by="test",
        )
        await forms_repo.set_preferred(pack_key="request_forms", version=f"test-{suffix}", updated_by="test")
        session.add(
            RequestTemplate(
                template_code=template_code,
                version="1",
                public_title="Laptop preview incident",
                ticket_type="incident",
                config_json={"default_queue_id": queue.id, "no_sla": True},
                is_active=True,
                published_at=datetime.now(timezone.utc),
            )
        )
        repo = ServiceCatalogRepo(session)
        await repo.upsert_service_draft(
            {
                "code": service_code,
                "public_title": "Requester preview workplace",
                "short_description": "Requester preview support",
                "visibility": "public",
                "owner_queue_id": queue.id,
                "default_queue_id": queue.id,
                "business_criticality": "medium",
                "reporting_category": "requester_preview_workplace",
            },
            actor_id="test",
            actor_role="admin",
        )
        offering = await repo.upsert_offering_draft(
            {
                "service_code": service_code,
                "code": "laptop_broken",
                "public_title": "Laptop broken preview",
                "short_description": "Laptop does not start",
                "request_type": "incident",
                "request_template_key": template_code,
                "visibility": "public",
                "reporting_category": "requester_preview_incidents",
            },
            actor_id="test",
            actor_role="admin",
        )
        await repo.publish_service(service_code, actor_id="test", actor_role="admin")
        await repo.publish_offering(offering["full_code"], actor_id="test", actor_role="admin")
        await _approved_binding(session, device_id=device_id, login=login)
        await session.commit()

    response = await test_client.post(
        "/api/web/requester/tickets/preview",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}"),
        json={
            "device_id": device_id,
            "service_code": service_code,
            "offering_code": "laptop_broken",
            "request_template_key": template_code,
            "form_key": template_code,
            "form_payload": {"summary": "No boot"},
            "description": "No boot",
        },
    )
    payload = await response.json()

    assert response.status == 200, payload
    assert payload["status"] == "success"
    assert payload["data"]["ok"] is True
    assert payload["data"]["service"]["code"] == service_code
    assert payload["data"]["offering"]["full_code"] == f"{service_code}.laptop_broken"
    assert payload["data"]["would_create_ticket"] is False
    assert payload["data"]["requester_context"]["profile"]["department"]
    assert payload["data"]["requester_context"]["device"]["device_id"] == device_id
    assert payload["data"]["requester_context"]["form_prefill"]["device_id"] == device_id
    assert payload["data"]["requester_context"]["routing_facts"]["account_mode"] == "confirmed_binding"
    assert payload["data"]["ticket_context"]["summary"]["created_on_behalf"] is False
    assert payload["data"]["ticket_context"]["summary"]["affected"]
    assert payload["data"]["ticket_context"]["diagnostic_target"]["available"] is False
    assert payload["data"]["ticket_context"]["diagnostic_target"]["status"] == "offline"
    assert payload["data"]["ticket_context"]["diagnostic_target"]["label"] == "preview-owned-device"
    assert "person_id" not in str(payload["data"]["ticket_context"])
    assert device_id not in str(payload["data"]["ticket_context"])

    async with session_maker() as session:
        ticket_count = await session.scalar(select(func.count()).select_from(Ticket))
        event_count = await session.scalar(select(func.count()).select_from(TicketEvent))
    assert ticket_count == 0
    assert event_count == 0

    agent_denied = await test_client.post(
        "/api/web/requester/tickets/preview",
        headers=_headers(f"{TEST_AGENT_PREFIX}{device_id}"),
        json={"service_code": service_code, "offering_code": "laptop_broken", "form_payload": {"summary": "No boot"}},
    )
    assert agent_denied.status == 403


@pytest.mark.asyncio
async def test_requester_on_behalf_people_search_filters_by_policy_scope(test_client, test_engine):
    suffix = uuid.uuid4().hex[:8]
    template_code = f"on_behalf_search_{suffix}"
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    login = f"requester-on-behalf-search-{suffix}@example.test"
    async with session_maker() as session:
        requester = await _person_for_login(session, login=login)
        same_department = RegistryPerson(
            person_id=str(uuid.uuid4()),
            display_name="Affected Same Department",
            full_name="Affected Same Department",
            email=f"affected-same-{suffix}@example.test",
            department_id=requester.department_id,
            location_id=requester.location_id,
            source="manual",
            status="active",
        )
        outside_department = RegistryPerson(
            person_id=str(uuid.uuid4()),
            display_name="Affected Outside Department",
            full_name="Affected Outside Department",
            email=f"affected-outside-{suffix}@example.test",
            source="manual",
            status="active",
        )
        await _seed_profile_context(session, outside_department, marker=f"outside-{suffix}")
        session.add_all([same_department, outside_department])
        await _publish_on_behalf_form(session, template_code=template_code, version=f"test-{suffix}")
        await session.commit()

    response = await test_client.get(
        f"/api/web/requester/on-behalf/people?form_key={template_code}&q=Affected",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}"),
    )
    payload = await response.json()

    assert response.status == 200, payload
    people = payload["data"]["people"]
    assert [item["display_name"] for item in people] == ["Affected Same Department"]
    assert people[0]["department"]["id"] == requester.department_id
    assert people[0]["primary_agent"]["status"] == "missing"
    assert "Affected Outside Department" not in str(payload)


@pytest.mark.asyncio
async def test_requester_on_behalf_preview_and_create_reject_out_of_scope_person(test_client, test_engine):
    suffix = uuid.uuid4().hex[:8]
    template_code = f"on_behalf_reject_{suffix}"
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    login = f"requester-on-behalf-reject-{suffix}@example.test"
    async with session_maker() as session:
        session.add(_device(device_id, "on-behalf-reject-owned"))
        approved = await _approved_binding(session, device_id=device_id, login=login)
        requester = await session.get(RegistryPerson, approved["person"]["person_id"])
        assert requester is not None
        outside_person = RegistryPerson(
            person_id=str(uuid.uuid4()),
            display_name="Out Of Scope Person",
            full_name="Out Of Scope Person",
            email=f"out-of-scope-{suffix}@example.test",
            source="manual",
            status="active",
        )
        await _seed_profile_context(session, outside_person, marker=f"outside-reject-{suffix}")
        session.add(outside_person)
        await _publish_on_behalf_form(session, template_code=template_code, version=f"test-{suffix}")
        await session.commit()

    ticket_context = {"affected_person_id": outside_person.person_id, "on_behalf_reason": "phone call"}
    preview = await test_client.post(
        "/api/web/requester/tickets/preview",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}"),
        json={
            "device_id": device_id,
            "form_key": template_code,
            "request_template_key": template_code,
            "ticket_context": ticket_context,
            "form_payload": {"summary": "Cannot start"},
            "description": "Cannot start",
        },
    )
    preview_payload = await preview.json()
    assert preview.status == 403, preview_payload
    assert preview_payload["error_code"] == "ON_BEHALF_SCOPE_DENIED"

    created = await test_client.post(
        "/api/web/requester/tickets",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}"),
        json={
            "device_id": device_id,
            "title": "Out of scope on-behalf ticket",
            "description": "Should be rejected",
            "form_key": template_code,
            "request_template_key": template_code,
            "ticket_context": ticket_context,
            "form_payload": {"summary": "Cannot start"},
            "ticket_type": "incident",
        },
    )
    created_payload = await created.json()
    assert created.status == 403, created_payload
    assert created_payload["error_code"] == "ON_BEHALF_SCOPE_DENIED"


@pytest.mark.asyncio
async def test_requester_on_behalf_exact_search_requires_exact_lookup(test_client, test_engine):
    suffix = uuid.uuid4().hex[:8]
    template_code = f"on_behalf_exact_{suffix}"
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    login = f"requester-on-behalf-exact-{suffix}@example.test"
    async with session_maker() as session:
        session.add(_device(device_id, "on-behalf-exact-owned"))
        await _approved_binding(session, device_id=device_id, login=login)
        affected = RegistryPerson(
            person_id=str(uuid.uuid4()),
            display_name="Exact Search Person",
            full_name="Exact Search Person",
            email=f"exact-search-{suffix}@example.test",
            source="manual",
            status="active",
        )
        await _seed_profile_context(session, affected, marker=f"outside-exact-{suffix}")
        session.add(affected)
        await _publish_on_behalf_form(
            session,
            template_code=template_code,
            version=f"test-{suffix}",
            allowed_scope="exact_search_only",
        )
        await session.commit()

    partial = await test_client.get(
        f"/api/web/requester/on-behalf/people?form_key={template_code}&q=Exact",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}"),
    )
    partial_payload = await partial.json()
    assert partial.status == 200, partial_payload
    assert partial_payload["data"]["people"] == []

    exact = await test_client.get(
        f"/api/web/requester/on-behalf/people?form_key={template_code}&q=Exact%20Search%20Person",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}"),
    )
    exact_payload = await exact.json()
    assert exact.status == 200, exact_payload
    assert [item["person_id"] for item in exact_payload["data"]["people"]] == [affected.person_id]

    rejected = await test_client.post(
        "/api/web/requester/tickets/preview",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}"),
        json={
            "device_id": device_id,
            "form_key": template_code,
            "request_template_key": template_code,
            "ticket_context": {
                "affected_person_id": affected.person_id,
                "on_behalf_reason": "phone call",
                "affected_person_lookup": "Exact",
            },
            "form_payload": {"summary": "Cannot start"},
            "description": "Cannot start",
        },
    )
    rejected_payload = await rejected.json()
    assert rejected.status == 403, rejected_payload
    assert rejected_payload["error_code"] == "ON_BEHALF_SCOPE_DENIED"

    accepted = await test_client.post(
        "/api/web/requester/tickets",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}"),
        json={
            "device_id": device_id,
            "title": "Exact on-behalf ticket",
            "description": "Cannot start",
            "form_key": template_code,
            "request_template_key": template_code,
            "ticket_context": {
                "affected_person_id": affected.person_id,
                "on_behalf_reason": "phone call",
                "affected_person_lookup": "Exact Search Person",
            },
            "form_payload": {"summary": "Cannot start"},
            "ticket_type": "incident",
        },
    )
    accepted_payload = await accepted.json()
    assert accepted.status == 200, accepted_payload


@pytest.mark.asyncio
async def test_requester_on_behalf_create_stores_authorized_ticket_context(test_client, test_engine):
    suffix = uuid.uuid4().hex[:8]
    template_code = f"on_behalf_create_{suffix}"
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    requester_device_id = str(uuid.uuid4())
    affected_device_id = str(uuid.uuid4())
    login = f"requester-on-behalf-create-{suffix}@example.test"
    affected_login = f"affected-on-behalf-create-{suffix}@example.test"
    async with session_maker() as session:
        session.add_all([
            _device(requester_device_id, "creator-owned-device"),
            _device(affected_device_id, "affected-primary-device"),
        ])
        requester_approved = await _approved_binding(session, device_id=requester_device_id, login=login)
        affected_approved = await _approved_binding(session, device_id=affected_device_id, login=affected_login)
        requester = await session.get(RegistryPerson, requester_approved["person"]["person_id"])
        affected = await session.get(RegistryPerson, affected_approved["person"]["person_id"])
        assert requester is not None
        assert affected is not None
        affected.department_id = requester.department_id
        affected.location_id = requester.location_id
        assert affected.department_id == requester.department_id
        await session.flush()
        await _publish_on_behalf_form(session, template_code=template_code, version=f"test-{suffix}")
        await session.commit()

    response = await test_client.post(
        "/api/web/requester/tickets",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}"),
        json={
            "device_id": requester_device_id,
            "title": "Laptop broken for coworker",
            "description": "Coworker laptop does not boot",
            "form_key": template_code,
            "request_template_key": template_code,
            "ticket_context": {
                "affected_person_id": affected_approved["person"]["person_id"],
                "on_behalf_reason": "phone call from coworker",
            },
            "form_payload": {"summary": "No boot"},
            "ticket_type": "incident",
        },
    )
    payload = await response.json()
    assert response.status == 200, payload

    async with session_maker() as session:
        ticket = await session.get(Ticket, payload["data"]["ticket_id"])

    assert ticket is not None
    custom_fields = ticket.custom_fields or {}
    assert custom_fields["created_on_behalf"] is True
    assert custom_fields["creator_person_id"] == requester_approved["person"]["person_id"]
    assert custom_fields["affected_person_id"] == affected_approved["person"]["person_id"]
    assert custom_fields["on_behalf_reason"] == "phone call from coworker"
    assert custom_fields["target_device_id"] == affected_device_id
    assert custom_fields["target_binding_id"] == affected_approved["binding"]["binding_id"]
    assert custom_fields["diagnostic_target_source"] == "affected_user_primary_agent"


@pytest.mark.asyncio
async def test_requester_ticket_detail_and_message_are_owned_only(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    owned_device_id = str(uuid.uuid4())
    foreign_device_id = str(uuid.uuid4())
    owner_login = "requester-chat-owner@example.test"
    foreign_login = "requester-chat-foreign@example.test"
    async with session_maker() as session:
        session.add_all([_device(owned_device_id, "chat-owned-device"), _device(foreign_device_id, "chat-foreign-device")])
        approved = await _approved_binding(session, device_id=owned_device_id, login=owner_login)
        await _approved_binding(session, device_id=foreign_device_id, login=foreign_login)
        created = await create_ticket_with_side_effects(
            session,
            device_id=owned_device_id,
            requester_id=owner_login,
            title="Requester message ticket",
            description="Visible to owner only",
            user_display_name="Requester Chat Owner",
            requester_profile={"full_name": "Requester Chat Owner", "email": owner_login},
            normalized_priority=build_default_priority_payload({}),
            requester_account={
                "account_mode": "confirmed_binding",
                "person_id": approved["person"]["person_id"],
                "binding_id": approved["binding"]["binding_id"],
            },
            include_public_access=True,
        )
        ticket_id = created["ticket_id"]
        await session.commit()

    owner_headers = _headers(f"{TEST_UI_USER_PREFIX}{owner_login}")
    foreign_headers = _headers(f"{TEST_UI_USER_PREFIX}{foreign_login}")

    detail = await test_client.get(f"/api/web/requester/tickets/{ticket_id}", headers=owner_headers)
    detail_payload = await detail.json()
    assert detail.status == 200, detail_payload
    assert detail_payload["data"]["ticket"]["ticket_id"] == ticket_id
    assert any(
        message.get("text") == "Visible to owner only"
        for message in detail_payload["data"].get("messages", [])
    )

    sent = await test_client.post(
        f"/api/web/requester/tickets/{ticket_id}/message",
        headers=owner_headers,
        json={"text": "Requester authenticated follow-up"},
    )
    sent_payload = await sent.json()
    assert sent.status == 200, sent_payload
    assert sent_payload["data"]["message_id"]

    denied = await test_client.post(
        f"/api/web/requester/tickets/{ticket_id}/message",
        headers=foreign_headers,
        json={"text": "Should not be accepted"},
    )
    denied_payload = await denied.json()
    assert denied.status == 404, denied_payload

    async with session_maker() as session:
        events = (
            await session.execute(
                select(TicketEvent)
                .where(TicketEvent.ticket_id == ticket_id)
                .where(TicketEvent.event_type == "chat_message")
            )
        ).scalars().all()

    texts = [event.payload.get("text") for event in events if isinstance(event.payload, dict)]
    assert "Requester authenticated follow-up" in texts
    assert "Should not be accepted" not in texts


@pytest.mark.asyncio
async def test_requester_can_claim_public_ticket_with_access_code(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    owner_device_id = str(uuid.uuid4())
    public_device_id = str(uuid.uuid4())
    login = "requester-public-claim@example.test"
    async with session_maker() as session:
        session.add_all([
            _device(owner_device_id, "claim-owned-device"),
            _device(public_device_id, "claim-public-device"),
        ])
        approved = await _approved_binding(session, device_id=owner_device_id, login=login)
        created = await create_ticket_with_side_effects(
            session,
            device_id=public_device_id,
            requester_id="public:claim-unbound",
            title="Public ticket to claim",
            description="Created before requester login",
            user_display_name="Public Claim Requester",
            requester_profile={"full_name": "Public Claim Requester"},
            normalized_priority=build_default_priority_payload({}),
            include_public_access=True,
        )
        ticket_id = created["ticket_id"]
        public_access_code = created["public_access_code"]
        await session.commit()

    before_claim = await test_client.get(
        "/api/web/requester/tickets",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}"),
    )
    before_payload = await before_claim.json()
    assert before_claim.status == 200, before_payload
    assert ticket_id not in {item["ticket_id"] for item in before_payload["data"]["tickets"]}

    response = await test_client.post(
        "/api/web/requester/tickets/claim-public",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}"),
        json={"ticket_id": ticket_id, "code": public_access_code},
    )
    payload = await response.json()
    assert response.status == 200, payload
    assert payload["data"]["ticket_id"] == ticket_id
    assert payload["data"]["requester_person_id"] == approved["person"]["person_id"]

    after_claim = await test_client.get(
        "/api/web/requester/tickets",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}"),
    )
    after_payload = await after_claim.json()
    assert after_claim.status == 200, after_payload
    assert ticket_id in {item["ticket_id"] for item in after_payload["data"]["tickets"]}

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        events = (
            await session.execute(
                select(TicketEvent)
                .where(TicketEvent.ticket_id == ticket_id)
                .where(TicketEvent.event_type == "requester_ticket_claimed")
            )
        ).scalars().all()
    assert ticket is not None
    assert ticket.requester_id == login
    assert ticket.requester_person_id == approved["person"]["person_id"]
    assert ticket.custom_fields["requester_claim"]["claimed_by_actor_id"] == login
    assert ticket.custom_fields["requester_claim"]["previous_requester_id"] == "public:claim-unbound"
    assert events
    assert events[0].payload["actor_id"] == login
    assert "code" not in events[0].payload


@pytest.mark.asyncio
async def test_requester_claim_public_ticket_requires_registry_person(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    public_device_id = str(uuid.uuid4())
    login = "requester-public-claim-unlinked@example.test"
    async with session_maker() as session:
        session.add(_device(public_device_id, "claim-unlinked-public-device"))
        created = await create_ticket_with_side_effects(
            session,
            device_id=public_device_id,
            requester_id="public:claim-unlinked",
            title="Public ticket unlinked claim",
            description="Unlinked requester must not claim",
            user_display_name="Public Claim Unlinked",
            requester_profile={"full_name": "Public Claim Unlinked"},
            normalized_priority=build_default_priority_payload({}),
            include_public_access=True,
        )
        ticket_id = created["ticket_id"]
        public_access_code = created["public_access_code"]
        await session.commit()

    response = await test_client.post(
        "/api/web/requester/tickets/claim-public",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}"),
        json={"ticket_id": ticket_id, "code": public_access_code},
    )
    payload = await response.json()
    assert response.status == 403, payload
    assert payload["error_code"] == "REQUESTER_IDENTITY_REQUIRED"

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        claimed_events = await session.scalar(
            select(func.count())
            .select_from(TicketEvent)
            .where(TicketEvent.ticket_id == ticket_id)
            .where(TicketEvent.event_type == "requester_ticket_claimed")
        )
    assert ticket is not None
    assert ticket.requester_id == "public:claim-unlinked"
    assert ticket.requester_person_id is None
    assert claimed_events == 0


@pytest.mark.asyncio
async def test_requester_claim_public_ticket_rejects_invalid_access_code(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    owner_device_id = str(uuid.uuid4())
    public_device_id = str(uuid.uuid4())
    login = "requester-public-claim-invalid@example.test"
    async with session_maker() as session:
        session.add_all([
            _device(owner_device_id, "claim-invalid-owned-device"),
            _device(public_device_id, "claim-invalid-public-device"),
        ])
        await _approved_binding(session, device_id=owner_device_id, login=login)
        created = await create_ticket_with_side_effects(
            session,
            device_id=public_device_id,
            requester_id="public:claim-invalid-unbound",
            title="Public ticket invalid claim",
            description="Wrong code must not claim",
            user_display_name="Public Claim Invalid",
            requester_profile={"full_name": "Public Claim Invalid"},
            normalized_priority=build_default_priority_payload({}),
            include_public_access=True,
        )
        ticket_id = created["ticket_id"]
        await session.commit()

    response = await test_client.post(
        "/api/web/requester/tickets/claim-public",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}"),
        json={"ticket_id": ticket_id, "code": "WRONG-CODE"},
    )
    payload = await response.json()
    assert response.status == 403, payload
    assert payload["error_code"] == "INVALID_PUBLIC_ACCESS_CODE"

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        claimed_events = await session.scalar(
            select(func.count())
            .select_from(TicketEvent)
            .where(TicketEvent.ticket_id == ticket_id)
            .where(TicketEvent.event_type == "requester_ticket_claimed")
        )
    assert ticket is not None
    assert ticket.requester_id == "public:claim-invalid-unbound"
    assert ticket.requester_person_id is None
    assert claimed_events == 0


@pytest.mark.asyncio
async def test_requester_ticket_message_accepts_attachment_refs(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    login = "requester-attachment@example.test"
    async with session_maker() as session:
        session.add(_device(device_id, "attachment-owned-device"))
        approved = await _approved_binding(session, device_id=device_id, login=login)
        created = await create_ticket_with_side_effects(
            session,
            device_id=device_id,
            requester_id=login,
            title="Requester attachment ticket",
            description="Requester can attach evidence",
            user_display_name="Requester Attachment",
            requester_profile={"full_name": "Requester Attachment", "email": login},
            normalized_priority=build_default_priority_payload({}),
            requester_account={
                "account_mode": "confirmed_binding",
                "person_id": approved["person"]["person_id"],
                "binding_id": approved["binding"]["binding_id"],
            },
            include_public_access=True,
        )
        ticket_id = created["ticket_id"]
        artifact = Artifact(
            artifact_id=str(uuid.uuid4()),
            storage_path="requester-log.txt",
            original_name="requester-log.txt",
            mime_type="text/plain",
            size_bytes=64,
            sha256="b" * 64,
            kind="file",
            device_id=device_id,
            ticket_id=ticket_id,
            operation_id=None,
            expires_at=None,
        )
        session.add(artifact)
        artifact_id = artifact.artifact_id
        await session.commit()

    sent = await test_client.post(
        f"/api/web/requester/tickets/{ticket_id}/message",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}"),
        json={"text": "", "attachment_refs": [artifact_id]},
    )
    sent_payload = await sent.json()
    assert sent.status == 200, sent_payload
    assert sent_payload["data"]["attachments_count"] == 1

    detail = await test_client.get(
        f"/api/web/requester/tickets/{ticket_id}",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}"),
    )
    detail_payload = await detail.json()
    assert detail.status == 200, detail_payload
    attached_messages = [
        message
        for message in detail_payload["data"]["messages"]
        if message.get("attachment_refs") == [artifact_id]
    ]
    assert attached_messages
    assert attached_messages[0]["attachments"][0]["artifact_id"] == artifact_id
    assert attached_messages[0]["attachments"][0]["name"] == "requester-log.txt"

    async with session_maker() as session:
        events = (
            await session.execute(
                select(TicketEvent)
                .where(TicketEvent.ticket_id == ticket_id)
                .where(TicketEvent.event_type == "chat_message")
            )
        ).scalars().all()
    event = next(item for item in events if item.payload.get("attachment_refs") == [artifact_id])
    assert event.payload["attachments"][0]["url"] == f"/api/artifacts/{artifact_id}/download"


@pytest.mark.asyncio
async def test_requester_ticket_message_rejects_foreign_attachment_ref(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    owned_device_id = str(uuid.uuid4())
    foreign_device_id = str(uuid.uuid4())
    login = "requester-foreign-attachment@example.test"
    async with session_maker() as session:
        session.add_all([_device(owned_device_id, "attachment-owned-device"), _device(foreign_device_id, "attachment-foreign-device")])
        approved = await _approved_binding(session, device_id=owned_device_id, login=login)
        created = await create_ticket_with_side_effects(
            session,
            device_id=owned_device_id,
            requester_id=login,
            title="Requester attachment boundary ticket",
            description="Requester attachment boundary",
            user_display_name="Requester Attachment Boundary",
            requester_profile={"full_name": "Requester Attachment Boundary", "email": login},
            normalized_priority=build_default_priority_payload({}),
            requester_account={
                "account_mode": "confirmed_binding",
                "person_id": approved["person"]["person_id"],
                "binding_id": approved["binding"]["binding_id"],
            },
            include_public_access=True,
        )
        foreign_artifact = Artifact(
            artifact_id=str(uuid.uuid4()),
            storage_path="foreign-log.txt",
            original_name="foreign-log.txt",
            mime_type="text/plain",
            size_bytes=64,
            sha256="c" * 64,
            kind="file",
            device_id=foreign_device_id,
            ticket_id=None,
            operation_id=None,
            expires_at=None,
        )
        session.add(foreign_artifact)
        ticket_id = created["ticket_id"]
        artifact_id = foreign_artifact.artifact_id
        await session.commit()

    response = await test_client.post(
        f"/api/web/requester/tickets/{ticket_id}/message",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}"),
        json={"text": "", "attachment_refs": [artifact_id]},
    )
    payload = await response.json()
    assert response.status == 400, payload
    assert payload["details"]["attachment_refs"]


@pytest.mark.asyncio
async def test_requester_can_close_owned_resolved_ticket_only(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    owned_device_id = str(uuid.uuid4())
    foreign_device_id = str(uuid.uuid4())
    owner_login = "requester-close-owner@example.test"
    foreign_login = "requester-close-foreign@example.test"
    async with session_maker() as session:
        session.add_all([_device(owned_device_id, "close-owned-device"), _device(foreign_device_id, "close-foreign-device")])
        approved = await _approved_binding(session, device_id=owned_device_id, login=owner_login)
        await _approved_binding(session, device_id=foreign_device_id, login=foreign_login)
        created = await create_ticket_with_side_effects(
            session,
            device_id=owned_device_id,
            requester_id=owner_login,
            title="Requester close ticket",
            description="Can be closed by owner only",
            user_display_name="Requester Close Owner",
            requester_profile={"full_name": "Requester Close Owner", "email": owner_login},
            normalized_priority=build_default_priority_payload({}),
            requester_account={
                "account_mode": "confirmed_binding",
                "person_id": approved["person"]["person_id"],
                "binding_id": approved["binding"]["binding_id"],
            },
            include_public_access=True,
        )
        ticket_id = created["ticket_id"]
        ticket = await session.get(Ticket, ticket_id)
        ticket.status = "resolved"
        ticket.resolved_at = datetime.now(timezone.utc)
        await session.commit()

    foreign_denied = await test_client.post(
        f"/api/web/requester/tickets/{ticket_id}/close",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{foreign_login}"),
        json={"reason": "requester_confirmed_resolution"},
    )
    assert foreign_denied.status == 404, await foreign_denied.text()

    closed = await test_client.post(
        f"/api/web/requester/tickets/{ticket_id}/close",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{owner_login}"),
        json={"reason": "requester_confirmed_resolution"},
    )
    closed_payload = await closed.json()
    assert closed.status == 200, closed_payload
    assert closed_payload["data"]["ticket"]["status"] == "closed"

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
    assert ticket.status == "closed"
    assert ticket.closed_at is not None


@pytest.mark.asyncio
async def test_requester_can_submit_feedback_and_reopen_owned_ticket_only(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    owned_device_id = str(uuid.uuid4())
    foreign_device_id = str(uuid.uuid4())
    owner_login = "requester-quality-owner@example.test"
    foreign_login = "requester-quality-foreign@example.test"
    async with session_maker() as session:
        session.add_all([_device(owned_device_id, "quality-owned-device"), _device(foreign_device_id, "quality-foreign-device")])
        approved = await _approved_binding(session, device_id=owned_device_id, login=owner_login)
        await _approved_binding(session, device_id=foreign_device_id, login=foreign_login)
        created = await create_ticket_with_side_effects(
            session,
            device_id=owned_device_id,
            requester_id=owner_login,
            title="Requester quality ticket",
            description="Can receive feedback and reopen",
            user_display_name="Requester Quality Owner",
            requester_profile={"full_name": "Requester Quality Owner", "email": owner_login},
            normalized_priority=build_default_priority_payload({}),
            requester_account={
                "account_mode": "confirmed_binding",
                "person_id": approved["person"]["person_id"],
                "binding_id": approved["binding"]["binding_id"],
            },
            include_public_access=True,
        )
        ticket_id = created["ticket_id"]
        ticket = await session.get(Ticket, ticket_id)
        ticket.status = "resolved"
        ticket.resolved_at = datetime.now(timezone.utc)
        await session.commit()

    foreign_feedback = await test_client.post(
        f"/api/web/requester/tickets/{ticket_id}/feedback",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{foreign_login}"),
        json={"rating": 1, "problem_resolved": False, "reason_codes": ["not_resolved"]},
    )
    assert foreign_feedback.status == 404, await foreign_feedback.text()

    feedback = await test_client.post(
        f"/api/web/requester/tickets/{ticket_id}/feedback",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{owner_login}"),
        json={
            "rating": 2,
            "problem_resolved": False,
            "resolution_confirmed": False,
            "reason_codes": ["not_resolved"],
            "comment": "Still broken",
        },
    )
    feedback_payload = await feedback.json()
    assert feedback.status == 200, feedback_payload
    assert feedback_payload["data"]["feedback_id"]
    assert feedback_payload["data"]["reopen_available"] is True

    foreign_reopen = await test_client.post(
        f"/api/web/requester/tickets/{ticket_id}/reopen",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{foreign_login}"),
        json={"reason_code": "not_resolved", "linked_feedback_id": feedback_payload["data"]["feedback_id"]},
    )
    assert foreign_reopen.status == 404, await foreign_reopen.text()

    reopened = await test_client.post(
        f"/api/web/requester/tickets/{ticket_id}/reopen",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{owner_login}"),
        json={
            "reason_code": "not_resolved",
            "reason_comment": "Still broken",
            "linked_feedback_id": feedback_payload["data"]["feedback_id"],
        },
    )
    reopened_payload = await reopened.json()
    assert reopened.status == 200, reopened_payload
    assert reopened_payload["data"]["ticket_status"] == "in_progress"

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        feedback_rows = (
            await session.execute(select(TicketFeedback).where(TicketFeedback.ticket_id == ticket_id))
        ).scalars().all()
        reopen_rows = (
            await session.execute(select(TicketReopenEvent).where(TicketReopenEvent.ticket_id == ticket_id))
        ).scalars().all()
    assert ticket.status == "in_progress"
    assert len(feedback_rows) == 1
    assert len(reopen_rows) == 1
    assert reopen_rows[0].linked_feedback_id == feedback_payload["data"]["feedback_id"]
