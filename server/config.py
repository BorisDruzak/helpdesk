"""
Конфигурация сервера и константы.
"""

import json
import math
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

SERVER_HOST = (os.getenv("SERVER_HOST", "0.0.0.0") or "0.0.0.0").strip()
SERVER_PORT = int(os.getenv("SERVER_PORT", "8666") or "8666")

# External-domain composition is fail-closed. Knowledge has no runtime adapter;
# Registry remains on its local compatibility adapter until external acceptance.
KNOWLEDGE_PORT_MODE = (os.getenv("KNOWLEDGE_PORT_MODE", "unavailable") or "unavailable").strip().lower()
REGISTRY_PORT_MODE = (os.getenv("REGISTRY_PORT_MODE", "local") or "local").strip().lower()
# PR-9 read-only Registry Platform integration. The token is never emitted by
# configuration diagnostics or RegistryPort logs. Commands remain local until
# their separate acceptance cutover.
REGISTRY_EXTERNAL_BASE_URL = (os.getenv("REGISTRY_EXTERNAL_BASE_URL", "") or "").strip().rstrip("/")
REGISTRY_EXTERNAL_SERVICE_TOKEN = os.getenv("REGISTRY_EXTERNAL_SERVICE_TOKEN", "") or ""


def _bounded_registry_external_timeout() -> float:
    try:
        timeout = float(os.getenv("REGISTRY_EXTERNAL_TIMEOUT_SECONDS", "2.0") or "2.0")
    except (TypeError, ValueError):
        return 2.0
    if not math.isfinite(timeout):
        return 2.0
    return max(0.05, min(timeout, 10.0))


REGISTRY_EXTERNAL_TIMEOUT_SECONDS = _bounded_registry_external_timeout()

# Endpoint Operations API v1 composition is fail-closed. The external adapter
# is introduced separately; these settings contain no production defaults.
ENDPOINT_PORT_MODE = (os.getenv("ENDPOINT_PORT_MODE", "unavailable") or "unavailable").strip().lower()
ENDPOINT_EXTERNAL_BASE_URL = (os.getenv("ENDPOINT_EXTERNAL_BASE_URL", "") or "").strip().rstrip("/")
ENDPOINT_EXTERNAL_SERVICE_TOKEN = os.getenv("ENDPOINT_EXTERNAL_SERVICE_TOKEN", "") or ""
ENDPOINT_EXTERNAL_CA_FILE = (os.getenv("ENDPOINT_EXTERNAL_CA_FILE", "") or "").strip()
ENDPOINT_DIAGNOSTIC_EXECUTION_MODE = (
    os.getenv("ENDPOINT_DIAGNOSTIC_EXECUTION_MODE", "endpoint") or "endpoint"
).strip().lower()
# Endpoint Module Platform is an independent typed boundary.  It must never
# inherit the diagnostic provider's execution mode or legacy fallback.
ENDPOINT_MODULE_PORT_MODE = (
    os.getenv("ENDPOINT_MODULE_PORT_MODE", "unavailable") or "unavailable"
).strip().lower()
# Module Platform credentials are deliberately separate from diagnostic access.
# A module-only service client must not inherit the diagnostic client's scopes.
ENDPOINT_MODULE_EXTERNAL_SERVICE_TOKEN = os.getenv(
    "ENDPOINT_MODULE_EXTERNAL_SERVICE_TOKEN", ""
) or ""
# The legacy Python-module workbench remains authoritative unless a reviewed
# deployment explicitly selects Endpoint-native recipes.  This flag is
# declarative only: it cannot enable execution by itself.
MODULE_WORKBENCH_AUTHORITY = (
    os.getenv("MODULE_WORKBENCH_AUTHORITY", "legacy") or "legacy"
).strip().lower()
# Module operations have a separate cutover from the read-only module port.
# Keep the established diagnostic execution path intact until the module
# reconciler has explicit acceptance in a pilot environment.
ENDPOINT_MODULE_EXECUTION_MODE = (
    os.getenv("ENDPOINT_MODULE_EXECUTION_MODE", "disabled") or "disabled"
).strip().lower()
LEGACY_MODULE_EXECUTION_ENABLED = (
    os.getenv("LEGACY_MODULE_EXECUTION_ENABLED", "true") or "true"
).strip().lower() in {"1", "true", "yes", "on"}


def _bounded_endpoint_external_timeout() -> float:
    try:
        timeout = float(os.getenv("ENDPOINT_EXTERNAL_TIMEOUT_SECONDS", "2.0") or "2.0")
    except (TypeError, ValueError):
        return 2.0
    if not math.isfinite(timeout):
        return 2.0
    return max(0.05, min(timeout, 10.0))


def _bounded_endpoint_reconcile_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)) or str(default))
    except (TypeError, ValueError):
        return default
    return max(minimum, min(value, maximum))


ENDPOINT_EXTERNAL_TIMEOUT_SECONDS = _bounded_endpoint_external_timeout()
ENDPOINT_OPERATION_RECONCILE_INTERVAL_SECONDS = _bounded_endpoint_reconcile_int(
    "ENDPOINT_OPERATION_RECONCILE_INTERVAL_SECONDS",
    5,
    1,
    60,
)
ENDPOINT_OPERATION_RECONCILE_BATCH_SIZE = _bounded_endpoint_reconcile_int(
    "ENDPOINT_OPERATION_RECONCILE_BATCH_SIZE",
    25,
    1,
    100,
)

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

# Pilot/readiness policy flags. Insecure local defaults require an explicit opt-in.
APP_ENV = (os.getenv("APP_ENV", "dev") or "dev").strip().lower()
VALID_APP_ENVS = {"dev", "test", "pilot", "prod"}
ALLOW_INSECURE_DEV_DEFAULTS = os.getenv("ALLOW_INSECURE_DEV_DEFAULTS", "false").lower() == "true"
PILOT_STAND_MODE = os.getenv("PILOT_STAND_MODE", "false").lower() == "true"
REQUIRE_HTTPS = os.getenv("REQUIRE_HTTPS", "false").lower() == "true"
REQUIRE_WSS = os.getenv("REQUIRE_WSS", "false").lower() == "true"
AUTH_ALLOW_QUERY_TOKEN = os.getenv("AUTH_ALLOW_QUERY_TOKEN", "false").lower() == "true"
PILOT_MIN_AGENT_VERSION = os.getenv("PILOT_MIN_AGENT_VERSION", "").strip()
_strict_profile = APP_ENV in {"pilot", "prod"} or PILOT_STAND_MODE
_default_secure_cookie = "true" if _strict_profile else ("false" if ALLOW_INSECURE_DEV_DEFAULTS else "true")
WEB_SESSION_COOKIE_SECURE = os.getenv("WEB_SESSION_COOKIE_SECURE", _default_secure_cookie).lower() == "true"
WEB_SESSION_COOKIE_HTTPONLY = os.getenv("WEB_SESSION_COOKIE_HTTPONLY", "true").lower() == "true"
WEB_SESSION_COOKIE_SAMESITE = (os.getenv("WEB_SESSION_COOKIE_SAMESITE", "Lax") or "Lax").strip()
WEB_CSRF_SAME_ORIGIN_ENABLED = os.getenv("WEB_CSRF_SAME_ORIGIN_ENABLED", "true").lower() == "true"
WEB_CSRF_TRUSTED_ORIGINS = os.getenv("WEB_CSRF_TRUSTED_ORIGINS", "").strip()
LEGACY_UI_TOKEN_LOGIN_ENABLED = os.getenv("LEGACY_UI_TOKEN_LOGIN_ENABLED", "false").lower() == "true"
ACCOUNT_SESSION_ALLOW_QUERY_TOKEN = os.getenv("ACCOUNT_SESSION_ALLOW_QUERY_TOKEN", "false").lower() == "true"
ACCOUNT_SESSION_DELIVERY_SECRET = os.getenv("ACCOUNT_SESSION_DELIVERY_SECRET", "").strip()
AGENT_TOKEN_MAX_ACTIVE_TOKENS = int(os.getenv("AGENT_TOKEN_MAX_ACTIVE_TOKENS", "2"))
TRUST_X_FORWARDED_FOR = os.getenv("TRUST_X_FORWARDED_FOR", "false").lower() == "true"
TRUSTED_PROXY_CIDRS = os.getenv("TRUSTED_PROXY_CIDRS", "").strip()
TECH_BACKUP_STATUS_PATH = os.getenv("TECH_BACKUP_STATUS_PATH", "").strip()
TECH_RESTORE_DRILL_STATUS_PATH = os.getenv("TECH_RESTORE_DRILL_STATUS_PATH", "").strip()
TECH_RELEASE_STATUS_PATH = os.getenv("TECH_RELEASE_STATUS_PATH", "").strip()
TECH_BUSINESS_SMOKE_STATUS_PATH = os.getenv("TECH_BUSINESS_SMOKE_STATUS_PATH", "").strip()
REQUIRE_BACKUP_RESTORE_EVIDENCE = os.getenv("REQUIRE_BACKUP_RESTORE_EVIDENCE", "false").lower() == "true"

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
    if str(os.getenv("PC_CLIENT_DISABLE_LEGACY_RUNTIME_MIGRATION") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return target
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
    f"http://127.0.0.1:{SERVER_PORT}"
)

AGENT_BUILTIN_MODULES = {
    module.strip().lower()
    for module in os.getenv("AGENT_BUILTIN_MODULES", "system,screen,diag,inventory,presence").split(",")
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

# Inventory refresh scheduler: disabled by default until an admin enables policy
# rows. The runtime only dispatches the existing inventory.collect tool.
INVENTORY_REFRESH_SCHEDULER_ENABLED = os.getenv("INVENTORY_REFRESH_SCHEDULER_ENABLED", "false").lower() == "true"
INVENTORY_REFRESH_SCHEDULER_INTERVAL_SEC = int(os.getenv("INVENTORY_REFRESH_SCHEDULER_INTERVAL_SEC", "60"))

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
AUTH_UI_CONFIG_FALLBACK_ENABLED = os.getenv("AUTH_UI_CONFIG_FALLBACK_ENABLED", "false").lower() == "true"
AUTH_UI_MAX_FAILED_ATTEMPTS = int(os.getenv("AUTH_UI_MAX_FAILED_ATTEMPTS", "5"))
AUTH_UI_LOCK_MINUTES = int(os.getenv("AUTH_UI_LOCK_MINUTES", "15"))
PUBLIC_TICKET_SESSION_MINUTES = int(os.getenv("PUBLIC_TICKET_SESSION_MINUTES", "15"))
WEB_SELF_REGISTRATION_ENABLED = os.getenv("WEB_SELF_REGISTRATION_ENABLED", "false").lower() == "true"
PROFILE_COMPLETION_REQUIRED = os.getenv("PROFILE_COMPLETION_REQUIRED", "true").lower() == "true"

# Stage 11: SLA Calendar + OLA
TICKET_SLA_CALENDAR_ENABLED = os.getenv("TICKET_SLA_CALENDAR_ENABLED", "false").lower() == "true"
TICKET_OLA_ENABLED = os.getenv("TICKET_OLA_ENABLED", "false").lower() == "true"# Stage 12: Retention / Archive
TICKET_RETENTION_ENABLED = os.getenv("TICKET_RETENTION_ENABLED", "false").lower() == "true"
TICKET_EVENTS_HOT_RETENTION_DAYS = int(os.getenv("TICKET_EVENTS_HOT_RETENTION_DAYS", "180"))
TICKET_ADMIN_AUDIT_HOT_RETENTION_DAYS = int(os.getenv("TICKET_ADMIN_AUDIT_HOT_RETENTION_DAYS", "365"))
TICKET_RETENTION_BATCH_SIZE = int(os.getenv("TICKET_RETENTION_BATCH_SIZE", "5000"))
TICKET_RETENTION_MAX_BATCHES_PER_RUN = int(os.getenv("TICKET_RETENTION_MAX_BATCHES_PER_RUN", "200"))
TICKET_RETENTION_DRY_RUN = os.getenv("TICKET_RETENTION_DRY_RUN", "true").lower() == "true"
REQUEST_STUDIO_CONFIRMATION_TTL_SECONDS = int(os.getenv("REQUEST_STUDIO_CONFIRMATION_TTL_SECONDS", "600"))
REQUEST_STUDIO_CONFIRMATION_SECRET = os.getenv("REQUEST_STUDIO_CONFIRMATION_SECRET", "").strip()
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


def _uses_default_ui_passwords() -> bool:
    if os.getenv("UI_USERS_JSON") or os.getenv("UI_ADMIN_PASSWORD") or os.getenv("UI_USER_PASSWORD"):
        return False
    return USERS.get("admin") == "admin123" or USERS.get("user") == "12345"


def is_strict_runtime_mode() -> bool:
    """Return true for pilot/production profiles that must fail closed."""
    return APP_ENV in {"pilot", "prod"} or PILOT_STAND_MODE


def validate_security_config() -> None:
    """Fail fast for pilot/production configs that would expose auth surfaces."""
    errors: list[str] = []
    strict_mode = is_strict_runtime_mode()
    if APP_ENV not in VALID_APP_ENVS:
        errors.append(f"APP_ENV must be one of {sorted(VALID_APP_ENVS)}, got {APP_ENV!r}")
    if AUTH_ALLOW_QUERY_TOKEN:
        errors.append("AUTH_ALLOW_QUERY_TOKEN must be false")
    if AUTH_UI_CONFIG_FALLBACK_ENABLED and (strict_mode or not ALLOW_INSECURE_DEV_DEFAULTS):
        errors.append("AUTH_UI_CONFIG_FALLBACK_ENABLED requires ALLOW_INSECURE_DEV_DEFAULTS=true")
    if strict_mode:
        if ALLOW_INSECURE_DEV_DEFAULTS:
            errors.append("ALLOW_INSECURE_DEV_DEFAULTS must be false in pilot/prod mode")
        if not ENABLE_DB_PERSISTENCE:
            errors.append("ENABLE_DB_PERSISTENCE must be true in pilot/prod mode")
        if not WEB_SESSION_COOKIE_SECURE:
            errors.append("WEB_SESSION_COOKIE_SECURE must be true in pilot/prod mode")
        if not REQUIRE_HTTPS:
            errors.append("REQUIRE_HTTPS must be true in pilot/prod mode")
        if not REQUIRE_WSS:
            errors.append("REQUIRE_WSS must be true in pilot/prod mode")
        if _uses_default_ui_passwords():
            errors.append("default UI users/passwords are forbidden in pilot/prod mode")
        if LEGACY_UI_TOKEN_LOGIN_ENABLED:
            errors.append("LEGACY_UI_TOKEN_LOGIN_ENABLED must be false in pilot/prod mode")
        if not ACCOUNT_SESSION_DELIVERY_SECRET:
            errors.append("ACCOUNT_SESSION_DELIVERY_SECRET must be set in pilot/prod mode")
    if errors:
        raise RuntimeError("Insecure security configuration: " + "; ".join(errors))

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
