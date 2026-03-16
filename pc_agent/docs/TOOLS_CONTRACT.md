# Контракт инструментов (list_tools / run_tool)

Единый контракт имён и метаданных для атомарных команд агента (Этап 3 внедрения Playbook).

**Версия:** 1.0  
**Дата:** 2026-02-21  

---

## 1. Именование: только `module.tool`

- **list_tools** возвращает каждый инструмент с полем `tool` в формате **`module.tool`** (например `ping_check.ping_host`, `system.collect`). Короткое имя без модуля не используется.
- **run_tool** принимает только полное имя в формате `module.tool`. Если передано короткое имя (без точки), агент возвращает детерминированную ошибку:
  - **code:** `INVALID_TOOL_FORMAT`
  - **message:** «Используйте формат "module.tool" (например ping_check.ping_host). Короткое имя не поддерживается.»

### Где реализовано

- `pc_agent/core/registry.py`: `get_tools_flat()` всегда формирует `tool` как `f"{module_name}.{tool_name}"`; `get_tool(tool_name)` возвращает `None`, если в `tool_name` нет точки.
- `pc_agent/core/orchestrator.py`: в обработчике `run_tool` при отсутствии точки в `tool` сразу возвращается `fail(code="INVALID_TOOL_FORMAT", ...)`.

---

## 2. Метаданные инструмента (целевой контракт)

Для каждого инструмента в `list_tools` в `spec` и/или `metadata` целесообразно иметь (для Playbook и PolicyEngine):

| Поле | Описание | По умолчанию в реестре |
|------|----------|-------------------------|
| `risk_level` | Уровень риска (safe_readonly, safe_read, system_write и т.д.) | `safe_readonly` |
| `metadata.requires_consent` | Требуется ли согласие пользователя | `False` |
| `metadata.scopes` | Области доступа | `[]` |
| `metadata.allow_roles` | Допустимые роли | `None` (проверка по policy) |

В дальнейших этапах могут быть добавлены: `platforms`, `timeout_sec`, `idempotent`, каталог по домену (system/process/filesystem/network/…).

---

## 3. Коды ошибок run_tool

| Код | Когда |
|-----|--------|
| `INVALID_TOOL_FORMAT` | Передано короткое имя (нет точки в `tool`). |
| `TOOL_NOT_FOUND` | Имя в формате `module.tool`, но инструмент не найден в реестре. |
| `MODULE_NOT_FOUND` | Модуль не загружен или не найден. |
| `TOOL_NOT_CALLABLE` | Атрибут не является вызываемым. |
| `INVALID_PARAMS` | Ошибка валидации параметров (например Pydantic). |

---

## 4. Связанные документы

- `pc_agent/docs/MODULES.md` — регистрация модулей и `@exposed_tool`.
- `server/docs/PLAYBOOK_IMPLEMENTATION.md` — этапы внедрения и контракт на стороне сервера.
- `server/docs/MODULES_API.md` — API модулей и инструментов.


## Update 2026-03-11

### Tool alias contract
- Public tool name is the `module.tool` alias exposed to the server/UI.
- Runtime invocation uses `real_method_name` resolved from the registry descriptor.
- Smoke/runtime checks now distinguish between declared tool alias and Python method name.
