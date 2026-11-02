"""Atomic, additive phase-one publication through real PostgreSQL services."""
from copy import deepcopy
from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import (ClosurePolicy, VisibilityPolicy, HelpdeskService,
    HelpdeskServiceCatalogAudit, HelpdeskPolicyAudit, RequestStudioPublishToken, Ticket, TicketQueue)
from app.db.request_scenario_models import RequestStudioScenario, RequestStudioScenarioVersion
from app.repos.request_scenario_repo import RequestScenarioRepo
from auth.context import AuthContext, AuthType
from scripts.helpdesk_phase1_catalog import CLOSURE_CODE, publish_phase1
from tests.test_helpdesk_phase1_catalog_no_db import base_definition
from tests.test_request_scenario_publication_api import ready
from tickets.request_scenario_publication import ScenarioPublicationService
from web_api.dto.request_scenario_admin import ScenarioPublish

pytestmark = pytest.mark.db_cleanup("full")
AUTH = AuthContext(actor_id="admin-test", actor_role="admin", auth_type=AuthType.UI_TOKEN)


async def seed_catalog(engine):
    _, initial = await ready(engine)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        # A real published template already has all canonical policy/form inputs.
        for code in ("access", "workplace", "other"):
            service = await session.scalar(select(HelpdeskService).where(HelpdeskService.code == code))
            if service is None:
                service = HelpdeskService(service_id=str(uuid.uuid4()), code=code, name=code, public_title=code)
                session.add(service)
            service.lifecycle_status, service.visibility = "published", "public"
            service.metadata_json = {"studio_default_template": initial["scenario_key"]}
        for code in ("network", "sysadmins", "servicedesk_l1"):
            queue = await session.scalar(select(TicketQueue).where(TicketQueue.code == code))
            if queue is None:
                session.add(TicketQueue(code=code, name=code, is_active=True))
            else:
                queue.is_active = True
        session.add(ClosurePolicy(code=CLOSURE_CODE, version="1.0.1", title="Обычное закрытие",
            config_json={"require_public_summary": True, "require_resolution_code": True},
            is_active=True, published_at=datetime.now(timezone.utc)))
        session.add(VisibilityPolicy(code="guided_studio_20261011_visibility", version="1.0.1", title="Видимость",
            config_json={"public_fields": ["ticket_code", "public_status"]}, is_active=True,
            published_at=datetime.now(timezone.utc)))
        await session.flush()
        base = base_definition()
        base["offering_full_code"] = ""
        base["publish_offering"] = False
        base["process_binding"]["request_template_key"] = ""
        repo = RequestScenarioRepo(session, AUTH)
        created = await repo.create_service(base)
        publisher = ScenarioPublicationService(repo)
        preview = await publisher.preview(created["scenario"]["id"], 1)
        assert preview["readiness"]["can_publish"], preview["readiness"]
        await publisher.publish(created["scenario"]["id"], ScenarioPublish(revision=1, confirm=True,
            confirmation_token=preview["confirmation_token"]))
        await session.commit()
    return factory


async def counts(factory):
    async with factory() as session:
        return [await session.scalar(select(func.count()).select_from(model)) for model in (
            RequestStudioScenario, RequestStudioScenarioVersion, ClosurePolicy,
            RequestStudioPublishToken, HelpdeskServiceCatalogAudit, HelpdeskPolicyAudit, Ticket)]


@pytest.mark.asyncio
async def test_plan_readonly_apply_idempotent_and_old_snapshots_unchanged(test_engine):
    factory = await seed_catalog(test_engine)
    before = await counts(factory)
    async with factory() as session:
        old_versions = {v.id: deepcopy(v.definition) for v in await session.scalars(select(RequestStudioScenarioVersion))}
        old_policy = await session.scalar(select(ClosurePolicy).where(ClosurePolicy.code == CLOSURE_CODE))
        old_config = deepcopy(old_policy.config_json)
    plan = await publish_phase1(factory, AUTH, isolated_test=True)
    assert plan["applied"] is False
    assert await counts(factory) == before
    result = await publish_phase1(factory, AUTH, apply=True, expected_fingerprint=plan["fingerprint"], isolated_test=True)
    assert result["applied"] is True and len(result["scenarios"]) == 4
    after = await counts(factory)
    assert after[0] == before[0] + 4 and after[1] == before[1] + 4
    assert after[2] == before[2] + 1 and after[-1] == before[-1]
    async with factory() as session:
        for identifier, content in old_versions.items():
            assert (await session.get(RequestStudioScenarioVersion, identifier)).definition == content
        rows = (await session.scalars(select(ClosurePolicy).where(ClosurePolicy.code == CLOSURE_CODE))).all()
        assert next(row for row in rows if row.version == "1.0.1").config_json == old_config
        assert next(row for row in rows if row.version == "1.0.2").config_json["require_public_summary"] is True
    fresh = await publish_phase1(factory, AUTH, isolated_test=True)
    again = await publish_phase1(factory, AUTH, apply=True, expected_fingerprint=fresh["fingerprint"], isolated_test=True)
    assert not again["closure_changed"] and all(not item["changed"] for item in again["scenarios"])
    assert await counts(factory) == after


@pytest.mark.asyncio
async def test_readiness_failure_rolls_back_all_policy_maps_tokens_and_audits(test_engine, monkeypatch):
    factory = await seed_catalog(test_engine)
    before = await counts(factory)
    plan = await publish_phase1(factory, AUTH, isolated_test=True)
    original = ScenarioPublicationService.publish
    calls = 0

    async def fail_second(self, identifier, payload):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ValueError("Injected publication failure")
        return await original(self, identifier, payload)

    monkeypatch.setattr(ScenarioPublicationService, "publish", fail_second)
    with pytest.raises(ValueError, match="Injected publication failure"):
        await publish_phase1(factory, AUTH, apply=True, expected_fingerprint=plan["fingerprint"], isolated_test=True)
    assert await counts(factory) == before


@pytest.mark.asyncio
async def test_changed_baseline_fails_closed_before_any_publication(test_engine):
    factory = await seed_catalog(test_engine)
    before = await counts(factory)
    with pytest.raises(ValueError, match="baseline changed"):
        await publish_phase1(factory, AUTH, apply=True, expected_fingerprint="stale", isolated_test=True)
    assert await counts(factory) == before
