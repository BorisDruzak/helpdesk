# AGENTS.md — инструкции для Codex (pc_agent)

Источник истины по проекту: `\\192.168.100.17\NTFS_Share\pc_client\AGENTS.md`

## Главное про агента

- Роль: сбор данных на ПК, GUI (Qt), WebSocket клиент, модульная система, outbox/ACK доставка.
- Локальная БД агента: SQLite `data/storage.db` (см. `docs/DATABASE.md`).

## Документация, с которой начинать

- `docs/README.md`
- `docs/PROTOCOL_V3.md` (полная спецификация протокола)
- `docs/AUTHENTICATION.md` (источники токена: `AUTH_TOKEN` → `auth_tokens` → legacy `identity.json`)
- `docs/MODULES.md`, `docs/ORCHESTRATOR.md`, `docs/SENDER.md`

## CODEMAP

- Карта кода агента: `docs/CODEMAP.md`.
- Перед анализом/правками сначала смотреть `docs/CODEMAP.md`.
- При изменении структуры агентского кода, точек входа или runtime-потоков **обязательно** обновлять `docs/CODEMAP.md`.

## Инварианты Protocol V3

- Тип события определяется ТОЛЬКО по `device_seq` vs `agent_seq` (см. `docs/PROTOCOL_V3.md`).
- ACK удаляет outbox записи (нет статуса “sent” → ACK ⇒ DELETE) (см. `docs/SENDER.md`).


