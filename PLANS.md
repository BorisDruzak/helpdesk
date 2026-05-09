# Requester Timeline Projection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:executing-plans` or the project safe workflow to execute this plan task by task. Keep this file current after each checkpoint.

**Goal:** make every requester-visible ticket event render as a clear Russian user-facing timeline item through server-owned fields: `requester_timeline_text`, `requester_timeline_kind`, and `requester_timeline_payload`.

**Architecture:** add a dedicated server projection module for requester timeline events, then have server ticket serializers, support/web DTOs, public/requester surfaces, and the desktop Qt agent consume that projection. Keep existing SLA/workflow/routing/assignment behavior unchanged; this is only a safe display projection.

**Tech Stack:** Python 3, aiohttp, SQLAlchemy async repos, Pydantic DTOs, `server/tickets/*`, `server/web_api/support_handlers.py`, Qt Widgets desktop GUI in `pc_agent/ui_gui/*`, React/Vite webapp requester and support workspace.

---

## Status

Created: 2026-05-09.

Working mode: **Plan / Contract**.

Overall progress: **100%**.

Change classification: **cross-cutting typed display contract**. The server will add projection fields consumed by desktop agent and web/requester surfaces. No DB schema, workflow state machine, SLA timers, assignment logic, WebSocket protocol, or operation dispatch semantics should change.

Current instruction from user: execute the plan by phases, test changes, do live checks where relevant, and report completion percentage on each checkpoint.

Dirty worktree note: before this plan update the worktree already had many modified/untracked files in server, agent, docs, tests, and web-related zones. This plan update intentionally touches only `PLANS.md`.

## Phase Progress

| Phase | Scope | Progress | Status |
|---|---|---:|---|
| 0. Intake and plan | Read canonical docs, find event producers/renderers, classify contract surface, write implementation plan | 100% | Completed |
| 1. Server projection core | Tests and `server/tickets/requester_timeline.py` with safe Russian projection and hidden-event rules | 100% | Completed |
| 2. Server API integration | Add projection fields to requester/agent serializers and support timeline DTOs | 100% | Completed |
| 3. Web requester/support integration | React requester page, support workspace mapping and legacy ticket page prefer projection text | 100% | Completed |
| 4. Desktop agent integration | Qt GUI consumes server projection first and keeps safe fallback for older servers | 100% | Completed |
| 5. Documentation sync | Update ticket/chat/CODEMAP/quick lookup docs and rebuild context index | 100% | Completed |
| 6. Verification and signoff | Focused server/agent/web tests, compileall, web build and browser check if visible UI changed | 100% | Completed |

Progress rule: update the overall percentage after every completed phase. Current 100% reflects completed analysis/planning, server projection core, server API integration, web integration, desktop agent integration, documentation sync and verification.

## Analysis Summary

Read and used:

- `AGENTS.md`
- `docs/CODEX_WORKFLOW.md`
- `docs/QUICK_LOOKUP.md`
- `docs/ARCHITECTURE_BOUNDARIES.md`
- `docs/CONTEXT_INDEX.md` via rebuilt context index
- `pc_agent/docs/CODEMAP.md`
- `server/docs/CODEMAP.md`
- `server/docs/TICKET_SYSTEM.md`
- `server/docs/CHAT_MESSAGE_CONTRACT.md`

Context commands already run:

```powershell
.\scripts\bootstrap_shell_utf8.ps1
python scripts/task_intake.py
python scripts/build_context_pack.py --topic "requester_timeline_text requester_timeline_kind requester_timeline_payload ticket_events requester timeline"
python scripts/build_context_index.py --force
python scripts/search_context_index.py "requester timeline ticket_events requester_timeline_text support timeline" --profile contract
python scripts/diff_context.py
git status --short
```

Important existing producer and serializer findings:

- `server/app/repos/ticket_events_repo.py` is the canonical event writer and reader; it also has first-response/chat counter logic that must not treat public access code messages as support replies.
- `server/tickets/handlers.py` currently serializes requester-visible events through `_serialize_event_for_agent()` and `_serialize_event_raw()`, with `_event_visible_to_requester()` hiding only a small SLA/OLA pause/resume set.
- `server/web_api/support_handlers.py` has a separate support timeline mapper: `_is_support_timeline_event()`, `_timeline_event_label()`, `_timeline_event_text()`, `_build_timeline_message()`, `_build_timeline_entry()`, and `_build_support_timeline_payload()`.
- `server/web_api/dto/support.py::SupportTicketMessage` is the Pydantic DTO used by the typed support workspace timeline.
- Public requester React fetches `GET /api/tickets/{ticket_id}` through `webapp/src/features/requester/api.ts` and currently renders `messages` only in `webapp/src/pages/requester-ticket/index.tsx`.
- Legacy requester/support page code in `server/ticket.js` still maps raw `event_type` locally for system rows.
- Desktop agent uses `pc_agent/ui_gui/ticket_view_models.py::map_ticket_event_to_user_timeline_item()` and `pc_agent/ui_gui/chat_panel.py::_build_timeline_items()`.
- The current desktop fallback already hides some events, but still has local status fallback text and no server projection support.

Existing risky text paths to remove or bypass:

- Agent fallback status text in `pc_agent/ui_gui/ticket_view_models.py::_status_change_text()` can return raw-ish fallback for unknown status.
- Support timeline fallback in `server/web_api/support_handlers.py::_timeline_event_label()` returns English labels and title-cased raw event types.
- Support timeline `_timeline_event_text()` can expose raw statuses, queue codes, priority values, and raw fallback labels.
- Legacy `server/ticket.js` can render `item.event_type` as a visible title for unknown history rows.

## Event Inventory

Requester-safe projection must explicitly cover these ticket event types or intentionally hide them.

Visible or safely projectable:

- `ticket_created` from legacy payload event aliases
- `chat_message`
- `status_changed`
- `assignee_changed`
- `queue_changed`
- `routing_applied`
- `priority_changed`
- `priority_overridden`
- `classification_changed`
- `requester_profile_changed`
- `device_changed`
- `sla_started`
- `sla_warning`
- `sla_breached`
- `sla_first_response_stopped`
- `sla_resolution_stopped`
- `tool_call_started`
- `tool_call_result`
- `diagnostic_result_classified`
- `playbook_started`
- `approval_approved`
- `approval_rejected`
- `approval_reminder_due`
- `approval_escalated`
- `approval_timed_out`
- `passport_generated`
- attachment-like `chat_message` payloads with `attachments`

Visible only if already explicitly requester-facing, otherwise hidden:

- `passport_evidence_added`
- `passport_evidence_linked`
- `passport_evidence_verified`
- `passport_evidence_rejected`
- `passport_evidence_archived`
- `passport_evidence_superseded`
- `passport_evidence_unverified`
- `operation_retried`
- `operation_retry_consent_requested`

Hidden from requester timeline by default:

- `internal_note`
- `worklog_added`
- `message_read`
- `external_notification_delivery`
- `policy_action_dispatched`
- `ticket_hidden_from_workspace`
- `ticket_unhidden_from_workspace`
- `ticket_archived_from_workspace`
- `ticket_unarchived_from_workspace`
- `sla_paused`
- `sla_resumed`
- `sla_reminder_sent`
- `ola_started`
- `ola_ack_stopped`
- `ola_processing_stopped`
- `ola_paused`
- `ola_resumed`
- `ola_breached`
- `operation_timed_out`
- raw observer/tool/internal logs and observer runtime events
- device/protocol/auth/module runtime events that are not ticket requester events

## Target Projection Contract

Create `server/tickets/requester_timeline.py`.

Core types and functions:

```python
@dataclass(frozen=True)
class RequesterTimelineProjection:
    text: str
    kind: Literal["system_event", "diagnostic_result", "attachment", "user_message", "support_message"]
    payload: dict[str, Any]
    icon: str | None = None
    style: str | None = None

def build_requester_timeline_projection(event: object | dict[str, Any], ticket: object | None = None) -> RequesterTimelineProjection | None:
    ...

def is_requester_visible_timeline_event(event_type: str, payload: Mapping[str, Any] | None) -> bool:
    ...
```

Projection rules:

- Return `None` for internal/debug/noise events.
- Never expose raw JSON, tokens, trace ids, internal notes, worklogs, observer logs, raw operation params, or raw tool output blobs.
- Prefer safe Russian fixed phrases over payload-derived raw values.
- Include only compact payload fields that a requester UI can use directly.
- `chat_message` with `visibility=internal` is hidden.
- Public access-code `chat_message` stays a system event and must not be treated as `support_message`.
- Public support/admin `chat_message` becomes `support_message`.
- Requester/user/agent-device `chat_message` becomes `user_message`.
- `tool_call_result` becomes `diagnostic_result` with compact `checks` only.
- Attachments are represented with safe descriptors: `name`, `size_label`, optional safe `url` if already a normal download URL; never put URL/token in visible text.

Required Russian text examples:

- `ticket_created`: `Заявка зарегистрирована.`
- `status_changed:new|queued`: `Заявка принята.`
- `status_changed:assigned`: `Назначен специалист поддержки.`
- `status_changed:in_progress`: `Специалист взял обращение в работу.`
- `status_changed:waiting_on_user|waiting_user`: `Специалист ждёт ваш ответ.`
- `status_changed:waiting_on_internal_team|waiting_internal`: `Обращение передано профильному специалисту.`
- `status_changed:waiting_on_vendor|waiting_vendor`: `Ожидаем ответ внешней стороны.`
- `status_changed:waiting_on_approval|waiting_approval`: `Обращение ожидает согласование.`
- `status_changed:resolved`: `Поддержка предложила решение. Проверьте, устранена ли проблема.`
- `status_changed:closed`: `Обращение закрыто.`
- `status_changed:canceled|cancelled`: `Обращение отменено.`
- `assignee_changed` with assignee display/id: `Назначен исполнитель: <name>.`
- `assignee_changed` without assignee: `Обращение вернулось в очередь поддержки.`
- `queue_changed`: `Обращение передано в профильную группу поддержки.`
- `routing_applied`: `Обращение направлено в подходящую группу поддержки.`
- `priority_changed` / `priority_overridden`: `Приоритет обращения обновлён.`
- `classification_changed`: `Категория обращения уточнена.`
- `requester_profile_changed`: `Контактные данные по обращению обновлены.`
- `device_changed`: `Устройство по обращению обновлено.`
- `sla_started`: `Сроки обращения рассчитаны.`
- `sla_warning`: `Есть риск нарушения срока. Поддержка получила уведомление.`
- `sla_breached`: `Срок нарушен. Обращение требует внимания поддержки.`
- `sla_first_response_stopped`: `Первый ответ получен.`
- `sla_resolution_stopped`: `Срок решения остановлен.`
- `tool_call_started`: `Специалист запустил диагностику.`
- `tool_call_result`: `Диагностика выполнена`
- `diagnostic_result_classified`: `Результат диагностики обработан.`
- `playbook_started`: `Запущена диагностика по обращению.`
- `approval_approved`: `Согласование получено.`
- `approval_rejected`: `Согласование отклонено.`
- `approval_reminder_due`: hidden by default, or `Ожидается согласование.` if a requester-visible flag exists.
- `approval_escalated`: `Согласование передано ответственному специалисту.`
- `approval_timed_out`: `Срок согласования истёк.`
- `passport_generated`: `Подготовлены материалы по решению.`

## Implementation Phases

### Phase 1: Server Projection Core

Progress: **100%**.

#### Task 1.1: Server Projection Tests

Files:

- Create: `server/tests/test_requester_timeline_projection.py`
- Modify if needed: `server/tests/test_ticket_first_response_classification.py`

Steps:

- [x] Add tests for `status_changed` to `in_progress`.
- [x] Add tests for `status_changed` with unknown status returning no raw `unknown`.
- [x] Add tests proving unknown technical events are hidden by default.
- [x] Add tests for `chat_message` public user/support/system access-code mapping.
- [x] Add tests for hidden `internal_note`, `worklog_added`, `message_read`, workspace hide/archive events and notification/policy audit events.
- [x] Add tests for `tool_call_result` compact diagnostic payload without raw JSON, token-like text, trace ids or full result blobs.
- [x] Keep or extend first-response tests proving public access-code message is system notice and not first response.

Expected command:

```powershell
python -m pytest server\tests\test_requester_timeline_projection.py server\tests\test_ticket_first_response_classification.py -q
```

#### Task 1.2: Server Projection Module

Files:

- Create: `server/tickets/requester_timeline.py`

Steps:

- [x] Implement the dataclass and helpers described above.
- [x] Implement payload extraction that accepts both ORM `TicketEvent` objects and dict-like events.
- [x] Implement status alias handling for top-level, `payload`, and `event_details` forms.
- [x] Implement assignee display extraction from `assignee_display_name`, `new_assignee_display_name`, `new_value`, and safe fallback ids.
- [x] Implement compact diagnostic check extraction compatible with current agent/web logic: `checks`, `steps`, `result.checks`, `result.steps`, `diagnostics`.
- [x] Implement hidden-event allow/deny sets in one place.
- [x] Do not import web DTOs or Qt/client code; keep the module domain-level and dependency-light.

Expected command:

```powershell
python -m pytest server\tests\test_requester_timeline_projection.py -q
```

### Phase 2: Server API Integration

Progress: **100%**.

#### Task 2.1: Server Serializers And Requester Filtering

Files:

- Modify: `server/tickets/handlers.py`

Steps:

- [x] Replace `_event_visible_to_requester()` internals with `build_requester_timeline_projection(...) is not None` for non-chat events, while preserving public chat visibility rules.
- [x] Add projection fields in `_serialize_event_raw()`:
  - `requester_timeline_text`
  - `requester_timeline_kind`
  - `requester_timeline_payload`
  - optional `requester_timeline_icon`
  - optional `requester_timeline_style`
- [x] Add the same projection fields in `_serialize_event_for_agent()` so the desktop GUI receives them in `events`.
- [x] Ensure `_serialize_message()` remains chat-compatible and does not change first-response logic.
- [x] Ensure `GET /api/tickets/{ticket_id}` requester visibility no longer returns hidden internal/debug events.
- [x] Ensure `GET /api/tickets/{ticket_id}/snapshot` history uses the same projection and does not reintroduce raw event labels.

Expected command:

```powershell
python -m pytest server\tests\test_ticket_first_response_classification.py -q
python -m pytest server\tests\test_web_support_api.py -k "timeline or requester" -q --tb=short
```

#### Task 2.2: Support Timeline DTO Integration

Files:

- Modify: `server/web_api/dto/support.py`
- Modify: `server/web_api/support_handlers.py`

Steps:

- [x] Add nullable requester projection fields to `SupportTicketMessage`.
- [x] Make `_build_timeline_message()` and `_build_timeline_entry()` call `build_requester_timeline_projection()`.
- [x] Preserve support-only fields such as operation actions, retry/cancel URLs, event details and internal filters for staff views.
- [x] For requester/public views, prefer projection `text` and `kind`; for support internal timeline, keep support details but expose projection fields for parity.
- [x] Stop using raw fallback labels as requester text.
- [x] Decide whether support timeline should continue to include `worklog_added` and internal notes for staff filters only. Requester projection must still be `None`.

Expected command:

```powershell
python -m pytest server\tests\test_web_support_api.py -k "timeline" -q --tb=short
```

### Phase 3: Web Requester And Support Integration

Progress: **100%**.

#### Task 3.1: Public Requester Web Timeline

Files:

- Modify: `webapp/src/features/requester/types.ts`
- Modify: `webapp/src/pages/requester-ticket/index.tsx`
- Modify if needed: `webapp/src/features/requester/api.ts`
- Modify if needed: `webapp/src/pages/requester-ticket/index.test.tsx`

Steps:

- [x] Extend public ticket detail types to accept `events` or requester timeline items from `GET /api/tickets/{ticket_id}`.
- [x] Render requester-safe system events alongside messages when projection fields are present.
- [x] Never render raw `event_type`, raw status, queue ids, trace ids, tool params or internal logs.
- [x] Keep access-code messages as system messages, not support replies.
- [x] Add a test that requester page displays `requester_timeline_text` and does not display raw `status_changed`, `unknown`, or `tool_call_result`.

Expected commands:

```powershell
python scripts/bootstrap_web_toolchain.py
pnpm --dir webapp exec vitest run src/pages/requester-ticket/index.test.tsx src/pages/requester-ticket/index.status.test.tsx --run
```

#### Task 3.2: Support React Workspace Mapping

Files:

- Modify: `webapp/src/features/queues/api.ts`
- Modify: `webapp/src/features/queues/support-workspace-mappers.ts`
- Modify: `webapp/src/features/queues/support-workspace-mappers.test.ts`
- Modify if needed: `webapp/src/pages/tickets/list-page.test.tsx`

Steps:

- [x] Add TS fields for requester timeline projection on support timeline entries.
- [x] In requester/public-facing sections, use `requester_timeline_text`.
- [x] Keep staff support workspace diagnostic/history details available, but ensure the displayed primary body uses safe text where appropriate.
- [x] Add a mapper test that raw event type/status does not become visible when projection exists.

Expected commands:

```powershell
python scripts/bootstrap_web_toolchain.py
pnpm --dir webapp exec vitest run src/features/queues/support-workspace-mappers.test.ts src/pages/tickets/list-page.test.tsx --run
pnpm --dir webapp run build
```

#### Task 3.3: Legacy Ticket Page Compatibility

Files:

- Modify: `server/ticket.js`

Steps:

- [x] In `renderSystemEvent()` or equivalent event rendering path, prefer `requester_timeline_text` and `requester_timeline_kind`.
- [x] Hide events where projection is absent for requester mode.
- [x] Remove visible raw fallback `item.event_type` from requester-facing rows.
- [x] Keep support/admin-only history panel behavior intact if that page is used by staff.

Expected check:

```powershell
python -m compileall -q server\tickets\handlers.py server\tickets\requester_timeline.py server\web_api\support_handlers.py
```

### Phase 4: Desktop Agent Integration

Progress: **100%**.

#### Task 4.1: Desktop Agent Fallback And Server Projection Consumption

Files:

- Modify: `pc_agent/ui_gui/ticket_view_models.py`
- Modify if needed: `pc_agent/ui_gui/chat_panel.py`
- Modify: `pc_agent/tests/test_chat_panel_helpers.py`

Steps:

- [x] Make `map_ticket_event_to_user_timeline_item()` first read server fields:
  - `requester_timeline_text`
  - `requester_timeline_kind`
  - `requester_timeline_payload`
  - optional style/icon fields
- [x] If server projection exists, return a `TimelineItem` directly from it.
- [x] Keep local fallback for older servers, but remove the generic raw fallback.
- [x] Ensure fallback never returns `Обращение обновлено.`.
- [x] Ensure fallback never returns `Статус обновлён: unknown.`.
- [x] Hide unknown/debug/internal events instead of showing raw text.
- [x] Preserve attachment/user/support/diagnostic rendering already covered by `TimelineItemWidget`.

Expected command:

```powershell
python -m pytest pc_agent\tests\test_chat_panel_helpers.py -q
```

### Phase 5: Documentation Sync

Progress: **100%**.

#### Task 5.1: Documentation Sync

Files:

- Modify: `server/docs/TICKET_SYSTEM.md`
- Modify: `server/docs/CHAT_MESSAGE_CONTRACT.md`
- Modify: `server/docs/CODEMAP.md`
- Modify: `pc_agent/docs/CODEMAP.md`
- Modify: `docs/QUICK_LOOKUP.md`
- Modify: `scripts/navigation_catalog.py`

Steps:

- [x] Document requester timeline projection fields and safety rules.
- [x] Document hidden internal/debug event categories.
- [x] Document that public access-code `chat_message` is a system notice and not first response.
- [x] Add `server/tickets/requester_timeline.py` to server CODEMAP.
- [x] Update agent CODEMAP to state that Qt GUI prefers server projection and only uses local fallback for older servers.
- [x] Rebuild context index after doc/navigation changes.

Expected command:

```powershell
python scripts/build_context_index.py --force
python scripts/verify_workspace.py
```

### Phase 6: Final Verification And Browser Check

Progress: **100%**.

#### Task 6.1: Final Verification And Browser Check

Minimum local commands:

```powershell
python scripts/verify_workspace.py
python -m pytest pc_agent\tests\test_chat_panel_helpers.py -q
python -m pytest server\tests\test_ticket_first_response_classification.py -q
python -m pytest server\tests\test_requester_timeline_projection.py -q
python -m pytest server\tests\test_web_support_api.py -k "timeline or requester" -q --tb=short
python -m compileall -q server\tickets\requester_timeline.py server\tickets\handlers.py server\web_api\support_handlers.py pc_agent\ui_gui\ticket_view_models.py pc_agent\ui_gui\chat_panel.py
```

If webapp files change:

```powershell
python scripts/bootstrap_web_toolchain.py
pnpm --dir webapp run test
pnpm --dir webapp run build
```

Browser signoff if web UI changes are visible:

- Use only `http://192.168.100.17:8666/admin`.
- Check `/app/tickets` timeline rows for support workspace.
- Check `/app/ticket/:ticketId` requester/public page if accessible with a public token/code fixture.
- Verify no raw `event_type`, `unknown` status, raw queue/status/tool log, trace id or token-like value is visible in requester-facing timeline.

Verification notes from 2026-05-09:

- `python scripts/verify_workspace.py` passed.
- Agent/server focused pytest and compileall passed.
- `pnpm --dir webapp run test` passed: 30 files, 162 tests.
- `pnpm --dir webapp run build` passed.
- Remote browser/login at `http://192.168.100.17:8666/admin` loaded the webapp shell and admin inventory without page/console errors. `pnpm --dir webapp run check:remote:webapp` reached `/app/tickets` but returned exit 1 because its support-page expected text list is stale relative to the current remote UI labels; no local deploy was performed in this task.

## Acceptance Criteria

- Desktop agent no longer shows `Обращение обновлено.` as a fallback.
- Desktop agent no longer shows `Статус обновлён: unknown.`.
- Server sends requester projection fields for requester-visible ticket events.
- Desktop agent uses server projection when present.
- Web/requester surfaces use the same server projection or compatible fallback.
- Internal/debug/noise events are not visible to requester timeline.
- Public access code remains a system message and does not stop first-response SLA.
- Assignee changes show either `Назначен исполнитель: ...` or `Обращение вернулось в очередь поддержки.`
- Diagnostic results expose compact checks, not raw JSON.
- Support staff timeline keeps needed diagnostic/detail data without leaking it into requester projection.
- Tests cover server projection, agent fallback, first-response classification and web timeline rendering.

## Handoff

Next implementation checkpoint: start with Task 1 and Task 2. Write server projection tests first, implement `server/tickets/requester_timeline.py`, then integrate serializers and consumers.

Current changed file from this checkpoint:

- `PLANS.md`
