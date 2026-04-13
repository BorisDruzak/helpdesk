from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Optional, Tuple


_MACHINE_ID_NAMESPACE = uuid.UUID("2f691b98-9bb8-4bd9-96d6-e5aa89bb1d8c")


def _is_valid_uuid(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = uuid.UUID(value.strip())
    except (ValueError, TypeError, AttributeError):
        return False
    return str(parsed) == value.strip().lower()


def _stable_uuid_from_seed(seed: str, source: str) -> str:
    normalized_seed = (seed or "").strip()
    if not normalized_seed:
        raise ValueError("seed must not be empty")
    return str(uuid.uuid5(_MACHINE_ID_NAMESPACE, f"{source}:{normalized_seed}"))


def _read_text(path: Path) -> Optional[str]:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return value or None


def _resolve_from_env() -> Optional[Tuple[str, str]]:
    raw = (os.environ.get("PC_AGENT_MACHINE_ID") or "").strip()
    if not raw:
        return None
    if _is_valid_uuid(raw):
        return raw.lower(), "env_uuid"
    return _stable_uuid_from_seed(raw, "env_seed"), "env_seed"


def _resolve_windows_machine_guid() -> Optional[Tuple[str, str]]:
    if os.name != "nt":
        return None
    try:
        import winreg
    except ImportError:
        return None

    flags = getattr(winreg, "KEY_READ", 0)
    wow64 = getattr(winreg, "KEY_WOW64_64KEY", 0)
    for access in (flags | wow64, flags):
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", 0, access) as key:
                machine_guid, _ = winreg.QueryValueEx(key, "MachineGuid")
        except OSError:
            continue
        value = str(machine_guid or "").strip()
        if value:
            return _stable_uuid_from_seed(value, "windows_machine_guid"), "windows_machine_guid"
    return None


def _resolve_linux_machine_id() -> Optional[Tuple[str, str]]:
    if os.name == "nt":
        return None
    for candidate in (Path("/etc/machine-id"), Path("/var/lib/dbus/machine-id")):
        value = _read_text(candidate)
        if value:
            return _stable_uuid_from_seed(value, f"linux_machine_id:{candidate}"), "linux_machine_id"
    return None


def _default_fallback_file() -> Path:
    env_path = (os.environ.get("PC_AGENT_MACHINE_ID_FILE") or "").strip()
    if env_path:
        return Path(env_path).expanduser()
    if os.name == "nt":
        base = (os.environ.get("PROGRAMDATA") or "").strip()
        root = Path(base).expanduser() if base else Path("C:/ProgramData")
        return root / "PCClientAgent" / "machine_id"
    return Path.home() / ".config" / "pcclient-agent" / "machine_id"


def _resolve_from_fallback_file(path: Optional[Path] = None) -> Tuple[str, str]:
    target = (path or _default_fallback_file()).expanduser()
    existing = _read_text(target)
    if existing:
        if _is_valid_uuid(existing):
            return existing.lower(), f"file_uuid:{target}"
        stable = _stable_uuid_from_seed(existing, f"file_seed:{target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(stable, encoding="utf-8")
        return stable, f"file_seed:{target}"

    machine_id = str(uuid.uuid4())
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(machine_id, encoding="utf-8")
    return machine_id, f"file_uuid:{target}"


def resolve_machine_identity(*, fallback_file: Optional[Path] = None) -> Tuple[str, str]:
    for resolver in (
        _resolve_from_env,
        _resolve_windows_machine_guid,
        _resolve_linux_machine_id,
    ):
        resolved = resolver()
        if resolved is not None:
            return resolved
    return _resolve_from_fallback_file(path=fallback_file)
