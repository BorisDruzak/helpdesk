"""
Helper functions for integration tests.
"""
import asyncio
import time
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy import select
from app.db.engine import async_sessionmaker
from app.repos.operations_repo import OperationsRepo
from app.db.models import TicketEvent, Operation
import pytest

pytestmark = pytest.mark.db_cleanup("full")

TEST_ECHO_TOOL = "test_echo.echo"
TEST_FAIL_TOOL = "test_fail.fail"
TEST_SLOW_ECHO_TOOL = "test_slow_echo.slow_echo"


async def find_operation_by_call_id(test_engine: AsyncEngine, ticket_id: str, call_id: str) -> Optional[str]:
    """
    Находит operation_id по call_id через ticket_events.
    
    Args:
        test_engine: Тестовый SQLAlchemy engine
        ticket_id: ID тикета
        call_id: ID вызова из handle_tools_run
    
    Returns:
        operation_id или None если не найден
    """
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        # Ищем событие tool_call_started с call_id
        stmt = select(TicketEvent).where(
            TicketEvent.ticket_id == ticket_id,
            TicketEvent.event_type == "tool_call_started",
            TicketEvent.payload['call_id'].astext == call_id
        )
        result = await session.execute(stmt)
        event = result.scalar_one_or_none()
        
        if event and event.operation_id:
            return event.operation_id
        
        return None


async def wait_for_operation_status(
    test_engine: AsyncEngine,
    operation_id: str,
    expected_statuses: list[str],
    timeout: float = 10.0
) -> str:
    """
    Ждет одного из expected_statuses через DB polling.
    
    Args:
        test_engine: Тестовый SQLAlchemy engine
        operation_id: ID операции
        expected_statuses: Список ожидаемых статусов
        timeout: Максимальное время ожидания в секундах
    
    Returns:
        str: Текущий статус операции
    
    Raises:
        TimeoutError: Если операция не достигла ожидаемого статуса за timeout
    """
    session_maker = async_sessionmaker(test_engine)
    start = time.time()
    backoff = 0.1
    
    while time.time() - start < timeout:
        async with session_maker() as session:
            repo = OperationsRepo(session)
            operation = await repo.get_by_operation_id(operation_id)
            
            if operation and operation.status in expected_statuses:
                return operation.status
        
        await asyncio.sleep(backoff)
        backoff = min(backoff * 1.5, 0.5)
    
    # Возвращаем текущий статус даже если не достигли ожидаемого
    async with session_maker() as session:
        repo = OperationsRepo(session)
        operation = await repo.get_by_operation_id(operation_id)
        current_status = operation.status if operation else "not_found"
    
    raise TimeoutError(
        f"Operation {operation_id} did not reach one of {expected_statuses} in {timeout}s. "
        f"Current status: {current_status}"
    )


async def wait_for_operation_terminal(test_engine: AsyncEngine, operation_id: str, timeout: float = 10.0) -> str:
    """
    Ждет terminal статуса операции через DB polling (стабильнее чем HTTP endpoint).
    
    Args:
        test_engine: Тестовый SQLAlchemy engine
        operation_id: ID операции
        timeout: Максимальное время ожидания в секундах
    
    Returns:
        str: Terminal статус операции
    
    Raises:
        TimeoutError: Если операция не достигла terminal статуса за timeout
    """
    session_maker = async_sessionmaker(test_engine)
    start = time.time()
    backoff = 0.1  # Начальный backoff
    
    while time.time() - start < timeout:
        async with session_maker() as session:
            repo = OperationsRepo(session)
            operation = await repo.get_by_operation_id(operation_id)
            
            if operation and operation.status in ["succeeded", "failed", "timed_out", "canceled"]:
                return operation.status
        
        await asyncio.sleep(backoff)
        backoff = min(backoff * 1.5, 0.5)  # Exponential backoff до 0.5s
    
    raise TimeoutError(
        f"Operation {operation_id} did not reach terminal status in {timeout}s"
    )


async def wait_for_ticket_event(
    test_engine: AsyncEngine,
    *,
    ticket_id: str,
    operation_id: str,
    event_type: str,
    timeout: float = 10.0,
) -> TicketEvent:
    """Ждёт, пока server-side ticket event материализуется в БД."""
    session_maker = async_sessionmaker(test_engine)
    start = time.time()
    backoff = 0.1

    while time.time() - start < timeout:
        async with session_maker() as session:
            stmt = (
                select(TicketEvent)
                .where(
                    TicketEvent.ticket_id == ticket_id,
                    TicketEvent.operation_id == operation_id,
                    TicketEvent.event_type == event_type,
                )
                .order_by(TicketEvent.created_at.desc(), TicketEvent.id.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            event = result.scalar_one_or_none()
            if event is not None:
                return event

        await asyncio.sleep(backoff)
        backoff = min(backoff * 1.5, 0.5)

    raise TimeoutError(
        f"Ticket event {event_type} for operation {operation_id} in ticket {ticket_id} "
        f"did not appear in {timeout}s"
    )


async def create_test_ticket(client, device_id: str, user_display_name: str = "Test User"):
    """
    Создает тестовый ticket и возвращает ticket_id, device_id.
    
    Args:
        client: aiohttp test client
        device_id: Device ID (обязательно)
        user_display_name: Имя пользователя (по умолчанию "Test User")
    
    Returns:
        tuple: (ticket_id, device_id)
    """
    resp = await client.post("/api/tickets/create", json={
        "title": "Test ticket",
        "description": "Test description",
        "device_id": device_id,
        "user_display_name": user_display_name
    })
    assert resp.status == 200, f"Failed to create ticket: {await resp.text()}"
    data = await resp.json()
    ticket_id = data["ticket"]["ticket_id"]
    return ticket_id, device_id
