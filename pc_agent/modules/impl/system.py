"""
System information collector with presets and section-based output.
"""

import platform
import socket
from pathlib import Path
from typing import Any, Dict, Optional

import psutil
from loguru import logger
from pydantic import BaseModel

from pc_agent.modules.base_module import BaseCollector
from pc_agent.core.registry import exposed_tool


SYSTEM_PRESETS: dict[str, dict[str, bool]] = {
    "minimal": {
        "include_cpu": True,
        "include_memory": True,
        "include_disk": False,
        "include_network": False,
        "include_hostname": False,
        "include_ip": False,
        "include_platform": False,
        "include_boot_time": False,
    },
    "basic": {
        "include_cpu": True,
        "include_memory": True,
        "include_disk": True,
        "include_network": False,
        "include_hostname": True,
        "include_ip": False,
        "include_platform": False,
        "include_boot_time": False,
    },
    "identity": {
        "include_cpu": False,
        "include_memory": False,
        "include_disk": False,
        "include_network": True,
        "include_hostname": True,
        "include_ip": True,
        "include_platform": True,
        "include_boot_time": False,
    },
    "network": {
        "include_cpu": False,
        "include_memory": False,
        "include_disk": False,
        "include_network": True,
        "include_hostname": True,
        "include_ip": True,
        "include_platform": False,
        "include_boot_time": False,
    },
    "full": {
        "include_cpu": True,
        "include_memory": True,
        "include_disk": True,
        "include_network": True,
        "include_hostname": True,
        "include_ip": True,
        "include_platform": True,
        "include_boot_time": True,
    },
}


class SystemCollectParams(BaseModel):
    preset: str = "basic"
    include_cpu: Optional[bool] = None
    include_memory: Optional[bool] = None
    include_disk: Optional[bool] = None
    include_network: Optional[bool] = None
    include_hostname: Optional[bool] = None
    include_ip: Optional[bool] = None
    include_platform: Optional[bool] = None
    include_boot_time: Optional[bool] = None


SYSTEM_COLLECT_OUTPUT_CONTRACT: Dict[str, Any] = {
    "kind": "endpoint.system_snapshot",
    "version": "1.0.0",
    "status_path": "status",
    "summary_path": "sections.network.hostname",
    "device_card": {
        "eligible": True,
        "slots": ["identity", "health", "network", "platform"],
        "priority": 100,
    },
}


SYSTEM_COLLECT_PRESENTATION_SCHEMA: Dict[str, Any] = {
    "version": "1.0",
    "kind": "tool_result",
    "title": "Системная информация",
    "summary": {
        "title_path": "sections.network.hostname",
        "subtitle_template": "{{sections.platform.system}} {{sections.platform.release}} · {{sections.network.primary_ip}}",
        "status_path": "status",
    },
    "blocks": [
        {
            "type": "field_grid",
            "id": "identity",
            "title": "Идентификация",
            "fields": [
                {"path": "sections.network.hostname", "label": "Имя ПК", "copyable": True},
                {"path": "sections.network.primary_ip", "label": "IP-адрес", "copyable": True},
                {"path": "sections.platform.system", "label": "Система"},
                {"path": "sections.platform.release", "label": "Релиз"},
                {"path": "sections.platform.machine", "label": "Архитектура"},
            ],
        },
        {
            "type": "metric_cards",
            "id": "resources",
            "title": "Ресурсы",
            "metrics": [
                {"path": "sections.cpu.percent", "label": "CPU", "unit": "%", "format": "percent"},
                {"path": "sections.memory.percent", "label": "RAM", "unit": "%", "format": "percent"},
                {"path": "sections.disk.percent", "label": "Disk", "unit": "%", "format": "percent"},
                {"path": "sections.boot_time.epoch", "label": "Boot time", "format": "datetime"},
            ],
        },
        {
            "type": "table",
            "id": "network_interfaces",
            "title": "Сетевые интерфейсы",
            "rows_path": "sections.network.interfaces",
            "columns": [
                {"path": "name", "label": "Интерфейс"},
                {"path": "ipv4", "label": "IPv4"},
                {"path": "mac", "label": "MAC", "empty_text": "—"},
                {"path": "status", "label": "Статус", "empty_text": "—"},
            ],
        },
        {"type": "raw_json", "collapsed": True},
    ],
    "fallback": {"show_raw_json": True},
}


class SystemCollector(BaseCollector):
    @property
    def name(self) -> str:
        return "system"

    @staticmethod
    def _resolve_flags(**kwargs: Optional[bool]) -> dict[str, bool]:
        preset = str(kwargs.pop("preset", "basic") or "basic").strip().lower()
        resolved = dict(SYSTEM_PRESETS.get(preset, SYSTEM_PRESETS["basic"]))
        for key, value in kwargs.items():
            if value is not None:
                resolved[key] = bool(value)
        resolved["preset"] = preset
        return resolved

    @staticmethod
    def _guess_primary_ip(hostname: str) -> str:
        try:
            ip = socket.gethostbyname(hostname)
            if ip and not ip.startswith("127."):
                return ip
        except Exception:
            pass
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.connect(("8.8.8.8", 80))
                return sock.getsockname()[0]
        except Exception:
            return "unknown"

    @staticmethod
    def _disk_path() -> str:
        return str(Path.home().anchor or "/")

    @exposed_tool(
        name="collect",
        description="Collect system information using presets or explicit sections",
        risk_level="safe_readonly",
        params_model=SystemCollectParams,
        presets=[
            {
                "id": "minimal",
                "name": "Minimal",
                "description": "CPU and memory only",
                "params": {"preset": "minimal"},
            },
            {
                "id": "basic",
                "name": "Basic",
                "description": "CPU, memory, disk and hostname",
                "params": {"preset": "basic"},
            },
            {
                "id": "identity",
                "name": "Identity",
                "description": "Hostname, IP and platform details",
                "params": {"preset": "identity"},
            },
            {
                "id": "network",
                "name": "Network",
                "description": "Network-focused snapshot",
                "params": {"preset": "network"},
            },
            {
                "id": "full",
                "name": "Full",
                "description": "All available system sections",
                "params": {"preset": "full"},
            },
        ],
        output_schema={
            "type": "object",
            "properties": {
                "preset": {"type": "string"},
                "selected_sections": {"type": "array", "items": {"type": "string"}},
                "sections": {
                    "type": "object",
                    "properties": {
                        "cpu": {
                            "type": "object",
                            "properties": {
                                "percent": {"type": "number"},
                                "count": {"type": "integer"},
                            },
                        },
                        "memory": {
                            "type": "object",
                            "properties": {
                                "total": {"type": "integer"},
                                "available": {"type": "integer"},
                                "percent": {"type": "number"},
                            },
                        },
                        "disk": {
                            "type": "object",
                            "properties": {
                                "total": {"type": "integer"},
                                "used": {"type": "integer"},
                                "free": {"type": "integer"},
                                "percent": {"type": "number"},
                            },
                        },
                        "network": {
                            "type": "object",
                            "properties": {
                                "hostname": {"type": "string"},
                                "primary_ip": {"type": "string"},
                                "interfaces": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "name": {"type": "string"},
                                            "ipv4": {"type": "string"},
                                            "mac": {"type": "string"},
                                            "status": {"type": "string"},
                                        },
                                    },
                                },
                            },
                        },
                        "platform": {
                            "type": "object",
                            "properties": {
                                "system": {"type": "string"},
                                "release": {"type": "string"},
                                "version": {"type": "string"},
                                "machine": {"type": "string"},
                                "processor": {"type": "string"},
                            },
                        },
                        "boot_time": {
                            "type": "object",
                            "properties": {
                                "epoch": {"type": "number"},
                                "iso": {"type": "string"},
                            },
                        },
                    },
                },
            },
            "required": ["preset", "selected_sections", "sections"],
        },
        output_contract=SYSTEM_COLLECT_OUTPUT_CONTRACT,
        presentation_schema=SYSTEM_COLLECT_PRESENTATION_SCHEMA,
        metadata_risk_level="safe_read",
        metadata_scopes=[],
        metadata_requires_consent=False,
        contract_version="1.0.0",
        lifecycle="stable",
        error_codes=["VALIDATION_ERROR", "TIMEOUT"],
        redaction={"enabled": True, "allow_raw_sensitive_data": False, "redact_headers": True, "redact_env": True, "redact_fields": []},
        resources={"max_runtime_sec": 15, "max_artifact_count": 0, "max_artifact_bytes": 0},
        execution={
            "target": "agent_builtin",
            "requires_device": True,
            "requires_agent_online": True,
            "supports_auto_install": False,
            "requires_integration": False,
        },
        deployment={"provider_id": "system", "install_required_on_agent": False, "package_type": "builtin"},
        safety={"side_effects": False, "requires_consent": False, "idempotent": True},
        evidence={
            "produces_evidence": True,
            "kind": "endpoint.system_snapshot",
            "domain": "endpoint",
            "perspective": "endpoint",
            "passport_eligible": True,
        },
    )
    async def collect(
        self,
        preset: str = "basic",
        include_cpu: Optional[bool] = None,
        include_memory: Optional[bool] = None,
        include_disk: Optional[bool] = None,
        include_network: Optional[bool] = None,
        include_hostname: Optional[bool] = None,
        include_ip: Optional[bool] = None,
        include_platform: Optional[bool] = None,
        include_boot_time: Optional[bool] = None,
    ) -> Dict[str, Any]:
        with self.trace_span("tool.entry", details={"tool_name": "system.collect"}):
            return await self._collect_impl(
                preset=preset,
                include_cpu=include_cpu,
                include_memory=include_memory,
                include_disk=include_disk,
                include_network=include_network,
                include_hostname=include_hostname,
                include_ip=include_ip,
                include_platform=include_platform,
                include_boot_time=include_boot_time,
            )

    async def _collect_impl(
        self,
        preset: str = "basic",
        include_cpu: Optional[bool] = None,
        include_memory: Optional[bool] = None,
        include_disk: Optional[bool] = None,
        include_network: Optional[bool] = None,
        include_hostname: Optional[bool] = None,
        include_ip: Optional[bool] = None,
        include_platform: Optional[bool] = None,
        include_boot_time: Optional[bool] = None,
    ) -> Dict[str, Any]:
        flags = self._resolve_flags(
            preset=preset,
            include_cpu=include_cpu,
            include_memory=include_memory,
            include_disk=include_disk,
            include_network=include_network,
            include_hostname=include_hostname,
            include_ip=include_ip,
            include_platform=include_platform,
            include_boot_time=include_boot_time,
        )
        logger.debug(f"[{self.name}] collecting system info with flags={flags}")

        result: Dict[str, Any] = {
            "preset": flags["preset"],
            "selected_sections": [],
            "sections": {},
        }

        hostname = socket.gethostname()

        if flags["include_cpu"]:
            with self.trace_span("collect.cpu", details={"preset": flags["preset"]}):
                cpu_percent = psutil.cpu_percent(interval=1)
            cpu_info = {
                "percent": cpu_percent,
                "logical_cores": psutil.cpu_count(logical=True),
                "physical_cores": psutil.cpu_count(logical=False),
            }
            result["cpu"] = cpu_percent
            result["sections"]["cpu"] = cpu_info
            result["selected_sections"].append("cpu")

        if flags["include_memory"]:
            with self.trace_span("collect.memory"):
                memory = psutil.virtual_memory()
            memory_info = {
                "percent": memory.percent,
                "total_bytes": memory.total,
                "available_bytes": memory.available,
                "used_bytes": memory.used,
            }
            result["ram"] = memory.percent
            result["sections"]["memory"] = memory_info
            result["selected_sections"].append("memory")

        if flags["include_disk"]:
            with self.trace_span("collect.disk"):
                disk_path = self._disk_path()
                disk_usage = psutil.disk_usage(disk_path)
            disk_info = {
                "path": disk_path,
                "percent": disk_usage.percent,
                "total_bytes": disk_usage.total,
                "used_bytes": disk_usage.used,
                "free_bytes": disk_usage.free,
            }
            result["disk"] = disk_usage.percent
            result["sections"]["disk"] = disk_info
            result["selected_sections"].append("disk")

        if flags["include_hostname"] or flags["include_ip"] or flags["include_network"]:
            self.trace_event(
                "collect.network.identity",
                details={
                    "include_hostname": flags["include_hostname"],
                    "include_ip": flags["include_ip"],
                    "include_network": flags["include_network"],
                },
            )
            network_info: Dict[str, Any] = {}
            if flags["include_hostname"]:
                result["hostname"] = hostname
                network_info["hostname"] = hostname
            if flags["include_ip"]:
                primary_ip = self._guess_primary_ip(hostname)
                result["ip"] = primary_ip
                network_info["primary_ip"] = primary_ip
            if flags["include_network"]:
                interfaces = []
                for iface_name, addresses in psutil.net_if_addrs().items():
                    iface_entry = {"name": iface_name, "ipv4": [], "ipv6": []}
                    for address in addresses:
                        if address.family == socket.AF_INET:
                            iface_entry["ipv4"].append(address.address)
                        elif address.family == socket.AF_INET6:
                            iface_entry["ipv6"].append(address.address)
                    if iface_entry["ipv4"] or iface_entry["ipv6"]:
                        interfaces.append(iface_entry)
                network_info["interfaces"] = interfaces
                network_counters = psutil.net_io_counters()
                if network_counters:
                    network_info["io"] = {
                        "bytes_sent": network_counters.bytes_sent,
                        "bytes_recv": network_counters.bytes_recv,
                    }
            if network_info:
                result["sections"]["network"] = network_info
                result["selected_sections"].append("network")

        if flags["include_platform"]:
            with self.trace_span("collect.platform"):
                platform_info = {
                    "system": platform.system(),
                    "release": platform.release(),
                    "version": platform.version(),
                    "machine": platform.machine(),
                    "python_version": platform.python_version(),
                }
            result["sections"]["platform"] = platform_info
            result["selected_sections"].append("platform")

        if flags["include_boot_time"]:
            with self.trace_span("collect.boot_time"):
                boot_ts = psutil.boot_time()
            result["sections"]["boot_time"] = {"epoch": boot_ts}
            result["selected_sections"].append("boot_time")

        self.trace_event(
            "collect.summary",
            summary="system collect finished",
            details={"selected_sections": list(result["selected_sections"])},
        )

        return result
