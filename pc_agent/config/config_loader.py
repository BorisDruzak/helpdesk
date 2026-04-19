"""
Загрузчик конфигурации приложения с валидацией через Pydantic.

- Валидирует типы данных.
- Конфиг привязан к data_root: инициализация через init_config(data_root).
- get_config() — lazy singleton после init_config (не eager-load при импорте).
- Переменные окружения (для E2E/тестов): PC_AGENT_WS_URL, PC_AGENT_API_URL переопределяют server.ws_url / server.api_url.
"""
from pathlib import Path
from typing import List, Optional
import os
import shutil
import yaml
from pydantic import BaseModel, Field, field_validator
from loguru import logger

_CONFIG_DIR = Path(__file__).resolve().parent
DEFAULT_SETTINGS_TEMPLATE = _CONFIG_DIR / "settings.default.yaml"
_config_base: Optional[Path] = None  # data_root при вызове init_config(); для разрешения относительных путей
CORE_ENABLED_MODULES = ("system", "screen")


def _normalize_enabled_modules(module_names: List[str] | None) -> List[str]:
    normalized: List[str] = []
    seen: set[str] = set()
    for module_name in [*CORE_ENABLED_MODULES, *(module_names or [])]:
        name = str(module_name or "").strip()
        if not name or name in seen:
            continue
        normalized.append(name)
        seen.add(name)
    return normalized


class ServerConfig(BaseModel):
    """Конфигурация сервера."""
    ws_url: str = Field(default="ws://192.168.100.17:8666/ws", description="URL WebSocket сервера")
    api_url: str = Field(default="http://192.168.100.17:8666/api", description="URL API сервера")
    http_port: int = Field(default=12345, ge=1, le=65535, description="Порт HTTP сервера")
    reconnect_interval: int = Field(default=5, ge=1, description="Интервал переподключения (сек)")


class SecurityConfig(BaseModel):
    """Конфигурация безопасности."""
    allow_remote_code: bool = Field(default=False, description="Разрешить выполнение удаленного кода")


class PathsConfig(BaseModel):
    """Конфигурация путей (относительно data_root при использовании с runtime_paths)."""
    data_dir: str = Field(default="data", description="Директория данных")
    identity_file: str = Field(default="data/identity.json", description="Файл идентификации")
    temp_dir: str = Field(default="data/temp", description="Временная директория")

    @field_validator('data_dir')
    @classmethod
    def validate_path(cls, v: str) -> str:
        """Валидация путей."""
        if not v or v.strip() == "":
            raise ValueError("Путь не может быть пустым")
        return v


class LoggingConfig(BaseModel):
    """Конфигурация логирования."""
    level: str = Field(default="INFO", description="Уровень логирования")
    file: str = Field(default="logs/agent.log", description="Файл логов")
    console_level: str = Field(default="INFO", description="Уровень логирования в консоли")
    rotation: str = Field(default="20 MB", description="Ротация файла логов")
    retention: str = Field(default="14 days", description="Срок хранения архивных логов")
    compression: str = Field(default="zip", description="Сжатие архивных логов")
    enqueue: bool = Field(default=True, description="Асинхронная запись логов")
    
    @field_validator('level')
    @classmethod
    def validate_level(cls, v: str) -> str:
        """Валидация уровня логирования."""
        allowed_levels = ["TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in allowed_levels:
            raise ValueError(f"Недопустимый уровень логирования: {v}. Разрешены: {', '.join(allowed_levels)}")
        return v_upper


class UiConfig(BaseModel):
    """Конфигурация UI."""
    enabled: bool = Field(default=False, description="Включен ли GUI")
    host: str = Field(default="127.0.0.1", description="Хост для UI API сервера")
    port: int = Field(default=8765, ge=1, le=65535, description="Порт для UI API сервера")
    autostart_gui: bool = Field(default=False, description="Автоматически запускать GUI при старте")
    tray_enabled: bool = Field(default=True, description="Включить system tray для always-on режима")
    minimize_to_tray: bool = Field(default=True, description="При закрытии окна сворачивать его в tray")
    start_hidden: bool = Field(default=False, description="Запускать GUI скрытым в tray")
    notifications_enabled: bool = Field(default=True, description="Показывать tray-уведомления")
    theme_mode: str = Field(default="light", description="Тема GUI: light или dark")

    @field_validator("theme_mode")
    @classmethod
    def validate_theme_mode(cls, v: str) -> str:
        mode = str(v or "").strip().lower()
        if mode not in {"light", "dark"}:
            raise ValueError("ui.theme_mode должен быть light или dark")
        return mode


class ModulesConfig(BaseModel):
    """Конфигурация модулей."""
    extra_paths: List[str] = Field(default_factory=list, description="Дополнительные пути для загрузки модулей")


class Settings(BaseModel):
    """Корневая модель конфигурации."""
    server: ServerConfig = Field(default_factory=ServerConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    enabled_modules: List[str] = Field(default_factory=lambda: ["system", "screen"], description="Список включенных модулей (базовая комплектация: system, screen)")
    ui: UiConfig = Field(default_factory=UiConfig, description="Конфигурация UI")
    modules: ModulesConfig = Field(default_factory=ModulesConfig, description="Конфигурация модулей")

    @field_validator("enabled_modules", mode="before")
    @classmethod
    def normalize_enabled_modules(cls, value):
        return _normalize_enabled_modules(value)


class ConfigLoader:
    """
    Класс-синглтон для загрузки конфигурации из YAML файла.
    
    Функционал:
    - Загрузка и валидация YAML конфигурации
    - Автоматическое создание необходимых директорий
    - Синглтон паттерн для единственного экземпляра
    """
    
    _instance: Optional['ConfigLoader'] = None
    _config: Optional[Settings] = None
    
    def __new__(cls):
        """Реализация паттерна Singleton."""
        if cls._instance is None:
            cls._instance = super(ConfigLoader, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Инициализация загрузчика."""
        if not hasattr(self, '_initialized'):
            self.config_path: Optional[Path] = None
            self._initialized = True

    def load(self, config_path: Path, create_dirs: bool = True) -> Settings:
        """
        Загружает и валидирует конфигурацию из YAML файла.

        Args:
            config_path: Путь к файлу settings.yaml.
            create_dirs: Создавать ли директории (относительно родителя config_path).

        Returns:
            Settings: Валидированный объект настроек.

        Raises:
            FileNotFoundError: Если файл конфигурации не найден
            ValidationError: Если структура конфигурации некорректна
        """
        config_path = config_path.resolve()
        if self.config_path != config_path:
            self.config_path = config_path
            self._config = None
        if self._config is not None:
            return self._config
        if not self.config_path.exists():
            raise FileNotFoundError(f"Файл конфигурации не найден: {self.config_path}")
        with open(self.config_path, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f)
        self._config = Settings(**(config_data or {}))
        self._config = self._config.model_copy(
            update={"enabled_modules": _normalize_enabled_modules(self._config.enabled_modules)}
        )
        # Переопределение из env (для E2E: локальный сервер без правки settings.yaml)
        ws_url = os.environ.get("PC_AGENT_WS_URL", "").strip()
        api_url = os.environ.get("PC_AGENT_API_URL", "").strip()
        if ws_url or api_url:
            updates = {}
            if ws_url:
                updates["ws_url"] = ws_url
            if api_url:
                updates["api_url"] = api_url
            if updates:
                self._config = self._config.model_copy(
                    update={"server": self._config.server.model_copy(update=updates)}
                )
                logger.debug(f"   Server URL overridden from env: ws_url={self._config.server.ws_url!r}")
        ui_port_str = os.environ.get("PC_AGENT_UI_PORT", "").strip()
        if ui_port_str:
            try:
                ui_port = int(ui_port_str)
                if 1 <= ui_port <= 65535:
                    self._config = self._config.model_copy(
                        update={"ui": self._config.ui.model_copy(update={"port": ui_port})}
                    )
                    logger.debug(f"   UI port overridden from env: port={ui_port}")
            except ValueError:
                pass
        logger.info(f"✅ Конфигурация загружена: {self.config_path}")
        logger.debug(f"   WebSocket URL: {self._config.server.ws_url}")
        logger.debug(f"   API URL: {self._config.server.api_url}")
        logger.debug(f"   Уровень логирования: {self._config.logging.level}")
        logger.debug(f"   Включенные модули: {', '.join(self._config.enabled_modules)}")
        if create_dirs:
            self._create_directories(self.config_path.parent)
        return self._config

    def _create_directories(self, base: Path) -> None:
        """Создает директории из конфигурации относительно base (обычно data_root)."""
        if self._config is None:
            return
        directories = [
            base / Path(self._config.logging.file).parent,
        ]
        if getattr(self._config.paths, "temp_dir", None):
            directories.append(base / self._config.paths.temp_dir)
        for directory in directories:
            if not directory.exists():
                directory.mkdir(parents=True, exist_ok=True)
                logger.success(f"📁 Создана директория: {directory}")
            else:
                logger.debug(f"📁 Директория уже существует: {directory}")


def load_config(config_path: Path, create_dirs: bool = True) -> Settings:
    """
    Загружает конфигурацию из указанного файла.

    Args:
        config_path: Путь к settings.yaml.
        create_dirs: Создавать ли директории.

    Returns:
        Settings: Объект настроек.
    """
    loader = ConfigLoader()
    return loader.load(config_path=config_path, create_dirs=create_dirs)


def get_config() -> Settings:
    """
    Возвращает уже инициализированный конфиг (lazy singleton).

    Вызывать только после init_config() или load_config() в точке входа.

    Raises:
        RuntimeError: Если конфиг ещё не был инициализирован.
    """
    loader = ConfigLoader()
    if loader._config is None:
        raise RuntimeError(
            "Конфигурация не инициализирована. Вызовите init_config(data_root) или load_config(config_path) в точке входа (например в main()) до использования get_config()."
        )
    return loader._config


def init_config(data_root: Path, config_override: Optional[Path] = None) -> Settings:
    """
    Инициализирует конфигурацию, привязанную к data_root.

    - Путь к конфигу по умолчанию: data_root / "settings.yaml".
    - Если файла нет — копируется шаблон из settings.default.yaml.
    - config_override: явный путь к YAML (если задан, используется вместо data_root/settings.yaml).
    - Устанавливает глобальный _config_base = data_root для разрешения относительных путей (identity и т.д.).

    Returns:
        Settings: Загруженная конфигурация.
    """
    global _config_base
    data_root = data_root.resolve()
    data_root.mkdir(parents=True, exist_ok=True)
    _config_base = data_root
    config_path = config_override if config_override is not None else data_root / "settings.yaml"
    config_path = config_path.resolve()
    if not config_path.exists() and DEFAULT_SETTINGS_TEMPLATE.exists():
        shutil.copy2(DEFAULT_SETTINGS_TEMPLATE, config_path)
        logger.info(f"Создан конфиг из шаблона: {config_path}")
    return load_config(config_path, create_dirs=True)


def get_config_base() -> Optional[Path]:
    """Возвращает data_root, заданный при init_config(), или None. Используется для разрешения относительных путей (identity.json и т.д.)."""
    return _config_base
