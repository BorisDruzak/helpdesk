"""
Конфигурация сервера и константы.
"""

import json
import os
import shutil
from pathlib import Path
from loguru import logger

# Загрузка .env из текущей директории (server/) при запуске сервера
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parent / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)
except ImportError:
    pass

# ============================================================================
# Server Configuration
# ============================================================================

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8666

# ============================================================================
# Database Configuration
# ============================================================================

# PostgreSQL connection URL
# Format: postgresql+asyncpg://user:password@host:port/database
# Example: postgresql+asyncpg://chatbot:password@127.0.0.1:5432/pc_client
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://chatbot:chatbot@127.0.0.1:5432/pc_client"
)

# Enable database persistence (set to False to disable DB features)
ENABLE_DB_PERSISTENCE = os.getenv("ENABLE_DB_PERSISTENCE", "true").lower() == "true"

# ============================================================================
# File Paths
# ============================================================================

SERVER_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = SERVER_DIR.parent


def _resolve_server_data_root() -> Path:
    raw = os.getenv("PC_CLIENT_SERVER_DATA_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA", "").strip()
        if base:
            return (Path(base) / "PCClientServer" / "data").resolve()
        return (Path.home() / "AppData" / "Local" / "PCClientServer" / "data").resolve()
    xdg = os.environ.get("XDG_DATA_HOME", "").strip()
    if xdg:
        return (Path(xdg).expanduser() / "pcclient-server").resolve()
    return (Path.home() / ".local" / "share" / "pcclient-server").resolve()


def _iter_legacy_dir_candidates(relative_path: str):
    seen: set[Path] = set()
    rel = Path(relative_path)
    for base in (SERVER_DIR, WORKSPACE_DIR, Path.cwd().resolve()):
        candidate = (base / rel).resolve()
        if candidate in seen:
            continue
        seen.add(candidate)
        yield candidate


def _prepare_runtime_dir(relative_path: str, *, legacy_relative_paths: tuple[str, ...]) -> Path:
    target = (SERVER_DATA_ROOT / relative_path).resolve()
    target.mkdir(parents=True, exist_ok=True)
    if any(target.iterdir()):
        return target
    for legacy_relative_path in legacy_relative_paths:
        for candidate in _iter_legacy_dir_candidates(legacy_relative_path):
            if candidate == target or not candidate.exists() or not candidate.is_dir():
                continue
            if not any(candidate.iterdir()):
                continue
            shutil.copytree(candidate, target, dirs_exist_ok=True)
            logger.warning(
                f"Migrated runtime data from legacy path: {candidate} -> {target}. "
                f"Set PC_CLIENT_SERVER_DATA_ROOT to control the storage location."
            )
            return target
    return target


SERVER_DATA_ROOT = _resolve_server_data_root()
SERVER_DATA_ROOT.mkdir(parents=True, exist_ok=True)

# Папка для загружаемых файлов (скриншоты, логи)
UPLOAD_DIR = _prepare_runtime_dir(
    "uploads",
    legacy_relative_paths=("uploads",),
)

# Modules storage directory
MODULES_STORAGE_DIR = _prepare_runtime_dir(
    "modules_storage",
    legacy_relative_paths=("data/modules_storage", "modules_storage"),
)

# Maximum module ZIP size (100MB, no longer limited by JSON)
MAX_MODULE_SIZE = 100 * 1024 * 1024

# Agent builds storage directory (remote self-update packages)
AGENT_BUILDS_STORAGE_DIR = _prepare_runtime_dir(
    "agent_builds",
    legacy_relative_paths=("data/agent_builds", "agent_builds"),
)

# Maximum agent build ZIP size (300MB)
MAX_AGENT_BUILD_SIZE = 300 * 1024 * 1024

# Maximum artifact upload size (200MB) — скриншоты, запись экрана
ARTIFACT_MAX_BYTES = 200 * 1024 * 1024

# Public base URL for module downloads (used to construct download_url for agents).
# Must be accessible from the agent's network. 0.0.0.0 is a bind address and cannot
# be used as download host — agents on other machines will get "invalid network name".
# For remote agents set SERVER_PUBLIC_BASE_URL to the server's IP or hostname, e.g.:
#   SERVER_PUBLIC_BASE_URL=http://192.168.1.100:8666
# Default uses 127.0.0.1 so at least the URL is valid; for same-host agents it works.
SERVER_PUBLIC_BASE_URL = os.getenv(
    "SERVER_PUBLIC_BASE_URL",
    f"http://192.168.100.17:{SERVER_PORT}"
)

AGENT_BUILTIN_MODULES = {
    module.strip().lower()
    for module in os.getenv("AGENT_BUILTIN_MODULES", "system,screen").split(",")
    if module.strip()
}

# ============================================================================
# Users Configuration
# ============================================================================

def _parse_users_from_env() -> dict[str, str]:
    """
    Загружает UI пользователей из JSON env.

    Формат:
      UI_USERS_JSON='{"admin":"secret","support":"secret2"}'
    """
    raw = os.getenv("UI_USERS_JSON", "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError) as exc:
        logger.warning(f"Invalid UI_USERS_JSON, fallback to defaults: {exc}")
        return {}
    if not isinstance(parsed, dict):
        logger.warning("UI_USERS_JSON must be a JSON object {login:password}")
        return {}
    users: dict[str, str] = {}
    for login, password in parsed.items():
        if not isinstance(login, str) or not login.strip():
            continue
        if not isinstance(password, str) or not password:
            continue
        users[login.strip()] = password
    return users


def _should_warn_about_default_admin_password(users: dict[str, str]) -> bool:
    warn_flag = str(os.getenv("UI_WARN_ON_DEFAULT_ADMIN_PASSWORD") or "").strip().lower()
    if warn_flag not in {"1", "true", "yes", "on"}:
        return False
    configured_users_json = str(os.getenv("UI_USERS_JSON") or "").strip()
    configured_admin_password = os.getenv("UI_ADMIN_PASSWORD")
    if configured_users_json:
        return False
    if configured_admin_password is not None:
        return False
    return users.get("admin") == "admin123"


# Хранилище пользователей (логин: пароль).
# Для production задавайте UI_USERS_JSON, дефолты только для локальной разработки.
USERS = _parse_users_from_env() or {
    "admin": os.getenv("UI_ADMIN_PASSWORD", "admin123"),
    "user": os.getenv("UI_USER_PASSWORD", "12345"),
}
if _should_warn_about_default_admin_password(USERS):
    logger.warning(
        "Using default admin password from config; set UI_USERS_JSON or UI_ADMIN_PASSWORD in production."
    )

# ============================================================================
# Limits and Constraints
# ============================================================================

# Максимальное количество событий в тикете
MAX_TICKET_EVENTS = 500

# Максимальное количество сообщений в тикете (для UI)
MAX_TICKET_MESSAGES_UI = 200

# TTL для кеша tools (секунды)
TOOLS_CACHE_TTL = 20.0

# Таймаут для WebSocket команд (секунды)
WS_COMMAND_TIMEOUT = 60.0

# Лимиты конкурентности send_ws_command (очередь не переполняется, при исчерпании — 429)
WS_COMMAND_MAX_INFLIGHT_GLOBAL = int(os.getenv("WS_COMMAND_MAX_INFLIGHT_GLOBAL", "200"))
WS_COMMAND_MAX_INFLIGHT_PER_DEVICE = int(os.getenv("WS_COMMAND_MAX_INFLIGHT_PER_DEVICE", "10"))
WS_COMMAND_MAX_INFLIGHT_PER_DEVICE_RUN_TOOL = int(
    os.getenv("WS_COMMAND_MAX_INFLIGHT_PER_DEVICE_RUN_TOOL", "1")
)
# Internal dispatch runtime mode for server->agent outbox delivery:
# - poll: compatibility/rollback poll-all sender loop
# - sharded: per-device queue + shard workers + reconcile sweep
DEVICE_DISPATCH_MODE = (os.getenv("DEVICE_DISPATCH_MODE", "sharded") or "sharded").strip().lower()
DEVICE_DISPATCH_SHARDS = int(os.getenv("DEVICE_DISPATCH_SHARDS", "4"))
DEVICE_DISPATCH_FETCH_LIMIT = int(os.getenv("DEVICE_DISPATCH_FETCH_LIMIT", "50"))
DEVICE_DISPATCH_RECONCILE_SECONDS = int(os.getenv("DEVICE_DISPATCH_RECONCILE_SECONDS", "30"))
DEVICE_DISPATCH_LEASE_SECONDS = int(os.getenv("DEVICE_DISPATCH_LEASE_SECONDS", "30"))

# Protocol V3 ingest guardrails (post-handshake only)
OUTBOX_INGEST_RATE_LIMIT_PER_SEC = int(os.getenv("OUTBOX_INGEST_RATE_LIMIT_PER_SEC", "150"))

# Таймаут для tool execution (секунды)
TOOL_EXECUTION_TIMEOUT = 120.0

# ============================================================================
# Operations SLA Configuration
# ============================================================================

# SLA timeouts for operation lifecycle (в секундах)
# Могут быть переопределены для конкретных kind операций

# Таймаут доставки команды агенту (от queued до sent/accepted)
OPERATION_DELIVERY_TIMEOUT = 30  # 30 секунд

# Таймаут выполнения операции (от accepted до finished)
OPERATION_EXECUTION_TIMEOUT = 180  # 3 минуты

# Таймаут ожидания consent (от waiting_consent до approved/denied)
OPERATION_CONSENT_TIMEOUT = 1800  # 30 минут

# Таймаут между accepted и running (если операция зависла после accept)
OPERATION_ACCEPTED_TIMEOUT = 60  # 1 минута

# SLA overrides для specific operation kinds
# command: list_tools и др. — увеличиваем accepted_timeout/execution_timeout,
# чтобы убрать доминирование list_tools в timeout-метрике (accepted→running часто дольше 60s)
OPERATION_SLA_OVERRIDES = {
    "agent_update": {
        "delivery_timeout": 120,
        "execution_timeout": 1800,  # 30 минут на download + restart + handshake confirm
        "accepted_timeout": 300,
    },
    "command": {
        "delivery_timeout": 60,
        "execution_timeout": 120,
        "accepted_timeout": 120,  # даём время accepted→running (list_tools и др.)
    },
    "screenshot": {
        "delivery_timeout": 15,
        "execution_timeout": 30,
    },
    "execute_program": {
        "delivery_timeout": 30,
        "execution_timeout": 300,  # 5 минут
    },
    "collect": {
        "delivery_timeout": 30,
        "execution_timeout": 600,  # 10 минут (для больших сборов)
    },
}

# Интервал проверки watchdog для таймаутов операций (секунды)
OPERATION_WATCHDOG_INTERVAL = 30  # 30 секунд

# Playbook Scheduler (Этап 6): интервал опроса due runs, макс. активных run на устройство
PLAYBOOK_SCHEDULER_INTERVAL = int(os.getenv("PLAYBOOK_SCHEDULER_INTERVAL", "3"))  # секунды
PLAYBOOK_MAX_ACTIVE_RUNS_PER_DEVICE = int(os.getenv("PLAYBOOK_MAX_ACTIVE_RUNS_PER_DEVICE", "10"))
# Этап 8: макс. параллельных шагов в одном run (fan-out в parallel_group)
PLAYBOOK_MAX_PARALLEL_STEPS_PER_RUN = int(os.getenv("PLAYBOOK_MAX_PARALLEL_STEPS_PER_RUN", "10"))
# Feature flags: откат без смены транспорта (канарейка 10% -> 50% -> 100%)
PLAYBOOK_SCHEDULER_ENABLED = os.getenv("PLAYBOOK_SCHEDULER_ENABLED", "true").lower() == "true"
PLAYBOOK_PARALLEL_ENABLED = os.getenv("PLAYBOOK_PARALLEL_ENABLED", "true").lower() == "true"
CAPABILITY_GATE_STRICT = os.getenv("CAPABILITY_GATE_STRICT", "true").lower() == "true"

# ============================================================================
# Logging Configuration
# ============================================================================
# DEBUG: нужен для диагностики отключений (is_agent_online причины, connected_agents)
LOG_LEVEL = "DEBUG"
LOG_FORMAT = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>"

# ============================================================================
# Security Configuration
# ============================================================================

# Allow remote code execution (for code_exec risk level tools)
# WARNING: Enabling this allows execution of arbitrary code on agent devices
ALLOW_REMOTE_CODE = os.getenv("ALLOW_REMOTE_CODE", "false").lower() == "true"# ============================================================================
# Ticket System (Stage 3)
# ============================================================================
# FSM mode: "soft" — нормализация входящих статусов
TICKET_FSM_MODE = os.getenv("TICKET_FSM_MODE", "soft")
# Принимать from_role/closed_by_role в body, но не использовать для прав; возвращать deprecation_warnings
TICKET_LEGACY_ROLE_FIELDS = os.getenv("TICKET_LEGACY_ROLE_FIELDS", "true").lower() == "true"
# Часы после resolved_at для авто-закрытия (Resolved -> Closed)
TICKET_AUTO_CLOSE_HOURS = int(os.getenv("TICKET_AUTO_CLOSE_HOURS", "72"))# Stage 5: Resolution policy (warn | enforce)
TICKET_RESOLUTION_VALIDATION_MODE = os.getenv("TICKET_RESOLUTION_VALIDATION_MODE", "warn")
# Priorities that require root_cause when enforcing (comma-separated, e.g. P1,P2)
TICKET_REQUIRE_ROOT_CAUSE_PRIORITIES = os.getenv("TICKET_REQUIRE_ROOT_CAUSE_PRIORITIES", "P1,P2")
# Metrics: default and max period in days
TICKET_METRICS_DEFAULT_DAYS = int(os.getenv("TICKET_METRICS_DEFAULT_DAYS", "30"))

# Stage 9: Admin Config API feature flags
TICKET_ADMIN_CONFIG_API_ENABLED = os.getenv("TICKET_ADMIN_CONFIG_API_ENABLED", "true").lower() == "true"
TICKET_ADMIN_CONFIG_WRITE_ENABLED = os.getenv("TICKET_ADMIN_CONFIG_WRITE_ENABLED", "false").lower() == "true"
TICKET_AUDITOR_ROLE_ENABLED = os.getenv("TICKET_AUDITOR_ROLE_ENABLED", "false").lower() == "true"

# Stage 10.x: queue target on take-self/accept flow.
# Modes:
# - keep: keep current queue
# - common: move to common queue code
# - test: move to test queue code
# - <queue_code>: move directly to this queue code
TICKET_TAKE_QUEUE_MODE = (os.getenv("TICKET_TAKE_QUEUE_MODE", "common") or "common").strip().lower()
TICKET_TAKE_QUEUE_COMMON_CODE = (os.getenv("TICKET_TAKE_QUEUE_COMMON_CODE", "servicedesk_l1") or "servicedesk_l1").strip()
TICKET_TAKE_QUEUE_TEST_CODE = (os.getenv("TICKET_TAKE_QUEUE_TEST_CODE", "servicedesk_test") or "servicedesk_test").strip()

# Stage 10: UI users from DB
AUTH_UI_DB_USERS_ENABLED = os.getenv("AUTH_UI_DB_USERS_ENABLED", "true").lower() == "true"
AUTH_UI_CONFIG_FALLBACK_ENABLED = os.getenv("AUTH_UI_CONFIG_FALLBACK_ENABLED", "true").lower() == "true"
AUTH_UI_MAX_FAILED_ATTEMPTS = int(os.getenv("AUTH_UI_MAX_FAILED_ATTEMPTS", "5"))
AUTH_UI_LOCK_MINUTES = int(os.getenv("AUTH_UI_LOCK_MINUTES", "15"))
PUBLIC_TICKET_SESSION_MINUTES = int(os.getenv("PUBLIC_TICKET_SESSION_MINUTES", "15"))
WEBAPP_CUTOVER_LOGIN_ENABLED = os.getenv("WEBAPP_CUTOVER_LOGIN_ENABLED", "true").lower() == "true"
WEBAPP_CUTOVER_SUPPORT_ENABLED = os.getenv("WEBAPP_CUTOVER_SUPPORT_ENABLED", "true").lower() == "true"
WEBAPP_CUTOVER_ADMIN_ENABLED = os.getenv("WEBAPP_CUTOVER_ADMIN_ENABLED", "true").lower() == "true"
# Operational rule: support/admin cutover becomes active only when the web bundle is built
# and login cutover is also enabled. The route handlers enforce those prerequisites at runtime.
# Explicit WEBAPP_CUTOVER_*=false in server/.env remains the rollback path.

# Stage 11: SLA Calendar + OLA
TICKET_SLA_CALENDAR_ENABLED = os.getenv("TICKET_SLA_CALENDAR_ENABLED", "false").lower() == "true"
TICKET_OLA_ENABLED = os.getenv("TICKET_OLA_ENABLED", "false").lower() == "true"# Stage 12: Retention / Archive
TICKET_RETENTION_ENABLED = os.getenv("TICKET_RETENTION_ENABLED", "false").lower() == "true"
TICKET_EVENTS_HOT_RETENTION_DAYS = int(os.getenv("TICKET_EVENTS_HOT_RETENTION_DAYS", "180"))
TICKET_ADMIN_AUDIT_HOT_RETENTION_DAYS = int(os.getenv("TICKET_ADMIN_AUDIT_HOT_RETENTION_DAYS", "365"))
TICKET_RETENTION_BATCH_SIZE = int(os.getenv("TICKET_RETENTION_BATCH_SIZE", "5000"))
TICKET_RETENTION_MAX_BATCHES_PER_RUN = int(os.getenv("TICKET_RETENTION_MAX_BATCHES_PER_RUN", "200"))
TICKET_RETENTION_DRY_RUN = os.getenv("TICKET_RETENTION_DRY_RUN", "true").lower() == "true"
# UI_USER_ROLES_JSON: JSON маппинг логин -> роль. Пример: {"admin":"admin","auditor1":"auditor"}
# Fallback для логинов без маппинга: admin
def _parse_ui_roles() -> dict:
    import json as _json
    raw = os.getenv("UI_USER_ROLES_JSON", "{}")
    if not raw or not raw.strip():
        return {}
    try:
        return _json.loads(raw)
    except (ValueError, TypeError):
        return {}

UI_USER_ROLES: dict = _parse_ui_roles()
TICKET_METRICS_MAX_DAYS = int(os.getenv("TICKET_METRICS_MAX_DAYS", "365"))

# ============================================================================
# Protocol V3 Configuration
# ============================================================================

# Server capabilities advertised to agents in handshake_ack
SERVER_CAPABILITIES = [
    "protocol_v3",
    "envelope_v3",
    "outbox_ack_v3",
    "outbox_nack",
    "trace_correlation",
    "ticket_context",
    "job_context",
    "device_outbox",
    "event_replay",
    "batch_ack",
    "outbox_batch_v1",
    "device_binding_validation",
    "device_registry",
    "toolset_snapshots",
    "config_management"
]
