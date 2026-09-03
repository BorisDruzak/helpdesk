# Docs Index

Короткий индекс по документации `pc_client`, чтобы не начинать с полного просмотра всей базы документов.

## Читать сначала

- `AGENTS.md` - обязательные правила проекта, source of truth и независимые deployment boundaries.
- `docs/CODEX_WORKFLOW.md` - режимы работы Codex: intake, debug, planning, execution, verification, commit, deploy и dirty worktree triage.
- `docs/ARCHITECTURE_BOUNDARIES.md` - карта границ владения и contract surfaces; читать перед правками, чтобы оценить blast radius и cross-cutting риски.
- `docs/LIVE_TESTING_DEBUG_RULES.md` - обязательные правила validation/debug: evidence before fix, browser/API separation and final gate.
- `scripts/docs_inventory.py --check-links` - инвентаризация docs, статусы, дубли и проверка локальных markdown-ссылок.
- `server/docs/CODEMAP.md` - карта серверной части.
- `docs/TESTING_RULES.md` - локальная разработка и focused verification.
- `docs/PILOT_RELEASE_GATE.md` - pilot readiness evidence, business/browser smoke, stand profile env, GitHub gate expectations and soak criteria.

## По областям

- Endpoint diagnostics: `server/docs/ENDPOINT_OPERATION_CONTRACT.md`.
- Auth/security: `server/docs/SECURITY_AND_AUTH.md`, `pc_agent/docs/AUTHENTICATION.md`.
- Tickets/chat/forms: `server/docs/TICKET_SYSTEM.md`, `server/docs/CHAT_MESSAGE_CONTRACT.md`, `server/docs/REQUEST_FORM_BUILDER.md`.
- External Knowledge/Registry boundaries: `server/docs/SEGMENTATION_BOUNDARIES.md`, `server/docs/KNOWLEDGE_PLATFORM_API_V1.md`, and `server/docs/REGISTRY_PLATFORM_API_V1.md` — Helpdesk consumes versioned ports; local Knowledge is removed/unavailable, while Registry uses a temporary local adapter behind a redacted `RegistryPort` during cutover.
- Endpoint operations: `server/docs/ENDPOINT_OPERATION_CONTRACT.md`.
- Observer/traces: `server/docs/OBSERVER_LAYER.md`, `server/docs/OBSERVER_AUTHORING_RULES.md`.
- Endpoint agent runtime/update: use the Endpoint Platform repository documentation.
- Webapp cutover: `docs/WEBAPP_CUTOVER_CHECKLIST.md`.
- Operations/runbooks: `server/docs/RUNBOOK_*.md`.
- Live testing/debug: `docs/LIVE_TESTING_DEBUG_RULES.md`, `docs/TESTING_RULES.md`.

## Не использовать как стартовый канон

- `docs/archive/**` - исторические материалы и старые test reports.
- `docs/superpowers/plans/**` и `docs/superpowers/specs/**` - task-specific планы и design snapshots; читать только когда текущая задача прямо указывает на них.
- Старые roadmap/gap-analysis документы теперь лежат только в `docs/archive/`; корневые stub-дубли удалены.

## Когда обновлять

Обновляйте этот индекс, если появился новый крупный раздел документации, поменялся canonical start path или старый документ перемещён в архив.
