# Docs Index

Короткий индекс по документации `pc_client`, чтобы не начинать с полного просмотра всей базы документов.

## Читать сначала

- `AGENTS.md` - обязательные правила проекта, source of truth, pipeline, Protocol V3 invariants.
- `docs/CODEX_WORKFLOW.md` - режимы работы Codex: intake, debug, planning, execution, verification, commit, deploy и dirty worktree triage.
- `docs/QUICK_LOOKUP.md` - быстрый роутер по темам: что открыть первым, какие docs и checks нужны.
- `docs/ARCHITECTURE_BOUNDARIES.md` - карта границ владения и contract surfaces; читать перед правками, чтобы оценить blast radius и cross-cutting риски.
- `docs/CONTEXT_INDEX.md` - локальный SQLite/FTS индекс canonical docs, CODEMAP, navigation topics, routes, route handlers, tests и symbols для быстрого поиска контекста; поддерживает профили `debug`, `contract`, `route`, `test`, `web`.
- `docs/LIVE_TESTING_DEBUG_RULES.md` - обязательные правила Live validation/debug/bugfix: evidence before fix, validation surfaces, browser/UIA evidence, account-session, clean-run markers, contamination и final gate.
- `scripts/build_context_pack.py --topic "<тема>"` - компактный пакет контекста для Codex из `navigation_catalog` и top context-index results.
- `scripts/docs_inventory.py --check-links` - инвентаризация docs, статусы, дубли и проверка локальных markdown-ссылок.
- `server/docs/CODEMAP.md` - карта серверной части.
- `pc_agent/docs/CODEMAP.md` - карта агентской части.
- `docs/LOCAL_WORKFLOW.md` - локальная разработка, deploy, remote stack, browser checks.
- `docs/PILOT_RELEASE_GATE.md` - pilot readiness evidence, business/browser smoke, stand profile env, GitHub gate expectations and soak criteria.
- `docs/CONTEXT_EFFICIENCY.md` - как экономить контекст и пользоваться `task_intake`, `agent_find`, `docs_drift_check`.

## По областям

- Protocol V3: `server/docs/PROTOCOL_V3.md`, `pc_agent/docs/PROTOCOL_V3.md`.
- Auth/security: `server/docs/SECURITY_AND_AUTH.md`, `pc_agent/docs/AUTHENTICATION.md`.
- Tickets/chat/forms: `server/docs/TICKET_SYSTEM.md`, `server/docs/CHAT_MESSAGE_CONTRACT.md`, `server/docs/REQUEST_FORM_BUILDER.md`.
- External Knowledge/Registry boundaries: `server/docs/SEGMENTATION_BOUNDARIES.md`, `server/docs/KNOWLEDGE_PLATFORM_API_V1.md`, and `server/docs/REGISTRY_PLATFORM_API_V1.md` — Helpdesk consumes versioned ports; local Knowledge is removed/unavailable, while Registry uses a temporary local adapter behind a redacted `RegistryPort` during cutover.
- Modules/tools: `server/docs/MODULES_API.md`, `server/docs/MODULE_AUTHORING_RULES.md`, `server/docs/RUNTIME_EXECUTION_CONTRACT.md`, `pc_agent/docs/MODULES.md`, `pc_agent/docs/TOOLS_CONTRACT.md`.
- Observer/traces: `server/docs/OBSERVER_LAYER.md`, `server/docs/OBSERVER_AUTHORING_RULES.md`.
- Agent runtime/update: `pc_agent/docs/AGENT_RUNTIME_ALWAYS_ON.md`, `pc_agent/docs/AGENT_UPDATE_WORKFLOW.md`, `pc_agent/docs/SELF_UPDATE.md`, `server/docs/AGENT_UPDATES_API.md`.
- Webapp cutover: `docs/WEBAPP_CUTOVER_CHECKLIST.md` плюс webapp topic в `docs/QUICK_LOOKUP.md`.
- Operations/runbooks: `server/docs/RUNBOOK_*.md`.
- Live testing/debug: `docs/LIVE_TESTING_DEBUG_RULES.md`, `docs/TESTING_RULES.md`.

## Не использовать как стартовый канон

- `docs/archive/**` - исторические материалы и старые test reports.
- `docs/superpowers/plans/**` и `docs/superpowers/specs/**` - task-specific планы и design snapshots; читать только когда `QUICK_LOOKUP` или текущая задача прямо указывает на них.
- Старые roadmap/gap-analysis документы теперь лежат только в `docs/archive/`; корневые stub-дубли удалены.

## Когда обновлять

Обновляйте этот индекс, если появился новый крупный раздел документации, поменялся canonical start path или старый документ перемещён в архив.
