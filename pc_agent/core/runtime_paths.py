"""
Единый источник истины для путей данных и установки агента (per-user).

Используется для кроссплатформенного layout: install_root/versions/<ver>/ + data_root.
Окружение: PC_AGENT_DATA_DIR, PC_AGENT_INSTALL_ROOT.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def resolve_data_root(
    env_key: str = "PC_AGENT_DATA_DIR",
    cli_value: Optional[str] = None,
) -> Path:
    """
    Корень данных агента (БД, логи, modules_store, updates).

    Приоритет: cli_value (если задан) -> env_key -> дефолт по ОС.
    Windows: %LOCALAPPDATA%\\PCClientAgent\\data
    Linux: $XDG_DATA_HOME/pcclient-agent или ~/.local/share/pcclient-agent
    """
    if cli_value is not None and cli_value.strip():
        return Path(cli_value.strip()).expanduser().resolve()
    env_val = os.environ.get(env_key)
    if env_val and env_val.strip():
        return Path(env_val.strip()).expanduser().resolve()
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA", "")
        if not base:
            base = Path.home() / "AppData" / "Local"
        else:
            base = Path(base)
        return (base / "PCClientAgent" / "data").resolve()
    # Linux / XDG
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg and xdg.strip():
        base = Path(xdg.strip()).expanduser()
    else:
        base = Path.home() / ".local" / "share"
    return (base / "pcclient-agent").resolve()


def resolve_install_root(
    env_key: str = "PC_AGENT_INSTALL_ROOT",
    cli_value: Optional[str] = None,
) -> Path:
    """
    Корень установки (launcher, current.json, versions/).

    Windows: %LOCALAPPDATA%\\PCClientAgent\\install
    Linux: ~/.local/opt/pcclient-agent
    """
    if cli_value is not None and cli_value.strip():
        return Path(cli_value.strip()).expanduser().resolve()
    env_val = os.environ.get(env_key)
    if env_val and env_val.strip():
        return Path(env_val.strip()).expanduser().resolve()
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA", "")
        if not base:
            base = Path.home() / "AppData" / "Local"
        else:
            base = Path(base)
        return (base / "PCClientAgent" / "install").resolve()
    return (Path.home() / ".local" / "opt" / "pcclient-agent").resolve()


def resolve_logs_dir(data_root: Path) -> Path:
    """Директория логов: data_root/logs."""
    return data_root / "logs"


def resolve_storage_db_path(data_root: Path) -> Path:
    """Путь к SQLite БД: data_root/storage.db."""
    return data_root / "storage.db"


def resolve_modules_store(data_root: Path) -> Path:
    """Директория установленных пакетов модулей: data_root/modules_store."""
    return data_root / "modules_store"
