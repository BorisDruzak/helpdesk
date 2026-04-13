"""Handshake handler extracted from agent websocket legacy module."""

"""
WebSocket обработчик для агентов.
"""

import asyncio
import time
import uuid
import json
from datetime import datetime, timezone
from aiohttp import web, WSMsgType
from loguru import logger
from typing import Optional, Tuple, Any
from utils import now_iso
from websocket.protocol import (
    send_ws_command,
    push_chat_event_to_ui,
    send_outbox_ack,
    send_outbox_nack
)
from websocket.batch_ack_manager import BatchAckManager, NackInfo
from websocket.validator import EventValidator
from websocket.command_result_parser import normalize_command_result_payload
from config import ENABLE_DB_PERSISTENCE
from auth.agent_token_service import AgentTokenService
from auth.connection_request_service import ConnectionRequestService
from auth.context import AuthContext, AuthType
from websocket.contexts import AgentConnectionContext, EnvelopeContext
from websocket.agent_services import (
    AgentLoopSafetyService,
    AgentCommandService,
    AgentMessageRouter,
    CommandAckService,
    CommandResultService,
    HandshakeService,
    OutboxIngestService,
)
from tech.runtime_audit import write_agent_runtime_audit

# Import database components (lazy import to handle missing dependencies)
try:
    from app.db import get_session
    from app.repos import JobEventsRepo, TicketEventsRepo, DeviceEventsRepo
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False


async def _confirm_update_operation_from_handshake(
    *,
    session: Any,
    state: Any,
    device_id: str,
    applied_update_version: Optional[str],
    last_update_operation_id: Optional[str],
    failed_update_version: Optional[str],
    failed_update_operation_id: Optional[str],
    failed_update_reason: Optional[str],
    failed_update_message: Optional[str],
) -> None:
    from app.repos.operations_repo import OperationsRepo
    from app.repos.device_outbox_repo import DeviceOutboxRepo
    from app.services.operation_service import OperationService

    op_repo = OperationsRepo(session)
    outbox_repo = DeviceOutboxRepo(session)
    op_service = OperationService(session, publisher=getattr(state, "ui_publisher", None))

    if failed_update_version and failed_update_operation_id:
        failed_operation = await op_repo.get_by_operation_id(failed_update_operation_id)
        if (
            failed_operation
            and failed_operation.device_id == device_id
            and failed_operation.kind == "agent_update"
        ):
            failed_code = str(failed_update_reason or "UPDATE_APPLY_FAILED").strip().upper() or "UPDATE_APPLY_FAILED"
            failed_message = (
                failed_update_message
                or f"Launcher reported failed update apply for version {failed_update_version}"
            )
            await op_service.mark_failed(
                operation_id=failed_update_operation_id,
                error_code=failed_code,
                error_message=failed_message,
                expected_statuses=["running", "accepted", "sent", "queued"],
            )
            await write_agent_runtime_audit(
                device_id=device_id,
                event_type="update_failed",
                severity="warning",
                source="handshake",
                operation_id=failed_update_operation_id,
                details_json={
                    "reason": failed_update_reason or "update_apply_failed",
                    "failed_update_version": failed_update_version,
                    "message": failed_message,
                },
            )

    if not applied_update_version or not last_update_operation_id:
        return
    operation = await op_repo.get_by_operation_id(last_update_operation_id)
    if not operation:
        return
    if operation.device_id != device_id or operation.kind != "agent_update":
        return

    outbox_entry = await outbox_repo.get_by_command_id(last_update_operation_id)
    expected_version = None
    if outbox_entry and isinstance(outbox_entry.params, dict):
        expected_version = outbox_entry.params.get("version")
    if expected_version and expected_version != applied_update_version:
        await op_service.mark_failed(
            operation_id=last_update_operation_id,
            error_code="UPDATE_VERSION_MISMATCH",
            error_message=(
                f"Handshake returned applied version {applied_update_version}, "
                f"expected {expected_version}"
            ),
            expected_statuses=["running", "accepted", "sent", "queued"],
        )
        await write_agent_runtime_audit(
            device_id=device_id,
            event_type="update_failed",
            severity="warning",
            source="handshake",
            operation_id=last_update_operation_id,
            details_json={"reason": "version_mismatch", "expected": expected_version, "actual": applied_update_version},
        )
        return

    await op_service.mark_succeeded(
        operation_id=last_update_operation_id,
        result_summary=f"confirmed_by_handshake:{applied_update_version}",
        expected_statuses=["running", "accepted", "sent", "queued"],
    )
    await write_agent_runtime_audit(
        device_id=device_id,
        event_type="update_handshake_confirmed",
        severity="info",
        source="handshake",
        operation_id=last_update_operation_id,
        details_json={"applied_update_version": applied_update_version},
    )


def _is_provision_stub(device: Any) -> bool:
    if not device:
        return True
    protocol_version = (getattr(device, "protocol_version", None) or "").strip().lower()
    agent_version = (getattr(device, "agent_version", None) or "").strip().lower()
    hostname = getattr(device, "hostname", None)
    os_name = getattr(device, "os", None)
    toolset_hash = getattr(device, "current_toolset_hash", None)
    metadata = getattr(device, "device_metadata", None) or {}
    if protocol_version not in ("", "pending"):
        return False
    if agent_version not in ("", "unknown"):
        return False
    if hostname or os_name or toolset_hash:
        return False
    return not bool(metadata)


async def _resolve_handshake_device_id(
    *,
    token_info: dict[str, Any],
    payload_device_id: Optional[str],
) -> str:
    token_device_id = token_info["device_id"]
    if not payload_device_id or payload_device_id == token_device_id:
        return token_device_id
    if not DB_AVAILABLE or not ENABLE_DB_PERSISTENCE:
        return token_device_id

    cleanup_stub_device_id: Optional[str] = None
    try:
        async with get_session() as session:
            from app.repos.auth_tokens_repo import AuthTokensRepo
            from app.repos.devices_repo import DevicesRepo

            devices_repo = DevicesRepo(session)
            tokens_repo = AuthTokensRepo(session)

            payload_device = await devices_repo.get_by_device_id(payload_device_id)
            if not payload_device or _is_provision_stub(payload_device):
                return token_device_id

            token_device = await devices_repo.get_by_device_id(token_device_id)
            if token_device and not _is_provision_stub(token_device):
                return token_device_id

            rebound = await tokens_repo.rebind_agent_token(
                token_hash=token_info["token_hash"],
                new_device_id=payload_device_id,
            )
            if not rebound:
                return token_device_id

            if token_device and _is_provision_stub(token_device):
                cleanup_stub_device_id = token_device_id

            logger.warning(
                f"🔁 Rebound fresh agent token {token_info.get('token_prefix', '')} "
                f"from device_id={token_device_id} to existing device_id={payload_device_id}"
            )
            await write_agent_runtime_audit(
                device_id=payload_device_id,
                event_type="token_rebound",
                severity="warning",
                source="handshake",
                details_json={
                    "from_device_id": token_device_id,
                    "token_prefix": token_info.get("token_prefix"),
                    "reason": "existing_payload_device_reused",
                },
            )
    except Exception as e:
        logger.warning(
            f"⚠️ Failed to resolve handshake device binding: token_device_id={token_device_id} "
            f"payload_device_id={payload_device_id} error={e}"
        )
        return token_device_id

    if cleanup_stub_device_id:
        try:
            async with get_session() as cleanup_session:
                from app.repos.auth_tokens_repo import AuthTokensRepo
                from app.repos.devices_repo import DevicesRepo

                cleanup_devices_repo = DevicesRepo(cleanup_session)
                cleanup_tokens_repo = AuthTokensRepo(cleanup_session)
                cleanup_device = await cleanup_devices_repo.get_by_device_id(cleanup_stub_device_id)
                bound_tokens = await cleanup_tokens_repo.get_agent_tokens_by_device(cleanup_stub_device_id)
                if cleanup_device and _is_provision_stub(cleanup_device) and not bound_tokens:
                    await cleanup_session.delete(cleanup_device)
                    await cleanup_session.flush()
        except Exception as cleanup_error:
            logger.warning(
                f"[handshake] Failed to cleanup placeholder device after token rebound: "
                f"device_id={cleanup_stub_device_id} error={cleanup_error}"
            )

    return payload_device_id

async def handle_handshake(
    ws: web.WebSocketResponse,
    data: dict,
    request: web.Request,
    state: Any,
) -> Tuple[Optional[web.WebSocketResponse], Optional[str], Optional[str], bool]:
    """
    Обработка handshake (Protocol V3).
    Возвращает (ws для return при закрытии, agent_id, device_id, authenticated) или (None, aid, did, True) при успехе.
    Логика реализована в основном цикле ниже (блок if msg_type == "handshake"); при рефакторинге перенести сюда.
    """
    agent_id = None
    device_id = None
    authenticated = False

    # Phase E: Строгая валидация protocol_version
    protocol_version = data.get("protocol_version")
    
    # КРИТИЧНО: требуем ws_ticket_v3 (Phase E)
    if protocol_version != "ws_ticket_v3":
        logger.error(
            f"🔴 Invalid protocol_version: {protocol_version}, "
            f"expected ws_ticket_v3"
        )
        await ws.close(
            code=4003,
            message=b"Protocol V3 (ws_ticket_v3) required"
        )
        return (ws, agent_id, device_id, authenticated)
    
    # Phase E: Проверяем обязательные capabilities
    meta = data.get("meta", {})
    capabilities = meta.get("capabilities", [])
    required_capabilities = {
        "protocol_v3",
        "envelope_v3",
        "outbox_ack_v3"
    }
    missing_capabilities = required_capabilities - set(capabilities)
    
    if missing_capabilities:
        logger.error(
            f"🔴 Missing required capabilities: {missing_capabilities}"
        )
        await ws.close(
            code=4003,
            message=f"Missing required capabilities: {missing_capabilities}".encode()
        )
        return (ws, agent_id, device_id, authenticated)
    
    # Phase 3: Проверяем токен для аутентификации через БД
    token = data.get("token")
    logger.debug(
        f"Handshake: token received=%s prefix=%s",
        bool(token),
        token[:12] + "..." if token and len(token) >= 12 else (token or "")
    )
    loop_safety_service = AgentLoopSafetyService()
    
    # Извлекаем device_id из payload для отслеживания попыток подключения
    # Проверяем в разных местах: корень сообщения, payload, meta
    payload_device_id = (
        data.get("device_id") or 
        data.get("payload", {}).get("device_id") or
        data.get("payload", {}).get("uuid") or
        data.get("uuid")
    )
    
    connection_request_service = ConnectionRequestService()
    if not token:
        logger.warning("🔴 Попытка подключения без токена")
        # Persist pending attempt in DB for admin visibility.
        if payload_device_id:
            await connection_request_service.record_unauthorized_attempt(
                device_id=payload_device_id,
                ip_address=request.remote,
                user_agent=request.headers.get("User-Agent", ""),
                reason="no_token",
            )
            await write_agent_runtime_audit(
                device_id=payload_device_id,
                event_type="invalid_token",
                severity="warning",
                source="handshake",
                details_json={"reason": "no_token"},
            )
            logger.info(f"[handshake] Unauthorized attempt persisted: device_id={payload_device_id[:8]}... reason=no_token")
        await ws.close(code=4003, message=b"Token required")
        return (ws, agent_id, device_id, authenticated)
    
    # Проверяем токен через AuthService (БД)
    token_service = AgentTokenService()
    token_info = await token_service.verify_agent_token(token)
    
    if not token_info:
        logger.warning(f"🔴 Невалидный токен агента: {token[:8]}...")
        # Persist pending attempt with invalid token reason.
        if payload_device_id:
            await connection_request_service.record_unauthorized_attempt(
                device_id=payload_device_id,
                ip_address=request.remote,
                user_agent=request.headers.get("User-Agent", ""),
                reason="invalid_token",
            )
            await write_agent_runtime_audit(
                device_id=payload_device_id,
                event_type="invalid_token",
                severity="warning",
                source="handshake",
                details_json={"reason": "invalid_token"},
            )
            logger.info(f"[handshake] Unauthorized attempt persisted: device_id={payload_device_id[:8]}... reason=invalid_token")
        await ws.close(code=4003, message=b"Invalid token")
        return (ws, agent_id, device_id, authenticated)
    
    # КРИТИЧНО: базовый source of truth — device_id из токена.
    # Исключение: controlled reprovision. Если токен выдан на свежий/пустой UUID,
    # а агент пришёл со своим уже известным payload device_id, мы перепривязываем
    # сам токен к существующему устройству и дальше всё равно работаем через запись токена.
    device_id = await _resolve_handshake_device_id(
        token_info=token_info,
        payload_device_id=payload_device_id,
    )
    agent_id = device_id
    
    # Создаем AuthContext для этого соединения
    auth_context = AuthContext(
        actor_id=device_id,
        actor_role="agent",
        auth_type=AuthType.AGENT_TOKEN,
        token=token
    )
    
    # Токен валиден - разрешаем работу
    authenticated = True
    
    # Проверяем, что device_id из payload совпадает с токеном (если указан)
    payload_device_id = data.get("device_id")
    if payload_device_id and payload_device_id != device_id:
        logger.warning(
            f"🔴 Device ID mismatch: token={device_id}, payload={payload_device_id}. "
            f"Using device_id from token."
        )
    
    # Регистрируем агента
    metadata = {
        "device_id": device_id,
        "agent_version": data.get("agent_version", "unknown"),
        "modules": data.get("modules", []),
        "protocol_version": protocol_version,  # Phase E: сохраняем
        "capabilities": capabilities,  # Phase E: сохраняем
        "connected_at": time.time(),
        "last_seen": time.time(),
        "status": "online",
        "pending_futures": {},  # Dict[str, asyncio.Future] для параллельных запросов
        "auth_context": auth_context,  # Phase 3: сохраняем AuthContext
        "token": token,  # Для обратной совместимости (deprecated)
        "ws": ws
    }
    payload_pre = data.get("payload", {}) or data.get("meta", {})
    metadata["os_type"] = payload_pre.get("os_type") or payload_pre.get("os")
    if payload_pre.get("applied_update_version") is not None:
        metadata["applied_update_version"] = payload_pre["applied_update_version"]
    if payload_pre.get("last_update_operation_id") is not None:
        metadata["last_update_operation_id"] = payload_pre["last_update_operation_id"]
    if payload_pre.get("failed_update_version") is not None:
        metadata["last_failed_update_version"] = payload_pre["failed_update_version"]
    if payload_pre.get("failed_update_operation_id") is not None:
        metadata["last_failed_update_operation_id"] = payload_pre["failed_update_operation_id"]
    if payload_pre.get("failed_update_reason") is not None:
        metadata["last_failed_update_reason"] = payload_pre["failed_update_reason"]
    if payload_pre.get("failed_update_at") is not None:
        metadata["last_failed_update_at"] = payload_pre["failed_update_at"]
    if payload_pre.get("failed_update_message") is not None:
        metadata["last_failed_update_message"] = payload_pre["failed_update_message"]
    state.register_agent(agent_id, ws, metadata)
    
    logger.success(f"✅ Агент зарегистрирован: {device_id}")
    await write_agent_runtime_audit(
        device_id=device_id,
        event_type="handshake_ok",
        severity="info",
        source="handshake",
        actor_id=device_id,
        actor_role="agent",
    )
    logger.info(f"   Protocol: {protocol_version}")
    logger.info(f"   Capabilities: {capabilities}")
    logger.info(f"   Модули: {data.get('modules', [])}")
    
    # Device Registry: upsert device and check toolset_hash
    desired_revision = 0
    should_request_toolset = False
    
    if DB_AVAILABLE and ENABLE_DB_PERSISTENCE:
        try:
            async with get_session() as session:
                from app.repos import DevicesRepo, DeviceConfigRepo
                
                devices_repo = DevicesRepo(session)
                config_repo = DeviceConfigRepo(session)
                
                # Читаем os, toolset_hash, tools_count из payload (агент шлёт в payload)
                payload = data.get("payload", {})
                agent_toolset_hash = payload.get("toolset_hash") or meta.get("toolset_hash")
                agent_version = payload.get("agent_version") or data.get("agent_version", "unknown")
                hostname = payload.get("hostname") or meta.get("hostname")
                os_info = payload.get("os") or meta.get("os")
                tools_version = payload.get("tools_version") or meta.get("tools_version")
                modules = payload.get("modules") or data.get("modules", [])
                metadata_db = {"modules": modules}
                if payload.get("applied_update_version") is not None:
                    metadata_db["applied_update_version"] = payload["applied_update_version"]
                if payload.get("last_update_operation_id") is not None:
                    metadata_db["last_update_operation_id"] = payload["last_update_operation_id"]
                if payload.get("failed_update_version") is not None:
                    metadata_db["last_failed_update_version"] = payload["failed_update_version"]
                if payload.get("failed_update_operation_id") is not None:
                    metadata_db["last_failed_update_operation_id"] = payload["failed_update_operation_id"]
                if payload.get("failed_update_reason") is not None:
                    metadata_db["last_failed_update_reason"] = payload["failed_update_reason"]
                if payload.get("failed_update_at") is not None:
                    metadata_db["last_failed_update_at"] = payload["failed_update_at"]
                if payload.get("failed_update_message") is not None:
                    metadata_db["last_failed_update_message"] = payload["failed_update_message"]
                if payload.get("os_type") is not None:
                    metadata_db["os_type"] = payload["os_type"]
                if not metadata_db.get("os_type") and os_info:
                    metadata_db["os_type"] = os_info
                # Upsert device
                device = await devices_repo.upsert_on_handshake(
                    device_id=device_id,
                    protocol_version=protocol_version,
                    agent_version=agent_version,
                    hostname=hostname,
                    os=os_info,
                    capabilities=capabilities,
                    tools_version=tools_version,
                    toolset_hash=agent_toolset_hash,
                    metadata=metadata_db
                )
                await _confirm_update_operation_from_handshake(
                    session=session,
                    state=state,
                    device_id=device_id,
                    applied_update_version=payload.get("applied_update_version"),
                    last_update_operation_id=payload.get("last_update_operation_id"),
                    failed_update_version=payload.get("failed_update_version"),
                    failed_update_operation_id=payload.get("failed_update_operation_id"),
                    failed_update_reason=payload.get("failed_update_reason"),
                    failed_update_message=payload.get("failed_update_message"),
                )
                
                # Get or create config
                device_config = await config_repo.get_or_create_default(device_id)
                desired_revision = device_config.desired_revision
                
                # Check if we should request toolset
                if agent_toolset_hash is None:
                    # No toolset hash provided - check rate-limit
                    should_request_toolset = await devices_repo.should_refresh_toolset(
                        device_id=device_id,
                        rate_limit_minutes=10
                    )
                    
                    if should_request_toolset:
                        logger.info(
                            f"[handshake] No toolset_hash provided, "
                            f"will request list_tools (rate-limit passed)"
                        )
                    else:
                        logger.debug(
                            f"[handshake] No toolset_hash provided, "
                            f"but rate-limited - skipping list_tools"
                        )
                
                elif agent_toolset_hash != device.current_toolset_hash:
                    # Toolset hash changed - always refresh (no rate-limit)
                    should_request_toolset = True
                    logger.info(
                        f"[handshake] Toolset hash changed: "
                        f"old={device.current_toolset_hash} "
                        f"new={agent_toolset_hash}, will request list_tools"
                    )
                else:
                    # Toolset hash unchanged - no need to refresh
                    logger.debug(
                        f"[handshake] Toolset hash unchanged: {agent_toolset_hash}"
                    )
                
                # Process modules_inventory if present (payload уже получен выше)
                modules_inventory = payload.get("modules_inventory")
                if isinstance(modules_inventory, list):
                    from websocket.modules_sync import sync_modules_inventory
                    await sync_modules_inventory(
                        session=session,
                        device_id=device_id,
                        inventory=modules_inventory
                    )
                else:
                    # Fallback: если modules_inventory отсутствует или имеет неверный формат, запросить через команду
                    logger.info(
                        f"[handshake] modules_inventory not provided/invalid, "
                        f"will request list_installed_modules"
                    )
                    # Enqueue list_installed_modules command (async, fire-and-forget)
                    from websocket.protocol import enqueue_command_async
                    await enqueue_command_async(
                        state=state,
                        device_id=device_id,
                        command="list_installed_modules",
                        params={},
                        actor_role="server",
                        trace_id=None
                    )
                
                await session.commit()
                
        except Exception as e:
            logger.opt(exception=True).error(
                "[handshake] Failed to upsert device: {}",
                e,
            )
    
    # Phase D: Get open tickets for handshake sync
    open_tickets = []
    if DB_AVAILABLE and ENABLE_DB_PERSISTENCE:
        try:
            async with get_session() as session:
                # КРИТИЧНО: локальный импорт — в этой же функции есть другие импорты TicketEventsRepo,
                # из-за чего имя считается локальным и в данной ветке может быть не определено
                from app.repos import TicketEventsRepo as _TicketEventsRepo
                if not DB_AVAILABLE:
                    logger.warning(
                        f"[handshake] DB not available, skipping open tickets fetch"
                    )
                else:
                    ticket_repo = _TicketEventsRepo(session)
                    open_tickets = await ticket_repo.get_open_tickets_for_device(device_id)
                    logger.info(
                        f"[handshake] Found {len(open_tickets)} open tickets "
                        f"for device_id={device_id}"
                    )
        except Exception as e:
            logger.warning(
                f"[handshake] Failed to fetch open tickets: {e}"
            )
    
    # Phase E: Отправляем handshake_ack с server_capabilities и desired_revision
    from config import SERVER_CAPABILITIES
    
    handshake_ack = {
        "type": "handshake_ack",
        "request_id": data.get("request_id"),
        "device_id": device_id,
        "protocol_version": "ws_ticket_v3",  # Phase E: обязательно
        "trace_id": data.get("trace_id") or str(uuid.uuid4()),
        "payload": {
            "status": "success",
            "message": "Handshake accepted",
            "server_version": "3.0.0",  # Phase E: версия сервера
            "open_tickets": open_tickets,  # Phase D: Send open tickets
            "desired_revision": desired_revision,  # Device config revision
            "server_capabilities": SERVER_CAPABILITIES  # Из config.py
        },
        "meta": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor_role": "server"
        }
    }
    await ws.send_json(handshake_ack)
    logger.debug(f"📤 Отправлен handshake_ack агенту {device_id}")
    if open_tickets:
        logger.debug(
            f"📤 Отправлено {len(open_tickets)} открытых тикетов "
            f"РІ handshake_ack"
        )
    
    # Enqueue list_tools if needed (с debounce: не ставим, если уже есть pending list_tools)
    if should_request_toolset and DB_AVAILABLE and ENABLE_DB_PERSISTENCE:
        try:
            from websocket.protocol import enqueue_command_async
            from app.repos import DevicesRepo, OperationsRepo
            
            # Защита от шторма: не enqueue list_tools, если уже есть ожидающая операция
            async with get_session() as session:
                op_repo = OperationsRepo(session)
                if await op_repo.has_pending_list_tools(device_id):
                    logger.debug(
                        f"[handshake] Skipping list_tools: device_id={device_id} "
                        f"already has pending list_tools"
                    )
                    should_request_toolset = False
            if not should_request_toolset:
                pass  # skip enqueue below
            else:
                # Enqueue list_tools command (создает операцию автоматически)
                command_id = await enqueue_command_async(
                state=state,
                device_id=device_id,
                command="list_tools",
                params={},
                actor_role="server",
                trace_id=None
            )
            
            logger.info(
                f"[handshake] Enqueued list_tools: "
                f"device_id={device_id} command_id={command_id}"
            )
            
            # Update last_toolset_refresh_at immediately to prevent duplicates
            async with get_session() as session:
                devices_repo = DevicesRepo(session)
                await devices_repo.update_toolset_refresh_time(device_id)
                await session.commit()
                
        except Exception as e:
            logger.error(
                f"[handshake] Failed to enqueue list_tools: {e}",
                exc_info=True
            )

# в"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓ
# b) type == "pong"
# в"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓ

    return (None, agent_id, device_id, authenticated)
