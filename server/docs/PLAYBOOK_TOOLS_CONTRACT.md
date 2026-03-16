# Контракт list_tools и run_tool для Playbook и каталога команд

**Назначение:** закрепить обязательные метаданные инструментов и коды ошибок run_tool для этапов 9–11 (Capability Gate, каталог 100–150 команд).

---

## list_tools: метаданные на каждый tool

Рекомендуемые/целевые поля в каждом элементе списка инструментов (для capability gate и каталога):

| Поле | Тип | Описание |
|------|-----|----------|
| tool | string | Имя в формате `module.tool` (обязательно). |
| domain | string | Домен: system, process, filesystem, network, service, security, diag, ui. |
| platforms | string[] | Поддерживаемые платформы (например `["linux","windows"]`). |
| risk_level | string | Уровень риска (например low, medium, high). |
| requires_consent | bool | Требуется ли подтверждение перед выполнением. |
| timeout_sec | int | Таймаут исполнения (секунды). |
| idempotent | bool | Идемпотентность операции. |
| allow_roles | string[] | Роли, которым разрешён вызов. |
| scopes | string[] | Скоупы доступа. |
| origin | string | Этап 10: `builtin` \| `managed` для drift (опционально). |

Сервер при обработке list_tools snapshot валидирует обязательные поля (domain, platforms, risk_level, requires_consent, timeout_sec, idempotent). Команда без обязательных metadata не попадает в production catalog (см. `utils/tool_metadata_validation.py`). У старых агентов при пустом результате фильтрации в snapshot сохраняется полный список (обратная совместимость).

---

## run_tool: коды ошибок

Единые коды ошибок в ответе агента (error.code / error_json):

| Код | Описание |
|-----|----------|
| INVALID_TOOL_FORMAT | Некорректный формат имени (требуется `module.tool`). |
| TOOL_NOT_FOUND | Инструмент не найден. |
| UNSUPPORTED_CAPABILITY | Инструмент недоступен или не поддерживается (в т.ч. платформа). |
| CONSENT_REQUIRED | Требуется подтверждение пользователя. |
| TIMEOUT | Превышен таймаут исполнения. |
| COMMAND_FAILED | Команда выполнена с ошибкой (не таймаут, не consent). |

Сервер при Capability Gate до отправки команды может установить step_run в failed с кодами:

- **UNSUPPORTED_CAPABILITY** — tool нет в toolset или не подходит платформа.
- **TOOL_UNAVAILABLE** — нет snapshot toolset или устройство не найдено.

---

## Связанные документы

- `PLAYBOOK_STAGES_7_12.md` — этапы 7–12.
- `pc_agent/docs/TOOLS_CONTRACT.md` — контракт на стороне агента.
