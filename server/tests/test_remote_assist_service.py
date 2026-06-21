import uuid

import pytest
from sqlalchemy import func, select

from app.db.engine import async_sessionmaker
from app.db.models import RemoteAccessSession, Ticket
from remote_assist.service import RemoteAssistError, RemoteAssistService


pytestmark = pytest.mark.db_cleanup("agent_runtime")

@pytest.mark.asyncio
async def test_remote_assist_rejects_ticket_without_requester_scope(test_engine):
    device_id = str(uuid.uuid4())
    ticket_id = str(uuid.uuid4())
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id=device_id,
                title="Remote Assist under-scoped ticket",
                description="Remote Assist consent must be requester-scoped.",
                status="in_progress",
                requester_id="legacy-requester",
            )
        )
        await session.commit()

        with pytest.raises(RemoteAssistError) as exc_info:
            await RemoteAssistService(session).request_session(
                state=object(),
                ticket_id=ticket_id,
                device_id=device_id,
                operator_id="support-test",
                requester_id=None,
                mode="view_only",
                reason="needs approval",
                duration_minutes=5,
            )

        assert exc_info.value.error_code == "REQUESTER_SCOPE_REQUIRED"
        count = await session.scalar(select(func.count()).select_from(RemoteAccessSession))
        assert count == 0
