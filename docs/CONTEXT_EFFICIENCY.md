# Эффективность контекста

Короткие правила, чтобы Codex быстрее находил нужные файлы и не загружал лишнюю документацию.

## Быстрый старт

- Для словесной задачи: `python scripts/task_intake.py --task "<описание>"`.
- Для компактного пакета контекста: `python scripts/build_context_pack.py --topic "<тема>"`.
- Для работы от текущего diff: `python scripts/task_intake.py` или `python scripts/diff_context.py`.
- Для точечного поиска: `python scripts/agent_find.py "<pattern>" --dir server|pc_agent`.
- Для проверки документации: `python scripts/docs_inventory.py --check-links`.

## Что уже помогает

- `docs/QUICK_LOOKUP.md` - human-facing стартовая карта тем.
- `scripts/navigation_catalog.py` - машиночитаемые темы, алиасы, checks, docs и drift-rules.
- `scripts/task_intake.py` - роутер по задаче или diff.
- `scripts/build_context_pack.py` - компактный вывод для Codex: open first, docs, skills, checks, suggested commands.
- `scripts/docs_inventory.py` - список docs со статусами `canonical`, `archive`, `plan`, `spec`, `historical`, broken links и duplicate basenames.
- `scripts/docs_drift_check.py` - защита от забытых CODEMAP/QUICK_LOOKUP обновлений.
- `python scripts/verify_workspace.py` - общий pre-commit harness; включает docs drift и broken-link check.
- `PLANS.md` - long-horizon артефакт для длинных задач.

## Как формулировать задачи

- Лучше: "В `server/websocket/agent_handshake.py` поправить timeout handshake".
- Лучше: "Собери context pack по обновлению агента".
- Хуже: "Посмотри всё и улучши".

Если формулировка широкая, сначала используйте `build_context_pack`; если уже есть конкретный файл или символ, используйте `agent_find`.

## Canonical vs Archive

Текущий канон: `AGENTS.md`, `docs/QUICK_LOOKUP.md`, `server/docs/CODEMAP.md`, `pc_agent/docs/CODEMAP.md` и профильные docs рядом с кодом.

Исторические roadmap/gap-analysis документы лежат только в `docs/archive/`. Они могут быть полезны как источник идей, но не являются источником истины для текущего поведения.
