"""Static key-application detection profiles for inventory.collect.

The detector is intentionally narrow: it checks trusted, hardcoded hints for a
small set of support-relevant applications and never enumerates all installed
software or user files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os
import platform
import re
import shutil
import subprocess
from typing import Any


@dataclass(frozen=True)
class KeyAppProfile:
    app_id: str
    name: str
    linux_paths: tuple[str, ...] = ()
    linux_commands: tuple[tuple[str, ...], ...] = ()
    windows_paths: tuple[str, ...] = ()
    windows_commands: tuple[tuple[str, ...], ...] = ()
    windows_registry: tuple[tuple[str, str], ...] = ()


KEY_APP_PROFILES: list[KeyAppProfile] = [
    KeyAppProfile(
        "libreoffice",
        "LibreOffice",
        linux_paths=("/usr/bin/libreoffice", "/usr/local/bin/libreoffice", "/snap/bin/libreoffice"),
        linux_commands=(("libreoffice", "--version"),),
        windows_paths=(
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        ),
        windows_commands=((r"C:\Program Files\LibreOffice\program\soffice.exe", "--version"),),
        windows_registry=((r"SOFTWARE\LibreOffice\LibreOffice", "Path"),),
    ),
    KeyAppProfile(
        "r7_office",
        "Р7-Офис",
        linux_paths=("/usr/bin/r7-office", "/opt/r7-office/program/desktopeditors"),
        windows_paths=(r"C:\Program Files\R7-Office\DesktopEditors\DesktopEditors.exe",),
    ),
    KeyAppProfile(
        "yandex_browser",
        "Yandex Browser",
        linux_paths=("/usr/bin/yandex-browser", "/opt/yandex/browser/yandex_browser"),
        linux_commands=(("yandex-browser", "--version"),),
        windows_paths=(r"C:\Program Files\Yandex\YandexBrowser\Application\browser.exe",),
    ),
    KeyAppProfile(
        "chromium_or_chrome",
        "Chromium / Chrome",
        linux_paths=("/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser"),
        linux_commands=(("google-chrome", "--version"), ("chromium", "--version"), ("chromium-browser", "--version")),
        windows_paths=(
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ),
    ),
    KeyAppProfile(
        "kaspersky",
        "Kaspersky",
        linux_paths=("/opt/kaspersky/kesl/bin/kesl-control",),
        linux_commands=(("/opt/kaspersky/kesl/bin/kesl-control", "--app-info"),),
        windows_paths=(r"C:\Program Files (x86)\Kaspersky Lab", r"C:\Program Files\Kaspersky Lab"),
    ),
    KeyAppProfile(
        "vipnet",
        "ViPNet",
        linux_paths=("/usr/bin/vipnetclient", "/opt/vipnet"),
        windows_paths=(r"C:\Program Files\InfoTeCS", r"C:\Program Files (x86)\InfoTeCS"),
    ),
    KeyAppProfile(
        "openvpn",
        "OpenVPN",
        linux_paths=("/usr/sbin/openvpn", "/usr/bin/openvpn"),
        linux_commands=(("openvpn", "--version"),),
        windows_paths=(r"C:\Program Files\OpenVPN\bin\openvpn.exe",),
    ),
    KeyAppProfile(
        "anydesk",
        "AnyDesk",
        linux_paths=("/usr/bin/anydesk",),
        linux_commands=(("anydesk", "--version"),),
        windows_paths=(r"C:\Program Files (x86)\AnyDesk\AnyDesk.exe", r"C:\Program Files\AnyDesk\AnyDesk.exe"),
    ),
    KeyAppProfile(
        "rustdesk",
        "RustDesk",
        linux_paths=("/usr/bin/rustdesk",),
        windows_paths=(r"C:\Program Files\RustDesk\rustdesk.exe",),
    ),
    KeyAppProfile(
        "directum_client",
        "Directum Client",
        windows_paths=(r"C:\Program Files (x86)\DIRECTUM Company", r"C:\Program Files\DIRECTUM Company"),
    ),
    KeyAppProfile(
        "vk_workspace",
        "VK Workspace",
        windows_paths=(r"C:\Program Files\VK Teams", r"C:\Program Files (x86)\VK Teams"),
    ),
]


def parse_version_from_output(output: str) -> str:
    match = re.search(r"\b\d+(?:\.\d+){1,4}\b", output or "")
    return match.group(0) if match else ""


def _safe_path_exists(path: str) -> bool:
    try:
        expanded = os.path.expandvars(os.path.expanduser(path))
        return Path(expanded).exists()
    except Exception:
        return False


def _safe_command_path(command: tuple[str, ...]) -> tuple[str, ...] | None:
    if not command:
        return None
    executable = command[0]
    if any(sep in executable for sep in ("/", "\\")):
        return command if _safe_path_exists(executable) else None
    resolved = shutil.which(executable)
    if not resolved:
        return None
    return (resolved, *command[1:])


def _run_version_command(command: tuple[str, ...]) -> tuple[bool, str, str | None]:
    resolved = _safe_command_path(command)
    if not resolved:
        return False, "", None
    try:
        completed = subprocess.run(
            list(resolved),
            check=False,
            capture_output=True,
            text=True,
            timeout=2.0,
            encoding="utf-8",
            errors="replace",
        )
    except Exception as exc:
        return True, "", str(exc)
    output = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
    return True, parse_version_from_output(output), None


def _windows_registry_present(profile: KeyAppProfile) -> tuple[bool, str]:
    if platform.system().lower() != "windows" or not profile.windows_registry:
        return False, ""
    try:
        import winreg  # type: ignore[import-not-found]
    except Exception:
        return False, ""

    hives = (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER)
    for key_path, value_name in profile.windows_registry:
        for hive in hives:
            try:
                with winreg.OpenKey(hive, key_path) as key:
                    value, _ = winreg.QueryValueEx(key, value_name)
                    return True, str(value or "")
            except OSError:
                continue
    return False, ""


def _detect_profile(profile: KeyAppProfile, os_name: str, warnings: list[str]) -> dict[str, Any]:
    is_windows = os_name == "windows"
    paths = profile.windows_paths if is_windows else profile.linux_paths
    commands = profile.windows_commands if is_windows else profile.linux_commands

    present = False
    source = "unknown"
    found_path = ""
    version = ""
    item_warnings: list[str] = []

    for path in paths:
        if _safe_path_exists(path):
            present = True
            source = "path"
            found_path = os.path.expandvars(os.path.expanduser(path))
            break

    if not present:
        for command in commands:
            command_present, command_version, error = _run_version_command(command)
            if error:
                item_warnings.append(error)
            if command_present:
                present = True
                source = "command"
                version = command_version
                found_path = command[0]
                break

    if not present and is_windows:
        registry_present, registry_value = _windows_registry_present(profile)
        if registry_present:
            present = True
            source = "registry"
            found_path = registry_value

    if item_warnings:
        warnings.append(f"{profile.app_id} detection warning: {'; '.join(item_warnings)}")

    return {
        "id": profile.app_id,
        "name": profile.name,
        "present": present,
        "version": version,
        "source": source if present else "unknown",
        "path": found_path,
        "status": "ok" if present else "missing",
        "warnings": item_warnings,
    }


def detect_key_apps(warnings: list[str] | None = None, *, os_name: str | None = None) -> dict[str, Any]:
    warnings = warnings if warnings is not None else []
    normalized_os = (os_name or platform.system()).lower()
    items: list[dict[str, Any]] = []
    for profile in KEY_APP_PROFILES:
        try:
            items.append(_detect_profile(profile, normalized_os, warnings))
        except Exception as exc:
            message = f"{profile.app_id} detection failed: {exc}"
            warnings.append(message)
            items.append(
                {
                    "id": profile.app_id,
                    "name": profile.name,
                    "present": False,
                    "version": "",
                    "source": "unknown",
                    "path": "",
                    "status": "unknown",
                    "warnings": [message],
                }
            )
    return {"profile_version": "1.0", "key_apps": items, "warnings": []}
