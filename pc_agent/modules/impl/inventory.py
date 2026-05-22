"""
Privacy-safe endpoint inventory collector.

The collector returns a normalized snapshot intended for device cards and
support diagnostics. It avoids user-content collection and performs only
bounded read-only OS queries.
"""

from __future__ import annotations

from datetime import datetime, timezone
import getpass
import os
import platform
from pathlib import Path
import re
import shutil
import socket
import subprocess
import time
from typing import Any

import psutil

from pc_agent.core.database import PROTOCOL_VERSION
from pc_agent.core.registry import exposed_tool
from pc_agent.modules.base_module import BaseCollector
from pc_agent.modules.impl.inventory_profiles import detect_key_apps
from pc_agent.version import AGENT_VERSION
from shared.builtin_tool_descriptors import (
    INVENTORY_COLLECT_OUTPUT_CONTRACT,
    INVENTORY_COLLECT_OUTPUT_SCHEMA,
    INVENTORY_COLLECT_PRESENTATION_SCHEMA,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _iso_from_epoch(epoch_seconds: float | int | None) -> str:
    if not epoch_seconds:
        return ""
    return datetime.fromtimestamp(float(epoch_seconds), tz=timezone.utc).isoformat().replace("+00:00", "Z")


class InventoryCollector(BaseCollector):
    @property
    def name(self) -> str:
        return "inventory"

    def _warn(self, warnings: list[str], message: str, exc: BaseException | None = None) -> None:
        if exc is None:
            warnings.append(message)
        else:
            warnings.append(f"{message}: {exc}")

    def _guess_primary_ip(self) -> str:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.settimeout(1.0)
                sock.connect(("8.8.8.8", 80))
                return str(sock.getsockname()[0])
        except Exception:
            try:
                hostname = socket.gethostname()
                ip = socket.gethostbyname(hostname)
                return "" if ip.startswith("127.") else ip
            except Exception:
                return ""

    def _collect_identity(self, warnings: list[str]) -> dict[str, Any]:
        hostname = socket.gethostname()
        try:
            current_user = getpass.getuser()
        except Exception as exc:
            current_user = ""
            self._warn(warnings, "current user is unavailable", exc)
        domain = os.environ.get("USERDOMAIN") or os.environ.get("USERDNSDOMAIN") or ""
        return {
            "device_id": os.environ.get("PC_AGENT_DEVICE_ID", ""),
            "hostname": hostname,
            "fqdn": socket.getfqdn() or "",
            "current_user": current_user,
            "domain": domain,
        }

    def _collect_platform(self, warnings: list[str]) -> dict[str, Any]:
        boot_epoch = None
        try:
            boot_epoch = psutil.boot_time()
        except Exception as exc:
            self._warn(warnings, "boot time is unavailable", exc)
        uptime_seconds = int(datetime.now(timezone.utc).timestamp() - boot_epoch) if boot_epoch else 0
        return {
            "os_name": platform.system(),
            "os_version": platform.version(),
            "os_release": platform.release(),
            "architecture": platform.architecture()[0],
            "machine": platform.machine(),
            "boot_time": _iso_from_epoch(boot_epoch),
            "uptime_seconds": uptime_seconds,
        }

    def _collect_memory(self, warnings: list[str]) -> Any | None:
        try:
            return psutil.virtual_memory()
        except Exception as exc:
            self._warn(warnings, "memory metrics are unavailable", exc)
            return None

    def _collect_cpu_percent(self, warnings: list[str]) -> float:
        try:
            return float(psutil.cpu_percent(interval=0.1))
        except Exception as exc:
            self._warn(warnings, "CPU metrics are unavailable", exc)
            return 0.0

    def _collect_disks(self, warnings: list[str]) -> list[dict[str, Any]]:
        disks: list[dict[str, Any]] = []
        partitions = psutil.disk_partitions(all=False)
        for partition in partitions:
            try:
                usage = psutil.disk_usage(partition.mountpoint)
            except Exception as exc:
                self._warn(warnings, f"disk usage is unavailable for {partition.mountpoint}", exc)
                continue
            disks.append(
                {
                    "name": partition.device or partition.mountpoint,
                    "mount": partition.mountpoint,
                    "filesystem": partition.fstype or "",
                    "total_bytes": int(usage.total),
                    "free_bytes": int(usage.free),
                    "used_percent": float(usage.percent),
                }
            )
        return disks

    def _collect_dns_servers(self, warnings: list[str]) -> list[str]:
        if platform.system().lower() != "linux":
            self._warn(warnings, "DNS server collection is not implemented for this OS")
            return []
        try:
            servers: list[str] = []
            with open("/etc/resolv.conf", "r", encoding="utf-8") as fh:
                for line in fh:
                    stripped = line.strip()
                    if stripped.startswith("nameserver "):
                        servers.append(stripped.split()[1])
            return servers
        except Exception as exc:
            self._warn(warnings, "DNS servers are unavailable", exc)
            return []

    def _collect_interfaces(self, primary_ip: str, warnings: list[str]) -> tuple[list[dict[str, Any]], str]:
        interfaces: list[dict[str, Any]] = []
        primary_mac = ""
        try:
            addrs = psutil.net_if_addrs()
            stats = psutil.net_if_stats()
        except Exception as exc:
            self._warn(warnings, "network interfaces are unavailable", exc)
            return interfaces, primary_mac

        for name, iface_addrs in addrs.items():
            ipv4: list[str] = []
            ipv6: list[str] = []
            mac = ""
            for addr in iface_addrs:
                family_name = str(addr.family)
                if addr.family == socket.AF_INET:
                    ipv4.append(addr.address)
                elif addr.family == socket.AF_INET6:
                    ipv6.append(addr.address.split("%")[0])
                elif "AF_LINK" in family_name or "AF_PACKET" in family_name:
                    mac = addr.address
            stat = stats.get(name)
            if primary_ip and primary_ip in ipv4:
                primary_mac = mac
            interfaces.append(
                {
                    "name": name,
                    "status": "up" if stat and stat.isup else "down",
                    "up": bool(stat and stat.isup),
                    "mac": mac,
                    "ipv4": ipv4,
                    "ipv6": ipv6,
                    "speed_mbps": int(stat.speed) if stat and stat.speed > 0 else 0,
                }
            )
        return interfaces, primary_mac

    def _clean_hardware_value(self, value: str | None) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            return ""
        lowered = cleaned.lower()
        if lowered in {"none", "unknown", "not specified", "to be filled by o.e.m.", "default string"}:
            return ""
        return cleaned

    def _read_text_file(self, path: str) -> str:
        try:
            return Path(path).read_text(encoding="utf-8", errors="replace").strip()
        except Exception:
            return ""

    def _run_fixed_command(self, args: list[str], *, timeout: float = 2.0) -> str:
        if not args:
            return ""
        executable = args[0]
        if not any(sep in executable for sep in ("/", "\\")):
            resolved = shutil.which(executable)
            if not resolved:
                return ""
            args = [resolved, *args[1:]]
        try:
            completed = subprocess.run(
                args,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
            )
        except Exception:
            return ""
        return (completed.stdout or completed.stderr or "").strip()

    def _collect_hardware_identifiers(self, warnings: list[str]) -> dict[str, Any]:
        result = {
            "serial_number": "",
            "manufacturer": "",
            "model": "",
            "bios_version": "",
            "asset_tag": "",
        }
        os_name = platform.system().lower()
        if os_name == "linux":
            dmi_paths = {
                "serial_number": "/sys/class/dmi/id/product_serial",
                "manufacturer": "/sys/class/dmi/id/sys_vendor",
                "model": "/sys/class/dmi/id/product_name",
                "bios_version": "/sys/class/dmi/id/bios_version",
                "asset_tag": "/sys/class/dmi/id/chassis_asset_tag",
            }
            for key, path in dmi_paths.items():
                result[key] = self._clean_hardware_value(self._read_text_file(path))
            if not any(result.values()):
                self._warn(warnings, "hardware identifiers are unavailable on this Linux host")
            return result

        if os_name == "windows":
            commands = {
                "serial_number": ["wmic", "bios", "get", "serialnumber", "/value"],
                "manufacturer": ["wmic", "computersystem", "get", "manufacturer", "/value"],
                "model": ["wmic", "computersystem", "get", "model", "/value"],
                "bios_version": ["wmic", "bios", "get", "smbiosbiosversion", "/value"],
                "asset_tag": ["wmic", "systemenclosure", "get", "smbiosassettag", "/value"],
            }
            for key, args in commands.items():
                output = self._run_fixed_command(args)
                match = re.search(r"=(.+)", output)
                value = match.group(1) if match else output.splitlines()[-1] if output.splitlines() else ""
                result[key] = self._clean_hardware_value(value)
            if not any(result.values()):
                self._warn(warnings, "hardware identifiers are unavailable on this Windows host")
            return result

        self._warn(warnings, "hardware identifier collection is not implemented for this OS")
        return result

    def _empty_printers(self, warning: str | None = None) -> dict[str, Any]:
        warnings = [warning] if warning else []
        return {"default_printer": "", "items": [], "warnings": warnings}

    def _collect_linux_printers(self, warnings: list[str]) -> dict[str, Any]:
        if not shutil.which("lpstat"):
            message = "CUPS lpstat is unavailable; printer inventory is partial"
            self._warn(warnings, message)
            return self._empty_printers(message)

        default_printer = ""
        default_output = self._run_fixed_command(["lpstat", "-d"])
        if ":" in default_output and "no system default" not in default_output.lower():
            default_printer = default_output.split(":", 1)[1].strip()

        uris: dict[str, str] = {}
        for line in self._run_fixed_command(["lpstat", "-v"]).splitlines():
            if line.startswith("device for ") and ":" in line:
                left, uri = line.split(":", 1)
                name = left.replace("device for ", "", 1).strip()
                uris[name] = uri.strip()

        status_by_name: dict[str, str] = {}
        for line in self._run_fixed_command(["lpstat", "-p"]).splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[0] == "printer":
                name = parts[1]
                lowered = line.lower()
                if "disabled" in lowered or "stopped" in lowered:
                    status = "stopped"
                elif "printing" in lowered:
                    status = "printing"
                elif "idle" in lowered or "enabled" in lowered:
                    status = "idle"
                else:
                    status = "unknown"
                status_by_name[name] = status

        names = sorted(set(uris) | set(status_by_name) | ({default_printer} if default_printer else set()))
        items = []
        for name in names:
            uri = uris.get(name, "")
            is_network = uri.startswith(("ipp://", "ipps://", "http://", "https://", "socket://", "lpd://", "smb://"))
            items.append(
                {
                    "name": name,
                    "is_default": name == default_printer,
                    "status": status_by_name.get(name, "unknown"),
                    "driver": "",
                    "uri": uri,
                    "location": "",
                    "is_network": is_network,
                    "is_shared": False,
                    "queue_length": 0,
                    "last_error": None,
                }
            )
        return {"default_printer": default_printer, "items": items, "warnings": []}

    def _windows_printer_status(self, status_code: Any) -> str:
        try:
            code = int(status_code or 0)
        except Exception:
            return "unknown"
        if code == 0:
            return "idle"
        if code & 0x00000400:
            return "printing"
        if code & 0x00000080 or code & 0x00000200:
            return "stopped"
        return "unknown"

    def _collect_windows_printers(self, warnings: list[str]) -> dict[str, Any]:
        try:
            import win32print  # type: ignore[import-not-found]
        except Exception as exc:
            message = f"printer collection requires Windows print APIs: {exc}"
            self._warn(warnings, message)
            return self._empty_printers(message)

        try:
            default_printer = win32print.GetDefaultPrinter() or ""
        except Exception:
            default_printer = ""
        items: list[dict[str, Any]] = []
        try:
            flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
            for printer in win32print.EnumPrinters(flags, None, 2):
                data = printer if isinstance(printer, dict) else {}
                name = str(data.get("pPrinterName") or (printer[2] if len(printer) > 2 else "") or "")
                attrs = int(data.get("Attributes") or 0)
                status = data.get("Status")
                items.append(
                    {
                        "name": name,
                        "is_default": name == default_printer,
                        "status": self._windows_printer_status(status),
                        "driver": str(data.get("pDriverName") or ""),
                        "uri": str(data.get("pPortName") or ""),
                        "location": str(data.get("pLocation") or ""),
                        "is_network": bool(attrs & getattr(win32print, "PRINTER_ATTRIBUTE_NETWORK", 0x10)),
                        "is_shared": bool(attrs & getattr(win32print, "PRINTER_ATTRIBUTE_SHARED", 0x8)),
                        "queue_length": int(data.get("cJobs") or 0),
                        "last_error": None,
                    }
                )
        except Exception as exc:
            self._warn(warnings, "printer list is unavailable", exc)
        return {"default_printer": default_printer, "items": items, "warnings": []}

    def _collect_printers(self, warnings: list[str]) -> dict[str, Any]:
        os_name = platform.system().lower()
        if os_name == "linux":
            return self._collect_linux_printers(warnings)
        if os_name == "windows":
            return self._collect_windows_printers(warnings)
        message = "printer collection is not implemented for this OS"
        self._warn(warnings, message)
        return self._empty_printers(message)

    def _collect_software(self, warnings: list[str]) -> dict[str, Any]:
        return detect_key_apps(warnings, os_name=platform.system())

    def _collect_processes(self, warnings: list[str], *, limit: int = 50, sort_by: str = "memory") -> dict[str, Any]:
        process_warnings: list[str] = []
        processes: list[dict[str, Any]] = []

        try:
            probes = list(psutil.process_iter(["pid", "name"]))
            for proc in probes:
                try:
                    proc.cpu_percent(interval=None)
                except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
                    continue
            time.sleep(0.05)

            for proc in psutil.process_iter(["pid", "name", "status", "username", "create_time"]):
                try:
                    info = proc.info
                    memory_rss_bytes = 0
                    try:
                        memory_rss_bytes = int(proc.memory_info().rss)
                    except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
                        pass
                    try:
                        cpu_percent = float(proc.cpu_percent(interval=None))
                    except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
                        cpu_percent = 0.0
                    processes.append(
                        {
                            "pid": int(info.get("pid") or 0),
                            "name": str(info.get("name") or ""),
                            "status": str(info.get("status") or "unknown"),
                            "username": str(info.get("username") or ""),
                            "cpu_percent": round(cpu_percent, 2),
                            "memory_rss_bytes": memory_rss_bytes,
                            "memory_mb": round(memory_rss_bytes / (1024 * 1024), 2),
                            "created_at": _iso_from_epoch(info.get("create_time")),
                        }
                    )
                except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
                    continue
        except Exception as exc:
            self._warn(warnings, "process list is unavailable", exc)
            process_warnings.append(str(exc))

        if sort_by == "cpu":
            processes.sort(
                key=lambda item: (
                    float(item.get("cpu_percent") or 0.0),
                    int(item.get("memory_rss_bytes") or 0),
                ),
                reverse=True,
            )
        else:
            processes.sort(
                key=lambda item: (
                    int(item.get("memory_rss_bytes") or 0),
                    float(item.get("cpu_percent") or 0.0),
                ),
                reverse=True,
            )

        count = len(processes)
        return {
            "count": count,
            "limit": limit,
            "truncated": count > limit,
            "sort_by": sort_by,
            "items": processes[:limit],
            "warnings": process_warnings,
        }

    @exposed_tool(
        name="collect",
        description="Collect a privacy-safe endpoint inventory snapshot for device cards",
        risk_level="safe_readonly",
        output_schema=INVENTORY_COLLECT_OUTPUT_SCHEMA,
        output_contract=INVENTORY_COLLECT_OUTPUT_CONTRACT,
        presentation_schema=INVENTORY_COLLECT_PRESENTATION_SCHEMA,
    )
    async def collect(self) -> dict[str, Any]:
        warnings: list[str] = []
        with self.trace_span("tool.entry", details={"tool": "inventory.collect"}):
            memory = self._collect_memory(warnings)
            cpu_percent = self._collect_cpu_percent(warnings)
            primary_ip = self._guess_primary_ip()

            try:
                disks = self._collect_disks(warnings)
            except Exception as exc:
                disks = []
                self._warn(warnings, "disk collector unavailable", exc)

            interfaces, primary_mac = self._collect_interfaces(primary_ip, warnings)
            printers = self._collect_printers(warnings)
            software = self._collect_software(warnings)
            processes = self._collect_processes(warnings)

            return {
                "schema_version": "1.0",
                "collected_at": _utc_now_iso(),
                "identity": self._collect_identity(warnings),
                "agent": {
                    "version": AGENT_VERSION,
                    "protocol_version": PROTOCOL_VERSION,
                    "toolset_hash": os.environ.get("PC_AGENT_TOOLSET_HASH", ""),
                    "module_count": 0,
                },
                "platform": self._collect_platform(warnings),
                "hardware": {
                    "cpu_model": platform.processor() or "",
                    "cpu_cores": int(psutil.cpu_count(logical=False) or 0),
                    "cpu_logical": int(psutil.cpu_count(logical=True) or 0),
                    "memory_total_bytes": int(memory.total) if memory is not None else 0,
                    "memory_available_bytes": int(memory.available) if memory is not None else 0,
                    "memory_percent": float(memory.percent) if memory is not None else 0.0,
                    **self._collect_hardware_identifiers(warnings),
                },
                "resources": {
                    "cpu_percent": cpu_percent,
                    "memory_percent": float(memory.percent) if memory is not None else 0.0,
                    "disks": disks,
                },
                "network": {
                    "primary_ip": primary_ip,
                    "primary_mac": primary_mac,
                    "default_gateway": "",
                    "dns_servers": self._collect_dns_servers(warnings),
                    "interfaces": interfaces,
                },
                "printers": printers,
                "software": software,
                "processes": processes,
                "warnings": warnings,
            }
