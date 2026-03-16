# Modules Terminology

Документация терминов для модульной системы.

## Термины

### Tool
Атомарное действие, вызываемое через `run_tool`, всегда принадлежит модулю.

### Module
Пакет кода, поставляющий 0..N tools (может быть без tools).

### SoT tools list
`device_toolset_snapshots.toolset_json` (полный список tools в JSONB).

### SoT module state
`device_modules` (сервер) + агентская FS (`modules_store/{name}/{version}`).

### Инвариант
После `activate` → должен появиться `tools_changed` → сервер обновляет snapshot.

## Семантика состояний device_modules

- `installed` / `active` = модуль установлен/активен (из inventory)
- `missing` = модуль был в registry, но отсутствует в inventory (не удаляем строку для истории)
- `removed` = модуль явно удален через remove/uninstall команду


