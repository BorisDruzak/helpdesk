"""Pure declarative descriptors for built-in agent tools.

This module must stay free of agent runtime imports so the server can resolve
module-default schemas for core builtins even before a fresh list_tools snapshot
has been persisted.
"""

from __future__ import annotations

from typing import Any


INVENTORY_COLLECT_TOOL_ID = "inventory.collect"
PRESENCE_COLLECT_TOOL_ID = "presence.collect"


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
                "serial_number": {"type": "string"},
                "manufacturer": {"type": "string"},
                "model": {"type": "string"},
                "bios_version": {"type": "string"},
                "asset_tag": {"type": "string"},
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
                            "driver": {"type": "string"},
                            "uri": {"type": "string"},
                            "location": {"type": "string"},
                            "is_network": {"type": "boolean"},
                            "is_shared": {"type": "boolean"},
                            "queue_length": {"type": "integer"},
                            "last_error": {"type": ["string", "null"]},
                        },
                    },
                },
                "warnings": {"type": "array", "items": {"type": "string"}},
            },
        },
        "software": {
            "type": "object",
            "properties": {
                "profile_version": {"type": "string"},
                "key_apps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "name": {"type": "string"},
                            "present": {"type": "boolean"},
                            "version": {"type": "string"},
                            "source": {"type": "string"},
                            "path": {"type": "string"},
                            "status": {"type": "string"},
                            "warnings": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                },
                "warnings": {"type": "array", "items": {"type": "string"}},
            },
        },
        "processes": {
            "type": "object",
            "properties": {
                "count": {"type": "integer"},
                "limit": {"type": "integer"},
                "truncated": {"type": "boolean"},
                "sort_by": {"type": "string"},
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "pid": {"type": "integer"},
                            "name": {"type": "string"},
                            "status": {"type": "string"},
                            "username": {"type": "string"},
                            "cpu_percent": {"type": "number"},
                            "memory_rss_bytes": {"type": "integer"},
                            "memory_mb": {"type": "number"},
                            "created_at": {"type": "string", "format": "date-time"},
                        },
                    },
                },
                "warnings": {"type": "array", "items": {"type": "string"}},
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
        "slots": ["identity", "health", "platform", "hardware", "network", "printers", "processes", "software", "agent"],
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
                {"path": "identity.domain", "label": "Домен/рабочая группа", "empty_text": "-"},
                {"path": "identity.fqdn", "label": "FQDN", "empty_text": "-"},
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
                {"path": "hardware.manufacturer", "label": "Производитель", "empty_text": "-"},
                {"path": "hardware.model", "label": "Модель", "empty_text": "-"},
                {"path": "hardware.serial_number", "label": "Серийный номер", "empty_text": "-", "copyable": True},
                {"path": "hardware.asset_tag", "label": "Asset tag", "empty_text": "-", "copyable": True},
                {"path": "hardware.bios_version", "label": "BIOS", "empty_text": "-"},
                {"path": "hardware.cpu_model", "label": "CPU", "empty_text": "-"},
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
                {"path": "filesystem", "label": "ФС", "empty_text": "-"},
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
                {"path": "mac", "label": "MAC", "empty_text": "-"},
                {"path": "ipv4", "label": "IPv4"},
                {"path": "ipv6", "label": "IPv6"},
                {"path": "speed_mbps", "label": "Скорость", "unit": "Мбит/с", "empty_text": "-"},
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
                {"path": "status", "label": "Статус", "empty_text": "-"},
                {"path": "driver", "label": "Драйвер", "empty_text": "-"},
                {"path": "uri", "label": "URI", "empty_text": "-"},
                {"path": "location", "label": "Локация", "empty_text": "-"},
                {"path": "queue_length", "label": "Очередь"},
            ],
        },
        {
            "type": "table",
            "id": "processes",
            "title": "Процессы",
            "rows_path": "processes.items",
            "columns": [
                {"path": "name", "label": "Процесс"},
                {"path": "pid", "label": "PID"},
                {"path": "status", "label": "Статус", "empty_text": "-"},
                {"path": "cpu_percent", "label": "CPU", "unit": "%", "format": "percent"},
                {"path": "memory_mb", "label": "RAM", "unit": "MB"},
                {"path": "username", "label": "Пользователь", "empty_text": "-"},
            ],
        },
        {
            "type": "checklist",
            "id": "warnings",
            "title": "Предупреждения",
            "items_path": "warnings",
        },
        {"type": "raw_json", "collapsed": True},
    ],
    "fallback": {"show_raw_json": True},
}


PRESENCE_COLLECT_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "schema_version": {"type": "string"},
        "collected_at": {"type": "string", "format": "date-time"},
        "agent": {
            "type": "object",
            "properties": {
                "online": {"type": "boolean"},
                "last_heartbeat_at": {"type": "string", "format": "date-time"},
                "connection_state": {"type": "string"},
                "agent_uptime_seconds": {"type": "integer"},
            },
        },
        "session": {
            "type": "object",
            "properties": {
                "current_user": {"type": "string"},
                "session_state": {"type": "string"},
                "locked": {"type": "boolean"},
                "idle_seconds": {"type": "integer"},
                "last_input_at": {"type": "string", "format": "date-time"},
                "session_started_at": {"type": "string", "format": "date-time"},
            },
        },
        "today": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "format": "date"},
                "active_seconds": {"type": "integer"},
                "idle_seconds": {"type": "integer"},
                "locked_seconds": {"type": "integer"},
                "offline_seconds": {"type": "integer"},
                "unknown_seconds": {"type": "integer"},
            },
        },
        "warnings": {"type": "array", "items": {"type": "string"}},
    },
}


PRESENCE_COLLECT_OUTPUT_CONTRACT: dict[str, Any] = {
    "kind": "device.presence.snapshot",
    "version": "1.0",
    "device_card": {
        "eligible": True,
        "slots": ["presence", "agent", "activity"],
        "priority": 80,
    },
    "privacy": {
        "purpose": "technical endpoint availability and workplace presence state",
        "collects_content": False,
        "forbidden": [
            "screenshots",
            "keystrokes",
            "mouse_coordinates",
            "browser_history",
            "full_urls",
            "document_contents",
            "clipboard_contents",
            "messages",
        ],
    },
    "evidence": {
        "domain": "endpoint",
        "perspective": "presence",
    },
}


PRESENCE_COLLECT_PRESENTATION_SCHEMA: dict[str, Any] = {
    "version": "1.0",
    "kind": "tool_result",
    "title": "Присутствие рабочего места",
    "summary": {
        "title_path": "session.current_user",
        "subtitle_template": "{{session.session_state}} · idle {{session.idle_seconds}} с",
        "status_path": "session.session_state",
    },
    "blocks": [
        {
            "type": "field_grid",
            "id": "presence_current",
            "title": "Текущее состояние",
            "fields": [
                {"path": "agent.online", "label": "Агент онлайн"},
                {"path": "agent.connection_state", "label": "Соединение"},
                {"path": "session.current_user", "label": "Сеанс"},
                {"path": "session.session_state", "label": "Состояние"},
                {"path": "session.locked", "label": "Экран заблокирован"},
                {"path": "session.idle_seconds", "label": "Простой", "format": "duration_seconds"},
                {
                    "path": "session.last_input_at",
                    "label": "Последняя активность ввода",
                    "format": "datetime",
                    "empty_text": "-",
                },
                {"path": "collected_at", "label": "Собрано", "format": "datetime"},
            ],
        },
        {
            "type": "metric_cards",
            "id": "presence_today",
            "title": "Сводка за сегодня",
            "metrics": [
                {"path": "today.active_seconds", "label": "Активно", "format": "duration_seconds"},
                {"path": "today.idle_seconds", "label": "Простой", "format": "duration_seconds"},
                {"path": "today.locked_seconds", "label": "Заблокировано", "format": "duration_seconds"},
                {"path": "today.offline_seconds", "label": "Офлайн", "format": "duration_seconds"},
                {"path": "today.unknown_seconds", "label": "Неизвестно", "format": "duration_seconds"},
            ],
        },
        {
            "type": "checklist",
            "id": "presence_warnings",
            "title": "Предупреждения",
            "items_path": "warnings",
        },
        {"type": "raw_json", "collapsed": True},
    ],
    "fallback": {"show_raw_json": True},
}


BUILTIN_TOOL_DESCRIPTORS: dict[str, dict[str, Any]] = {
    INVENTORY_COLLECT_TOOL_ID: {
        "id": INVENTORY_COLLECT_TOOL_ID,
        "title": "Inventory collect",
        "description": "Privacy-safe endpoint inventory snapshot",
        "provider_id": "inventory",
        "provider_type": "agent_builtin",
        "execution_target": "agent_builtin",
        "tool_kind": "inventory",
        "risk_level": "low",
        "side_effects": False,
        "requires_device": True,
        "requires_agent_online": True,
        "platforms": ["win32", "linux"],
        "params_schema": {"type": "object", "additionalProperties": False, "properties": {}},
        "output_schema": INVENTORY_COLLECT_OUTPUT_SCHEMA,
        "output_contract": INVENTORY_COLLECT_OUTPUT_CONTRACT,
        "presentation_schema": INVENTORY_COLLECT_PRESENTATION_SCHEMA,
        "source": "agent_builtin",
    },
    PRESENCE_COLLECT_TOOL_ID: {
        "id": PRESENCE_COLLECT_TOOL_ID,
        "title": "Presence collect",
        "description": "Privacy-safe workplace presence and session state snapshot",
        "provider_id": "presence",
        "provider_type": "agent_builtin",
        "execution_target": "agent_builtin",
        "tool_kind": "presence",
        "risk_level": "low",
        "side_effects": False,
        "requires_device": True,
        "requires_agent_online": True,
        "platforms": ["win32", "linux"],
        "params_schema": {"type": "object", "additionalProperties": False, "properties": {}},
        "output_schema": PRESENCE_COLLECT_OUTPUT_SCHEMA,
        "output_contract": PRESENCE_COLLECT_OUTPUT_CONTRACT,
        "presentation_schema": PRESENCE_COLLECT_PRESENTATION_SCHEMA,
        "source": "agent_builtin",
    }
}


def get_builtin_tool_descriptor(tool_id: str) -> dict[str, Any] | None:
    descriptor = BUILTIN_TOOL_DESCRIPTORS.get(tool_id)
    if descriptor is None:
        return None
    return dict(descriptor)
