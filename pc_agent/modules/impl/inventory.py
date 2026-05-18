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
import socket
from typing import Any

import psutil

from pc_agent.core.database import PROTOCOL_VERSION
from pc_agent.core.registry import exposed_tool
from pc_agent.modules.base_module import BaseCollector
from pc_agent.version import AGENT_VERSION


INVENTORY_COLLECT_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "schema_version": {"type": "string"},
        "collected_at": {"type": "string", "format": "date-time"},
        "identity": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string"},
                "hostname": {"type": "string"},
                "fqdn": {"type": "string"},
                "current_user": {"type": "string"},
                "domain": {"type": "string"},
            },
        },
        "agent": {
            "type": "object",
            "properties": {
                "version": {"type": "string"},
                "protocol_version": {"type": "string"},
                "toolset_hash": {"type": "string"},
                "module_count": {"type": "integer"},
            },
        },
        "platform": {
            "type": "object",
            "properties": {
                "os_name": {"type": "string"},
                "os_version": {"type": "string"},
                "os_release": {"type": "string"},
                "architecture": {"type": "string"},
                "machine": {"type": "string"},
                "boot_time": {"type": "string", "format": "date-time"},
                "uptime_seconds": {"type": "integer"},
            },
        },
        "hardware": {
            "type": "object",
            "properties": {
                "cpu_model": {"type": "string"},
                "cpu_cores": {"type": "integer"},
                "cpu_logical": {"type": "integer"},
                "memory_total_bytes": {"type": "integer"},
                "memory_available_bytes": {"type": "integer"},
                "memory_percent": {"type": "number"},
            },
        },
        "resources": {
            "type": "object",
            "properties": {
                "cpu_percent": {"type": "number"},
                "memory_percent": {"type": "number"},
                "disks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "mount": {"type": "string"},
                            "filesystem": {"type": "string"},
                            "total_bytes": {"type": "integer"},
                            "free_bytes": {"type": "integer"},
                            "used_percent": {"type": "number"},
                        },
                    },
                },
            },
        },
        "network": {
            "type": "object",
            "properties": {
                "primary_ip": {"type": "string"},
                "primary_mac": {"type": "string"},
                "default_gateway": {"type": "string"},
                "dns_servers": {"type": "array", "items": {"type": "string"}},
                "interfaces": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "status": {"type": "string"},
                            "up": {"type": "boolean"},
                            "mac": {"type": "string"},
                            "ipv4": {"type": "array", "items": {"type": "string"}},
                            "ipv6": {"type": "array", "items": {"type": "string"}},
                            "speed_mbps": {"type": "integer"},
                        },
                    },
                },
            },
        },
        "printers": {
            "type": "object",
            "properties": {
                "default_printer": {"type": "string"},
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "is_default": {"type": "boolean"},
                            "status": {"type": "string"},
                        },
                    },
                },
            },
        },
        "software": {
            "type": "object",
            "properties": {
                "key_apps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "version": {"type": "string"},
                            "present": {"type": "boolean"},
                        },
                    },
                }
            },
        },
        "warnings": {"type": "array", "items": {"type": "string"}},
    },
}


INVENTORY_COLLECT_OUTPUT_CONTRACT: dict[str, Any] = {
    "kind": "device.inventory.snapshot",
    "version": "1.0",
    "device_card": {
        "eligible": True,
        "slots": ["identity", "health", "platform", "hardware", "network", "printers", "software", "agent"],
        "priority": 100,
    },
    "evidence": {
        "passport_eligible": True,
        "domain": "endpoint",
        "perspective": "endpoint",
    },
}


INVENTORY_COLLECT_PRESENTATION_SCHEMA: dict[str, Any] = {
    "version": "1.0",
    "kind": "tool_result",
    "title": "Инвентарь устройства",
    "summary": {
        "title_path": "identity.hostname",
        "subtitle_template": "{{platform.os_name}} {{platform.os_version}} · {{network.primary_ip}}",
        "status_path": "status",
    },
    "blocks": [
        {
            "type": "field_grid",
            "id": "identity",
            "title": "Идентификация",
            "fields": [
                {"path": "identity.hostname", "label": "Имя ПК", "copyable": True},
                {"path": "network.primary_ip", "label": "IP-адрес", "copyable": True},
                {"path": "identity.current_user", "label": "Пользователь"},
                {"path": "identity.domain", "label": "Домен/рабочая группа", "empty_text": "—"},
                {"path": "identity.fqdn", "label": "FQDN", "empty_text": "—"},
                {"path": "collected_at", "label": "Собрано", "format": "datetime"},
            ],
        },
        {
            "type": "metric_cards",
            "id": "resources",
            "title": "Состояние",
            "metrics": [
                {"path": "resources.cpu_percent", "label": "CPU", "unit": "%", "format": "percent"},
                {"path": "resources.memory_percent", "label": "RAM", "unit": "%", "format": "percent"},
                {"path": "platform.uptime_seconds", "label": "Uptime", "format": "duration_seconds"},
            ],
        },
        {
            "type": "field_grid",
            "id": "os_agent",
            "title": "ОС и агент",
            "fields": [
                {"path": "platform.os_name", "label": "ОС"},
                {"path": "platform.os_version", "label": "Версия"},
                {"path": "platform.os_release", "label": "Релиз"},
                {"path": "platform.architecture", "label": "Архитектура"},
                {"path": "platform.machine", "label": "Машина"},
                {"path": "agent.version", "label": "Версия агента"},
                {"path": "agent.protocol_version", "label": "Протокол"},
            ],
        },
        {
            "type": "field_grid",
            "id": "hardware",
            "title": "Железо",
            "fields": [
                {"path": "hardware.cpu_model", "label": "CPU", "empty_text": "—"},
                {"path": "hardware.cpu_cores", "label": "Ядра"},
                {"path": "hardware.cpu_logical", "label": "Потоки"},
                {"path": "hardware.memory_total_bytes", "label": "Память", "format": "bytes"},
                {"path": "hardware.memory_available_bytes", "label": "Доступно", "format": "bytes"},
            ],
        },
        {
            "type": "table",
            "id": "disks",
            "title": "Диски",
            "rows_path": "resources.disks",
            "columns": [
                {"path": "name", "label": "Диск"},
                {"path": "mount", "label": "Точка"},
                {"path": "filesystem", "label": "ФС", "empty_text": "—"},
                {"path": "total_bytes", "label": "Всего", "format": "bytes"},
                {"path": "free_bytes", "label": "Свободно", "format": "bytes"},
                {"path": "used_percent", "label": "Занято", "unit": "%", "format": "percent"},
            ],
        },
        {
            "type": "table",
            "id": "network_interfaces",
            "title": "Сетевые интерфейсы",
            "rows_path": "network.interfaces",
            "columns": [
                {"path": "name", "label": "Интерфейс"},
                {"path": "status", "label": "Статус"},
                {"path": "mac", "label": "MAC", "empty_text": "—"},
                {"path": "ipv4", "label": "IPv4"},
                {"path": "ipv6", "label": "IPv6"},
                {"path": "speed_mbps", "label": "Скорость", "unit": "Мбит/с", "empty_text": "—"},
            ],
        },
        {
            "type": "table",
            "id": "printers",
            "title": "Принтеры",
            "rows_path": "printers.items",
            "columns": [
                {"path": "name", "label": "Имя"},
                {"path": "is_default", "label": "По умолчанию"},
                {"path": "status", "label": "Статус", "empty_text": "—"},
            ],
        },
        {
            "type": "table",
            "id": "software",
            "title": "Ключевое ПО",
            "rows_path": "software.key_apps",
            "columns": [
                {"path": "name", "label": "Приложение"},
                {"path": "version", "label": "Версия", "empty_text": "—"},
                {"path": "present", "label": "Найдено"},
            ],
        },
        {"type": "raw_json", "collapsed": True},
    ],
    "fallback": {"show_raw_json": True},
}


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

    def _collect_printers(self, warnings: list[str]) -> dict[str, Any]:
        if platform.system().lower() != "windows":
            self._warn(warnings, "printer collection is not implemented for this OS")
            return {"default_printer": "", "items": []}
        try:
            import win32print  # type: ignore[import-not-found]
        except Exception as exc:
            self._warn(warnings, "printer collection requires Windows print APIs", exc)
            return {"default_printer": "", "items": []}

        try:
            default_printer = win32print.GetDefaultPrinter() or ""
        except Exception:
            default_printer = ""
        items: list[dict[str, Any]] = []
        try:
            for printer in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS):
                name = str(printer[2] or "")
                items.append({"name": name, "is_default": name == default_printer, "status": ""})
        except Exception as exc:
            self._warn(warnings, "printer list is unavailable", exc)
        return {"default_printer": default_printer, "items": items}

    def _collect_software(self, warnings: list[str]) -> dict[str, Any]:
        self._warn(warnings, "key application detection is not implemented in inventory.collect v1")
        return {"key_apps": []}

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
                "warnings": warnings,
            }
