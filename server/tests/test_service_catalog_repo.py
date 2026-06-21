from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import ApprovalPolicy, RequestTemplate, TicketQueue
from app.repos.service_catalog_repo import ServiceCatalogRepo
from tickets.service_catalog_publication import ServiceCatalogPublicationService
from tickets.service_catalog_runtime import ServiceCatalogRuntimeResolver


pytestmark = pytest.mark.db_cleanup("tickets")

@pytest.mark.asyncio
async def test_service_catalog_repo_draft_publish_and_safe_catalog(test_engine) -> None:
    suffix = uuid.uuid4().hex[:8]
    service_code = f"workplace_{suffix}"
    offering_code = "laptop_broken"
    template_code = f"laptop_incident_{suffix}"
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        queue = TicketQueue(code=f"queue_{suffix}", name="Internal Workplace Support", is_active=True)
        session.add(queue)
        await session.flush()
        session.add(
            RequestTemplate(
                template_code=template_code,
                version="1",
                public_title="Laptop incident",
                ticket_type="incident",
                config_json={"no_sla": True},
                is_active=True,
                published_at=datetime.now(timezone.utc),
            )
        )
        repo = ServiceCatalogRepo(session)
        service = await repo.upsert_service_draft(
            {
                "code": service_code,
                "public_title": "Рабочее место",
                "short_description": "Ноутбук, ПК и периферия",
                "visibility": "public",
                "owner_queue_id": queue.id,
                "default_queue_id": queue.id,
                "business_criticality": "medium",
                "reporting_category": "end_user_computing",
            },
            actor_id="admin-test",
            actor_role="admin",
        )
        offering = await repo.upsert_offering_draft(
            {
                "service_code": service_code,
                "code": offering_code,
                "public_title": "Сломался ноутбук",
                "short_description": "Ноутбук не включается или работает нестабильно",
                "request_type": "incident",
                "request_template_key": template_code,
                "visibility": "public",
            },
            actor_id="admin-test",
            actor_role="admin",
        )

        service_validation = await ServiceCatalogPublicationService(session).validate_service(service_code)
        offering_validation = await ServiceCatalogPublicationService(session).validate_offering(offering["full_code"])
        assert service_validation["blocking"] is False
        assert offering_validation["blocking"] is False

        await repo.publish_service(service_code, actor_id="admin-test", actor_role="admin")
        await repo.publish_offering(offering["full_code"], actor_id="admin-test", actor_role="admin")
        await session.commit()

    async with session_maker() as session:
        catalog = await ServiceCatalogRuntimeResolver(session).current_catalog_for_requester()

    public_service = next(item for item in catalog["services"] if item["service_code"] == service["code"])
    public_offering = public_service["offerings"][0]
    assert public_offering["full_code"] == f"{service_code}.{offering_code}"
    assert public_offering["request_template_key"] == template_code
    assert "queue_id" not in public_offering
    assert "raw_policy_json" not in public_offering


@pytest.mark.asyncio
async def test_service_catalog_runtime_resolves_and_snapshots_catalog_fields(test_engine) -> None:
    suffix = uuid.uuid4().hex[:8]
    service_code = f"access_{suffix}"
    template_code = f"access_template_{suffix}"
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        queue = TicketQueue(code=f"queue_{suffix}", name="Access Support", is_active=True)
        session.add(queue)
        await session.flush()
        session.add(
            RequestTemplate(
                template_code=template_code,
                version="1",
                public_title="Access request",
                ticket_type="access_request",
                config_json={"no_sla": True},
                is_active=True,
                published_at=datetime.now(timezone.utc),
            )
        )
        repo = ServiceCatalogRepo(session)
        await repo.upsert_service_draft(
            {
                "code": service_code,
                "public_title": "Доступы",
                "short_description": "Права и учетные записи",
                "visibility": "public",
                "owner_queue_id": queue.id,
                "default_queue_id": queue.id,
                "support_group_code": "iam",
                "business_criticality": "high",
                "reporting_category": "identity_access",
            },
            actor_id="admin-test",
            actor_role="admin",
        )
        offering = await repo.upsert_offering_draft(
            {
                "service_code": service_code,
                "code": "new_account",
                "public_title": "Новая учетная запись",
                "short_description": "Создание учетной записи",
                "request_type": "access_request",
                "request_template_key": template_code,
                "visibility": "public",
                "reporting_category": "identity_onboarding",
            },
            actor_id="admin-test",
            actor_role="admin",
        )
        await repo.publish_service(service_code, actor_id="admin-test", actor_role="admin")
        await repo.publish_offering(offering["full_code"], actor_id="admin-test", actor_role="admin")
        await session.commit()

    async with session_maker() as session:
        resolver = ServiceCatalogRuntimeResolver(session)
        selection = await resolver.resolve_selection(
            service_code=service_code,
            offering_code="new_account",
            actor_role="requester",
            require_catalog=True,
        )
        submission = await resolver.apply_to_validated_submission(
            {"request_template_key": template_code, "template_context": {"key": template_code}},
            selection,
        )

    assert submission["catalog_fields"]["service_code"] == service_code
    assert submission["catalog_fields"]["offering_code"] == f"{service_code}.new_account"
    assert submission["catalog_fields"]["request_type"] == "access_request"
    snapshot = submission["template_context"]["service_catalog"]
    assert snapshot["service_code"] == service_code
    assert snapshot["offering_full_code"] == f"{service_code}.new_account"
    assert snapshot["selected_by"] == "requester"


@pytest.mark.asyncio
async def test_service_catalog_publication_blocks_invalid_policy_refs_and_empty_approval(test_engine) -> None:
    suffix = uuid.uuid4().hex[:8]
    service_code = f"governance_{suffix}"
    template_code = f"governance_template_{suffix}"
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        queue = TicketQueue(code=f"queue_{suffix}", name="Governance Support", is_active=True)
        session.add(queue)
        await session.flush()
        session.add(
            RequestTemplate(
                template_code=template_code,
                version="1",
                public_title="Governance template",
                ticket_type="request",
                config_json={"no_sla": True},
                is_active=True,
                published_at=datetime.now(timezone.utc),
            )
        )
        session.add(
            ApprovalPolicy(
                code=f"approval_empty_{suffix}",
                version="1",
                title="Approval without approvers",
                config_json={"required": True},
                is_active=True,
                published_at=datetime.now(timezone.utc),
            )
        )
        repo = ServiceCatalogRepo(session)
        await repo.upsert_service_draft(
            {
                "code": service_code,
                "public_title": "Governance",
                "short_description": "Governance service",
                "visibility": "public",
                "owner_queue_id": queue.id,
                "default_queue_id": queue.id,
                "default_sla_policy_code": f"missing_sla_{suffix}",
            },
            actor_id="admin-test",
            actor_role="admin",
        )
        offering = await repo.upsert_offering_draft(
            {
                "service_code": service_code,
                "code": "approval_required",
                "public_title": "Approval required",
                "short_description": "Approval required request",
                "request_type": "request",
                "request_template_key": template_code,
                "visibility": "public",
                "approval_policy_code": f"approval_empty_{suffix}",
            },
            actor_id="admin-test",
            actor_role="admin",
        )
        publication = ServiceCatalogPublicationService(session)
        service_validation = await publication.validate_service(service_code)
        offering_validation = await publication.validate_offering(offering["full_code"])

    assert service_validation["blocking"] is True
    assert any(issue["path"] == "default_sla_policy_code" for issue in service_validation["issues"])
    assert offering_validation["blocking"] is True
    assert any(issue["path"] == "approval_policy_code" for issue in offering_validation["issues"])


@pytest.mark.asyncio
async def test_service_catalog_publication_blocks_offering_when_runtime_simulation_cannot_route(test_engine) -> None:
    suffix = uuid.uuid4().hex[:8]
    service_code = f"runtime_gate_{suffix}"
    template_code = f"runtime_gate_template_{suffix}"
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(
            RequestTemplate(
                template_code=template_code,
                version="1",
                public_title="Runtime gate template",
                ticket_type="service_request",
                config_json={"no_sla": True},
                is_active=True,
                published_at=datetime.now(timezone.utc),
            )
        )
        repo = ServiceCatalogRepo(session)
        await repo.upsert_service_draft(
            {
                "code": service_code,
                "public_title": "Runtime gate",
                "short_description": "Runtime gate service",
                "visibility": "public",
                "owner_actor_id": "owner",
                "reporting_category": "governance",
                "metadata": {"no_ticket": True},
            },
            actor_id="admin-test",
            actor_role="admin",
        )
        offering = await repo.upsert_offering_draft(
            {
                "service_code": service_code,
                "code": "unroutable",
                "public_title": "Unroutable offering",
                "short_description": "Offering has no runtime route",
                "request_type": "service_request",
                "request_template_key": template_code,
                "visibility": "public",
                "reporting_category": "governance",
            },
            actor_id="admin-test",
            actor_role="admin",
        )

        validation = await ServiceCatalogPublicationService(session).validate_offering(offering["full_code"])

    assert validation["blocking"] is True
    assert any(issue["kind"] == "runtime_simulation_failed" for issue in validation["issues"])
