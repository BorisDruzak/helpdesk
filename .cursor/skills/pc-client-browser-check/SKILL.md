---
name: pc-client-browser-check
description: Browser checks for pc_client web UI. Always use 192.168.100.17. Use when changing admin, tickets, or static assets.
---

# PC Client — проверка веб-интерфейса в браузере

Использовать при изменениях админки, страниц тикетов или статики.

## Единый URL

- **Всегда использовать:** `http://192.168.100.17:8666/admin`
- Не использовать `127.0.0.1`, `localhost` или другие адреса без явного запроса пользователя.

## Когда проверка обязательна

- Изменения в `server/ticket.html`, `server/ticket.js`, админка, статика.
- Любые правки веб-интерфейса сервера.
- После smoke — при необходимости убедиться, что GUI открывается и ключевые действия работают.

## Как проверять

1. Убедиться, что на Linux подняты `control` и основной сервер (`python scripts/manage_remote_stack.py status control`, `python scripts/manage_remote_stack.py status server`).
2. Открыть в браузере (или через MCP/Playwright): `http://192.168.100.17:8666/admin`.
3. Минимум: загрузка страницы, при необходимости — snapshot, клики по ключевым элементам (список тикетов, открытие тикета, кнопки).
4. При изменении страницы тикета — открыть конкретный тикет и проверить новый функционал.
5. Если менялась техпанель:
   - проверить блок статуса сервера;
   - проверить health block (DB, latency, pool, WS UI/agent, stuck operations);
   - проверить полные логи сервера: refresh, filter, search, copy/download;
   - проверить confirm-модалку и обязательную причину для `stop/restart`;
   - убедиться, что после `restart` техпанель восстанавливает связь с main server через внешний control-plane.

Не ограничиваться только smoke_test или перезапуском сервера: изменения в веб-интерфейсе проверять в браузере.
