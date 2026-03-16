#!/usr/bin/env python3
"""
Smoke-check модуля при upload (фаза 2b Playbook).

Запускается изолированно (subprocess от сервера): загружает модуль из распакованной
директории через loader, регистрирует в registry, вызывает list_tools.
Выход 0 + JSON с tools_count при успехе; 1 + сообщение в stderr при ошибке.

Использование:
  PYTHONPATH=<project_root> python3 pc_agent/scripts/smoke_check_module.py --dir /path/to/extracted
  или из корня проекта:
  python3 -m pc_agent.scripts.smoke_check_module --dir /path/to/extracted
"""

import argparse
import json
import sys
from pathlib import Path


def _ensure_paths() -> None:
    """Добавляет корень проекта в sys.path для импорта pc_agent."""
    script_dir = Path(__file__).resolve().parent
    pc_agent_root = script_dir.parent
    project_root = pc_agent_root.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


def _quiet_logs() -> None:
    """Снижает шум loguru в subprocess, чтобы stderr содержал только итог smoke."""
    try:
        import loguru
        loguru.logger.remove()
        loguru.logger.add(sys.stderr, level="WARNING")
    except Exception:
        pass


def find_module_root(extract_dir: Path) -> Path | None:
    """Находит директорию, содержащую manifest.json (корень модуля)."""
    extract_dir = Path(extract_dir)
    if not extract_dir.is_dir():
        return None
    if (extract_dir / "manifest.json").exists():
        return extract_dir
    for p in extract_dir.rglob("manifest.json"):
        if p.is_file():
            return p.parent
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-check модуля: load, register, list_tools")
    parser.add_argument("--dir", required=True, type=Path, help="Директория с распакованным ZIP модуля")
    args = parser.parse_args()
    extract_dir = args.dir.resolve()
    if not extract_dir.is_dir():
        print("smoke_check_module: --dir must be an existing directory", file=sys.stderr)
        return 1
    _ensure_paths()
    _quiet_logs()
    from pc_agent.core.loader import DynamicModuleLoader
    from pc_agent.core.registry import ModuleRegistry
    module_root = find_module_root(extract_dir)
    if not module_root:
        print("smoke_check_module: manifest.json not found under --dir", file=sys.stderr)
        return 1
    manifest_path = module_root / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"smoke_check_module: invalid manifest.json: {e}", file=sys.stderr)
        return 1
    module_name = (manifest.get("module_name") or "").strip()
    entrypoint = (manifest.get("entrypoint") or "module:register").strip()
    if not module_name:
        print("smoke_check_module: manifest.json missing module_name", file=sys.stderr)
        return 1
    # Проверка ОС: если в manifest указаны platforms и не "any", текущая ОС должна входить в список
    platforms = manifest.get("platforms")
    if platforms is not None and isinstance(platforms, list) and len(platforms) > 0:
        if "any" not in [str(p).lower() for p in platforms]:
            import platform
            current = (platform.system() or sys.platform or "").lower()
            if current == "darwin":
                current = "darwin"
            elif current == "windows":
                current = "win32"
            elif current == "linux":
                current = "linux"
            else:
                current = (sys.platform or "").lower()
            allowed = [str(p).lower() for p in platforms]
            if current not in allowed:
                print(
                    f"smoke_check_module: module not supported on this OS: current={current!r}, supported={allowed}",
                    file=sys.stderr
                )
                return 1
    try:
        # data_root чтобы не вызывать get_config() (конфиг в subprocess не инициализирован)
        import tempfile
        dummy_data = Path(tempfile.gettempdir()) / "pc_agent_smoke"
        loader = DynamicModuleLoader(data_root=dummy_data)
        registry = ModuleRegistry()
        instance = loader.load_module_from_path(module_name, module_root, entrypoint=entrypoint)
        registry.register(instance)
        tools = registry.get_tools_flat()
        tool_details = []
        for tool in tools:
            tool_name = tool.get("tool")
            resolved = registry.get_tool(tool_name) if tool_name else None
            tool_details.append(
                {
                    "tool": tool_name,
                    "module": tool.get("module"),
                    "method_name": resolved.get("method_name") if resolved else None,
                }
            )
        out = {"ok": True, "tools_count": len(tools), "tools": tool_details}
        print(json.dumps(out, ensure_ascii=False))
        return 0
    except Exception as e:
        print(f"smoke_check_module: load/register failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
