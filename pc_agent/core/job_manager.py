"""
Менеджер фоновых задач JobManager.
Protocol V3: Ticket-first архитектура (замечание 8).

Управляет выполнением фоновых задач через asyncio.Task,
сохраняет статус в БД и отправляет события в outbox.

Изменения V3:
- Любая задача автоматически создаёт тикет
- ticket_id обязателен в outbox (делегировано в database.py)
- Маппинг job_type → ticket category
- Политика merge при конфликте тикетов (server overwrites)
"""

import asyncio
import json
import time
import uuid as uuid_module
from typing import Dict, Any, Optional, Callable
from uuid import uuid4

from loguru import logger


class JobCompletedException(Exception):
    """Исключение для передачи reason завершения job."""
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Job completed with reason: {reason}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TICKET-FIRST MAPPING (Фаза 5.1, замечание 8)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Маппинг job_type → ticket category
JOB_TYPE_TO_CATEGORY = {
    "support_chat": "support",
    "support_ticket": "support",
    "chat_echo": "diagnostic",
    "system_check": "background",
    "periodic_update": "scheduled",
    "diagnostic": "diagnostic",
    "background": "background",
}


def map_job_type_to_category(job_type: str) -> str:
    """
    Маппинг job_type → ticket category (Фаза 5.1).
    
    Args:
        job_type: Тип задачи
        
    Returns:
        Категория тикета
    """
    return JOB_TYPE_TO_CATEGORY.get(job_type, "background")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MAKE_* ФУНКЦИИ (Фаза 5.3) - с обязательным ticket_id
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def make_chat_message(
    ticket_id: str,
    job_id: str,
    from_: str,
    text: str,
    message_id: str | None = None,
    seq: int | None = None
) -> tuple[str, dict]:
    """
    Создает событие chat_message.
    
    Protocol V3: ticket_id обязателен.
    
    Args:
        ticket_id: UUID тикета (ОБЯЗАТЕЛЬНО)
        job_id: Идентификатор задачи
        from_: Отправитель сообщения ("user", "agent", "support", "system")
        text: Текст сообщения
        message_id: Идентификатор сообщения (если не указан, генерируется автоматически)
        seq: Порядковый номер сообщения (если не указан, будет получен из БД в JobManager)
        
    Returns:
        (kind, payload) для передачи в enqueue_event()
    """
    message_id = message_id or str(uuid4())
    
    kind = "message"
    payload = {
        "ticket_id": ticket_id,
        "job_id": job_id,
        "message_id": message_id,
        "from": from_,
        "text": text,
        "ts": time.time()
    }
    if seq is not None:
        payload["seq"] = seq
    
    return (kind, payload)


def make_job_status_event(
    ticket_id: str,
    job_id: str,
    event: str,
    **extra
) -> tuple[str, dict]:
    """
    Создает событие статуса задачи.
    
    Protocol V3: ticket_id обязателен.
    
    Args:
        ticket_id: UUID тикета (ОБЯЗАТЕЛЬНО)
        job_id: Идентификатор задачи
        event: Тип события (например, "job_started", "job_running", "job_succeeded")
        **extra: Дополнительные поля для события
        
    Returns:
        (kind, payload) для передачи в enqueue_event()
    """
    kind = event  # kind = "job_started", "job_running", etc.
    payload = {
        "event": event,
        "ticket_id": ticket_id,
        "job_id": job_id,
        "ts": time.time(),
        **extra
    }
    
    return (kind, payload)


def make_agent_action(
    ticket_id: str,
    session_id: str,
    job_id: str,
    kind_action: str,
    title: str,
    details: dict | None = None
) -> tuple[str, dict]:
    """
    Создает событие agent_action.
    
    Protocol V3: ticket_id обязателен.
    
    Args:
        ticket_id: Идентификатор тикета (ОБЯЗАТЕЛЬНО)
        session_id: Идентификатор сессии
        job_id: Идентификатор задачи
        kind_action: Тип действия ("status" | "collect" | "tool_call" | "note" | "error")
        title: Краткое описание действия
        details: Дополнительные детали (JSON-совместимый словарь)
        
    Returns:
        (kind, payload) для передачи в enqueue_event()
    """
    kind = "agent_action"
    payload = {
        "event": "agent_action",
        "ticket_id": ticket_id,
        "session_id": session_id,
        "job_id": job_id,
        "kind": kind_action,
        "title": title,
        "details": details or {},
        "ts": time.time()
    }
    
    return (kind, payload)


def make_tool_call_started(
    ticket_id: str,
    session_id: str,
    job_id: str,
    call_id: str,
    tool_name: str,
    params: dict | None = None
) -> tuple[str, dict]:
    """
    Создает событие tool_call_started.
    
    Protocol V3: ticket_id обязателен.
    
    Args:
        ticket_id: Идентификатор тикета (ОБЯЗАТЕЛЬНО)
        session_id: Идентификатор сессии
        job_id: Идентификатор задачи
        call_id: Уникальный идентификатор вызова инструмента
        tool_name: Имя инструмента
        params: Параметры вызова (безопасные, без секретов)
        
    Returns:
        (kind, payload) для передачи в enqueue_event()
    """
    kind = "tool_started"
    payload = {
        "event": "tool_call_started",
        "ticket_id": ticket_id,
        "session_id": session_id,
        "job_id": job_id,
        "call_id": call_id,
        "tool_name": tool_name,
        "params": params or {},
        "ts": time.time()
    }
    
    return (kind, payload)


def make_tool_call_result(
    ticket_id: str,
    session_id: str,
    job_id: str,
    call_id: str,
    tool_name: str,
    status: str,
    summary: str,
    result: dict | None = None
) -> tuple[str, dict]:
    """
    Создает событие tool_call_result.
    
    Protocol V3: ticket_id обязателен.
    
    Args:
        ticket_id: Идентификатор тикета (ОБЯЗАТЕЛЬНО)
        session_id: Идентификатор сессии
        job_id: Идентификатор задачи
        call_id: Уникальный идентификатор вызова инструмента (тот же, что в tool_call_started)
        tool_name: Имя инструмента
        status: Статус выполнения ("success" | "error")
        summary: Краткое описание результата
        result: Результат выполнения (маленький JSON, без больших дампов)
        
    Returns:
        (kind, payload) для передачи в enqueue_event()
    """
    kind = "tool_completed" if status == "success" else "tool_failed"
    payload = {
        "event": "tool_call_result",
        "ticket_id": ticket_id,
        "session_id": session_id,
        "job_id": job_id,
        "call_id": call_id,
        "tool_name": tool_name,
        "status": status,
        "summary": summary,
        "result": result or {},
        "ts": time.time()
    }
    
    return (kind, payload)


# Legacy compatibility wrappers
def make_chat_message_legacy(
    job_id: str, 
    from_: str, 
    text: str, 
    message_id: str | None = None, 
    seq: int | None = None
) -> dict:
    """Legacy wrapper для make_chat_message."""
    message_id = message_id or str(uuid4())
    result = {
        "event": "chat_message",
        "job_id": job_id,
        "message_id": message_id,
        "from": from_,
        "text": text,
        "ts": time.time()
    }
    if seq is not None:
        result["seq"] = seq
    return result


def make_job_status_event_legacy(job_id: str, event: str, **extra) -> dict:
    """Legacy wrapper для make_job_status_event."""
    return {"event": event, "job_id": job_id, "ts": time.time(), **extra}


class JobManager:
    """
    Менеджер фоновых задач.
    
    Protocol V3 изменения:
    - Любая задача автоматически создаёт тикет (замечание 8)
    - ticket_id обязателен в событиях
    - Маппинг job_type → ticket category
    - Политика merge при конфликте тикетов (server overwrites)
    
    Управляет выполнением фоновых задач через asyncio.Task,
    сохраняет статус в БД и отправляет события в outbox.
    """
    
    def __init__(
        self,
        db_manager,
        outbox_enqueue_func: Callable,
        logger_instance=None
    ):
        """
        Инициализация JobManager.
        
        Args:
            db_manager: Экземпляр DatabaseManager для работы с БД
            outbox_enqueue_func: Функция для записи в outbox (db_manager.enqueue_job_event)
            logger_instance: Экземпляр логгера (опционально, используется loguru по умолчанию)
        """
        self.db = db_manager
        self.enqueue = outbox_enqueue_func
        self.log = logger_instance or logger
        self.tasks: Dict[str, asyncio.Task] = {}
        self.cancel_flags: Dict[str, asyncio.Event] = {}
        self.inboxes: dict[str, asyncio.Queue] = {}   # job_id -> queue
        self.message_dedup: dict[str, set[str]] = {}  # job_id -> set(message_id) (MVP дедуп на уровне доставки)
        self.message_processed: dict[str, set[str]] = {}  # job_id -> set(message_id) (дедуп на уровне обработки в job loop)
        self.job_device: Dict[str, str] = {}  # job_id -> device_id
        self.job_ticket: Dict[str, str] = {}  # job_id -> ticket_id (Protocol V3)
        self.job_locks: Dict[str, asyncio.Lock] = {}  # job_id -> Lock для идемпотентного start_job
    
    async def start_job(
        self,
        job_type: str,
        device_id: str,
        actor_role: str,
        params: dict
    ) -> dict:
        """
        Запускает новую фоновую задачу (идемпотентно).
        
        Protocol V3: Любая задача создаёт тикет (замечание 8).
        
        Если job с таким job_id уже запущен, возвращает информацию о нем без создания дубликата.
        Если job существует в БД но не запущен (zombie после restart), возобновляет его.
        
        Args:
            job_type: Тип задачи (например, "chat_echo", "support_chat")
            device_id: Идентификатор устройства
            actor_role: Роль актора
            params: Параметры задачи
            
        Returns:
            Словарь с информацией о задаче:
            {
                "job_id": str,
                "ticket_id": str,  # Protocol V3
                "job_type": str,
                "status": str,
                "started": bool,
                "start_reason": "created" | "already_running" | "resumed"
            }
        """
        try:
            # Сервер может задать job_id и ticket_id (для сквозной chat session)
            requested_job_id = None
            requested_ticket_id = None
            if isinstance(params, dict):
                requested_job_id = params.get("job_id") or params.get("_job_id")
                requested_ticket_id = params.get("ticket_id")

            if requested_job_id:
                job_id = str(requested_job_id)
            else:
                job_id = str(uuid4())

            # Получаем или создаем lock для этого job_id
            if job_id not in self.job_locks:
                self.job_locks[job_id] = asyncio.Lock()
            
            async with self.job_locks[job_id]:
                # Чистим завершенные задачи (done tasks) для корректной проверки активности
                if job_id in self.tasks and self.tasks[job_id].done():
                    del self.tasks[job_id]
                    self.log.debug(f"🧹 Удалена завершенная задача: job_id={job_id}")
                
                # Определяем, активна ли задача (единый предикат)
                is_active = job_id in self.tasks
                
                # Проверяем, есть ли уже активная задача
                if is_active:
                    self.log.info(f"🔁 Job уже запущен: job_id={job_id}, job_type={job_type}")
                    return {
                        "job_id": job_id,
                        "ticket_id": self.job_ticket.get(job_id),
                        "job_type": job_type,
                        "status": "running",
                        "started": False,
                        "start_reason": "already_running"
                    }

                # Проверяем БД: есть ли job с таким id
                existing = await self.db.get_job(job_id)
                
                if existing:
                    # Job существует в БД
                    if existing['status'] in ('queued', 'running'):
                        # Job в БД со статусом queued/running, но нет активной задачи
                        # Это zombie job (после restart) или queued job - возобновляем
                        self.log.warning(
                            f"⚠️  Обнаружен zombie/queued job: job_id={job_id}, "
                            f"status={existing['status']}, active={is_active}. Возобновляю..."
                        )
                        return await self._resume_job(
                            job_id=job_id,
                            job_type=existing['job_type'],
                            device_id=device_id,
                            existing_job=existing
                        )
                    else:
                        # Job завершен (success/error/stopped) - нельзя перезапустить с тем же id
                        self.log.error(
                            f"❌ Job с таким id уже завершен: job_id={job_id}, "
                            f"status={existing['status']}"
                        )
                        return {
                            "error": "job_already_finished",
                            "job_id": job_id,
                            "status": existing['status']
                        }
                
                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                # TICKET-FIRST: Создание/валидация тикета (замечание 8)
                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                
                if requested_ticket_id:
                    ticket_id = requested_ticket_id
                    # Проверяем существует ли тикет локально
                    existing_ticket = await self.db.get_ticket_state(ticket_id)
                    
                    if existing_ticket:
                        # Политика merge: server overwrites (замечание 8)
                        self.log.debug(
                            f"🎫 Ticket exists locally: {ticket_id}, "
                            f"applying server overwrites policy"
                        )
                        # Обновляем статус если сервер прислал ticket_id
                        await self.db.create_ticket_state(
                            ticket_id=ticket_id,
                            status="open",
                            category=map_job_type_to_category(job_type),
                            title=params.get("title"),
                            priority=params.get("priority"),
                            metadata=params
                        )
                    else:
                        # Создаём новый ticket_state с server ticket_id
                        await self.db.create_ticket_state(
                            ticket_id=ticket_id,
                            status="open",
                            category=map_job_type_to_category(job_type),
                            title=params.get("title", f"{job_type} task"),
                            priority=params.get("priority", "normal"),
                            metadata=params
                        )
                        self.log.info(f"🎫 Created ticket from server: {ticket_id}")
                else:
                    # Автоматически создаём тикет (замечание 8)
                    ticket_id = str(uuid4())
                    category = map_job_type_to_category(job_type)
                    title = params.get("title", f"{job_type} task")
                    priority = params.get("priority", "normal")
                    
                    await self.db.create_ticket_state(
                        ticket_id=ticket_id,
                        status="open",
                        category=category,
                        title=title,
                        priority=priority,
                        metadata=params
                    )
                    
                    self.log.info(
                        f"🎫 Auto-created ticket: ticket_id={ticket_id}, "
                        f"category={category}, job_type={job_type}"
                    )
                
                # Новый job - создаем
                # Создаем очередь для входящих событий
                queue = asyncio.Queue()
                self.inboxes[job_id] = queue
                self.message_dedup[job_id] = set()
                self.message_processed[job_id] = set()
                self.job_device[job_id] = device_id
                self.job_ticket[job_id] = ticket_id  # Protocol V3
                
                # Формируем метаданные для сохранения в БД
                meta = {
                    "device_id": device_id,
                    "actor_role": actor_role,
                    "ticket_id": ticket_id,  # Protocol V3
                    "params": params
                }
                meta_json = json.dumps(meta, ensure_ascii=False)
                
                # Создаем запись в БД
                await self.db.create_job(
                    job_id=job_id,
                    job_type=job_type,
                    meta_json=meta_json,
                    ticket_id=ticket_id  # Protocol V3
                )
                
                # Устанавливаем статус "queued"
                await self.db.update_job_status(job_id, "queued")
                
                # Создаем Event для отмены задачи
                cancel_event = asyncio.Event()
                self.cancel_flags[job_id] = cancel_event
                
                # Создаем и запускаем задачу
                task = asyncio.create_task(
                    self._runner(
                        job_id=job_id,
                        ticket_id=ticket_id,  # Protocol V3
                        job_type=job_type,
                        device_id=device_id,
                        actor_role=actor_role,
                        params=params,
                        cancel_event=cancel_event
                    )
                )
                self.tasks[job_id] = task
                
                # Отправляем событие о старте задачи
                await self.enqueue(
                    job_id=job_id,
                    request_id=None,
                    device_id=device_id,
                    event_payload={
                        "event": "job_started",
                        "ticket_id": ticket_id,  # Protocol V3
                        "job_id": job_id,
                        "job_type": job_type,
                        "status": "queued"
                    }
                )
                
                self.log.info(f"✅ Задача запущена: job_id={job_id}, ticket_id={ticket_id}, job_type={job_type}")
                
                return {
                    "job_id": job_id,
                    "ticket_id": ticket_id,  # Protocol V3
                    "job_type": job_type,
                    "status": "queued",
                    "started": True,
                    "start_reason": "created"
                }
            
        except Exception as e:
            self.log.error(f"❌ Ошибка запуска задачи: {e}")
            raise
    
    async def _resume_job(
        self,
        job_id: str,
        job_type: str,
        device_id: str,
        existing_job: dict
    ) -> dict:
        """
        Возобновляет job после restart или из zombie состояния.
        
        Гарантирует инициализацию всех необходимых структур данных.
        
        Args:
            job_id: Идентификатор задачи
            job_type: Тип задачи
            device_id: Идентификатор устройства
            existing_job: Данные job из БД
            
        Returns:
            Словарь с информацией о возобновленной задаче
        """
        try:
            # Извлекаем meta из existing_job
            meta = existing_job.get('meta') or {}
            actor_role = meta.get('actor_role', 'system')
            params = meta.get('params', {})
            
            # Protocol V3: Получаем ticket_id из meta или existing_job
            ticket_id = meta.get('ticket_id') or existing_job.get('ticket_id')
            
            if not ticket_id:
                # Если ticket_id нет, создаём автоматически (для legacy jobs)
                ticket_id = str(uuid4())
                await self.db.create_ticket_state(
                    ticket_id=ticket_id,
                    status="open",
                    category=map_job_type_to_category(job_type),
                    title=f"{job_type} task (resumed)",
                    priority="normal",
                    metadata=params
                )
                self.log.warning(
                    f"⚠️  Legacy job without ticket_id, created: {ticket_id}"
                )
            
            # КРИТИЧНО: Инициализируем ВСЕ структуры данных для job
            # (используем setdefault для безопасности, если частично инициализировано)
            
            # Inbox для входящих событий
            if job_id not in self.inboxes:
                self.inboxes[job_id] = asyncio.Queue()
            
            # Dedup sets (in-memory cache)
            self.message_dedup.setdefault(job_id, set())
            self.message_processed.setdefault(job_id, set())
            
            # Device и ticket mapping
            self.job_device[job_id] = device_id
            self.job_ticket[job_id] = ticket_id  # Protocol V3
            
            # Cancel event для graceful shutdown
            cancel_event = asyncio.Event()
            self.cancel_flags[job_id] = cancel_event
            
            # Создаем и запускаем задачу с флагом resumed=True
            task = asyncio.create_task(
                self._runner(
                    job_id=job_id,
                    ticket_id=ticket_id,  # Protocol V3
                    job_type=job_type,
                    device_id=device_id,
                    actor_role=actor_role,
                    params=params,
                    cancel_event=cancel_event,
                    resumed=True
                )
            )
            self.tasks[job_id] = task
            
            # Отправляем событие job_running с resumed=true
            await self.enqueue(
                job_id=job_id,
                request_id=None,
                device_id=device_id,
                event_payload={
                    "event": "job_running",
                    "ticket_id": ticket_id,  # Protocol V3
                    "job_id": job_id,
                    "job_type": job_type,
                    "resumed": True
                }
            )
            
            self.log.info(f"🔄 Задача возобновлена: job_id={job_id}, ticket_id={ticket_id}, job_type={job_type}")
            
            return {
                "job_id": job_id,
                "ticket_id": ticket_id,  # Protocol V3
                "job_type": job_type,
                "status": "running",
                "started": True,
                "start_reason": "resumed"
            }
            
        except Exception as e:
            self.log.error(f"❌ Ошибка возобновления задачи {job_id}: {e}")
            raise
    
    async def stop_job(self, job_id: str) -> dict:
        """
        Останавливает задачу.
        
        Args:
            job_id: Идентификатор задачи
            
        Returns:
            Словарь со статусом задачи или {"error": "not_found"}
        """
        if job_id not in self.tasks:
            return {"error": "not_found"}
        
        try:
            # Получаем ticket_id для события
            ticket_id = self.job_ticket.get(job_id)
            
            # Устанавливаем флаг отмены
            if job_id in self.cancel_flags:
                self.cancel_flags[job_id].set()
            
            # Пытаемся отменить задачу
            task = self.tasks[job_id]
            task.cancel()
            
            # Обновляем статус в БД
            await self.db.update_job_status(job_id, "stopped")
            
            # Обновляем статус тикета
            if ticket_id:
                await self.db.update_ticket_status(ticket_id, "closed")
            
            # Отправляем событие об остановке
            job = await self.db.get_job(job_id)
            device_id = None
            if job and job.get('meta'):
                device_id = job['meta'].get('device_id')
            
            await self.enqueue(
                job_id=job_id,
                request_id=None,
                device_id=device_id,
                event_payload={
                    "event": "job_stopped",
                    "ticket_id": ticket_id,  # Protocol V3
                    "job_id": job_id,
                    "status": "stopped"
                }
            )
            
            # Удаляем из словарей
            if job_id in self.tasks:
                del self.tasks[job_id]
            if job_id in self.cancel_flags:
                del self.cancel_flags[job_id]
            try:
                if job_id in self.inboxes:
                    del self.inboxes[job_id]
                if job_id in self.message_dedup:
                    del self.message_dedup[job_id]
                if job_id in self.message_processed:
                    del self.message_processed[job_id]
                if job_id in self.job_device:
                    del self.job_device[job_id]
                if job_id in self.job_ticket:
                    del self.job_ticket[job_id]
            except Exception:
                pass
            
            self.log.info(f"🛑 Задача остановлена: job_id={job_id}")
            
            return {"job_id": job_id, "ticket_id": ticket_id, "status": "stopped"}
            
        except Exception as e:
            self.log.error(f"❌ Ошибка остановки задачи {job_id}: {e}")
            raise
    
    async def get_job_status(self, job_id: str) -> dict:
        """
        Получает статус задачи.
        
        Args:
            job_id: Идентификатор задачи
            
        Returns:
            Словарь с данными задачи или None если не найдена
        """
        return await self.db.get_job(job_id)
    
    async def list_jobs(self, limit: int = 50) -> dict:
        """
        Получает список задач.
        
        Args:
            limit: Максимальное количество записей
            
        Returns:
            Словарь с ключом "jobs" и списком задач
        """
        jobs = await self.db.list_jobs(limit=limit)
        return {"jobs": jobs}
    
    async def recover_jobs_on_startup(self) -> dict:
        """
        Восстанавливает состояние jobs после перезапуска агента.
        
        Проверяет все jobs в БД со статусом "running" или "queued":
        - Если job устарел (превышен max_session_sec), останавливает его и уведомляет сервер
        - Если job еще актуален, возобновляет его выполнение
        
        Должен вызываться при старте агента после инициализации БД и перед приемом новых команд.
        
        Returns:
            Словарь со статистикой восстановления:
            {
                "recovered": int,  # количество возобновленных jobs
                "stopped": int,    # количество остановленных (expired) jobs
                "errors": int      # количество ошибок
            }
        """
        self.log.info("🔄 Начинаю восстановление jobs после перезапуска...")
        
        recovered_count = 0
        stopped_count = 0
        error_count = 0
        
        try:
            # Используем прямой SQL запрос для получения jobs со статусом running или queued
            import aiosqlite
            async with aiosqlite.connect(self.db._db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    """
                    SELECT job_id, job_type, status, created_at, started_at, 
                           updated_at, meta_json, ticket_id
                    FROM jobs
                    WHERE status IN ('running', 'queued')
                    ORDER BY created_at ASC
                    """
                )
                rows = await cursor.fetchall()
            
            if not rows:
                self.log.info("✅ Нет jobs для восстановления")
                return {"recovered": 0, "stopped": 0, "errors": 0}
            
            self.log.info(f"📋 Найдено {len(rows)} jobs для проверки")
            
            now = time.time()
            
            for row in rows:
                job_id = row['job_id']
                job_type = row['job_type']
                status = row['status']
                started_at = row['started_at']
                created_at = row['created_at']
                meta_json = row['meta_json']
                ticket_id = row['ticket_id']  # Protocol V3
                
                try:
                    # Парсим meta для получения параметров
                    meta = {}
                    if meta_json:
                        try:
                            meta = json.loads(meta_json)
                        except json.JSONDecodeError:
                            self.log.warning(f"⚠️  Не удалось распарсить meta_json для job_id={job_id}")
                    
                    params = meta.get('params', {})
                    device_id = meta.get('device_id', 'unknown')
                    
                    # Protocol V3: ticket_id из meta или БД
                    if not ticket_id:
                        ticket_id = meta.get('ticket_id')
                    
                    # Проверяем, есть ли уже активная задача (не должно быть, но проверим)
                    if job_id in self.tasks and not self.tasks[job_id].done():
                        self.log.debug(f"⏭️  Job {job_id} уже активен, пропускаю")
                        continue
                    
                    # Определяем, устарел ли job
                    max_session_sec = params.get('max_session_sec', 14400)  # 4 часа по умолчанию
                    
                    # Используем started_at если есть, иначе created_at
                    job_start_time = started_at if started_at else created_at
                    
                    if job_start_time and (now - job_start_time) > max_session_sec:
                        # Job устарел - останавливаем
                        reason = f"Recovered on startup: expired (max_session={max_session_sec}s)"
                        self.log.warning(
                            f"⏱️  Job {job_id} ({job_type}) expired: "
                            f"started_at={job_start_time}, age={now - job_start_time:.0f}s, "
                            f"max={max_session_sec}s"
                        )
                        
                        # Обновляем статус в БД
                        await self.db.update_job_status(
                            job_id=job_id,
                            status="stopped",
                            last_error=reason
                        )
                        
                        # Обновляем статус тикета
                        if ticket_id:
                            await self.db.update_ticket_status(ticket_id, "closed")
                        
                        # Отправляем события в outbox
                        await self.enqueue(
                            job_id=job_id,
                            request_id=None,
                            device_id=device_id,
                            event_payload={
                                "event": "job_stopped",
                                "ticket_id": ticket_id,  # Protocol V3
                                "job_id": job_id,
                                "job_type": job_type,
                                "reason": "recovered_expired",
                                "ts": time.time()
                            }
                        )
                        
                        # Для support_chat/support_ticket отправляем chat_ended
                        if job_type in ('support_chat', 'support_ticket'):
                            chat_ended_event = {
                                "event": "chat_ended",
                                "ticket_id": ticket_id,  # Protocol V3
                                "job_id": job_id,
                                "reason": "recovered_expired",
                                "ts": time.time()
                            }
                            
                            # Добавляем session_id если есть
                            if 'session_id' in params:
                                chat_ended_event['session_id'] = params['session_id']
                            
                            await self.enqueue(
                                job_id=job_id,
                                request_id=None,
                                device_id=device_id,
                                event_payload=chat_ended_event
                            )
                        
                        stopped_count += 1
                    else:
                        # Job еще актуален - возобновляем
                        self.log.info(
                            f"🔄 Возобновляю job {job_id} ({job_type}): "
                            f"age={now - job_start_time:.0f}s, max={max_session_sec}s"
                        )
                        
                        # Используем start_job для возобновления (он идемпотентен)
                        actor_role = meta.get('actor_role', 'system')
                        result = await self.start_job(
                            job_type=job_type,
                            device_id=device_id,
                            actor_role=actor_role,
                            params=params
                        )
                        
                        if result.get('started') or result.get('start_reason') == 'already_running':
                            recovered_count += 1
                        else:
                            self.log.error(f"❌ Не удалось возобновить job {job_id}: {result}")
                            error_count += 1
                
                except Exception as e:
                    self.log.error(f"❌ Ошибка восстановления job {job_id}: {e}")
                    error_count += 1
            
            self.log.success(
                f"✅ Восстановление завершено: recovered={recovered_count}, "
                f"stopped={stopped_count}, errors={error_count}"
            )
            
            return {
                "recovered": recovered_count,
                "stopped": stopped_count,
                "errors": error_count
            }
            
        except Exception as e:
            self.log.error(f"❌ Критическая ошибка при восстановлении jobs: {e}")
            return {
                "recovered": recovered_count,
                "stopped": stopped_count,
                "errors": error_count + 1
            }
    
    async def _runner(
        self,
        job_id: str,
        ticket_id: str,  # Protocol V3
        job_type: str,
        device_id: str,
        actor_role: str,
        params: dict,
        cancel_event: asyncio.Event,
        resumed: bool = False
    ) -> None:
        """
        Внутренний метод для выполнения задачи.
        
        Args:
            job_id: Идентификатор задачи
            ticket_id: Идентификатор тикета (Protocol V3)
            job_type: Тип задачи
            device_id: Идентификатор устройства
            actor_role: Роль актора
            params: Параметры задачи
            cancel_event: Event для отмены задачи
            resumed: True если job возобновлен после restart (не отправляем job_started)
        """
        try:
            # Обновляем статус на "running"
            await self.db.update_job_status(job_id, "running")
            
            # Обновляем статус тикета
            await self.db.update_ticket_status(ticket_id, "in_progress")
            
            # Отправляем событие о запуске выполнения (только если не resumed)
            if not resumed:
                await self.enqueue(
                    job_id=job_id,
                    request_id=None,
                    device_id=device_id,
                    event_payload={
                        "event": "job_running",
                        "ticket_id": ticket_id,  # Protocol V3
                        "job_id": job_id,
                        "job_type": job_type
                    }
                )
            
            # Выполняем задачу в зависимости от типа
            if job_type == "chat_echo":
                await self._run_chat_echo(
                    job_id=job_id,
                    ticket_id=ticket_id,  # Protocol V3
                    device_id=device_id,
                    params=params,
                    cancel_event=cancel_event
                )
            elif job_type == "support_chat":
                await self._job_support_chat(
                    job_id=job_id,
                    ticket_id=ticket_id,  # Protocol V3
                    device_id=device_id,
                    cancel_event=cancel_event,
                    params=params
                )
            elif job_type == "support_ticket":
                await self._job_support_ticket(
                    job_id=job_id,
                    ticket_id=ticket_id,  # Protocol V3
                    device_id=device_id,
                    actor_role=actor_role,
                    params=params,
                    cancel_event=cancel_event
                )
            else:
                raise ValueError(f"Неизвестный тип задачи: {job_type}")
            
            # Если задача завершилась успешно
            await self.db.update_job_status(job_id, "success")
            await self.db.update_ticket_status(ticket_id, "closed")
            
            await self.enqueue(
                job_id=job_id,
                request_id=None,
                device_id=device_id,
                event_payload={
                    "event": "job_succeeded",
                    "ticket_id": ticket_id,  # Protocol V3
                    "job_id": job_id,
                    "job_type": job_type,
                    "result": {"status": "completed"}
                }
            )
            
        except JobCompletedException as e:
            # Задача завершилась с указанной причиной
            reason = e.reason
            if reason == "stopped":
                status = "stopped"
                event_name = "job_stopped"
            else:
                status = "success"
                event_name = "job_succeeded"
            
            await self.db.update_job_status(job_id, status)
            await self.db.update_ticket_status(ticket_id, "closed")
            
            await self.enqueue(
                job_id=job_id,
                request_id=None,
                device_id=device_id,
                event_payload={
                    "event": event_name,
                    "ticket_id": ticket_id,  # Protocol V3
                    "job_id": job_id,
                    "job_type": job_type,
                    "status": status,
                    "reason": reason
                }
            )
            
        except asyncio.CancelledError:
            # Задача была отменена
            self.log.info(f"⚠️ Задача отменена: job_id={job_id}")
            await self.db.update_job_status(job_id, "stopped", last_error="Cancelled")
            await self.db.update_ticket_status(ticket_id, "closed")
            raise
        except Exception as e:
            # Ошибка выполнения задачи
            error_msg = str(e)
            self.log.error(f"❌ Ошибка выполнения задачи {job_id}: {error_msg}")
            await self.db.update_job_status(job_id, "error", last_error=error_msg)
            await self.db.update_ticket_status(ticket_id, "closed")
            
            await self.enqueue(
                job_id=job_id,
                request_id=None,
                device_id=device_id,
                event_payload={
                    "event": "job_failed",
                    "ticket_id": ticket_id,  # Protocol V3
                    "job_id": job_id,
                    "job_type": job_type,
                    "error": error_msg
                }
            )
        finally:
            # Удаляем из словарей после завершения (всегда выполняется)
            if job_id in self.tasks:
                del self.tasks[job_id]
            if job_id in self.cancel_flags:
                del self.cancel_flags[job_id]
            try:
                if job_id in self.inboxes:
                    del self.inboxes[job_id]
                if job_id in self.message_dedup:
                    del self.message_dedup[job_id]
                if job_id in self.message_processed:
                    del self.message_processed[job_id]
                if job_id in self.job_device:
                    del self.job_device[job_id]
                if job_id in self.job_ticket:
                    del self.job_ticket[job_id]
            except Exception:
                pass
    
    async def emit_agent_action(
        self,
        job_id: str,
        ticket_id: str,
        session_id: str,
        device_id: str,
        kind: str,
        title: str,
        details: dict | None = None
    ) -> None:
        """
        Отправляет событие agent_action в outbox.
        
        Args:
            job_id: Идентификатор задачи
            ticket_id: Идентификатор тикета (Protocol V3)
            session_id: Идентификатор сессии
            device_id: Идентификатор устройства
            kind: Тип действия ("status" | "collect" | "tool_call" | "note" | "error")
            title: Краткое описание действия
            details: Дополнительные детали
        """
        event_payload = {
            "event": "agent_action",
            "ticket_id": ticket_id,
            "session_id": session_id,
            "job_id": job_id,
            "kind": kind,
            "title": title,
            "details": details or {},
            "ts": time.time()
        }
        
        await self.enqueue(
            job_id=job_id,
            request_id=None,
            device_id=device_id,
            event_payload=event_payload
        )
        
        self.log.debug(
            f"📋 emit_agent_action: ticket_id={ticket_id} kind={kind} title='{title}'"
        )
    
    async def emit_tool_call(
        self,
        job_id: str,
        ticket_id: str,
        session_id: str,
        device_id: str,
        call_id: str,
        tool_name: str,
        params: dict | None = None
    ) -> None:
        """
        Отправляет событие tool_call_started в outbox.
        
        Args:
            job_id: Идентификатор задачи
            ticket_id: Идентификатор тикета (Protocol V3)
            session_id: Идентификатор сессии
            device_id: Идентификатор устройства
            call_id: Уникальный идентификатор вызова
            tool_name: Имя инструмента
            params: Параметры вызова
        """
        event_payload = {
            "event": "tool_call_started",
            "ticket_id": ticket_id,
            "session_id": session_id,
            "job_id": job_id,
            "call_id": call_id,
            "tool_name": tool_name,
            "params": params or {},
            "ts": time.time()
        }
        
        await self.enqueue(
            job_id=job_id,
            request_id=None,
            device_id=device_id,
            event_payload=event_payload
        )
        
        self.log.debug(
            f"🔧 emit_tool_call_started: call_id={call_id} tool_name={tool_name}"
        )
    
    async def emit_tool_call_result(
        self,
        job_id: str,
        ticket_id: str,
        session_id: str,
        device_id: str,
        call_id: str,
        tool_name: str,
        status: str,
        summary: str,
        result: dict | None = None
    ) -> None:
        """
        Отправляет событие tool_call_result в outbox.
        
        Args:
            job_id: Идентификатор задачи
            ticket_id: Идентификатор тикета (Protocol V3)
            session_id: Идентификатор сессии
            device_id: Идентификатор устройства
            call_id: Уникальный идентификатор вызова (тот же, что в tool_call_started)
            tool_name: Имя инструмента
            status: Статус выполнения ("success" | "error")
            summary: Краткое описание результата
            result: Результат выполнения
        """
        event_payload = {
            "event": "tool_call_result",
            "ticket_id": ticket_id,
            "session_id": session_id,
            "job_id": job_id,
            "call_id": call_id,
            "tool_name": tool_name,
            "status": status,
            "summary": summary,
            "result": result or {},
            "ts": time.time()
        }
        
        await self.enqueue(
            job_id=job_id,
            request_id=None,
            device_id=device_id,
            event_payload=event_payload
        )
        
        self.log.debug(
            f"✅ emit_tool_call_result: call_id={call_id} status={status} summary='{summary}'"
        )
    
    async def emit_chat_message(
        self,
        job_id: str,
        device_id: str,
        from_: str,
        text: str,
        ticket_id: str | None = None,
        session_id: str | None = None
    ) -> str:
        """
        Отправляет chat_message с автоматическим seq и ts.
        
        Args:
            job_id: Идентификатор задачи
            device_id: Идентификатор устройства
            from_: Отправитель сообщения ("user", "agent", "support", "system")
            text: Текст сообщения
            ticket_id: Идентификатор тикета (Protocol V3 - получается из job_ticket если не передан)
            session_id: Идентификатор сессии (опционально)
            
        Returns:
            message_id созданного сообщения
        """
        # Protocol V3: ticket_id обязателен
        if not ticket_id:
            ticket_id = self.job_ticket.get(job_id)
        
        if not ticket_id:
            # Fallback: создаём ticket_id автоматически
            ticket_id = str(uuid4())
            self.job_ticket[job_id] = ticket_id
            self.log.warning(
                f"⚠️  emit_chat_message: auto-created ticket_id={ticket_id} for job_id={job_id}"
            )
        
        # Получаем следующий seq из БД
        seq = await self.db.get_next_seq(job_id)
        
        # Создаем сообщение
        message_id = str(uuid4())
        message = {
            "event": "chat_message",
            "ticket_id": ticket_id,  # Protocol V3
            "job_id": job_id,
            "message_id": message_id,
            "from": from_,
            "text": text,
            "seq": seq,
            "ts": time.time()
        }
        
        # Добавляем session_id если передан
        if session_id:
            message["session_id"] = session_id
        
        # Отправляем в outbox
        await self.enqueue(
            job_id=job_id,
            request_id=str(uuid4()),
            device_id=device_id,
            event_payload=message
        )
        
        return message_id
    
    async def _ack_event_delivered(
        self,
        job_id: str,
        device_id: str,
        message_id: str,
        event: dict
    ) -> None:
        """
        Отправляет подтверждение доставки события (event_delivered ACK).
        
        Args:
            job_id: Идентификатор задачи
            device_id: Идентификатор устройства
            message_id: Идентификатор сообщения
            event: Исходное событие (для извлечения ticket_id/session_id)
        """
        try:
            # Protocol V3: ticket_id обязателен
            ticket_id = event.get("ticket_id") or self.job_ticket.get(job_id)
            
            receipt = {
                "event": "event_delivered",
                "ticket_id": ticket_id,  # Protocol V3
                "job_id": job_id,
                "message_id": message_id,
                "delivered": True,
                "ts": time.time()
            }
            
            # Добавляем session_id из исходного события (если есть)
            if "session_id" in event:
                receipt["session_id"] = event["session_id"]
            
            await self.enqueue(
                job_id=job_id,
                request_id=str(uuid4()),
                device_id=device_id,
                event_payload=receipt
            )
        except Exception as e:
            self.log.warning(f"Не удалось отправить подтверждение доставки для job_id={job_id}: {e}")
    
    async def deliver_event(self, job_id: str, event: dict) -> dict:
        """
        Доставляет событие в очередь конкретного job с persistent dedup (атомарно).
        
        Args:
            job_id: Идентификатор задачи
            event: Словарь с событием (может содержать message_id для дедупликации)
            
        Returns:
            Словарь с результатом:
            - {"ok": False, "error": "JOB_NOT_FOUND"} - если job не найден
            - {"ok": True, "delivered": True, "chat_job_id": str, "message_id": str, "dedup_hit": True, "received_at_ts": float, "queued": False} - если сообщение уже было доставлено (dedup)
            - {"ok": True, "delivered": True, "chat_job_id": str, "message_id": str|None, "dedup_hit": False, "received_at_ts": float, "queued": True} - если событие успешно доставлено
        """
        received_at_ts = time.time()
        message_id = event.get("message_id")
        
        # Проверка существования job_id
        if job_id not in self.inboxes:
            # Job не найден - но если есть message_id и device_id, отправляем ACK с queued=false
            # чтобы избежать бесконечных ретраев на сервере
            if message_id:
                device_id = self.job_device.get(job_id) or event.get("device_id")
                if device_id:
                    self.log.warning(
                        f"⚠️  Job не найден, но отправляю ACK для предотвращения ретраев: "
                        f"job_id={job_id}, message_id={message_id}"
                    )
                    await self._ack_event_delivered(job_id, device_id, message_id, event)
            
            return {"ok": False, "error": "JOB_NOT_FOUND"}
        
        # PERSISTENT DEDUP: атомарная вставка (INSERT OR IGNORE)
        if message_id:
            # Используем setdefault для безопасности (если структуры не инициализированы)
            dedup_set = self.message_dedup.setdefault(job_id, set())
            
            # Проверяем hot-cache (быстрая проверка в памяти)
            if message_id in dedup_set:
                self.log.debug(
                    f"🔁 In-memory dedup hit: job_id={job_id}, message_id={message_id}"
                )
                
                # Отправляем ACK
                device_id = self.job_device.get(job_id)
                if device_id:
                    await self._ack_event_delivered(job_id, device_id, message_id, event)
                
                return {
                    "ok": True,
                    "delivered": True,
                    "chat_job_id": job_id,
                    "message_id": message_id,
                    "dedup_hit": True,
                    "received_at_ts": received_at_ts,
                    "queued": False
                }
            
            # Атомарная вставка в БД (возвращает True если вставилось, False если было)
            inserted = await self.db.mark_message_seen(job_id, message_id)
            
            if not inserted:
                # Сообщение уже было обработано ранее (persistent dedup hit)
                self.log.debug(
                    f"🔁 Persistent dedup hit: job_id={job_id}, message_id={message_id}"
                )
                
                # Добавляем в hot-cache для будущих проверок
                dedup_set.add(message_id)
                
                # Отправляем ACK
                device_id = self.job_device.get(job_id)
                if device_id:
                    await self._ack_event_delivered(job_id, device_id, message_id, event)
                
                return {
                    "ok": True,
                    "delivered": True,
                    "chat_job_id": job_id,
                    "message_id": message_id,
                    "dedup_hit": True,
                    "received_at_ts": received_at_ts,
                    "queued": False
                }
            
            # Новое сообщение - добавляем в hot-cache
            dedup_set.add(message_id)
            
            self.log.debug(
                f"✅ Новое сообщение принято: job_id={job_id}, message_id={message_id}"
            )
        
        # Кладем событие в очередь
        await self.inboxes[job_id].put(event)
        
        # Отправляем подтверждение о доставке (ACK уровня приложения)
        if message_id:
            device_id = self.job_device.get(job_id)
            if device_id:
                await self._ack_event_delivered(job_id, device_id, message_id, event)
        
        return {
            "ok": True,
            "delivered": True,
            "chat_job_id": job_id,
            "message_id": message_id,
            "dedup_hit": False,
            "received_at_ts": received_at_ts,
            "queued": True
        }
    
    async def _run_chat_echo(
        self,
        job_id: str,
        ticket_id: str,  # Protocol V3
        device_id: str,
        params: dict,
        cancel_event: asyncio.Event
    ) -> None:
        """
        Выполняет тестовую задачу "chat_echo".
        
        Каждые 2 секунды отправляет job_event с chat_message 5 раз,
        затем завершается успехом. Учитывает cancel_event для graceful stop.
        
        Args:
            job_id: Идентификатор задачи
            ticket_id: Идентификатор тикета (Protocol V3)
            device_id: Идентификатор устройства
            params: Параметры задачи
            cancel_event: Event для отмены задачи
        """
        max_iterations = 5
        delay_seconds = 2.0
        
        for i in range(1, max_iterations + 1):
            # Проверяем флаг отмены
            if cancel_event.is_set():
                self.log.info(f"⚠️ Задача {job_id} получила сигнал отмены на итерации {i}")
                return
            
            # Отправляем событие chat_message
            await self.enqueue(
                job_id=job_id,
                request_id=None,
                device_id=device_id,
                event_payload={
                    "event": "chat_message",
                    "ticket_id": ticket_id,  # Protocol V3
                    "job_id": job_id,
                    "from": "agent",
                    "text": f"ping {i}"
                }
            )
            
            # Обновляем прогресс
            progress = i / max_iterations
            await self.db.update_job_status(job_id, "running", progress=progress)
            
            # Отправляем событие о прогрессе
            await self.enqueue(
                job_id=job_id,
                request_id=None,
                device_id=device_id,
                event_payload={
                    "event": "job_progress",
                    "ticket_id": ticket_id,  # Protocol V3
                    "job_id": job_id,
                    "progress": progress
                }
            )
            
            self.log.debug(f"📤 Отправлено сообщение {i}/{max_iterations} для задачи {job_id}")
            
            # Ждем перед следующей итерацией
            # Используем asyncio.wait для ожидания либо sleep, либо cancel_event
            done, pending = await asyncio.wait(
                [
                    asyncio.create_task(asyncio.sleep(delay_seconds)),
                    asyncio.create_task(cancel_event.wait())
                ],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Отменяем оставшуюся задачу
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            # Проверяем отмену после ожидания
            if cancel_event.is_set():
                self.log.info(f"⚠️ Задача {job_id} получила сигнал отмены после итерации {i}")
                return
        
        self.log.info(f"✅ Задача chat_echo завершена успешно: job_id={job_id}")
    
    async def _job_support_chat(
        self,
        job_id: str,
        ticket_id: str,  # Protocol V3
        device_id: str,
        cancel_event: asyncio.Event,
        params: dict
    ) -> None:
        """
        Выполняет задачу "support_chat" - базовый чатовый движок.
        
        Слушает входящие события из inbox и эмитит chat_message в ответ.
        Это базовый чатовый движок без GUI.
        
        Job живет до stop_job или до idle-timeout/max-session/end_session.
        
        Args:
            job_id: Идентификатор задачи
            ticket_id: Идентификатор тикета (Protocol V3)
            device_id: Идентификатор устройства
            cancel_event: Event для отмены задачи
            params: Параметры задачи
        """
        reason = None
        try:
            # Получаем параметры таймаутов из params
            idle_timeout_sec = params.get("idle_timeout_sec", 900)
            max_session_sec = params.get("max_session_sec", 14400)
            
            # Отправляем события о старте задачи
            await self.enqueue(
                job_id=job_id,
                request_id=None,
                device_id=device_id,
                event_payload={
                    "event": "job_started",
                    "ticket_id": ticket_id,  # Protocol V3
                    "job_id": job_id
                }
            )
            
            await self.enqueue(
                job_id=job_id,
                request_id=None,
                device_id=device_id,
                event_payload={
                    "event": "job_running",
                    "ticket_id": ticket_id,  # Protocol V3
                    "job_id": job_id
                }
            )
            
            # Отправляем событие chat_session для UI
            await self.enqueue(
                job_id=job_id,
                request_id=None,
                device_id=device_id,
                event_payload={
                    "event": "chat_session",
                    "ticket_id": ticket_id,  # Protocol V3
                    "job_id": job_id,
                    "ts": time.time(),
                    "title": params.get("title", "Support Chat"),
                    "participants": ["support", "agent"]
                }
            )
            
            # Отправляем приветственное сообщение
            await self.emit_chat_message(
                job_id=job_id,
                device_id=device_id,
                from_="agent",
                text="Support chat started",
                ticket_id=ticket_id  # Protocol V3
            )
            
            self.log.info(f"💬 Support chat запущен: job_id={job_id}, ticket_id={ticket_id}")
            
            # Инициализация дедупликации на уровне job loop
            seen_message_ids: set[str] = set()
            seen_max = params.get("seen_max", 5000)  # лимит, чтобы не рос бесконечно
            
            # Инициализация переменных времени
            started_at = time.time()
            last_activity = time.time()
            
            # Основной цикл обработки событий
            while True:
                # Проверка отмены
                if cancel_event.is_set():
                    reason = "stopped"
                    break
                
                # Проверка таймаутов
                now = time.time()
                if now - last_activity > idle_timeout_sec:
                    reason = "idle_timeout"
                    break
                
                if now - started_at > max_session_sec:
                    reason = "max_session"
                    break
                
                # Получение события с таймаутом
                try:
                    incoming = await asyncio.wait_for(
                        self.inboxes[job_id].get(),
                        timeout=1.0
                    )
                except TimeoutError:
                    continue
                
                # Обновляем время последней активности
                last_activity = time.time()
                
                # Обработка событий
                if incoming.get("event") == "chat_message":
                    msg_id = incoming.get("message_id")
                    
                    # Защитный слой дедупликации на уровне job loop
                    # (дополнительно к дедупу в deliver_event)
                    if msg_id:
                        if msg_id in seen_message_ids:
                            # Это повтор — ничего не отвечаем
                            self.log.debug(f"🔁 Duplicate chat_message ignored: job_id={job_id} message_id={msg_id}")
                            continue
                        seen_message_ids.add(msg_id)
                        # ограничение памяти:
                        if len(seen_message_ids) > seen_max:
                            # простая стратегия: очистить весь set (MVP)
                            # или хранить deque + set (лучше), но MVP достаточно:
                            seen_message_ids.clear()
                            seen_message_ids.add(msg_id)
                    
                    from_ = incoming.get("from")
                    text = incoming.get("text", "")
                    
                    self.log.debug(
                        f"📨 Получено сообщение от {from_}: {text[:50]}... "
                        f"(job_id={job_id}, message_id={msg_id})"
                    )
                    
                    # Для support_chat не создаём авто-echo, иначе в тикете появляются ложные ответы.
                    # Сообщение уже доставлено оператору и останется в истории тикета без дубля.
                    continue
                
                elif incoming.get("event") == "end_session":
                    reason = "end_session"
                    break
                
                # Поддерживаем stop событие для обратной совместимости
                elif incoming.get("event") == "stop":
                    reason = "stopped"
                    break
            
            # Отправляем событие chat_ended перед выходом
            if reason:
                await self.enqueue(
                    job_id=job_id,
                    request_id=None,
                    device_id=device_id,
                    event_payload={
                        "event": "chat_ended",
                        "ticket_id": ticket_id,  # Protocol V3
                        "job_id": job_id,
                        "reason": reason,
                        "ts": time.time()
                    }
                )
                self.log.info(f"💬 Support chat ended: job_id={job_id}, ticket_id={ticket_id}, reason={reason}")
                # Выбрасываем исключение для передачи reason в _runner
                raise JobCompletedException(reason)
                
        except JobCompletedException:
            # Пробрасываем исключение выше для обработки в _runner
            raise
        except Exception as e:
            self.log.error(f"❌ Ошибка в support_chat {job_id}: {e}")
            raise
    
    async def _job_support_ticket(
        self,
        job_id: str,
        ticket_id: str,  # Protocol V3
        device_id: str,
        actor_role: str,
        params: dict,
        cancel_event: asyncio.Event
    ) -> None:
        """
        Выполняет задачу "support_ticket" - чат по конкретному тикету с multiplex по ticket_id.
        
        Отличия от support_chat:
        - Привязка к ticket_id и session_id (обязательные параметры)
        - Отправка событий с ticket_id для мультиплексирования на сервере
        - Дополнительные события прозрачности (agent_action kind "status" и "note")
        - Поддержка события ticket_close в дополнение к end_session
        
        Job живет до stop_job или до idle-timeout/max-session/end_session/ticket_close.
        
        Args:
            job_id: Идентификатор задачи
            ticket_id: Идентификатор тикета (Protocol V3 - обязателен)
            device_id: Идентификатор устройства
            actor_role: Роль актора
            params: Параметры задачи (session_id, title, idle_timeout_sec, max_session_sec)
            cancel_event: Event для отмены задачи
        """
        reason = None
        try:
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # A1) ВАЛИДАЦИЯ ПАРАМЕТРОВ
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            
            session_id = params.get("session_id")
            
            # Protocol V3: ticket_id уже передан как аргумент
            if not ticket_id:
                error_msg = f"support_ticket requires ticket_id. Got: ticket_id={ticket_id}"
                self.log.error(f"❌ {error_msg}")
                
                # Публикуем событие job_failed
                await self.enqueue(
                    job_id=job_id,
                    request_id=None,
                    device_id=device_id,
                    event_payload={
                        "event": "job_failed",
                        "job_id": job_id,
                        "error": error_msg,
                        "ts": time.time()
                    }
                )
                
                raise ValueError(error_msg)
            
            # session_id опционален, генерируем если нет
            if not session_id:
                session_id = str(uuid4())
            
            # Получаем параметры таймаутов из params (с дефолтами как у support_chat)
            idle_timeout_sec = params.get("idle_timeout_sec", 900)  # 15 минут
            max_session_sec = params.get("max_session_sec", 14400)  # 4 часа
            title = params.get("title", "Support Ticket Session")
            
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # A2) СТАРТ JOB - ОТПРАВКА СОБЫТИЙ
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            
            # Отправляем событие agent_action kind "status" - Ticket session started
            await self.emit_agent_action(
                job_id=job_id,
                ticket_id=ticket_id,
                session_id=session_id,
                device_id=device_id,
                kind="status",
                title="Ticket session started",
                details={
                    "ticket_id": ticket_id,
                    "session_id": session_id,
                    "job_id": job_id
                }
            )
            
            # Отправляем событие job_started
            await self.enqueue(
                job_id=job_id,
                request_id=None,
                device_id=device_id,
                event_payload={
                    "event": "job_started",
                    "ticket_id": ticket_id,
                    "session_id": session_id,
                    "job_id": job_id
                }
            )
            
            # Отправляем событие job_running
            await self.enqueue(
                job_id=job_id,
                request_id=None,
                device_id=device_id,
                event_payload={
                    "event": "job_running",
                    "ticket_id": ticket_id,
                    "session_id": session_id,
                    "job_id": job_id
                }
            )
            
            # Отправляем событие chat_session для UI
            await self.enqueue(
                job_id=job_id,
                request_id=None,
                device_id=device_id,
                event_payload={
                    "event": "chat_session",
                    "job_id": job_id,
                    "ticket_id": ticket_id,
                    "session_id": session_id,
                    "ts": time.time(),
                    "title": title,
                    "participants": ["support", "agent"]
                }
            )
            
            self.log.info(f"🎫 Support ticket session started: job_id={job_id}, ticket_id={ticket_id}, session_id={session_id}")
            
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # A3) ИНИЦИАЛИЗАЦИЯ ДЕДУПЛИКАЦИИ НА УРОВНЕ JOB (ВТОРОЙ СЛОЙ)
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            
            seen_message_ids: set[str] = set()
            seen_max = params.get("seen_max", 5000)  # лимит, чтобы не рос бесконечно
            
            # Инициализация переменных времени
            started_at = time.time()
            last_activity = time.time()
            
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # ОСНОВНОЙ ЦИКЛ ОБРАБОТКИ СОБЫТИЙ
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            
            while True:
                # Проверка отмены
                if cancel_event.is_set():
                    reason = "stopped"
                    break
                
                # Проверка таймаутов
                now = time.time()
                if now - last_activity > idle_timeout_sec:
                    reason = "idle_timeout"
                    break
                
                if now - started_at > max_session_sec:
                    reason = "max_session"
                    break
                
                # Получение события с таймаутом
                try:
                    incoming = await asyncio.wait_for(
                        self.inboxes[job_id].get(),
                        timeout=1.0
                    )
                except TimeoutError:
                    continue
                
                # Обновляем время последней активности
                last_activity = time.time()
                
                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                # ОБРАБОТКА chat_message
                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                
                if incoming.get("event") == "chat_message":
                    msg_id = incoming.get("message_id")
                    
                    # Второй слой дедупликации (защитный слой на уровне job loop)
                    # Первый слой - это дедупликация в deliver_event
                    if msg_id:
                        if msg_id in seen_message_ids:
                            # Это повтор на уровне job - игнорируем
                            self.log.debug(
                                f"🔁 Duplicate chat_message ignored at job level: "
                                f"job_id={job_id} ticket_id={ticket_id} message_id={msg_id}"
                            )
                            continue
                        
                        seen_message_ids.add(msg_id)
                        
                        # Ограничение памяти для seen_message_ids
                        if len(seen_message_ids) > seen_max:
                            # Простая стратегия MVP: очистить весь set
                            # Альтернатива (лучше): хранить deque + set, но для MVP достаточно
                            seen_message_ids.clear()
                            seen_message_ids.add(msg_id)
                    
                    from_ = incoming.get("from")
                    text = incoming.get("text", "")
                    
                    self.log.debug(
                        f"📨 Получено сообщение от {from_} в ticket {ticket_id}: {text[:50]}... "
                        f"(job_id={job_id}, message_id={msg_id})"
                    )
                    
                    # Примечание: event_delivered уже отправлено в deliver_event
                    # Не дублируем отправку здесь
                    
                    # Отправляем agent_action kind "note" - User message received
                    await self.emit_agent_action(
                        job_id=job_id,
                        ticket_id=ticket_id,
                        session_id=session_id,
                        device_id=device_id,
                        kind="note",
                        title="User message received",
                        details={
                            "message_id": msg_id,
                            "from": from_,
                            "text_preview": text[:100]
                        }
                    )
                    
                    # MVP: Имитация tool call для эха
                    # Генерируем call_id для отслеживания вызова
                    call_id = str(uuid4())
                    
                    # Эмитим tool_call_started
                    await self.emit_tool_call(
                        job_id=job_id,
                        ticket_id=ticket_id,
                        session_id=session_id,
                        device_id=device_id,
                        call_id=call_id,
                        tool_name="support.echo",
                        params={"input_length": len(text)}
                    )
                    
                    # MVP: Echo - просто возвращаем текст обратно от support
                    reply_message_id = await self.emit_chat_message(
                        job_id=job_id,
                        device_id=device_id,
                        from_="support",
                        text=f"Echo: {text}",
                        ticket_id=ticket_id,
                        session_id=session_id
                    )
                    
                    # Эмитим tool_call_result
                    await self.emit_tool_call_result(
                        job_id=job_id,
                        ticket_id=ticket_id,
                        session_id=session_id,
                        device_id=device_id,
                        call_id=call_id,
                        tool_name="support.echo",
                        status="success",
                        summary="Echo generated",
                        result={"echo": text[:200], "reply_message_id": reply_message_id}
                    )
                    
                    # НЕ завершаем job здесь! Продолжаем цикл
                    continue
                
                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                # ОБРАБОТКА end_session
                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                
                elif incoming.get("event") == "end_session":
                    # Берем reason из события (если передан), иначе дефолтный
                    reason = incoming.get("reason", "closed_by_server")
                    self.log.info(f"🔚 Получено событие end_session для ticket {ticket_id}, reason={reason}")
                    break
                
                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                # ОБРАБОТКА ticket_close
                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                
                elif incoming.get("event") == "ticket_close":
                    # Берем reason из события (если передан), иначе дефолтный
                    reason = incoming.get("reason", "closed_by_server")
                    self.log.info(f"🎫 Получено событие ticket_close для ticket {ticket_id}, reason={reason}")
                    break
                
                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                # ОБРАБОТКА stop (для обратной совместимости)
                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                
                elif incoming.get("event") == "stop":
                    reason = "stopped"
                    break
            
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # ЗАВЕРШЕНИЕ JOB - ОТПРАВКА СОБЫТИЙ
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            
            if reason:
                # Отправляем событие chat_ended
                await self.enqueue(
                    job_id=job_id,
                    request_id=None,
                    device_id=device_id,
                    event_payload={
                        "event": "chat_ended",
                        "job_id": job_id,
                        "ticket_id": ticket_id,
                        "session_id": session_id,
                        "reason": reason,
                        "ts": time.time()
                    }
                )
                
                # Отправляем событие agent_action kind "status" - Ticket session ended
                await self.emit_agent_action(
                    job_id=job_id,
                    ticket_id=ticket_id,
                    session_id=session_id,
                    device_id=device_id,
                    kind="status",
                    title="Ticket session ended",
                    details={"reason": reason}
                )
                
                self.log.info(
                    f"🎫 Support ticket session ended: "
                    f"job_id={job_id}, ticket_id={ticket_id}, session_id={session_id}, reason={reason}"
                )
                
                # Выбрасываем исключение для передачи reason в _runner
                raise JobCompletedException(reason)
        
        except JobCompletedException:
            # Пробрасываем исключение выше для обработки в _runner
            raise
        except Exception as e:
            self.log.error(f"❌ Ошибка в support_ticket {job_id}: {e}")
            raise
