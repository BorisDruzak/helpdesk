"""
Модуль для управления локальной SQLite базой данных.
Protocol V3: Ticket-first архитектура с улучшенной надежностью.

Изменения V3:
- PRAGMA user_version для миграций
- outbox с ticket_id (обязательно), agent_seq per-ticket
- ACK → DELETE из outbox (без статуса 'sent')
- Таблицы: seq_ticket, rpc_idempotency_cache, ticket_state, scheduled_tasks
- outbox_sent_history для диагностики
"""

import os
import time
import json
import uuid
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

import aiosqlite
from loguru import logger

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ВЕРСИОНИРОВАНИЕ (замечание 1.1)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DB_SCHEMA_VERSION = 9  # v9: controlled retry metadata for seen_commands
PROTOCOL_VERSION = "ws_ticket_v3"  # Версия протокола WebSocket

# Лимиты (замечание 8.2)
MAX_OUTBOX_ITEM_SIZE = 262144  # 256KB
MAX_EVENT_PAYLOAD_SIZE = 1048576  # 1MB
MAX_ATTACHMENT_SIZE = 104857600  # 100MB
CHUNK_SIZE = 65536  # 64KB

# Канонические NACK error codes (замечание 7)
NACK_ERROR_CODES = {
    "VALIDATION_ERROR": {"retryable": False, "description": "Invalid payload structure"},
    "UNAUTHORIZED": {"retryable": False, "description": "Authentication failed"},
    "FORBIDDEN": {"retryable": False, "description": "Permission denied"},
    "SCHEMA_MISMATCH": {"retryable": False, "description": "Protocol version mismatch"},
    "PAYLOAD_TOO_LARGE": {"retryable": False, "description": "Payload exceeds size limit"},
    "RATE_LIMITED": {"retryable": True, "description": "Too many requests"},
    "TRANSIENT_STORAGE": {"retryable": True, "description": "Temporary storage error"},
    "POSTGRES_UNAVAILABLE": {"retryable": True, "description": "Database temporarily unavailable"},
    "INTERNAL_ERROR": {"retryable": True, "description": "Internal server error"},
}


def _get_default_db_path() -> str:
    """Путь по умолчанию (используется только если db_path не передан явно). Рекомендуется передавать db_path из точки входа (runtime_paths.resolve_storage_db_path(data_root))."""
    return "data/storage.db"


class DatabaseManager:
    """
    Менеджер базы данных Protocol V3.
    
    Ключевые изменения:
    - ticket_id обязателен в outbox
    - agent_seq per-ticket (не per-job)
    - ACK → DELETE (без статуса 'sent')
    - PRAGMA user_version для миграций
    """
    
    _instance: Optional['DatabaseManager'] = None
    _db_path: Path
    _initialized: bool = False
    
    def __new__(cls, db_path: Optional[str] = None):
        """Singleton pattern. Путь к БД задаётся только при первом создании (из точки входа с data_root)."""
        if cls._instance is None:
            if db_path is None:
                db_path = _get_default_db_path()
            
            cls._instance = super(DatabaseManager, cls).__new__(cls)
            cls._instance._db_path = Path(db_path)
            cls._instance._initialized = False
            logger.info(f"DatabaseManager создан с путем к БД: {db_path}")
            # Обновляем глобальный db_manager в этом модуле (для "from pc_agent.core.database import db_manager"),
            # чтобы использовался путь из точки входа, а не дефолт при импорте.
            import sys
            mod = sys.modules.get(cls.__module__)
            if mod is not None:
                setattr(mod, "db_manager", cls._instance)
        return cls._instance
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ИНИЦИАЛИЗАЦИЯ И МИГРАЦИИ (Фаза 1.1)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def init_db(self) -> None:
        """
        Инициализирует базу данных с поддержкой миграций через PRAGMA user_version.
        
        Критично: Без этого любое изменение схемы требует ручного удаления БД.
        """
        if self._initialized:
            logger.debug("База данных уже инициализирована")
            return
        
        try:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Директория для БД создана/проверена: {self._db_path.parent}")
            
            async with aiosqlite.connect(self._db_path) as db:
                # Получаем текущую версию
                cursor = await db.execute("PRAGMA user_version")
                current_version = (await cursor.fetchone())[0]
                
                if current_version == 0:
                    # Новая БД или legacy без версии
                    # Проверяем, есть ли старые таблицы
                    cursor = await db.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name='outbox'"
                    )
                    has_old_outbox = await cursor.fetchone() is not None
                    
                    if has_old_outbox:
                        # Legacy БД - мигрируем
                        logger.info(f"Обнаружена legacy БД, мигрирую на v{DB_SCHEMA_VERSION}")
                        await self._migrate_from_legacy(db)
                    else:
                        # Новая БД
                        await self._create_schema_v3(db)
                    
                    await db.execute(f"PRAGMA user_version = {DB_SCHEMA_VERSION}")
                    await db.commit()
                    logger.info(f"База данных инициализирована: v{DB_SCHEMA_VERSION}")
                
                elif current_version < DB_SCHEMA_VERSION:
                    # Миграция между версиями
                    logger.info(f"Мигрирую БД с v{current_version} на v{DB_SCHEMA_VERSION}")
                    await self._migrate_schema(db, current_version, DB_SCHEMA_VERSION)
                    await db.execute(f"PRAGMA user_version = {DB_SCHEMA_VERSION}")
                    await db.commit()
                
                elif current_version > DB_SCHEMA_VERSION:
                    raise ValueError(
                        f"Версия БД {current_version} > версия кода {DB_SCHEMA_VERSION}. "
                        "Обновите код агента."
                    )
                else:
                    logger.info(f"База данных актуальна: v{current_version}")
            
            self._initialized = True
            
        except Exception as e:
            logger.error(f"Ошибка инициализации базы данных: {e}")
            raise
    
    async def _create_schema_v3(self, db: aiosqlite.Connection) -> None:
        """Создает схему V3 с нуля."""
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # ТАБЛИЦА outbox (Фаза 1.2) - Reliable Event Store
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        await db.execute("""
            CREATE TABLE outbox (
                outbox_id INTEGER PRIMARY KEY AUTOINCREMENT,
                
                -- Context (ОБЯЗАТЕЛЬНО)
                ticket_id TEXT NOT NULL,
                job_id TEXT,
                
                -- Event identity (генерируется в 2 шага)
                event_id TEXT UNIQUE,
                kind TEXT NOT NULL,
                
                -- Event data
                payload_json TEXT NOT NULL,
                actor_role TEXT NOT NULL,
                
                -- Timestamps
                created_at REAL NOT NULL,
                
                -- Sequence (per-ticket для ticket events, per-device для device events)
                agent_seq INTEGER,  -- NULL для device events
                device_seq INTEGER, -- NULL для ticket events
                
                -- Batch support (замечание 4)
                batch_seq INTEGER NOT NULL DEFAULT 0,
                
                -- Delivery state (NO 'sent' - ACK → DELETE)
                status TEXT NOT NULL DEFAULT 'pending',
                lease_until REAL,
                attempts INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                
                -- Trace correlation (замечание 10)
                trace_id TEXT,
                span_id TEXT,
                
                CHECK (status IN ('pending', 'inflight', 'failed'))
            )
        """)
        
        await db.execute("CREATE INDEX idx_outbox_status ON outbox(status)")
        await db.execute("CREATE INDEX idx_outbox_ticket ON outbox(ticket_id, agent_seq)")
        await db.execute("CREATE INDEX idx_outbox_device_seq ON outbox(device_seq) WHERE device_seq IS NOT NULL")
        await db.execute("CREATE INDEX idx_outbox_lease ON outbox(lease_until) WHERE status = 'inflight'")
        await db.execute("CREATE INDEX idx_outbox_event_id ON outbox(event_id) WHERE event_id IS NOT NULL")
        await db.execute("CREATE INDEX idx_outbox_created ON outbox(created_at)")
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # ТАБЛИЦА seq_ticket (Фаза 1.3) - Атомарная генерация agent_seq
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        await db.execute("""
            CREATE TABLE seq_ticket (
                ticket_id TEXT PRIMARY KEY,
                last_seq INTEGER NOT NULL DEFAULT 0
            )
        """)
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # ТАБЛИЦА seq_device (Protocol V3) - Атомарная генерация device_seq
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        await db.execute("""
            CREATE TABLE seq_device (
                device_id TEXT PRIMARY KEY,
                next_seq INTEGER NOT NULL DEFAULT 0
            )
        """)
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # ТАБЛИЦА seen_commands (Protocol V3) - Идемпотентность команд
        # КРИТИЧНО: command_id = request_id (Protocol V3)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        await db.execute("""
            CREATE TABLE seen_commands (
                command_id TEXT PRIMARY KEY,  -- request_id из envelope
                status TEXT NOT NULL,  -- 'success' | 'error' | 'in_progress'
                result_json TEXT,      -- JSON payload (status + data), не весь tool_response
                completed_at INTEGER NOT NULL,
                started_at INTEGER,      -- Для статуса in_progress
                stale_retry_count INTEGER NOT NULL DEFAULT 0,
                owner_instance_id TEXT
            )
        """)
        
        await db.execute("CREATE INDEX idx_seen_commands_completed_at ON seen_commands(completed_at)")
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # ТАБЛИЦА pending_consents (Protocol V3) - Persistent consent tracking
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        await db.execute("""
            CREATE TABLE pending_consents (
                operation_id TEXT PRIMARY KEY,
                device_id TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                requested_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                payload_hash TEXT,
                params_json TEXT,  -- JSON serialized params
                request_id TEXT,   -- Original request_id
                session_key TEXT,  -- Session key for consent cache
                actor_role TEXT NOT NULL,
                ticket_id TEXT,
                job_id TEXT
            )
        """)
        
        await db.execute("CREATE INDEX idx_pending_consents_expires_at ON pending_consents(expires_at)")
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # ТАБЛИЦА rpc_idempotency_cache (Фаза 1.5)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        await db.execute("""
            CREATE TABLE rpc_idempotency_cache (
                idempotency_key TEXT PRIMARY KEY,
                method TEXT NOT NULL,
                ticket_id TEXT,
                response_json TEXT NOT NULL,
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL
            )
        """)
        
        await db.execute(
            "CREATE INDEX idx_rpc_idempotency_expires ON rpc_idempotency_cache(expires_at)"
        )
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # ТАБЛИЦА ticket_state (Фаза 1.5) - Ticket runtime state
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        await db.execute("""
            CREATE TABLE ticket_state (
                ticket_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                category TEXT NOT NULL,
                title TEXT,
                priority TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                metadata_json TEXT
            )
        """)
        
        await db.execute("CREATE INDEX idx_ticket_state_status ON ticket_state(status)")
        await db.execute("CREATE INDEX idx_ticket_state_category ON ticket_state(category)")
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # ТАБЛИЦА scheduled_tasks (Фаза 1.5, замечания п.2-3)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        await db.execute("""
            CREATE TABLE scheduled_tasks (
                task_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                schedule TEXT NOT NULL,
                params_json TEXT,
                enabled INTEGER NOT NULL DEFAULT 1,
                last_run_at REAL,
                next_run_at REAL,
                created_at REAL NOT NULL
            )
        """)
        
        await db.execute(
            "CREATE INDEX idx_tasks_next_run ON scheduled_tasks(next_run_at) WHERE enabled = 1"
        )
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # ТАБЛИЦА outbox_sent_history (Фаза 1.7) - Диагностика
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        await db.execute("""
            CREATE TABLE outbox_sent_history (
                outbox_id INTEGER PRIMARY KEY,
                ticket_id TEXT NOT NULL,
                event_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                created_at REAL NOT NULL,
                sent_at REAL NOT NULL,
                payload_preview TEXT
            )
        """)
        
        await db.execute("CREATE INDEX idx_sent_history_ticket ON outbox_sent_history(ticket_id)")
        await db.execute("CREATE INDEX idx_sent_history_sent_at ON outbox_sent_history(sent_at)")
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # ТАБЛИЦА jobs (legacy support + обновления)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        await db.execute("""
            CREATE TABLE jobs (
                job_id TEXT PRIMARY KEY,
                job_type TEXT NOT NULL,
                status TEXT NOT NULL,
                progress REAL DEFAULT 0,
                created_at REAL NOT NULL,
                started_at REAL,
                updated_at REAL,
                finished_at REAL,
                last_error TEXT,
                meta_json TEXT,
                ticket_id TEXT
            )
        """)
        
        await db.execute("CREATE INDEX idx_jobs_status ON jobs(status)")
        await db.execute("CREATE INDEX idx_jobs_created_at ON jobs(created_at)")
        await db.execute("CREATE INDEX idx_jobs_ticket ON jobs(ticket_id)")
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # ТАБЛИЦА tool_jobs (legacy support)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        await db.execute("""
            CREATE TABLE tool_jobs (
                job_id TEXT PRIMARY KEY,
                request_id TEXT,
                device_id TEXT,
                command TEXT NOT NULL,
                actor_role TEXT,
                status TEXT NOT NULL,
                created_at REAL NOT NULL,
                started_at REAL,
                finished_at REAL,
                meta_json TEXT,
                error_json TEXT
            )
        """)
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # ТАБЛИЦА seen_messages (persistent dedup)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        await db.execute("""
            CREATE TABLE seen_messages (
                job_id TEXT NOT NULL,
                message_id TEXT NOT NULL,
                seen_at REAL NOT NULL,
                PRIMARY KEY (job_id, message_id)
            )
        """)
        
        await db.execute("CREATE INDEX idx_seen_messages_seen_at ON seen_messages(seen_at)")
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # ТАБЛИЦА outbox_attachments (Фаза 8.3)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        await db.execute("""
            CREATE TABLE outbox_attachments (
                outbox_id INTEGER PRIMARY KEY,
                artifact_id TEXT NOT NULL,
                artifact_local_path TEXT NOT NULL,
                artifact_mime TEXT NOT NULL,
                artifact_size INTEGER NOT NULL,
                artifact_sha256 TEXT NOT NULL,
                upload_status TEXT NOT NULL DEFAULT 'pending',
                upload_url TEXT,
                upload_error TEXT
            )
        """)
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # ТАБЛИЦА unknown_message_tracking (замечание 6)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        await db.execute("""
            CREATE TABLE unknown_message_tracking (
                session_id TEXT PRIMARY KEY,
                count INTEGER NOT NULL DEFAULT 0,
                first_seen_at REAL NOT NULL,
                last_seen_at REAL NOT NULL
            )
        """)
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # ТАБЛИЦА auth_tokens (v8) - Хранение токена авторизации агента
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        await db.execute("""
            CREATE TABLE auth_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT NOT NULL UNIQUE,
                device_id TEXT NOT NULL,
                created_at REAL NOT NULL,
                last_used_at REAL,
                is_active INTEGER NOT NULL DEFAULT 1
            )
        """)
        
        await db.execute("CREATE INDEX idx_auth_tokens_device_id ON auth_tokens(device_id)")
        await db.execute("CREATE INDEX idx_auth_tokens_active ON auth_tokens(device_id, is_active) WHERE is_active = 1")
        
        logger.info(f"Создана схема БД v{DB_SCHEMA_VERSION}")
    
    async def _migrate_from_legacy(self, db: aiosqlite.Connection) -> None:
        """Миграция с legacy схемы на V3."""
        logger.info("Начинаю миграцию с legacy схемы...")
        
        # 1. Переименовываем старую outbox
        await db.execute("ALTER TABLE outbox RENAME TO outbox_legacy")
        
        # 2. Создаем новые таблицы
        await self._create_schema_v3(db)
        
        # 3. Мигрируем данные из outbox_legacy в outbox
        # Примечание: устанавливаем ticket_id = job_id для legacy данных
        await db.execute("""
            INSERT INTO outbox (
                ticket_id, job_id, event_id, kind, payload_json, 
                actor_role, created_at, agent_seq, batch_seq,
                status, lease_until, attempts, last_error
            )
            SELECT 
                COALESCE(job_id, 'legacy_' || id) as ticket_id,
                job_id,
                NULL as event_id,
                COALESCE(item_type, 'legacy') as kind,
                payload_json,
                COALESCE(actor_role, 'agent') as actor_role,
                created_at,
                0 as agent_seq,
                0 as batch_seq,
                CASE 
                    WHEN status = 'sent' THEN 'pending'
                    WHEN status IN ('pending', 'inflight', 'failed') THEN status
                    ELSE 'pending'
                END as status,
                lease_until,
                COALESCE(attempts, 0) as attempts,
                last_error
            FROM outbox_legacy
            WHERE status != 'sent'
        """)
        
        # 4. Удаляем legacy таблицу
        await db.execute("DROP TABLE outbox_legacy")
        
        logger.success("Миграция с legacy схемы завершена")
    
    async def _migrate_v3_to_v4(self, db: aiosqlite.Connection) -> None:
        """Миграция v3 → v4: Добавляем seq_device и device_seq."""
        logger.info("Начинаю миграцию v3 → v4...")
        
        # 1. Создаем таблицу seq_device если её нет
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='seq_device'"
        )
        has_seq_device = await cursor.fetchone() is not None
        
        if not has_seq_device:
            await db.execute("""
                CREATE TABLE seq_device (
                    device_id TEXT PRIMARY KEY,
                    next_seq INTEGER NOT NULL DEFAULT 0
                )
            """)
            logger.info("Таблица seq_device создана")
        
        # 2. Добавляем колонку device_seq в outbox если её нет
        cursor = await db.execute("PRAGMA table_info(outbox)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if 'device_seq' not in column_names:
            await db.execute("ALTER TABLE outbox ADD COLUMN device_seq INTEGER")
            logger.info("Колонка device_seq добавлена в outbox")
        
        # 3. Изменяем agent_seq на nullable (не можем прямо изменить NOT NULL в SQLite)
        # SQLite не поддерживает ALTER COLUMN, поэтому agent_seq остается NOT NULL
        # Для существующих записей это нормально (все ticket events уже имеют agent_seq)
        
        # 4. Создаем индекс для device_seq
        try:
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_outbox_device_seq ON outbox(device_seq) WHERE device_seq IS NOT NULL"
            )
            logger.info("Индекс idx_outbox_device_seq создан")
        except Exception as e:
            logger.warning(f"Не удалось создать индекс: {e}")
        
        logger.success("Миграция v3 → v4 завершена")
    
    async def _migrate_v4_to_v5(self, db: aiosqlite.Connection) -> None:
        """Миграция v4 → v5: Добавляем seen_commands для идемпотентности."""
        logger.info("Начинаю миграцию v4 → v5...")
        
        # Проверяем наличие таблицы
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='seen_commands'"
        )
        has_seen_commands = await cursor.fetchone() is not None
        
        if not has_seen_commands:
            await db.execute("""
                CREATE TABLE seen_commands (
                    command_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    result_json TEXT,
                    completed_at INTEGER NOT NULL,
                    started_at INTEGER,
                    stale_retry_count INTEGER NOT NULL DEFAULT 0,
                    owner_instance_id TEXT
                )
            """)
            await db.execute("CREATE INDEX idx_seen_commands_completed_at ON seen_commands(completed_at)")
            logger.info("Таблица seen_commands создана")
        
        logger.success("Миграция v4 → v5 завершена")
    
    async def _migrate_v5_to_v6(self, db: aiosqlite.Connection) -> None:
        """Миграция v5 → v6: Добавляем pending_consents для persistent consent tracking."""
        logger.info("Начинаю миграцию v5 → v6...")
        
        # Проверяем наличие таблицы
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='pending_consents'"
        )
        has_pending_consents = await cursor.fetchone() is not None
        
        if not has_pending_consents:
            await db.execute("""
                CREATE TABLE pending_consents (
                    operation_id TEXT PRIMARY KEY,
                    device_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    requested_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL,
                    payload_hash TEXT,
                    params_json TEXT,
                    request_id TEXT,
                    session_key TEXT,
                    actor_role TEXT NOT NULL,
                    ticket_id TEXT,
                    job_id TEXT
                )
            """)
            await db.execute("CREATE INDEX idx_pending_consents_expires_at ON pending_consents(expires_at)")
            logger.info("Таблица pending_consents создана")
        
        logger.success("Миграция v5 → v6 завершена")
    
    async def _migrate_v7_to_v8(self, db: aiosqlite.Connection) -> None:
        """Миграция v7 → v8: Добавляем auth_tokens для хранения токена авторизации."""
        logger.info("Начинаю миграцию v7 → v8...")
        
        # Проверяем наличие таблицы
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='auth_tokens'"
        )
        has_auth_tokens = await cursor.fetchone() is not None
        
        if not has_auth_tokens:
            await db.execute("""
                CREATE TABLE auth_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    token TEXT NOT NULL UNIQUE,
                    device_id TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    last_used_at REAL,
                    is_active INTEGER NOT NULL DEFAULT 1
                )
            """)
            await db.execute("CREATE INDEX idx_auth_tokens_device_id ON auth_tokens(device_id)")
            await db.execute("CREATE INDEX idx_auth_tokens_active ON auth_tokens(device_id, is_active) WHERE is_active = 1")
            logger.info("Таблица auth_tokens создана")
        
        logger.success("Миграция v7 → v8 завершена")

    async def _migrate_v8_to_v9(self, db: aiosqlite.Connection) -> None:
        """Миграция v8 → v9: Добавляем controlled retry metadata в seen_commands."""
        logger.info("Начинаю миграцию v8 → v9...")

        cursor = await db.execute("PRAGMA table_info(seen_commands)")
        columns = await cursor.fetchall()
        column_names = {col[1] for col in columns}

        if "stale_retry_count" not in column_names:
            await db.execute(
                "ALTER TABLE seen_commands ADD COLUMN stale_retry_count INTEGER NOT NULL DEFAULT 0"
            )
            logger.info("Колонка stale_retry_count добавлена в seen_commands")

        if "owner_instance_id" not in column_names:
            await db.execute("ALTER TABLE seen_commands ADD COLUMN owner_instance_id TEXT")
            logger.info("Колонка owner_instance_id добавлена в seen_commands")

        logger.success("Миграция v8 → v9 завершена")
    
    async def _migrate_schema(
        self, 
        db: aiosqlite.Connection, 
        from_version: int, 
        to_version: int
    ) -> None:
        """Инкрементальная миграция между версиями."""
        logger.info(f"Миграция схемы: v{from_version} → v{to_version}")
        
        # V1/V2 → V3
        if from_version < 3 and to_version >= 3:
            await self._migrate_from_legacy(db)
        
        # V3 → V4: Добавляем seq_device и device_seq
        if from_version < 4 and to_version >= 4:
            await self._migrate_v3_to_v4(db)
        
        # V4 → V5: Добавляем seen_commands для идемпотентности
        if from_version < 5 and to_version >= 5:
            await self._migrate_v4_to_v5(db)
        
        # V5 → V6: Добавляем pending_consents для persistent consent tracking
        if from_version < 6 and to_version >= 6:
            await self._migrate_v5_to_v6(db)
        
        # V7 → V8: Добавляем auth_tokens для хранения токена авторизации
        if from_version < 8 and to_version >= 8:
            await self._migrate_v7_to_v8(db)

        # V8 → V9: controlled retry metadata в seen_commands
        if from_version < 9 and to_version >= 9:
            await self._migrate_v8_to_v9(db)
        
        logger.success(f"Миграция на v{to_version} завершена")
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ТРАНЗАКЦИОННЫЙ enqueue_event (замечание 1 - один connection, один BEGIN IMMEDIATE)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def enqueue_event(
        self,
        device_id: str,
        kind: str,
        payload: dict,
        actor_role: str,
        ticket_id: Optional[str] = None,
        job_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        span_id: Optional[str] = None,
        batch_seq: int = 0
    ) -> int:
        """
        Добавляет событие в outbox атомарно в одной транзакции.
        
        Protocol V3: Поддержка device events (без ticket_id).
        Для device events используется device_id как ticket_id для совместимости.
        
        Замечание 1: Все операции в одном connection и одном BEGIN IMMEDIATE:
        1. INSERT OR IGNORE seq_ticket (или seq_device)
        2. UPDATE seq_ticket SET last_seq = last_seq + 1
        3. SELECT last_seq (получаем agent_seq или device_seq)
        4. INSERT outbox ... agent_seq=last_seq ... event_id=NULL
        5. UPDATE outbox SET event_id=...
        6. COMMIT
        
        Замечание 11: При превышении лимита payload создается событие ошибки.
        
        Args:
            device_id: UUID устройства (ОБЯЗАТЕЛЬНО)
            kind: Тип события ('message', 'tool_started', etc)
            payload: Данные события
            actor_role: Роль актора ('user', 'agent', 'support', 'system')
            ticket_id: UUID тикета (ОПЦИОНАЛЬНО - для ticket events)
            job_id: UUID job (опционально)
            trace_id: ID трассировки (опционально)
            span_id: ID span (опционально)
            batch_seq: Позиция в batch (по умолчанию 0)
            
        Returns:
            outbox_id созданной записи
            
        Raises:
            ValueError: При невалидных UUID или превышении лимитов
        """
        # Protocol V3: Если ticket_id не указан, это device event
        # Используем device_id как ticket_id для совместимости со схемой БД
        effective_ticket_id = ticket_id if ticket_id else device_id
        is_device_event = ticket_id is None
        
        # Валидация UUID (замечание 1.7)
        try:
            uuid.UUID(device_id)
            if ticket_id:
                uuid.UUID(ticket_id)
            if job_id:
                uuid.UUID(job_id)
        except ValueError as e:
            raise ValueError(f"Invalid UUID format: {e}")
        
        # Валидация размера payload (замечание 11)
        payload_json = json.dumps(payload, ensure_ascii=False)
        payload_size = len(payload_json.encode('utf-8'))
        
        if payload_size > MAX_EVENT_PAYLOAD_SIZE:
            # Создаем событие ошибки вместо падения
            logger.error(
                f"Payload too large: {payload_size} bytes (max {MAX_EVENT_PAYLOAD_SIZE}). "
                f"Creating payload_rejected event instead."
            )
            error_payload = {
                "error": "payload_too_large",
                "original_kind": kind,
                "size": payload_size,
                "max_size": MAX_EVENT_PAYLOAD_SIZE,
                "ts": time.time()
            }
            return await self._enqueue_event_internal(
                ticket_id=ticket_id,
                job_id=job_id,
                kind="payload_rejected",
                payload_json=json.dumps(error_payload, ensure_ascii=False),
                actor_role=actor_role,
                device_id=device_id,
                trace_id=trace_id,
                span_id=span_id,
                batch_seq=batch_seq
            )
        
        return await self._enqueue_event_internal(
            ticket_id=effective_ticket_id,
            job_id=job_id,
            kind=kind,
            payload_json=payload_json,
            actor_role=actor_role,
            device_id=device_id,
            trace_id=trace_id,
            span_id=span_id,
            batch_seq=batch_seq,
            is_device_event=is_device_event
        )
    
    async def _enqueue_event_internal(
        self,
        ticket_id: str,
        job_id: Optional[str],
        kind: str,
        payload_json: str,
        actor_role: str,
        device_id: str,
        trace_id: Optional[str],
        span_id: Optional[str],
        batch_seq: int,
        is_device_event: bool = False
    ) -> int:
        """
        Внутренний метод для атомарной вставки события.
        
        Protocol V4: Использует device_seq для device events, agent_seq для ticket events.
        
        Args:
            is_device_event: Если True, используется device_seq
        """
        
        async with aiosqlite.connect(self._db_path, timeout=10.0) as db:
            await db.execute("PRAGMA busy_timeout=10000")
            await db.execute("BEGIN IMMEDIATE")
            
            try:
                # Step 1-3: Атомарно генерируем seq
                if is_device_event:
                    # Для device events используем device_seq
                    await db.execute(
                        "INSERT OR IGNORE INTO seq_device (device_id, next_seq) VALUES (?, 0)",
                        (device_id,)
                    )
                    await db.execute(
                        "UPDATE seq_device SET next_seq = next_seq + 1 WHERE device_id = ?",
                        (device_id,)
                    )
                    cursor = await db.execute(
                        "SELECT next_seq FROM seq_device WHERE device_id = ?",
                        (device_id,)
                    )
                    row = await cursor.fetchone()
                    device_seq = row[0]
                    agent_seq = None
                else:
                    # Для ticket events используем agent_seq
                    await db.execute(
                        "INSERT OR IGNORE INTO seq_ticket (ticket_id, last_seq) VALUES (?, 0)",
                        (ticket_id,)
                    )
                    await db.execute(
                        "UPDATE seq_ticket SET last_seq = last_seq + 1 WHERE ticket_id = ?",
                        (ticket_id,)
                    )
                    cursor = await db.execute(
                        "SELECT last_seq FROM seq_ticket WHERE ticket_id = ?",
                        (ticket_id,)
                    )
                    row = await cursor.fetchone()
                    agent_seq = row[0]
                    device_seq = None
                
                # Step 4: INSERT без event_id
                cursor = await db.execute(
                    """
                    INSERT INTO outbox (
                        ticket_id, job_id, event_id, kind,
                        payload_json, actor_role, created_at,
                        agent_seq, device_seq, batch_seq, status, trace_id, span_id
                    ) VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
                    """,
                    (
                        ticket_id, job_id, kind,
                        payload_json, actor_role,
                        time.time(), agent_seq, device_seq, batch_seq,
                        trace_id, span_id
                    )
                )
                
                outbox_id = cursor.lastrowid
                
                # Step 5: Генерируем event_id и UPDATE
                event_id = self._generate_event_id(
                    device_id=device_id,
                    ticket_id=ticket_id,
                    outbox_id=outbox_id,
                    seq_in_batch=batch_seq
                )
                
                await db.execute(
                    "UPDATE outbox SET event_id = ? WHERE outbox_id = ?",
                    (event_id, outbox_id)
                )
                
                # Step 6: COMMIT
                await db.commit()
                
                # Логирование
                event_type = "device_event" if is_device_event else "ticket_event"
                seq_name = "device_seq" if is_device_event else "agent_seq"
                seq_value = device_seq if is_device_event else agent_seq
                logger.debug(
                    f"Enqueued {event_type}: outbox_id={outbox_id}, "
                    f"event_id={event_id}, kind={kind}, {seq_name}={seq_value}"
                )
                
                return outbox_id
                
            except Exception:
                await db.rollback()
                raise
    
    def _generate_event_id(
        self,
        device_id: str,
        ticket_id: str,
        outbox_id: int,
        seq_in_batch: int
    ) -> str:
        """
        Генерирует детерминированный event_id.
        
        Format: {device_id}:{ticket_id}:{outbox_id}:{seq_in_batch}
        """
        return f"{device_id}:{ticket_id}:{outbox_id}:{seq_in_batch}"
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # CLAIM/LEASE (замечание 2 - атомарный select+mark inflight)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def claim_outbox_batch(
        self,
        limit: int,
        lease_sec: int,
        now: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Атомарно резервирует batch записей из outbox для отправки.
        
        Замечание 2: Делает выборку pending + expired inflight и в той же
        транзакции переводит в inflight, увеличивает attempts, ставит lease_until.
        
        Args:
            limit: Максимальное количество записей
            lease_sec: Время аренды в секундах
            now: Текущее время (для тестов)
            
        Returns:
            Список зарезервированных записей
        """
        if now is None:
            now = time.time()
        
        lease_until = now + lease_sec
        
        async with aiosqlite.connect(self._db_path, timeout=10.0) as db:
            db.row_factory = aiosqlite.Row
            await db.execute("PRAGMA busy_timeout=10000")
            await db.execute("BEGIN IMMEDIATE")
            
            try:
                # Атомарный UPDATE + SELECT через RETURNING (SQLite 3.35+)
                # Fallback для старых версий: используем подзапрос
                
                # Сначала получаем ID записей для резервирования
                cursor = await db.execute(
                    """
                    SELECT outbox_id
                    FROM outbox
                    WHERE status = 'pending'
                       OR (status = 'inflight' AND lease_until IS NOT NULL AND lease_until < ?)
                    ORDER BY created_at ASC
                    LIMIT ?
                    """,
                    (now, limit)
                )
                rows = await cursor.fetchall()
                
                if not rows:
                    await db.commit()
                    return []
                
                ids_to_claim = [row['outbox_id'] for row in rows]
                placeholders = ','.join('?' * len(ids_to_claim))
                
                # Атомарный UPDATE
                await db.execute(
                    f"""
                    UPDATE outbox
                    SET status = 'inflight',
                        lease_until = ?,
                        attempts = attempts + 1
                    WHERE outbox_id IN ({placeholders})
                    """,
                    (lease_until,) + tuple(ids_to_claim)
                )
                
                # Получаем полные данные
                cursor = await db.execute(
                    f"""
                    SELECT outbox_id, ticket_id, job_id, event_id, kind,
                           payload_json, actor_role, created_at, agent_seq, device_seq,
                           batch_seq, attempts, lease_until, trace_id, span_id
                    FROM outbox
                    WHERE outbox_id IN ({placeholders})
                    ORDER BY created_at ASC
                    """,
                    tuple(ids_to_claim)
                )
                rows = await cursor.fetchall()
                
                await db.commit()
                
                items = []
                for row in rows:
                    try:
                        item = {
                            'id': row['outbox_id'],
                            'outbox_id': row['outbox_id'],
                            'ticket_id': row['ticket_id'],
                            'job_id': row['job_id'],
                            'event_id': row['event_id'],
                            'kind': row['kind'],
                            'payload_json': row['payload_json'],
                            'payload': json.loads(row['payload_json']),
                            'actor_role': row['actor_role'],
                            'created_at': row['created_at'],
                            'agent_seq': row['agent_seq'],
                            'device_seq': row['device_seq'],
                            'batch_seq': row['batch_seq'],
                            'attempts': row['attempts'],
                            'lease_until': row['lease_until'],
                            'trace_id': row['trace_id'],
                            'span_id': row['span_id']
                        }
                        items.append(item)
                    except json.JSONDecodeError as e:
                        logger.error(f"Ошибка десериализации outbox ID={row['outbox_id']}: {e}")
                        continue
                
                if items:
                    logger.debug(f"Claimed {len(items)} outbox items (lease until {lease_until:.2f})")
                
                return items
                
            except Exception:
                await db.rollback()
                raise
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ACK → DELETE + sent_history (замечание 3)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def ack_and_delete_outbox(
        self,
        outbox_ids: List[int],
        trim_history_threshold: int = 1100,
        trim_history_target: int = 1000
    ) -> int:
        """
        Обрабатывает ACK: сохраняет в историю и удаляет из outbox.
        
        Замечание 3: Порядок операций:
        1. Прочитать acked items для истории
        2. Записать в outbox_sent_history
        3. Удалить из outbox
        
        Замечание 3.1: Trimming батчами - только если COUNT > threshold.
        
        Args:
            outbox_ids: Список ID записей для ACK
            trim_history_threshold: Порог для запуска trimming
            trim_history_target: Целевое количество записей после trimming
            
        Returns:
            Количество удаленных записей
        """
        if not outbox_ids:
            return 0
        
        async with aiosqlite.connect(self._db_path, timeout=10.0) as db:
            db.row_factory = aiosqlite.Row
            await db.execute("PRAGMA busy_timeout=10000")
            await db.execute("BEGIN IMMEDIATE")
            
            try:
                placeholders = ','.join('?' * len(outbox_ids))
                sent_at = time.time()
                
                # Step 1: Читаем данные для истории
                cursor = await db.execute(
                    f"""
                    SELECT outbox_id, ticket_id, event_id, kind, 
                           created_at, payload_json
                    FROM outbox
                    WHERE outbox_id IN ({placeholders})
                    """,
                    tuple(outbox_ids)
                )
                items = await cursor.fetchall()
                
                # Step 2: Записываем в историю
                for item in items:
                    payload_preview = (item['payload_json'] or '')[:200]
                    await db.execute(
                        """
                        INSERT OR REPLACE INTO outbox_sent_history (
                            outbox_id, ticket_id, event_id, kind,
                            created_at, sent_at, payload_preview
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            item['outbox_id'], item['ticket_id'],
                            item['event_id'], item['kind'],
                            item['created_at'], sent_at, payload_preview
                        )
                    )
                
                # Step 3: Удаляем из outbox
                cursor = await db.execute(
                    f"DELETE FROM outbox WHERE outbox_id IN ({placeholders})",
                    tuple(outbox_ids)
                )
                deleted_count = cursor.rowcount
                
                # Step 4: Trimming истории (только если превышен порог)
                cursor = await db.execute("SELECT COUNT(*) FROM outbox_sent_history")
                history_count = (await cursor.fetchone())[0]
                
                if history_count > trim_history_threshold:
                    # Удаляем старые записи, оставляя target
                    await db.execute(
                        """
                        DELETE FROM outbox_sent_history
                        WHERE outbox_id NOT IN (
                            SELECT outbox_id FROM outbox_sent_history
                            ORDER BY sent_at DESC
                            LIMIT ?
                        )
                        """,
                        (trim_history_target,)
                    )
                    logger.debug(
                        f"Trimmed sent_history: {history_count} → ~{trim_history_target}"
                    )
                
                await db.commit()
                
                logger.debug(f"ACK: deleted {deleted_count} items from outbox")
                return deleted_count
                
            except Exception:
                await db.rollback()
                raise
    
    async def delete_outbox_items(self, outbox_ids: List[int]) -> int:
        """Алиас для ack_and_delete_outbox (для совместимости)."""
        return await self.ack_and_delete_outbox(outbox_ids)
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # NACK HANDLING
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def mark_outbox_failed(
        self,
        outbox_ids: List[int],
        reason: Optional[str] = None
    ) -> int:
        """Помечает записи как failed (non-retryable NACK)."""
        if not outbox_ids:
            return 0
        
        placeholders = ','.join('?' * len(outbox_ids))
        
        async with aiosqlite.connect(self._db_path, timeout=10.0) as db:
            await db.execute("PRAGMA busy_timeout=10000")
            cursor = await db.execute(
                f"""
                UPDATE outbox
                SET status = 'failed',
                    last_error = ?,
                    lease_until = NULL
                WHERE outbox_id IN ({placeholders})
                """,
                (reason,) + tuple(outbox_ids)
            )
            await db.commit()
            updated = cursor.rowcount
        
        if updated:
            logger.debug(f"Marked {updated} items as failed: {reason}")
        return updated
    
    async def update_outbox_lease(
        self,
        outbox_ids: List[int],
        new_lease: float
    ) -> int:
        """Обновляет lease_until для retryable NACK."""
        if not outbox_ids:
            return 0
        
        placeholders = ','.join('?' * len(outbox_ids))
        
        async with aiosqlite.connect(self._db_path, timeout=10.0) as db:
            await db.execute("PRAGMA busy_timeout=10000")
            cursor = await db.execute(
                f"""
                UPDATE outbox
                SET lease_until = ?,
                    status = 'pending'
                WHERE outbox_id IN ({placeholders})
                """,
                (new_lease,) + tuple(outbox_ids)
            )
            await db.commit()
            updated = cursor.rowcount
        
        logger.debug(f"Updated lease for {updated} items to {new_lease}")
        return updated
    
    async def release_expired_leases(self, now: Optional[float] = None) -> int:
        """Освобождает expired leases (переводит в pending)."""
        if now is None:
            now = time.time()
        
        async with aiosqlite.connect(self._db_path, timeout=10.0) as db:
            await db.execute("PRAGMA busy_timeout=10000")
            cursor = await db.execute(
                """
                UPDATE outbox
                SET status = 'pending', lease_until = NULL
                WHERE status = 'inflight' AND lease_until < ?
                """,
                (now,)
            )
            await db.commit()
            released = cursor.rowcount
        
        if released > 0:
            logger.debug(f"Released {released} expired leases")
        
        return released
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # IDEMPOTENCY CACHE (замечание 5)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def check_idempotency_cache(
        self,
        idempotency_key: str
    ) -> Optional[Dict[str, Any]]:
        """Проверяет кеш идемпотентности."""
        now = time.time()
        
        async with aiosqlite.connect(self._db_path, timeout=5.0) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT response_json FROM rpc_idempotency_cache
                WHERE idempotency_key = ? AND expires_at > ?
                """,
                (idempotency_key, now)
            )
            row = await cursor.fetchone()
        
        if row:
            try:
                return json.loads(row['response_json'])
            except json.JSONDecodeError:
                return None
        
        return None
    
    async def save_idempotency_cache(
        self,
        idempotency_key: str,
        method: str,
        ticket_id: Optional[str],
        response: Dict[str, Any],
        ttl_seconds: int = 3600
    ) -> None:
        """Сохраняет результат в кеш идемпотентности."""
        now = time.time()
        expires_at = now + ttl_seconds
        response_json = json.dumps(response, ensure_ascii=False)
        
        async with aiosqlite.connect(self._db_path, timeout=5.0) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO rpc_idempotency_cache (
                    idempotency_key, method, ticket_id,
                    response_json, created_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (idempotency_key, method, ticket_id, response_json, now, expires_at)
            )
            await db.commit()
        
        logger.debug(f"Saved idempotency cache: {idempotency_key} (TTL={ttl_seconds}s)")
    
    async def cleanup_expired_idempotency_cache(self) -> int:
        """Удаляет expired записи из idempotency cache."""
        now = time.time()
        
        async with aiosqlite.connect(self._db_path, timeout=5.0) as db:
            cursor = await db.execute(
                "DELETE FROM rpc_idempotency_cache WHERE expires_at < ?",
                (now,)
            )
            await db.commit()
            deleted = cursor.rowcount
        
        if deleted > 0:
            logger.info(f"Cleaned up {deleted} expired idempotency cache entries")
        
        return deleted
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # TICKET STATE (замечание 8)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def create_ticket_state(
        self,
        ticket_id: str,
        status: str,
        category: str,
        title: Optional[str] = None,
        priority: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Создает или обновляет состояние тикета."""
        now = time.time()
        metadata_json = json.dumps(metadata, ensure_ascii=False) if metadata else None
        
        async with aiosqlite.connect(self._db_path, timeout=5.0) as db:
            await db.execute(
                """
                INSERT INTO ticket_state (
                    ticket_id, status, category, title, priority,
                    created_at, updated_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticket_id) DO UPDATE SET
                    status = excluded.status,
                    category = excluded.category,
                    title = COALESCE(excluded.title, ticket_state.title),
                    priority = COALESCE(excluded.priority, ticket_state.priority),
                    updated_at = excluded.updated_at,
                    metadata_json = COALESCE(excluded.metadata_json, ticket_state.metadata_json)
                """,
                (ticket_id, status, category, title, priority, now, now, metadata_json)
            )
            await db.commit()
        
        logger.debug(f"Created/updated ticket_state: {ticket_id}, status={status}")
    
    async def get_ticket_state(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        """Получает состояние тикета."""
        async with aiosqlite.connect(self._db_path, timeout=5.0) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT ticket_id, status, category, title, priority,
                       created_at, updated_at, metadata_json
                FROM ticket_state
                WHERE ticket_id = ?
                """,
                (ticket_id,)
            )
            row = await cursor.fetchone()
        
        if not row:
            return None
        
        result = dict(row)
        if result.get('metadata_json'):
            try:
                result['metadata'] = json.loads(result['metadata_json'])
            except json.JSONDecodeError:
                result['metadata'] = None
        else:
            result['metadata'] = None
        
        return result
    
    async def update_ticket_status(self, ticket_id: str, status: str) -> bool:
        """Обновляет статус тикета."""
        now = time.time()
        
        async with aiosqlite.connect(self._db_path, timeout=5.0) as db:
            cursor = await db.execute(
                """
                UPDATE ticket_state
                SET status = ?, updated_at = ?
                WHERE ticket_id = ?
                """,
                (status, now, ticket_id)
            )
            await db.commit()
            return cursor.rowcount > 0
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # UNKNOWN MESSAGE TRACKING (замечание 6)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def track_unknown_message(
        self,
        session_id: str,
        max_per_minute: int = 10
    ) -> bool:
        """
        Отслеживает неизвестные типы сообщений.
        
        Замечание 6: Если за сессию получено N неизвестных типов (10 за минуту),
        возвращает True для закрытия соединения.
        
        Returns:
            True если нужно закрыть соединение
        """
        now = time.time()
        one_minute_ago = now - 60
        
        async with aiosqlite.connect(self._db_path, timeout=5.0) as db:
            db.row_factory = aiosqlite.Row
            
            # Получаем или создаем запись
            cursor = await db.execute(
                """
                SELECT count, first_seen_at FROM unknown_message_tracking
                WHERE session_id = ?
                """,
                (session_id,)
            )
            row = await cursor.fetchone()
            
            if row:
                # Проверяем, истек ли период
                if row['first_seen_at'] < one_minute_ago:
                    # Сбрасываем счетчик
                    await db.execute(
                        """
                        UPDATE unknown_message_tracking
                        SET count = 1, first_seen_at = ?, last_seen_at = ?
                        WHERE session_id = ?
                        """,
                        (now, now, session_id)
                    )
                    await db.commit()
                    return False
                else:
                    # Увеличиваем счетчик
                    new_count = row['count'] + 1
                    await db.execute(
                        """
                        UPDATE unknown_message_tracking
                        SET count = ?, last_seen_at = ?
                        WHERE session_id = ?
                        """,
                        (new_count, now, session_id)
                    )
                    await db.commit()
                    
                    if new_count >= max_per_minute:
                        logger.warning(
                            f"Too many unknown messages from session {session_id}: "
                            f"{new_count} in last minute"
                        )
                        return True
                    return False
            else:
                # Создаем новую запись
                await db.execute(
                    """
                    INSERT INTO unknown_message_tracking 
                    (session_id, count, first_seen_at, last_seen_at)
                    VALUES (?, 1, ?, ?)
                    """,
                    (session_id, now, now)
                )
                await db.commit()
                return False
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # SCHEDULED TASKS (замечание 9)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def create_scheduled_task(
        self,
        task_id: str,
        kind: str,
        schedule: str,
        params: Optional[Dict[str, Any]] = None,
        enabled: bool = True
    ) -> None:
        """Создает scheduled task."""
        # Валидация task_id = UUIDv4 (замечание 9)
        try:
            uuid.UUID(task_id)
        except ValueError:
            raise ValueError(f"task_id must be UUIDv4: {task_id}")
        
        now = time.time()
        params_json = json.dumps(params, ensure_ascii=False) if params else None
        
        # Вычисляем next_run_at (упрощенная логика для MVP)
        next_run_at = self._calculate_next_run(schedule, now)
        
        async with aiosqlite.connect(self._db_path, timeout=5.0) as db:
            await db.execute(
                """
                INSERT INTO scheduled_tasks (
                    task_id, kind, schedule, params_json,
                    enabled, next_run_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (task_id, kind, schedule, params_json, 1 if enabled else 0, next_run_at, now)
            )
            await db.commit()
        
        logger.debug(f"Created scheduled task: {task_id}, kind={kind}, next_run={next_run_at}")
    
    def _calculate_next_run(self, schedule: str, now: float) -> float:
        """Вычисляет next_run_at (упрощенная логика)."""
        # MVP: простые интервалы
        intervals = {
            'minutely': 60,
            'hourly': 3600,
            'daily': 86400,
            'weekly': 604800,
        }
        
        if schedule in intervals:
            return now + intervals[schedule]
        
        # MVP не поддерживает cron/timestamp и другие форматы.
        raise ValueError(
            f"Unsupported schedule '{schedule}'. "
            "Supported values: minutely, hourly, daily, weekly"
        )
    
    async def get_due_scheduled_tasks(self, now: Optional[float] = None) -> List[Dict[str, Any]]:
        """Получает задачи, готовые к выполнению."""
        if now is None:
            now = time.time()
        
        async with aiosqlite.connect(self._db_path, timeout=5.0) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT task_id, kind, schedule, params_json, next_run_at
                FROM scheduled_tasks
                WHERE enabled = 1 AND next_run_at <= ?
                ORDER BY next_run_at ASC
                """,
                (now,)
            )
            rows = await cursor.fetchall()
        
        tasks = []
        for row in rows:
            task = dict(row)
            if task.get('params_json'):
                try:
                    task['params'] = json.loads(task['params_json'])
                except json.JSONDecodeError:
                    task['params'] = None
            else:
                task['params'] = None
            tasks.append(task)
        
        return tasks
    
    async def update_scheduled_task_after_run(self, task_id: str) -> None:
        """Обновляет scheduled task после выполнения."""
        now = time.time()
        
        async with aiosqlite.connect(self._db_path, timeout=5.0) as db:
            db.row_factory = aiosqlite.Row
            
            # Получаем schedule
            cursor = await db.execute(
                "SELECT schedule FROM scheduled_tasks WHERE task_id = ?",
                (task_id,)
            )
            row = await cursor.fetchone()
            
            if row:
                next_run = self._calculate_next_run(row['schedule'], now)
                await db.execute(
                    """
                    UPDATE scheduled_tasks
                    SET last_run_at = ?, next_run_at = ?
                    WHERE task_id = ?
                    """,
                    (now, next_run, task_id)
                )
                await db.commit()

    async def list_scheduled_tasks(self) -> List[Dict[str, Any]]:
        """Возвращает полный список scheduled tasks."""
        async with aiosqlite.connect(self._db_path, timeout=5.0) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT task_id, kind, schedule, params_json, enabled,
                       last_run_at, next_run_at, created_at
                FROM scheduled_tasks
                ORDER BY created_at ASC
                """
            )
            rows = await cursor.fetchall()

        tasks: List[Dict[str, Any]] = []
        for row in rows:
            task = dict(row)
            if task.get("params_json"):
                try:
                    task["params"] = json.loads(task["params_json"])
                except json.JSONDecodeError:
                    task["params"] = None
            else:
                task["params"] = None
            tasks.append(task)
        return tasks

    async def get_scheduled_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Возвращает scheduled task по ID."""
        async with aiosqlite.connect(self._db_path, timeout=5.0) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT task_id, kind, schedule, params_json, enabled,
                       last_run_at, next_run_at, created_at
                FROM scheduled_tasks
                WHERE task_id = ?
                """,
                (task_id,)
            )
            row = await cursor.fetchone()

        if not row:
            return None

        task = dict(row)
        if task.get("params_json"):
            try:
                task["params"] = json.loads(task["params_json"])
            except json.JSONDecodeError:
                task["params"] = None
        else:
            task["params"] = None
        return task

    async def disable_scheduled_task(self, task_id: str) -> bool:
        """Отключает scheduled task (cancel semantics для MVP)."""
        async with aiosqlite.connect(self._db_path, timeout=5.0) as db:
            cursor = await db.execute(
                """
                UPDATE scheduled_tasks
                SET enabled = 0
                WHERE task_id = ?
                """,
                (task_id,)
            )
            await db.commit()
            return cursor.rowcount > 0

    async def request_scheduled_task_run_now(self, task_id: str) -> bool:
        """Планирует немедленный запуск задачи без удаления расписания."""
        now = time.time()
        async with aiosqlite.connect(self._db_path, timeout=5.0) as db:
            cursor = await db.execute(
                """
                UPDATE scheduled_tasks
                SET enabled = 1, next_run_at = ?
                WHERE task_id = ?
                """,
                (now, task_id)
            )
            await db.commit()
            return cursor.rowcount > 0
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # LEGACY COMPATIBILITY - Jobs
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def create_job(
        self,
        job_id: str,
        job_type: Optional[str] = None,
        request_id: Optional[str] = None,
        device_id: Optional[str] = None,
        command: Optional[str] = None,
        actor_role: Optional[str] = None,
        meta_json: Optional[str] = None,
        ticket_id: Optional[str] = None
    ) -> None:
        """Создает новую запись job."""
        created_at = time.time()
        
        if job_type is not None and command is None:
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(
                    """
                    INSERT INTO jobs (
                        job_id, job_type, status, progress, created_at, meta_json, ticket_id
                    ) VALUES (?, ?, 'queued', 0, ?, ?, ?)
                    """,
                    (job_id, job_type, created_at, meta_json, ticket_id)
                )
                await db.commit()
            logger.debug(f"Создан job: {job_id}, job_type={job_type}")
        elif command is not None:
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(
                    """
                    INSERT INTO tool_jobs (
                        job_id, request_id, device_id, command, actor_role,
                        status, created_at, started_at, meta_json
                    ) VALUES (?, ?, ?, ?, ?, 'running', ?, ?, ?)
                    """,
                    (job_id, request_id, device_id, command, actor_role, created_at, created_at, meta_json)
                )
                await db.commit()
            logger.debug(f"Создан tool_job: {job_id}, command={command}")
        else:
            raise ValueError("Необходимо указать либо job_type, либо command")
    
    async def update_job_status(
        self,
        job_id: str,
        status: str,
        progress: Optional[float] = None,
        last_error: Optional[str] = None
    ) -> None:
        """Обновляет статус job."""
        updated_at = time.time()
        
        update_fields = ["status = ?", "updated_at = ?"]
        params = [status, updated_at]
        
        if status == "running":
            update_fields.append("started_at = COALESCE(started_at, ?)")
            params.append(updated_at)
        elif status in ("success", "error", "stopped"):
            update_fields.append("finished_at = COALESCE(finished_at, ?)")
            params.append(updated_at)
        
        if progress is not None:
            update_fields.append("progress = ?")
            params.append(progress)
        
        if last_error is not None:
            update_fields.append("last_error = ?")
            params.append(last_error)
        
        params.append(job_id)
        
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                f"UPDATE jobs SET {', '.join(update_fields)} WHERE job_id = ?",
                tuple(params)
            )
            await db.commit()
        
        logger.debug(f"Обновлен job: {job_id}, status={status}")
    
    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Получает job по ID."""
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT job_id, job_type, status, progress, created_at,
                       started_at, updated_at, finished_at, last_error, meta_json, ticket_id
                FROM jobs
                WHERE job_id = ?
                """,
                (job_id,)
            )
            row = await cursor.fetchone()
        
        if not row:
            return None
        
        job = dict(row)
        if job.get('meta_json'):
            try:
                job['meta'] = json.loads(job['meta_json'])
            except json.JSONDecodeError:
                job['meta'] = None
        else:
            job['meta'] = None
        
        return job
    
    async def list_jobs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Получает список jobs."""
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT job_id, job_type, status, progress, created_at,
                       started_at, updated_at, finished_at, last_error, meta_json, ticket_id
                FROM jobs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,)
            )
            rows = await cursor.fetchall()
        
        jobs = []
        for row in rows:
            job = dict(row)
            if job.get('meta_json'):
                try:
                    job['meta'] = json.loads(job['meta_json'])
                except json.JSONDecodeError:
                    job['meta'] = None
            else:
                job['meta'] = None
            jobs.append(job)
        
        return jobs
    
    async def finish_job(
        self,
        job_id: str,
        status: str,
        error_json: Optional[str] = None
    ) -> None:
        """Завершает job (для tool_jobs)."""
        finished_at = time.time()
        
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                UPDATE tool_jobs
                SET status = ?, finished_at = ?, error_json = ?
                WHERE job_id = ?
                """,
                (status, finished_at, error_json, job_id)
            )
            await db.commit()
        
        logger.debug(f"Завершен tool_job: {job_id}, status={status}")
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # LEGACY COMPATIBILITY - seen_messages & seq
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def mark_message_seen(self, job_id: str, message_id: str) -> bool:
        """Атомарно помечает сообщение как обработанное (persistent dedup)."""
        seen_at = time.time()
        async with aiosqlite.connect(self._db_path, timeout=5.0) as db:
            await db.execute("PRAGMA busy_timeout=5000")
            cursor = await db.execute(
                "INSERT OR IGNORE INTO seen_messages (job_id, message_id, seen_at) VALUES (?, ?, ?)",
                (job_id, message_id, seen_at)
            )
            await db.commit()
            return (cursor.rowcount or 0) > 0

    async def is_message_seen(self, job_id: str, message_id: str) -> bool:
        """Returns True when message_id already exists in seen_messages for the job."""
        async with aiosqlite.connect(self._db_path, timeout=5.0) as db:
            await db.execute("PRAGMA busy_timeout=5000")
            cursor = await db.execute(
                "SELECT 1 FROM seen_messages WHERE job_id = ? AND message_id = ? LIMIT 1",
                (job_id, message_id),
            )
            row = await cursor.fetchone()
            return row is not None
    
    async def cleanup_old_seen_messages(self, ttl_seconds: int = 1209600) -> int:
        """Удаляет старые записи из seen_messages."""
        cutoff = time.time() - ttl_seconds
        async with aiosqlite.connect(self._db_path, timeout=5.0) as db:
            cursor = await db.execute(
                "DELETE FROM seen_messages WHERE seen_at < ?",
                (cutoff,)
            )
            await db.commit()
            deleted = cursor.rowcount
        
        if deleted > 0:
            logger.info(f"Очищено {deleted} старых записей из seen_messages")
        
        return deleted
    
    async def get_next_seq(self, job_id: str) -> int:
        """
        Получает следующий seq для job (legacy compatibility).
        
        Note: В V3 используется agent_seq per-ticket, но для обратной
        совместимости оставляем этот метод.
        """
        async with aiosqlite.connect(self._db_path, timeout=5.0) as db:
            await db.execute("PRAGMA busy_timeout=5000")
            await db.execute("BEGIN IMMEDIATE")
            
            try:
                await db.execute(
                    "INSERT OR IGNORE INTO seq_ticket (ticket_id, last_seq) VALUES (?, 0)",
                    (job_id,)
                )
                await db.execute(
                    "UPDATE seq_ticket SET last_seq = last_seq + 1 WHERE ticket_id = ?",
                    (job_id,)
                )
                cursor = await db.execute(
                    "SELECT last_seq FROM seq_ticket WHERE ticket_id = ?",
                    (job_id,)
                )
                row = await cursor.fetchone()
                await db.commit()
                return row[0] if row else 1
            except Exception:
                await db.rollback()
                raise
    
    async def next_device_seq(self, device_id: str) -> int:
        """
        Атомарно генерирует следующий device_seq для device events.
        
        Логика:
        - BEGIN IMMEDIATE transaction
        - INSERT OR IGNORE INTO seq_device (device_id, next_seq) VALUES (?, 0)
        - UPDATE seq_device SET next_seq = next_seq + 1 WHERE device_id = ?
        - SELECT next_seq FROM seq_device WHERE device_id = ?
        - COMMIT
        - Return next_seq (первый вызов вернет 1, не 0)
        
        Args:
            device_id: UUID устройства
            
        Returns:
            Следующий device_seq (начинается с 1)
        """
        async with aiosqlite.connect(self._db_path, timeout=5.0) as db:
            await db.execute("PRAGMA busy_timeout=5000")
            await db.execute("BEGIN IMMEDIATE")
            
            try:
                # Создаем запись если не существует
                await db.execute(
                    "INSERT OR IGNORE INTO seq_device (device_id, next_seq) VALUES (?, 0)",
                    (device_id,)
                )
                
                # Инкрементируем
                await db.execute(
                    "UPDATE seq_device SET next_seq = next_seq + 1 WHERE device_id = ?",
                    (device_id,)
                )
                
                # Получаем новое значение
                cursor = await db.execute(
                    "SELECT next_seq FROM seq_device WHERE device_id = ?",
                    (device_id,)
                )
                row = await cursor.fetchone()
                await db.commit()
                
                return row[0] if row else 1
            except Exception:
                await db.rollback()
                raise
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # SEEN_COMMANDS - Идемпотентность команд (Protocol V3)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def mark_command_started(
        self,
        command_id: str,
        *,
        owner_instance_id: Optional[str] = None,
        stale_retry: bool = False,
    ) -> None:
        """
        Помечает команду как начатую (для отслеживания in_progress).
        
        Args:
            command_id: UUID команды (request_id)
        """
        async with aiosqlite.connect(self._db_path, timeout=5.0) as db:
            await db.execute("PRAGMA busy_timeout=5000")
            await db.execute(
                """
                INSERT OR IGNORE INTO seen_commands 
                (command_id, status, completed_at, started_at, stale_retry_count, owner_instance_id)
                VALUES (?, 'in_progress', ?, ?, 0, ?)
                """,
                (command_id, int(time.time()), int(time.time()), owner_instance_id)
            )
            if stale_retry:
                await db.execute(
                    """
                    UPDATE seen_commands
                    SET status='in_progress',
                        started_at=?,
                        completed_at=?,
                        stale_retry_count=COALESCE(stale_retry_count, 0) + 1,
                        owner_instance_id=?
                    WHERE command_id=?
                    """,
                    (
                        int(time.time()),
                        int(time.time()),
                        owner_instance_id,
                        command_id,
                    ),
                )
            await db.commit()
    
    async def mark_command_seen(
        self,
        command_id: str,
        status: str,  # 'success' | 'error'
        result_json: Optional[str] = None
    ) -> bool:
        """
        Помечает команду как выполненную (идемпотентность).
        
        КРИТИЧНО: Политика "не затирать success"
        - Если есть success → не перезаписывать (return False)
        - Если есть error → можно перезаписать на success (return True)
        - Если нет записи → создать (return True)
        
        Args:
            command_id: UUID команды (request_id)
            status: 'success' или 'error'
            result_json: JSON payload (status + data), не весь tool_response
            
        Returns:
            True если запись создана/обновлена, False если success уже есть
        """
        async with aiosqlite.connect(self._db_path, timeout=5.0) as db:
            await db.execute("PRAGMA busy_timeout=5000")
            await db.execute("BEGIN IMMEDIATE")
            
            try:
                # Проверяем текущий статус
                cursor = await db.execute(
                    "SELECT status FROM seen_commands WHERE command_id = ?",
                    (command_id,)
                )
                row = await cursor.fetchone()
                
                if row and row[0] == "success":
                    # Уже есть success - не затираем
                    await db.rollback()
                    return False
                
                # Можно записать (нет записи, или error, или in_progress)
                await db.execute(
                    """
                    INSERT OR REPLACE INTO seen_commands 
                    (command_id, status, result_json, completed_at, started_at, stale_retry_count, owner_instance_id)
                    VALUES (?, ?, ?, ?, ?, 0, ?)
                    """,
                    (
                        command_id,
                        status,
                        result_json,
                        int(time.time()),
                        int(time.time()),
                        None,
                    )
                )
                await db.commit()
                return True
            except Exception:
                await db.rollback()
                raise
    
    async def get_command_result(self, command_id: str) -> Optional[dict]:
        """
        Получает кэшированный результат команды (для идемпотентности).
        
        Args:
            command_id: UUID команды (request_id)
            
        Returns:
            Dict с полями status, result_json, completed_at, started_at или None если не найдено
        """
        async with aiosqlite.connect(self._db_path, timeout=5.0) as db:
            await db.execute("PRAGMA busy_timeout=5000")
            cursor = await db.execute(
                """
                SELECT status, result_json, completed_at, started_at,
                       COALESCE(stale_retry_count, 0), owner_instance_id
                FROM seen_commands
                WHERE command_id = ?
                """,
                (command_id,)
            )
            row = await cursor.fetchone()
            if row:
                return {
                    "status": row[0],
                    "result_json": row[1],
                    "completed_at": row[2],
                    "started_at": row[3],
                    "stale_retry_count": row[4],
                    "owner_instance_id": row[5],
                }
            return None
    
    async def cleanup_seen_commands(self, max_age_days: int = 14, max_records: int = 50000) -> int:
        """
        Очищает старые записи из seen_commands (housekeeping).
        
        Args:
            max_age_days: Максимальный возраст записей в днях (default: 14)
            max_records: Максимальное количество записей (default: 50000)
            
        Returns:
            Количество удаленных записей
        """
        async with aiosqlite.connect(self._db_path, timeout=10.0) as db:
            await db.execute("PRAGMA busy_timeout=10000")
            await db.execute("BEGIN IMMEDIATE")
            
            try:
                current_time = int(time.time())
                age_threshold = current_time - (max_age_days * 24 * 3600)
                
                # Удаляем старые записи
                cursor = await db.execute(
                    "DELETE FROM seen_commands WHERE completed_at < ?",
                    (age_threshold,)
                )
                deleted_by_age = cursor.rowcount
                
                # Если всё ещё слишком много записей, удаляем самые старые
                cursor = await db.execute("SELECT COUNT(*) FROM seen_commands")
                count = (await cursor.fetchone())[0]
                
                if count > max_records:
                    cursor = await db.execute(
                        """
                        DELETE FROM seen_commands 
                        WHERE command_id IN (
                            SELECT command_id FROM seen_commands 
                            ORDER BY completed_at ASC 
                            LIMIT ?
                        )
                        """,
                        (count - max_records,)
                    )
                    deleted_by_count = cursor.rowcount
                else:
                    deleted_by_count = 0
                
                await db.commit()
                total_deleted = deleted_by_age + deleted_by_count
                logger.info(f"Cleaned up {total_deleted} old seen_commands records")
                return total_deleted
            except Exception:
                await db.rollback()
                raise
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # PENDING CONSENTS (Protocol V3) - Persistent consent tracking
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def add_pending_consent(
        self,
        operation_id: str,
        device_id: str,
        tool_name: str,
        expires_at: int,
        params: Optional[dict] = None,
        payload_hash: Optional[str] = None,
        request_id: Optional[str] = None,
        session_key: Optional[str] = None,
        actor_role: str = "user",
        ticket_id: Optional[str] = None,
        job_id: Optional[str] = None
    ) -> None:
        """
        Добавляет pending consent запись.
        
        Args:
            operation_id: Operation identifier (UUID)
            device_id: Device identifier
            tool_name: Tool name requiring consent
            expires_at: Expiration timestamp (Unix time)
            params: Tool parameters dict (will be JSON serialized)
            payload_hash: Optional hash of payload for verification
            request_id: Original request_id
            session_key: Session key for consent cache
            actor_role: Role of actor requesting consent
            ticket_id: Optional ticket ID
            job_id: Optional job ID
        """
        params_json = json.dumps(params, ensure_ascii=False) if params else None
        async with aiosqlite.connect(self._db_path, timeout=5.0) as db:
            await db.execute("PRAGMA busy_timeout=5000")
            await db.execute(
                """
                INSERT OR REPLACE INTO pending_consents 
                (operation_id, device_id, tool_name, requested_at, expires_at, 
                 payload_hash, params_json, request_id, session_key, actor_role, ticket_id, job_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    operation_id, device_id, tool_name, int(time.time()),
                    expires_at, payload_hash, params_json, request_id, session_key,
                    actor_role, ticket_id, job_id
                )
            )
            await db.commit()
            logger.debug(f"Pending consent added: operation_id={operation_id} tool_name={tool_name}")
    
    async def get_pending_consent(self, operation_id: str) -> Optional[dict]:
        """
        Получает pending consent запись.
        
        Args:
            operation_id: Operation identifier
            
        Returns:
            Dict с полями или None если не найдено
        """
        async with aiosqlite.connect(self._db_path, timeout=5.0) as db:
            await db.execute("PRAGMA busy_timeout=5000")
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT operation_id, device_id, tool_name, requested_at, expires_at,
                       payload_hash, params_json, request_id, session_key, actor_role, ticket_id, job_id
                FROM pending_consents
                WHERE operation_id = ?
                """,
                (operation_id,)
            )
            row = await cursor.fetchone()
            if row:
                # Deserialize params_json
                params = None
                if row["params_json"]:
                    try:
                        params = json.loads(row["params_json"])
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to deserialize params_json for operation_id={operation_id}")
                
                return {
                    "operation_id": row["operation_id"],
                    "device_id": row["device_id"],
                    "tool_name": row["tool_name"],
                    "requested_at": row["requested_at"],
                    "expires_at": row["expires_at"],
                    "payload_hash": row["payload_hash"],
                    "params": params,
                    "request_id": row["request_id"],
                    "session_key": row["session_key"],
                    "actor_role": row["actor_role"],
                    "ticket_id": row["ticket_id"],
                    "job_id": row["job_id"]
                }
            return None
    
    async def remove_pending_consent(self, operation_id: str) -> bool:
        """
        Удаляет pending consent запись.
        
        Args:
            operation_id: Operation identifier
            
        Returns:
            True если запись была удалена, False если не найдена
        """
        async with aiosqlite.connect(self._db_path, timeout=5.0) as db:
            await db.execute("PRAGMA busy_timeout=5000")
            cursor = await db.execute(
                "DELETE FROM pending_consents WHERE operation_id = ?",
                (operation_id,)
            )
            await db.commit()
            deleted = cursor.rowcount > 0
            if deleted:
                logger.debug(f"Pending consent removed: operation_id={operation_id}")
            return deleted
    
    async def cleanup_expired_consents(self) -> int:
        """
        Удаляет истекшие pending consents.
        
        Returns:
            Количество удаленных записей
        """
        async with aiosqlite.connect(self._db_path, timeout=10.0) as db:
            await db.execute("PRAGMA busy_timeout=10000")
            current_time = int(time.time())
            cursor = await db.execute(
                "DELETE FROM pending_consents WHERE expires_at < ?",
                (current_time,)
            )
            await db.commit()
            deleted = cursor.rowcount
            if deleted > 0:
                logger.info(f"Cleaned up {deleted} expired pending consents")
            return deleted
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # LEGACY COMPATIBILITY - enqueue_job_event & enqueue_tool_response
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def enqueue_job_event(
        self,
        job_id: str,
        request_id: Optional[str],
        device_id: Optional[str],
        event_payload: Dict[str, Any]
    ) -> int:
        """
        Legacy wrapper для enqueue_event.
        
        Берет ticket_id из event_payload (если нет, событие считается device_event).
        """
        # КРИТИЧНО: Извлекаем ticket_id из event_payload
        # НЕ используем job_id как fallback - это неправильно!
        # Если ticket_id отсутствует, это device event (без ticket_id)
        ticket_id = event_payload.get('ticket_id')
        
        # Определяем kind из event_payload
        kind = event_payload.get('event', 'job_event')
        
        # Определяем actor_role
        actor_role = event_payload.get('from', 'agent')
        if actor_role not in ('user', 'agent', 'support', 'system'):
            actor_role = 'agent'
        
        # Генерируем trace_id если нет
        trace_id = event_payload.get('trace_id') or str(uuid.uuid4())
        
        # device_id обязателен: нельзя генерировать случайный UUID,
        # иначе событие будет записано как device_event для "чужого" устройства.
        if not device_id:
            device_id = event_payload.get('device_id')
        if not device_id:
            raise ValueError("device_id is required for enqueue_job_event")
        
        return await self.enqueue_event(
            device_id=device_id,
            kind=kind,
            payload=event_payload,
            actor_role=actor_role,
            ticket_id=ticket_id,
            job_id=job_id,
            trace_id=trace_id
        )
    
    async def enqueue_tool_response(
        self,
        job_id: str,
        request_id: Optional[str],
        device_id: Optional[str],
        ticket_id: Optional[str],
        tool_response: Dict[str, Any],
        artifact_local_path: Optional[str] = None,
        artifact_url: Optional[str] = None,
        artifact_mime: Optional[str] = None,
        artifact_sha256: Optional[str] = None
    ) -> int:
        """Legacy wrapper для enqueue_event с поддержкой артефактов."""
        if not ticket_id:
            meta = tool_response.get("meta") if isinstance(tool_response, dict) else None
            ticket_id = (
                (meta or {}).get("ticket_id")
                if isinstance(meta, dict)
                else None
            ) or (tool_response.get("ticket_id") if isinstance(tool_response, dict) else None)
        
        if not ticket_id:
            raise ValueError("ticket_id is required for enqueue_tool_response")
        
        if not device_id:
            raise ValueError("device_id is required for enqueue_tool_response")
        
        outbox_id = await self.enqueue_event(
            ticket_id=ticket_id,
            job_id=job_id,
            kind='tool_response',
            payload=tool_response,
            actor_role='agent',
            device_id=device_id
        )
        
        # Если есть артефакт, добавляем в outbox_attachments
        if artifact_local_path:
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(
                    """
                    INSERT INTO outbox_attachments (
                        outbox_id, artifact_id, artifact_local_path,
                        artifact_mime, artifact_size, artifact_sha256
                    ) VALUES (?, ?, ?, ?, 0, ?)
                    """,
                    (
                        outbox_id, str(uuid.uuid4()), artifact_local_path,
                        artifact_mime or 'application/octet-stream',
                        artifact_sha256 or ''
                    )
                )
                await db.commit()
        
        return outbox_id
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # LEGACY COMPATIBILITY - outbox getters
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def get_outbox_item(self, outbox_id: int) -> Optional[Dict[str, Any]]:
        """Получает одну запись из outbox по ID."""
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT outbox_id, ticket_id, job_id, event_id, kind,
                       payload_json, actor_role, created_at, agent_seq,
                       status, attempts, lease_until, last_error,
                       trace_id, span_id
                FROM outbox
                WHERE outbox_id = ?
                """,
                (outbox_id,)
            )
            row = await cursor.fetchone()
        
        if not row:
            return None
        
        try:
            return {
                'id': row['outbox_id'],
                'outbox_id': row['outbox_id'],
                'ticket_id': row['ticket_id'],
                'job_id': row['job_id'],
                'event_id': row['event_id'],
                'kind': row['kind'],
                'item_type': row['kind'],  # legacy alias
                'payload_json': row['payload_json'],
                'payload': json.loads(row['payload_json']),
                'actor_role': row['actor_role'],
                'created_at': row['created_at'],
                'agent_seq': row['agent_seq'],
                'status': row['status'],
                'attempts': row['attempts'],
                'lease_until': row['lease_until'],
                'last_error': row['last_error'],
                'trace_id': row['trace_id'],
                'span_id': row['span_id']
            }
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка десериализации outbox ID={outbox_id}: {e}")
            return None
    
    async def get_pending_outbox_batch(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Legacy wrapper для claim_outbox_batch."""
        return await self.claim_outbox_batch(limit=limit, lease_sec=30)
    
    async def reserve_outbox_batch(
        self, 
        limit: int = 20, 
        lease_seconds: int = 20
    ) -> List[Dict[str, Any]]:
        """Алиас для claim_outbox_batch (legacy compatibility)."""
        return await self.claim_outbox_batch(limit=limit, lease_sec=lease_seconds)
    
    async def mark_outbox_sent(self, outbox_ids: List[int]) -> int:
        """
        Legacy: помечает как sent.
        В V3 ACK → DELETE, поэтому просто удаляем.
        """
        return await self.ack_and_delete_outbox(outbox_ids)
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # UTILITY
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def close(self) -> None:
        """Закрывает соединение с базой данных."""
        logger.debug("DatabaseManager.close() вызван")
    
    async def add_event(
        self,
        module: str,
        data: Dict[str, Any],
        file_path: Optional[str] = None
    ) -> int:
        """Legacy: добавляет событие (для обратной совместимости)."""
        job_id = str(uuid.uuid4())
        from datetime import datetime, timezone
        
        tool_response = {
            "status": "success",
            "data": {
                "observations": {
                    "module": module,
                    "data": data,
                    "file_path": file_path
                }
            },
            "meta": {
                "timestamp_iso": datetime.now(timezone.utc).isoformat(),
                "command": "collect"
            }
        }
        
        return await self.enqueue_tool_response(
            job_id=job_id,
            request_id=None,
            device_id=str(uuid.uuid4()),
            ticket_id=job_id,
            tool_response=tool_response,
            artifact_local_path=file_path
        )
    
    async def get_events(
        self,
        limit: int = 10,
        module_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Legacy: получает историю событий."""
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT outbox_id, ticket_id, kind, payload_json, created_at
                FROM outbox
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit * 2,)
            )
            rows = await cursor.fetchall()
        
        events = []
        for row in rows:
            try:
                payload = json.loads(row['payload_json'])
                observations = payload.get('data', {}).get('observations', {})
                
                if isinstance(observations, dict):
                    module = observations.get('module')
                    if module_name and module != module_name:
                        continue
                    
                    events.append({
                        "id": row['outbox_id'],
                        "module": module or "unknown",
                        "timestamp": row['created_at'],
                        "data": observations.get('data', {}),
                        "file_path": observations.get('file_path')
                    })
                    
                    if len(events) >= limit:
                        break
            except Exception:
                continue
        
        return events
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # МЕТОДЫ ДЛЯ РАБОТЫ С ТОКЕНОМ АВТОРИЗАЦИИ (v8)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def save_auth_token(self, token: str, device_id: str) -> bool:
        """
        Сохраняет токен авторизации в БД.
        
        Args:
            token: Токен авторизации
            device_id: UUID устройства
            
        Returns:
            True если успешно сохранено
        """
        async with aiosqlite.connect(self._db_path) as db:
            import time
            try:
                # Деактивируем старые токены для этого устройства
                await db.execute("""
                    UPDATE auth_tokens 
                    SET is_active = 0 
                    WHERE device_id = ? AND is_active = 1
                """, (device_id,))
                
                # Если такой токен уже существует под legacy device_id,
                # перепривязываем его к каноническому device_id вместо вставки.
                cursor = await db.execute("""
                    SELECT token FROM auth_tokens WHERE token = ?
                """, (token,))
                existing = await cursor.fetchone()

                if existing:
                    await db.execute("""
                        UPDATE auth_tokens
                        SET device_id = ?, is_active = 1, created_at = ?
                        WHERE token = ?
                    """, (device_id, time.time(), token))
                else:
                    await db.execute("""
                        INSERT INTO auth_tokens (token, device_id, created_at, is_active)
                        VALUES (?, ?, ?, 1)
                    """, (token, device_id, time.time()))
                
                await db.commit()
                logger.info(f"[DatabaseManager] Токен сохранен для device_id={device_id[:8]}...")
                return True
            except Exception as e:
                logger.error(f"[DatabaseManager] Ошибка сохранения токена: {e}")
                await db.rollback()
                return False
    
    def save_auth_token_sync(self, token: str, device_id: str) -> bool:
        """
        СИНХРОННАЯ версия save_auth_token для использования в GUI callbacks.
        
        Args:
            token: Токен авторизации
            device_id: UUID устройства
            
        Returns:
            True если успешно сохранено
        """
        import sqlite3
        import time
        
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            
            # Де активируем старые токены для этого device_id
            cursor.execute("""
                UPDATE auth_tokens 
                SET is_active = 0 
                WHERE device_id = ? AND is_active = 1
            """, (device_id,))
            
            # Проверяем, существует ли уже такой токен
            cursor.execute("""
                SELECT token FROM auth_tokens WHERE token = ?
            """, (token,))
            existing = cursor.fetchone()
            
            if existing:
                # Токен уже существует - активируем его для этого device_id
                cursor.execute("""
                    UPDATE auth_tokens 
                    SET device_id = ?, is_active = 1, created_at = ?
                    WHERE token = ?
                """, (device_id, time.time(), token))
            else:
                # Новый токен - вставляем
                cursor.execute("""
                    INSERT INTO auth_tokens (token, device_id, created_at, is_active)
                    VALUES (?, ?, ?, 1)
                """, (token, device_id, time.time()))
            
            conn.commit()
            conn.close()
            
            logger.info(f"[DatabaseManager] Токен сохранен (sync) для device_id={device_id[:8]}...")
            return True
        except Exception as e:
            logger.error(f"[DatabaseManager] Ошибка сохранения токена (sync): {e}")
            logger.exception(e)
            return False
    
    async def get_auth_token(self, device_id: str) -> Optional[str]:
        """
        Получает активный токен авторизации для устройства.
        
        Args:
            device_id: UUID устройства
            
        Returns:
            Токен или None если не найден
        """
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT token FROM auth_tokens
                WHERE device_id = ? AND is_active = 1
                ORDER BY created_at DESC
                LIMIT 1
            """, (device_id,))
            row = await cursor.fetchone()
            if row:
                return row['token']
            return None
    
    async def update_token_last_used(self, token: str) -> None:
        """
        Обновляет время последнего использования токена.
        
        Args:
            token: Токен авторизации
        """
        async with aiosqlite.connect(self._db_path) as db:
            import time
            await db.execute("""
                UPDATE auth_tokens 
                SET last_used_at = ?
                WHERE token = ? AND is_active = 1
            """, (time.time(), token))
            await db.commit()
    
    async def clear_auth_token(self, device_id: str) -> None:
        """
        Очищает (деактивирует) все токены для устройства.
        
        Args:
            device_id: UUID устройства
        """
        async with aiosqlite.connect(self._db_path) as db:
            try:
                await db.execute("""
                    UPDATE auth_tokens 
                    SET is_active = 0 
                    WHERE device_id = ? AND is_active = 1
                """, (device_id,))
                await db.commit()
                logger.info(f"[DatabaseManager] Токены очищены для device_id={device_id[:8]}...")
            except Exception as e:
                logger.error(f"[DatabaseManager] Ошибка очистки токенов: {e}")
                await db.rollback()
    
    async def revoke_auth_token(self, token: str) -> bool:
        """
        Отзывает токен (деактивирует).
        
        Args:
            token: Токен для отзыва
            
        Returns:
            True если токен был отозван
        """
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute("""
                UPDATE auth_tokens 
                SET is_active = 0
                WHERE token = ? AND is_active = 1
            """, (token,))
            await db.commit()
            return cursor.rowcount > 0


# Глобальный инстанс: задаётся при первом вызове DatabaseManager(db_path) из точки входа (ws_agent с data_root).
# Не создаём здесь DatabaseManager() — иначе путь будет дефолтный (data/storage.db от cwd), и после смены путей токен окажется в другой БД.
db_manager: Optional[DatabaseManager] = None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ТЕСТИРОВАНИЕ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def test_database_v3():
    """Тест Protocol V3 database."""
    import tempfile
    import os
    
    logger.info("=" * 60)
    logger.info("Тестирование DatabaseManager V3")
    logger.info("=" * 60)
    
    # Создаем временную БД
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        
        # Сбрасываем singleton
        DatabaseManager._instance = None
        
        db = DatabaseManager(db_path)
        await db.init_db()
        
        # Тест enqueue_event
        logger.info("1. Тест enqueue_event...")
        ticket_id = str(uuid.uuid4())
        device_id = str(uuid.uuid4())
        
        outbox_id = await db.enqueue_event(
            ticket_id=ticket_id,
            job_id=None,
            kind="test_event",
            payload={"message": "hello"},
            actor_role="agent",
            device_id=device_id
        )
        assert outbox_id > 0
        logger.success(f"   ✅ enqueue_event: outbox_id={outbox_id}")
        
        # Тест claim_outbox_batch
        logger.info("2. Тест claim_outbox_batch...")
        items = await db.claim_outbox_batch(limit=10, lease_sec=30)
        assert len(items) == 1
        assert items[0]['ticket_id'] == ticket_id
        assert items[0]['event_id'] is not None
        logger.success(f"   ✅ claim_outbox_batch: {len(items)} items")
        
        # Тест ack_and_delete_outbox
        logger.info("3. Тест ack_and_delete_outbox...")
        deleted = await db.ack_and_delete_outbox([outbox_id])
        assert deleted == 1
        
        # Проверяем что удалено
        remaining = await db.claim_outbox_batch(limit=10, lease_sec=30)
        assert len(remaining) == 0
        logger.success(f"   ✅ ack_and_delete_outbox: deleted={deleted}")
        
        # Тест конкурентного enqueue
        logger.info("4. Тест конкурентного enqueue_event...")
        import asyncio
        
        concurrent_ticket = str(uuid.uuid4())
        
        async def enqueue_one(i: int) -> int:
            return await db.enqueue_event(
                ticket_id=concurrent_ticket,
                job_id=None,
                kind=f"concurrent_{i}",
                payload={"index": i},
                actor_role="agent",
                device_id=device_id
            )
        
        results = await asyncio.gather(*[enqueue_one(i) for i in range(10)])
        assert len(results) == 10
        assert len(set(results)) == 10  # Все ID уникальны
        
        # Проверяем agent_seq монотонен
        items = await db.claim_outbox_batch(limit=20, lease_sec=30)
        ticket_items = [i for i in items if i['ticket_id'] == concurrent_ticket]
        seqs = [i['agent_seq'] for i in ticket_items]
        assert seqs == sorted(seqs)  # Монотонны
        assert len(set(seqs)) == len(seqs)  # Уникальны
        logger.success(f"   ✅ Конкурентный enqueue: {len(results)} events, seqs={seqs}")
        
        # Тест idempotency cache
        logger.info("5. Тест idempotency cache...")
        key = "test-key-123"
        response = {"status": "success", "data": "test"}
        
        await db.save_idempotency_cache(key, "test_method", ticket_id, response, ttl_seconds=60)
        cached = await db.check_idempotency_cache(key)
        assert cached == response
        logger.success(f"   ✅ idempotency cache: hit")
        
        # Тест ticket_state
        logger.info("6. Тест ticket_state...")
        await db.create_ticket_state(
            ticket_id=ticket_id,
            status="open",
            category="support",
            title="Test Ticket"
        )
        state = await db.get_ticket_state(ticket_id)
        assert state['status'] == "open"
        assert state['category'] == "support"
        logger.success(f"   ✅ ticket_state: {state['status']}")
        
        # Сбрасываем singleton
        DatabaseManager._instance = None
        
        logger.info("=" * 60)
        logger.success("Все тесты V3 пройдены!")
        logger.info("=" * 60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_database_v3())
