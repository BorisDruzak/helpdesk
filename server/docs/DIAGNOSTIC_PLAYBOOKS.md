# Diagnostic playbooks

Update note 2026-06-16 diagnostic target execution: ticket diagnostics now resolve the execution device through `server/tickets/diagnostic_target.py`, which reads the server-owned `ticket_context_v1`/flat aliases (`target_device_id`, `diagnostic_target_source`, `target_agent_status`) and falls back to legacy `ticket.device_id` only for tickets without a context snapshot. Request-form auto-run, diagnostic-policy auto-run, support manual tool runs, support playbook preflight/run, and the legacy `/api/tools/run` ticket-device guard all use this resolved target. Offline targets write `diagnostic_autorun_skipped.reason=target_agent_offline`; missing or ambiguous targets write `target_device_missing` / `target_device_ambiguous` evidence instead of enqueueing a module on the creator's current device. Support tools/playbooks payloads include `diagnostic_target` so `/app/tickets/:ticketId` can show the target device and affected person before a manual launch.

Update note 2026-05-02 diagnostic result routing: terminal diagnostic/tool operations now pass through `tickets.diagnostic_policy.apply_diagnostic_result_policy(...)` from the command-result pipeline. The helper extracts a stable `diagnostic_result` class from result payloads or `Operation.error_code` (`DNS_FAIL`, `HTTP_500`, `TLS_CERT_INVALID`, etc.), stores it in `ticket.custom_fields.diagnostic_result` / `diagnostics`, and executes `diagnostic_policy.reroute_by_result` as a queue handoff with `diagnostic_result_classified`, `routing_applied` and `queue_changed` events. This path is idempotent per `operation_id` and does not change `ticket.status`; operation status remains the source for running/succeeded/failed diagnostics.

Update note 2026-05-11 diagnostic layer: playbook and tool results can now be projected into the separate Diagnostic Layer (`diagnostic_sessions`, `diagnostic_steps`, `diagnostic_evidence`, `diagnostic_findings`, `diagnostic_bundles`) without changing playbook execution semantics or ticket status. The first projection path is service/API driven from `server/diagnostics/projection.py` and `server/diagnostics/service.py`: terminal operations become normalized evidence, `diag.logs.collect` maps to `logs.bundle`, observer root traces become `observer.summary`, remote assist sessions become `remote_assist.session`, and rule-based findings can be evaluated through `/api/tickets/{ticket_id}/diagnostics/findings/evaluate`.

Update note 2026-05-12 diagnostic profile/passport bridge: `POST /api/tickets/{ticket_id}/diagnostics/run-profile` creates a diagnostic session, records recommended capability/playbook steps from the profile registry, projects current ticket sources, evaluates findings and can auto-select passport-eligible evidence. `POST /api/tickets/{ticket_id}/diagnostics/passport/attach-selected` promotes selected diagnostic evidence into existing `ticket_evidence_items` idempotently with `source_kind=diagnostic_evidence`, preserving the existing passport/evidence model.

Update note 2026-05-12 capability-backed playbooks: playbook drafts may now use `capability_id` in addition to legacy `tool`. Saved manifests keep backward-compatible `required_tools` for agent-backed steps and add `required_capabilities` with `execution_target`, provider, schemas, output contract and evidence metadata. Agent targets still run through the existing module auto-install + `run_tool` path; non-agent targets (`server_builtin`, `server_connector`, `observer_query`, `remote_assist`, `manual`) route through `CapabilityExecutionRouter`, complete the playbook step with normalized output/error JSON, and never enqueue ordinary agent `run_tool` commands. If a routed capability returns an evidence preview and the playbook context has a real ticket, the result is projected into diagnostic evidence without making diagnostics a ticket status.

Update note 2026-05-02 diagnostic policy auto-run: request templates can now run `diagnostic_policy.suggested_playbooks` automatically on ticket creation when `auto_run.enabled=true`. The auto-run path uses the same playbook runtime as form triggers but adds safety gates: `only_for_priorities`, `only_if_agent_online`, requester-device consent (`requires_user_consent` / `consent.required_for_requester_device`) and high-risk tool consent (`consent.required_for_high_risk_tools`). Before a policy auto-run starts, the server inspects the published playbook manifest `required_tools` / block `tool_manifest` risk metadata; levels `high`, `dangerous`, `system_write` and `code_exec` require an explicit `diagnostic_consent.high_risk_tools_granted=true` or equivalent grant. Blocked auto-runs write `diagnostic_autorun_skipped` with a reason (`priority_not_allowed`, `target_agent_offline`, `target_device_missing`, `target_device_ambiguous`, `consent_required`, `high_risk_consent_required`) instead of silently doing nothing.

Update note 2026-04-30 diagnostic policy evidence: request templates can now execute `diagnostic_policy.attach_results` during passport generation. When `attach_results.as_evidence=true` and `attach_results.to_passport` is not disabled, `server/tickets/diagnostic_policy.py` materializes terminal ticket operations as `ticket_evidence_items` with `evidence_type=diagnostic_result` and `source_ref=operation:<operation_id>`. This keeps `ticket.status` independent from operation status while allowing diagnostic results to satisfy passport/closure evidence requirements.

Update note 2026-04-28/2026-05-04 ticket launch: support ticket detail now has typed playbook launch routes. `GET /api/web/support/tickets/{ticket_id}/playbooks` returns published playbook versions with required tools, missing tools, missing required params, readiness for the resolved diagnostic target device, and recent ticket playbook runs with step errors. `POST /api/web/support/tickets/{ticket_id}/playbooks/run` starts the selected version through `playbook_engine.start_run` with `trigger_type=support_ticket` and a ticket-bound context that includes `diagnostic_target`, but blocks `PLAYBOOK_PREFLIGHT_BLOCKED` before enqueue if the playbook is not runnable.

Update note 2026-04-27: saved drafts now use `pc_client.playbook.self_healing.v2`. The server stores `required_tools` with module owner, source, install policy, platforms, minimum agent version, params/output schemas, output contract, condition hints, presets and known error codes. Tool-backed playbook steps run the existing module auto-install preflight before `run_tool`; install failures stop the step with `stage=module_install`, while capability gate failures use `stage=capability_gate`. After a successful DB-backed module preflight/install, the playbook engine treats that preflight as authoritative for the immediate `run_tool` enqueue, because device module inventory/toolset snapshots can lag behind the install command result. Presets are expanded into concrete params on the server for both support tool launches and playbook steps, so agents receive normal command params.

Update note 2026-04-27 low-code canvas: `/app/admin/playbooks` is now canvas-first. The React builder keeps the same typed catalog/save API, but operators assemble drafts by dragging atomic module commands from the left palette onto a grid, moving blocks visually, selecting the command inside each block, and editing presets/params/output contracts in the right inspector. Canvas coordinates are client-side UI state; the saved playbook order is derived from block position top-to-bottom so the existing server manifest and runtime contract remain compatible.

Дата обновления: 2026-04-26

## Модель

Плейбук — это версия сценария из шагов. В текущем low-code UI поддержан безопасный класс `diagnostic`: шаги собирают факты и не меняют устройство.

- Конструктор UI: `/app/admin/playbooks`
- Typed API: `GET /api/web/admin/playbooks/catalog`, `POST /api/web/admin/playbooks/save`
- Каталог блоков: `server/playbooks/catalog.py`
- Автозапуск из формы: `server/playbooks/form_triggers.py`
- Исполнение: существующий `server/app/services/playbook_engine.py`

Каждый диагностический шаг должен возвращать структурированный пакет:

- `status`: `success` или `error`
- `found`: найденные факты
- `error_code`: машинный код ошибки или `null`
- `attachments`: ссылки на логи, скриншоты, замеры или другие артефакты

For playbook branching the command catalog does not rely on free-form text. Each atomic tool may declare an `output_contract`:

```json
{
  "status_path": "result.status",
  "status_values": ["ok", "error"],
  "success_values": ["ok"],
  "error_values": ["error"],
  "summary_path": "result.output.summary",
  "error_code_path": "result.error.code",
  "compact_fields": [
    { "path": "result.output.reachable", "label": "Reachable", "type": "boolean" }
  ]
}
```

`server/playbooks/tool_catalog.py` normalizes this into `condition_hints`. The builder shows status path, allowed values and error codes, then offers quick condition templates for decision blocks. This keeps the UI predictable even when the full module result contains verbose logs, stdout or diagnostic measurements.

## Диагностика и исправление

Классы разделены намеренно:

- `diagnostic` — только сбор фактов, без изменений на устройстве.
- `remediation` — может менять состояние, но должен идти отдельным flow с подтверждением пользователя/оператора.

Typed builder сейчас сохраняет только `diagnostic`-блоки. Попытка опубликовать `remediation` через этот endpoint отклоняется, чтобы не смешать сбор доказательств и исправляющие действия.

## Минимальный каталог модулей

Базовые диагностические блоки:

- `system.collect` — системный и сетевой снимок.
- `ip_address.get_ip` — IP и базовая сетевая видимость.
- `diag.logs.collect` — пакет логов агента, может требовать согласие.

Типовые шаблоны сценариев:

- `site_not_opening`
- `printer_not_printing`
- `access_issue`
- `agent_offline`
- `internet_not_working`

## Автозапуск из форм

Форма в каталоге `request_forms` может содержать:

```json
{
  "playbook_triggers": [
    {
      "event": "ticket_created",
      "playbook_key": "site_not_opening",
      "module_kind": "diagnostic",
      "enabled": true
    }
  ]
}
```

При создании тикета `server/tickets/create_flow.py` переносит настройки формы в `custom_fields.request_form_playbook_triggers`, строит `facts_package` из ответов формы и запускает последнюю опубликованную версию плейбука с idempotency key `ticket:<ticket_id>:playbook:<key>:ticket_created`.

Результат старта фиксируется событием тикета `playbook_started`; дальнейшие step results остаются в существующих таблицах `playbook_run` / `playbook_step_run` и operation timeline.

## Привязка к паспорту и evidence

Шаблон обращения может хранить diagnostic policy:

```json
{
  "diagnostic_policy": {
    "id": "website_diagnostics",
    "suggested_playbooks": ["diagnose.website"],
    "auto_run": {
      "enabled": true,
      "only_if_agent_online": true,
      "only_for_priorities": ["P0", "P1"]
    },
    "consent": {
      "required_for_requester_device": true,
      "required_for_high_risk_tools": true
    },
    "reroute_by_result": {
      "DNS_FAIL": "networks",
      "HTTP_500": "information_systems",
      "TLS_CERT_INVALID": "security_or_servers"
    },
    "attach_results": {
      "to_passport": true,
      "as_evidence": true
    }
  }
}
```

При генерации паспорта `server/tickets/passport_service.py` вызывает `tickets.diagnostic_policy.materialize_diagnostic_operation_evidence(...)`. Завершённые операции тикета (`succeeded`, `failed`, `denied`, `timed_out`, `canceled`) становятся доказательствами только если policy это разрешает. Повторная генерация паспорта не создаёт дубликаты: идемпотентность строится по `ticket_id`, `evidence_type=diagnostic_result` и `source_ref=operation:<operation_id>`.

Диагностика не является статусом тикета: тикет остаётся, например, `in_progress`, а выполнение/результат живёт в `operations`, playbook tables, timeline и evidence/passport.

На создании тикета `server/playbooks/form_triggers.py` запускает legacy `playbook_triggers` и policy-driven `diagnostic_policy.auto_run` через один runtime. Для policy auto-run `trigger_type=diagnostic_policy_auto_run`, idempotency key строится по `ticket_id + playbook_key + diagnostic_policy_auto_run`, а context содержит `scenario.source=diagnostic_policy` и snapshot `diagnostic_policy.auto_run`. Если policy требует `consent.required_for_high_risk_tools`, опубликованная версия playbook дополнительно проверяется по `manifest.required_tools[*].risk_level` и `blocks[*].tool_manifest.risk_level`; high-risk playbook не стартует без явного high-risk grant и пишет `diagnostic_autorun_skipped`.

Если terminal operation содержит результат классификации, `apply_diagnostic_result_policy(...)` пишет структурированный факт в `custom_fields` и может выполнить `reroute_by_result`. Значение policy может быть кодом очереди (`"networks"`), числовым `queue_id` или объектом `{ "queue": "networks" }` / `{ "queue_id": 12 }`. Ручной routing lock блокирует автоматический handoff, но факт диагностики всё равно сохраняется.

## Проверки

Минимальный локальный baseline при изменении этого потока:

- `python -m pytest server/tests/test_playbook_scenarios_no_db.py server/tests/test_web_admin_api.py server/tests/test_ticket_form_packs.py -q --tb=short`
- `python -m pytest server/tests/test_ticket_diagnostic_policy.py -q --tb=short`
- `python -m pytest server/tests/test_ticket_passport_service.py -q --tb=short`
- `pnpm --dir webapp run test -- --run src/features/playbooks/playbook-builder-panel.test.tsx src/features/forms-builder/forms-builder-panel.test.tsx src/features/agent-updates/device-update-panel.test.tsx`
- `pnpm --dir webapp run build`
# Agent Recipe capabilities

Published `agent_recipe` capabilities appear in the diagnostics capability catalog alongside server builtins, connectors, observer, remote assist, manual and agent module tools. Playbook steps should treat them as provider-aware capabilities and route through `CapabilityExecutionRouter`, which delegates `agent_recipe` to `RecipeExecutionService`.

First release recipe capabilities are read-only diagnostics. Remediation and side-effect recipes must not be enabled until a separate approval/governance phase defines risk gates, dry-run semantics and rollout controls.
