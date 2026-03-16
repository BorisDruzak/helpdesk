"""
Integration tests for cancel operations functionality.
"""
import pytest
import asyncio
from app.db.engine import async_sessionmaker
from app.repos.operations_repo import OperationsRepo
from app.repos.ticket_events_repo import TicketEventsRepo
from tests.test_helpers import (
    wait_for_operation_terminal,
    wait_for_operation_status,
    create_test_ticket,
    find_operation_by_call_id
)


@pytest.mark.asyncio
async def test_cancel_running_operation(test_client, test_agent, test_engine):
    """T1: Cancel running operation → canceled."""
    # 1. Создать ticket
    device_id = test_agent.device_id
    ticket_id, _ = await create_test_ticket(test_client, device_id=device_id)
    
    # 2. Запустить slow_echo (с delay=2)
    tool_resp = await test_client.post("/api/tools/run", json={
        "tool_name": "slow_echo",  # Тестовый tool с delay
        "params": {"message": "hi", "delay": 2},
        "device_id": device_id,
        "ticket_id": ticket_id
    })
    assert tool_resp.status == 200
    operation_data = await tool_resp.json()
    call_id = operation_data["call_id"]
    
    # 3. Найти operation_id
    operation_id = await find_operation_by_call_id(test_engine, ticket_id, call_id)
    assert operation_id is not None
    
    # 4. Дождаться accepted/running
    await wait_for_operation_status(test_engine, operation_id, ["accepted", "running"], timeout=5)
    
    # 5. Cancel операцию
    cancel_resp = await test_client.post(f"/api/operations/{operation_id}/cancel", json={
        "reason": "User requested",
        "actor_role": "user"
    })
    assert cancel_resp.status == 200
    cancel_data = await cancel_resp.json()
    assert cancel_data["status"] == "ok"
    cancel_operation_id = cancel_data["cancel_operation_id"]
    
    # 6. Дождаться canceled
    target_status = await wait_for_operation_terminal(test_engine, operation_id, timeout=10)
    assert target_status == "canceled"
    
    # 7. Проверки
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        op_repo = OperationsRepo(session)
        target_op = await op_repo.get_by_operation_id(operation_id)
        cancel_op = await op_repo.get_by_operation_id(cancel_operation_id)
        
        assert target_op.status == "canceled"
        assert target_op.status_before_cancel is None  # Очищено после успешного cancel
        assert target_op.canceled_at is not None
        
        assert cancel_op.status == "succeeded"
        assert cancel_op.kind == "cancel_operation"
        assert cancel_op.cancel_target_operation_id == operation_id
        
        # Проверка событий
        events_repo = TicketEventsRepo(session)
        events = await events_repo.get_events(ticket_id)
        event_types = [e.event_type for e in events]
        assert "op_cancel_requested" in event_types
        assert "op_canceled" in event_types


@pytest.mark.asyncio
async def test_cancel_idempotent(test_client, test_agent, test_engine):
    """T3: Cancel idempotent on cancel_requested."""
    # 1. Создать ticket и операцию
    device_id = test_agent.device_id
    ticket_id, _ = await create_test_ticket(test_client, device_id=device_id)
    
    tool_resp = await test_client.post("/api/tools/run", json={
        "tool_name": "slow_echo",
        "params": {"message": "hi", "delay": 2},
        "device_id": device_id,
        "ticket_id": ticket_id
    })
    assert tool_resp.status == 200
    operation_data = await tool_resp.json()
    call_id = operation_data["call_id"]
    operation_id = await find_operation_by_call_id(test_engine, ticket_id, call_id)
    assert operation_id is not None
    
    # 2. Дождаться running
    await wait_for_operation_status(test_engine, operation_id, ["accepted", "running"], timeout=5)
    
    # 3. Запросить cancel дважды подряд
    cancel_resp1 = await test_client.post(f"/api/operations/{operation_id}/cancel", json={
        "reason": "First cancel",
        "actor_role": "user"
    })
    assert cancel_resp1.status == 200
    cancel_data1 = await cancel_resp1.json()
    cancel_operation_id1 = cancel_data1["cancel_operation_id"]
    
    # Второй запрос должен вернуть тот же cancel_operation_id
    cancel_resp2 = await test_client.post(f"/api/operations/{operation_id}/cancel", json={
        "reason": "Second cancel",
        "actor_role": "user"
    })
    assert cancel_resp2.status == 200
    cancel_data2 = await cancel_resp2.json()
    assert cancel_data2["status"] == "ok"
    assert cancel_data2["cancel_operation_id"] == cancel_operation_id1  # Тот же cancel-op
    
    # 4. Проверки: target-op остается cancel_requested до результата
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        op_repo = OperationsRepo(session)
        target_op = await op_repo.get_by_operation_id(operation_id)
        assert target_op.status == "cancel_requested"
        assert target_op.active_cancel_operation_id == cancel_operation_id1


@pytest.mark.asyncio
async def test_cancel_terminal_operation(test_client, test_agent, test_engine):
    """T4: Cancel terminal operation → 409/no-op."""
    # 1. Создать ticket и операцию
    device_id = test_agent.device_id
    ticket_id, _ = await create_test_ticket(test_client, device_id=device_id)
    
    tool_resp = await test_client.post("/api/tools/run", json={
        "tool_name": "echo",
        "params": {"message": "hi"},
        "device_id": device_id,
        "ticket_id": ticket_id
    })
    assert tool_resp.status == 200
    operation_data = await tool_resp.json()
    call_id = operation_data["call_id"]
    operation_id = await find_operation_by_call_id(test_engine, ticket_id, call_id)
    assert operation_id is not None
    
    # 2. Дождаться succeeded
    terminal_status = await wait_for_operation_terminal(test_engine, operation_id, timeout=10)
    assert terminal_status == "succeeded"
    
    # 3. Cancel → 409
    cancel_resp = await test_client.post(f"/api/operations/{operation_id}/cancel", json={
        "reason": "Too late",
        "actor_role": "user"
    })
    assert cancel_resp.status == 409
    cancel_data = await cancel_resp.json()
    assert cancel_data["status"] == "noop"
    assert cancel_data["reason"] == "already_terminal"
    
    # 4. Проверки: статус не меняется
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        op_repo = OperationsRepo(session)
        operation = await op_repo.get_by_operation_id(operation_id)
        assert operation.status == "succeeded"


@pytest.mark.asyncio
async def test_cancel_request_race(test_client, test_agent, test_engine):
    """T5: Two parallel cancel requests → one cancel-op (idempotency)."""
    # 1. Создать операцию
    device_id = test_agent.device_id
    ticket_id, _ = await create_test_ticket(test_client, device_id=device_id)
    
    tool_resp = await test_client.post("/api/tools/run", json={
        "tool_name": "slow_echo",
        "params": {"message": "hi", "delay": 2},
        "device_id": device_id,
        "ticket_id": ticket_id
    })
    assert tool_resp.status == 200
    operation_data = await tool_resp.json()
    call_id = operation_data["call_id"]
    operation_id = await find_operation_by_call_id(test_engine, ticket_id, call_id)
    assert operation_id is not None
    
    await wait_for_operation_status(test_engine, operation_id, ["accepted", "running"], timeout=5)
    
    # 2. Отправить два параллельных cancel запроса
    async def cancel_request():
        resp = await test_client.post(f"/api/operations/{operation_id}/cancel", json={
            "reason": "Race test",
            "actor_role": "user"
        })
        return await resp.json()
    
    results = await asyncio.gather(cancel_request(), cancel_request())
    
    # 3. Проверки: должен получиться один cancel-op (или два, но второй no-op)
    # Оба запроса должны вернуть один и тот же cancel_operation_id
    cancel_op_ids = [r.get("cancel_operation_id") for r in results if r.get("status") == "ok"]
    assert len(cancel_op_ids) > 0
    # Все cancel_op_ids должны быть одинаковыми
    assert len(set(cancel_op_ids)) == 1, f"Expected single cancel_op_id, got: {cancel_op_ids}"
    
    # target-op.active_cancel_operation_id установлен
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        op_repo = OperationsRepo(session)
        target_op = await op_repo.get_by_operation_id(operation_id)
        assert target_op.active_cancel_operation_id == cancel_op_ids[0]


@pytest.mark.asyncio
async def test_cancel_after_completion_race(test_client, test_agent, test_engine):
    """T6: Cancel after operation completes → no rollback to incorrect status."""
    # 1. Запустить echo (быстрая операция)
    device_id = test_agent.device_id
    ticket_id, _ = await create_test_ticket(test_client, device_id=device_id)
    
    tool_resp = await test_client.post("/api/tools/run", json={
        "tool_name": "echo",
        "params": {"message": "hi"},
        "device_id": device_id,
        "ticket_id": ticket_id
    })
    assert tool_resp.status == 200
    operation_data = await tool_resp.json()
    call_id = operation_data["call_id"]
    operation_id = await find_operation_by_call_id(test_engine, ticket_id, call_id)
    assert operation_id is not None
    
    # 2. Почти сразу дождаться terminal (succeeded)
    terminal_status = await wait_for_operation_terminal(test_engine, operation_id, timeout=10)
    assert terminal_status == "succeeded"
    
    # 3. Параллельно отправить cancel
    cancel_resp = await test_client.post(f"/api/operations/{operation_id}/cancel", json={
        "reason": "Too late",
        "actor_role": "user"
    })
    
    # 4. Проверки: target остается succeeded (не перезаписывается)
    assert cancel_resp.status == 409  # Conflict - terminal operation
    
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        op_repo = OperationsRepo(session)
        target_op = await op_repo.get_by_operation_id(operation_id)
        assert target_op.status == "succeeded"  # НЕ перезаписан
        # НЕТ rollback в некорректный статус


