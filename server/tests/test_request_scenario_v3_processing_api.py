"""Isolated v3 publication, simulation and canonical ticket creation parity."""
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import ApprovalPolicy, RequestTemplate, Ticket, TicketApproval, TicketBusinessCalendar, TicketQueue
from tests.test_request_scenario_admin_api import ADMIN, BASE
from tests.test_request_scenario_publication_api import ready
from tests.test_request_scenario_submit_api import OWNER
from tests.test_request_scenario_session_api import BASE as SESSION_BASE

pytestmark = [pytest.mark.db_cleanup("full"), pytest.mark.light_app]


@pytest.mark.asyncio
async def test_profile_to_v3_ticket_to_ordinary_manager_approval_and_organization_audience(test_client_light, test_engine):
    import uuid
    from app.db.models import (AccessGroup, AccessGroupMember, AccessGroupPermission, HelpdeskService, RegistryAudienceGroup, RegistryAudienceGroupMember, RegistryDepartment, RegistryLocation, RegistryPerson, RegistryPersonIdentity, UiUser)
    from registry.effective_identity_service import EffectiveIdentityService
    from requester.identity_service import RequesterIdentityResolver
    identifier, definition, _, _ = await configured(test_engine)
    manager_id, old_id, new_id, location_id = [str(uuid.uuid4()) for _ in range(4)]
    login = "ordinary-manager-" + manager_id[:8]
    fallback_login = "fallback-manager-" + manager_id[:8]
    async with async_sessionmaker(test_engine)() as session:
        session.add_all([
            RegistryDepartment(department_id=old_id, code="old-" + old_id[:8], name="Old department", status="active"),
            RegistryDepartment(department_id=new_id, code="new-" + new_id[:8], name="New department", status="active"),
            RegistryLocation(location_id=location_id, building="Synthetic office", floor="1", room="101", display_name="Synthetic office", status="active"),
            RegistryPerson(person_id=manager_id, display_name="Ordinary manager", status="active", metadata_json={}),
            RegistryPersonIdentity(person_id=manager_id, provider="ui_login", identifier=login, normalized_identifier=login, verified=True),
            UiUser(user_login=login, password_hash="test", actor_role="user", is_active=True),
            UiUser(user_login=fallback_login, password_hash="test", actor_role="admin", is_active=True),
        ])
        group = AccessGroup(code="decide-" + manager_id[:8], name="Synthetic explicit approvers", is_active=True)
        audience_code = "dept-" + new_id[:8]
        audience = RegistryAudienceGroup(audience_group_id=str(uuid.uuid4()), code=audience_code, name="New department audience", source="manual", status="active")
        session.add_all([group, audience]); await session.flush()
        session.add_all([AccessGroupMember(group_id=group.id, actor_id=login), AccessGroupPermission(group_id=group.id, permission_code="approval.decide.assigned"),
            RegistryAudienceGroupMember(audience_group_id=audience.audience_group_id, member_type="department", member_id=new_id, source="manual")])
        approval_policy = await session.scalar(select(ApprovalPolicy).where(ApprovalPolicy.code == definition["scenario_key"] + "_approval"))
        approval_policy.config_json = {"required": False, "approver_source": {"type": "requester_manager", "fallback": {"type": "explicit_user", "user_id": fallback_login}}}
        await session.commit()
    profile_payload = {"full_name": "Synthetic employee", "department_id": old_id, "location_id": location_id, "phone": "123"}
    response = await test_client_light.put("/api/web/requester/profile", headers=OWNER, json=profile_payload)
    assert response.status == 200, await response.text()
    employee_id = (await response.json())["data"]["profile"]["person_id"]
    confirmed = await test_client_light.patch(f"/api/web/admin/registry/people/{employee_id}", headers=ADMIN, json={"department_id": old_id, "location_id": location_id, "manager_person_id": manager_id, "reason": "Synthetic official context"})
    assert confirmed.status == 200, await confirmed.text()
    await publish(test_client_light, identifier, definition)
    requester = await at_submit(test_client_light, definition, "team")
    created = await test_client_light.post(requester + "/submit", headers=OWNER, json={"revision": 3, "confirm": True})
    assert created.status == 200, await created.text()
    ticket_id = (await created.json())["data"]["linked_ticket_id"]
    async with async_sessionmaker(test_engine)() as session:
        ticket = await session.get(Ticket, ticket_id)
        historical_context = ticket.custom_fields
        assert ticket.device_id is None
        assignment = await session.scalar(select(TicketApproval).where(TicketApproval.ticket_id == ticket_id))
        assert assignment.approver_id == login
        approval_id = assignment.id
    manager_headers = {"Authorization": "Bearer test-ui-user:" + login}
    pending = await test_client_light.get("/api/web/requester/approvals", headers=manager_headers)
    assert pending.status == 200 and any(item["approval_id"] == approval_id for item in (await pending.json())["data"]["items"])
    decided = await test_client_light.post(f"/api/web/support/tickets/{ticket_id}/approvals/{approval_id}/decision", headers=manager_headers, json={"decision": "approved", "comment": "Approved by ordinary manager"})
    assert decided.status == 200, await decided.text()
    # A later profile proposal cannot expand the audience or mutate retained ticket context.
    proposed = await test_client_light.put("/api/web/requester/profile", headers=OWNER, json={**profile_payload, "department_id": new_id})
    assert proposed.status == 200, await proposed.text()
    async with async_sessionmaker(test_engine)() as session:
        employee = await session.get(RegistryPerson, employee_id)
        proposal = employee.metadata_json["organization_context_v1"]["fields"]["department_id"]["pending"]
        identity = await EffectiveIdentityService(session).resolve_actor_identity("scenario-owner", "user")
        assert not any(item["code"] == audience_code for item in identity.audience_groups)
        assert (await session.get(Ticket, ticket_id)).custom_fields == historical_context
        # Restricted catalog visibility is independent of organizational audiences.
        service = await session.scalar(select(HelpdeskService).where(HelpdeskService.code == definition["service_code"]))
        service.visibility = "restricted"; await session.commit()
    before = await (await test_client_light.get("/api/service-catalog/current", headers=OWNER)).json()
    assert not any(item["service_code"] == definition["service_code"] for item in before["services"])
    approved = await test_client_light.patch(f"/api/web/admin/registry/people/{employee_id}", headers=ADMIN, json={"organization_review": {"field": "department_id", "proposal_id": proposal["proposal_id"], "decision": "approve"}, "reason": "Synthetic department move"})
    assert approved.status == 200, await approved.text()
    async with async_sessionmaker(test_engine)() as session:
        identity = await EffectiveIdentityService(session).resolve_actor_identity("scenario-owner", "user")
        assert any(item["code"] == audience_code for item in identity.audience_groups)
        assert (await session.get(Ticket, ticket_id)).custom_fields == historical_context
        employee = await RequesterIdentityResolver(session).resolve_person_for_web_user("scenario-owner")
        assert employee.department_id == new_id
    after = await (await test_client_light.get("/api/service-catalog/current", headers=OWNER)).json()
    assert not any(item["service_code"] == definition["service_code"] for item in after["services"])
    report = await test_client_light.get("/api/web/admin/registry/scenario-readiness", headers=ADMIN)
    assert report.status == 200, await report.text()
    issues = (await report.json())["data"]["issues"]
    assert not any(item["kind"] == "scenario_map_unavailable" and item["object_id"] == identifier for item in issues)
    assert any(item["kind"] == "scenario_manager_unavailable" and item["object_type"] == "request_scenario" and item["object_id"] == identifier for item in issues)


async def configured(engine, *, business=False, draft_offering=False):
    identifier, definition = await ready(engine)
    code = definition["scenario_key"]
    async with async_sessionmaker(engine)() as session:
        queue = TicketQueue(code=code + "-v3", name="Map-specific queue", is_active=True)
        calendar = TicketBusinessCalendar(code=code + "-v3", name="Map calendar", timezone="UTC", is_active=True,
            weekly_hours_json=[{"day": day, "start": "09:00", "end": "18:00"} for day in range(5)], holidays_json=[])
        session.add_all([queue, calendar])
        await session.flush()
        queue_id, calendar_id = queue.id, calendar.id
        approval = await session.scalar(select(ApprovalPolicy).where(ApprovalPolicy.code == code + "_approval"))
        approval.config_json = {"required": False, "approver_source": {"type": "explicit_user", "user_id": "test-manager"}}
        # The map must work without a shared SLA row or a global route template.
        template = await session.scalar(select(RequestTemplate).where(RequestTemplate.template_code == code))
        template.sla_policy_id = None
        template.routing_policy_code = None
        template.sla_policy_code = None
        config = dict(template.config_json)
        config.pop("routing_policy", None)
        config.pop("sla_policy", None)
        template.config_json = config
        if draft_offering:
            from app.db.models import HelpdeskServiceOffering
            offering = await session.scalar(select(HelpdeskServiceOffering).where(HelpdeskServiceOffering.full_code == definition["offering_full_code"]))
            offering.lifecycle_status = "draft"
            offering.request_type = "incident"
        await session.commit()
    definition.update(schema_version=3, publish_offering=draft_offering, processing={
        "routes": {"support": {"title": "Map queue", "queue_code": code + "-v3"}},
        "sla_profiles": {
            "standard": {"title": "Standard", "first_response_minutes": 60, "resolution_minutes": 300},
            "urgent": {"title": "Urgent", "first_response_minutes": 15, "resolution_minutes": 120,
                       **({"time_basis": "business", "calendar_id": calendar_id} if business else {})}},
        "defaults": {"route": "support", "sla_profile": "standard"}})
    definition["blocks"][0]["fields"][1]["options"].append({"value": "single", "label": "One person"})
    definition["blocks"][0]["transitions"] = [
        {"to": "review", "when": {"source": "answer", "field": "scope", "op": "eq", "value": "team"},
         "processing": {"sla_profile": "urgent", "approval_required": True}},
        {"to": "review", "processing": {"approval_required": False}}]
    return identifier, definition, queue_id, calendar_id


async def publish(client, identifier, definition):
    url = BASE + "/scenarios/" + identifier
    saved = await client.put(url + "/draft", headers=ADMIN, json={"revision": 1, "definition": definition})
    assert saved.status == 200, await saved.text()
    response = await client.post(url + "/publish-preview", headers=ADMIN, json={"revision": 2})
    assert response.status == 200, await response.text()
    preview = (await response.json())["data"]
    assert preview["readiness"]["can_publish"], preview["readiness"]
    response = await client.post(url + "/publish", headers=ADMIN, json={"revision": 2, "confirm": True, "confirmation_token": preview["confirmation_token"]})
    assert response.status == 200, await response.text()
    return url, preview


async def at_submit(client, definition, scope):
    started = await client.post(SESSION_BASE, headers=OWNER, json={"offering_full_code": definition["offering_full_code"]})
    assert started.status == 200, await started.text()
    url = SESSION_BASE + "/" + (await started.json())["data"]["id"]
    response = await client.post(url + "/answer", headers=OWNER, json={"expected_block_id": "questions", "revision": 1,
        "answers": {"summary": "No print", "scope": scope, "continuity": "work_stopped_no_workaround"}})
    assert response.status == 200, await response.text()
    response = await client.post(url + "/advance", headers=OWNER, json={"expected_block_id": "review", "revision": 2})
    assert response.status == 200, await response.text()
    return url


@pytest.mark.asyncio
@pytest.mark.parametrize("scope,minutes,required", [("team", 120, True), ("single", 300, False)])
async def test_map_sla_route_and_approval_match_actual_creation(test_client_light, test_engine, scope, minutes, required):
    identifier, definition, queue_id, _ = await configured(test_engine, draft_offering=True)
    url, _ = await publish(test_client_light, identifier, definition)
    response = await test_client_light.post(url + "/simulate", headers=ADMIN, json={"revision": 2, "steps": [
        {"expected_block_id": "questions", "revision": 1, "answers": {"summary": "No print", "scope": scope, "continuity": "work_stopped_no_workaround"}},
        {"expected_block_id": "review", "revision": 2}]})
    assert response.status == 200, await response.text()
    processing = (await response.json())["data"]["processing"]
    assert processing["routing"]["queue_id"] == queue_id
    assert processing["sla"]["resolution_min"] == minutes
    assert processing["approval"]["required"] is required
    requester = await at_submit(test_client_light, definition, scope)
    response = await test_client_light.post(requester + "/submit", headers=OWNER, json={"revision": 3, "confirm": True})
    assert response.status == 200, await response.text()
    ticket_id = (await response.json())["data"]["linked_ticket_id"]
    async with async_sessionmaker(test_engine)() as session:
        ticket = await session.get(Ticket, ticket_id)
        assert ticket.queue_id == queue_id
        assert ticket.sla_policy_id is None and ticket.resolution_due_at is not None
        context = ticket.custom_fields["request_template"]
        assert context["sla_policy"]["targets"]["resolution"]["P2"] == minutes
        assert context["approval_policy"]["required"] is required
        assert bool(await session.scalar(select(func.count()).select_from(TicketApproval).where(TicketApproval.ticket_id == ticket_id))) is required


@pytest.mark.asyncio
async def test_published_business_calendar_pinned_and_disabled_queue_blocks_create(test_client_light, test_engine):
    identifier, definition, queue_id, calendar_id = await configured(test_engine, business=True)
    await publish(test_client_light, identifier, definition)
    async with async_sessionmaker(test_engine)() as session:
        calendar = await session.get(TicketBusinessCalendar, calendar_id)
        calendar.weekly_hours_json = [{"day": 0, "start": "10:00", "end": "12:00"}]
        await session.commit()
    requester = await at_submit(test_client_light, definition, "team")
    response = await test_client_light.post(requester + "/submit", headers=OWNER, json={"revision": 3, "confirm": True})
    assert response.status == 200, await response.text()
    async with async_sessionmaker(test_engine)() as session:
        ticket = await session.get(Ticket, (await response.json())["data"]["linked_ticket_id"])
        assert len(ticket.custom_fields["request_template"]["sla_policy"]["calendar"]["weekly_hours_json"]) == 5
        queue = await session.get(TicketQueue, queue_id)
        queue.is_active = False
        await session.commit()
        count = await session.scalar(select(func.count()).select_from(Ticket))
    requester = await at_submit(test_client_light, definition, "single")
    response = await test_client_light.post(requester + "/submit", headers=OWNER, json={"revision": 3, "confirm": True})
    assert response.status == 409, await response.text()
    async with async_sessionmaker(test_engine)() as session:
        assert await session.scalar(select(func.count()).select_from(Ticket)) == count


@pytest.mark.asyncio
async def test_manager_approval_uses_registry_identity_then_explicit_fallback_and_fails_closed(test_client_light, test_engine):
    import uuid
    from app.db.models import RegistryPerson, RegistryPersonIdentity, UiUser, TicketQueueMember
    identifier, definition, queue_id, _ = await configured(test_engine)
    manager_id, employee_id = str(uuid.uuid4()), str(uuid.uuid4())
    source = {"type": "requester_manager", "fallback": {"type": "explicit_user", "user_id": "fallback-manager"}}
    async with async_sessionmaker(test_engine)() as session:
        session.add_all([
            RegistryPerson(person_id=manager_id, display_name="Known manager", status="active"),
            RegistryPerson(person_id=employee_id, display_name="Employee", status="active", metadata_json={"manager_person_id": manager_id}),
        ])
        from registry.organization_trust import confirm_fields
        employee = next(row for row in session.new if isinstance(row, RegistryPerson) and row.person_id == employee_id)
        confirm_fields(employee, ["manager_person_id"], actor_id="admin")
        await session.flush()
        session.add_all([
            RegistryPersonIdentity(person_id=manager_id, provider="ui_login", identifier="Support-Test", normalized_identifier="support-test", verified=True),
            RegistryPersonIdentity(person_id=employee_id, provider="ui_login", identifier="scenario-owner", normalized_identifier="scenario-owner", verified=True),
        ])
        for login, role in (("support-test", "support"), ("fallback-manager", "admin")):
            account = await session.get(UiUser, login)
            if account is None:
                session.add(UiUser(user_login=login, password_hash="test-only-unusable", actor_role=role, is_active=True))
            else:
                account.actor_role, account.is_active = role, True
        session.add(TicketQueueMember(queue_id=queue_id, actor_id="support-test", role_in_queue="operator"))
        approval = await session.scalar(select(ApprovalPolicy).where(ApprovalPolicy.code == definition["scenario_key"] + "_approval"))
        approval.config_json = {"required": False, "approver_source": source}
        await session.commit()
    url, preview = await publish(test_client_light, identifier, definition)
    assert any(item["approval_required"] for item in preview["outcomes"] if item["kind"] == "ticket")
    requester = await at_submit(test_client_light, definition, "team")
    response = await test_client_light.post(requester + "/ticket-preview", headers=OWNER, json={"revision": 3})
    assert response.status == 200 and (await response.json())["data"]["approval"]["required"], await response.text()
    response = await test_client_light.post(requester + "/submit", headers=OWNER, json={"revision": 3, "confirm": True})
    assert response.status == 200, await response.text()
    ticket_id = (await response.json())["data"]["linked_ticket_id"]
    async with async_sessionmaker(test_engine)() as session:
        approval = await session.scalar(select(TicketApproval).where(TicketApproval.ticket_id == ticket_id))
        assert approval.approver_id == "support-test"
        approval_id = approval.id
        await session.commit()
    decision = await test_client_light.post(f"/api/web/support/tickets/{ticket_id}/approvals/{approval_id}/decision",
        headers={"Authorization": "Bearer test-ui-support-token"}, json={"decision": "approved", "reason": "Manager approved request"})
    assert decision.status == 200, await decision.text()
    assert (await decision.json())["data"]["approval"]["status"] == "approved"
    # A manager reference must remain actionable as canonical account access
    # changes; a configured fallback handles disabled and requester-only users.
    for mode in ("requester_only", "disabled", "missing"):
        async with async_sessionmaker(test_engine)() as session:
            account = await session.get(UiUser, "support-test")
            if mode == "missing":
                await session.delete(account)
            else:
                account.actor_role = "user" if mode == "requester_only" else "support"
                account.is_active = mode != "disabled"
            await session.commit()
        requester = await at_submit(test_client_light, definition, "team")
        response = await test_client_light.post(requester + "/submit", headers=OWNER, json={"revision": 3, "confirm": True})
        assert response.status == 200, await response.text()
        fallback_ticket_id = (await response.json())["data"]["linked_ticket_id"]
        async with async_sessionmaker(test_engine)() as session:
            assert await session.scalar(select(TicketApproval.approver_id).where(TicketApproval.ticket_id == fallback_ticket_id)) == "fallback-manager"
    async with async_sessionmaker(test_engine)() as session:
        approval = await session.scalar(select(ApprovalPolicy).where(ApprovalPolicy.code == definition["scenario_key"] + "_approval"))
        approval.config_json = {"required": False, "approver_source": {"type": "requester_manager"}}
        await session.commit()
        count = await session.scalar(select(func.count()).select_from(Ticket))
    readiness = await test_client_light.post(url + "/publish-preview", headers=ADMIN, json={"revision": 2})
    assert any(item["code"] == "approval_unavailable" for item in (await readiness.json())["data"]["readiness"]["issues"])
    requester = await at_submit(test_client_light, definition, "team")
    response = await test_client_light.post(requester + "/submit", headers=OWNER, json={"revision": 3, "confirm": True})
    assert response.status == 409, await response.text()
    async with async_sessionmaker(test_engine)() as session:
        assert await session.scalar(select(func.count()).select_from(Ticket)) == count
