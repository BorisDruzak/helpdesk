# AGENTS.md — инструкции для Codex (pc_agent)

Канон инструкций и доков — **локальная рабочая копия** монорепо; шара `\\192.168.100.17\NTFS_Share\pc_client` и Linux `/var/chat_bot/pc_client` — зеркала. См. корневой `AGENTS.md`.

## Главное про агента

- Роль: сбор данных на ПК, GUI (Qt), WebSocket клиент, модульная система, outbox/ACK доставка.
- Локальная БД агента: SQLite `data/storage.db` (см. `docs/DATABASE.md`).

## Документация, с которой начинать

- `docs/README.md`
- `docs/PROTOCOL_V3.md` (полная спецификация протокола)
- `docs/AUTHENTICATION.md` (источники токена: `AUTH_TOKEN` → `auth_tokens` → legacy `identity.json`)
- `docs/MODULES.md`, `docs/ORCHESTRATOR.md`, `docs/SENDER.md`
- `../server/docs/OBSERVER_LAYER.md` и `../server/docs/OBSERVER_AUTHORING_RULES.md`, если задача затрагивает action trace, module breadcrumbs, update trace или agent-side dangerous flow instrumentation

## Обязательное правило для новых модулей

- Каждый новый `BaseCollector`-модуль обязан использовать observer SDK из `pc_agent/modules/base_module.py`.
- Минимум: один верхнеуровневый `with self.trace_span("tool.entry", ...)` на каждый tool method и дополнительные `self.trace_event(...)` или `self.trace_span(...)` на опасных шагах (`subprocess`, `network`, `retry`, `timeout`, `artifact`, `consent`, `publish`).
- В `details` нельзя класть сырой токен, пароль, cookie, consent token или другие чувствительные поля; они должны идти через built-in redaction helpers.
- Если модуль создаётся через workbench/builder, generated scaffold с trace SDK нельзя удалять без осознанной замены эквивалентной инструментировкой.

## CODEMAP

- Каноническая карта агента — **только** `docs/CODEMAP.md` в этом дереве (путь от корня монорепо: `pc_agent/docs/CODEMAP.md`).
- Перед анализом/правками сначала смотреть этот файл.
- При изменении структуры агентского кода, точек входа или runtime-потоков **обязательно** обновлять `pc_agent/docs/CODEMAP.md`. Если меняется agent-side observer coverage, module breadcrumbs, action trace bridge или dangerous flow instrumentation, синхронно обновлять и `../server/docs/OBSERVER_LAYER.md` + `../server/docs/OBSERVER_AUTHORING_RULES.md`. Критерии — в конце файла, в `docs/QUICK_LOOKUP.md` и в корневом `AGENTS.md`.

## Инварианты Protocol V3

- Тип события определяется ТОЛЬКО по `device_seq` vs `agent_seq` (см. `docs/PROTOCOL_V3.md`).
- ACK удаляет outbox записи (нет статуса “sent” → ACK ⇒ DELETE) (см. `docs/SENDER.md`).
