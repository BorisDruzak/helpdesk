"""
Контракт metadata для атомарных команд (production catalog).
Обязательные поля: domain, platforms, risk_level, requires_consent, timeout_sec, idempotent.
Команда без обязательных metadata не попадает в production catalog (snapshot для capability gate / run_tool).
"""
from typing import Dict, Any, List

REQUIRED_METADATA_KEYS = frozenset({
    "domain",
    "platforms",
    "risk_level",
    "requires_consent",
    "timeout_sec",
    "idempotent",
})


def tool_has_required_metadata(tool_entry: Dict[str, Any]) -> bool:
    """
    Проверяет наличие обязательных полей metadata у инструмента.
    Читает из формата snapshot: tool.spec.metadata (и fallback tool.metadata).
    """
    spec = tool_entry.get("spec") or {}
    meta = spec.get("metadata") or tool_entry.get("metadata") or {}
    return REQUIRED_METADATA_KEYS.issubset(meta.keys())


def filter_tools_production_catalog(tools_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Оставляет только инструменты с полным набором обязательных metadata.
    Используется при сохранении list_tools snapshot — в каталог попадают только валидные команды.
    """
    return [t for t in tools_list if tool_has_required_metadata(t)]
