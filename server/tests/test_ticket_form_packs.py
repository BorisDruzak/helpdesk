import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Playbook, PlaybookRun, PlaybookVersion, ServerConfig, Ticket, TicketCategory, TicketEvent, TicketFormPack
from app.repos.ticket_form_packs_repo import TICKET_FORM_PREFERRED_KEY_PREFIX
from tickets.form_catalog import validate_form_pack_schema, validate_form_submission


def _admin_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-ui-admin-token"}


async def _clear_request_form_packs(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        await session.execute(
            delete(TicketFormPack).where(TicketFormPack.pack_key == "request_forms")
        )
        await session.execute(
            delete(ServerConfig).where(
                ServerConfig.key == f"{TICKET_FORM_PREFERRED_KEY_PREFIX}request_forms"
            )
        )
        await session.commit()


@pytest.mark.asyncio
async def test_public_ticket_forms_current_returns_builtin_catalog(test_client, test_engine):
    await _clear_request_form_packs(test_engine)

    response = await test_client.get("/public_api/ticket_forms/current")
    assert response.status == 200, await response.text()
    data = await response.json()
    assert data["status"] == "ok"
    pack = data["pack"]
    assert pack["pack_key"] == "request_forms"
    form_keys = {form["key"] for form in pack.get("forms") or []}
    assert {"breakage", "access", "printer", "site_system"} <= form_keys
    site_form = next(form for form in pack["forms"] if form["key"] == "site_system")
    assert site_form["priority_policy"]["impact_field"] == "impact_scope"
    assert site_form["priority_policy"]["urgency_field"] == "work_continuity"
    assert site_form["priority_policy"]["importance_field"] == "business_importance"
    assert {"impact_scope", "work_continuity", "business_importance"}.issubset(
        {field["key"] for field in site_form["fields"]}
    )
    assert "priority_field" in site_form["field_roles"]["impact_scope"]


@pytest.mark.asyncio
async def test_admin_can_save_ticket_form_pack_and_switch_current_version(test_client, test_engine):
    await _clear_request_form_packs(test_engine)

    response = await test_client.post(
        "/api/ticket_forms/packs/save",
        json={
            "pack": {
                "pack_key": "request_forms",
                "title": "Каталог заявок",
                "description": "Тестовая публикация каталога",
                "forms": [
                    {
                        "key": "printer",
                        "request_kind": "printer",
                        "title": "Печать / принтер",
                        "description": "Проверка сохранения каталога",
                        "fields": [
                            {"key": "room", "label": "Кабинет", "type": "text", "required": True},
                            {"key": "printer_model", "label": "Модель", "type": "text", "required": False},
                        ],
                    }
                ],
            },
        },
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert response.status == 200, await response.text()
    data = await response.json()
    assert data["status"] == "ok"
    assert data["pack"]["version"] == "1.0.1"

    current_response = await test_client.get(
        "/api/ticket_forms/current?pack_key=request_forms",
        headers=_admin_headers(),
    )
    assert current_response.status == 200, await current_response.text()
    current_data = await current_response.json()
    assert current_data["status"] == "ok"
    assert current_data["pack"]["version"] == "1.0.1"
    assert current_data["pack"]["forms"][0]["fields"][0]["key"] == "room"
    assert current_data["pack"]["forms"][0]["ticket_type"] == "incident"


@pytest.mark.asyncio
async def test_admin_save_auto_increments_internal_pack_version(test_client, test_engine):
    await _clear_request_form_packs(test_engine)

    payload = {
        "pack": {
            "pack_key": "request_forms",
            "title": "Каталог заявок",
            "description": "Автоматический выпуск",
            "forms": [
                {
                    "key": "printer",
                    "request_kind": "printer",
                    "title": "Печать / принтер",
                    "fields": [
                        {"key": "room", "label": "Кабинет", "type": "text", "required": True},
                    ],
                }
            ],
        }
    }

    first = await test_client.post(
        "/api/ticket_forms/packs/save",
        json=payload,
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert first.status == 200, await first.text()
    assert (await first.json())["pack"]["version"] == "1.0.1"

    payload["pack"]["description"] = "Автоматический выпуск 2"
    second = await test_client.post(
        "/api/ticket_forms/packs/save",
        json=payload,
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert second.status == 200, await second.text()
    second_data = await second.json()
    assert second_data["pack"]["version"] == "1.0.2"


@pytest.mark.asyncio
async def test_admin_save_rejects_duplicate_form_key(test_client):
    response = await test_client.post(
        "/api/ticket_forms/packs/save",
        json={
            "pack": {
                "pack_key": "request_forms",
                "title": "Каталог заявок",
                "forms": [
                    {
                        "key": "printer",
                        "request_kind": "printer",
                        "title": "Печать / принтер",
                        "fields": [{"key": "room", "label": "Кабинет", "type": "text", "required": True}],
                    },
                    {
                        "key": "printer",
                        "request_kind": "printer_duplicate",
                        "title": "Дубликат",
                        "fields": [{"key": "room_2", "label": "Кабинет 2", "type": "text", "required": False}],
                    },
                ],
            }
        },
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert response.status == 400, await response.text()
    data = await response.json()
    assert data["error"] == "validation_error"
    assert "duplicate form key" in str(data["details"])


@pytest.mark.asyncio
async def test_create_ticket_accepts_form_payload_and_sets_ticket_type(test_client, test_engine):
    device_id = str(uuid.uuid4())
    response = await test_client.post(
        "/api/tickets/create",
        json={
            "title": "Printer issue",
            "description": "Paper jam on floor 2",
            "device_id": device_id,
            "user_display_name": "Alice",
            "form_key": "printer",
            "form_pack_key": "request_forms",
            "form_payload": {
                "room": "214",
                "printer_model": "HP LaserJet",
                "printer_number": "PR-17",
                "impact_scope": "single_user",
                "work_continuity": "workaround_available",
                "business_importance": "normal",
            },
            "ticket_type": "printer",
        },
        headers={"Authorization": "Bearer test-ui-user:alice"},
    )
    assert response.status == 200, await response.text()
    ticket_id = (await response.json())["ticket"]["ticket_id"]

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        ticket = (
            await session.execute(select(Ticket).where(Ticket.ticket_id == ticket_id))
        ).scalar_one()

    assert ticket.ticket_type == "incident"
    custom_fields = ticket.custom_fields or {}
    assert custom_fields["request_kind"] == "printer"
    assert custom_fields["request_form_key"] == "printer"
    assert custom_fields["request_form_data"]["room"] == "214"
    assert custom_fields["request_form_data"]["printer_model"] == "HP LaserJet"


@pytest.mark.asyncio
async def test_create_ticket_from_form_starts_configured_playbook(test_client, test_engine):
    await _clear_request_form_packs(test_engine)
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    playbook_key = f"printer.quick_diag.{uuid.uuid4().hex[:8]}"

    async with session_maker() as session:
        playbook = Playbook(
            key=playbook_key,
            name="Быстрая диагностика принтера",
            domain="diagnostics",
            owner="tests",
            archived=False,
        )
        session.add(playbook)
        await session.flush()
        session.add(
            PlaybookVersion(
                playbook_id=playbook.id,
                version="1.0.0",
                manifest_json={},
                status="published",
                created_at=datetime.now(timezone.utc),
                published_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()

    pack_response = await test_client.post(
        "/api/ticket_forms/packs/save",
        json={
            "pack": {
                "pack_key": "request_forms",
                "title": "Каталог заявок",
                "forms": [
                    {
                        "key": "printer",
                        "request_kind": "printer",
                        "title": "Печать / принтер",
                        "fields": [
                            {"key": "room", "label": "Кабинет", "type": "text", "required": True},
                            {"key": "symptom", "label": "Симптом", "type": "text", "required": True},
                        ],
                        "playbook_triggers": [
                            {
                                "event": "ticket_created",
                                "playbook_key": playbook_key,
                                "module_kind": "diagnostic",
                                "enabled": True,
                            }
                        ],
                    }
                ],
            },
        },
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert pack_response.status == 200, await pack_response.text()

    device_id = str(uuid.uuid4())
    response = await test_client.post(
        "/api/tickets/create",
        json={
            "title": "Printer issue",
            "description": "Paper jam on floor 2",
            "device_id": device_id,
            "user_display_name": "Alice",
            "form_key": "printer",
            "form_pack_key": "request_forms",
            "form_payload": {
                "room": "214",
                "symptom": "Не печатает",
                "impact_scope": "single_user",
                "work_continuity": "workaround_available",
                "business_importance": "normal",
            },
            "ticket_type": "printer",
        },
        headers={"Authorization": "Bearer test-ui-user:alice"},
    )
    assert response.status == 200, await response.text()
    ticket_id = (await response.json())["ticket"]["ticket_id"]

    async with session_maker() as session:
        run = (
            await session.execute(select(PlaybookRun).where(PlaybookRun.device_id == device_id))
        ).scalar_one()
        event = (
            await session.execute(
                select(TicketEvent).where(
                    TicketEvent.ticket_id == ticket_id,
                    TicketEvent.event_type == "playbook_started",
                )
            )
        ).scalar_one()

    assert run.trigger_type == "ticket_created"
    request_form_data = run.context_json["facts_package"]["request_form_data"]
    assert request_form_data["room"] == "214"
    assert request_form_data["symptom"] == "Не печатает"
    assert request_form_data["impact_scope"] == "single_user"
    assert event.payload["playbook_key"] == playbook_key
    assert event.payload["playbook_run_id"] == run.id
    assert event.payload["facts_package"]["request_form_summary"][0] == {
        "key": "room",
        "label": "Кабинет",
        "value": "214",
    }


@pytest.mark.asyncio
async def test_public_create_ticket_from_form_starts_configured_playbook(test_client, test_engine):
    await _clear_request_form_packs(test_engine)
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    playbook_key = f"public_printer_diag_{uuid.uuid4().hex[:8]}"

    async with session_maker() as session:
        playbook = Playbook(
            key=playbook_key,
            name="Публичная диагностика принтера",
            domain="diagnostics",
            owner="tests",
            archived=False,
        )
        session.add(playbook)
        await session.flush()
        session.add(
            PlaybookVersion(
                playbook_id=playbook.id,
                version="1.0.0",
                manifest_json={},
                status="published",
                created_at=datetime.now(timezone.utc),
                published_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()

    pack_response = await test_client.post(
        "/api/ticket_forms/packs/save",
        json={
            "pack": {
                "pack_key": "request_forms",
                "title": "Каталог заявок",
                "forms": [
                    {
                        "key": "printer",
                        "request_kind": "printer",
                        "title": "Печать / принтер",
                        "fields": [
                            {"key": "room", "label": "Кабинет", "type": "text", "required": True},
                            {"key": "symptom", "label": "Симптом", "type": "text", "required": True},
                        ],
                        "playbook_triggers": [
                            {
                                "event": "ticket_created",
                                "playbook_key": playbook_key,
                                "module_kind": "diagnostic",
                                "enabled": True,
                            }
                        ],
                    }
                ],
            },
        },
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert pack_response.status == 200, await pack_response.text()

    response = await test_client.post(
        "/public_api/tickets/create",
        json={
            "title": "Printer public issue",
            "description": "Printer does not print",
            "user_display_name": "Public Alice",
            "form_key": "printer",
            "form_pack_key": "request_forms",
            "form_payload": {
                "room": "214",
                "symptom": "Не печатает",
                "impact_scope": "single_user",
                "work_continuity": "workaround_available",
                "business_importance": "normal",
            },
            "ticket_type": "printer",
            "urgency": False,
            "importance": False,
            "urgency_reason": "Live/public request",
            "importance_reason": "Live/public request",
        },
    )
    assert response.status == 200, await response.text()
    ticket_id = (await response.json())["ticket"]["ticket_id"]

    async with session_maker() as session:
        ticket = (await session.execute(select(Ticket).where(Ticket.ticket_id == ticket_id))).scalar_one()
        run = (
            await session.execute(select(PlaybookRun).where(PlaybookRun.device_id == ticket.device_id))
        ).scalar_one()
        event = (
            await session.execute(
                select(TicketEvent).where(
                    TicketEvent.ticket_id == ticket_id,
                    TicketEvent.event_type == "playbook_started",
                )
            )
        ).scalar_one()

    assert run.trigger_type == "ticket_created"
    request_form_data = run.context_json["facts_package"]["request_form_data"]
    assert request_form_data["room"] == "214"
    assert request_form_data["symptom"] == "Не печатает"
    assert request_form_data["impact_scope"] == "single_user"
    assert event.payload["playbook_key"] == playbook_key
    assert event.payload["playbook_run_id"] == run.id


def test_validate_form_pack_schema_rejects_unknown_visible_when_field():
    with pytest.raises(ValueError, match="visible_when.field"):
        validate_form_pack_schema(
            {
                "pack_key": "request_forms",
                "title": "Каталог заявок",
                "forms": [
                    {
                        "key": "printer",
                        "request_kind": "printer",
                        "title": "Принтер",
                        "fields": [
                            {
                                "key": "room",
                                "label": "Кабинет",
                                "type": "text",
                                "required": True,
                            },
                            {
                                "key": "printer_model",
                                "label": "Модель",
                                "type": "text",
                                "required": False,
                                "visible_when": {"field": "missing_field", "equals": "214"},
                            },
                        ],
                    }
                ],
            },
            require_version=False,
        )


def test_validate_form_submission_applies_visible_when_equals():
    pack = validate_form_pack_schema(
        {
            "pack_key": "request_forms",
            "title": "Каталог заявок",
            "forms": [
                {
                    "key": "site_system",
                    "request_kind": "site_system",
                    "title": "Сайт и система",
                    "fields": [
                        {
                            "key": "issue_kind",
                            "label": "Тип проблемы",
                            "type": "select",
                            "required": True,
                            "options": [
                                {"value": "site_down", "label": "Сайт недоступен"},
                                {"value": "auth", "label": "Вход"},
                            ],
                        },
                        {
                            "key": "url",
                            "label": "URL",
                            "type": "text",
                            "required": False,
                            "visible_when": {"field": "issue_kind", "equals": "site_down"},
                        },
                    ],
                }
            ],
        },
        require_version=False,
    )

    visible = validate_form_submission(
        pack,
        form_key="site_system",
        raw_values={
            "issue_kind": "site_down",
            "url": "https://helpdesk.local",
            "impact_scope": "single_user",
            "work_continuity": "workaround_available",
            "business_importance": "normal",
        },
    )
    hidden = validate_form_submission(
        pack,
        form_key="site_system",
        raw_values={
            "issue_kind": "auth",
            "url": "https://should-not-pass.local",
            "impact_scope": "single_user",
            "work_continuity": "workaround_available",
            "business_importance": "normal",
        },
    )

    assert visible["submitted_values"]["url"] == "https://helpdesk.local"
    assert ["issue_kind", "url"] == [item["key"] for item in visible["summary_rows"][:2]]
    assert "impact_scope" in [item["key"] for item in visible["summary_rows"]]
    assert "url" not in hidden["submitted_values"]
    assert [item["key"] for item in hidden["summary_rows"][:1]] == ["issue_kind"]
    assert "impact_scope" in [item["key"] for item in hidden["summary_rows"]]


def test_validate_form_pack_schema_preserves_request_template_process_context():
    pack = validate_form_pack_schema(
        {
            "pack_key": "request_forms",
            "title": "Каталог заявок",
            "forms": [
                {
                    "key": "website_unavailable",
                    "request_kind": "website_unavailable",
                    "ticket_type": "incident",
                    "title": "Не открывается сайт",
                    "category_id": 10,
                    "service_id": 20,
                    "subcategory_id": 30,
                    "default_queue_id": 40,
                    "sla_policy_id": 50,
                    "suggested_playbook_id": "diagnose.website",
                    "field_roles": {
                        "url": ["routing_field", "diagnostic_input"],
                        "affected_scope": ["priority_field"],
                    },
                    "priority_policy": {
                        "impact_field": "affected_scope",
                        "urgency_field": "work_continuity",
                    },
                    "approval_policy": {"required": False},
                    "closure_policy": {"require_resolution_code": True},
                    "fields": [
                        {"key": "url", "label": "URL", "type": "text", "required": True},
                        {"key": "affected_scope", "label": "Кого затронуло", "type": "text"},
                    ],
                }
            ],
        },
        require_version=False,
    )

    form = pack["forms"][0]
    assert form["ticket_type"] == "incident"
    assert form["category_id"] == 10
    assert form["service_id"] == 20
    assert form["subcategory_id"] == 30
    assert form["default_queue_id"] == 40
    assert form["sla_policy_id"] == 50
    assert form["suggested_playbook_id"] == "diagnose.website"
    assert form["field_roles"]["url"] == ["routing_field", "diagnostic_input"]
    assert form["priority_policy"]["impact_field"] == "affected_scope"
    assert form["closure_policy"]["require_resolution_code"] is True


def test_validate_form_pack_schema_preserves_custom_ticket_type():
    pack = validate_form_pack_schema(
        {
            "pack_key": "request_forms",
            "title": "Request catalog",
            "forms": [
                {
                    "key": "custom_access",
                    "request_kind": "custom_access",
                    "ticket_type": "custom_access_process",
                    "title": "Custom access",
                    "fields": [
                        {"key": "system", "label": "System", "type": "text", "required": True},
                    ],
                }
            ],
        },
        require_version=False,
    )

    assert pack["forms"][0]["ticket_type"] == "custom_access_process"


@pytest.mark.asyncio
async def test_create_ticket_uses_template_ticket_type_over_request_body(test_client, test_engine):
    await _clear_request_form_packs(test_engine)
    category_id = 700_000 + int(uuid.uuid4().hex[:6], 16)
    service_id = category_id + 1
    subcategory_id = category_id + 2
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add_all(
            [
                TicketCategory(id=category_id, code=f"web-{category_id}", name="Web", level=1),
                TicketCategory(id=service_id, code=f"reports-{service_id}", name="Reports", parent_id=category_id, level=2),
                TicketCategory(
                    id=subcategory_id,
                    code=f"unavailable-{subcategory_id}",
                    name="Website unavailable",
                    parent_id=service_id,
                    level=3,
                ),
            ]
        )
        await session.commit()

    save_response = await test_client.post(
        "/api/ticket_forms/packs/save",
        json={
            "pack": {
                "pack_key": "request_forms",
                "title": "Каталог заявок",
                "forms": [
                        {
                            "key": "website_unavailable",
                            "request_kind": "website_unavailable",
                            "ticket_type": "incident",
                            "title": "Не открывается сайт",
                            "category_id": category_id,
                            "service_id": service_id,
                            "subcategory_id": subcategory_id,
                        "suggested_playbook_id": "diagnose.website",
                        "field_roles": {"url": ["routing_field", "diagnostic_input"]},
                        "fields": [
                            {"key": "url", "label": "URL", "type": "text", "required": True},
                        ],
                    }
                ],
            }
        },
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert save_response.status == 200, await save_response.text()

    response = await test_client.post(
        "/api/tickets/create",
        json={
            "title": "Website issue",
            "description": "Cannot open reporting site",
            "device_id": str(uuid.uuid4()),
            "user_display_name": "Alice",
            "form_key": "website_unavailable",
            "form_pack_key": "request_forms",
            "form_payload": {
                "url": "https://reports.example.local",
                "impact_scope": "single_user",
                "work_continuity": "workaround_available",
                "business_importance": "normal",
            },
            "ticket_type": "consultation",
        },
        headers={"Authorization": "Bearer test-ui-user:alice"},
    )
    assert response.status == 200, await response.text()
    ticket_id = (await response.json())["ticket"]["ticket_id"]

    async with session_maker() as session:
        ticket = (await session.execute(select(Ticket).where(Ticket.ticket_id == ticket_id))).scalar_one()

    assert ticket.ticket_type == "incident"
    assert ticket.category_id == category_id
    assert ticket.service_id == service_id
    assert ticket.subcategory_id == subcategory_id
    assert ticket.custom_fields["request_kind"] == "website_unavailable"
    assert ticket.custom_fields["request_template"]["key"] == "website_unavailable"
    assert ticket.custom_fields["request_template"]["ticket_type"] == "incident"
    assert ticket.custom_fields["request_template"]["suggested_playbook_id"] == "diagnose.website"


def test_validate_form_submission_applies_visible_when_in():
    pack = validate_form_pack_schema(
        {
            "pack_key": "request_forms",
            "title": "Каталог заявок",
            "forms": [
                {
                    "key": "hardware",
                    "request_kind": "hardware",
                    "title": "Оборудование",
                    "fields": [
                        {
                            "key": "asset_type",
                            "label": "Тип актива",
                            "type": "select",
                            "required": True,
                            "options": [
                                {"value": "printer", "label": "Принтер"},
                                {"value": "scanner", "label": "Сканер"},
                                {"value": "pc", "label": "ПК"},
                            ],
                        },
                        {
                            "key": "inventory_number",
                            "label": "Инвентарный номер",
                            "type": "text",
                            "required": False,
                            "visible_when": {"field": "asset_type", "in": ["printer", "scanner"]},
                        },
                    ],
                }
            ],
        },
        require_version=False,
    )

    visible = validate_form_submission(
        pack,
        form_key="hardware",
        raw_values={
            "asset_type": "scanner",
            "inventory_number": "INV-17",
            "impact_scope": "single_user",
            "work_continuity": "workaround_available",
            "business_importance": "normal",
        },
    )
    hidden = validate_form_submission(
        pack,
        form_key="hardware",
        raw_values={
            "asset_type": "pc",
            "inventory_number": "INV-88",
            "impact_scope": "single_user",
            "work_continuity": "workaround_available",
            "business_importance": "normal",
        },
    )

    assert visible["submitted_values"]["inventory_number"] == "INV-17"
    assert ["asset_type", "inventory_number"] == [item["key"] for item in visible["summary_rows"][:2]]
    assert "impact_scope" in [item["key"] for item in visible["summary_rows"]]
    assert "inventory_number" not in hidden["submitted_values"]
    assert [item["key"] for item in hidden["summary_rows"][:1]] == ["asset_type"]
    assert "impact_scope" in [item["key"] for item in hidden["summary_rows"]]
