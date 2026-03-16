"""
Toolset hash computation utility.

Provides canonical hash computation for tool lists.
"""
import hashlib
import json
from typing import List, Dict, Any


def compute_toolset_hash(tools_list: List[Dict[str, Any]]) -> str:
    """
    Compute SHA256 hash of canonical JSON representation.
    
    КРИТИЧНО: tools_list должен быть уже отсортирован по name/id перед вызовом!
    Эта функция не сортирует - сортировка выполняется в обработчике command_result.
    
    Args:
        tools_list: List of tool dictionaries (предполагается отсортированным)
        
    Returns:
        First 16 hex characters of SHA256 hash
    
    Example:
        >>> tools = [{"name": "tool1", "id": "1"}, {"name": "tool2", "id": "2"}]
        >>> # tools должен быть отсортирован перед вызовом
        >>> sorted_tools = sorted(tools, key=lambda t: t.get("name") or t.get("tool_id", ""))
        >>> hash_value = compute_toolset_hash(sorted_tools)
    """
    # Создаем canonical JSON structure
    canonical = {"tools": tools_list}
    
    # Преобразуем в JSON с фиксированным порядком ключей
    # sort_keys=True обеспечивает детерминированный порядок внутри каждого tool
    # separators убирают лишние пробелы
    # ensure_ascii=False сохраняет Unicode символы
    json_str = json.dumps(
        canonical,
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=False
    )
    
    # Вычисляем SHA256 hash
    hash_bytes = hashlib.sha256(json_str.encode('utf-8')).digest()
    
    # Возвращаем первые 16 символов hex представления (64 бита)
    return hash_bytes.hex()[:16]


def sort_tools(tools_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Sort tools list by name or tool_id for canonical ordering.
    
    This ensures that the same set of tools always produces the same hash,
    regardless of their original order.
    
    Args:
        tools_list: List of tool dictionaries (unsorted)
        
    Returns:
        Sorted list of tool dictionaries
    
    Example:
        >>> tools = [{"name": "ztool"}, {"name": "atool"}]
        >>> sorted_tools = sort_tools(tools)
        >>> sorted_tools[0]["name"]
        'atool'
    """
    return sorted(
        tools_list,
        key=lambda t: t.get("name") or t.get("tool_id", "")
    )
