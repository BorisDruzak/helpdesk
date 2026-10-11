"""A calendar change after preview cannot consume a scenario publish token."""
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.db.models import TicketBusinessCalendar, TicketSlaPolicy
from tests.test_request_scenario_publication_api import ready, preview
from tests.test_request_scenario_admin_api import BASE, ADMIN

pytestmark = [pytest.mark.db_cleanup("full"), pytest.mark.light_app]


@pytest.mark.asyncio
async def test_calendar_change_invalidates_publication_confirmation(test_client_light, test_engine):
    identifier, definition = await ready(test_engine)
    async with async_sessionmaker(test_engine, expire_on_commit=False)() as session:
        calendar = TicketBusinessCalendar(code=definition["scenario_key"], name="Test calendar", timezone="UTC")
        session.add(calendar)
        await session.flush()
        policy = await session.scalar(select(TicketSlaPolicy).where(TicketSlaPolicy.name == definition["scenario_key"]))
        policy.calendar_id = calendar.id
        await session.commit()
        calendar_id = calendar.id
    body = await preview(test_client_light, identifier)
    async with async_sessionmaker(test_engine)() as session:
        calendar = await session.get(TicketBusinessCalendar, calendar_id)
        calendar.timezone = "Asia/Yekaterinburg"
        await session.commit()
    response = await test_client_light.post(BASE + "/scenarios/" + identifier + "/publish", headers=ADMIN, json=body)
    assert response.status == 409
