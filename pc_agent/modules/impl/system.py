"""
Модуль для сбора системной информации.

Собирает данные о загрузке процессора, использовании памяти,
состоянии дисков и сетевой активности.
"""

import socket
from typing import Dict, Any
import psutil
from loguru import logger
from pydantic import BaseModel

from modules.base_module import BaseCollector
from core.registry import exposed_tool


class SystemCollectParams(BaseModel):
    """Параметры для сбора системной информации."""
    include_ip: bool = True
    include_hostname: bool = True


class SystemCollector(BaseCollector):
    """
    Коллектор системной информации (CPU, RAM, диски, сеть).
    """
    
    @property
    def name(self) -> str:
        """Возвращает уникальное имя модуля."""
        return "system"
    
    @exposed_tool(
        name="collect",
        description="Collect basic system metrics",
        risk_level="safe_readonly",
        params_model=SystemCollectParams,
        presets=[
            {
                "id": "basic",
                "name": "Базовые метрики",
                "description": "Сбор основных метрик (CPU, RAM, Disk) без IP-адреса",
                "params": {"include_ip": False, "include_hostname": True}
            },
            {
                "id": "full",
                "name": "Полная информация",
                "description": "Сбор всех доступных метрик включая IP-адрес",
                "params": {"include_ip": True, "include_hostname": True}
            },
            {
                "id": "minimal",
                "name": "Минимальная информация",
                "description": "Только CPU, RAM и Disk без сетевой информации",
                "params": {"include_ip": False, "include_hostname": False}
            }
        ],
        metadata_risk_level="safe_read",
        metadata_scopes=[],
        metadata_requires_consent=False
    )
    async def collect(self, include_ip: bool = True, include_hostname: bool = True) -> Dict[str, Any]:
        """
        Асинхронный сбор системной информации.
        
        Args:
            include_ip: Включать ли IP-адрес в результат (по умолчанию True)
            include_hostname: Включать ли hostname в результат (по умолчанию True)
        
        Returns:
            Dict[str, Any]: Словарь с системными метриками (observations)
        
        Raises:
            Exception: В случае ошибок сбора данных
        """
        logger.debug(f"[{self.name}] Начинаю сбор системной информации (include_ip={include_ip}, include_hostname={include_hostname})")
        
        cpu = psutil.cpu_percent(interval=1)
        
        memory = psutil.virtual_memory()
        ram = memory.percent
        
        disk = psutil.disk_usage('/')
        disk_percent = disk.percent
        
        result = {
            "cpu": cpu,
            "ram": ram,
            "disk": disk_percent
        }
        
        if include_hostname:
            hostname = socket.gethostname()
            result["hostname"] = hostname
            
            if include_ip:
                try:
                    ip = socket.gethostbyname(hostname)
                    result["ip"] = ip
                except Exception:
                    result["ip"] = "unknown"
        elif include_ip:
            # Если нужен только IP, но не hostname, получаем hostname только для IP
            hostname = socket.gethostname()
            try:
                ip = socket.gethostbyname(hostname)
                result["ip"] = ip
            except Exception:
                result["ip"] = "unknown"
        
        return result

