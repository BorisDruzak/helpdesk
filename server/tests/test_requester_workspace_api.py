from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import (
    Artifact,
    Device,
    KnowledgeFeedbackEvent,
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
from registry.registration_service import RegistrationService
from tests.conftest import TEST_AGENT_PREFIX, TEST_UI_USER_PREFIX
from tickets.create_flow import build_default_priority_payload, create_ticket_with_side_effects


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


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


async def _approved_binding(session, *, device_id: str, login: str):
    service = RegistrationService(session)
    claim = await service.submit_agent_profile_claim(
        device_id=device_id,
        requester_id=login,
        display_name=f"Requester {login}",
        profile={"full_name": f"Requester {login}", "email": login, "login": login, "user_confirmed": True},
    )
    return await service.approve_claim(claim["registration"]["claim_id"], reviewed_by="admin")


async def _person_for_login(session, *, login: str) -> RegistryPerson:
    person = RegistryPerson(
        person_id=str(uuid.uuid4()),
        display_name=f"Requester {login}",
        full_name=f"Requester {login}",
        email=login,
        source="manual",
        status="active",
    )
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
        session.add_all([_device(device_id, "catalog-owned-device"), queue])
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
                public_title="Laptop incident",
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
        approved = await _approved_binding(session, device_id=device_id, login=login)
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
    custom_fields = ticket.custom_fields or {}
    assert custom_fields["request_context"] == "authenticated_requester_workspace"
    assert custom_fields["request_form_data"] == {"summary": "No boot"}
    assert custom_fields["service_catalog"]["service_code"] == service_code
    assert custom_fields["service_catalog"]["offering_full_code"] == f"{service_code}.laptop_broken"
    assert custom_fields["knowledge_attempts"] == [
        {
            "item_id": "kb-requester-1",
            "version_id": "kb-version-1",
            "result": "not_helpful",
            "surface": "requester_portal",
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
