from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
from types import SimpleNamespace
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import (
    Device,
    ObserverErrorOccurrence,
    ObserverErrorSignature,
    ObserverIntegrityEvent,
    ObserverSpan,
    ObserverTrace,
    RegistryDepartment,
    RegistryLocation,
    RegistryPerson,
    RegistryPersonIdentity,
    RequestTemplate,
    Ticket,
    TicketQueue,
)
from app.repos.service_catalog_repo import ServiceCatalogRepo
from app.repos.ticket_form_packs_repo import TicketFormPacksRepo
from customer_history.projection_service import CustomerHistoryProjectionService
from domain_ports import (
    RegistryInvalidProjection,
    RegistryNotFound,
    RegistryObserverReadContext,
    RequesterProfileCompletionProjection,
    RequesterRef,
    UnavailableRegistryPort,
)
from observer.checks.web_cabinet import check_web_cabinet
from observer.integrity_service import ObserverIntegrityService
from observer.service import ObserverOverlayService, TraceOverlayFilters
from observer.web_event_writer import write_web_cabinet_observer_event
from registry.policy_service import RegistryPolicyService
from registry.registration_service import RegistrationService
from tests.conftest import TEST_UI_ADMIN_TOKEN, TEST_UI_USER_PREFIX
from tickets.ticket_context import build_ticket_context_v1
import web_api.session_handlers as session_handlers_module


pytestmark = pytest.mark.db_cleanup("observer_diagnostics")


class _ProfileCompletionPort:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def requester_profile_completion(
        self,
        observer: RegistryObserverReadContext,
        person: RequesterRef,
    ) -> RequesterProfileCompletionProjection:
        self.calls.append((observer.source, person.external_id))
        return RequesterProfileCompletionProjection(
            person=person,
            complete=False,
            blocks=True,
            status="required",
            missing_field_keys=("phone",),
            source="local_authoritative",
        )


class _ProfileCompletionOutcomePort:
    def __init__(self, outcome: object) -> None:
        self._outcome = outcome

    async def requester_profile_completion(
        self,
        _observer: RegistryObserverReadContext,
        _person: RequesterRef,
    ) -> object:
        return self._outcome


class _WebCabinetCheckResult:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def scalars(self) -> "_WebCabinetCheckResult":
        return self

    def all(self) -> list[object]:
        return list(self._rows)


class _WebCabinetCheckSession:
    def __init__(self, ticket: object | list[object]) -> None:
        self._tickets = ticket if isinstance(ticket, list) else [ticket]

    async def execute(self, _statement: object) -> _WebCabinetCheckResult:
        return _WebCabinetCheckResult(self._tickets)

    async def scalar(self, _statement: object) -> int:
        return 1

def _headers(token: str, *, request_id: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if request_id:
        headers["X-Request-ID"] = request_id
    return headers


def _device(device_id: str, hostname: str = "observer-device") -> Device:
    return Device(
        device_id=device_id,
        protocol_version="ws_ticket_v3",
        agent_version="3.1.59",
        hostname=hostname,
        os="Windows",
        capabilities={},
        device_metadata={},
    )


async def _seed_completed_person_for_login(session, *, login: str) -> RegistryPerson:
    suffix = uuid.uuid4().hex[:8]
    department_id = str(uuid.uuid4())
    location_id = str(uuid.uuid4())
    person = RegistryPerson(
        person_id=str(uuid.uuid4()),
        display_name=f"Requester {login}",
        full_name=f"Requester {login}",
        email=login,
        department_id=department_id,
        location_id=location_id,
        phone="1001",
        source="test",
        status="active",
    )
    session.add_all(
        [
            RegistryDepartment(
                department_id=department_id,
                code=f"observer-web-dept-{suffix}",
                name=f"Observer Web Dept {suffix}",
                status="active",
                source="test",
                metadata_json={},
            ),
            RegistryLocation(
                location_id=location_id,
                building=f"Observer Web Building {suffix}",
                floor="1",
                room="101",
                display_name=f"Observer Web Building {suffix} / 101",
                status="active",
                source="test",
                metadata_json={},
            ),
            person,
            RegistryPersonIdentity(
                person_id=person.person_id,
                provider="ui_login",
                identifier=login,
                normalized_identifier=login,
                verified=True,
                source="test",
            ),
        ]
    )
    return person


def _web_ticket_context(
    *,
    creator_person_id: str,
    affected_person_id: str,
    target_device_id: str,
    source: str,
    created_on_behalf: bool = False,
    requester_context: dict | None = None,
) -> dict:
    context_snapshot = {
        "profile_schema": {
            "schema_key": "requester_profile",
            "version": "observer-test-profile-schema",
        }
    }
    if requester_context:
        context_snapshot.update(requester_context)
    return build_ticket_context_v1(
        creator={"person_id": creator_person_id, "actor_id": f"{creator_person_id}@example.test"},
        affected={"person_id": affected_person_id, "display_name": "Affected User"},
        created_on_behalf=created_on_behalf,
        on_behalf_reason="phone call" if created_on_behalf else None,
        requester_context=context_snapshot,
        diagnostic_target={
            "device_id": target_device_id,
            "agent_status": "online",
            "source": source,
            "hostname": f"target-{target_device_id[:8]}",
        },
        form={
            "key": "observer_web_form",
            "form_schema_version": "observer-test-form-schema",
            "availability_policy": {"available_without_completed_profile": False},
        },
        policy_refs={"diagnostic_policy": "server_owned_primary_agent"},
    )


async def _write_ticket_create_trace(session, *, ticket_id: str, device_id: str, person_id: str) -> None:
    await write_web_cabinet_observer_event(
        session,
        source="requester_ticket_create",
        event_type="ticket_create_succeeded",
        severity="info",
        route="/api/web/requester/tickets",
        actor_context={"actor_id": f"{person_id}@example.test", "actor_role": "user", "method": "POST"},
        ticket_id=ticket_id,
        device_id=device_id,
        person_id=person_id,
        result="succeeded",
        payload={"test_marker": "web-cabinet-integrity"},
    )


@pytest.mark.asyncio
async def test_web_cabinet_writer_persists_redacted_searchable_trace(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())
    person_id = str(uuid.uuid4())

    async with session_maker() as session:
        trace_id = await write_web_cabinet_observer_event(
            session,
            source="requester_ticket_create",
            event_type="ticket_create_blocked",
            severity="warning",
            route="/api/web/requester/tickets",
            actor_context={
                "actor_id": "requester@example.test",
                "actor_role": "user",
                "method": "POST",
                "correlation_id": "corr-phase-d",
            },
            ticket_id=ticket_id,
            device_id=device_id,
            person_id=person_id,
            result="blocked",
            error_code="REQUESTER_PROFILE_INCOMPLETE",
            payload={
                "Authorization": "Bearer raw-secret",
                "Cookie": "pc_client_web_session=raw-cookie",
                "password": "secret-password",
                "token": "secret-token",
                "email": "requester@example.test",
                "phone": "+15551234567",
                "raw_request_body": {"password": "nested-secret"},
                "safe_flag": True,
            },
        )
        await session.flush()

        trace = await session.get(ObserverTrace, trace_id)
        span = (
            await session.execute(sa.select(ObserverSpan).where(ObserverSpan.trace_id == trace_id))
        ).scalar_one()

        assert trace is not None
        assert trace.root_kind == "requester_web"
        assert trace.ticket_id == ticket_id
        assert trace.device_id == device_id
        assert trace.status == "failed"
        assert trace.error_count == 1
        assert trace.attrs_json["source"] == "requester_ticket_create"
        assert trace.attrs_json["event_type"] == "ticket_create_blocked"
        assert trace.attrs_json["person_id"] == person_id
        assert trace.attrs_json["error_code"] == "REQUESTER_PROFILE_INCOMPLETE"
        assert span.component == "web_cabinet"
        assert span.event_type == "ticket_create_blocked"
        assert span.attrs_json["route"] == "/api/web/requester/tickets"
        assert span.attrs_json["payload"]["safe_flag"] is True

        serialized = json.dumps({"trace": trace.attrs_json, "span": span.attrs_json}, sort_keys=True)
        assert "raw-secret" not in serialized
        assert "raw-cookie" not in serialized
        assert "secret-password" not in serialized
        assert "secret-token" not in serialized
        assert "nested-secret" not in serialized
        assert "requester@example.test" not in serialized
        assert "+15551234567" not in serialized

        found = await ObserverOverlayService(session).search_traces(
            TraceOverlayFilters(
                root_kind="requester_web",
                source="requester_ticket_create",
                route="/api/web/requester/tickets",
                person_id=person_id,
                error_code="REQUESTER_PROFILE_INCOMPLETE",
                event_type="ticket_create_blocked",
            ),
            limit=10,
        )

    assert any(item["trace_id"] == trace_id for item in found)


@pytest.mark.asyncio
async def test_web_cabinet_writer_does_not_mutate_ticket_business_state(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())
    person_id = str(uuid.uuid4())
    custom_fields = {
        "request_context": "authenticated_requester_workspace",
        "requester_account_mode": "confirmed_binding",
        "business_marker": {"source": "ticket_business_state", "version": 1},
    }

    async with session_maker() as session:
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id=device_id,
                title="Business state must stay on the ticket",
                description="Observer writes must not become the ticket source of truth.",
                status="new",
                requester_id="overlay-check@example.test",
                requester_person_id=person_id,
                requester_account_mode="confirmed_binding",
                custom_fields=dict(custom_fields),
            )
        )
        await session.commit()

    async with session_maker() as session:
        before = await session.get(Ticket, ticket_id)
        assert before is not None
        before_snapshot = {
            "device_id": before.device_id,
            "status": before.status,
            "title": before.title,
            "description": before.description,
            "requester_id": before.requester_id,
            "requester_person_id": before.requester_person_id,
            "requester_account_mode": before.requester_account_mode,
            "custom_fields": before.custom_fields,
        }

        trace_id = await write_web_cabinet_observer_event(
            session,
            source="requester_ticket_create",
            event_type="ticket_create_blocked",
            severity="warning",
            route="/api/web/requester/tickets",
            actor_context={
                "actor_id": "overlay-check@example.test",
                "actor_role": "user",
                "method": "POST",
                "correlation_id": "overlay-invariant",
            },
            ticket_id=ticket_id,
            device_id=device_id,
            person_id=person_id,
            result="blocked",
            error_code="REQUESTER_PROFILE_INCOMPLETE",
            payload={"reason": "profile_incomplete", "raw_request_body": {"token": "raw-secret"}},
        )
        await session.commit()

    async with session_maker() as session:
        after = await session.get(Ticket, ticket_id)
        trace = await session.get(ObserverTrace, trace_id)
        signature = await session.get(
            ObserverErrorSignature,
            "web_cabinet:requester_ticket_create:ticket_create_blocked:requester_profile_incomplete",
        )
        span_count = await session.scalar(
            sa.select(sa.func.count()).select_from(ObserverSpan).where(ObserverSpan.trace_id == trace_id)
        )
        occurrence_count = await session.scalar(
            sa.select(sa.func.count())
            .select_from(ObserverErrorOccurrence)
            .where(ObserverErrorOccurrence.trace_id == trace_id)
        )

    assert after is not None
    assert {
        "device_id": after.device_id,
        "status": after.status,
        "title": after.title,
        "description": after.description,
        "requester_id": after.requester_id,
        "requester_person_id": after.requester_person_id,
        "requester_account_mode": after.requester_account_mode,
        "custom_fields": after.custom_fields,
    } == before_snapshot
    assert trace is not None
    assert trace.root_kind == "requester_web"
    assert span_count == 1
    assert occurrence_count == 1
    assert signature is not None


@pytest.mark.asyncio
async def test_web_cabinet_integrity_scan_detects_missing_context_and_create_event(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())
    person_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id=device_id,
                title="Web requester ticket without observer coverage",
                description="Created before Phase D instrumentation",
                status="new",
                requester_id="requester@example.test",
                requester_person_id=person_id,
                requester_account_mode="confirmed_binding",
                custom_fields={
                    "request_context": "authenticated_requester_workspace",
                    "requester_account_mode": "confirmed_binding",
                },
            )
        )
        await session.commit()

    async with session_maker() as session:
        result = await ObserverIntegrityService(session).run_scan(run_id="phase-d-web-cabinet-test")
        await session.commit()

        rows = (
            await session.execute(
                sa.select(ObserverIntegrityEvent).where(ObserverIntegrityEvent.ticket_id == ticket_id)
            )
        ).scalars().all()

        by_type = {row.event_type: row for row in rows}
        assert result.active >= 2
        assert by_type["web_ticket_missing_ticket_context_v1"].severity == "critical"
        assert (
            by_type["web_ticket_missing_ticket_context_v1"].dedupe_key
            == f"web_ticket_missing_ticket_context_v1:{ticket_id}"
        )
        assert by_type["missing_observer_event_for_web_ticket_create"].severity == "medium"
        assert (
            by_type["missing_observer_event_for_web_ticket_create"].dedupe_key
            == f"missing_observer_event_for_web_ticket_create:{ticket_id}"
        )
        assert by_type["missing_observer_event_for_web_ticket_create"].source == "observer.web_cabinet"

        filtered = await ObserverIntegrityService(session).list_events(
            source="observer.web_cabinet",
            event_type="missing_observer_event_for_web_ticket_create",
            ticket_id=ticket_id,
            limit=10,
        )
        assert [item["event_type"] for item in filtered["items"]] == [
            "missing_observer_event_for_web_ticket_create"
        ]


@pytest.mark.asyncio
async def test_web_cabinet_integrity_scan_detects_missing_schema_versions(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())
    person_id = str(uuid.uuid4())
    context = _web_ticket_context(
        creator_person_id=person_id,
        affected_person_id=person_id,
        target_device_id=device_id,
        source="creator_primary_agent",
    )
    context["requester_context"].pop("profile_schema", None)
    context["form"].pop("form_schema_version", None)

    async with session_maker() as session:
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id=device_id,
                title="Schema version evidence missing",
                description="Web requester ticket has context but lacks form/profile schema versions.",
                status="new",
                requester_id="schema-version@example.test",
                requester_person_id=person_id,
                requester_account_mode="confirmed_binding",
                custom_fields={
                    "request_context": "authenticated_requester_workspace",
                    "requester_account_mode": "confirmed_binding",
                    "ticket_context": context,
                    "creator_person_id": person_id,
                    "affected_person_id": person_id,
                    "target_device_id": device_id,
                    "diagnostic_target_source": "creator_primary_agent",
                    "requester_context_snapshot": {"account": {"account_mode": "confirmed_binding"}},
                    "request_form": {
                        "source": "legacy_pack",
                        "pack_key": "request_forms",
                        "pack_version": "observer-form-pack-only",
                        "form_key": "observer_web_form",
                    },
                    "request_form_key": "observer_web_form",
                },
            )
        )
        await _write_ticket_create_trace(session, ticket_id=ticket_id, device_id=device_id, person_id=person_id)
        await session.commit()

    async with session_maker() as session:
        await ObserverIntegrityService(session).run_scan(run_id="phase-m-schema-versions")
        await session.commit()
        rows = (
            await session.execute(
                sa.select(ObserverIntegrityEvent).where(ObserverIntegrityEvent.ticket_id == ticket_id)
            )
        ).scalars().all()

    by_type = {row.event_type: row for row in rows}
    profile_event = by_type["web_ticket_missing_profile_schema_version"]
    form_event = by_type["web_ticket_missing_form_schema_version"]
    assert profile_event.severity == "high"
    assert profile_event.dedupe_key == f"web_ticket_missing_profile_schema_version:{ticket_id}"
    assert profile_event.evidence_json["has_requester_context_snapshot"] is True
    assert form_event.severity == "high"
    assert form_event.dedupe_key == f"web_ticket_missing_form_schema_version:{ticket_id}"
    assert form_event.evidence_json["has_request_form_snapshot"] is True
    assert "web_ticket_missing_ticket_context_v1" not in by_type
    assert "missing_observer_event_for_web_ticket_create" not in by_type


@pytest.mark.asyncio
async def test_web_cabinet_integrity_scan_detects_remaining_web_first_target_invariants(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    profile_ticket_id = str(uuid.uuid4())
    fallback_ticket_id = str(uuid.uuid4())
    forged_ticket_id = str(uuid.uuid4())
    profile_person_id = str(uuid.uuid4())
    creator_person_id = str(uuid.uuid4())
    affected_person_id = str(uuid.uuid4())
    profile_device_id = str(uuid.uuid4())
    creator_device_id = str(uuid.uuid4())
    canonical_device_id = str(uuid.uuid4())
    forged_device_id = str(uuid.uuid4())

    profile_context = _web_ticket_context(
        creator_person_id=profile_person_id,
        affected_person_id=profile_person_id,
        target_device_id=profile_device_id,
        source="creator_primary_agent",
        requester_context={
            "profile_completion": {
                "complete": False,
                "blocks": True,
                "status": "required",
                "missing_fields": [{"key": "phone"}],
            }
        },
    )
    fallback_context = _web_ticket_context(
        creator_person_id=creator_person_id,
        affected_person_id=affected_person_id,
        target_device_id=creator_device_id,
        source="creator_primary_agent",
        created_on_behalf=True,
        requester_context={"account": {"account_mode": "confirmed_binding"}},
    )
    forged_context = _web_ticket_context(
        creator_person_id=profile_person_id,
        affected_person_id=profile_person_id,
        target_device_id=canonical_device_id,
        source="creator_primary_agent",
        requester_context={"account": {"account_mode": "confirmed_binding"}},
    )

    async with session_maker() as session:
        session.add_all(
            [
                Ticket(
                    ticket_id=profile_ticket_id,
                    device_id=profile_device_id,
                    title="Profile gate bypass should be detected",
                    description="Normal form was created while profile completion still blocked tickets.",
                    status="new",
                    requester_id="profile-incomplete@example.test",
                    requester_person_id=profile_person_id,
                    requester_account_mode="confirmed_binding",
                    custom_fields={
                        "request_context": "authenticated_requester_workspace",
                        "requester_account_mode": "confirmed_binding",
                        "ticket_context": profile_context,
                        "created_on_behalf": False,
                        "creator_person_id": profile_person_id,
                        "affected_person_id": profile_person_id,
                        "target_device_id": profile_device_id,
                        "diagnostic_target_source": "creator_primary_agent",
                        "requester_context_snapshot": profile_context["requester_context"],
                    },
                ),
                Ticket(
                    ticket_id=fallback_ticket_id,
                    device_id=creator_device_id,
                    title="On-behalf fallback should be detected",
                    description="Affected ticket incorrectly targets creator primary agent.",
                    status="new",
                    requester_id="creator@example.test",
                    requester_person_id=creator_person_id,
                    requester_account_mode="confirmed_binding",
                    custom_fields={
                        "request_context": "authenticated_requester_workspace",
                        "requester_account_mode": "confirmed_binding",
                        "ticket_context": fallback_context,
                        "created_on_behalf": True,
                        "creator_person_id": creator_person_id,
                        "affected_person_id": affected_person_id,
                        "target_device_id": creator_device_id,
                        "diagnostic_target_source": "creator_primary_agent",
                        "on_behalf_reason": "phone call",
                    },
                ),
                Ticket(
                    ticket_id=forged_ticket_id,
                    device_id=forged_device_id,
                    title="Forged target alias should be detected",
                    description="Browser-supplied target leaked into flat dispatch alias.",
                    status="new",
                    requester_id="forged-target@example.test",
                    requester_person_id=profile_person_id,
                    requester_account_mode="confirmed_binding",
                    custom_fields={
                        "request_context": "authenticated_requester_workspace",
                        "requester_account_mode": "confirmed_binding",
                        "ticket_context": forged_context,
                        "created_on_behalf": False,
                        "creator_person_id": profile_person_id,
                        "affected_person_id": profile_person_id,
                        "target_device_id": forged_device_id,
                        "diagnostic_target_source": "creator_primary_agent",
                        "request_payload": {"target_device_id": forged_device_id},
                    },
                ),
            ]
        )
        await _write_ticket_create_trace(
            session,
            ticket_id=profile_ticket_id,
            device_id=profile_device_id,
            person_id=profile_person_id,
        )
        await _write_ticket_create_trace(
            session,
            ticket_id=fallback_ticket_id,
            device_id=creator_device_id,
            person_id=creator_person_id,
        )
        await _write_ticket_create_trace(
            session,
            ticket_id=forged_ticket_id,
            device_id=forged_device_id,
            person_id=profile_person_id,
        )
        await session.commit()

    async with session_maker() as session:
        await ObserverIntegrityService(session).run_scan(run_id="phase-d-web-cabinet-invariants")
        await session.commit()

        rows = (
            await session.execute(
                sa.select(ObserverIntegrityEvent).where(
                    ObserverIntegrityEvent.ticket_id.in_(
                        [profile_ticket_id, fallback_ticket_id, forged_ticket_id]
                    )
                )
            )
        ).scalars().all()

    by_type = {(row.ticket_id, row.event_type): row for row in rows}
    profile_event = by_type[(profile_ticket_id, "profile_incomplete_normal_ticket_created")]
    fallback_event = by_type[(fallback_ticket_id, "diagnostic_target_creator_fallback_on_behalf")]
    forged_event = by_type[(forged_ticket_id, "forged_target_device_accepted")]

    assert profile_event.severity == "high"
    assert profile_event.dedupe_key == f"profile_incomplete_normal_ticket_created:{profile_ticket_id}"
    assert fallback_event.severity == "critical"
    assert fallback_event.dedupe_key == f"diagnostic_target_creator_fallback_on_behalf:{fallback_ticket_id}"
    assert forged_event.severity == "critical"
    assert forged_event.dedupe_key == f"forged_target_device_accepted:{forged_ticket_id}"
    assert forged_event.evidence_json["requested_target_device_id"] == forged_device_id
    assert forged_event.evidence_json["context_target_device_id"] == canonical_device_id


@pytest.mark.asyncio
async def test_web_cabinet_integrity_scan_detects_on_behalf_knowledge_audience_leak(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    creator_person_id = str(uuid.uuid4())
    affected_person_id = str(uuid.uuid4())
    affected_device_id = str(uuid.uuid4())
    context = _web_ticket_context(
        creator_person_id=creator_person_id,
        affected_person_id=affected_person_id,
        target_device_id=affected_device_id,
        source="affected_person_primary_agent",
        created_on_behalf=True,
        requester_context={"account": {"account_mode": "confirmed_binding"}},
    )

    async with session_maker() as session:
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id=affected_device_id,
                title="On-behalf Knowledge audience leak",
                description="Requester-side Knowledge attempt was stored with affected audience scope.",
                status="new",
                requester_id="creator@example.test",
                requester_person_id=creator_person_id,
                requester_account_mode="confirmed_binding",
                custom_fields={
                    "request_context": "authenticated_requester_workspace",
                    "requester_account_mode": "confirmed_binding",
                    "ticket_context": context,
                    "created_on_behalf": True,
                    "creator_person_id": creator_person_id,
                    "affected_person_id": affected_person_id,
                    "target_device_id": affected_device_id,
                    "diagnostic_target_source": "affected_person_primary_agent",
                    "knowledge_attempts": [
                        {
                            "item_id": "kb-affected-only",
                            "version_id": "kb-version-affected",
                            "result": "suggested",
                            "surface": "requester_portal",
                            "visibility_scope": "requester_visible",
                            "audience_scope": "affected",
                            "title": "Affected-only troubleshooting article",
                        },
                        {
                            "item_id": "kb-creator-safe",
                            "result": "viewed",
                            "surface": "requester_portal",
                            "visibility_scope": "creator_visible",
                            "audience_scope": "creator",
                        },
                    ],
                },
            )
        )
        await _write_ticket_create_trace(
            session,
            ticket_id=ticket_id,
            device_id=affected_device_id,
            person_id=creator_person_id,
        )
        await session.commit()

    async with session_maker() as session:
        await ObserverIntegrityService(session).run_scan(run_id="phase-d-web-cabinet-knowledge-leak")
        await session.commit()

        event = await session.scalar(
            sa.select(ObserverIntegrityEvent).where(
                ObserverIntegrityEvent.ticket_id == ticket_id,
                ObserverIntegrityEvent.event_type == "knowledge_audience_leak_on_behalf",
            )
        )

    assert event is not None
    assert event.severity == "critical"
    assert event.dedupe_key == f"knowledge_audience_leak_on_behalf:{ticket_id}"
    assert event.source == "observer.web_cabinet"
    assert event.evidence_json["invalid_attempt_count"] == 1
    assert event.evidence_json["invalid_attempts"] == [
        {
            "item_ref": "knowledge:kb-affec",
            "surface": "requester_portal",
            "visibility_scope": "requester_visible",
            "audience_scope": "affected",
        }
    ]
    assert "Affected-only troubleshooting article" not in json.dumps(event.evidence_json)


@pytest.mark.asyncio
async def test_web_cabinet_integrity_scan_detects_missing_customer_history_projection(
    test_engine,
    monkeypatch,
) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    person_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())
    context = _web_ticket_context(
        creator_person_id=person_id,
        affected_person_id=person_id,
        target_device_id=device_id,
        source="creator_primary_agent",
        requester_context={"account": {"account_mode": "confirmed_binding"}},
    )

    async def broken_history_for_ticket(self, ticket_id, **kwargs):
        return {
            "ticket_ref": None,
            "events": [],
            "count": 0,
            "redaction_report": {"removed_count": 0, "role": "support"},
            "sources": [],
        }

    monkeypatch.setattr(
        CustomerHistoryProjectionService,
        "history_for_ticket",
        broken_history_for_ticket,
    )

    async with session_maker() as session:
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id=device_id,
                title="Customer History projection missing",
                description="Observer should detect a broken Customer History projection.",
                status="new",
                requester_id="customer-history-missing@example.test",
                requester_person_id=person_id,
                requester_account_mode="confirmed_binding",
                custom_fields={
                    "request_context": "authenticated_requester_workspace",
                    "requester_account_mode": "confirmed_binding",
                    "ticket_context": context,
                    "created_on_behalf": False,
                    "creator_person_id": person_id,
                    "affected_person_id": person_id,
                    "target_device_id": device_id,
                    "diagnostic_target_source": "creator_primary_agent",
                },
            )
        )
        await _write_ticket_create_trace(session, ticket_id=ticket_id, device_id=device_id, person_id=person_id)
        await session.commit()

    async with session_maker() as session:
        await ObserverIntegrityService(session).run_scan(run_id="phase-d-web-cabinet-customer-history")
        await session.commit()

        event = await session.scalar(
            sa.select(ObserverIntegrityEvent).where(
                ObserverIntegrityEvent.ticket_id == ticket_id,
                ObserverIntegrityEvent.event_type == "missing_customer_history_for_ticket",
            )
        )

    assert event is not None
    assert event.severity == "medium"
    assert event.dedupe_key == f"missing_customer_history_for_ticket:{ticket_id}"
    assert event.source == "observer.web_cabinet"
    assert set(event.evidence_json["missing_fields"]) >= {
        "ticket_ref",
        "events",
        "sources.ticket",
        "events.ticket_created",
    }
    assert event.evidence_json["projection_event_count"] == 0
    assert event.evidence_json["sources"] == []
    assert "Customer History projection missing" not in json.dumps(event.evidence_json)


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_web_cabinet_recomputes_completion_through_registry_port_when_snapshot_is_missing() -> None:
    ticket_id = "web-cabinet-port-ticket"
    person_id = "person-1"
    device_id = "web-cabinet-port-device"
    context = _web_ticket_context(
        creator_person_id=person_id,
        affected_person_id=person_id,
        target_device_id=device_id,
        source="creator_primary_agent",
        requester_context={"account": {"account_mode": "confirmed_binding"}},
    )

    ticket = SimpleNamespace(
        ticket_id=ticket_id,
        device_id=device_id,
        requester_id="person-1@example.test",
        requester_person_id=person_id,
        requester_account_mode="confirmed_binding",
        custom_fields={
            "request_context": "authenticated_requester_workspace",
            "requester_account_mode": "confirmed_binding",
            "ticket_context": context,
        },
        created_at=None,
    )

    profile_completion_port = _ProfileCompletionPort()
    result = await check_web_cabinet(
        _WebCabinetCheckSession(ticket),
        registry_port=profile_completion_port,
    )

    assert profile_completion_port.calls == [("observer.web_cabinet", "person-1")]
    assert any(event.event_type == "profile_incomplete_normal_ticket_created" for event in result.events)


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_web_cabinet_emits_degradation_when_profile_completion_port_is_unavailable() -> None:
    ticket_id = "web-cabinet-unavailable-ticket"
    person_id = "web-cabinet-unavailable-person"
    device_id = "web-cabinet-unavailable-device"
    context = _web_ticket_context(
        creator_person_id=person_id,
        affected_person_id=person_id,
        target_device_id=device_id,
        source="creator_primary_agent",
        requester_context={"account": {"account_mode": "confirmed_binding"}},
    )

    ticket = SimpleNamespace(
        ticket_id=ticket_id,
        device_id=device_id,
        requester_id="profile-unavailable@example.test",
        requester_person_id=person_id,
        requester_account_mode="confirmed_binding",
        custom_fields={
            "request_context": "authenticated_requester_workspace",
            "requester_account_mode": "confirmed_binding",
            "ticket_context": context,
        },
        created_at=None,
    )
    result = await check_web_cabinet(
        _WebCabinetCheckSession(ticket),
        registry_port=UnavailableRegistryPort(),
    )

    assert any(event.event_type == "profile_completion_registry_unavailable" for event in result.events)


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_web_cabinet_emits_redacted_degradation_when_profile_completion_port_is_invalid() -> None:
    ticket_id = "web-cabinet-invalid-ticket"
    person_id = "web-cabinet-invalid-person"
    device_id = "web-cabinet-invalid-device"
    context = _web_ticket_context(
        creator_person_id=person_id,
        affected_person_id=person_id,
        target_device_id=device_id,
        source="creator_primary_agent",
        requester_context={"account": {"account_mode": "confirmed_binding"}},
    )
    ticket = SimpleNamespace(
        ticket_id=ticket_id,
        device_id=device_id,
        requester_id="profile-invalid@example.test",
        requester_person_id=person_id,
        requester_account_mode="confirmed_binding",
        custom_fields={
            "request_context": "authenticated_requester_workspace",
            "requester_account_mode": "confirmed_binding",
            "ticket_context": context,
        },
        created_at=None,
    )

    result = await check_web_cabinet(
        _WebCabinetCheckSession(ticket),
        registry_port=_ProfileCompletionOutcomePort(RegistryInvalidProjection()),
    )

    event = next(event for event in result.events if event.event_type == "profile_completion_registry_invalid")
    assert event.evidence == {
        "profile_completion_source": "registry_port",
        "registry_outcome": "invalid",
        "registry_code": "registry_projection_invalid",
    }
    assert not any(event.event_type == "profile_incomplete_normal_ticket_created" for event in result.events)


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_web_cabinet_skips_completion_evidence_when_profile_completion_port_returns_not_found() -> None:
    ticket_id = "web-cabinet-not-found-ticket"
    person_id = "web-cabinet-not-found-person"
    device_id = "web-cabinet-not-found-device"
    context = _web_ticket_context(
        creator_person_id=person_id,
        affected_person_id=person_id,
        target_device_id=device_id,
        source="creator_primary_agent",
        requester_context={"account": {"account_mode": "confirmed_binding"}},
    )
    ticket = SimpleNamespace(
        ticket_id=ticket_id,
        device_id=device_id,
        requester_id="profile-not-found@example.test",
        requester_person_id=person_id,
        requester_account_mode="confirmed_binding",
        custom_fields={
            "request_context": "authenticated_requester_workspace",
            "requester_account_mode": "confirmed_binding",
            "ticket_context": context,
        },
        created_at=None,
    )

    result = await check_web_cabinet(
        _WebCabinetCheckSession(ticket),
        registry_port=_ProfileCompletionOutcomePort(RegistryNotFound(code="registry_requester_not_found")),
    )

    assert not any(event.event_type.startswith("profile_completion_registry_") for event in result.events)
    assert not any(event.event_type == "profile_incomplete_normal_ticket_created" for event in result.events)


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_web_cabinet_contains_malformed_creator_ref_and_continues_next_ticket() -> None:
    malformed_ref = "x" * 513
    invalid_ticket = SimpleNamespace(
        ticket_id="web-cabinet-malformed-ref-ticket",
        device_id="web-cabinet-malformed-ref-device",
        requester_id="malformed-ref@example.test",
        requester_person_id=malformed_ref,
        requester_account_mode="confirmed_binding",
        custom_fields={
            "request_context": "authenticated_requester_workspace",
            "requester_account_mode": "confirmed_binding",
            "ticket_context": _web_ticket_context(
                creator_person_id=malformed_ref,
                affected_person_id=malformed_ref,
                target_device_id="web-cabinet-malformed-ref-device",
                source="creator_primary_agent",
                requester_context={"account": {"account_mode": "confirmed_binding"}},
            ),
        },
        created_at=None,
    )
    valid_ticket = SimpleNamespace(
        ticket_id="web-cabinet-valid-after-malformed-ticket",
        device_id="web-cabinet-valid-after-malformed-device",
        requester_id="valid-after-malformed@example.test",
        requester_person_id="valid-person",
        requester_account_mode="confirmed_binding",
        custom_fields={
            "request_context": "authenticated_requester_workspace",
            "requester_account_mode": "confirmed_binding",
            "ticket_context": _web_ticket_context(
                creator_person_id="valid-person",
                affected_person_id="valid-person",
                target_device_id="web-cabinet-valid-after-malformed-device",
                source="creator_primary_agent",
                requester_context={"account": {"account_mode": "confirmed_binding"}},
            ),
        },
        created_at=None,
    )
    profile_completion_port = _ProfileCompletionPort()

    result = await check_web_cabinet(
        _WebCabinetCheckSession([invalid_ticket, valid_ticket]),
        registry_port=profile_completion_port,
    )

    invalid_event = next(
        event
        for event in result.events
        if event.ticket_id == invalid_ticket.ticket_id
        and event.event_type == "profile_completion_registry_invalid"
    )
    assert malformed_ref not in json.dumps(invalid_event.evidence, sort_keys=True)
    assert profile_completion_port.calls == [("observer.web_cabinet", "valid-person")]
    assert any(
        event.ticket_id == valid_ticket.ticket_id
        and event.event_type == "profile_incomplete_normal_ticket_created"
        for event in result.events
    )


@pytest.mark.asyncio
async def test_web_cabinet_integrity_recomputes_profile_completion_when_ticket_lacks_snapshot(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    person_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())
    context = _web_ticket_context(
        creator_person_id=person_id,
        affected_person_id=person_id,
        target_device_id=device_id,
        source="creator_primary_agent",
        requester_context={"account": {"account_mode": "confirmed_binding"}},
    )

    async with session_maker() as session:
        session.add(
            RegistryPerson(
                person_id=person_id,
                display_name="Incomplete Profile Owner",
                full_name="Incomplete Profile Owner",
                email="incomplete-profile-owner@example.test",
                department_id=None,
                location_id=None,
                phone=None,
                source="test",
                status="active",
            )
        )
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id=device_id,
                title="Profile gate bypass without saved snapshot",
                description="Observer should recompute profile completion when ticket lacks cached evidence.",
                status="new",
                requester_id="incomplete-profile-owner@example.test",
                requester_person_id=person_id,
                requester_account_mode="confirmed_binding",
                custom_fields={
                    "request_context": "authenticated_requester_workspace",
                    "requester_account_mode": "confirmed_binding",
                    "ticket_context": context,
                    "created_on_behalf": False,
                    "creator_person_id": person_id,
                    "affected_person_id": person_id,
                    "target_device_id": device_id,
                    "diagnostic_target_source": "creator_primary_agent",
                },
            )
        )
        await _write_ticket_create_trace(session, ticket_id=ticket_id, device_id=device_id, person_id=person_id)
        await session.commit()

    async with session_maker() as session:
        await ObserverIntegrityService(session).run_scan(run_id="phase-d-web-cabinet-profile-recompute")
        await session.commit()

        event = await session.scalar(
            sa.select(ObserverIntegrityEvent).where(
                ObserverIntegrityEvent.ticket_id == ticket_id,
                ObserverIntegrityEvent.event_type == "profile_incomplete_normal_ticket_created",
            )
        )

    assert event is not None
    assert event.severity == "high"
    assert event.evidence_json["profile_completion_source"] == "registry_recomputed"
    assert set(event.evidence_json["missing_field_keys"]) >= {"department_id", "location_id", "phone"}


@pytest.mark.asyncio
async def test_requester_profile_preview_and_create_write_web_observer_events(test_client, test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    suffix = uuid.uuid4().hex[:8]

    blocked_request_id = f"phase-d-profile-{suffix}"
    blocked = await test_client.post(
        "/api/web/requester/tickets",
        headers=_headers(
            f"{TEST_UI_USER_PREFIX}observer-profile-blocked-{suffix}@example.test",
            request_id=blocked_request_id,
        ),
        json={"title": "Blocked", "description": "Profile is not complete yet"},
    )
    blocked_payload = await blocked.json()
    assert blocked.status == 403, blocked_payload
    assert blocked_payload["error_code"] == "REQUESTER_PROFILE_INCOMPLETE"

    login = f"observer-web-create-{suffix}@example.test"
    async with session_maker() as session:
        person = await _seed_completed_person_for_login(session, login=login)
        await session.commit()

    preview_request_id = f"phase-d-preview-{suffix}"
    preview = await test_client.post(
        "/api/web/requester/tickets/preview",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}", request_id=preview_request_id),
        json={"description": "Preview without catalog selection"},
    )
    preview_payload = await preview.json()
    assert preview.status == 200, preview_payload
    assert preview_payload["data"]["ok"] is True

    create = await test_client.post(
        "/api/web/requester/tickets",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}", request_id=f"phase-d-create-{suffix}"),
        json={"title": "Observer create", "description": "Create should be traced"},
    )
    create_payload = await create.json()
    assert create.status == 200, create_payload
    ticket_id = create_payload["data"]["ticket_id"]

    async with session_maker() as session:
        profile_traces = await ObserverOverlayService(session).search_traces(
            TraceOverlayFilters(
                root_kind="requester_web",
                source="requester_profile",
                event_type="profile_incomplete_blocked",
                error_code="REQUESTER_PROFILE_INCOMPLETE",
                query=blocked_request_id,
            ),
            limit=10,
        )
        preview_traces = await ObserverOverlayService(session).search_traces(
            TraceOverlayFilters(
                root_kind="requester_web",
                source="requester_ticket_preview",
                event_type="ticket_preview_succeeded",
                person_id=person.person_id,
                query=preview_request_id,
            ),
            limit=10,
        )
        create_traces = await ObserverOverlayService(session).search_traces(
            TraceOverlayFilters(
                root_kind="requester_web",
                source="requester_ticket_create",
                event_type="ticket_create_succeeded",
                ticket_id=ticket_id,
                person_id=person.person_id,
            ),
            limit=10,
        )

    assert profile_traces
    assert preview_traces
    assert create_traces


@pytest.mark.asyncio
async def test_web_requester_create_missing_diagnostic_target_writes_observer_event(test_client, test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    suffix = uuid.uuid4().hex[:8]
    login = f"observer-target-missing-{suffix}@example.test"
    request_id = f"phase-d-target-missing-{suffix}"

    async with session_maker() as session:
        person = await _seed_completed_person_for_login(session, login=login)
        await session.commit()

    created = await test_client.post(
        "/api/web/requester/tickets",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}", request_id=request_id),
        json={
            "title": "Missing target observer",
            "description": "Create without a primary agent should be observable",
            "token": "raw-target-token",
        },
    )
    created_payload = await created.json()
    assert created.status == 200, created_payload
    ticket_id = created_payload["data"]["ticket_id"]

    async with session_maker() as session:
        traces = await ObserverOverlayService(session).search_traces(
            TraceOverlayFilters(
                root_kind="requester_web",
                source="requester_ticket_create",
                event_type="diagnostic_target_missing",
                ticket_id=ticket_id,
                person_id=person.person_id,
                query=request_id,
            ),
            limit=10,
        )
        assert len(traces) == 1
        ticket = await session.get(Ticket, ticket_id)
        trace = await session.get(ObserverTrace, traces[0]["trace_id"])
        span = (
            await session.execute(sa.select(ObserverSpan).where(ObserverSpan.trace_id == traces[0]["trace_id"]))
        ).scalar_one()

    assert ticket is not None
    custom_fields = ticket.custom_fields or {}
    assert custom_fields["diagnostic_target_source"] == "no_primary_agent"
    assert trace is not None
    assert trace.status == "failed"
    assert trace.device_id is None
    assert trace.attrs_json["source"] == "requester_ticket_create"
    assert trace.attrs_json["event_type"] == "diagnostic_target_missing"
    assert trace.attrs_json["error_code"] == "DIAGNOSTIC_TARGET_MISSING"
    assert span.attrs_json["payload"] == {
        "diagnostic_target_source": "no_primary_agent",
        "agent_status": "missing",
        "reason_code": "primary_device_missing",
        "created_on_behalf": False,
        "has_dispatch_device": False,
        "manual_triage": False,
        "diagnostics_autorun_suppressed": False,
    }
    serialized = json.dumps({"trace": trace.attrs_json, "span": span.attrs_json}, sort_keys=True)
    assert login not in serialized
    assert "raw-target-token" not in serialized


@pytest.mark.asyncio
async def test_web_form_runtime_preview_and_create_write_observer_events(test_client, test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    suffix_seed = uuid.uuid4().hex
    # Keep an alphabetic separator inside the generated form key: an all-digit
    # UUID fragment is intentionally redacted as phone-like observer evidence.
    suffix = f"{suffix_seed[:4]}x{suffix_seed[4:8]}"
    login = f"observer-form-runtime-{suffix}@example.test"
    device_id = str(uuid.uuid4())
    service_code = f"observer_runtime_{suffix}"
    template_code = f"observer_runtime_form_{suffix}"
    preview_request_id = f"phase-d-form-runtime-preview-{suffix}"
    create_request_id = f"phase-d-form-runtime-create-{suffix}"
    raw_summary = f"raw observer form value {suffix}"

    async with session_maker() as session:
        queue = TicketQueue(code=f"observer_runtime_queue_{suffix}", name="Observer runtime queue", is_active=True)
        fallback_queue = TicketQueue(
            code=f"observer_runtime_fallback_{suffix}",
            name="Observer runtime fallback",
            is_active=True,
        )
        session.add_all([_device(device_id, "observer-form-runtime-device"), queue, fallback_queue])
        await session.flush()
        person = await _seed_completed_person_for_login(session, login=login)
        await session.flush()
        await RegistrationService(session).bind_person_to_device(
            device_id=device_id,
            person_id=person.person_id,
            relationship_type="primary_user",
            replace_existing=False,
            reviewed_by="seed-admin",
            reason="observer form runtime seed",
        )
        forms_repo = TicketFormPacksRepo(session)
        await forms_repo.upsert_pack(
            pack_key="request_forms",
            version=f"observer-runtime-{suffix}",
            schema_json={
                "pack_key": "request_forms",
                "version": f"observer-runtime-{suffix}",
                "forms": [
                    {
                        "key": template_code,
                        "request_template_key": template_code,
                        "title": "Observer runtime incident",
                        "request_kind": "incident",
                        "ticket_type": "incident",
                        "fields": [
                            {"key": "summary", "label": "Summary", "type": "text", "required": True},
                            {
                                "key": "impact_scope",
                                "label": "Impact",
                                "type": "select",
                                "required": True,
                                "options": [{"value": "company", "label": "Company"}],
                            },
                            {
                                "key": "work_continuity",
                                "label": "Continuity",
                                "type": "select",
                                "required": True,
                                "options": [{"value": "blocked", "label": "Blocked"}],
                            },
                        ],
                        "field_roles": {
                            "impact_scope": ["priority_impact"],
                            "work_continuity": ["priority_urgency"],
                        },
                        "priority_policy": {
                            "impact_field": "impact_scope",
                            "urgency_field": "work_continuity",
                            "importance_field": "business_importance",
                            "modifier_fields": {},
                        },
                        "routing_policy": {
                            "rules": [
                                {
                                    "code": f"observer_runtime_rule_{suffix}",
                                    "priority_order": 5,
                                    "when": {
                                        "field": "request_form_data.impact_scope",
                                        "op": "eq",
                                        "value": "company",
                                    },
                                    "then": {"queue_id": queue.id},
                                }
                            ],
                            "fallback": {"queue_id": fallback_queue.id},
                        },
                        "sla_policy": {
                            "code": f"observer_runtime_sla_{suffix}",
                            "targets": {
                                "first_response": {"P1": "15m"},
                                "resolution": {"P1": "4h"},
                            },
                        },
                    }
                ],
            },
            created_by="test",
        )
        await forms_repo.set_preferred(
            pack_key="request_forms",
            version=f"observer-runtime-{suffix}",
            updated_by="test",
        )
        session.add(
            RequestTemplate(
                template_code=template_code,
                version="1",
                public_title="Observer runtime incident",
                ticket_type="incident",
                config_json={},
                is_active=True,
                published_at=datetime.now(timezone.utc),
            )
        )
        repo = ServiceCatalogRepo(session)
        await repo.upsert_service_draft(
            {
                "code": service_code,
                "public_title": "Observer runtime service",
                "short_description": "Observer runtime support",
                "visibility": "public",
                "owner_queue_id": queue.id,
                "default_queue_id": fallback_queue.id,
                "business_criticality": "high",
                "reporting_category": "observer_runtime",
            },
            actor_id="test",
            actor_role="admin",
        )
        offering = await repo.upsert_offering_draft(
            {
                "service_code": service_code,
                "code": "runtime_incident",
                "public_title": "Runtime incident",
                "short_description": "Runtime policy incident",
                "request_type": "incident",
                "request_template_key": template_code,
                "visibility": "public",
                "reporting_category": "observer_runtime_incidents",
            },
            actor_id="test",
            actor_role="admin",
        )
        await repo.publish_service(service_code, actor_id="test", actor_role="admin")
        await repo.publish_offering(offering["full_code"], actor_id="test", actor_role="admin")
        await session.commit()

    form_payload = {
        "summary": raw_summary,
        "impact_scope": "company",
        "work_continuity": "blocked",
    }
    preview = await test_client.post(
        "/api/web/requester/tickets/preview",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}", request_id=preview_request_id),
        json={
            "device_id": device_id,
            "service_code": service_code,
            "offering_code": "runtime_incident",
            "request_template_key": template_code,
            "form_key": template_code,
            "form_payload": form_payload,
            "description": "Preview runtime policy",
        },
    )
    preview_payload = await preview.json()
    assert preview.status == 200, preview_payload
    assert preview_payload["data"]["ok"] is True

    created = await test_client.post(
        "/api/web/requester/tickets",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}", request_id=create_request_id),
        json={
            "device_id": device_id,
            "title": "Observer runtime ticket",
            "description": "Create runtime policy",
            "service_code": service_code,
            "offering_code": "runtime_incident",
            "request_template_key": template_code,
            "form_key": template_code,
            "form_payload": form_payload,
            "ticket_type": "incident",
        },
    )
    create_payload = await created.json()
    assert created.status == 200, create_payload
    ticket_id = create_payload["data"]["ticket_id"]

    async with session_maker() as session:
        preview_traces = await ObserverOverlayService(session).search_traces(
            TraceOverlayFilters(
                root_kind="requester_web",
                source="web_form_runtime",
                route="/api/web/requester/tickets/preview",
                event_type="form_runtime_preview_succeeded",
                person_id=person.person_id,
                query=preview_request_id,
            ),
            limit=10,
        )
        create_traces = await ObserverOverlayService(session).search_traces(
            TraceOverlayFilters(
                root_kind="requester_web",
                source="web_form_runtime",
                route="/api/web/requester/tickets",
                event_type="form_runtime_create_succeeded",
                ticket_id=ticket_id,
                person_id=person.person_id,
            ),
            limit=10,
        )
        assert len(preview_traces) == 1
        assert len(create_traces) == 1
        preview_span = (
            await session.execute(sa.select(ObserverSpan).where(ObserverSpan.trace_id == preview_traces[0]["trace_id"]))
        ).scalar_one()
        create_span = (
            await session.execute(sa.select(ObserverSpan).where(ObserverSpan.trace_id == create_traces[0]["trace_id"]))
        ).scalar_one()

    preview_runtime = preview_span.attrs_json["payload"]
    assert preview_runtime["stage"] == "preview"
    assert preview_runtime["form_key"] == template_code
    assert preview_runtime["has_catalog_selection"] is True
    assert preview_runtime["form_payload_present"] is True

    create_runtime = create_span.attrs_json["payload"]
    assert create_runtime["stage"] == "create"
    assert create_runtime["form_pack_version"] == f"observer-runtime-{suffix}"
    assert create_runtime["resolved_from"] == "legacy_pack"
    assert create_runtime["resolved_form_schema_version"] == f"observer-runtime-{suffix}"
    assert create_runtime["profile_schema_version"]
    assert create_runtime["priority_class"] == "P0"
    assert create_runtime["priority_source"] == "system"
    assert create_runtime["routing_source"] == "request_template.routing_policy"
    assert create_runtime["queue_resolved"] is True
    assert create_runtime["sla_started"] is True
    assert create_runtime["sla_due_present"] is True

    serialized = json.dumps(
        {"preview": preview_span.attrs_json, "create": create_span.attrs_json},
        sort_keys=True,
        ensure_ascii=False,
    )
    assert raw_summary not in serialized


@pytest.mark.asyncio
async def test_web_ticket_create_discards_retired_knowledge_attempts_without_local_observer_write(
    test_client,
    test_engine,
) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    suffix = uuid.uuid4().hex[:8]
    login = f"observer-knowledge-attempt-{suffix}@example.test"
    request_id = f"phase-d-knowledge-attempt-{suffix}"
    raw_query = f"raw attempt query marker {suffix}"
    raw_item_id = f"kb-raw-attempt-{suffix}"
    raw_version_id = f"kb-raw-version-{suffix}"

    async with session_maker() as session:
        person = await _seed_completed_person_for_login(session, login=login)
        await session.commit()

    created = await test_client.post(
        "/api/web/requester/tickets",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}", request_id=request_id),
        json={
            "title": "Knowledge attempt observer guard",
            "description": "Create after knowledge attempt",
            "token": "raw-attempt-token",
            "knowledge_attempts": [
                {
                    "item_id": raw_item_id,
                    "version_id": raw_version_id,
                    "result": "not_helpful",
                    "surface": "support_workspace",
                    "visibility_scope": "affected_context",
                    "audience_scope": "affected_context",
                    "timestamp": "2026-06-08T08:00:00Z",
                    "query": raw_query,
                    "email": login,
                }
            ],
        },
    )
    payload = await created.json()
    assert created.status == 200, payload
    ticket_id = payload["data"]["ticket_id"]

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        traces = await ObserverOverlayService(session).search_traces(
            TraceOverlayFilters(
                root_kind="requester_web",
                source="requester_knowledge",
                route="/api/web/requester/tickets",
                event_type="knowledge_attempt_guard_succeeded",
                ticket_id=ticket_id,
                person_id=person.person_id,
                query=request_id,
            ),
            limit=10,
        )

    assert ticket is not None
    assert traces == []
    serialized = json.dumps(ticket.custom_fields, sort_keys=True)
    assert "knowledge_attempts" not in ticket.custom_fields
    assert raw_query not in serialized
    assert raw_item_id not in serialized
    assert raw_version_id not in serialized
    assert "raw-attempt-token" not in serialized


@pytest.mark.asyncio
async def test_web_requester_chat_message_writes_observer_event(test_client, test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    suffix = uuid.uuid4().hex[:8]
    login = f"observer-chat-{suffix}@example.test"
    create_request_id = f"phase-d-chat-create-{suffix}"
    message_request_id = f"phase-d-chat-message-{suffix}"
    raw_message = f"raw requester chat text {suffix}"
    raw_metadata = f"raw requester metadata {suffix}"

    async with session_maker() as session:
        person = await _seed_completed_person_for_login(session, login=login)
        await session.commit()

    created = await test_client.post(
        "/api/web/requester/tickets",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}", request_id=create_request_id),
        json={"title": "Observer chat ticket", "description": "Create ticket before chat"},
    )
    created_payload = await created.json()
    assert created.status == 200, created_payload
    ticket_id = created_payload["data"]["ticket_id"]

    message = await test_client.post(
        f"/api/web/requester/tickets/{ticket_id}/message",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}", request_id=message_request_id),
        json={
            "text": raw_message,
            "metadata": {"raw_note": raw_metadata, "token": "raw-chat-token"},
        },
    )
    message_payload = await message.json()
    assert message.status == 200, message_payload
    assert message_payload["data"]["message_id"]

    async with session_maker() as session:
        traces = await ObserverOverlayService(session).search_traces(
            TraceOverlayFilters(
                root_kind="requester_web",
                source="requester_chat",
                route=f"/api/web/requester/tickets/{ticket_id}/message",
                event_type="chat_message_sent",
                ticket_id=ticket_id,
                person_id=person.person_id,
                query=message_request_id,
            ),
            limit=10,
        )
        assert len(traces) == 1
        trace = await session.get(ObserverTrace, traces[0]["trace_id"])
        span = (
            await session.execute(sa.select(ObserverSpan).where(ObserverSpan.trace_id == traces[0]["trace_id"]))
        ).scalar_one()

    assert trace is not None
    assert trace.status == "succeeded"
    assert trace.ticket_id == ticket_id
    assert trace.attrs_json["source"] == "requester_chat"
    assert trace.attrs_json["event_type"] == "chat_message_sent"
    assert trace.attrs_json["person_id"] == person.person_id
    assert span.attrs_json["method"] == "POST"
    assert span.attrs_json["payload"] == {
        "message_present": True,
        "attachment_count": 0,
        "visibility": "public",
        "status_transitioned": False,
    }
    serialized = json.dumps({"trace": trace.attrs_json, "span": span.attrs_json}, sort_keys=True)
    assert raw_message not in serialized
    assert raw_metadata not in serialized
    assert login not in serialized
    assert "raw-chat-token" not in serialized


@pytest.mark.asyncio
async def test_web_requester_closure_confirmed_writes_observer_event(test_client, test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    suffix = uuid.uuid4().hex[:8]
    login = f"observer-closure-{suffix}@example.test"
    create_request_id = f"phase-d-closure-create-{suffix}"
    close_request_id = f"phase-d-closure-close-{suffix}"
    raw_reason = f"raw closure reason {suffix}"

    async with session_maker() as session:
        person = await _seed_completed_person_for_login(session, login=login)
        await session.commit()

    created = await test_client.post(
        "/api/web/requester/tickets",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}", request_id=create_request_id),
        json={"title": "Observer closure ticket", "description": "Create ticket before closure"},
    )
    created_payload = await created.json()
    assert created.status == 200, created_payload
    ticket_id = created_payload["data"]["ticket_id"]

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        assert ticket is not None
        custom_fields = dict(ticket.custom_fields or {})
        custom_fields["resolution_confirmation"] = {"pending": True, "request_id": str(uuid.uuid4())}
        custom_fields["resolution_confirmation_pending"] = True
        ticket.status = "resolved"
        ticket.resolved_at = datetime.now(timezone.utc)
        ticket.custom_fields = custom_fields
        await session.commit()

    closed = await test_client.post(
        f"/api/web/requester/tickets/{ticket_id}/close",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}", request_id=close_request_id),
        json={"reason": raw_reason, "token": "raw-closure-token"},
    )
    closed_payload = await closed.json()
    assert closed.status == 200, closed_payload
    assert closed_payload["data"]["ticket"]["status"] == "closed"

    async with session_maker() as session:
        traces = await ObserverOverlayService(session).search_traces(
            TraceOverlayFilters(
                root_kind="requester_web",
                source="requester_closure",
                route=f"/api/web/requester/tickets/{ticket_id}/close",
                event_type="closure_confirmed",
                ticket_id=ticket_id,
                person_id=person.person_id,
                query=close_request_id,
            ),
            limit=10,
        )
        assert len(traces) == 1
        trace = await session.get(ObserverTrace, traces[0]["trace_id"])
        span = (
            await session.execute(sa.select(ObserverSpan).where(ObserverSpan.trace_id == traces[0]["trace_id"]))
        ).scalar_one()

    assert trace is not None
    assert trace.status == "succeeded"
    assert trace.ticket_id == ticket_id
    assert trace.attrs_json["source"] == "requester_closure"
    assert trace.attrs_json["event_type"] == "closure_confirmed"
    assert trace.attrs_json["person_id"] == person.person_id
    assert span.attrs_json["method"] == "POST"
    assert span.attrs_json["payload"] == {
        "from_status": "resolved",
        "to_status": "closed",
        "reason_present": True,
        "confirmation_pending_cleared": True,
    }
    serialized = json.dumps({"trace": trace.attrs_json, "span": span.attrs_json}, sort_keys=True)
    assert raw_reason not in serialized
    assert login not in serialized
    assert "raw-closure-token" not in serialized


@pytest.mark.asyncio
async def test_web_requester_feedback_writes_closure_observer_event(test_client, test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    suffix = uuid.uuid4().hex[:8]
    login = f"observer-feedback-{suffix}@example.test"
    create_request_id = f"phase-d-feedback-create-{suffix}"
    feedback_request_id = f"phase-d-feedback-submit-{suffix}"
    raw_comment = f"raw feedback comment {suffix}"
    raw_metadata = f"raw feedback metadata {suffix}"

    async with session_maker() as session:
        person = await _seed_completed_person_for_login(session, login=login)
        await session.commit()

    created = await test_client.post(
        "/api/web/requester/tickets",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}", request_id=create_request_id),
        json={"title": "Observer feedback ticket", "description": "Create ticket before feedback"},
    )
    created_payload = await created.json()
    assert created.status == 200, created_payload
    ticket_id = created_payload["data"]["ticket_id"]

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        assert ticket is not None
        ticket.status = "resolved"
        ticket.resolved_at = datetime.now(timezone.utc)
        await session.commit()

    feedback = await test_client.post(
        f"/api/web/requester/tickets/{ticket_id}/feedback",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}", request_id=feedback_request_id),
        json={
            "rating": 2,
            "problem_resolved": False,
            "resolution_confirmed": False,
            "reason_codes": ["not_resolved"],
            "comment": raw_comment,
            "metadata": {"raw_note": raw_metadata, "token": "raw-feedback-token"},
        },
    )
    feedback_payload = await feedback.json()
    assert feedback.status == 200, feedback_payload
    assert feedback_payload["data"]["feedback_id"]
    assert feedback_payload["data"]["reopen_available"] is True

    async with session_maker() as session:
        traces = await ObserverOverlayService(session).search_traces(
            TraceOverlayFilters(
                root_kind="requester_web",
                source="requester_closure",
                route=f"/api/web/requester/tickets/{ticket_id}/feedback",
                event_type="feedback_submitted",
                ticket_id=ticket_id,
                person_id=person.person_id,
                query=feedback_request_id,
            ),
            limit=10,
        )
        assert len(traces) == 1
        trace = await session.get(ObserverTrace, traces[0]["trace_id"])
        span = (
            await session.execute(sa.select(ObserverSpan).where(ObserverSpan.trace_id == traces[0]["trace_id"]))
        ).scalar_one()

    assert trace is not None
    assert trace.status == "succeeded"
    assert trace.ticket_id == ticket_id
    assert trace.attrs_json["source"] == "requester_closure"
    assert trace.attrs_json["event_type"] == "feedback_submitted"
    assert trace.attrs_json["person_id"] == person.person_id
    assert span.attrs_json["method"] == "POST"
    assert span.attrs_json["payload"] == {
        "rating_present": True,
        "problem_resolved": False,
        "resolution_confirmed": False,
        "reason_code_count": 1,
        "comment_present": True,
        "metadata_present": True,
        "reopen_available": True,
    }
    serialized = json.dumps({"trace": trace.attrs_json, "span": span.attrs_json}, sort_keys=True)
    assert raw_comment not in serialized
    assert raw_metadata not in serialized
    assert login not in serialized
    assert "raw-feedback-token" not in serialized


@pytest.mark.asyncio
async def test_web_requester_reopen_writes_closure_observer_event(test_client, test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    suffix = uuid.uuid4().hex[:8]
    login = f"observer-reopen-{suffix}@example.test"
    create_request_id = f"phase-d-reopen-create-{suffix}"
    feedback_request_id = f"phase-d-reopen-feedback-{suffix}"
    reopen_request_id = f"phase-d-reopen-ticket-{suffix}"
    raw_comment = f"raw reopen feedback {suffix}"
    raw_reason = f"raw reopen reason {suffix}"
    raw_knowledge_item_id = f"raw-knowledge-item-{suffix}"

    async with session_maker() as session:
        person = await _seed_completed_person_for_login(session, login=login)
        await session.commit()

    created = await test_client.post(
        "/api/web/requester/tickets",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}", request_id=create_request_id),
        json={"title": "Observer reopen ticket", "description": "Create ticket before reopen"},
    )
    created_payload = await created.json()
    assert created.status == 200, created_payload
    ticket_id = created_payload["data"]["ticket_id"]

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        assert ticket is not None
        ticket.status = "resolved"
        ticket.resolved_at = datetime.now(timezone.utc)
        await session.commit()

    feedback = await test_client.post(
        f"/api/web/requester/tickets/{ticket_id}/feedback",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}", request_id=feedback_request_id),
        json={
            "rating": 1,
            "problem_resolved": False,
            "resolution_confirmed": False,
            "reason_codes": ["knowledge_article_failed"],
            "comment": raw_comment,
        },
    )
    feedback_payload = await feedback.json()
    assert feedback.status == 200, feedback_payload
    feedback_id = feedback_payload["data"]["feedback_id"]

    reopened = await test_client.post(
        f"/api/web/requester/tickets/{ticket_id}/reopen",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}", request_id=reopen_request_id),
        json={
            "reason_code": "not_resolved",
            "reason_comment": raw_reason,
            "linked_feedback_id": feedback_id,
            "linked_knowledge_item_id": raw_knowledge_item_id,
        },
    )
    reopened_payload = await reopened.json()
    assert reopened.status == 200, reopened_payload
    assert reopened_payload["data"]["ticket_status"] == "in_progress"

    async with session_maker() as session:
        traces = await ObserverOverlayService(session).search_traces(
            TraceOverlayFilters(
                root_kind="requester_web",
                source="requester_closure",
                route=f"/api/web/requester/tickets/{ticket_id}/reopen",
                event_type="ticket_reopened",
                ticket_id=ticket_id,
                person_id=person.person_id,
                query=reopen_request_id,
            ),
            limit=10,
        )
        assert len(traces) == 1
        trace = await session.get(ObserverTrace, traces[0]["trace_id"])
        span = (
            await session.execute(sa.select(ObserverSpan).where(ObserverSpan.trace_id == traces[0]["trace_id"]))
        ).scalar_one()

    assert trace is not None
    assert trace.status == "succeeded"
    assert trace.ticket_id == ticket_id
    assert trace.attrs_json["source"] == "requester_closure"
    assert trace.attrs_json["event_type"] == "ticket_reopened"
    assert trace.attrs_json["person_id"] == person.person_id
    assert span.attrs_json["method"] == "POST"
    assert span.attrs_json["payload"] == {
        "from_status": "resolved",
        "to_status": "in_progress",
        "reason_code_present": True,
        "reason_comment_present": True,
        "linked_feedback_present": True,
        "linked_knowledge_item_present": True,
    }
    serialized = json.dumps({"trace": trace.attrs_json, "span": span.attrs_json}, sort_keys=True)
    assert raw_comment not in serialized
    assert raw_reason not in serialized
    assert feedback_id not in serialized
    assert raw_knowledge_item_id not in serialized
    assert login not in serialized


@pytest.mark.asyncio
async def test_web_session_login_writes_web_session_observer_event(
    test_client,
    test_engine,
    monkeypatch,
) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    login = f"observer-session-{uuid.uuid4().hex[:8]}@example.test"
    request_id = f"phase-d-login-{uuid.uuid4().hex[:8]}"

    @asynccontextmanager
    async def test_get_session():
        async with session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def fake_authenticate(_self, candidate_login: str, password: str):
        assert candidate_login == login
        assert password == "VeryStrong123!"
        return True, "user"

    async def fake_generate_ui_token(_self, user_login: str, actor_role: str, expires_hours: int = 24):
        assert user_login == login
        assert actor_role == "user"
        assert expires_hours == 24
        return f"{TEST_UI_USER_PREFIX}{login}"

    monkeypatch.setattr(session_handlers_module, "get_session", test_get_session)
    monkeypatch.setattr(session_handlers_module.AuthService, "authenticate", fake_authenticate)
    monkeypatch.setattr(session_handlers_module.AuthService, "generate_ui_token", fake_generate_ui_token)

    response = await test_client.post(
        "/api/web/session/login",
        headers={"X-Request-ID": request_id},
        json={"login": login, "password": "VeryStrong123!"},
    )
    payload = await response.json()

    assert response.status == 200, payload

    async with session_maker() as session:
        traces = await ObserverOverlayService(session).search_traces(
            TraceOverlayFilters(
                root_kind="requester_web",
                source="web_session",
                route="/api/web/session/login",
                event_type="login_succeeded",
                query=request_id,
            ),
            limit=10,
        )
        assert len(traces) == 1
        trace = await session.get(ObserverTrace, traces[0]["trace_id"])
        span = (
            await session.execute(sa.select(ObserverSpan).where(ObserverSpan.trace_id == traces[0]["trace_id"]))
        ).scalar_one()

    assert trace is not None
    assert trace.status == "succeeded"
    assert trace.attrs_json["source"] == "web_session"
    assert trace.attrs_json["event_type"] == "login_succeeded"
    assert trace.attrs_json["actor_role"] == "user"
    assert span.attrs_json["route"] == "/api/web/session/login"
    assert span.attrs_json["method"] == "POST"
    serialized = json.dumps({"trace": trace.attrs_json, "span": span.attrs_json}, sort_keys=True)
    assert "VeryStrong123!" not in serialized
    assert login not in serialized


@pytest.mark.asyncio
async def test_web_session_register_writes_web_session_observer_event(
    test_client,
    test_engine,
    monkeypatch,
) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    login = f"observer-register-{uuid.uuid4().hex[:8]}@example.test"
    request_id = f"phase-d-register-{uuid.uuid4().hex[:8]}"

    @asynccontextmanager
    async def test_get_session():
        async with session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    monkeypatch.setattr(session_handlers_module.config_module, "WEB_SELF_REGISTRATION_ENABLED", True, raising=False)
    monkeypatch.setattr(session_handlers_module, "get_session", test_get_session)

    response = await test_client.post(
        "/api/web/session/register",
        headers={"X-Request-ID": request_id},
        json={
            "login": login,
            "password": "VeryStrong123!",
            "password_repeat": "VeryStrong123!",
        },
    )
    payload = await response.json()

    assert response.status == 201, payload

    async with session_maker() as session:
        traces = await ObserverOverlayService(session).search_traces(
            TraceOverlayFilters(
                root_kind="requester_web",
                source="web_session",
                route="/api/web/session/register",
                event_type="register_succeeded",
                query=request_id,
            ),
            limit=10,
        )
        assert len(traces) == 1
        trace = await session.get(ObserverTrace, traces[0]["trace_id"])
        span = (
            await session.execute(sa.select(ObserverSpan).where(ObserverSpan.trace_id == traces[0]["trace_id"]))
        ).scalar_one()

    assert trace is not None
    assert trace.status == "succeeded"
    assert trace.attrs_json["source"] == "web_session"
    assert trace.attrs_json["event_type"] == "register_succeeded"
    assert trace.attrs_json["actor_role"] == "user"
    assert span.attrs_json["route"] == "/api/web/session/register"
    assert span.attrs_json["method"] == "POST"
    assert span.attrs_json["payload"]["device_link_accepted"] is False
    serialized = json.dumps({"trace": trace.attrs_json, "span": span.attrs_json}, sort_keys=True)
    assert "VeryStrong123!" not in serialized
    assert login not in serialized


@pytest.mark.asyncio
async def test_web_session_logout_writes_web_session_observer_event(
    test_client,
    test_engine,
    monkeypatch,
) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    login = f"observer-logout-{uuid.uuid4().hex[:8]}@example.test"
    token = f"{TEST_UI_USER_PREFIX}{login}"
    request_id = f"phase-d-logout-{uuid.uuid4().hex[:8]}"
    revoked_tokens: list[str] = []

    @asynccontextmanager
    async def test_get_session():
        async with session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def fake_revoke_ui_token(_self, candidate_token: str) -> bool:
        revoked_tokens.append(candidate_token)
        return True

    monkeypatch.setattr(session_handlers_module, "get_session", test_get_session)
    monkeypatch.setattr(session_handlers_module.AuthService, "revoke_ui_token", fake_revoke_ui_token)

    response = await test_client.post(
        "/api/web/session/logout",
        headers=_headers(token, request_id=request_id),
    )
    payload = await response.json()

    assert response.status == 200, payload
    assert revoked_tokens == [token]

    async with session_maker() as session:
        traces = await ObserverOverlayService(session).search_traces(
            TraceOverlayFilters(
                root_kind="requester_web",
                source="web_session",
                route="/api/web/session/logout",
                event_type="logout_succeeded",
                query=request_id,
            ),
            limit=10,
        )
        assert len(traces) == 1
        trace = await session.get(ObserverTrace, traces[0]["trace_id"])
        span = (
            await session.execute(sa.select(ObserverSpan).where(ObserverSpan.trace_id == traces[0]["trace_id"]))
        ).scalar_one()

    assert trace is not None
    assert trace.status == "succeeded"
    assert trace.attrs_json["source"] == "web_session"
    assert trace.attrs_json["event_type"] == "logout_succeeded"
    assert trace.attrs_json["actor_role"] == "user"
    assert span.attrs_json["route"] == "/api/web/session/logout"
    assert span.attrs_json["method"] == "POST"
    assert span.attrs_json["payload"]["credential_seen"] is True
    assert span.attrs_json["payload"]["revoked"] is True
    serialized = json.dumps({"trace": trace.attrs_json, "span": span.attrs_json}, sort_keys=True)
    assert token not in serialized
    assert login not in serialized


@pytest.mark.asyncio
async def test_web_session_role_mismatch_writes_web_session_observer_event(
    test_client,
    test_engine,
    monkeypatch,
) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    login = f"observer-mismatch-{uuid.uuid4().hex[:8]}@example.test"
    request_id = f"phase-d-mismatch-{uuid.uuid4().hex[:8]}"

    @asynccontextmanager
    async def test_get_session():
        async with session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def fake_authenticate(_self, candidate_login: str, password: str):
        assert candidate_login == login
        assert password == "VeryStrong123!"
        return True, "user"

    monkeypatch.setattr(session_handlers_module, "get_session", test_get_session)
    monkeypatch.setattr(session_handlers_module.AuthService, "authenticate", fake_authenticate)

    response = await test_client.post(
        "/api/web/session/login",
        headers={"X-Request-ID": request_id},
        json={"login": login, "password": "VeryStrong123!", "expected_role": "admin"},
    )
    payload = await response.json()

    assert response.status == 403, payload
    assert payload["error_code"] == "ROLE_MISMATCH"

    async with session_maker() as session:
        traces = await ObserverOverlayService(session).search_traces(
            TraceOverlayFilters(
                root_kind="requester_web",
                source="web_session",
                route="/api/web/session/login",
                event_type="role_mismatch",
                error_code="ROLE_MISMATCH",
                query=request_id,
            ),
            limit=10,
        )
        assert len(traces) == 1
        trace = await session.get(ObserverTrace, traces[0]["trace_id"])
        span = (
            await session.execute(sa.select(ObserverSpan).where(ObserverSpan.trace_id == traces[0]["trace_id"]))
        ).scalar_one()

    assert trace is not None
    assert trace.status == "failed"
    assert trace.attrs_json["source"] == "web_session"
    assert trace.attrs_json["event_type"] == "role_mismatch"
    assert trace.attrs_json["actor_role"] == "user"
    assert span.status == "error"
    assert span.attrs_json["route"] == "/api/web/session/login"
    assert span.attrs_json["error_code"] == "ROLE_MISMATCH"
    assert span.attrs_json["payload"]["expected_role"] == "admin"
    assert span.attrs_json["payload"]["actual_role"] == "user"
    serialized = json.dumps({"trace": trace.attrs_json, "span": span.attrs_json}, sort_keys=True)
    assert "VeryStrong123!" not in serialized
    assert login not in serialized


@pytest.mark.asyncio
async def test_web_device_linking_admin_approve_reject_write_observer_events(
    test_client,
    test_engine,
) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    approve_device_id = str(uuid.uuid4())
    reject_device_id = str(uuid.uuid4())
    approve_request_id = f"phase-d-device-link-approve-{uuid.uuid4().hex[:8]}"
    reject_request_id = f"phase-d-device-link-reject-{uuid.uuid4().hex[:8]}"
    reject_reason = "wrong user"

    async with session_maker() as session:
        session.add_all([_device(approve_device_id), _device(reject_device_id)])
        service = RegistrationService(session)
        approve_claim = await service.submit_agent_profile_claim(
            device_id=approve_device_id,
            requester_id="observer-approve-owner",
            display_name="Observer Approve Owner",
            profile={
                "full_name": "Observer Approve Owner",
                "email": "observer-approve@example.test",
                "user_confirmed": True,
            },
        )
        reject_claim = await service.submit_agent_profile_claim(
            device_id=reject_device_id,
            requester_id="observer-reject-owner",
            display_name="Observer Reject Owner",
            profile={"full_name": "Observer Reject Owner", "email": "observer-reject@example.test"},
        )
        await session.commit()

    approve_claim_id = approve_claim["registration"]["claim_id"]
    reject_claim_id = reject_claim["registration"]["claim_id"]
    approve_person_id = approve_claim["person"]["person_id"]
    reject_person_id = reject_claim["person"]["person_id"]

    approved = await test_client.post(
        f"/api/web/admin/registry/registrations/{approve_claim_id}/approve",
        headers=_headers(TEST_UI_ADMIN_TOKEN, request_id=approve_request_id),
        json={},
    )
    approved_payload = await approved.json()
    rejected = await test_client.post(
        f"/api/web/admin/registry/registrations/{reject_claim_id}/reject",
        headers=_headers(TEST_UI_ADMIN_TOKEN, request_id=reject_request_id),
        json={"reason": reject_reason},
    )
    rejected_payload = await rejected.json()

    assert approved.status == 200, approved_payload
    assert approved_payload["data"]["registration"]["status"] == "approved"
    assert rejected.status == 200, rejected_payload
    assert rejected_payload["data"]["registration"]["status"] == "rejected"

    async with session_maker() as session:
        approve_traces = await ObserverOverlayService(session).search_traces(
            TraceOverlayFilters(
                root_kind="requester_web",
                source="device_linking",
                route="/api/web/admin/registry/registrations/{claim_id}/approve",
                device_id=approve_device_id,
                person_id=approve_person_id,
                event_type="device_link_request_approved",
                query=approve_request_id,
            ),
            limit=10,
        )
        reject_traces = await ObserverOverlayService(session).search_traces(
            TraceOverlayFilters(
                root_kind="requester_web",
                source="device_linking",
                route="/api/web/admin/registry/registrations/{claim_id}/reject",
                device_id=reject_device_id,
                person_id=reject_person_id,
                event_type="device_link_request_rejected",
                query=reject_request_id,
            ),
            limit=10,
        )
        assert len(approve_traces) == 1
        assert len(reject_traces) == 1
        approve_trace = await session.get(ObserverTrace, approve_traces[0]["trace_id"])
        reject_trace = await session.get(ObserverTrace, reject_traces[0]["trace_id"])
        approve_span = (
            await session.execute(sa.select(ObserverSpan).where(ObserverSpan.trace_id == approve_traces[0]["trace_id"]))
        ).scalar_one()
        reject_span = (
            await session.execute(sa.select(ObserverSpan).where(ObserverSpan.trace_id == reject_traces[0]["trace_id"]))
        ).scalar_one()

    assert approve_trace is not None
    assert approve_trace.status == "succeeded"
    assert approve_trace.device_id == approve_device_id
    assert approve_trace.attrs_json["event_type"] == "device_link_request_approved"
    assert approve_trace.attrs_json["actor_role"] == "admin"
    assert approve_span.attrs_json["route"] == "/api/web/admin/registry/registrations/{claim_id}/approve"
    assert approve_span.attrs_json["method"] == "POST"
    assert approve_span.attrs_json["payload"]["registration_status"] == "approved"
    assert approve_span.attrs_json["payload"]["binding_status"] == "active"
    assert approve_span.attrs_json["payload"]["relationship_type"] == "primary_user"

    assert reject_trace is not None
    assert reject_trace.status == "succeeded"
    assert reject_trace.device_id == reject_device_id
    assert reject_trace.attrs_json["event_type"] == "device_link_request_rejected"
    assert reject_trace.attrs_json["actor_role"] == "admin"
    assert reject_span.attrs_json["route"] == "/api/web/admin/registry/registrations/{claim_id}/reject"
    assert reject_span.attrs_json["method"] == "POST"
    assert reject_span.attrs_json["payload"]["registration_status"] == "rejected"
    assert reject_span.attrs_json["payload"]["reason_present"] is True

    serialized = json.dumps(
        {
            "approve_trace": approve_trace.attrs_json,
            "approve_span": approve_span.attrs_json,
            "reject_trace": reject_trace.attrs_json,
            "reject_span": reject_span.attrs_json,
        },
        sort_keys=True,
    )
    assert approve_claim_id not in serialized
    assert reject_claim_id not in serialized
    assert reject_reason not in serialized
    assert "observer-approve@example.test" not in serialized
    assert "observer-reject@example.test" not in serialized


@pytest.mark.asyncio
async def test_web_device_linking_transfer_owner_writes_observer_event(
    test_client,
    test_engine,
) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    request_id = f"phase-d-device-link-transfer-{uuid.uuid4().hex[:8]}"
    transfer_reason = "device handed to replacement owner"
    old_login = f"observer-transfer-old-{uuid.uuid4().hex[:8]}@example.test"
    new_login = f"observer-transfer-new-{uuid.uuid4().hex[:8]}@example.test"

    async with session_maker() as session:
        session.add(_device(device_id))
        old_person = await _seed_completed_person_for_login(session, login=old_login)
        new_person = await _seed_completed_person_for_login(session, login=new_login)
        await session.flush()
        first_binding = await RegistrationService(session).bind_person_to_device(
            device_id=device_id,
            person_id=old_person.person_id,
            relationship_type="primary_user",
            replace_existing=False,
            reviewed_by="seed-admin",
            reason="initial owner",
        )
        await session.commit()

    response = await test_client.post(
        f"/api/web/admin/registry/devices/{device_id}/transfer-owner",
        headers=_headers(TEST_UI_ADMIN_TOKEN, request_id=request_id),
        json={
            "new_person_id": new_person.person_id,
            "old_binding_action": "transferred",
            "reason": transfer_reason,
        },
    )
    payload = await response.json()

    assert response.status == 200, payload
    assert payload["data"]["operation"] == "transfer_owner"
    assert payload["data"]["binding"]["person_id"] == new_person.person_id
    assert payload["data"]["binding"]["status"] == "active"

    async with session_maker() as session:
        traces = await ObserverOverlayService(session).search_traces(
            TraceOverlayFilters(
                root_kind="requester_web",
                source="device_linking",
                route="/api/web/admin/registry/devices/{device_id}/transfer-owner",
                device_id=device_id,
                person_id=new_person.person_id,
                event_type="device_link_owner_transferred",
                query=request_id,
            ),
            limit=10,
        )
        assert len(traces) == 1
        trace = await session.get(ObserverTrace, traces[0]["trace_id"])
        span = (
            await session.execute(sa.select(ObserverSpan).where(ObserverSpan.trace_id == traces[0]["trace_id"]))
        ).scalar_one()

    assert trace is not None
    assert trace.status == "succeeded"
    assert trace.device_id == device_id
    assert trace.attrs_json["event_type"] == "device_link_owner_transferred"
    assert trace.attrs_json["actor_role"] == "admin"
    assert span.attrs_json["route"] == "/api/web/admin/registry/devices/{device_id}/transfer-owner"
    assert span.attrs_json["method"] == "POST"
    assert span.attrs_json["payload"]["operation"] == "transfer_owner"
    assert span.attrs_json["payload"]["new_binding_status"] == "active"
    assert span.attrs_json["payload"]["relationship_type"] == "primary_user"
    assert span.attrs_json["payload"]["old_binding_action"] == "transferred"
    assert span.attrs_json["payload"]["revoked_session_count"] == 0
    assert span.attrs_json["payload"]["reason_present"] is True

    serialized = json.dumps({"trace": trace.attrs_json, "span": span.attrs_json}, sort_keys=True)
    assert first_binding["binding"]["binding_id"] not in serialized
    assert payload["data"]["binding"]["binding_id"] not in serialized
    assert transfer_reason not in serialized
    assert old_login not in serialized
    assert new_login not in serialized


@pytest.mark.asyncio
async def test_web_registry_bind_person_writes_observer_event(
    test_client,
    test_engine,
) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    request_id = f"phase-d-registry-bind-person-{uuid.uuid4().hex[:8]}"
    bind_reason = "verified service desk request"
    login = f"observer-bind-person-{uuid.uuid4().hex[:8]}@example.test"

    async with session_maker() as session:
        session.add(_device(device_id))
        person = await _seed_completed_person_for_login(session, login=login)
        await session.commit()

    response = await test_client.post(
        f"/api/web/admin/registry/devices/{device_id}/bind-person",
        headers=_headers(TEST_UI_ADMIN_TOKEN, request_id=request_id),
        json={
            "person_id": person.person_id,
            "relationship_type": "primary_user",
            "replace_existing": False,
            "reason": bind_reason,
        },
    )
    payload = await response.json()

    assert response.status == 200, payload
    assert payload["data"]["binding"]["person_id"] == person.person_id
    assert payload["data"]["binding"]["status"] == "active"

    async with session_maker() as session:
        traces = await ObserverOverlayService(session).search_traces(
            TraceOverlayFilters(
                root_kind="requester_web",
                source="registry_binding",
                route="/api/web/admin/registry/devices/{device_id}/bind-person",
                device_id=device_id,
                person_id=person.person_id,
                event_type="registry_binding_created",
                query=request_id,
            ),
            limit=10,
        )
        assert len(traces) == 1
        trace = await session.get(ObserverTrace, traces[0]["trace_id"])
        span = (
            await session.execute(sa.select(ObserverSpan).where(ObserverSpan.trace_id == traces[0]["trace_id"]))
        ).scalar_one()

    assert trace is not None
    assert trace.status == "succeeded"
    assert trace.device_id == device_id
    assert trace.attrs_json["event_type"] == "registry_binding_created"
    assert trace.attrs_json["actor_role"] == "admin"
    assert span.attrs_json["route"] == "/api/web/admin/registry/devices/{device_id}/bind-person"
    assert span.attrs_json["method"] == "POST"
    assert span.attrs_json["payload"]["binding_status"] == "active"
    assert span.attrs_json["payload"]["relationship_type"] == "primary_user"
    assert span.attrs_json["payload"]["replace_existing"] is False
    assert span.attrs_json["payload"]["reason_present"] is True
    assert span.attrs_json["payload"]["reused_existing_binding"] is False

    serialized = json.dumps({"trace": trace.attrs_json, "span": span.attrs_json}, sort_keys=True)
    assert payload["data"]["binding"]["binding_id"] not in serialized
    assert bind_reason not in serialized
    assert login not in serialized


@pytest.mark.asyncio
async def test_web_registry_binding_revoke_writes_observer_event(
    test_client,
    test_engine,
) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    request_id = f"phase-d-registry-binding-revoke-{uuid.uuid4().hex[:8]}"
    revoke_reason = "device returned to inventory"
    login = f"observer-revoke-binding-{uuid.uuid4().hex[:8]}@example.test"

    async with session_maker() as session:
        session.add(_device(device_id))
        person = await _seed_completed_person_for_login(session, login=login)
        await session.flush()
        bound = await RegistrationService(session).bind_person_to_device(
            device_id=device_id,
            person_id=person.person_id,
            relationship_type="primary_user",
            replace_existing=False,
            reviewed_by="seed-admin",
            reason="initial owner",
        )
        await session.commit()

    binding_id = bound["binding"]["binding_id"]
    response = await test_client.post(
        f"/api/web/admin/registry/bindings/{binding_id}/revoke",
        headers=_headers(TEST_UI_ADMIN_TOKEN, request_id=request_id),
        json={"reason": revoke_reason},
    )
    payload = await response.json()

    assert response.status == 200, payload
    assert payload["data"]["binding"]["status"] == "revoked"

    async with session_maker() as session:
        traces = await ObserverOverlayService(session).search_traces(
            TraceOverlayFilters(
                root_kind="requester_web",
                source="registry_binding",
                route="/api/web/admin/registry/bindings/{binding_id}/revoke",
                device_id=device_id,
                person_id=person.person_id,
                event_type="registry_binding_revoked",
                query=request_id,
            ),
            limit=10,
        )
        assert len(traces) == 1
        trace = await session.get(ObserverTrace, traces[0]["trace_id"])
        span = (
            await session.execute(sa.select(ObserverSpan).where(ObserverSpan.trace_id == traces[0]["trace_id"]))
        ).scalar_one()

    assert trace is not None
    assert trace.status == "succeeded"
    assert trace.device_id == device_id
    assert trace.attrs_json["event_type"] == "registry_binding_revoked"
    assert trace.attrs_json["actor_role"] == "admin"
    assert span.attrs_json["route"] == "/api/web/admin/registry/bindings/{binding_id}/revoke"
    assert span.attrs_json["method"] == "POST"
    assert span.attrs_json["payload"]["binding_status"] == "revoked"
    assert span.attrs_json["payload"]["reason_present"] is True
    assert span.attrs_json["payload"]["revoked_session_count"] == 0
    assert span.attrs_json["payload"]["canceled_login_request_count"] == 0

    serialized = json.dumps({"trace": trace.attrs_json, "span": span.attrs_json}, sort_keys=True)
    assert binding_id not in serialized
    assert revoke_reason not in serialized
    assert login not in serialized


@pytest.mark.asyncio
async def test_web_registry_shared_and_responsible_bindings_write_observer_events(
    test_client,
    test_engine,
) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    shared_request_id = f"phase-d-registry-shared-{uuid.uuid4().hex[:8]}"
    responsible_request_id = f"phase-d-registry-responsible-{uuid.uuid4().hex[:8]}"
    shared_reason = "temporary shared workstation"
    responsible_reason = "asset responsible person"
    shared_login = f"observer-shared-{uuid.uuid4().hex[:8]}@example.test"
    responsible_login = f"observer-responsible-{uuid.uuid4().hex[:8]}@example.test"

    async with session_maker() as session:
        session.add(_device(device_id))
        shared_person = await _seed_completed_person_for_login(session, login=shared_login)
        responsible_person = await _seed_completed_person_for_login(session, login=responsible_login)
        await session.commit()

    shared_response = await test_client.post(
        f"/api/web/admin/registry/devices/{device_id}/shared-users",
        headers=_headers(TEST_UI_ADMIN_TOKEN, request_id=shared_request_id),
        json={"person_id": shared_person.person_id, "reason": shared_reason},
    )
    shared_payload = await shared_response.json()
    responsible_response = await test_client.post(
        f"/api/web/admin/registry/devices/{device_id}/responsible",
        headers=_headers(TEST_UI_ADMIN_TOKEN, request_id=responsible_request_id),
        json={"person_id": responsible_person.person_id, "replace_existing": True, "reason": responsible_reason},
    )
    responsible_payload = await responsible_response.json()

    assert shared_response.status == 200, shared_payload
    assert shared_payload["data"]["binding"]["relationship_type"] == "shared_user"
    assert responsible_response.status == 200, responsible_payload
    assert responsible_payload["data"]["binding"]["relationship_type"] == "responsible"

    async with session_maker() as session:
        shared_traces = await ObserverOverlayService(session).search_traces(
            TraceOverlayFilters(
                root_kind="requester_web",
                source="registry_binding",
                route="/api/web/admin/registry/devices/{device_id}/shared-users",
                device_id=device_id,
                person_id=shared_person.person_id,
                event_type="registry_binding_created",
                query=shared_request_id,
            ),
            limit=10,
        )
        responsible_traces = await ObserverOverlayService(session).search_traces(
            TraceOverlayFilters(
                root_kind="requester_web",
                source="registry_binding",
                route="/api/web/admin/registry/devices/{device_id}/responsible",
                device_id=device_id,
                person_id=responsible_person.person_id,
                event_type="registry_binding_created",
                query=responsible_request_id,
            ),
            limit=10,
        )
        assert len(shared_traces) == 1
        assert len(responsible_traces) == 1
        shared_trace = await session.get(ObserverTrace, shared_traces[0]["trace_id"])
        responsible_trace = await session.get(ObserverTrace, responsible_traces[0]["trace_id"])
        shared_span = (
            await session.execute(sa.select(ObserverSpan).where(ObserverSpan.trace_id == shared_traces[0]["trace_id"]))
        ).scalar_one()
        responsible_span = (
            await session.execute(
                sa.select(ObserverSpan).where(ObserverSpan.trace_id == responsible_traces[0]["trace_id"])
            )
        ).scalar_one()

    assert shared_trace is not None
    assert shared_trace.status == "succeeded"
    assert shared_trace.attrs_json["event_type"] == "registry_binding_created"
    assert shared_span.attrs_json["route"] == "/api/web/admin/registry/devices/{device_id}/shared-users"
    assert shared_span.attrs_json["payload"]["binding_status"] == "active"
    assert shared_span.attrs_json["payload"]["relationship_type"] == "shared_user"
    assert shared_span.attrs_json["payload"]["replace_existing"] is False
    assert shared_span.attrs_json["payload"]["reason_present"] is True

    assert responsible_trace is not None
    assert responsible_trace.status == "succeeded"
    assert responsible_trace.attrs_json["event_type"] == "registry_binding_created"
    assert responsible_span.attrs_json["route"] == "/api/web/admin/registry/devices/{device_id}/responsible"
    assert responsible_span.attrs_json["payload"]["binding_status"] == "active"
    assert responsible_span.attrs_json["payload"]["relationship_type"] == "responsible"
    assert responsible_span.attrs_json["payload"]["replace_existing"] is True
    assert responsible_span.attrs_json["payload"]["reason_present"] is True

    serialized = json.dumps(
        {
            "shared_trace": shared_trace.attrs_json,
            "shared_span": shared_span.attrs_json,
            "responsible_trace": responsible_trace.attrs_json,
            "responsible_span": responsible_span.attrs_json,
        },
        sort_keys=True,
    )
    assert shared_payload["data"]["binding"]["binding_id"] not in serialized
    assert responsible_payload["data"]["binding"]["binding_id"] not in serialized
    assert shared_reason not in serialized
    assert responsible_reason not in serialized
    assert shared_login not in serialized
    assert responsible_login not in serialized
