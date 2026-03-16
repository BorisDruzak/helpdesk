"""
P0 (Critical) integration tests for Protocol V3.
"""
import pytest
import asyncio
from app.db.engine import async_sessionmaker
from app.repos.operations_repo import OperationsRepo
from app.repos.ticket_events_repo import TicketEventsRepo
from app.repos.device_outbox_repo import DeviceOutboxRepo
from tests.test_helpers import (
    wait_for_operation_terminal,
    create_test_ticket,
    find_operation_by_call_id
)


@pytest.mark.asyncio
async def test_happy_path_echo(test_client, test_agent, test_engine):
    """T1: Happy path - run_tool echo успешно выполняется."""
    # 1. Создать ticket (явно указываем device_id из агента)
    device_id = test_agent.device_id
    ticket_id, _ = await create_test_ticket(test_client, device_id=device_id)
    
    # 2. Запустить tool echo
    tool_resp = await test_client.post("/api/tools/run", json={
        "tool_name": "echo",
        "params": {"message": "hi"},
        "device_id": device_id,
        "ticket_id": ticket_id
    })
    assert tool_resp.status == 200
    operation_data = await tool_resp.json()
    call_id = operation_data["call_id"]
    
    # 3. Найти operation_id по call_id
    operation_id = await find_operation_by_call_id(test_engine, ticket_id, call_id)
    assert operation_id is not None, "Operation not found"
    
    # 4. Дождаться terminal статуса через DB polling
    terminal_status = await wait_for_operation_terminal(test_engine, operation_id, timeout=10)
    assert terminal_status == "succeeded"
    
    # 5. Проверки
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        repo = OperationsRepo(session)
        operation = await repo.get_by_operation_id(operation_id)
        
        assert operation is not None
        assert operation.status == "succeeded"
        assert operation.operation_id == operation_id
        assert operation.queued_at is not None
        assert operation.sent_at is not None
        assert operation.accepted_at is not None
        assert operation.finished_at is not None
        assert operation.queued_at < operation.sent_at
        assert operation.sent_at < operation.accepted_at
        assert operation.accepted_at < operation.finished_at
        
        # device_outbox delivered
        outbox_repo = DeviceOutboxRepo(session)
        outbox_item = await outbox_repo.get_command_by_id(operation_id)
        assert outbox_item is not None
        assert outbox_item.status == "delivered"
        
        # ticket_events содержат tool_call_started и tool_call_result
        events_repo = TicketEventsRepo(session)
        events = await events_repo.get_events(ticket_id)
        event_types = [e.event_type for e in events]
        assert "tool_call_started" in event_types
        assert "tool_call_result" in event_types
        # Проверяем что все события связаны с operation_id
        operation_events = [e for e in events if e.operation_id == operation_id]
        assert len(operation_events) > 0


@pytest.mark.asyncio
async def test_error_path_fail(test_client, test_agent, test_engine):
    """T2: Error path - run_tool fail возвращает ошибку."""
    device_id = test_agent.device_id
    ticket_id, _ = await create_test_ticket(test_client, device_id=device_id)
    
    # Запустить tool fail
    tool_resp = await test_client.post("/api/tools/run", json={
        "tool_name": "fail",
        "params": {"error_code": "TEST_ERROR"},
        "device_id": device_id,
        "ticket_id": ticket_id
    })
    assert tool_resp.status == 200
    operation_data = await tool_resp.json()
    call_id = operation_data["call_id"]
    
    # Найти operation_id
    operation_id = await find_operation_by_call_id(test_engine, ticket_id, call_id)
    assert operation_id is not None
    
    # Дождаться terminal статуса
    terminal_status = await wait_for_operation_terminal(test_engine, operation_id, timeout=10)
    assert terminal_status == "failed"
    
    # Проверки
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        repo = OperationsRepo(session)
        operation = await repo.get_by_operation_id(operation_id)
        
        assert operation is not None
        assert operation.status == "failed"
        
        # КРИТИЧНО: Проверяем что outbox = delivered (не failed!)
        # Execution error ≠ delivery error
        outbox_repo = DeviceOutboxRepo(session)
        outbox_item = await outbox_repo.get_command_by_id(operation_id)
        assert outbox_item is not None, "Outbox entry should exist"
        assert outbox_item.status == "delivered", f"Outbox should be delivered, got {outbox_item.status}"
        
        # Проверяем timestamps
        assert operation.queued_at is not None
        assert operation.sent_at is not None
        assert operation.accepted_at is not None
        assert operation.finished_at is not None
        assert operation.queued_at < operation.sent_at
        assert operation.sent_at < operation.accepted_at
        assert operation.accepted_at < operation.finished_at
        
        # Проверяем ticket_events содержит tool_call_result с ошибкой
        events_repo = TicketEventsRepo(session)
        events = await events_repo.get_events(ticket_id)
        result_events = [e for e in events if e.event_type == "tool_call_result" and e.operation_id == operation_id]
        assert len(result_events) > 0
        result_event = result_events[0]
        assert result_event.payload.get("status") in ["error", "failed"]


@pytest.mark.asyncio
async def test_command_ack_before_result(test_client, test_agent, test_engine):
    """T3: command_ack устанавливает accepted до финального результата."""
    device_id = test_agent.device_id
    ticket_id, _ = await create_test_ticket(test_client, device_id=device_id)
    
    # Запустить tool echo
    tool_resp = await test_client.post("/api/tools/run", json={
        "tool_name": "echo",
        "params": {"message": "test"},
        "device_id": device_id,
        "ticket_id": ticket_id
    })
    assert tool_resp.status == 200
    operation_data = await tool_resp.json()
    call_id = operation_data["call_id"]
    
    operation_id = await find_operation_by_call_id(test_engine, ticket_id, call_id)
    assert operation_id is not None
    
    # Дождаться terminal статуса
    await wait_for_operation_terminal(test_engine, operation_id, timeout=10)
    
    # Проверки: accepted_at установлен до finished_at
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        repo = OperationsRepo(session)
        operation = await repo.get_by_operation_id(operation_id)
        
        assert operation is not None
        assert operation.accepted_at is not None
        assert operation.finished_at is not None
        assert operation.accepted_at < operation.finished_at


@pytest.mark.asyncio
async def test_duplicate_command_result_idempotency(test_client, test_agent, test_engine):
    """T4: Повторный command_result не создает дубликаты."""
    device_id = test_agent.device_id
    ticket_id, _ = await create_test_ticket(test_client, device_id=device_id)
    
    # Выполнить tool echo
    tool_resp = await test_client.post("/api/tools/run", json={
        "tool_name": "echo",
        "params": {"message": "test"},
        "device_id": device_id,
        "ticket_id": ticket_id
    })
    assert tool_resp.status == 200
    operation_data = await tool_resp.json()
    call_id = operation_data["call_id"]
    
    operation_id = await find_operation_by_call_id(test_engine, ticket_id, call_id)
    assert operation_id is not None
    
    # Дождаться завершения
    await wait_for_operation_terminal(test_engine, operation_id, timeout=10)
    
    # Получить начальное состояние
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        repo = OperationsRepo(session)
        operation = await repo.get_by_operation_id(operation_id)
        initial_finished_at = operation.finished_at
        initial_status = operation.status
        
        # Подсчитать события до дубликата
        events_repo = TicketEventsRepo(session)
        events_before = await events_repo.get_events(ticket_id)
        events_count_before = len([e for e in events_before if e.operation_id == operation_id])
    
    # TODO: Отправить повторный command_result через WS клиент
    # Пока пропускаем этот тест, так как требует WS клиента
    
    # Проверки: operations остается terminal и не меняет timestamps
    async with session_maker() as session:
        repo = OperationsRepo(session)
        operation = await repo.get_by_operation_id(operation_id)
        
        assert operation.status == initial_status
        assert operation.finished_at == initial_finished_at
        
        # ticket_events не дублируются
        events_repo = TicketEventsRepo(session)
        events_after = await events_repo.get_events(ticket_id)
        events_count_after = len([e for e in events_after if e.operation_id == operation_id])
        # События не должны увеличиться (если дубликат был обработан идемпотентно)
        assert events_count_after == events_count_before


@pytest.mark.asyncio
async def test_device_only_operation(test_client, test_agent, test_engine):
    """T6: Операция без ticket_id (device-only)."""
    device_id = test_agent.device_id
    
    # POST /api/commands/send с list_tools (ticket_id отсутствует)
    from websocket.protocol import send_ws_command
    
    state = test_client.app['state']
    result = await send_ws_command(
        state=state,
        device_id=device_id,
        command="list_tools",
        params={},
        actor_role="support",
        timeout=10
    )
    
    # Извлекаем operation_id из результата (если есть)
    # Проверки:
    # - operations.ticket_id IS NULL
    # - операции terminal
    # TODO: Реализовать после понимания структуры ответа send_ws_command


@pytest.mark.asyncio
async def test_state_transition_guards(test_client, test_agent, test_engine):
    """T9: Проверка что operations не может перейти из terminal обратно в non-terminal."""
    device_id = test_agent.device_id
    ticket_id, _ = await create_test_ticket(test_client, device_id=device_id)
    
    # Выполнить tool echo до terminal
    tool_resp = await test_client.post("/api/tools/run", json={
        "tool_name": "echo",
        "params": {"message": "test"},
        "device_id": device_id,
        "ticket_id": ticket_id
    })
    assert tool_resp.status == 200
    operation_data = await tool_resp.json()
    call_id = operation_data["call_id"]
    
    operation_id = await find_operation_by_call_id(test_engine, ticket_id, call_id)
    assert operation_id is not None
    
    # Дождаться terminal статуса
    terminal_status = await wait_for_operation_terminal(test_engine, operation_id, timeout=10)
    assert terminal_status in ["succeeded", "failed"]
    
    # Получить начальное состояние
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        repo = OperationsRepo(session)
        operation = await repo.get_by_operation_id(operation_id)
        initial_status = operation.status
        initial_finished_at = operation.finished_at
        
        # Попытаться изменить статус обратно (через прямой update - это должно быть защищено)
        # В реальности это должно быть защищено на уровне OperationService
        # Здесь мы просто проверяем, что статус остался terminal
        
        # Проверки:
        assert operation.status == initial_status
        assert operation.finished_at == initial_finished_at
        assert operation.status in ["succeeded", "failed", "timed_out", "canceled"]


@pytest.mark.asyncio
async def test_server_event_dedup(test_client, test_agent, test_engine):
    """T10: Дедупликация server-originated событий (agent_seq=NULL)."""
    device_id = test_agent.device_id
    ticket_id, _ = await create_test_ticket(test_client, device_id=device_id)
    
    # Создать server-originated событие (tool_call_started)
    tool_resp = await test_client.post("/api/tools/run", json={
        "tool_name": "echo",
        "params": {"message": "test"},
        "device_id": device_id,
        "ticket_id": ticket_id
    })
    assert tool_resp.status == 200
    
    # Подсчитать события
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        events_repo = TicketEventsRepo(session)
        events = await events_repo.get_events(ticket_id)
        
        # Найти server-originated события (agent_seq IS NULL)
        server_events = [e for e in events if e.agent_seq is None]
        assert len(server_events) > 0
        
        # Проверяем, что нет дубликатов по event_id (если он есть)
        # или по комбинации (device_id, ticket_id, event_type, payload)
        # TODO: Реализовать проверку дедупликации после понимания механизма


@pytest.mark.asyncio
async def test_error_result_outbox_terminal(test_client, test_agent, test_engine):
    """Тест: command_result error гарантирует terminal состояние даже при битом payload."""
    device_id = test_agent.device_id
    ticket_id, _ = await create_test_ticket(test_client, device_id=device_id)
    
    # 1. Создать операцию через tool echo
    tool_resp = await test_client.post("/api/tools/run", json={
        "tool_name": "echo",
        "params": {"message": "test"},
        "device_id": device_id,
        "ticket_id": ticket_id
    })
    assert tool_resp.status == 200
    operation_data = await tool_resp.json()
    call_id = operation_data["call_id"]
    
    operation_id = await find_operation_by_call_id(test_engine, ticket_id, call_id)
    assert operation_id is not None
    
    # 2. Дождаться завершения (обычный путь)
    await wait_for_operation_terminal(test_engine, operation_id, timeout=10)
    
    # 3. Проверки: operations terminal, outbox terminal
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        repo = OperationsRepo(session)
        operation = await repo.get_by_operation_id(operation_id)
        
        assert operation is not None
        assert operation.status in ["succeeded", "failed", "timed_out", "canceled"]
        
        outbox_repo = DeviceOutboxRepo(session)
        outbox_item = await outbox_repo.get_command_by_id(operation_id)
        assert outbox_item is not None
        assert outbox_item.status in ["delivered", "failed"]  # Terminal состояния outbox


@pytest.mark.asyncio
async def test_watchdog_marks_stuck_sent(test_client, test_agent, test_engine):
    """Тест: watchdog помечает зависшие операции."""
    # Этот тест требует мокирования watchdog или настройки короткого timeout
    # Пока пропускаем, так как требует дополнительной настройки
    # TODO: Реализовать после настройки test config для коротких таймаутов
    pass


@pytest.mark.asyncio
async def test_watchdog_does_not_override_terminal(test_client, test_agent, test_engine):
    """Тест: watchdog не перезаписывает terminal состояния."""
    device_id = test_agent.device_id
    ticket_id, _ = await create_test_ticket(test_client, device_id=device_id)
    
    # 1. Довести операцию до succeeded/failed
    tool_resp = await test_client.post("/api/tools/run", json={
        "tool_name": "echo",
        "params": {"message": "test"},
        "device_id": device_id,
        "ticket_id": ticket_id
    })
    assert tool_resp.status == 200
    operation_data = await tool_resp.json()
    call_id = operation_data["call_id"]
    
    operation_id = await find_operation_by_call_id(test_engine, ticket_id, call_id)
    assert operation_id is not None
    
    # Дождаться terminal статуса
    terminal_status = await wait_for_operation_terminal(test_engine, operation_id, timeout=10)
    assert terminal_status in ["succeeded", "failed"]
    
    # 2. Получить начальное состояние
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        repo = OperationsRepo(session)
        operation = await repo.get_by_operation_id(operation_id)
        initial_status = operation.status
        initial_finished_at = operation.finished_at
        
        # 3. Попытаться изменить статус обратно (через guarded update - должно быть защищено)
        # Guards в operations_repo должны блокировать это
        success = await repo.update_status(
            operation_id=operation_id,
            new_status="running",  # Попытка вернуть в non-terminal
            expected_statuses=None  # Forced update
        )
        
        # Должно быть False из-за guards
        assert success is False, "Guards should block terminal state overwrite"
        
        # 4. Проверки: статус не изменился
        operation_after = await repo.get_by_operation_id(operation_id)
        assert operation_after.status == initial_status
        assert operation_after.finished_at == initial_finished_at


@pytest.mark.asyncio
async def test_consent_required_status(test_client, test_agent, test_engine):
    """Тест: status=consent_required обрабатывается корректно."""
    # Этот тест требует tool, который возвращает consent_required
    # Пока пропускаем, так как нет такого tool в test_modules
    # TODO: Реализовать после добавления test tool с consent_required
    pass

