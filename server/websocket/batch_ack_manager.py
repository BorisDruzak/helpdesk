"""
Batch ACK Manager для накопления и отправки ACK/NACK в одном batch.

Phase B: Batch ACK System
Накапливает успешные и неуспешные outbox_ids для отправки в одном сообщении.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class NackInfo:
    """Информация о NACK для outbox_id."""
    retryable: bool
    error_code: str
    error_message: str
    retry_after_sec: Optional[int] = None


class BatchAckManager:
    """
    Менеджер для накопления ACK/NACK и их batch-отправки.
    
    Накапливает подтверждения за один "tick" обработки (синхронный batch),
    не использует задержки по времени.
    
    Usage:
        manager = BatchAckManager()
        
        # Накапливаем ACK/NACK
        manager.add_ack(device_id, outbox_id, trace_id)
        manager.add_nack(device_id, outbox_id, trace_id, nack_info)
        
        # Отправляем накопленные
        await manager.flush(ws, device_id)
    """
    
    def __init__(self):
        """Инициализация пустого менеджера."""
        # Структура: {device_id: {trace_id: [outbox_ids]}}
        self._acks: Dict[str, Dict[str, List[str]]] = {}
        
        # Структура: {device_id: {trace_id: {outbox_id: NackInfo}}}
        self._nacks: Dict[str, Dict[str, Dict[str, NackInfo]]] = {}
    
    def add_ack(self, device_id: str, outbox_id: str, trace_id: str) -> None:
        """
        Добавляет outbox_id в список успешных ACK.
        
        Args:
            device_id: ID устройства
            outbox_id: ID элемента outbox для подтверждения
            trace_id: Trace ID из входящего envelope
        """
        if device_id not in self._acks:
            self._acks[device_id] = {}
        
        if trace_id not in self._acks[device_id]:
            self._acks[device_id][trace_id] = []
        
        self._acks[device_id][trace_id].append(outbox_id)
        
        logger.debug(
            f"[BatchAck] Added ACK: device_id={device_id} "
            f"outbox_id={outbox_id} trace_id={trace_id}"
        )
    
    def add_nack(
        self,
        device_id: str,
        outbox_id: str,
        trace_id: str,
        nack_info: NackInfo
    ) -> None:
        """
        Добавляет outbox_id в список NACK.
        
        Args:
            device_id: ID устройства
            outbox_id: ID элемента outbox для отклонения
            trace_id: Trace ID из входящего envelope
            nack_info: Информация об ошибке
        """
        if device_id not in self._nacks:
            self._nacks[device_id] = {}
        
        if trace_id not in self._nacks[device_id]:
            self._nacks[device_id][trace_id] = {}
        
        self._nacks[device_id][trace_id][outbox_id] = nack_info
        
        logger.debug(
            f"[BatchAck] Added NACK: device_id={device_id} "
            f"outbox_id={outbox_id} trace_id={trace_id} "
            f"code={nack_info.error_code}"
        )
    
    async def flush(self, ws, device_id: str) -> None:
        """
        Отправляет накопленные ACK/NACK для указанного device_id.
        
        Группирует по trace_id для корректной корреляции.
        После отправки очищает накопленные данные для этого устройства.
        
        Args:
            ws: WebSocket connection
            device_id: ID устройства для flush
        """
        # Импортируем функции здесь, чтобы избежать циклических импортов
        from websocket.protocol import send_outbox_ack, send_outbox_nack
        
        # Flush ACKs
        if device_id in self._acks:
            for trace_id, outbox_ids in self._acks[device_id].items():
                if outbox_ids:
                    await send_outbox_ack(
                        ws=ws,
                        outbox_ids=outbox_ids,
                        agent_device_id=device_id,
                        trace_id=trace_id
                    )
                    logger.info(
                        f"[BatchAck] Flushed {len(outbox_ids)} ACKs "
                        f"for device_id={device_id} trace_id={trace_id}"
                    )
            
            # Очищаем ACKs для этого device
            del self._acks[device_id]
        
        # Flush NACKs
        if device_id in self._nacks:
            for trace_id, nacks in self._nacks[device_id].items():
                if nacks:
                    # Группируем NACK по типу ошибки для batch отправки
                    # (одинаковые error_code + retryable могут быть в одном NACK)
                    grouped_nacks = self._group_nacks_by_error(nacks)
                    
                    for (error_code, retryable, retry_after), outbox_ids in grouped_nacks.items():
                        error_message = nacks[outbox_ids[0]].error_message
                        
                        await send_outbox_nack(
                            ws=ws,
                            outbox_ids=list(outbox_ids),
                            agent_device_id=device_id,
                            retryable=retryable,
                            error_code=error_code,
                            error_message=error_message,
                            trace_id=trace_id,
                            retry_after_sec=retry_after
                        )
                        logger.info(
                            f"[BatchAck] Flushed {len(outbox_ids)} NACKs "
                            f"for device_id={device_id} trace_id={trace_id} "
                            f"code={error_code}"
                        )
            
            # Очищаем NACKs для этого device
            del self._nacks[device_id]
    
    def _group_nacks_by_error(
        self, 
        nacks: Dict[str, NackInfo]
    ) -> Dict[tuple, List[str]]:
        """
        Группирует NACK по типу ошибки для batch отправки.
        
        Args:
            nacks: Словарь {outbox_id: NackInfo}
        
        Returns:
            Dict с ключами (error_code, retryable, retry_after) и значениями [outbox_ids]
        """
        grouped: Dict[tuple, List[str]] = {}
        
        for outbox_id, nack_info in nacks.items():
            key = (
                nack_info.error_code,
                nack_info.retryable,
                nack_info.retry_after_sec
            )
            
            if key not in grouped:
                grouped[key] = []
            
            grouped[key].append(outbox_id)
        
        return grouped
    
    def has_pending(self, device_id: str) -> bool:
        """
        Проверяет, есть ли накопленные ACK/NACK для устройства.
        
        Args:
            device_id: ID устройства
        
        Returns:
            True если есть pending ACK или NACK
        """
        has_acks = device_id in self._acks and bool(self._acks[device_id])
        has_nacks = device_id in self._nacks and bool(self._nacks[device_id])
        return has_acks or has_nacks
    
    def clear_device(self, device_id: str) -> None:
        """
        Очищает все накопленные ACK/NACK для устройства без отправки.
        
        Используется при disconnect агента.
        
        Args:
            device_id: ID устройства
        """
        if device_id in self._acks:
            del self._acks[device_id]
        
        if device_id in self._nacks:
            del self._nacks[device_id]
        
        logger.debug(f"[BatchAck] Cleared all pending for device_id={device_id}")
