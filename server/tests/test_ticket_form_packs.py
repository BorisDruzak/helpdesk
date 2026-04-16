import uuid

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import ServerConfig, Ticket, TicketFormPack
from app.repos.ticket_form_packs_repo import TICKET_FORM_PREFERRED_KEY_PREFIX


def _admin_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-ui-admin-token"}


@pytest.mark.asyncio
async def test_public_ticket_forms_current_returns_builtin_catalog(test_client, test_engine):
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

    response = await test_client.get("/public_api/ticket_forms/current")
    assert response.status == 200, await response.text()
    data = await response.json()
    assert data["status"] == "ok"
    pack = data["pack"]
    assert pack["pack_key"] == "request_forms"
    form_keys = {form["key"] for form in pack.get("forms") or []}
    assert {"breakage", "access", "printer", "site_system"} <= form_keys


@pytest.mark.asyncio
async def test_admin_can_save_ticket_form_pack_and_switch_current_version(test_client):
    response = await test_client.post(
        "/api/ticket_forms/packs/save",
        json={
            "pack": {
                "pack_key": "request_forms",
                "version": "1.0.1",
                "title": "Каталог заявок",
                "description": "Тестовая версия каталога",
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
            "make_preferred": True,
        },
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert response.status == 200, await response.text()

    current_response = await test_client.get(
        "/api/ticket_forms/current?pack_key=request_forms",
        headers=_admin_headers(),
    )
    assert current_response.status == 200, await current_response.text()
    current_data = await current_response.json()
    assert current_data["status"] == "ok"
    assert current_data["pack"]["version"] == "1.0.1"
    assert current_data["pack"]["forms"][0]["fields"][0]["key"] == "room"


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

    assert ticket.ticket_type == "printer"
    custom_fields = ticket.custom_fields or {}
    assert custom_fields["request_kind"] == "printer"
    assert custom_fields["request_form_key"] == "printer"
    assert custom_fields["request_form_data"]["room"] == "214"
    assert custom_fields["request_form_data"]["printer_model"] == "HP LaserJet"
