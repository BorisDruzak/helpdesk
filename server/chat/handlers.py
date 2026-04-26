"""
HTTP обработчики для chat API.
"""

import asyncio
import time
import uuid
from aiohttp import web
from loguru import logger
from app.db import get_session
from auth.context import AuthType
from tickets.create_flow import build_agent_raise_description, create_ticket_with_side_effects
from websocket.protocol import send_ws_command, push_chat_event_to_ui
from chat.service import ChatService


async def handle_chat_start(request):
    """
    API эндпоинт для запуска чат-job: POST /api/chat_start
    
    POST JSON:
    {
      "device_id": "test_pc_01",
      "actor_role": "admin"
    }
    
    Запускает support_chat job и возвращает job_id.
    """
    try:
        state = request.app['state']
        service = ChatService(state)
        
        data = await request.json()
        device_id = data.get("device_id")
        actor_role = data.get("actor_role", "admin")
        
        if not device_id:
            return web.json_response({
                "status": "error",
                "error": "Missing device_id"
            }, status=400)
        
        logger.info(f"[SERVER] chat_start device_id={device_id} actor_role={actor_role}")
        
        # Генерируем chat_job_id на сервере
        chat_job_id = str(uuid.uuid4())
        
        # Создаем chat_session
        service.create_session(chat_job_id, device_id, created_by="support")
        
        # Отправляем команду start_job с job_type="support_chat" и переданным job_id
        res = await send_ws_command(
            state=state,
            device_id=device_id,
            command="start_job",
            params={"job_type": "support_chat", "params": {"job_id": chat_job_id}},
            actor_role=actor_role,
            timeout=60
        )
        
        logger.info(f"[SERVER] chat_start success job_id={chat_job_id}")
        
        # Создаем invite событие
        invite_event = {
            "event": "chat_invite",
            "job_id": chat_job_id,
            "device_id": device_id,
            "from": "support",
            "title": "Support Chat",
            "ts": time.time(),
        }
        
        # PUSH invite в UI (через WebSocket подписчиков)
        await push_chat_event_to_ui(state, chat_job_id, invite_event)
        logger.info(f"[SERVER] TX chat_invite to UI subscribers job_id={chat_job_id}")
        
        # PUSH invite в локальный GUI агента (через EventBus -> /ui/events)
        try:
            await send_ws_command(
                state=state,
                device_id=device_id,
                command="ui_notify",
                params={"event": invite_event},
                actor_role=actor_role,
                timeout=10
            )
            logger.info(f"[SERVER] TX ui_notify chat_invite job_id={chat_job_id} device_id={device_id}")
        except Exception as e:
            # invite не должен ломать chat_start
            logger.warning(f"[SERVER] Failed to send chat_invite to agent UI: {e}")
        
        return web.json_response({
            "status": "success",
            "job_id": chat_job_id,
            "device_id": device_id
        })
    
    except ValueError as e:
        logger.warning(f"⚠️  {str(e)}")
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=404)
    except asyncio.TimeoutError:
        logger.error(f"⏱️  Таймаут команды chat_start")
        return web.json_response({
            "status": "error",
            "error": "Command timeout"
        }, status=504)
    except Exception as e:
        logger.error(f"❌ Ошибка обработки chat_start: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_chat_raise(request):
    """
    API эндпоинт для инициации чата агентом: POST /api/chat_raise
    
    POST JSON:
    {
      "device_id": "test_pc_01"
    }
    
    Агент инициирует чат, сервер стартует support_chat job и отправляет chat_invite в GUI агента.
    """
    try:
        state = request.app['state']
        service = ChatService(state)

        auth_context = request.get("auth_context")
        if not auth_context:
            return web.json_response({
                "status": "error",
                "error": "Unauthorized"
            }, status=401)

        data = await request.json()
        body_device_id = str(data.get("device_id") or "").strip()
        title = str(data.get("title") or "Agent Support Request").strip() or "Agent Support Request"
        reason = str(data.get("reason") or "agent_initiated").strip() or "agent_initiated"
        severity = str(data.get("severity") or "warning").strip() or "warning"
        context_payload = data.get("context") if isinstance(data.get("context"), dict) else {}

        if auth_context.auth_type == AuthType.AGENT_TOKEN:
            device_id = auth_context.actor_id
            if body_device_id and body_device_id != device_id:
                return web.json_response({
                    "status": "error",
                    "error": "device_id does not match authenticated agent"
                }, status=403)
        elif auth_context.actor_role in {"admin", "support"}:
            device_id = body_device_id
            if not device_id:
                return web.json_response({
                    "status": "error",
                    "error": "Missing device_id"
                }, status=400)
        else:
            return web.json_response({
                "status": "error",
                "error": "Forbidden"
            }, status=403)
        
        if not state.is_agent_online(device_id):
            return web.json_response({
                "status": "error",
                "error": f"Agent {device_id} not connected"
            }, status=404)
        
        logger.info(f"[SERVER] chat_raise device_id={device_id}")
        
        # Генерируем chat_job_id
        chat_job_id = str(uuid.uuid4())
        ticket_id = str(uuid.uuid4())
        
        # Создаем chat_session
        service.create_session(chat_job_id, device_id, created_by="agent")

        async with get_session() as session:
            created = await create_ticket_with_side_effects(
                session,
                device_id=device_id,
                requester_id=device_id if auth_context.auth_type == AuthType.AGENT_TOKEN else auth_context.actor_id,
                title=title,
                description=build_agent_raise_description(
                    reason=reason,
                    severity=severity,
                    context=context_payload,
                ),
                user_display_name=device_id,
                initial_message_sender_role="agent",
                initial_message_from="agent",
                include_public_access=False,
                state=state,
            )
            ticket_id = created["ticket_id"]
            await session.commit()
        
        # Отправляем команду start_job с job_type="support_chat" и переданным job_id
        res = await send_ws_command(
            state=state,
            device_id=device_id,
            command="start_job",
            params={"job_type": "support_chat", "params": {"job_id": chat_job_id, "ticket_id": ticket_id}},
            auth_context=auth_context,
            timeout=60
        )
        
        logger.info(f"[SERVER] chat_raise success job_id={chat_job_id}")
        
        # Создаем invite событие
        invite_event = {
            "event": "chat_invite",
            "job_id": chat_job_id,
            "ticket_id": ticket_id,
            "device_id": device_id,
            "from": "agent",
            "title": title,
            "reason": reason,
            "severity": severity,
            "context": context_payload,
            "ts": time.time(),
        }
        
        # PUSH invite в UI (через WebSocket подписчиков)
        await push_chat_event_to_ui(state, chat_job_id, invite_event)
        logger.info(f"[SERVER] TX chat_invite to UI subscribers job_id={chat_job_id}")
        
        # PUSH invite в локальный GUI агента (через EventBus -> /ui/events)
        try:
            await send_ws_command(
                state=state,
                device_id=device_id,
                command="ui_notify",
                params={"event": invite_event},
                auth_context=auth_context,
                timeout=10
            )
            logger.info(f"[SERVER] TX ui_notify chat_invite job_id={chat_job_id} device_id={device_id}")
        except Exception as e:
            # invite не должен ломать chat_raise
            logger.warning(f"[SERVER] Failed to send chat_invite to agent UI: {e}")
        
        return web.json_response({
            "status": "success",
            "job_id": chat_job_id,
            "ticket_id": ticket_id,
            "device_id": device_id
        })
    
    except ValueError as e:
        logger.warning(f"⚠️  {str(e)}")
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=404)
    except asyncio.TimeoutError:
        logger.error(f"⏱️  Таймаут команды chat_raise")
        return web.json_response({
            "status": "error",
            "error": "Command timeout"
        }, status=504)
    except Exception as e:
        logger.error(f"❌ Ошибка обработки chat_raise: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_chat_send(request):
    """
    API эндпоинт для отправки сообщения в чат-job: POST /api/chat_send
    
    POST JSON:
    {
      "device_id": "test_pc_01",
      "job_id": "<job_id>",
      "text": "hello",
      "from": "support",
      "actor_role": "support"
    }
    
    Отправляет chat_message событие в job через job_send_event.
    """
    try:
        state = request.app['state']
        
        data = await request.json()
        device_id = data.get("device_id")
        job_id = data.get("job_id")
        text = data.get("text")
        from_ = data.get("from")
        actor_role = data.get("actor_role", "support")
        
        if not device_id:
            return web.json_response({
                "status": "error",
                "error": "Missing device_id"
            }, status=400)
        
        if not job_id:
            return web.json_response({
                "status": "error",
                "error": "Missing job_id"
            }, status=400)
        
        if not text:
            return web.json_response({
                "status": "error",
                "error": "Missing text"
            }, status=400)
        
        if not from_:
            return web.json_response({
                "status": "error",
                "error": "Missing from"
            }, status=400)
        
        # Формируем событие chat_message
        event = {
            "event": "chat_message",
            "job_id": job_id,
            "message_id": str(uuid.uuid4()),
            "from": from_,
            "text": text,
            "ts": time.time()
        }
        
        # Логируем отправку (truncate длинный текст)
        text_preview = text[:50] + "..." if len(text) > 50 else text
        logger.info(f"[SERVER] chat_send job_id={job_id} text_len={len(text)} text_preview={text_preview}")
        
        # Отправляем команду job_send_event
        res = await send_ws_command(
            state=state,
            device_id=device_id,
            command="job_send_event",
            params={"job_id": job_id, "event": event},
            actor_role=actor_role,
            timeout=30
        )
        
        # Валидация ответа (опционально, но рекомендовано для отладки)
        validated = False
        try:
            observations = res.get("payload", {}).get("data", {}).get("observations", {})
            if observations:
                obs_job_id = observations.get("chat_job_id")
                obs_message_id = observations.get("message_id")
                validated = (
                    obs_job_id == job_id and
                    obs_message_id == event["message_id"]
                )
        except Exception:
            pass  # Валидация не критична, просто пропускаем
        
        # Возвращаем результат
        return web.json_response({
            "status": "success",
            "job_id": job_id,
            "message_id": event["message_id"],
            "validated": validated,
            "response": res
        })
    
    except ValueError as e:
        logger.warning(f"⚠️  {str(e)}")
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=404)
    except asyncio.TimeoutError:
        logger.error(f"⏱️  Таймаут команды chat_send")
        return web.json_response({
            "status": "error",
            "error": "Command timeout"
        }, status=504)
    except Exception as e:
        logger.error(f"❌ Ошибка обработки chat_send: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_active_chats(request):
    """
    API эндпоинт для получения списка активных чатов: GET /api/active_chats
    
    Возвращает все активные чат-сессии с информацией о них.
    """
    try:
        state = request.app['state']
        service = ChatService(state)
        
        active_chats = service.get_active_chats()
        
        return web.json_response({
            "status": "success",
            "chats": active_chats,
            "total": len(active_chats)
        })
        
    except Exception as e:
        logger.error(f"[handle_active_chats] Error: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_chat_events(request):
    """
    API эндпоинт для получения истории событий чат-job: GET /api/chat_events?job_id=...
    
    Query params:
    - job_id: обязательный
    - since_ts: optional float - фильтр событий где ts > since_ts
    - limit: optional int (default 200) - максимальное количество событий (последние N)
    - format: optional str - "raw" (по умолчанию) или "normalized" - формат ответа
    - wait: optional bool ("1"/"true"/"True"/"yes") - включить long-polling
    - timeout_ms: optional int (default 25000) - таймаут long-polling в миллисекундах
    
    Возвращает список событий для указанного job_id из хранилища job_events.
    При включённом wait и заданном since_ts ожидает новые события до таймаута.
    """
    try:
        state = request.app['state']
        
        job_id = request.query.get("job_id")
        
        if not job_id:
            return web.json_response({
                "status": "error",
                "error": "Missing job_id parameter"
            }, status=400)
        
        # Получаем события для job_id
        events = state.get_job_events(job_id)
        
        # Инициализируем events_with_ts сразу после получения events
        events_with_ts = [(float(e.get("ts", 0.0) or 0.0), e) for e in events]
        
        # Парсим since_ts
        since_ts_value = None
        since_ts = request.query.get("since_ts")
        if since_ts is not None:
            try:
                since_ts_value = float(since_ts)
            except (ValueError, TypeError):
                return web.json_response({
                    "status": "error",
                    "error": "Invalid since_ts parameter (must be float)"
                }, status=400)
        
        # Парсим параметры long-polling
        wait = request.query.get("wait", "0")
        wait_enabled = wait in ("1", "true", "True", "yes")
        
        timeout_ms = 25000  # default
        timeout_ms_param = request.query.get("timeout_ms")
        if timeout_ms_param is not None:
            try:
                timeout_ms = int(timeout_ms_param)
                if timeout_ms < 0:
                    return web.json_response({
                        "status": "error",
                        "error": "Invalid timeout_ms parameter (must be >= 0)"
                    }, status=400)
            except (ValueError, TypeError):
                return web.json_response({
                    "status": "error",
                    "error": "Invalid timeout_ms parameter (must be int)"
                }, status=400)
        
        deadline = time.time() + (timeout_ms / 1000.0)
        
        # Long-poll режим
        while True:
            filtered = events_with_ts
            if since_ts_value is not None:
                filtered = [(ts, e) for (ts, e) in filtered if ts > since_ts_value and ts > 0]
            
            # если нашли события — выходим
            if filtered:
                events = [e for (ts, e) in filtered]
                break
            
            # если не wait — сразу отдаём пусто
            if not wait_enabled:
                events = []
                break
            
            # wait включен — ждём до дедлайна
            if time.time() >= deadline:
                events = []
                break
            
            await asyncio.sleep(0.25)
            # важно: обновить events_with_ts, потому что job_events мог пополниться
            events = state.get_job_events(job_id)
            events_with_ts = [(float(e.get("ts", 0.0) or 0.0), e) for e in events]
        
        # Применяем limit
        limit = request.query.get("limit")
        limit_int = None
        if limit is not None:
            try:
                limit_int = int(limit)
                if limit_int < 0:
                    return web.json_response({
                        "status": "error",
                        "error": "Invalid limit parameter (must be >= 0)"
                    }, status=400)
            except (ValueError, TypeError):
                return web.json_response({
                    "status": "error",
                    "error": "Invalid limit parameter (must be int)"
                }, status=400)
        
        if limit_int is not None:
            # Сортируем по ts перед применением limit (для корректного "последних N")
            events.sort(key=lambda e: float(e.get("ts", 0.0) or 0.0))
            events = events[-limit_int:] if limit_int > 0 else []
        else:
            # Default limit = 200
            events.sort(key=lambda e: float(e.get("ts", 0.0) or 0.0))
            events = events[-200:] if len(events) > 200 else events
        
        # Параметр формата (raw или normalized)
        fmt = request.query.get("format", "raw")
        
        # Вспомогательные функции для обогащения событий
        def _event_type(e):
            return e.get("type") or e.get("event") or (e.get("payload", {}) if isinstance(e.get("payload"), dict) else {}).get("type") or "unknown"
        
        # Применяем формат
        if fmt == "normalized":
            normalized_events = []
            for e in events:
                et = _event_type(e)
                # Используем стабильный ts из события (или 0.0, не подставляем now)
                ts = float(e.get("ts", 0.0) or 0.0)
                
                normalized_events.append({
                    "ts": ts,
                    "type": et,
                    "job_id": job_id,
                    "payload": e,
                })
            events = normalized_events
        else:
            # raw mode: гарантируем ts и type-подсказку, не ломая существующие поля
            for e in events:
                if not isinstance(e.get("ts"), (int, float)):
                    # Если ts отсутствует, используем 0.0 (не now)
                    e["ts"] = 0.0
                if "type" not in e and "event" in e:
                    # старый формат: оставляем event, но добавим type для унификации
                    e["type"] = e.get("event")
        
        return web.json_response({
            "status": "ok",
            "job_id": job_id,
            "count": len(events),
            "events": events,
            "server_ts": time.time()
        })
    
    except Exception as e:
        logger.error(f"❌ Ошибка получения chat_events: {e}")
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)

