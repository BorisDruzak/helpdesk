"""
Атомарный модуль: получение IP-адреса машины.
Только стандартная библиотека (socket), без внешних зависимостей.
"""

import socket
from typing import Dict, Any

from modules.base_module import BaseCollector
from core.registry import exposed_tool


def _get_primary_ip() -> str:
    """Возвращает основной исходящий IP (подключение к внешнему адресу только для определения интерфейса)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1.0)
        try:
            # Не отправляем данные — только определяем исходящий интерфейс
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        except (OSError, socket.error):
            try:
                ip = socket.gethostbyname(socket.gethostname() or "localhost")
            except Exception:
                ip = "127.0.0.1"
        finally:
            s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class IpAddressCollector(BaseCollector):
    @property
    def name(self) -> str:
        return "ip_address"

    async def collect(self) -> Dict[str, Any]:
        return {"ip": _get_primary_ip()}

    @exposed_tool(
        name="get_ip",
        description="Получить IP-адрес машины",
        risk_level="safe_readonly",
        metadata_risk_level="safe_read",
        metadata_scopes=["network"],
        metadata_requires_consent=False,
        metadata_allow_roles=["user", "agent", "llm", "support", "admin"],
    )
    async def get_ip(self) -> Dict[str, Any]:
        """Возвращает основной IP-адрес текущей машины."""
        with self.trace_span("tool.entry", details={"tool_name": "ip_address.get_ip"}):
            ip = _get_primary_ip()
            return {"ip": ip, "ok": True}


def register():
    """Entrypoint для загрузки из modules_store (manifest entrypoint: module:register)."""
    return IpAddressCollector()
