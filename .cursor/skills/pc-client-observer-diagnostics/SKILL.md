---
name: pc-client-observer-diagnostics
description: Use when diagnosing tool failures, ticket traces, mass signatures, degradation patterns, or observer-layer regressions in pc_client.
---

# PC Client Observer Diagnostics

Использовать, когда нужно быстро диагностировать:

- тикет, у которого “ничего не произошло”;
- проблему в tool/module/update/consent flow;
- массовую signature;
- degradation по timeout/retry/slow rate;
- регрессию observer-слоя.

## С чего начинать

1. `docs/QUICK_LOOKUP.md`
2. `server/docs/CODEMAP.md`
3. `server/docs/OBSERVER_LAYER.md`
4. `server/docs/OBSERVER_AUTHORING_RULES.md`

Если кейс agent-side:

5. `pc_agent/docs/CODEMAP.md`
6. `pc_agent/core/action_trace.py`
7. `pc_agent/modules/base_module.py`

## Основные API

- `GET /api/admin/tech/observer/quick`
- `GET /api/admin/tech/traces/runtime`
- `GET /api/admin/tech/traces`
- `GET /api/admin/tech/traces/{trace_id}`
- `GET /api/admin/tech/signatures`
- `GET /api/admin/tech/signatures/{error_signature}`
- `GET /api/admin/tech/degradations`
- `GET /api/tickets/{ticket_id}/observer`

## Быстрый путь диагностики

1. Открыть tech quick diagnosis.
2. Если есть ticket id, открыть ticket observer summary.
3. Если видна массовая проблема, идти через signatures/degradations.
4. Если нужен конкретный случай, открыть trace detail.
5. Для живого agent trail включить `include_agent_actions=1`.

## Что проверить в браузере

- URL только `http://192.168.100.17:8666/admin`
- tech quick diagnosis загрузился
- trace search/detail работает
- support trace summary для тикета виден

## Что проверять в коде

- `server/observer/service.py`
- `server/observer/runtime.py`
- `server/tech/handlers.py`
- `server/tickets/handlers.py`
- `server/admin.js`
- `server/support.js`
- `pc_agent/core/action_trace.py`

## Если добавляете новый dangerous flow

Не закрывать задачу, пока не обновлены:

- `server/docs/OBSERVER_LAYER.md`
- `server/docs/OBSERVER_AUTHORING_RULES.md`
- `server/docs/CODEMAP.md`
- `pc_agent/docs/CODEMAP.md`
- `docs/QUICK_LOOKUP.md`
- `scripts/navigation_catalog.py`
