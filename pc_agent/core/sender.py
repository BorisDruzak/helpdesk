"""
Модуль для надежной доставки outbox через WebSocket.
Protocol V3: Типизированный NACK, ACK → DELETE, event_batch формат.

Изменения V3:
- ACK → DELETE из outbox (без статуса 'sent')
- Типизированный NACK с retryable/non-retryable
- event_batch формат для отправки
- Exponential backoff для retryable NACK
- Сохранение в outbox_sent_history для диагностики
"""

import asyncio
import json
import time
import uuid
import math
from datetime import datetime, timezone
from typing import Dict, Any, Callable, Optional, List
from loguru import logger

# Канонические NACK error codes (замечание 7)
NACK_ERROR_CODES = {
    "VALIDATION_ERROR": {"retryable": False},
    "UNAUTHORIZED": {"retryable": False},
    "FORBIDDEN": {"retryable": False},
    "SCHEMA_MISMATCH": {"retryable": False},
    "PAYLOAD_TOO_LARGE": {"retryable": False},
    "RATE_LIMITED": {"retryable": True},
    "TRANSIENT_STORAGE": {"retryable": True},
    "POSTGRES_UNAVAILABLE": {"retryable": True},
    "INTERNAL_ERROR": {"retryable": True},
}

# Backoff constants (замечание 7)
BACKOFF_MIN_SEC = 1
BACKOFF_MAX_SEC = 60
BACKOFF_MULTIPLIER = 2


def calculate_backoff(attempts: int) -> float:
    """
    Вычисляет exponential backoff.
    
    Formula: min(BACKOFF_MAX, BACKOFF_MIN * (BACKOFF_MULTIPLIER ^ attempts))
    """
    delay = BACKOFF_MIN_SEC * (BACKOFF_MULTIPLIER ** attempts)
    return min(delay, BACKOFF_MAX_SEC)


class WSOutboxFlusher:
    """
    Компонент для надежной доставки outbox через WebSocket.
    
    Protocol V3 изменения:
    - Использует claim_outbox_batch (атомарный select+mark)
    - ACK → DELETE из outbox
    - Типизированный NACK с exponential backoff
    - event_batch формат для отправки
    """
    
    def __init__(
        self,
        db_manager,
        device_id: str,
        logger_instance=None,
        max_inflight: int = 50,
        ack_timeout_sec: float = 30.0,
        resend_limit: int = 5
    ):
        """
        Инициализация WSOutboxFlusher.
        
        Args:
            db_manager: Экземпляр DatabaseManager
            device_id: Идентификатор устройства
            logger_instance: Экземпляр логгера
            max_inflight: Максимальное количество inflight сообщений
            ack_timeout_sec: Таймаут ожидания ACK в секундах
            resend_limit: Максимальное количество попыток (для exponential backoff)
        """
        self.db_manager = db_manager
        self.device_id = device_id
        self.log = logger_instance if logger_instance else logger
        self.max_inflight = max_inflight
        self.ack_timeout_sec = ack_timeout_sec
        self.resend_limit = resend_limit
        self.supports_outbox_batch = False
        
        # Трекинг inflight: outbox_id -> deadline_ts
        self.inflight_deadlines: Dict[int, float] = {}
        
        # Статистика
        self.stats = {
            'sent': 0,
            'acked': 0,
            'failed': 0,
            'resends': 0,
            'nack_retryable': 0,
            'nack_non_retryable': 0
        }
        
        # ACK counter для оптимизированного trimming (замечание 3.1)
        self._ack_counter = 0
        self._trim_interval = 100
        
        # Lock для сериализации ACK и claim: избегаем гонки между ack_and_delete и claim_outbox_batch
        self._ack_lock = asyncio.Lock()
    
    async def run(self, send_func: Callable[..., None]) -> None:
        """
        Основной цикл отправки outbox.
        
        Args:
            send_func: Функция для отправки envelope
        """
        self.log.info("🚀 WSOutboxFlusher V3 запущен")
        
        try:
            while True:
                now = time.time()
                
                self.log.debug(
                    f"[Flusher] Iteration: inflight={len(self.inflight_deadlines)}, "
                    f"max={self.max_inflight}"
                )
                
                # Освобождаем expired leases в БД
                released = await self.db_manager.release_expired_leases(now)
                if released > 0:
                    self.log.debug(f"[Flusher] Released {released} expired leases")
                
                # Проверяем таймауты inflight сообщений
                await self._check_timeouts(now)
                
                # Отправляем новые pending записи
                batch_sent = False
                if len(self.inflight_deadlines) < self.max_inflight:
                    batch_sent = await self._send_pending_batch(send_func)
                
                # Определяем время ожидания
                if not batch_sent and not self.inflight_deadlines:
                    sleep_time = 2.0
                else:
                    sleep_time = self._calculate_sleep_time()
                
                await asyncio.sleep(sleep_time)
                
        except asyncio.CancelledError:
            self.log.info("🛑 WSOutboxFlusher остановлен (cancelled)")
            raise
        except Exception as e:
            self.log.error(f"❌ Критическая ошибка в WSOutboxFlusher: {e}")
            self.log.exception(e)
            raise
    
    async def _check_timeouts(self, now: float) -> None:
        """
        Проверяет таймауты inflight сообщений.
        
        При таймауте:
        - Если attempts < resend_limit: lease истечет, будет retry
        - Если attempts >= resend_limit: помечаем как failed
        """
        timed_out_failed = []
        timed_out_retry = []
        
        for outbox_id, deadline in list(self.inflight_deadlines.items()):
            if now >= deadline:
                try:
                    item = await self.db_manager.get_outbox_item(outbox_id)
                except Exception as e:
                    self.log.error(f"❌ Ошибка чтения outbox item ID={outbox_id}: {e}")
                    del self.inflight_deadlines[outbox_id]
                    timed_out_failed.append(outbox_id)
                    continue
                
                if not item:
                    del self.inflight_deadlines[outbox_id]
                    continue
                
                if item.get('status') != 'inflight':
                    del self.inflight_deadlines[outbox_id]
                    continue
                
                attempts = item.get('attempts', 0)
                if attempts >= self.resend_limit:
                    self.log.error(
                        f"❌ Исчерпаны попытки для outbox_id={outbox_id} "
                        f"({attempts}/{self.resend_limit}), помечаю как failed"
                    )
                    timed_out_failed.append(outbox_id)
                    del self.inflight_deadlines[outbox_id]
                else:
                    self.log.warning(
                        f"⏱️  Таймаут ACK для outbox_id={outbox_id} "
                        f"({attempts}/{self.resend_limit}), будет повторно отправлено"
                    )
                    timed_out_retry.append(outbox_id)
                    del self.inflight_deadlines[outbox_id]
                    self.stats['resends'] += 1
        
        # Помечаем как failed
        if timed_out_failed:
            try:
                await self.db_manager.mark_outbox_failed(
                    timed_out_failed, 
                    reason="ack_timeout_exhausted"
                )
                self.stats['failed'] += len(timed_out_failed)
            except Exception as e:
                self.log.error(f"❌ Ошибка при пометке failed: {e}")
        
        # Для retry - lease уже истек в БД, они будут выбраны при следующем claim

    async def _handle_send_failure(self, outbox_id: int, attempts: int, error: Exception) -> None:
        try:
            if attempts >= self.resend_limit:
                await self.db_manager.mark_outbox_failed(
                    [outbox_id],
                    reason=f"send_error_exhausted({attempts}/{self.resend_limit}): {str(error)}"
                )
                self.stats['failed'] += 1
            else:
                backoff = calculate_backoff(attempts)
                new_lease = time.time() + backoff
                await self.db_manager.update_outbox_lease([outbox_id], new_lease)
                self.stats['resends'] += 1
                self.log.warning(
                    f"⚠️  send_error для outbox_id={outbox_id}, attempts={attempts}/{self.resend_limit}; "
                    f"будет retry через {backoff}s"
                )
        except Exception as e2:
            self.log.error(f"❌ Ошибка при пометке failed: {e2}")
    
    async def _send_pending_batch(
        self, 
        send_func: Callable
    ) -> bool:
        """
        Отправляет пакет pending записей из БД.
        
        Использует claim_outbox_batch для атомарного резервирования.
        Формирует event_batch согласно Protocol V3.
        """
        try:
            available_slots = self.max_inflight - len(self.inflight_deadlines)
            if available_slots <= 0:
                return False
            
            batch_size = min(20, available_slots)
            
            # Сериализуем с ACK: claim не должен пересекаться с ack_and_delete
            async with self._ack_lock:
                batch = await self.db_manager.claim_outbox_batch(
                    limit=batch_size,
                    lease_sec=int(self.ack_timeout_sec)
                )
            
            if not batch:
                return False
            
            self.log.info(f"📤 Отправляю пакет из {len(batch)} записей")
            prepared_messages = []

            for item in batch:
                outbox_id = item['id']
                
                if outbox_id in self.inflight_deadlines:
                    continue
                
                try:
                    # Определяем: ticket event или device event
                    # КРИТИЧНО: тип события определяется ТОЛЬКО через device_seq/agent_seq
                    # НЕ используем ticket_id == device_id как признак (это хрупкое допущение)
                    device_seq = item.get('device_seq')
                    agent_seq = item.get('agent_seq')
                    ticket_id = item.get('ticket_id')
                    
                    # Валидация: проверяем корректность seq полей
                    # Инвариант: device_event ⇔ device_seq IS NOT NULL AND agent_seq IS NULL
                    #            ticket_event ⇔ agent_seq IS NOT NULL AND device_seq IS NULL
                    if device_seq is not None and agent_seq is not None:
                        # Некорректная запись: оба seq присутствуют
                        self.log.error(
                            f"❌ Некорректная запись outbox_id={outbox_id}: "
                            f"оба device_seq и agent_seq присутствуют "
                            f"(device_seq={device_seq}, agent_seq={agent_seq})"
                        )
                        await self.db_manager.mark_outbox_failed(
                            [outbox_id],
                            reason="Invalid: both device_seq and agent_seq present"
                        )
                        self.stats['failed'] += 1
                        continue
                    
                    if device_seq is None and agent_seq is None:
                        # Некорректная запись: оба seq отсутствуют
                        # Это может быть старая запись до миграции
                        self.log.warning(
                            f"⚠️  Запись outbox_id={outbox_id} без seq полей "
                            f"(возможно, старая запись до миграции). Пропускаю."
                        )
                        await self.db_manager.mark_outbox_failed(
                            [outbox_id],
                            reason="Invalid: missing both device_seq and agent_seq (legacy record?)"
                        )
                        self.stats['failed'] += 1
                        continue
                    
                    # Определяем тип события
                    is_device_event = (device_seq is not None and agent_seq is None)

                    # Формируем event согласно Protocol V3. Device events may have a
                    # compatibility ticket_id in SQLite, but that context must not leak
                    # onto the wire because device_seq is the source of truth.
                    event = self._format_event(item, include_ticket_id=not is_device_event)
                    
                    # Формируем envelope payload
                    envelope_payload = {
                        "outbox_id": outbox_id,
                        "item_type": "job_event",
                        "event": event
                    }
                    
                    # Добавляем соответствующий seq (гарантированно не None)
                    if is_device_event:
                        # Device event: используем device_seq (НЕ agent_seq!)
                        envelope_payload["device_seq"] = device_seq
                    else:
                        # Ticket event: используем agent_seq (гарантированно не None)
                        if agent_seq is None:
                            # Защита от None (не должно произойти после проверки выше)
                            self.log.error(
                                f"❌ КРИТИЧНО: agent_seq is None для ticket event "
                                f"outbox_id={outbox_id}, ticket_id={ticket_id}"
                            )
                            await self.db_manager.mark_outbox_failed(
                                [outbox_id],
                                reason="Invalid: agent_seq is None for ticket event"
                            )
                            self.stats['failed'] += 1
                            continue
                        envelope_payload["agent_seq"] = agent_seq
                    
                    # Опциональные поля
                    if item.get('event_id'):
                        envelope_payload["event_id"] = item.get('event_id')
                    
                    request_id = str(uuid.uuid4())
                    trace_id = str(uuid.uuid4())
                    envelope = {
                        "type": "outbox_item",
                        "request_id": request_id,
                        "device_id": self.device_id,
                        "protocol_version": "ws_ticket_v3",
                        "payload": envelope_payload,
                        "meta": {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "actor_role": "agent",
                        },
                        "trace_id": trace_id,
                    }
                    wire_ticket_id = None if is_device_event else ticket_id
                    if wire_ticket_id:
                        envelope["ticket_id"] = wire_ticket_id
                    if item.get('job_id'):
                        envelope["job_id"] = item.get('job_id')

                    prepared_messages.append(
                        {
                            "outbox_id": outbox_id,
                            "request_id": request_id,
                            "trace_id": trace_id,
                            "payload": envelope_payload,
                            "ticket_id": wire_ticket_id,
                            "job_id": item.get('job_id'),
                            "attempts": int(item.get('attempts', 0) or 0),
                            "event_id": item.get('event_id'),
                            "envelope": envelope,
                        }
                    )
                    
                except Exception as e:
                    self.log.error(f"❌ Ошибка отправки outbox_id={outbox_id}: {e}")
                    attempts = int(item.get('attempts', 0) or 0)
                    await self._handle_send_failure(outbox_id, attempts, e)

            if not prepared_messages:
                return False

            if self.supports_outbox_batch and len(prepared_messages) > 1:
                try:
                    await send_func(
                        "outbox_items_batch",
                        str(uuid.uuid4()),
                        {"items": [msg["envelope"] for msg in prepared_messages]},
                        None,
                        None,
                    )
                    deadline = time.time() + self.ack_timeout_sec
                    for msg in prepared_messages:
                        self.inflight_deadlines[msg["outbox_id"]] = deadline
                        self.stats['sent'] += 1
                    self.log.debug(
                        f"📤 Отправлен outbox_items_batch: size={len(prepared_messages)}, "
                        f"outbox_ids={[msg['outbox_id'] for msg in prepared_messages]}"
                    )
                    return True
                except Exception as e:
                    self.log.error(f"❌ Ошибка отправки outbox_items_batch: {e}")
                    for msg in prepared_messages:
                        await self._handle_send_failure(msg["outbox_id"], msg["attempts"], e)
                    return False

            for msg in prepared_messages:
                try:
                    await send_func(
                        "outbox_item",
                        msg["request_id"],
                        msg["payload"],
                        msg["ticket_id"],
                        msg["job_id"],
                        trace_id=msg["trace_id"],
                    )

                    deadline = time.time() + self.ack_timeout_sec
                    self.inflight_deadlines[msg["outbox_id"]] = deadline
                    self.stats['sent'] += 1

                    self.log.debug(
                        f"📤 Отправлен outbox_item: outbox_id={msg['outbox_id']}, "
                        f"event_id={msg['event_id']}, attempts={msg['attempts']}"
                    )
                except Exception as e:
                    self.log.error(f"❌ Ошибка отправки outbox_id={msg['outbox_id']}: {e}")
                    await self._handle_send_failure(msg["outbox_id"], msg["attempts"], e)

            return True
            
        except Exception as e:
            self.log.error(f"❌ Ошибка при отправке пакета: {e}")
            self.log.exception(e)
            return False
    
    def _format_event(self, item: Dict[str, Any], *, include_ticket_id: bool = True) -> Dict[str, Any]:
        """
        Форматирует событие для Protocol V3 server.
        
        Args:
            item: Запись из outbox
            
        Returns:
            Словарь события с flat структурой (event вместо kind)
        """
        # Парсим payload из JSON если нужно
        payload = item.get('payload', {})
        if isinstance(payload, str):
            import json
            payload = json.loads(payload)
        
        # Тип события: только ключ "event", не '"event"' (нормализация для сервера)
        event_type = payload.get("event") or payload.get('"event"') or item.get('kind')
        
        # Protocol V3: event вместо kind, все поля в одном уровне; исключаем ключ '"event"'
        excluded_keys = {"event", '"event"'}
        if not include_ticket_id:
            excluded_keys.add("ticket_id")
        rest = {k: v for k, v in payload.items() if k not in excluded_keys}
        event = {"event": event_type, **rest}
        
        # Обеспечиваем наличие обязательных полей
        if include_ticket_id and 'ticket_id' not in event and item.get('ticket_id'):
            event['ticket_id'] = item.get('ticket_id')
        if 'job_id' not in event and item.get('job_id'):
            event['job_id'] = item.get('job_id')
        
        return event
    
    def _calculate_sleep_time(self) -> float:
        """Вычисляет время ожидания перед следующей итерацией."""
        if not self.inflight_deadlines:
            return 2.0
        elif len(self.inflight_deadlines) >= self.max_inflight:
            return 0.5
        else:
            return 1.0
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ACK/NACK HANDLERS (Фаза 3)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def handle_ack(self, outbox_ids: List[int]) -> None:
        """
        Обрабатывает получение ACK от сервера.
        
        V3: ACK → DELETE из outbox (без статуса 'sent').
        Сериализован с claim_outbox_batch через _ack_lock (избегаем гонки).
        
        Args:
            outbox_ids: Список ID записей, для которых получен ACK
        """
        if not outbox_ids:
            return
        
        # Фильтруем только те, которые есть в трекинге
        acked_inflight = [oid for oid in outbox_ids if oid in self.inflight_deadlines]
        
        if not acked_inflight:
            self.log.warning(
                f"⚠️  Получен ACK для {len(outbox_ids)} записей, "
                f"но ни одна не в трекинге"
            )
        
        self.log.info(f"✅ Получен ACK для {len(outbox_ids)} записей")
        
        async with self._ack_lock:
            await self._handle_ack_async(outbox_ids)
            # Удаляем из трекинга только после завершения ack_and_delete
            for outbox_id in outbox_ids:
                self.inflight_deadlines.pop(outbox_id, None)
        
        self.stats['acked'] += len(outbox_ids)
        self._ack_counter += len(outbox_ids)
        
        self.log.debug(
            f"📊 Статистика: sent={self.stats['sent']}, "
            f"acked={self.stats['acked']}, failed={self.stats['failed']}, "
            f"resends={self.stats['resends']}"
        )
    
    async def _handle_ack_async(self, outbox_ids: List[int]) -> None:
        """
        Асинхронно обрабатывает ACK: удаляет из outbox, сохраняет в историю.
        
        Замечание 3.1: Trimming батчами - только каждые N ACK.
        """
        try:
            # Определяем нужен ли trimming
            do_trim = self._ack_counter >= self._trim_interval
            if do_trim:
                self._ack_counter = 0
            
            await self.db_manager.ack_and_delete_outbox(
                outbox_ids,
                trim_history_threshold=1100 if do_trim else 999999,
                trim_history_target=1000
            )
            
        except Exception as e:
            self.log.error(f"❌ Ошибка при обработке ACK: {e}")
    
    async def handle_nack(
        self,
        outbox_ids: List[int],
        retryable: bool,
        retry_after_sec: Optional[int] = None,
        error: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Обрабатывает типизированный NACK от сервера (Фаза 3.2).
        
        Замечание 7: Exponential backoff при retryable=True без retry_after_sec.
        
        Args:
            outbox_ids: ID записей
            retryable: Можно ли повторить
            retry_after_sec: Через сколько повторить (если retryable)
            error: Детали ошибки {code, message}
        """
        if not outbox_ids:
            return
        
        # Удаляем из трекинга
        for oid in outbox_ids:
            self.inflight_deadlines.pop(oid, None)
        
        error_code = error.get('code', 'UNKNOWN') if error else 'UNKNOWN'
        error_message = error.get('message', '') if error else ''
        
        if not retryable:
            # Идемпотентность: не помечаем и не логируем ERROR повторно для уже failed
            ids_to_mark = []
            for oid in outbox_ids:
                if oid is None:
                    continue
                oid_int = int(oid)
                item = await self.db_manager.get_outbox_item(oid_int)
                if item and item.get("status") != "failed":
                    ids_to_mark.append(oid_int)
            if not ids_to_mark:
                self.log.debug(
                    f"NACK для outbox_ids={outbox_ids}: уже помечены failed, пропускаем"
                )
                return
            
            self.log.error(
                f"❌ Non-retryable NACK для {len(ids_to_mark)} items: "
                f"code={error_code}, message={error_message}"
            )
            try:
                await self.db_manager.mark_outbox_failed(
                    ids_to_mark,
                    reason=f"NACK: {error_code} - {error_message}"
                )
                self.stats['failed'] += len(ids_to_mark)
                self.stats['nack_non_retryable'] += len(ids_to_mark)
            except Exception as e:
                self.log.error(f"❌ Ошибка при пометке failed: {e}")
        
        else:
            # Retryable NACK - обновляем lease_until
            self.log.warning(
                f"⚠️  Retryable NACK для {len(outbox_ids)} items: "
                f"code={error_code}, retry_after={retry_after_sec}s"
            )
            
            try:
                # Если retry_after_sec указан, используем его
                # Иначе используем exponential backoff (замечание 7)
                if retry_after_sec:
                    new_lease = time.time() + retry_after_sec
                else:
                    # Получаем максимальное количество attempts для backoff
                    max_attempts = 0
                    for oid in outbox_ids:
                        item = await self.db_manager.get_outbox_item(oid)
                        if item:
                            max_attempts = max(max_attempts, item.get('attempts', 0))
                    
                    backoff = calculate_backoff(max_attempts)
                    new_lease = time.time() + backoff
                    self.log.debug(
                        f"Exponential backoff: attempts={max_attempts}, "
                        f"delay={backoff}s"
                    )
                
                await self.db_manager.update_outbox_lease(outbox_ids, new_lease)
                self.stats['resends'] += len(outbox_ids)
                self.stats['nack_retryable'] += len(outbox_ids)
                
            except Exception as e:
                self.log.error(f"❌ Ошибка при обновлении lease: {e}")
    
    def get_stats(self) -> Dict[str, int]:
        """Возвращает статистику работы flusher."""
        return {
            **self.stats,
            'inflight_count': len(self.inflight_deadlines)
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ТЕСТИРОВАНИЕ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def test_sender_v3():
    """Тест WSOutboxFlusher V3."""
    logger.info("=" * 60)
    logger.info("Тестирование WSOutboxFlusher V3")
    logger.info("=" * 60)
    
    # Тест backoff calculation
    logger.info("1. Тест exponential backoff...")
    assert calculate_backoff(0) == 1  # 1 * 2^0 = 1
    assert calculate_backoff(1) == 2  # 1 * 2^1 = 2
    assert calculate_backoff(2) == 4  # 1 * 2^2 = 4
    assert calculate_backoff(10) == 60  # Capped at BACKOFF_MAX
    logger.success("   ✅ Backoff calculation correct")
    
    logger.info("=" * 60)
    logger.success("Все тесты WSOutboxFlusher V3 пройдены!")
    logger.info("=" * 60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_sender_v3())
