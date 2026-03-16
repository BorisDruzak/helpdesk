"""
Module for operating system detection and information.

Проверяет операционную систему (Windows, Linux, Mac) и собирает информацию о системе.
"""

import platform
import sys
from typing import Dict, Any
from loguru import logger

# Импорты без префикса pc_agent: загрузчик агента добавляет корень агента в sys.path,
# в frozen-сборке пакета pc_agent нет — работают только core.* и modules.*
try:
    from pc_agent.modules.base_module import BaseCollector
    from pc_agent.core.registry import exposed_tool
except ImportError:
    from modules.base_module import BaseCollector
    from core.registry import exposed_tool


class OSCheckCollector(BaseCollector):
    """
    Модуль для проверки операционной системы и сбора информации о системе.
    """
    
    @property
    def name(self) -> str:
        """Возвращает уникальное имя модуля."""
        return "os_check"
    
    async def collect(self) -> Dict[str, Any]:
        """
        Дефолтный метод collect - собирает информацию об ОС.
        """
        return await self.get_os_info()
    
    @exposed_tool(
        name="get_os_info",
        description="Get operating system information (Windows, Linux, or Mac)",
        risk_level="safe_readonly",
        metadata_risk_level="safe_read",
        metadata_scopes=["system.read"],
        metadata_requires_consent=False
    )
    async def get_os_info(self) -> Dict[str, Any]:
        """
        Собирает информацию об операционной системе.
        
        Returns:
            Dict[str, Any]: Информация об ОС включая тип, версию, архитектуру и детали
        
        Example:
            {
                "os_type": "Linux",
                "os_name": "Linux",
                "os_version": "6.12.27-6.12-alt1",
                "os_release": "6.12.27",
                "architecture": "x86_64",
                "machine": "x86_64",
                "processor": "x86_64",
                "platform": "Linux-6.12.27-6.12-alt1-x86_64-with-glibc2.38",
                "python_version": "3.11.5",
                "python_implementation": "CPython"
            }
        """
        logger.info(f"[{self.name}] Collecting OS information")
        
        try:
            # Определяем тип ОС
            system = platform.system()
            os_type = self._normalize_os_type(system)
            
            # Собираем базовую информацию
            os_name = system
            os_version = platform.version()
            os_release = platform.release()
            architecture = platform.machine()
            processor = platform.processor()
            
            # Для Linux получаем более детальную информацию
            if os_type == "Linux":
                dist_info = self._get_linux_distribution()
            elif os_type == "Windows":
                dist_info = self._get_windows_info()
            elif os_type == "Mac":
                dist_info = self._get_mac_info()
            else:
                dist_info = {}
            
            # Информация о Python
            python_version = sys.version.split()[0]
            python_implementation = platform.python_implementation()
            
            result = {
                "os_type": os_type,
                "os_name": os_name,
                "os_version": os_version,
                "os_release": os_release,
                "architecture": architecture,
                "machine": platform.machine(),
                "processor": processor if processor else "unknown",
                "platform": platform.platform(),
                "python_version": python_version,
                "python_implementation": python_implementation,
                **dist_info
            }
            
            logger.info(f"[{self.name}] OS detected: {os_type} ({os_name} {os_release})")
            return result
            
        except Exception as e:
            logger.error(f"[{self.name}] Error collecting OS info: {e}")
            return {
                "os_type": "unknown",
                "error": str(e),
                "message": f"Error occurred while collecting OS information: {str(e)}"
            }
    
    def _normalize_os_type(self, system: str) -> str:
        """
        Нормализует тип ОС к стандартным значениям.
        
        Args:
            system: Результат platform.system()
            
        Returns:
            str: "Windows", "Linux", "Mac" или "Unknown"
        """
        system_lower = system.lower()
        if system_lower == "windows":
            return "Windows"
        elif system_lower == "linux":
            return "Linux"
        elif system_lower in ("darwin", "macos"):
            return "Mac"
        else:
            return "Unknown"
    
    def _get_linux_distribution(self) -> Dict[str, Any]:
        """
        Получает информацию о дистрибутиве Linux.
        
        Returns:
            Dict[str, Any]: Информация о дистрибутиве
        """
        try:
            # Пытаемся использовать platform.dist() (устаревший, но работает)
            # или читаем /etc/os-release
            dist_info = {}
            
            # Читаем /etc/os-release если доступен
            try:
                with open('/etc/os-release', 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if '=' in line and not line.startswith('#'):
                            key, value = line.split('=', 1)
                            key = key.strip()
                            value = value.strip().strip('"').strip("'")
                            if key == 'NAME':
                                dist_info['distribution'] = value
                            elif key == 'VERSION':
                                dist_info['distribution_version'] = value
                            elif key == 'ID':
                                dist_info['distribution_id'] = value
                            elif key == 'PRETTY_NAME':
                                dist_info['distribution_pretty_name'] = value
            except (FileNotFoundError, PermissionError, IOError):
                # Если /etc/os-release недоступен, используем platform
                try:
                    # platform.dist() устарел, но может работать на старых системах
                    dist_name, dist_version, dist_id = platform.dist()
                    if dist_name:
                        dist_info['distribution'] = dist_name
                    if dist_version:
                        dist_info['distribution_version'] = dist_version
                    if dist_id:
                        dist_info['distribution_id'] = dist_id
                except AttributeError:
                    # platform.dist() не доступен в Python 3.8+
                    pass
            
            return dist_info
            
        except Exception as e:
            logger.debug(f"Error getting Linux distribution info: {e}")
            return {}
    
    def _get_windows_info(self) -> Dict[str, Any]:
        """
        Получает дополнительную информацию о Windows.
        
        Returns:
            Dict[str, Any]: Информация о Windows
        """
        try:
            win_info = {}
            
            # Пытаемся получить версию Windows через platform.win32_ver()
            try:
                win_version = platform.win32_ver()
                if win_version:
                    win_info['windows_version'] = win_version[0] if win_version[0] else "unknown"
                    win_info['windows_build'] = win_version[1] if len(win_version) > 1 and win_version[1] else "unknown"
                    win_info['windows_edition'] = win_version[2] if len(win_version) > 2 and win_version[2] else "unknown"
            except Exception:
                pass
            
            # Пытаемся определить версию Windows по release
            release = platform.release()
            if release:
                win_info['windows_release'] = release
            
            return win_info
            
        except Exception as e:
            logger.debug(f"Error getting Windows info: {e}")
            return {}
    
    def _get_mac_info(self) -> Dict[str, Any]:
        """
        Получает дополнительную информацию о macOS.
        
        Returns:
            Dict[str, Any]: Информация о macOS
        """
        try:
            mac_info = {}
            
            # Пытаемся получить версию macOS через platform.mac_ver()
            try:
                mac_version = platform.mac_ver()
                if mac_version and mac_version[0]:
                    mac_info['macos_version'] = mac_version[0]
                if mac_version and len(mac_version) > 1 and mac_version[1]:
                    mac_info['macos_version_info'] = mac_version[1]
            except Exception:
                pass
            
            return mac_info
            
        except Exception as e:
            logger.debug(f"Error getting Mac info: {e}")
            return {}

