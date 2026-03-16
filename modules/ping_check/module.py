"""
Module for network ping checking.

Проверяет доступность IP адресов через ping команду.
"""

import subprocess
import platform
from typing import Dict, Any
from loguru import logger
from pydantic import BaseModel

# Импорты без префикса pc_agent: в frozen-сборке агента пакета pc_agent нет в sys.path
try:
    from pc_agent.modules.base_module import BaseCollector
    from pc_agent.core.registry import exposed_tool
except ImportError:
    from modules.base_module import BaseCollector
    from core.registry import exposed_tool


class PingParams(BaseModel):
    """Параметры для ping команды."""
    host: str = "192.168.100.250"
    count: int = 4
    timeout: int = 5


class PingCheckCollector(BaseCollector):
    """
    Модуль для проверки сетевой доступности через ping.
    """
    
    @property
    def name(self) -> str:
        """Возвращает уникальное имя модуля."""
        return "ping_check"
    
    async def collect(self) -> Dict[str, Any]:
        """
        Дефолтный метод collect - пингует 192.168.100.250.
        """
        return await self.ping_host(host="192.168.100.250", count=4, timeout=5)
    
    @exposed_tool(
        name="ping_host",
        description="Ping a host to check network connectivity. Pings 192.168.100.250 by default.",
        risk_level="safe_readonly",
        params_model=PingParams,
        metadata_risk_level="safe_read",
        metadata_scopes=["network.read"],
        metadata_requires_consent=False
    )
    async def ping_host(self, host: str = "192.168.100.250", count: int = 4, timeout: int = 5) -> Dict[str, Any]:
        """
        Пингует указанный хост и возвращает результат.
        
        Args:
            host: IP адрес или hostname для пинга (по умолчанию 192.168.100.250)
            count: Количество пакетов для отправки (по умолчанию 4)
            timeout: Таймаут в секундах (по умолчанию 5)
        
        Returns:
            Dict[str, Any]: Результат пинга с информацией о доступности хоста
        
        Example:
            {
                "host": "192.168.100.250",
                "reachable": True,
                "packets_sent": 4,
                "packets_received": 4,
                "packet_loss": "0%",
                "avg_time_ms": 1.5,
                "message": "Host is reachable"
            }
        """
        logger.info(f"[{self.name}] Pinging host: {host} (count={count}, timeout={timeout}s)")
        
        # Определяем команду ping в зависимости от ОС
        system = platform.system().lower()
        
        if system == "windows":
            # Windows ping: ping -n <count> -w <timeout_ms> <host>
            cmd = ["ping", "-n", str(count), "-w", str(timeout * 1000), host]
        else:
            # Linux/Unix ping: ping -c <count> -W <timeout> <host>
            cmd = ["ping", "-c", str(count), "-W", str(timeout), host]
        
        try:
            # Выполняем ping команду
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout + 2  # Добавляем небольшой запас для timeout
            )
            
            output = result.stdout
            return_code = result.returncode
            
            # Парсим результат в зависимости от ОС
            if system == "windows":
                return self._parse_windows_ping(output, host, return_code)
            else:
                return self._parse_unix_ping(output, host, return_code)
                
        except subprocess.TimeoutExpired:
            logger.warning(f"[{self.name}] Ping timeout for {host}")
            return {
                "host": host,
                "reachable": False,
                "packets_sent": count,
                "packets_received": 0,
                "packet_loss": "100%",
                "avg_time_ms": None,
                "message": "Ping timeout - host is not reachable or timeout exceeded"
            }
        except FileNotFoundError:
            logger.error(f"[{self.name}] Ping command not found")
            return {
                "host": host,
                "reachable": False,
                "error": "ping_command_not_found",
                "message": "Ping command is not available on this system"
            }
        except Exception as e:
            logger.error(f"[{self.name}] Error pinging {host}: {e}")
            return {
                "host": host,
                "reachable": False,
                "error": str(e),
                "message": f"Error occurred: {str(e)}"
            }
    
    def _parse_windows_ping(self, output: str, host: str, return_code: int) -> Dict[str, Any]:
        """Парсит результат ping для Windows."""
        # Windows ping возвращает 0 если успешно, иначе не 0
        reachable = return_code == 0
        
        # Пытаемся извлечь информацию о пакетах
        packets_sent = 0
        packets_received = 0
        packet_loss = "100%"
        avg_time_ms = None
        
        try:
            lines = output.split('\n')
            for line in lines:
                if "Packets:" in line or "Sent =" in line:
                    # Пример: "Packets: Sent = 4, Received = 4, Lost = 0 (0% loss)"
                    parts = line.split(',')
                    for part in parts:
                        if "Sent" in part:
                            packets_sent = int(''.join(filter(str.isdigit, part.split('=')[1])))
                        elif "Received" in part:
                            packets_received = int(''.join(filter(str.isdigit, part.split('=')[1])))
                        elif "Lost" in part and "%" in part:
                            packet_loss = part.split('(')[1].split(')')[0].strip()
                
                if "Average" in line and "ms" in line:
                    # Пример: "Average = 1ms"
                    avg_str = line.split('=')[1].strip()
                    avg_time_ms = float(''.join(filter(lambda c: c.isdigit() or c == '.', avg_str)))
        except Exception as e:
            logger.debug(f"Error parsing Windows ping output: {e}")
        
        message = "Host is reachable" if reachable else "Host is not reachable"
        
        return {
            "host": host,
            "reachable": reachable,
            "packets_sent": packets_sent if packets_sent > 0 else 4,
            "packets_received": packets_received,
            "packet_loss": packet_loss if packets_received > 0 else "100%",
            "avg_time_ms": avg_time_ms,
            "message": message
        }
    
    def _parse_unix_ping(self, output: str, host: str, return_code: int) -> Dict[str, Any]:
        """Парсит результат ping для Linux/Unix."""
        # Unix ping возвращает 0 если успешно, иначе не 0
        reachable = return_code == 0
        
        packets_sent = 0
        packets_received = 0
        packet_loss = "100%"
        avg_time_ms = None
        
        try:
            lines = output.split('\n')
            for line in lines:
                # Пример: "4 packets transmitted, 4 received, 0% packet loss, time 3003ms"
                if "packets transmitted" in line:
                    parts = line.split(',')
                    for part in parts:
                        if "transmitted" in part:
                            packets_sent = int(''.join(filter(str.isdigit, part.split()[0])))
                        elif "received" in part:
                            packets_received = int(''.join(filter(str.isdigit, part.split()[0])))
                        elif "% packet loss" in part:
                            packet_loss = part.split()[0]
                
                # Пример: "rtt min/avg/max/mdev = 1.234/1.567/2.345/0.456 ms"
                if "rtt min/avg/max/mdev" in line or "round-trip min/avg/max" in line:
                    # Извлекаем avg время
                    time_part = line.split('=')[1].strip().split('/')
                    if len(time_part) >= 2:
                        avg_time_ms = float(time_part[1])
        except Exception as e:
            logger.debug(f"Error parsing Unix ping output: {e}")
        
        # Если не удалось распарсить, используем return_code
        if packets_sent == 0:
            packets_sent = 4
            if reachable:
                packets_received = 4
                packet_loss = "0%"
            else:
                packets_received = 0
                packet_loss = "100%"
        
        message = "Host is reachable" if reachable else "Host is not reachable"
        
        return {
            "host": host,
            "reachable": reachable,
            "packets_sent": packets_sent,
            "packets_received": packets_received,
            "packet_loss": packet_loss,
            "avg_time_ms": avg_time_ms,
            "message": message
        }

