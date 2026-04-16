"""
Tests for tool_call_started event creation.

Инвариант: tool_call_started всегда создаётся сервером до отправки run_tool команды.
Корреляция по operation_id (call_id - legacy, не используется для поиска).
"""
import pytest
import asyncio
from unittest.mock import patch
from sqlalchemy import select
from app.db.engine import async_sessionmaker
from app.repos.ticket_events_repo import TicketEventsRepo
from app.repos.operations_repo import OperationsRepo
from app.db.models import TicketEvent
from auth.context import AuthContext, AuthType
from tests.test_helpers import TEST_ECHO_TOOL, create_test_ticket


@pytest.mark.asyncio
async def test_tool_call_started_created_before_command(test_client, test_agent, test_engine):
    """
    T1: tool_call_started создаётся на сервере ДО отправки команды агенту.
    
    Assert:
    - В ticket_events появляется tool_call_started с non-null operation_id
    - Событие создаётся сразу после HTTP call (до получения ответа от агента)
    - event_type='tool_call_started', operation_id совпадает с возвращённым operation_id
    """
    device_id = test_agent.device_id
    ticket_id, _ = await create_test_ticket(test_client, device_id=device_id)
    
    # Запускаем tool (async mode, не ждём ответа от агента)
    tool_resp = await test_client.post("/api/tools/run", json={
        "tool_name": TEST_ECHO_TOOL,
        "params": {"message": "test"},
        "device_id": device_id,
        "ticket_id": ticket_id
    })
    
    assert tool_resp.status == 202  # Accepted (async mode)
    operation_data = await tool_resp.json()
    operation_id = operation_data["operation_id"]
    assert operation_id is not None
    
    # КРИТИЧНО: Небольшая задержка для завершения фоновой задачи создания события
    # (в async mode событие создаётся в asyncio.create_task)
    await asyncio.sleep(0.1)
    
    # КРИТИЧНО: Проверяем что tool_call_started создан СРАЗУ (до ответа от агента)
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        events_repo = TicketEventsRepo(session)
        
        # Получаем все события для тикета
        events = await events_repo.get_events(ticket_id)
        
        # Ищем tool_call_started с нашим operation_id
        started_events = [
            e for e in events 
            if e.event_type == "tool_call_started" and e.operation_id == operation_id
        ]
        
        assert len(started_events) == 1, (
            f"Expected exactly one tool_call_started event with operation_id={operation_id}, "
            f"found {len(started_events)}"
        )
        
        started_event = started_events[0]
        
        # Проверки события
        assert started_event.ticket_id == ticket_id
        assert started_event.device_id == device_id
        assert started_event.operation_id == operation_id
        assert started_event.agent_seq is None  # Server-originated
        assert started_event.event_type == "tool_call_started"
        
        # Проверки payload
        payload = started_event.payload
        assert payload.get("event") == "tool_call_started"
        assert payload.get("tool_name") == TEST_ECHO_TOOL
        assert payload.get("params", {}).get("message") == "test"
        assert payload.get("actor_role") == "support"
        
        # Проверяем что operation существует
        op_repo = OperationsRepo(session)
        operation = await op_repo.get_by_operation_id(operation_id)
        assert operation is not None
        assert operation.operation_id == operation_id
        assert operation.ticket_id == ticket_id


@pytest.mark.asyncio
async def test_tool_call_started_idempotency(test_engine):
    """
    T2: Идемпотентность tool_call_started - повторная вставка не создаёт дубль.
    
    Assert:
    - Первая вставка создаёт событие
    - Вторая вставка с тем же (ticket_id, operation_id, event_type) возвращает None (дубликат)
    - UNIQUE индекс предотвращает дубликаты
    """
    from app.repos.ticket_events_repo import TicketEventsRepo
    from app.db.engine import async_sessionmaker
    import uuid
    
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())
    operation_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())
    
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        # Создаём тикет для теста
        repo = TicketEventsRepo(session)
        await repo.create_ticket(
            ticket_id=ticket_id,
            device_id=device_id,
            title="Test",
            description="Test"
        )
        await session.commit()
    
    # Первая вставка - должна успешно создать событие
    async with session_maker() as session:
        repo = TicketEventsRepo(session)
        result1 = await repo.add_event(
            ticket_id=ticket_id,
            device_id=device_id,
            agent_seq=None,  # Server-originated
            event_type="tool_call_started",
            payload={
                "event": "tool_call_started",
                "tool_name": TEST_ECHO_TOOL,
                "params": {"message": "test"}
            },
            trace_id=trace_id,
            event_id=None,
            operation_id=operation_id
        )
        await session.commit()
        
        assert result1 is not None, "First insert should succeed"
        event_id1, created_at1 = result1
    
    # Вторая вставка с теми же (ticket_id, operation_id, event_type) - должна вернуть None (дубликат)
    async with session_maker() as session:
        repo = TicketEventsRepo(session)
        result2 = await repo.add_event(
            ticket_id=ticket_id,
            device_id=device_id,
            agent_seq=None,
            event_type="tool_call_started",
            payload={
                "event": "tool_call_started",
                "tool_name": TEST_ECHO_TOOL,
                "params": {"message": "test2"}  # Даже с другим payload
            },
            trace_id=str(uuid.uuid4()),  # Даже с другим trace_id
            event_id=None,
            operation_id=operation_id  # Но тот же operation_id
        )
        await session.commit()
        
        assert result2 is None, "Second insert with same operation_id should return None (duplicate)"
    
    # Проверяем что в БД только одно событие
    async with session_maker() as session:
        stmt = select(TicketEvent).where(
            TicketEvent.ticket_id == ticket_id,
            TicketEvent.operation_id == operation_id,
            TicketEvent.event_type == "tool_call_started"
        )
        from sqlalchemy.ext.asyncio import AsyncSession
        result = await session.execute(stmt)
        events = result.scalars().all()
        
        assert len(events) == 1, (
            f"Expected exactly one tool_call_started event, found {len(events)}"
        )
        
        # Проверяем что это первое событие (с оригинальным payload)
        assert events[0].id == event_id1
        assert events[0].payload.get("params", {}).get("message") == "test"


@pytest.mark.asyncio
async def test_tool_call_started_with_different_operation_ids(test_engine):
    """
    T3: Разные operation_id создают разные tool_call_started события.
    
    Assert:
    - Два события с разными operation_id оба создаются успешно
    - UNIQUE индекс не блокирует разные operation_id
    """
    from app.db.engine import get_session
    from app.repos.ticket_events_repo import TicketEventsRepo
    import uuid
    
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())
    operation_id1 = str(uuid.uuid4())
    operation_id2 = str(uuid.uuid4())
    trace_id1 = str(uuid.uuid4())
    trace_id2 = str(uuid.uuid4())
    
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        # Создаём тикет
        repo = TicketEventsRepo(session)
        await repo.create_ticket(
            ticket_id=ticket_id,
            device_id=device_id,
            title="Test",
            description="Test"
        )
        await session.commit()
    
    # Первое событие с operation_id1
    async with session_maker() as session:
        repo = TicketEventsRepo(session)
        result1 = await repo.add_event(
            ticket_id=ticket_id,
            device_id=device_id,
            agent_seq=None,
            event_type="tool_call_started",
            payload={"event": "tool_call_started", "tool_name": TEST_ECHO_TOOL},
            trace_id=trace_id1,
            event_id=None,
            operation_id=operation_id1
        )
        await session.commit()
        assert result1 is not None
    
    # Второе событие с operation_id2 (должно успешно создать)
    async with session_maker() as session:
        repo = TicketEventsRepo(session)
        result2 = await repo.add_event(
            ticket_id=ticket_id,
            device_id=device_id,
            agent_seq=None,
            event_type="tool_call_started",
            payload={"event": "tool_call_started", "tool_name": TEST_ECHO_TOOL},
            trace_id=trace_id2,
            event_id=None,
            operation_id=operation_id2
        )
        await session.commit()
        assert result2 is not None
    
    # Проверяем что в БД оба события
    async with session_maker() as session:
        stmt = select(TicketEvent).where(
            TicketEvent.ticket_id == ticket_id,
            TicketEvent.event_type == "tool_call_started"
        )
        result = await session.execute(stmt)
        events = result.scalars().all()
        
        assert len(events) == 2, f"Expected 2 events, found {len(events)}"
        
        operation_ids = {e.operation_id for e in events}
        assert operation_id1 in operation_ids
        assert operation_id2 in operation_ids


@pytest.mark.asyncio
async def test_tool_call_started_uses_auth_context_actor_role(test_client, test_agent, test_engine):
    device_id = test_agent.device_id
    ticket_id, _ = await create_test_ticket(test_client, device_id=device_id)

    async def _agent_auth_context(_request):
        return AuthContext(
            actor_id=device_id,
            actor_role="agent",
            auth_type=AuthType.AGENT_TOKEN,
            token="test-agent-tool-role",
        )

    with patch("auth.middleware.extract_auth_context", new=_agent_auth_context):
        tool_resp = await test_client.post(
            "/api/tools/run",
            headers={"Authorization": "Bearer test-agent-tool-role"},
            json={
                "tool_name": "screen.collect",
                "params": {},
                "device_id": device_id,
                "ticket_id": ticket_id,
            },
        )

    assert tool_resp.status == 202
    operation_id = (await tool_resp.json())["operation_id"]

    await asyncio.sleep(0.1)

    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        events_repo = TicketEventsRepo(session)
        events = await events_repo.get_events(ticket_id)
        started_event = next(
            e
            for e in events
            if e.event_type == "tool_call_started" and e.operation_id == operation_id
        )

        assert started_event.payload.get("actor_role") == "agent"
