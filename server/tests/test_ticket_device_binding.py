from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Ticket, TicketEvent
from app.repos import DevicesRepo
from app.repos.auth_tokens_repo import AuthTokensRepo
from auth.rate_limit import reset_rate_limits
from tickets import public_ticket_handlers
from tickets.public_access import is_public_unbound_ticket, set_public_access_code


pytestmark = pytest.mark.db_cleanup("tickets")

@pytest.mark.asyncio
async def test_staff_can_bind_public_ticket_to_existing_device(test_client, test_engine):
    create_response = await test_client.post(
        "/public_api/tickets/create",
        json={
            "title": "Веб-заявка",
            "description": "Проверка привязки к агенту",
            "user_display_name": "Веб пользователь",
            "urgency": False,
            "importance": False,
            "urgency_reason": "Не срочно",
            "importance_reason": "Обычная проверка",
            "requester_profile": {
                "full_name": "Тестовый Пользователь",
                "building": "А",
                "room": "101",
                "phone": "+7 900 000 00 00",
            },
        },
    )
    assert create_response.status == 200, await create_response.text()
    ticket_id = (await create_response.json())["ticket"]["ticket_id"]

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = "device-bind-001"
    async with session_maker() as session:
        devices_repo = DevicesRepo(session)
        await devices_repo.ensure_device_exists(device_id)
        await session.commit()

    bind_response = await test_client.post(
        f"/api/tickets/{ticket_id}/device",
        json={"device_id": device_id, "reason": "manual_bind"},
        headers={"Authorization": "Bearer test-ui-support-token"},
    )
    assert bind_response.status == 200, await bind_response.text()
    payload = await bind_response.json()
    assert payload["ticket"]["device_id"] == device_id
    assert payload["ticket"]["public_ticket_unbound"] is False

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        assert ticket is not None
        assert ticket.device_id == device_id
        assert is_public_unbound_ticket(ticket) is False

        events = (
            await session.execute(
                TicketEvent.__table__.select().where(TicketEvent.ticket_id == ticket_id)
            )
        ).mappings().all()
        device_events = [event for event in events if event["event_type"] == "device_changed"]
        assert device_events
        assert device_events[-1]["payload"]["device_id"] == device_id


@pytest.mark.asyncio
async def test_bind_device_rejects_unknown_device(test_client):
    create_response = await test_client.post(
        "/public_api/tickets/create",
        json={
            "title": "Веб-заявка",
            "description": "Проверка ошибки привязки",
            "user_display_name": "Веб пользователь",
            "urgency": False,
            "importance": False,
            "urgency_reason": "Не срочно",
            "importance_reason": "Обычная проверка",
        },
    )
    assert create_response.status == 200, await create_response.text()
    ticket_id = (await create_response.json())["ticket"]["ticket_id"]

    bind_response = await test_client.post(
        f"/api/tickets/{ticket_id}/device",
        json={"device_id": "missing-device"},
        headers={"Authorization": "Bearer test-ui-support-token"},
    )
    assert bind_response.status == 400, await bind_response.text()
    payload = await bind_response.json()
    assert payload["error"] == "validation_error"
    assert payload["details"]["device_id"] == "unknown device_id"


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_public_ticket_authorize_rate_limits_invalid_code_attempts(monkeypatch):
    ticket_id = str(uuid.uuid4())
    ticket = SimpleNamespace(
        ticket_id=ticket_id,
        requester_id=f"public:{ticket_id}",
        custom_fields=set_public_access_code({}, "GOODCODE"),
    )

    class FakeRequest:
        def __init__(self, code: str):
            self.match_info = {"ticket_id": ticket_id}
            self.headers = {}
            self.remote = "198.51.100.10"
            self.app = {"state": object()}
            self._code = code

        async def json(self):
            return {"code": self._code}

    class FakeSessionContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeTicketRepo:
        def __init__(self, _session):
            pass

        async def get_ticket(self, _ticket_id):
            return ticket

    class FakeAuthService:
        def __init__(self, _state):
            pass

        async def generate_ticket_public_session_token(self, **_kwargs):
            return "public-token"

    monkeypatch.setattr(public_ticket_handlers, "get_session", lambda: FakeSessionContext())
    monkeypatch.setattr(public_ticket_handlers, "TicketEventsRepo", FakeTicketRepo)
    monkeypatch.setattr(public_ticket_handlers, "AuthService", FakeAuthService)

    reset_rate_limits()
    try:
        valid_response = await public_ticket_handlers.handle_public_ticket_authorize(
            FakeRequest("GOODCODE")
        )
        assert valid_response.status == 200
        reset_rate_limits()

        statuses = []
        for index in range(6):
            response = await public_ticket_handlers.handle_public_ticket_authorize(
                FakeRequest(f"BAD{index:05d}")
            )
            statuses.append(response.status)

        assert statuses[:5] == [403, 403, 403, 403, 403]
        assert statuses[5] == 429
    finally:
        reset_rate_limits()


@pytest.mark.asyncio
@pytest.mark.parametrize("terminal_status", ["closed", "canceled"])
async def test_public_ticket_session_rejects_terminal_ticket_even_if_not_revoked(test_engine, terminal_status):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    raw_token = f"public-session-{uuid.uuid4().hex}"
    now = datetime.now(timezone.utc)

    async with session_maker() as session:
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id=None,
                title="Closed public session",
                description="Closed ticket token should fail closed.",
                status="new",
                requester_id="public:closed-session",
            )
        )
        await session.commit()

        repo = AuthTokensRepo(session)
        await repo.create_ticket_public_session(
            token=raw_token,
            ticket_id=ticket_id,
            actor_id="public:closed-session",
            expires_at=now + timedelta(hours=1),
        )
        assert await repo.verify_ticket_public_session(raw_token) is not None

        ticket = await session.get(Ticket, ticket_id)
        assert ticket is not None
        ticket.status = terminal_status
        if terminal_status == "closed":
            ticket.closed_at = now
        else:
            ticket.canceled_at = now
        await session.commit()

    async with session_maker() as session:
        repo = AuthTokensRepo(session)
        assert await repo.verify_ticket_public_session(raw_token) is None
