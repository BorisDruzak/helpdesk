"""
Точка входа для GUI приложения.
"""

import asyncio
import aiohttp
from pathlib import Path
from typing import Any, Callable, Optional
from PySide6.QtWidgets import QApplication, QDialog
from PySide6.QtCore import QObject, Signal, QTimer, Qt
from loguru import logger

from pc_agent.auth.token_source import load_auth_token_from_db
from pc_agent.core import runtime_paths
from . import theme
from .main_window import MainWindow
from .automation_controller import GuiAutomationController
from .sse_client import SseClient
from .token_dialog import TokenDialog
from .tray_manager import TrayManager
from .wait_for_auth_dialog import WaitForAuthDialog


class EventHandler(QObject):
    """
    QObject для передачи событий из async контекста в Qt.
    """
    event_received = Signal(dict)
    
    def __init__(self, window: MainWindow, after_event: Optional[Callable[[dict], None]] = None):
        super().__init__()
        self.window = window
        self.after_event = after_event
        self.event_received.connect(self._on_event)
    
    def _on_event(self, event: dict):
        """Обработчик события в Qt контексте."""
        self.window.handle_event(event)
        if self.after_event:
            self.after_event(event)


async def verify_token_on_server(api_url: str, token: str) -> bool:
    """
    Проверяет валидность токена через сервер API.
    
    Args:
        api_url: URL API сервера (например, http://localhost:8666/api)
        token: Токен для проверки
        
    Returns:
        True если токен валиден, False иначе
    """
    if not token:
        return False
    
    try:
        # Используем любой защищенный endpoint для проверки токена
        # Например, /api/agents - он требует авторизацию
        check_url = f"{api_url}/agents"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                check_url,
                headers={"Authorization": f"Bearer {token}"},
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                # 200 или 404 (пустой список агентов) = токен валиден
                # 401 = токен невалиден
                if response.status in (200, 404):
                    logger.info("✅ Токен проверен и валиден на сервере")
                    return True
                elif response.status == 401:
                    logger.warning("❌ Токен невалиден (401 Unauthorized)")
                    return False
                else:
                    logger.warning(f"⚠️ Неожиданный статус при проверке токена: {response.status}")
                    return False
    except aiohttp.ClientError as e:
        logger.error(f"❌ Ошибка сети при проверке токена: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка при проверке токена: {e}")
        return False


async def get_stored_token() -> Optional[str]:
    """
    Получает сохраненный токен из БД агента.
    
    Returns:
        Токен если найден, None иначе
    """
    import os
    
    # 1. Проверяем ENV переменную
    env_token = os.getenv("AUTH_TOKEN")
    if env_token:
        logger.debug("Токен найден в переменной окружения AUTH_TOKEN")
        return env_token
    
    # 2. Проверяем БД агента (основной источник)
    try:
        from core.identity import IdentityManager
        from core.database import db_manager  # Используем глобальный экземпляр
        
        identity_manager = IdentityManager()
        identity_data = identity_manager.load_or_create()
        device_uuid = identity_data.get('uuid')
        
        if device_uuid and db_manager:
            token = await load_auth_token_from_db(db_manager, identity_manager)
            if token:
                logger.debug("✅ Токен найден в БД агента")
                return token
            else:
                logger.debug("⚠️ Токен не найден в БД агента")
    except Exception as e:
        logger.debug(f"❌ Не удалось загрузить токен из БД: {e}")
    
    return None


async def show_token_dialog_async(device_uuid: str) -> Optional[str]:
    """
    Показывает диалог ввода токена асинхронно.
    
    Args:
        device_uuid: UUID устройства
        
    Returns:
        Введенный токен или None если отменено
    """
    app = QApplication.instance()
    if app is None:
        logger.error("QApplication не инициализирован")
        return None
    
    logger.info("📋 Создаю диалог ввода токена...")
    dialog = TokenDialog(device_uuid)
    
    # Используем Future для асинхронного ожидания результата
    dialog_future = asyncio.Future()
    
    def on_finished(result):
        if not dialog_future.done():
            try:
                if result == QDialog.DialogCode.Accepted:
                    token = dialog.get_token()
                    logger.info(f"✅ Диалог закрыт с токеном (длина: {len(token) if token else 0})")
                    
                    # КРИТИЧНО: Сохраняем токен В БД СРАЗУ, до возврата из функции
                    # Используем СИНХРОННЫЙ метод чтобы избежать проблем с event loop
                    if token:
                        try:
                            from core.identity import IdentityManager
                            from core.database import db_manager
                            
                            identity_manager = IdentityManager()
                            identity_manager.load_or_create()
                            identity_manager.uuid = device_uuid
                            identity_manager.token = token
                            
                            logger.info(f"💾 Сохраняю токен в БД (синхронно, внутри on_finished)...")
                            
                            # Используем СИНХРОННЫЙ метод для надежного сохранения
                            if db_manager:
                                success = db_manager.save_auth_token_sync(token, device_uuid)
                                if success:
                                    logger.success(f"✅ Токен сохранен в БД для device_id={device_uuid[:8]}...")
                                else:
                                    logger.error("❌ Не удалось сохранить токен в БД")
                            else:
                                logger.error("❌ DatabaseManager недоступен")
                        except Exception as e:
                            logger.error(f"❌ Ошибка сохранения токена: {e}")
                            logger.exception(e)
                    
                    # Устанавливаем результат безопасно
                    try:
                        dialog_future.set_result(token)
                    except Exception as e:
                        logger.error(f"❌ Ошибка при установке результата Future: {e}")
                else:
                    logger.info("❌ Диалог отменен пользователем")
                    try:
                        dialog_future.set_result(None)
                    except Exception as e:
                        logger.error(f"❌ Ошибка при установке None в Future: {e}")
            except Exception as e:
                logger.error(f"❌ Ошибка в on_finished: {e}")
                logger.exception(e)
                if not dialog_future.done():
                    try:
                        dialog_future.set_result(None)
                    except Exception:
                        pass
    
    dialog.finished.connect(on_finished)
    
    # Устанавливаем флаги окна, чтобы диалог был поверх всех окон
    dialog.setWindowFlags(
        dialog.windowFlags() | 
        Qt.WindowType.WindowStaysOnTopHint | 
        Qt.WindowType.WindowCloseButtonHint |
        Qt.WindowType.Dialog
    )
    dialog.setModal(True)
    
    # Планируем показ диалога
    dialog_shown = False
    
    def show_dialog():
        nonlocal dialog_shown
        try:
            logger.info("🖼️ Показываю диалог ввода токена...")
            dialog.show()  # Используем show() вместо open() для лучшей совместимости
            dialog.raise_()
            dialog.activateWindow()
            if dialog.isMinimized():
                dialog.showNormal()
            dialog.setWindowState(dialog.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
            dialog_shown = True
            logger.info("✅ Диалог ввода токена отображен")
        except Exception as e:
            logger.error(f"❌ Ошибка при показе диалога: {e}")
            logger.exception(e)
    
    # Показываем диалог сразу
    show_dialog()
    
    # Обрабатываем события Qt, чтобы диалог отобразился
    # Используем try-except для обработки ошибок event loop
    for _ in range(10):  # Несколько раз обрабатываем события
        app.processEvents()
        try:
            # Получаем текущий event loop
            loop = asyncio.get_running_loop()
            if loop.is_running():
                await asyncio.sleep(0.05)
            else:
                # Если loop не запущен, просто обрабатываем события Qt
                import time
                time.sleep(0.05)
        except RuntimeError:
            # Если event loop не доступен, используем обычный sleep
            import time
            time.sleep(0.05)
    
    if not dialog_shown:
        logger.warning("⚠️ Диалог не был показан, повторная попытка...")
        QTimer.singleShot(0, show_dialog)
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                await asyncio.sleep(0.2)
            else:
                import time
                time.sleep(0.2)
        except RuntimeError:
            import time
            time.sleep(0.2)
        app.processEvents()
        
        # Если диалог все еще не показан, завершаем Future немедленно
        if not dialog_shown:
            logger.error("❌ Диалог не может быть показан, завершаю Future")
            if not dialog_future.done():
                try:
                    dialog_future.set_result(None)
                except Exception:
                    pass
            return None
    
    # Ждем результат асинхронно, периодически обрабатывая события Qt
    max_wait_time = 300  # Максимум 30 секунд
    wait_time = 0
    try:
        while not dialog_future.done() and wait_time < max_wait_time:
            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    await asyncio.sleep(0.1)
                else:
                    import time
                    time.sleep(0.1)
            except RuntimeError:
                import time
                time.sleep(0.1)
            app.processEvents()  # Важно обрабатывать события Qt
            wait_time += 0.1
        
        if not dialog_future.done():
            logger.warning("⏱️ Тайм-аут ожидания ввода токена")
            dialog.close()
            if not dialog_future.done():
                try:
                    dialog_future.set_result(None)
                except Exception:
                    pass  # Future уже может быть done
            return None
        
        # Получаем результат безопасно
        if dialog_future.done():
            try:
                # Используем .result() вместо await для избежания проблем с event loop
                result = dialog_future.result()
                logger.info(f"✅ Результат диалога получен: {'токен' if result else 'None'}")
                return result
            except Exception as e:
                logger.error(f"❌ Ошибка при получении результата диалога: {e}")
                logger.exception(e)
                return None
        else:
            logger.warning("⚠️ Future не завершен, но цикл ожидания закончился")
            return None
    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка при ожидании диалога: {e}")
        logger.exception(e)
        if not dialog_future.done():
            try:
                dialog_future.set_result(None)
            except Exception:
                pass
        return None
    finally:
        # Гарантируем, что Future всегда завершен перед возвратом
        if not dialog_future.done():
            logger.warning("⚠️ Future не завершен в finally, завершаю принудительно")
            try:
                dialog_future.set_result(None)
            except Exception:
                pass


async def run_gui(
    host: str,
    port: int,
    stop_event: Optional[asyncio.Event] = None,
    auth_complete_event: Optional[asyncio.Event] = None,
    *,
    ui_bridge_listening: Optional[bool] = None,
    ui_api_server: Any = None,
):
    """
    Запускает GUI приложение.

    Требует валидный токен аутентификации перед показом главного окна.
    Если токен отсутствует или невалиден - показывает диалог авторизации.

    Args:
        host: Хост UI API сервера
        port: Порт UI API сервера
        stop_event: Событие для остановки (опционально)
        ui_bridge_listening: False — мост не поднят (порт занят и т.д.), SSE не запускать;
            None — определить по /health; True — считать, что bind был успешен, всё равно проверить /health.
    """
    try:
        logger.info("🚀 run_gui() начал выполнение")
        # QApplication должен быть уже создан в main() через qasync
        # Даем event loop возможность обработать другие задачи перед работой с Qt
        await asyncio.sleep(0)
        
        app = QApplication.instance()
        if app is None:
            logger.error("❌ QApplication не инициализирован!")
            raise RuntimeError("QApplication должен быть создан до вызова run_gui()")
        
        # КРИТИЧНО: Устанавливаем флаг чтобы QApplication НЕ завершался при закрытии последнего окна
        # Это необходимо потому что TokenDialog может быть единственным окном на момент закрытия
        app.setQuitOnLastWindowClosed(False)
        logger.debug("✅ setQuitOnLastWindowClosed(False) установлен")

        from PySide6.QtGui import QFont

        _app_font = QFont()
        _app_font.setFamilies(["Segoe UI", "Tahoma", "Arial"])
        _app_font.setPointSize(10)
        app.setFont(_app_font)

        logger.info("✅ QApplication найден")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при инициализации GUI: {e}")
        logger.exception(e)
        if stop_event:
            stop_event.set()
        raise
    
    # Получаем конфигурацию для API URL (дефолт — сервер 192.168.100.17, не localhost)
    try:
        from pc_agent.config.config_loader import get_config
        cfg = get_config()
        api_url = cfg.server.api_url
        theme.apply_application_theme(app, getattr(cfg.ui, "theme_mode", "light"))
    except Exception as e:
        from pc_agent.config.config_loader import ServerConfig
        logger.warning(f"Не удалось загрузить конфиг, используем дефолтный API URL: {e}")
        api_url = ServerConfig().api_url
        theme.apply_application_theme(app, "light")
    
    # Получаем device UUID для диалога
    try:
        from core.identity import IdentityManager
        identity_manager = IdentityManager()
        identity_data = identity_manager.load_or_create()
        device_uuid = identity_data.get('uuid', 'Unknown')
    except Exception as e:
        logger.error(f"Не удалось загрузить device UUID: {e}")
        device_uuid = 'Unknown'
    
    # ===== ПРОВЕРКА ТОКЕНА ПЕРЕД ПОКАЗОМ ГЛАВНОГО ОКНА =====
    logger.info("🔐 Проверка токена аутентификации...")
    
    valid_token = None
    stored_token = await get_stored_token()
    
    if stored_token:
        logger.info("✅ Найден сохраненный токен в БД агента")
        # Не проверяем через HTTP API - agent токены работают только через WebSocket
        # Токен будет проверен при подключении к серверу
        valid_token = stored_token
        logger.success("✅ Токен загружен из БД, открываю главное окно")
        # Сигнализируем main_async(), что авторизация завершена — агент может сразу подключаться по WebSocket
        if auth_complete_event:
            auth_complete_event.set()
    
    # Если токен невалиден или отсутствует — показываем «Дождитесь авторизации» или диалог ввода токена
    if not valid_token:
        logger.info("🔑 Требуется авторизация (запрос на подключение или ввод токена вручную)")
        # Сначала показываем экран «Дождитесь авторизации»; агент отправит запрос на подключение
        while not valid_token:
            wait_dialog = WaitForAuthDialog(device_uuid, on_auth_complete=lambda: auth_complete_event and auth_complete_event.set())
            wait_dialog.start_polling()
            # Неблокирующее ожидание: exec() блокирует поток и не даёт asyncio-задаче опроса статуса выполняться.
            loop = asyncio.get_event_loop()
            future = loop.create_future()
            def on_finished():
                if not future.done():
                    future.set_result(wait_dialog.result())
            wait_dialog.finished.connect(on_finished)
            wait_dialog.show()
            result = await future
            if result == 1:  # QDialog.Accepted
                valid_token = wait_dialog.get_token()
                if valid_token:
                    if auth_complete_event:
                        auth_complete_event.set()
                    break
            if wait_dialog.was_manual_requested():
                # Пользователь нажал «Ввести токен вручную» — показываем старый диалог
                if auth_complete_event:
                    auth_complete_event.set()
                token = None
                try:
                    token = await show_token_dialog_async(device_uuid)
                except Exception as e:
                    logger.error(f"Ошибка при показе диалога токена: {e}")
                    token = None
                if token:
                    valid_token = token
                    try:
                        from core.database import db_manager
                        if db_manager:
                            import sqlite3
                            conn = sqlite3.connect(db_manager._db_path)
                            cursor = conn.cursor()
                            cursor.execute("""
                                SELECT token FROM auth_tokens
                                WHERE device_id = ? AND is_active = 1
                                ORDER BY created_at DESC
                                LIMIT 1
                            """, (device_uuid,))
                            row = cursor.fetchone()
                            conn.close()
                            if row:
                                valid_token = row[0]
                    except Exception as e:
                        logger.warning(f"Не удалось загрузить токен из БД: {e}")
                    if auth_complete_event:
                        auth_complete_event.set()
                    break
                continue
            # Отмена
            logger.info("Авторизация отменена пользователем")
            if stop_event:
                stop_event.set()
            if auth_complete_event:
                auth_complete_event.set()
            return
        logger.info("=" * 70)
    
    # ===== ТОЛЬКО ПОСЛЕ УСПЕШНОЙ АВТОРИЗАЦИИ СОЗДАЕМ ГЛАВНОЕ ОКНО =====
    if not valid_token:
        logger.error("❌ Не удалось получить валидный токен")
        if stop_event:
            stop_event.set()
        return
    
    logger.info("🚀 Открываю главное окно GUI...")
    
    # Создаем главное окно ТОЛЬКО после успешной авторизации
    # Передаем токен в MainWindow для использования в API клиенте
    window = MainWindow(host, port, auth_token=valid_token)
    
    # Не включаем quit при закрытии окна — завершение через stop_event и main_async cleanup,
    # затем app.quit() в ws_agent.main(), чтобы не останавливать event loop до завершения main_async
    app = QApplication.instance()
    if app:
        app.setQuitOnLastWindowClosed(False)
        logger.debug("✅ setQuitOnLastWindowClosed(False) — выход по закрытию окна обрабатывается в main_async")
    
    cfg = get_config()
    tray_config = cfg.ui if cfg and cfg.ui else None
    try:
        from pc_agent.config.config_loader import get_config_base

        data_root = get_config_base() or Path.cwd()
    except Exception:
        data_root = Path.cwd()
    logs_dir = runtime_paths.resolve_logs_dir(Path(data_root))

    exit_requested = False
    tray_hidden_once = False
    tray_manager: Optional[TrayManager] = None

    async def request_agent_restart_from_tray() -> None:
        url = f"http://{host}:{port}/ui/agent/restart"
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.post(url, json={"reason": "tray", "delay_sec": 0.8}) as resp:
                if resp.status >= 400:
                    raise RuntimeError(await resp.text())

    def show_window_from_tray() -> None:
        if not window.isVisible():
            window.show()
        if window.isMinimized():
            window.showNormal()
        window.raise_()
        window.activateWindow()

    def restart_agent_from_tray() -> None:
        asyncio.create_task(request_agent_restart_from_tray())

    def exit_agent_from_tray() -> None:
        nonlocal exit_requested
        exit_requested = True
        window.close()

    if tray_config and tray_config.tray_enabled:
        tray_manager = TrayManager(
            tooltip="Maria Agent",
            logs_dir=logs_dir,
            notifications_enabled=bool(tray_config.notifications_enabled),
            on_show_window=show_window_from_tray,
            on_restart_agent=restart_agent_from_tray,
            on_exit_agent=exit_agent_from_tray,
        )
        if tray_manager.available:
            tray_manager.show()
        else:
            tray_manager = None

    automation_controller: Optional[GuiAutomationController] = None
    if ui_api_server is not None:
        automation_controller = GuiAutomationController(
            window,
            tray_manager=tray_manager,
            request_exit=exit_agent_from_tray,
        )
        ui_api_server.on_get_automation_status = automation_controller.get_status
        ui_api_server.on_run_automation = automation_controller.run_action

    def after_event(event: dict) -> None:
        if not tray_manager:
            return
        event_type = str(event.get("event_type") or "")
        if event_type != "connection_state":
            return
        payload = event.get("data") or {}
        state = str(payload.get("state") or "unknown")
        detail = str(payload.get("detail") or "").strip()
        tooltip = f"Maria Agent — {state}"
        if detail:
            tooltip += f" ({detail})"
        tray_manager.set_tooltip(tooltip)

    # Создаем обработчик событий
    event_handler = EventHandler(window, after_event=after_event)
    
    # Создаем SSE клиент (только если есть шанс, что на порту именно UiApiServer)
    base_url = f"http://{host}:{port}"
    sse_client = SseClient(base_url)

    import aiohttp

    max_retries = 10
    retry_count = 0
    server_ready = False

    if ui_bridge_listening is False:
        logger.error(
            f"❌ Локальный UI-мост не слушает {host}:{port} (порт занят другим процессом или bind не удался). "
            f"Закройте лишний экземпляр агента или смените ui.port в конфиге. SSE не запускаю."
        )
    else:
        while retry_count < max_retries and not server_ready:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{base_url}/health", timeout=aiohttp.ClientTimeout(total=2)
                    ) as response:
                        if response.status != 200:
                            logger.debug(
                                f"UI API health: HTTP {response.status} (попытка {retry_count + 1}/{max_retries})"
                            )
                        else:
                            try:
                                data = await response.json()
                            except Exception as exc:
                                logger.debug(f"UI API health: не JSON ({exc})")
                                data = {}
                            if data.get("service") == "ui_bridge":
                                server_ready = True
                                logger.info("✅ UI API (ui_bridge) готов к подключению")
                                break
                            logger.warning(
                                f"⚠️ На {host}:{port} отвечает не pc_agent UiApiServer "
                                f"(health service={data.get('service')!r}). "
                                f"Закройте процесс, занявший порт, или смените ui.port."
                            )
            except Exception as e:
                logger.debug(f"UI API сервер еще не готов (попытка {retry_count + 1}/{max_retries}): {e}")

            if not server_ready:
                retry_count += 1
                await asyncio.sleep(0.5)

        if not server_ready:
            logger.error(
                f"❌ Не найден ui_bridge на {base_url}/health — SSE не запускаю (избегаем HTTP 404 в цикле)."
            )

    window.set_bridge_connected(False)
    window.set_connection_state("connecting", "ожидание сервера")
    
    # Создаем событие для ожидания закрытия окна
    window_closed = asyncio.Event()
    window_closing = False  # Флаг для защиты от двойного вызова
    sse_stop_task: Optional[asyncio.Task] = None
    
    # Запускаем SSE клиент в фоне
    async def sse_task():
        def on_event(event: dict):
            # Передаем событие в Qt контекст через сигнал
            event_handler.event_received.emit(event)

        def on_connection_change(connected: bool):
            window.set_bridge_connected(connected)
        
        try:
            await sse_client.run(on_event, on_connection_change=on_connection_change)
        except asyncio.CancelledError:
            logger.info("SSE клиент отменен")
        except Exception as e:
            logger.error(f"Ошибка в SSE клиенте: {e}")
            window.set_bridge_connected(False)
    
    sse_task_obj: Optional[asyncio.Task] = None
    if server_ready:
        sse_task_obj = asyncio.create_task(sse_task())
    else:
        window.set_bridge_connected(False)
        window.set_connection_state("disconnected", "мост UI недоступен")
    
    # Обработчик финального закрытия окна
    def on_window_closed():
        nonlocal window_closing, sse_stop_task
        if window_closing:
            return  # Уже обрабатывается
        window_closing = True
        
        # Сразу останавливаем опрос тикетов, чтобы не было запросов list_tickets после закрытия
        try:
            cp = getattr(window, "chat_panel", None)
        except Exception:
            cp = None
        if cp:
            for method_name in ("_stop_ticket_list_polling", "_stop_ticket_detail_polling"):
                stopper = getattr(cp, method_name, None)
                if callable(stopper):
                    try:
                        stopper()
                    except Exception as e:
                        logger.debug(f"Ошибка остановки polling ({method_name}): {e}")
        logger.info("GUI закрывается, останавливаю SSE клиент...")
        sse_client.stop()
        try:
            loop = asyncio.get_running_loop()
            if not loop.is_closed():
                sse_stop_task = loop.create_task(sse_client.stop_async(), name="gui.sse_stop")
        except Exception as e:
            logger.debug(f"Не удалось создать задачу остановки SSE: {e}")
        if sse_task_obj is not None:
            sse_task_obj.cancel()
        try:
            window_closed.set()
        except RuntimeError as e:
            logger.debug(f"Не удалось сигнализировать window_closed: {e}")
        if stop_event and exit_requested:
            stop_event.set()
    
    # Подключаем обработчик к сигналу destroyed() окна
    # Также переопределяем closeEvent для корректной обработки закрытия
    # Сохраняем оригинальный метод
    original_close_event = window.closeEvent
    
    # Создаем новый метод, который вызывает обработчик и оригинальный метод
    def close_event_handler(event):
        nonlocal tray_hidden_once
        if (
            tray_manager
            and tray_manager.available
            and tray_config
            and tray_config.minimize_to_tray
            and not exit_requested
        ):
            event.ignore()
            window.hide()
            if not tray_hidden_once:
                tray_hidden_once = True
                tray_manager.notify("Maria Agent", "Агент продолжает работать в трее.")
            logger.info("GUI скрыт в tray; агент продолжает работать")
            return
        on_window_closed()
        if original_close_event:
            original_close_event(event)
        else:
            event.accept()
    
    # Переопределяем метод
    window.closeEvent = close_event_handler
    if tray_manager:
        tray_manager.set_tooltip("Maria Agent — запуск GUI")

    if tray_config and tray_config.start_hidden and tray_manager and tray_manager.available:
        window.hide()
        tray_manager.notify("Maria Agent", "Агент запущен в фоне и доступен из трея.")
    else:
        window.show()

    async def cleanup_gui_resources() -> None:
        if not window_closed.is_set():
            on_window_closed()

        if ui_api_server is not None:
            ui_api_server.on_get_automation_status = None
            ui_api_server.on_run_automation = None

        if hasattr(window, "chat_panel") and window.chat_panel:
            cp = window.chat_panel
            if getattr(cp, "ticket_client", None):
                try:
                    await cp.ticket_client.close()
                except Exception as e:
                    logger.debug(f"Р—Р°РєСЂС‹С‚РёРµ ticket_client: {e}")
            if getattr(cp, "client", None):
                try:
                    await cp.client.close()
                except Exception as e:
                    logger.debug(f"Р—Р°РєСЂС‹С‚РёРµ client: {e}")
        if sse_stop_task:
            try:
                await asyncio.wait_for(sse_stop_task, timeout=1.5)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                logger.debug("РћСЃС‚Р°РЅРѕРІРєР° SSE РєР»РёРµРЅС‚Р° РїСЂРµРІС‹СЃРёР»Р° С‚Р°Р№РјР°СѓС‚")
        if sse_task_obj is not None:
            try:
                await asyncio.wait_for(sse_task_obj, timeout=2.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                logger.debug("РћР¶РёРґР°РЅРёРµ Р·Р°РІРµСЂС€РµРЅРёСЏ SSE Р·Р°РґР°С‡Рё РїСЂРµРІС‹СЃРёР»Рѕ С‚Р°Р№РјР°СѓС‚")
        if tray_manager:
            tray_manager.cleanup()
    
    logger.success(f"GUI запущен на {host}:{port}")
    
    # В qasync event loop уже запущен, поэтому не вызываем app.exec()
    # Вместо этого ждем, пока окно не закроется
    try:
        await window_closed.wait()
    finally:
        await cleanup_gui_resources()
    return

    # Закрываем сессии API-клиентов и даём SSE-задаче завершиться (избегаем Unclosed client session)
    if hasattr(window, "chat_panel") and window.chat_panel:
        cp = window.chat_panel
        if getattr(cp, "ticket_client", None):
            try:
                await cp.ticket_client.close()
            except Exception as e:
                logger.debug(f"Закрытие ticket_client: {e}")
        if getattr(cp, "client", None):
            try:
                await cp.client.close()
            except Exception as e:
                logger.debug(f"Закрытие client: {e}")
    if sse_stop_task:
        try:
            await asyncio.wait_for(sse_stop_task, timeout=1.5)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            logger.debug("Остановка SSE клиента превысила таймаут")
    if sse_task_obj is not None:
        try:
            await asyncio.wait_for(sse_task_obj, timeout=2.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            logger.debug("Ожидание завершения SSE задачи превысило таймаут")
    if tray_manager:
        tray_manager.cleanup()
