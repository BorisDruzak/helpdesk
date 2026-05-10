from __future__ import annotations

import hashlib
import ctypes
import os
import platform
import re
import socket
import subprocess
from typing import Any

try:
    import psutil
except Exception:  # pragma: no cover - optional runtime dependency guard
    psutil = None  # type: ignore[assignment]


FINGERPRINT_SCHEMA = "device_fingerprint_v1"
_SALT = "pc_client_device_fingerprint_v1"


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _hash(value: Any) -> str | None:
    normalized = _norm(value)
    if not normalized or normalized in {"none", "unknown", "to be filled by o.e.m.", "default string"}:
        return None
    return hashlib.sha256(f"{_SALT}:{normalized}".encode("utf-8")).hexdigest()


def _run_text(command: list[str], *, timeout: float = 2.5) -> str | None:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            timeout=timeout,
            check=False,
            shell=False,
        )
    except Exception:
        return None
    output = completed.stdout or completed.stderr
    if not output:
        return None
    for encoding in ("utf-8-sig", "utf-16", "cp866", "cp1251"):
        try:
            text = output.decode(encoding).strip()
        except Exception:
            continue
        if text:
            return text
    return output.decode("utf-8", errors="ignore").strip() or None


def _powershell_value(script: str) -> str | None:
    text = _run_text(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ]
    )
    if not text:
        return None
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else None


def _windows_system_uuid() -> str | None:
    return _powershell_value("(Get-CimInstance Win32_ComputerSystemProduct).UUID")


def _windows_machine_guid() -> str | None:
    if os.name != "nt":
        return None
    try:
        import winreg
    except Exception:
        return None
    flags = getattr(winreg, "KEY_READ", 0)
    wow64 = getattr(winreg, "KEY_WOW64_64KEY", 0)
    for access in (flags | wow64, flags):
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", 0, access) as key:
                value, _ = winreg.QueryValueEx(key, "MachineGuid")
        except OSError:
            continue
        text = str(value or "").strip()
        if text:
            return text
    return None


def _windows_baseboard() -> str | None:
    return _powershell_value(
        "$b=Get-CimInstance Win32_BaseBoard; @($b.Manufacturer,$b.Product,$b.SerialNumber) -join '|'"
    )


def _windows_boot_volume() -> str | None:
    drive = os.environ.get("SystemDrive", "C:")
    root = drive if drive.endswith("\\") else f"{drive}\\"
    serial = ctypes.c_uint32(0)
    try:
        ok = ctypes.windll.kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p(root),
            None,
            0,
            ctypes.byref(serial),
            None,
            None,
            None,
            0,
        )
    except Exception:
        return None
    if not ok:
        return None
    return f"{serial.value:08x}"


def _windows_allow_wmi_fingerprint() -> bool:
    return str(os.environ.get("PC_AGENT_ENABLE_WMI_FINGERPRINT") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _read_first(paths: list[str]) -> str | None:
    for raw_path in paths:
        try:
            value = open(raw_path, "r", encoding="utf-8", errors="ignore").read().strip()
        except Exception:
            continue
        if value:
            return value
    return None


def _linux_system_uuid() -> str | None:
    return _read_first(["/sys/class/dmi/id/product_uuid", "/sys/class/dmi/id/product_serial"])


def _linux_baseboard() -> str | None:
    board = _read_first(["/sys/class/dmi/id/board_name"]) or ""
    vendor = _read_first(["/sys/class/dmi/id/board_vendor"]) or ""
    serial = _read_first(["/sys/class/dmi/id/board_serial"]) or ""
    return "|".join(part for part in (vendor, board, serial) if part) or None


def _linux_boot_volume() -> str | None:
    text = _run_text(["findmnt", "-no", "UUID,SOURCE", "/"])
    return text.strip() if text else None


def _cpu_signature() -> str:
    return "|".join(
        str(part)
        for part in (
            platform.system(),
            platform.machine(),
            platform.processor(),
            os.cpu_count(),
        )
        if part
    )


def _mac_hashes() -> list[str]:
    if psutil is None:
        return []
    result: set[str] = set()
    try:
        addrs = psutil.net_if_addrs()
    except Exception:
        return []
    for entries in addrs.values():
        for entry in entries:
            address = str(getattr(entry, "address", "") or "").strip().lower()
            if not address or address in {"00:00:00:00:00:00", "ff:ff:ff:ff:ff:ff"}:
                continue
            if not re.fullmatch(r"[0-9a-f]{2}([-:][0-9a-f]{2}){5}", address):
                continue
            hashed = _hash(address.replace("-", ":"))
            if hashed:
                result.add(hashed)
    return sorted(result)


def collect_device_fingerprint() -> dict[str, Any]:
    system = platform.system().lower()
    if system == "windows":
        system_uuid = _windows_machine_guid()
        baseboard = _windows_baseboard() if _windows_allow_wmi_fingerprint() else None
        boot_volume = _windows_boot_volume()
    elif system == "linux":
        system_uuid = _linux_system_uuid()
        baseboard = _linux_baseboard()
        boot_volume = _linux_boot_volume()
    else:
        system_uuid = None
        baseboard = None
        boot_volume = None

    components = {
        key: value
        for key, value in {
            "system_uuid": _hash(system_uuid),
            "baseboard": _hash(baseboard),
            "cpu": _hash(_cpu_signature()),
            "boot_volume": _hash(boot_volume),
        }.items()
        if value
    }
    mac_hashes = _mac_hashes()
    return {
        "schema": FINGERPRINT_SCHEMA,
        "components": components,
        "mac_hashes": mac_hashes,
        "summary": {
            "component_count": len(components),
            "mac_count": len(mac_hashes),
            "hostname_hash": _hash(socket.gethostname()),
            "platform": platform.system(),
        },
    }
