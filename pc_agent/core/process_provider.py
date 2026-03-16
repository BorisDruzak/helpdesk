"""
ProcessProvider - Ультимативный сервис ядра для работы с процессами и окнами
===============================================================================

Этот модуль предоставляет единый API для работы с процессами и окнами в системе,
инкапсулируя работу с WinAPI (Windows) и X11 (Linux) через простой интерфейс.

ИСПОЛЬЗОВАНИЕ В ДИНАМИЧЕСКИХ СКРИПТАХ:
--------------------------------------
```python
from pc_agent.core.process_provider import ProcessProvider

# Получить экземпляр провайдера (синглтон)
provider = ProcessProvider.get_instance()

# Получить активное окно
active_win = provider.get_active_window()
print(f"Active: {active_win['title']} - {active_win['process_name']}")

# Список топ процессов по CPU
top_cpu = provider.get_process_list(top_n=5, sort_by='cpu')
for proc in top_cpu:
    print(f"{proc['name']}: {proc['cpu_percent']}% CPU")

# Системная нагрузка
load = provider.get_system_load()
print(f"CPU: {load['cpu_percent']}%, RAM: {load['memory_percent']}%")
```

Автор: PC Agent System Architecture
Лицензия: Internal Use Only
"""

import os
import sys
import time
import platform
import subprocess
import re
from typing import Dict, List, Optional, Tuple, Any
from threading import Lock
from dataclasses import dataclass, field
from datetime import datetime, timedelta

try:
    import psutil
except ImportError:
    raise ImportError("psutil is required. Install it: pip install psutil")

# Windows-специфичные импорты
if platform.system() == "Windows":
    try:
        import ctypes
        from ctypes import wintypes
        WINDOWS_AVAILABLE = True
    except ImportError:
        WINDOWS_AVAILABLE = False
else:
    WINDOWS_AVAILABLE = False


@dataclass
class ProcessInfo:
    """Структура данных о процессе"""
    pid: int
    name: str
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    status: str = "running"
    path: str = "Unknown"
    username: str = "Unknown"


@dataclass
class WindowInfo:
    """Структура данных об окне"""
    title: str = "Unknown"
    process_name: str = "Unknown"
    pid: int = 0
    path: str = "Unknown"
    hwnd: Optional[int] = None  # Windows HWND или X11 window ID


@dataclass
class SystemLoad:
    """Структура системной нагрузки"""
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_total_mb: float
    disk_usage_percent: float = 0.0


class ProcessProviderCache:
    """Кэш для хранения данных о процессах"""
    
    def __init__(self, ttl_ms: int = 500):
        self.ttl_ms = ttl_ms
        self.process_list: List[ProcessInfo] = []
        self.last_update: Optional[datetime] = None
        self.lock = Lock()
    
    def is_valid(self) -> bool:
        """Проверяет, актуален ли кэш"""
        if self.last_update is None:
            return False
        elapsed = (datetime.now() - self.last_update).total_seconds() * 1000
        return elapsed < self.ttl_ms
    
    def update(self, data: List[ProcessInfo]) -> None:
        """Обновляет кэш"""
        with self.lock:
            self.process_list = data
            self.last_update = datetime.now()
    
    def get(self) -> Optional[List[ProcessInfo]]:
        """Получает данные из кэша, если они актуальны"""
        with self.lock:
            if self.is_valid():
                return self.process_list
            return None


class ProcessProvider:
    """
    Синглтон-класс для работы с процессами и окнами в системе.
    
    Предоставляет кроссплатформенный API для:
    - Получения информации об активном окне
    - Мониторинга процессов
    - Управления процессами
    - Сбора системной статистики
    
    Все методы безопасны и не выбрасывают исключения наружу.
    """
    
    _instance: Optional['ProcessProvider'] = None
    _lock: Lock = Lock()
    
    def __init__(self):
        """Приватный конструктор. Используйте get_instance()"""
        if ProcessProvider._instance is not None:
            raise RuntimeError("Use get_instance() to get ProcessProvider instance")
        
        self.os_type = platform.system()
        self.cache = ProcessProviderCache(ttl_ms=500)
        self.agent_process_name = self._detect_agent_name()
        
        # Windows-специфичная инициализация
        if self.os_type == "Windows" and WINDOWS_AVAILABLE:
            self._init_windows_api()
    
    @classmethod
    def get_instance(cls) -> 'ProcessProvider':
        """
        Получить экземпляр ProcessProvider (синглтон).
        
        Returns:
            ProcessProvider: Единственный экземпляр класса
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    def _detect_agent_name(self) -> str:
        """Определяет имя процесса агента"""
        try:
            current_process = psutil.Process()
            return current_process.name()
        except Exception:
            return "python"
    
    def _init_windows_api(self) -> None:
        """Инициализация Windows API функций"""
        if not WINDOWS_AVAILABLE:
            return
        
        try:
            # Определение необходимых WinAPI функций
            self.user32 = ctypes.windll.user32
            self.kernel32 = ctypes.windll.kernel32
            
            # Настройка типов для функций
            self.user32.GetForegroundWindow.restype = wintypes.HWND
            self.user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
            self.user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
            self.user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        except Exception as e:
            self.user32 = None
            self.kernel32 = None
    
    # ============================================================================
    # ПУБЛИЧНЫЙ API - РАБОТА С ОКНАМИ
    # ============================================================================
    
    def get_active_window(self) -> Dict[str, Any]:
        """
        Получить информацию об активном (фокусном) окне системы.
        
        Автоматически определяет активное окно в зависимости от ОС (Windows/Linux).
        Если активное окно принадлежит агенту PC Agent, автоматически ищет 
        первое окно под ним в Z-порядке, которое не является агентом.
        
        Кроссплатформенная реализация:
        - Windows: Использует WinAPI (GetForegroundWindow)
        - Linux: Использует xdotool/xprop для работы с X11
        
        Returns:
            dict: Словарь с информацией об активном окне:
                {
                    'title': str,           # Заголовок окна
                    'process_name': str,    # Имя процесса (например, "chrome.exe")
                    'pid': int,             # ID процесса
                    'path': str,            # Полный путь к исполняемому файлу
                    'hwnd': int|None,       # Handle окна (Windows) или Window ID (Linux)
                    'error': str|None       # Сообщение об ошибке, если есть
                }
        
        Example:
            >>> provider = ProcessProvider.get_instance()
            >>> active = provider.get_active_window()
            >>> print(f"Active: {active['title']} - {active['process_name']}")
            Active: Google Chrome - chrome.exe
        
        Note:
            Метод безопасен и не выбрасывает исключения. В случае ошибки
            возвращает словарь с полем 'error' и значениями по умолчанию.
        """
        if self.os_type == "Windows":
            return self._get_active_window_windows()
        elif self.os_type == "Linux":
            return self._get_active_window_linux()
        else:
            return self._create_error_window("Unsupported OS")
    
    def _get_active_window_windows(self) -> Dict[str, Any]:
        """Получить активное окно на Windows"""
        if not WINDOWS_AVAILABLE or self.user32 is None:
            return self._create_error_window("Windows API not available")
        
        try:
            hwnd = self.user32.GetForegroundWindow()
            if not hwnd:
                return self._create_error_window("No foreground window")
            
            # Получаем информацию об окне
            window_info = self._get_window_info_by_hwnd(hwnd)
            
            # Проверяем, является ли это окном агента
            if window_info['process_name'].lower() == self.agent_process_name.lower():
                # Пытаемся найти окно под агентом
                next_window = self._find_next_window_windows(hwnd)
                if next_window:
                    return next_window
            
            return window_info
            
        except Exception as e:
            return self._create_error_window(f"Windows error: {str(e)}")
    
    def _get_window_info_by_hwnd(self, hwnd: int) -> Dict[str, Any]:
        """Получить информацию об окне по HWND"""
        try:
            # Получаем заголовок окна
            length = self.user32.GetWindowTextLengthW(hwnd)
            buff = ctypes.create_unicode_buffer(length + 1)
            self.user32.GetWindowTextW(hwnd, buff, length + 1)
            title = buff.value
            
            # Получаем PID процесса
            pid = wintypes.DWORD()
            self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            pid = pid.value
            
            # Получаем информацию о процессе
            process_name = "Unknown"
            path = "Unknown"
            
            try:
                proc = psutil.Process(pid)
                process_name = proc.name()
                path = proc.exe()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            
            return {
                'title': title or "Unknown",
                'process_name': process_name,
                'pid': pid,
                'path': path,
                'hwnd': hwnd,
                'error': None
            }
        except Exception as e:
            return self._create_error_window(f"HWND error: {str(e)}")
    
    def _find_next_window_windows(self, current_hwnd: int) -> Optional[Dict[str, Any]]:
        """Найти следующее окно в Z-порядке на Windows"""
        try:
            next_hwnd = self.user32.GetWindow(current_hwnd, 2)  # GW_HWNDNEXT = 2
            
            while next_hwnd:
                if self.user32.IsWindowVisible(next_hwnd):
                    window_info = self._get_window_info_by_hwnd(next_hwnd)
                    if window_info['process_name'].lower() != self.agent_process_name.lower():
                        return window_info
                
                next_hwnd = self.user32.GetWindow(next_hwnd, 2)
            
            return None
        except Exception:
            return None
    
    def _get_active_window_linux(self) -> Dict[str, Any]:
        """Получить активное окно на Linux (через xprop и xdotool)"""
        try:
            # Получаем ID активного окна
            result = subprocess.run(
                ['xdotool', 'getactivewindow'],
                capture_output=True,
                text=True,
                timeout=1
            )
            
            if result.returncode != 0:
                return self._create_error_window("Cannot get active window")
            
            window_id = result.stdout.strip()
            
            # Получаем информацию об окне
            window_info = self._get_window_info_by_id_linux(window_id)
            
            # Проверяем, является ли это окном агента
            if window_info['process_name'].lower() == self.agent_process_name.lower():
                # Пытаемся найти окно под агентом
                next_window = self._find_next_window_linux(window_id)
                if next_window:
                    return next_window
            
            return window_info
            
        except FileNotFoundError:
            # xdotool не установлен, пробуем альтернативный метод
            return self._get_active_window_linux_fallback()
        except Exception as e:
            return self._create_error_window(f"Linux error: {str(e)}")
    
    def _get_window_info_by_id_linux(self, window_id: str) -> Dict[str, Any]:
        """Получить информацию об окне по ID на Linux"""
        try:
            # Получаем заголовок окна
            title_result = subprocess.run(
                ['xdotool', 'getwindowname', window_id],
                capture_output=True,
                text=True,
                timeout=1
            )
            title = title_result.stdout.strip() if title_result.returncode == 0 else "Unknown"
            
            # Получаем PID процесса
            pid_result = subprocess.run(
                ['xdotool', 'getwindowpid', window_id],
                capture_output=True,
                text=True,
                timeout=1
            )
            
            pid = 0
            process_name = "Unknown"
            path = "Unknown"
            
            if pid_result.returncode == 0:
                try:
                    pid = int(pid_result.stdout.strip())
                    proc = psutil.Process(pid)
                    process_name = proc.name()
                    path = proc.exe()
                except (ValueError, psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            return {
                'title': title,
                'process_name': process_name,
                'pid': pid,
                'path': path,
                'hwnd': int(window_id) if window_id.isdigit() else None,
                'error': None
            }
        except Exception as e:
            return self._create_error_window(f"Window ID error: {str(e)}")
    
    def _find_next_window_linux(self, current_window_id: str) -> Optional[Dict[str, Any]]:
        """Найти следующее окно в стеке на Linux"""
        try:
            # Получаем список всех окон в Z-порядке
            result = subprocess.run(
                ['xdotool', 'search', '--onlyvisible', '--name', '.*'],
                capture_output=True,
                text=True,
                timeout=2
            )
            
            if result.returncode != 0:
                return None
            
            window_ids = result.stdout.strip().split('\n')
            
            # Находим текущее окно и берем следующее
            found_current = False
            for wid in window_ids:
                if found_current:
                    window_info = self._get_window_info_by_id_linux(wid)
                    if window_info['process_name'].lower() != self.agent_process_name.lower():
                        return window_info
                elif wid == current_window_id:
                    found_current = True
            
            return None
        except Exception:
            return None
    
    def _get_active_window_linux_fallback(self) -> Dict[str, Any]:
        """Запасной метод получения активного окна на Linux (через xprop)"""
        try:
            # Используем xprop для получения активного окна
            result = subprocess.run(
                ['xprop', '-root', '_NET_ACTIVE_WINDOW'],
                capture_output=True,
                text=True,
                timeout=1
            )
            
            if result.returncode != 0:
                return self._create_error_window("xprop failed")
            
            # Парсим вывод: _NET_ACTIVE_WINDOW(WINDOW): window id # 0x...
            match = re.search(r'0x[0-9a-fA-F]+', result.stdout)
            if not match:
                return self._create_error_window("Cannot parse window ID")
            
            window_id = match.group()
            
            # Получаем заголовок окна
            title_result = subprocess.run(
                ['xprop', '-id', window_id, 'WM_NAME'],
                capture_output=True,
                text=True,
                timeout=1
            )
            
            title = "Unknown"
            if title_result.returncode == 0:
                title_match = re.search(r'"([^"]*)"', title_result.stdout)
                if title_match:
                    title = title_match.group(1)
            
            # Получаем PID
            pid_result = subprocess.run(
                ['xprop', '-id', window_id, '_NET_WM_PID'],
                capture_output=True,
                text=True,
                timeout=1
            )
            
            pid = 0
            process_name = "Unknown"
            path = "Unknown"
            
            if pid_result.returncode == 0:
                pid_match = re.search(r'(\d+)', pid_result.stdout)
                if pid_match:
                    try:
                        pid = int(pid_match.group(1))
                        proc = psutil.Process(pid)
                        process_name = proc.name()
                        path = proc.exe()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
            
            return {
                'title': title,
                'process_name': process_name,
                'pid': pid,
                'path': path,
                'hwnd': int(window_id, 16) if window_id else None,
                'error': None
            }
            
        except Exception as e:
            return self._create_error_window(f"Fallback error: {str(e)}")
    
    def _create_error_window(self, error_msg: str) -> Dict[str, Any]:
        """Создать структуру окна с ошибкой"""
        return {
            'title': "Unknown",
            'process_name': "Unknown",
            'pid': 0,
            'path': "Unknown",
            'hwnd': None,
            'error': error_msg
        }
    
    # ============================================================================
    # ПУБЛИЧНЫЙ API - РАБОТА С ПРОЦЕССАМИ
    # ============================================================================
    
    def get_process_list(self, top_n: int = 10, sort_by: str = 'cpu') -> List[Dict[str, Any]]:
        """
        Получить список активных процессов системы с сортировкой.
        
        Собирает информацию обо всех запущенных процессах и возвращает 
        топ N процессов по выбранному критерию (CPU или память).
        Использует внутреннее кэширование для оптимизации (TTL = 500ms).
        
        Args:
            top_n (int): Количество процессов для возврата. По умолчанию 10.
            sort_by (str): Критерий сортировки - 'cpu' или 'memory'. 
                          По умолчанию 'cpu' (по загрузке процессора).
        
        Returns:
            List[dict]: Список словарей с информацией о процессах, отсортированный
                       по убыванию выбранного критерия:
                {
                    'pid': int,              # ID процесса
                    'name': str,             # Имя процесса
                    'cpu_percent': float,    # Загрузка CPU в процентах
                    'memory_mb': float,      # Используемая память в MB
                    'status': str,           # Статус: running, sleeping, zombie и т.д.
                    'path': str,             # Полный путь к исполняемому файлу
                    'username': str          # Имя пользователя, запустившего процесс
                }
        
        Example:
            >>> provider = ProcessProvider.get_instance()
            >>> # Топ 5 процессов по CPU
            >>> top_cpu = provider.get_process_list(top_n=5, sort_by='cpu')
            >>> for proc in top_cpu:
            ...     print(f"{proc['name']}: {proc['cpu_percent']}%")
            chrome.exe: 45.2%
            python.exe: 12.8%
            ...
            
            >>> # Топ 10 процессов по памяти
            >>> top_mem = provider.get_process_list(top_n=10, sort_by='memory')
        
        Note:
            - Результаты кэшируются на 500ms для оптимизации
            - Метод безопасен и не выбрасывает исключения
            - При ошибках возвращает пустой список
            - Требует небольшой задержки (~100ms) для точного замера CPU
        """
        # Проверяем кэш
        cached_data = self.cache.get()
        if cached_data is not None:
            return self._format_and_sort_processes(cached_data, top_n, sort_by)
        
        # Собираем данные о процессах
        process_list: List[ProcessInfo] = []
        
        try:
            # Первый вызов cpu_percent() для инициализации
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    proc.cpu_percent(interval=0)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            # Короткая пауза для сбора статистики CPU
            time.sleep(0.1)
            
            # Собираем данные
            for proc in psutil.process_iter(['pid', 'name', 'status']):
                try:
                    pinfo = ProcessInfo(
                        pid=proc.info['pid'],
                        name=proc.info['name'] or "Unknown",
                        status=proc.info['status'] or "unknown"
                    )
                    
                    # Безопасно получаем дополнительные данные
                    try:
                        pinfo.cpu_percent = proc.cpu_percent(interval=0)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pinfo.cpu_percent = 0.0
                    
                    try:
                        mem_info = proc.memory_info()
                        pinfo.memory_mb = mem_info.rss / (1024 * 1024)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pinfo.memory_mb = 0.0
                    
                    try:
                        pinfo.path = proc.exe()
                    except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
                        pinfo.path = "Access Denied"
                    
                    try:
                        pinfo.username = proc.username()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pinfo.username = "Unknown"
                    
                    process_list.append(pinfo)
                    
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # Обновляем кэш
            self.cache.update(process_list)
            
        except Exception as e:
            # В случае критической ошибки возвращаем пустой список
            return []
        
        return self._format_and_sort_processes(process_list, top_n, sort_by)
    
    def _format_and_sort_processes(
        self, 
        process_list: List[ProcessInfo], 
        top_n: int, 
        sort_by: str
    ) -> List[Dict[str, Any]]:
        """Форматирует и сортирует список процессов"""
        # Сортируем
        if sort_by.lower() == 'memory':
            process_list.sort(key=lambda x: x.memory_mb, reverse=True)
        else:  # по умолчанию по CPU
            process_list.sort(key=lambda x: x.cpu_percent, reverse=True)
        
        # Ограничиваем количество
        process_list = process_list[:top_n]
        
        # Форматируем в словари
        return [
            {
                'pid': p.pid,
                'name': p.name,
                'cpu_percent': round(p.cpu_percent, 2),
                'memory_mb': round(p.memory_mb, 2),
                'status': p.status,
                'path': p.path,
                'username': p.username
            }
            for p in process_list
        ]
    
    def find_process(self, name_pattern: str) -> List[Dict[str, Any]]:
        """
        Найти процессы по паттерну имени.
        
        Args:
            name_pattern: Паттерн для поиска (регистронезависимый, поддерживает *)
        
        Returns:
            List[dict]: Список найденных процессов (тот же формат, что и get_process_list)
        """
        try:
            # Преобразуем паттерн в regex
            pattern = name_pattern.replace('*', '.*').lower()
            regex = re.compile(pattern, re.IGNORECASE)
            
            found_processes: List[Dict[str, Any]] = []
            
            for proc in psutil.process_iter(['pid', 'name', 'status']):
                try:
                    proc_name = proc.info['name'] or ""
                    
                    if regex.search(proc_name):
                        pinfo = {
                            'pid': proc.info['pid'],
                            'name': proc_name,
                            'status': proc.info['status'] or "unknown",
                            'cpu_percent': 0.0,
                            'memory_mb': 0.0,
                            'path': "Unknown",
                            'username': "Unknown"
                        }
                        
                        # Безопасно получаем дополнительные данные
                        try:
                            pinfo['cpu_percent'] = round(proc.cpu_percent(interval=0), 2)
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                        
                        try:
                            mem_info = proc.memory_info()
                            pinfo['memory_mb'] = round(mem_info.rss / (1024 * 1024), 2)
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                        
                        try:
                            pinfo['path'] = proc.exe()
                        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
                            pinfo['path'] = "Access Denied"
                        
                        try:
                            pinfo['username'] = proc.username()
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                        
                        found_processes.append(pinfo)
                
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            return found_processes
            
        except Exception as e:
            return []
    
    def get_system_load(self) -> Dict[str, Any]:
        """
        Получить общую статистику системы.
        
        Returns:
            dict: {
                'cpu_percent': float,       # Общая загрузка CPU в %
                'memory_percent': float,    # Использование RAM в %
                'memory_used_mb': float,    # Использовано RAM в MB
                'memory_total_mb': float,   # Всего RAM в MB
                'disk_usage_percent': float,# Использование диска в %
                'error': str|None           # Ошибка, если есть
            }
        """
        try:
            # CPU загрузка
            cpu_percent = psutil.cpu_percent(interval=0.1)
            
            # Память
            mem = psutil.virtual_memory()
            memory_percent = mem.percent
            memory_used_mb = mem.used / (1024 * 1024)
            memory_total_mb = mem.total / (1024 * 1024)
            
            # Диск
            disk_usage_percent = 0.0
            try:
                disk = psutil.disk_usage('/')
                disk_usage_percent = disk.percent
            except Exception:
                pass
            
            return {
                'cpu_percent': round(cpu_percent, 2),
                'memory_percent': round(memory_percent, 2),
                'memory_used_mb': round(memory_used_mb, 2),
                'memory_total_mb': round(memory_total_mb, 2),
                'disk_usage_percent': round(disk_usage_percent, 2),
                'error': None
            }
            
        except Exception as e:
            return {
                'cpu_percent': 0.0,
                'memory_percent': 0.0,
                'memory_used_mb': 0.0,
                'memory_total_mb': 0.0,
                'disk_usage_percent': 0.0,
                'error': f"System load error: {str(e)}"
            }
    
    def kill_process(self, pid: int, force: bool = False) -> Tuple[bool, str]:
        """
        Завершить процесс по PID.
        
        Args:
            pid: ID процесса для завершения
            force: Если True, использует SIGKILL (Linux) или TerminateProcess (Windows)
        
        Returns:
            Tuple[bool, str]: (успех, сообщение)
        """
        try:
            proc = psutil.Process(pid)
            proc_name = proc.name()
            
            if force:
                proc.kill()  # SIGKILL
            else:
                proc.terminate()  # SIGTERM
            
            # Ждем завершения процесса (максимум 3 секунды)
            try:
                proc.wait(timeout=3)
            except psutil.TimeoutExpired:
                if not force:
                    return (False, f"Process {proc_name} (PID: {pid}) did not terminate in time. Try force=True")
            
            return (True, f"Process {proc_name} (PID: {pid}) terminated successfully")
            
        except psutil.NoSuchProcess:
            return (False, f"Process with PID {pid} not found")
        except psutil.AccessDenied:
            return (False, f"Access denied to terminate process PID {pid}. Insufficient privileges")
        except Exception as e:
            return (False, f"Error terminating process PID {pid}: {str(e)}")
    
    # ============================================================================
    # ДОПОЛНИТЕЛЬНЫЕ УТИЛИТЫ
    # ============================================================================
    
    def get_process_info(self, pid: int) -> Optional[Dict[str, Any]]:
        """
        Получить подробную информацию о конкретном процессе.
        
        Args:
            pid: ID процесса
        
        Returns:
            dict|None: Информация о процессе или None, если не найден
        """
        try:
            proc = psutil.Process(pid)
            
            info = {
                'pid': pid,
                'name': proc.name(),
                'status': proc.status(),
                'cpu_percent': round(proc.cpu_percent(interval=0.1), 2),
                'memory_mb': round(proc.memory_info().rss / (1024 * 1024), 2),
                'path': "Unknown",
                'username': "Unknown",
                'create_time': 0,
                'num_threads': 0,
                'connections': []
            }
            
            try:
                info['path'] = proc.exe()
            except (psutil.AccessDenied, OSError):
                info['path'] = "Access Denied"
            
            try:
                info['username'] = proc.username()
            except psutil.AccessDenied:
                pass
            
            try:
                info['create_time'] = proc.create_time()
            except psutil.AccessDenied:
                pass
            
            try:
                info['num_threads'] = proc.num_threads()
            except psutil.AccessDenied:
                pass
            
            try:
                connections = proc.connections()
                info['connections'] = [
                    {
                        'fd': conn.fd,
                        'family': str(conn.family),
                        'type': str(conn.type),
                        'laddr': f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else None,
                        'raddr': f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else None,
                        'status': conn.status
                    }
                    for conn in connections[:5]  # Ограничиваем 5 соединениями
                ]
            except (psutil.AccessDenied, AttributeError):
                pass
            
            return info
            
        except psutil.NoSuchProcess:
            return None
        except Exception:
            return None
    
    def clear_cache(self) -> None:
        """Очистить кэш процессов (форсировать обновление при следующем вызове)"""
        with self.cache.lock:
            self.cache.last_update = None
            self.cache.process_list = []


# ============================================================================
# CONVENIENCE FUNCTIONS - Удобные функции для быстрого использования
# ============================================================================

def get_active_window() -> Dict[str, Any]:
    """Быстрый доступ к информации об активном окне"""
    return ProcessProvider.get_instance().get_active_window()


def get_top_processes(count: int = 10, by: str = 'cpu') -> List[Dict[str, Any]]:
    """Быстрый доступ к списку топ процессов"""
    return ProcessProvider.get_instance().get_process_list(top_n=count, sort_by=by)


def get_system_stats() -> Dict[str, Any]:
    """Быстрый доступ к системной статистике"""
    return ProcessProvider.get_instance().get_system_load()


def find_processes(pattern: str) -> List[Dict[str, Any]]:
    """Быстрый поиск процессов по паттерну"""
    return ProcessProvider.get_instance().find_process(pattern)


# ============================================================================
# ПРИМЕР ИСПОЛЬЗОВАНИЯ
# ============================================================================

if __name__ == "__main__":
    # Демонстрация использования ProcessProvider
    provider = ProcessProvider.get_instance()
    
    print("=" * 80)
    print("ProcessProvider Demo")
    print("=" * 80)
    
    # 1. Активное окно
    print("\n1. Active Window:")
    active = provider.get_active_window()
    if active['error']:
        print(f"   Error: {active['error']}")
    else:
        print(f"   Title: {active['title']}")
        print(f"   Process: {active['process_name']} (PID: {active['pid']})")
        print(f"   Path: {active['path']}")
    
    # 2. Топ процессов по CPU
    print("\n2. Top 5 Processes by CPU:")
    top_cpu = provider.get_process_list(top_n=5, sort_by='cpu')
    for i, proc in enumerate(top_cpu, 1):
        print(f"   {i}. {proc['name']} - CPU: {proc['cpu_percent']}%, RAM: {proc['memory_mb']} MB")
    
    # 3. Топ процессов по памяти
    print("\n3. Top 5 Processes by Memory:")
    top_mem = provider.get_process_list(top_n=5, sort_by='memory')
    for i, proc in enumerate(top_mem, 1):
        print(f"   {i}. {proc['name']} - RAM: {proc['memory_mb']} MB, CPU: {proc['cpu_percent']}%")
    
    # 4. Системная нагрузка
    print("\n4. System Load:")
    load = provider.get_system_load()
    if load['error']:
        print(f"   Error: {load['error']}")
    else:
        print(f"   CPU: {load['cpu_percent']}%")
        print(f"   RAM: {load['memory_percent']}% ({load['memory_used_mb']:.0f} / {load['memory_total_mb']:.0f} MB)")
        print(f"   Disk: {load['disk_usage_percent']}%")
    
    # 5. Поиск процессов
    print("\n5. Search for Python processes:")
    python_procs = provider.find_process("python*")
    for proc in python_procs[:3]:  # Показываем первые 3
        print(f"   - {proc['name']} (PID: {proc['pid']}) - CPU: {proc['cpu_percent']}%")
    
    # 6. Демонстрация кэширования
    print("\n6. Cache Demo:")
    print("   First call (no cache)...")
    start = time.time()
    provider.get_process_list(top_n=10)
    print(f"   Time: {(time.time() - start) * 1000:.2f} ms")
    
    print("   Second call (with cache)...")
    start = time.time()
    provider.get_process_list(top_n=10)
    print(f"   Time: {(time.time() - start) * 1000:.2f} ms")
    
    print("\n" + "=" * 80)

