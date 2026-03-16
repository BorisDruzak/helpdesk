"""
Утилита для вычисления стабильного хеша toolset.

Используется для синхронизации toolset с сервером и определения
необходимости обновления tools snapshot на сервере.
"""

import hashlib
import json
from typing import List, Dict, Any, Optional


def compute_toolset_hash(tools_list: List[Dict[str, Any]]) -> Optional[str]:
    """
    Вычисляет стабильный SHA-256 хеш от списка tools.
    
    Хеш основан на:
    - tool name (tool_id)
    - module name
    - spec (параметры и описание)
    
    Args:
        tools_list: Список tools в формате [{tool, module, spec}, ...]
    
    Returns:
        SHA-256 хеш в hex формате (64 символа) или None если список пуст
    
    Алгоритм гарантирует стабильность:
    - Детерминированная сортировка (по tool name)
    - Детерминированная сериализация JSON (sort_keys=True)
    - Фильтрация нестабильных полей (если будут добавлены)
    """
    if not tools_list:
        return None
    
    # Сортируем tools по имени для детерминированности
    sorted_tools = sorted(tools_list, key=lambda t: t.get('tool', ''))
    
    # Формируем стабильное представление для хеширования
    # Включаем только стабильные поля: tool, module, spec
    stable_repr = []
    for tool in sorted_tools:
        stable_tool = {
            'tool': tool.get('tool'),
            'module': tool.get('module'),
            'spec': tool.get('spec', {})
        }
        stable_repr.append(stable_tool)
    
    # Детерминированная сериализация
    json_repr = json.dumps(stable_repr, sort_keys=True, separators=(',', ':'))
    
    # SHA-256 хеш
    hash_bytes = hashlib.sha256(json_repr.encode('utf-8')).digest()
    return hash_bytes.hex()[:16]  # First 16 characters (как в плане, строка 264)


def verify_toolset_hash_stability(tools_list: List[Dict[str, Any]], expected_hash: str) -> bool:
    """
    Проверяет, что вычисленный хеш совпадает с ожидаемым.
    
    Используется для тестирования стабильности хеш-функции.
    
    Args:
        tools_list: Список tools
        expected_hash: Ожидаемый хеш
    
    Returns:
        True если хеши совпадают
    """
    computed = compute_toolset_hash(tools_list)
    return computed == expected_hash
def sort_tools(tools_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Сортирует список tools по полю 'tool' для канонического представления.
    
    Args:
        tools_list: List of tool dictionaries
        
    Returns:
        Отсортированный список tools
    """
    return sorted(tools_list, key=lambda t: t.get('tool', ''))