"""
WebSocket сервер для управления удалёнными PC агентами (relay-архитектура).

Этот сервер выступает в роли ретранслятора команд между веб-интерфейсом
и удалёнными агентами. Сервер НЕ выполняет сбор данных - он только:
1. Аутентифицирует агентов
2. Регистрирует подключённые агенты
3. Пересылает команды от веб-интерфейса к агентам
4. Возвращает ответы от агентов обратно к веб-интерфейсу

Вся логика сбора данных (SystemCollector, ScreenCollector, etc.)
выполняется на стороне агента через ws_agent.py и AgentOrchestrator.

РЕСТРУКТУРИЗАЦИЯ: Код разделён на модули для улучшения читаемости и поддержки.
Архивный legacy runtime-path удалён из активного дерева; источник истины по структуре
и потокам теперь в CODEMAP/документации рядом с кодом.
"""

import sys
from aiohttp import web
from loguru import logger
from pathlib import Path

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from tech.log_buffer import capture_loguru_message

# Import configuration and core modules
from config import (
    SERVER_HOST,
    SERVER_PORT,
    SERVER_DATA_ROOT,
    UPLOAD_DIR,
    LOG_LEVEL,
    LOG_FORMAT,
    DATABASE_URL,
    ENABLE_DB_PERSISTENCE,
    ENDPOINT_DIAGNOSTIC_EXECUTION_MODE,
    ENDPOINT_MODULE_EXECUTION_MODE,
    ENDPOINT_MODULE_PORT_MODE,
    ENDPOINT_OPERATION_RECONCILE_BATCH_SIZE,
    ENDPOINT_OPERATION_RECONCILE_INTERVAL_SECONDS,
    ENDPOINT_PORT_MODE,
    is_strict_runtime_mode,
    validate_security_config,
)
# Этап 7.2: очистка истёкших артефактов
ARTIFACTS_CLEANUP_INTERVAL_SEC = 3600  # 1 час
from state_manager import StateManager
from app_keys import OBSERVER_REFRESH_RUNTIME_APP_KEY, STATE_APP_KEY, OUTBOX_SENDER_APP_KEY, bind_app_value
from routes import setup_routes

# Import database initialization
from app.db import get_session, init_db, shutdown_db
from app.db.engine import get_session_maker
from app.repos.operations_repo import OperationsRepo
from websocket.ui_publisher import UiPublisherImpl

# Phase C: Import device outbox sender
from websocket.device_outbox_sender import DeviceOutboxSender, recover_pending_commands

# PR#7: Import operation watchdog
from app.services.operation_watchdog import get_watchdog

# Phase G2: Import asyncio and datetime for housekeeping
import asyncio
from datetime import datetime, timezone, timedelta


def _configure_utf8_stdio() -> None:
    """Force UTF-8 for console streams to avoid mojibake on Windows."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


async def housekeeping_cleanup_task(app: web.Application):
    """
    Phase G2: Периодический cleanup runtime cache.
    
    Выполняется каждые 10 минут:
    - Очищает неактивные сессии (last_activity_at > 30 мин)
    - Ограничивает размер ticket_seen_message_ids (max 10k IDs per ticket)
    """
    state: StateManager = app['state']
    logger.info("[HOUSEKEEPING] Cleanup task started")
    
    while True:
        try:
            await asyncio.sleep(600)  # Каждые 10 минут
            
            current_time = datetime.now(timezone.utc)
            
            # Cleanup inactive sessions (last_activity_at > 30 мин)
            inactive_threshold = current_time - timedelta(minutes=30)
            sessions_to_remove = []
            
            for ticket_id, session in state.sessions_by_ticket.items():
                # Проверяем last_activity_at
                if hasattr(session, 'last_activity_at') and session.last_activity_at:
                    # Если last_activity_at - строка, преобразуем в datetime
                    if isinstance(session.last_activity_at, str):
                        from dateutil import parser
                        last_activity = parser.isoparse(session.last_activity_at)
                    else:
                        last_activity = session.last_activity_at
                    
                    # Убедимся, что last_activity timezone-aware
                    if last_activity.tzinfo is None:
                        last_activity = last_activity.replace(tzinfo=timezone.utc)
                    
                    if last_activity < inactive_threshold:
                        sessions_to_remove.append(ticket_id)
            
            # Удаляем неактивные сессии
            for ticket_id in sessions_to_remove:
                session = state.sessions_by_ticket[ticket_id]
                if session.session_id in state.sessions_by_id:
                    del state.sessions_by_id[session.session_id]
                del state.sessions_by_ticket[ticket_id]
                logger.debug(f"[HOUSEKEEPING] Cleaned up inactive session: ticket_id={ticket_id}")
            
            if sessions_to_remove:
                logger.info(f"[HOUSEKEEPING] Cleaned up {len(sessions_to_remove)} inactive sessions")
            
            # Limit ticket_seen_message_ids size (max 10k IDs per ticket)
            max_ids_per_ticket = 10000
            trimmed_count = 0
            
            for ticket_id, seen_ids in list(state.ticket_seen_message_ids.items()):
                if len(seen_ids) > max_ids_per_ticket:
                    # Keep only last N IDs (FIFO)
                    state.ticket_seen_message_ids[ticket_id] = set(list(seen_ids)[-max_ids_per_ticket:])
                    trimmed_count += 1
                    logger.debug(f"[HOUSEKEEPING] Trimmed ticket_seen_message_ids: ticket_id={ticket_id}")
            
            if trimmed_count > 0:
                logger.info(f"[HOUSEKEEPING] Trimmed {trimmed_count} ticket_seen_message_ids caches")

            # Repair device_outbox: status='sent' без соответствующей операции → failed (ORPHAN_SENT)
            try:
                from app.db import get_session
                from app.repos.device_outbox_repo import DeviceOutboxRepo
                async with get_session() as session:
                    repo = DeviceOutboxRepo(session)
                    repaired = await repo.repair_sent_without_operation(limit=100)
                    if repaired > 0:
                        await session.commit()
                        logger.info(f"[HOUSEKEEPING] device_outbox repair: {repaired} entries marked ORPHAN_SENT")
            except Exception as outbox_err:
                logger.warning(f"[HOUSEKEEPING] device_outbox repair skipped: {outbox_err}")
        
        except Exception as e:
            logger.error(f"[HOUSEKEEPING] Cleanup error: {e}", exc_info=True)


async def artifacts_expired_cleanup_task(app: web.Application):
    """
    Этап 7.2: периодическое удаление истёкших артефактов (expires_at < NOW())
    и соответствующих файлов на диске.
    """
    try:
        from app.db import get_session
        from app.repos import ArtifactsRepo
    except ImportError:
        logger.warning("[ARTIFACTS_CLEANUP] DB not available, task disabled")
        return
    logger.info("[ARTIFACTS_CLEANUP] Task started")
    while True:
        try:
            await asyncio.sleep(ARTIFACTS_CLEANUP_INTERVAL_SEC)
            async with get_session() as session:
                repo = ArtifactsRepo(session)
                expired = await repo.delete_expired()
                for a in expired:
                    fp = UPLOAD_DIR / a.storage_path
                    if fp.exists():
                        try:
                            fp.unlink()
                            logger.debug(f"[ARTIFACTS_CLEANUP] Deleted file {a.storage_path}")
                        except OSError as e:
                            logger.warning(f"[ARTIFACTS_CLEANUP] Failed to unlink {fp}: {e}")
                await session.commit()
                if expired:
                    logger.info(f"[ARTIFACTS_CLEANUP] Removed {len(expired)} expired artifact(s)")
        except asyncio.CancelledError:
            logger.info("[ARTIFACTS_CLEANUP] Task cancelled")
            break
        except Exception as e:
            logger.error(f"[ARTIFACTS_CLEANUP] Error: {e}", exc_info=True)



def _endpoint_operation_ui_publisher(state: StateManager):
    """Build the post-commit UI publication callback for Endpoint facades."""

    publisher = UiPublisherImpl(state)

    async def publish(operation_id: str) -> None:
        # Called only by EndpointOperationReconciler after its store commit.
        async with get_session() as session:
            operation = await OperationsRepo(session).get_by_operation_id(operation_id)
        if operation is not None:
            await publisher.push_operation_updated(operation)

    return publish


async def start_inventory_refresh_runtime(app: web.Application) -> None:
    """Start the inventory scheduler once per aiohttp application lifecycle."""
    if app.get("inventory_refresh_runtime") is not None:
        logger.warning("Inventory refresh runtime already initialized; skipping duplicate start")
        return

    from inventory.scheduler import InventoryRefreshRuntime

    inventory_refresh_runtime = InventoryRefreshRuntime(state=app["state"])
    await inventory_refresh_runtime.start()
    app["inventory_refresh_runtime"] = inventory_refresh_runtime
    logger.success("Inventory refresh runtime initialized")


async def on_startup(app: web.Application):
    """
    Обработчик события запуска приложения.
    Инициализирует подключение к базе данных.
    """
    validate_security_config()
    if ENABLE_DB_PERSISTENCE:
        try:
            await init_db(DATABASE_URL)
            logger.success("✅ Database initialized successfully")
            
            # Phase C: Recover pending commands from device_outbox
            logger.info("🔄 Recovering pending commands...")
            await recover_pending_commands(app['state'])
            
            # Phase C: Start device outbox sender loop
            logger.info("🚀 Starting device outbox sender...")
            sender = DeviceOutboxSender(app['state'], poll_interval=1.0)
            await sender.start_async()
            bind_app_value(app, key=OUTBOX_SENDER_APP_KEY, legacy_name="outbox_sender", value=sender)
            logger.success("✅ Device outbox sender started")
            
            # PR#7: Start operation watchdog (Этап 5: set_app для advance_after_terminal при timeout)
            logger.info("⏰ Starting operation watchdog...")
            watchdog = get_watchdog()
            watchdog.set_app(app)
            await watchdog.start()
            app['operation_watchdog'] = watchdog
            logger.success("✅ Operation watchdog started")

            # Endpoint diagnostic reconciliation is isolated from the legacy
            # outbox: it exists only for the explicit external/endpoint cutover.
            if (
                ENDPOINT_PORT_MODE == "external"
                and ENDPOINT_DIAGNOSTIC_EXECUTION_MODE == "endpoint"
            ):
                from app.services.endpoint_operation_reconciler import (
                    EndpointOperationReconciler,
                    EndpointOperationReconcilerRunner,
                    SqlAlchemyEndpointOperationReconcileStore,
                )
                from domain_ports.container import DomainPortContainer

                runner = EndpointOperationReconcilerRunner(
                    EndpointOperationReconciler(
                        endpoint_port=DomainPortContainer.from_config().endpoint,
                        store=SqlAlchemyEndpointOperationReconcileStore(get_session_maker()),
                        mode=ENDPOINT_PORT_MODE,
                        diagnostic_execution_mode=ENDPOINT_DIAGNOSTIC_EXECUTION_MODE,
                        owner="helpdesk-endpoint-reconciler",
                        publish_after_commit=_endpoint_operation_ui_publisher(app["state"]),
                    ),
                    interval_seconds=ENDPOINT_OPERATION_RECONCILE_INTERVAL_SECONDS,
                    batch_size=ENDPOINT_OPERATION_RECONCILE_BATCH_SIZE,
                )
                runner.start()
                app["endpoint_operation_reconciler"] = runner
                logger.success("✅ Endpoint operation reconciler started")

            if (
                ENDPOINT_MODULE_PORT_MODE == "external"
                and ENDPOINT_MODULE_EXECUTION_MODE == "endpoint"
            ):
                from app.services.endpoint_module_operation_reconciler import (
                    EndpointModuleOperationReconciler,
                    EndpointModuleOperationReconcilerRunner,
                    SqlAlchemyEndpointModuleOperationReconcileStore,
                )
                from domain_ports.container import DomainPortContainer

                runner = EndpointModuleOperationReconcilerRunner(
                    EndpointModuleOperationReconciler(
                        endpoint_port=DomainPortContainer.from_config().endpoint_modules,
                        store=SqlAlchemyEndpointModuleOperationReconcileStore(get_session_maker()),
                        mode=ENDPOINT_MODULE_PORT_MODE,
                        execution_mode=ENDPOINT_MODULE_EXECUTION_MODE,
                        owner="helpdesk-endpoint-module-reconciler",
                    ),
                    interval_seconds=ENDPOINT_OPERATION_RECONCILE_INTERVAL_SECONDS,
                    batch_size=ENDPOINT_OPERATION_RECONCILE_BATCH_SIZE,
                )
                runner.start()
                app["endpoint_module_operation_reconciler"] = runner
                logger.success("✅ Endpoint module operation reconciler started")
            
            # Этап 2: Ticket SLA Watchdog (breach + reminders)
            from app.services.ticket_sla_watchdog import get_ticket_sla_watchdog
            sla_watchdog = get_ticket_sla_watchdog(state=app['state'])
            await sla_watchdog.start()
            app['ticket_sla_watchdog'] = sla_watchdog
            logger.success("✅ Ticket SLA watchdog started")

            # Stage 3: Ticket Auto-Close Watchdog (Resolved -> Closed после TICKET_AUTO_CLOSE_HOURS)
            from app.services.ticket_auto_close_watchdog import get_ticket_auto_close_watchdog
            auto_close_watchdog = get_ticket_auto_close_watchdog(state=app['state'])
            await auto_close_watchdog.start()
            app['ticket_auto_close_watchdog'] = auto_close_watchdog
            logger.success("✅ Ticket auto-close watchdog started")

            # Этап 6: Playbook Scheduler (deferred runs)
            from app.services.playbook_scheduler import get_playbook_scheduler
            pb_scheduler = get_playbook_scheduler()
            pb_scheduler.set_app(app)
            await pb_scheduler.start()
            app['playbook_scheduler'] = pb_scheduler
            logger.success("✅ Playbook scheduler started")

            from app.services.quality_snapshot_scheduler import get_quality_snapshot_scheduler
            quality_snapshot_scheduler = get_quality_snapshot_scheduler()
            await quality_snapshot_scheduler.start()
            app['quality_snapshot_scheduler'] = quality_snapshot_scheduler
            logger.success("✅ Quality snapshot scheduler started")

            from app.services.problem_candidate_scheduler import get_problem_candidate_scheduler
            problem_candidate_scheduler = get_problem_candidate_scheduler()
            await problem_candidate_scheduler.start()
            app['problem_candidate_scheduler'] = problem_candidate_scheduler
            logger.success("✅ Problem candidate scheduler initialized")

            # Reconcile scheduler: периодически сверяет desired vs actual state модулей
            from app.services.module_reconcile_scheduler import start_reconcile_scheduler
            app['reconcile_task'] = asyncio.create_task(
                start_reconcile_scheduler(app['state'])
            )
            logger.success("✅ Module reconcile scheduler started")

            from observer.runtime import ObserverRefreshRuntime

            observer_refresh_runtime = ObserverRefreshRuntime()
            await observer_refresh_runtime.start()
            bind_app_value(
                app,
                key=OBSERVER_REFRESH_RUNTIME_APP_KEY,
                legacy_name="observer_refresh_runtime",
                value=observer_refresh_runtime,
            )
            await start_inventory_refresh_runtime(app)
            logger.success("✅ Observer refresh runtime started")

            from observer.runtime_snapshot_writer import ServerRuntimeSnapshotWriter

            runtime_snapshot_writer = ServerRuntimeSnapshotWriter(app)
            await runtime_snapshot_writer.start()
            app["runtime_snapshot_writer"] = runtime_snapshot_writer
            logger.success("✅ Server runtime snapshot writer started")

        except Exception as e:
            logger.error(f"❌ Failed to initialize database: {e}")
            if is_strict_runtime_mode():
                raise
            logger.warning("⚠️  Server will run WITHOUT database persistence (in-memory only)")
            # Don't crash the server - continue without DB
    else:
        logger.info("ℹ️  Database persistence disabled (ENABLE_DB_PERSISTENCE=false)")
        logger.warning("⚠️  Phase C device outbox will NOT work without database")
    
    # Phase G2: Start housekeeping cleanup task
    logger.info("🧹 Starting housekeeping cleanup task...")
    app['housekeeping_task'] = asyncio.create_task(housekeeping_cleanup_task(app))
    logger.success("✅ Housekeeping cleanup task started")

    # Этап 7.2: фоновая очистка истёкших артефактов
    if ENABLE_DB_PERSISTENCE:
        logger.info("🧹 Starting artifacts expired cleanup task...")
        app['artifacts_cleanup_task'] = asyncio.create_task(artifacts_expired_cleanup_task(app))
        logger.success("✅ Artifacts cleanup task started")


async def on_cleanup(app: web.Application):
    """
    Обработчик события остановки приложения.
    Закрывает подключение к базе данных.
    """
    if 'runtime_snapshot_writer' in app:
        logger.info("⏹️ Stopping server runtime snapshot writer...")
        await app['runtime_snapshot_writer'].stop()
        logger.success("✅ Server runtime snapshot writer stopped")

    # Этап 7.2: Stop artifacts cleanup task
    if 'artifacts_cleanup_task' in app:
        logger.info("⏹️ Stopping artifacts cleanup task...")
        app['artifacts_cleanup_task'].cancel()
        try:
            await app['artifacts_cleanup_task']
        except asyncio.CancelledError:
            pass
        logger.success("✅ Artifacts cleanup task stopped")

    # Phase G2: Stop housekeeping cleanup task
    if 'housekeeping_task' in app:
        logger.info("⏹️ Stopping housekeeping cleanup task...")
        app['housekeeping_task'].cancel()
        try:
            await app['housekeeping_task']
        except asyncio.CancelledError:
            pass
        logger.success("✅ Housekeeping cleanup task stopped")
    
    # PR#7: Stop operation watchdog
    if "endpoint_operation_reconciler" in app:
        logger.info("⏹️ Stopping Endpoint operation reconciler...")
        await app["endpoint_operation_reconciler"].stop()
        logger.success("✅ Endpoint operation reconciler stopped")

    if "endpoint_module_operation_reconciler" in app:
        logger.info("⏹️ Stopping Endpoint module operation reconciler...")
        await app["endpoint_module_operation_reconciler"].stop()
        logger.success("✅ Endpoint module operation reconciler stopped")

    if 'operation_watchdog' in app:
        logger.info("⏹️ Stopping operation watchdog...")
        await app['operation_watchdog'].stop()
        logger.success("✅ Operation watchdog stopped")
    
    # Этап 2: Stop ticket SLA watchdog
    if 'ticket_sla_watchdog' in app:
        logger.info("⏹️ Stopping ticket SLA watchdog...")
        await app['ticket_sla_watchdog'].stop()
        logger.success("✅ Ticket SLA watchdog stopped")

    # Stage 3: Stop ticket auto-close watchdog
    if 'ticket_auto_close_watchdog' in app:
        logger.info("⏹️ Stopping ticket auto-close watchdog...")
        await app['ticket_auto_close_watchdog'].stop()
        logger.success("✅ Ticket auto-close watchdog stopped")

    # Этап 6: Stop playbook scheduler
    if 'playbook_scheduler' in app:
        logger.info("⏹️ Stopping playbook scheduler...")
        await app['playbook_scheduler'].stop()
        logger.success("✅ Playbook scheduler stopped")

    if 'quality_snapshot_scheduler' in app:
        logger.info("⏹️ Stopping quality snapshot scheduler...")
        await app['quality_snapshot_scheduler'].stop()
        logger.success("✅ Quality snapshot scheduler stopped")

    if 'problem_candidate_scheduler' in app:
        logger.info("⏹️ Stopping problem candidate scheduler...")
        await app['problem_candidate_scheduler'].stop()
        logger.success("✅ Problem candidate scheduler stopped")

    # Stop reconcile scheduler
    if 'reconcile_task' in app:
        app['reconcile_task'].cancel()
        try:
            await app['reconcile_task']
        except Exception:
            pass
    
    observer_refresh_runtime = app._state.get(OBSERVER_REFRESH_RUNTIME_APP_KEY)
    if observer_refresh_runtime is not None:
        logger.info("⏹️ Stopping observer refresh runtime...")
        await observer_refresh_runtime.stop()
        logger.success("✅ Observer refresh runtime stopped")

    if 'inventory_refresh_runtime' in app:
        logger.info("Stopping inventory refresh runtime...")
        await app['inventory_refresh_runtime'].stop()
        logger.success("Inventory refresh runtime stopped")

    # Phase C: Stop device outbox sender
    if 'outbox_sender' in app:
        logger.info("⏹️ Stopping device outbox sender...")
        await app['outbox_sender'].stop_async()
        logger.success("✅ Device outbox sender stopped")
    
    if ENABLE_DB_PERSISTENCE:
        try:
            await shutdown_db()
        except Exception as e:
            logger.error(f"❌ Error during database shutdown: {e}")


def create_app() -> web.Application:
    """
    Создаёт и конфигурирует экземпляр приложения.
    
    Returns:
        Настроенный экземпляр aiohttp.web.Application
    """
    # Создаём приложение
    app = web.Application()
    
    # Инициализируем глобальное состояние
    state = StateManager()
    
    # Сохраняем state в app для доступа из обработчиков
    bind_app_value(app, key=STATE_APP_KEY, legacy_name="state", value=state)
    
    # Регистрируем lifecycle hooks
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    
    # КРИТИЧНО: Регистрируем request/auth middleware ПЕРЕД маршрутами
    from auth.middleware import auth_middleware, request_id_middleware
    app.middlewares.append(request_id_middleware)
    app.middlewares.append(auth_middleware)
    
    # Регистрируем маршруты
    setup_routes(app)
    
    # Артефакты (скриншоты, видео) — только через защищённый GET /api/artifacts/{id}/download.
    # Публичная раздача /uploads/ отключена (этап 1 плана скриншот/запись экрана).
    # app.router.add_static('/uploads/', path=UPLOAD_DIR, name='uploads')
    
    return app


def main():
    """Главная точка входа приложения."""
    _configure_utf8_stdio()
    # Настраиваем логирование
    logger.remove()  # Удаляем стандартный обработчик
    logger.add(
        sys.stderr,
        level=LOG_LEVEL,
        format=LOG_FORMAT
    )
    logger.add(capture_loguru_message, level="WARNING")
    
    logger.info(f"📁 Server data root: {SERVER_DATA_ROOT.absolute()}")
    # Создаём папку для загрузок, если её нет
    logger.info(f"📁 Папка загрузок: {UPLOAD_DIR.absolute()}")
    
    # Баннер при запуске
    logger.info("=" * 70)
    logger.info("🚀 PC Agent WebSocket Server (Restructured)")
    logger.info(f"📡 WebSocket (Agents): ws://{SERVER_HOST}:{SERVER_PORT}/ws")
    logger.info(f"📡 WebSocket (UI): ws://{SERVER_HOST}:{SERVER_PORT}/ws_ui")
    logger.info(f"🌐 Web Interface: http://{SERVER_HOST}:{SERVER_PORT}/app")
    logger.info(f"🔧 Admin Panel: http://{SERVER_HOST}:{SERVER_PORT}/app/admin")
    logger.info(f"📋 Tickets: http://{SERVER_HOST}:{SERVER_PORT}/app/tickets")
    logger.info(f"🔧 API: http://{SERVER_HOST}:{SERVER_PORT}/api/")
    logger.info(f"📤 File Upload: http://{SERVER_HOST}:{SERVER_PORT}/api/upload")
    logger.info(f"📂 Uploaded Files: http://{SERVER_HOST}:{SERVER_PORT}/uploads/")
    logger.info(f"📚 Protocol Docs: http://{SERVER_HOST}:{SERVER_PORT}/api/protocol")
    logger.info("=" * 70)
    
    if ENABLE_DB_PERSISTENCE:
        logger.info("🗄️  Database: PostgreSQL (async)")
        db_host = DATABASE_URL.split('@')[-1].split('/')[0] if '@' in DATABASE_URL else '127.0.0.1'
        logger.info(f"   Host: {db_host}")
        logger.info("   Features: Job events persistence + UI replay")
    else:
        logger.info("🗄️  Database: DISABLED (in-memory only)")
    
    logger.info("=" * 70)
    
    logger.info("✅ Структура модулей:")
    logger.info("   📦 config.py - Конфигурация")
    logger.info("   📦 models.py - Модели данных")
    logger.info("   📦 utils.py - Утилиты")
    logger.info("   📦 state_manager.py - Управление состоянием")
    logger.info("   📦 routes.py - Регистрация маршрутов")
    logger.info("   📂 auth/ - Аутентификация")
    logger.info("   📂 agents/ - Управление агентами")
    logger.info("   📂 tickets/ - Система тикетов")
    logger.info("   📂 tools/ - Инструменты")
    logger.info("   📂 websocket/ - WebSocket коммуникация")
    logger.info("   📂 uploads/ - Загрузка файлов")
    logger.info("   📂 static_pages/ - HTML страницы")
    logger.info("   📂 api/ - Дополнительные API")
    logger.info("=" * 70)
    
    logger.warning("⚠️  ВНИМАНИЕ: Некоторые модули содержат упрощенные реализации.")
    logger.warning("    Runtime legacy-path уже удалён; ориентируйтесь на CODEMAP и актуальные docs.")
    logger.warning("    Перед release обязателен green baseline: verify_workspace + pytest + CI artifact.")
    logger.info("=" * 70)
    
    # Создаём и запускаем приложение
    app = create_app()
    web.run_app(app, host=SERVER_HOST, port=SERVER_PORT)


if __name__ == '__main__':
    main()
