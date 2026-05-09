# Support Workspace Tools Catalog and Layout Polish Plan

> Active slice created 2026-05-09. Execute in small UI-only steps first; do not change operation dispatch or backend policy unless verification shows the typed endpoint itself lacks required catalog data.

**Goal:** make `/app/tickets` show the full ticket-scoped tools/playbooks catalog clearly, let the operator resize the three workspace columns, and make dark-theme scrollbars visually consistent with the SaaS workspace.

**Scope:**

- `/app/tickets` support workspace React page.
- Support tools/playbooks rendering and launcher selection UX.
- Column sizing state and drag handles for left/center/right layout.
- Dark/light scrollbar styling in `webapp/src/styles.css`.

**Constraints:**

- Do not bypass existing backend policy, consent, permission, device-online, or operation-run checks.
- Do not turn the support tools card into an admin module registry; it must remain ticket/device-scoped.
- Preserve existing topbar, navigation, archive/hide controls, realtime refresh, and composer behavior.
- Keep layout usable at desktop widths from 1366px.

## Current Slice Status

Overall progress: **100%**.

| Phase | Scope | Progress | Status |
|---|---|---:|---|
| P6.1 | Analyze tools/modules mismatch and define UI correction | 100% | Completed |
| P6.2 | Replace compact 8-item tools preview with searchable full ticket-scoped catalog | 100% | Completed |
| P6.3 | Add resizable left/right workspace columns with persisted widths | 100% | Completed |
| P6.4 | Add dark-theme scrollbar styling and light-theme safe fallback | 100% | Completed |
| P6.5 | Run focused tests/build and browser checks on `/app/tickets` | 100% | Completed |

## Findings

- Backend `GET /api/web/support/tickets/{ticket_id}/tools` and aggregate `/workspace` return a ticket/device-scoped tool payload, not the admin-wide module registry.
- The current page additionally limits visible automation entries to `4 playbooks + 4 tools`, or `8` total when only one kind exists.
- This makes the right-side tools card look incomplete even when the API has more tools/playbooks.
- The three-column shell currently uses fixed grid columns: left `320px`, center flexible, right `390px`; there are no resize handles.
- Dark scrollbars are still browser/default colored in several scroll containers.

## Implementation Plan

1. **Full catalog UI**
   - Build a single `allAutomationItems` collection from `viewModel.right.playbooks` and `viewModel.right.tools`.
   - Add catalog filters: all, runnable, playbooks, tools, disabled.
   - Add search by title, subtitle, id, and meta labels.
   - Show counts: displayed count vs total, plus playbook/tool totals.
   - Keep disabled cards visible with reason; only disable the run/select button.

2. **Resizable columns**
   - Add persisted column width state with safe defaults: left `320px`, right `390px`.
   - Add two drag handles between left/center and center/right.
   - Clamp widths so the center keeps a practical minimum.
   - Store values in `localStorage`; allow resize without changing routing or data flow.

3. **Scrollbar styling**
   - Add scoped CSS under `.support-workspace[data-theme="dark"]`.
   - Use dark track/thumb colors for Firefox and WebKit.
   - Keep light theme readable and unobtrusive.

4. **Verification**
   - Run focused web tests where available.
   - Run web build.
   - Open `/app/tickets` in browser and check: full tools list, search/filter, resize handles, dark scrollbars, no console errors.

## Expected User-Facing Improvements

- Operators can find every ticket-available module/tool/playbook without guessing why only eight items are shown.
- The right tools panel explains unavailable actions instead of silently hiding them.
- Operators can widen ticket timeline or right context depending on the task.
- Scrollbars match the dark SaaS theme and stop drawing bright visual noise.

## Verification Log

- 2026-05-09: `pnpm --dir webapp test -- src/pages/tickets/list-page.test.tsx src/features/queues/support-workspace-mappers.test.ts` passed, 47 tests.
- 2026-05-09: `pnpm --dir webapp build` passed.
- 2026-05-09: `python scripts/verify_workspace.py` passed.
- 2026-05-09: committed `7fb2a57 webapp: improve support workspace tools layout`.
- 2026-05-09: `python scripts/release_server_to_remote.py --skip-ci-check --leave-running` completed; remote smoke passed at `http://192.168.100.17:8666`.
- 2026-05-09: browser signoff on `/app/tickets` passed: resize handles are visible, tools catalog shows the full ticket-scoped list (`103 из 103` on the checked ticket), search filters to `1 из 103`, and browser console reported 0 errors / 0 warnings.

---

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
- `tool_call_result`: `Выполнена диагностика`
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

---

# Support Workspace Realtime Updates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:executing-plans` or the project safe workflow to execute this plan task by task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** make `/app/tickets` update selected-ticket messages, timeline, SLA/OLA, next action, queue counts and operation results without requiring the operator to click refresh or reload the page.

**Architecture:** reuse the existing typed web realtime bridge (`GET /api/web/realtime/bootstrap` -> `/ws_ui`) and subscribe the new `/app/tickets` page only to the currently selected ticket. Treat WebSocket push as the primary invalidation channel and keep bounded polling as fallback for disconnected/reconnecting states and active operations.

**Tech Stack:** React/Vite, TanStack Query, existing `webapp/src/shared/realtime/client.ts`, aiohttp `/ws_ui`, typed support APIs in `server/web_api/support_handlers.py`, Vitest, server pytest, remote browser signoff.

---

## Status

Created: 2026-05-09.

Working mode: **Plan / Debug / Typed Web Boundary**.

Overall progress: **95% implementation for this new slice**.

Change classification: **boundary change inside typed web boundary**. The work changes how `/app/tickets` consumes existing realtime events and query invalidation, but it should not change ticket workflow, SLA calculation, message persistence, operation dispatch, DB schema, Protocol V3 frames, or requester-visible semantics.

Current instruction from user: keep the current plan content, add a new plan part for seamless support workspace refresh, and do not clear the existing update plan.

## Root Cause / Analysis

Observed behavior:

- In `/app/tickets`, incoming support workspace messages and some operation/timeline updates become visible only after manual refresh or full page reload.
- Own outgoing messages call `refreshSelectedTicketData()` after mutation success, so the sender path looks fresher than external incoming messages.
- Operation polling exists only while selected-ticket operations are live, so ordinary `chat_message` events do not trigger an automatic selected-ticket refresh.

Evidence from code:

- `webapp/src/pages/tickets/list-page.tsx` has `workspaceQuery`, `timelineQuery` and `refreshSelectedTicketData()`, but currently does not import or call `getSharedWebRealtimeClient()`.
- `workspaceQuery` short-polls only when `workspaceHasLiveOperations(...)` is true.
- `timelineQuery` short-polls only for non-`all` filters and only while `workspaceHasLiveOperations(workspaceQuery.data)` is true.
- `webapp/src/features/queues/support-workspace.tsx` already has the desired pattern: `getSharedWebRealtimeClient().subscribeTicket(selectedTicketId, ...)` and query invalidation.
- `webapp/src/pages/tickets/detail-page.tsx` also subscribes selected ticket realtime and invalidates related ticket queries.
- `webapp/src/shared/realtime/client.ts` already normalizes `/ws_ui` frames:
  - `ticket_event_committed` -> `{ kind: "ticket_event", ticketId, eventId, eventType, payload }`
  - `operation_updated` -> `{ kind: "operation_updated", ticketId, operationId, deviceId, status, updatedAt }`
- Server message path `server/web_api/support_handlers.py::handle_web_support_send_message()` writes `chat_message`, commits, then calls `_push_ticket_event(...)`.
- `_push_ticket_event(...)` delegates to `push_ticket_event_committed(...)`, so the transport path already exists for support messages.
- Existing tests cover the bridge and older support workspace subscription behavior:
  - `webapp/src/shared/realtime/client.test.ts`
  - `webapp/src/features/queues/support-workspace.test.tsx`
  - `server/tests/test_web_realtime_api.py`
  - `server/tests/test_ui_transport_v3.py`

Conclusion:

- The likely gap is frontend consumption in the new `/app/tickets` page, not missing core backend transport.
- Backend verification is still required for all message producers, especially requester/public reply paths and operation completion paths, but the first implementation should avoid adding duplicate realtime infrastructure.

## Non-Goals

- Do not add a second SSE or polling-only realtime stack.
- Do not subscribe to every visible ticket row in the left list; subscribe only to the selected ticket to avoid websocket burst and stale subscription leaks.
- Do not optimistically append external messages from WS payload unless the payload contract is explicitly sufficient; prefer query invalidation/refetch for correctness.
- Do not change SLA/OLA business rules or first-response calculation.
- Do not change operation dispatch or retry semantics.
- Do not expose raw WebSocket tokens or raw event payloads in the UI.

## Target Behavior

- When another user/requester sends a message to the selected ticket, `/app/tickets` refreshes the selected timeline/workspace automatically.
- If the operator is on `Все`, messages appear in the central timeline from aggregate workspace payload after invalidation.
- If the operator is on `Сообщения`, `Внутреннее`, `Диагностика` or `История`, the active standalone timeline endpoint is invalidated/refetched.
- Next action, SLA/OLA timers, first-response state, unread/requester reply indicators and queue counts refresh from server truth.
- Operation rows update from `operation_updated` and `ticket_event_committed` without page reload.
- On reconnect after a socket outage, the page does a catch-up refetch of selected workspace/timeline/queue.
- If realtime is unavailable, selected-ticket fallback polling keeps the page eventually consistent.
- Manual refresh remains available.

## Phase Progress

| Phase | Scope | Progress | Status |
|---|---|---:|---|
| P14.1 | Frontend realtime hook and selected-ticket subscription design | 100% | Completed |
| P14.2 | `/app/tickets` query invalidation and fallback polling | 100% | Completed |
| P14.3 | Backend producer audit for all message/operation event paths | 100% | Completed |
| P14.4 | Unit/integration tests for realtime invalidation | 100% | Completed |
| P14.5 | Remote browser/live checks with T-000520-style scenario | 60% | In progress |
| P14.6 | Docs/CODEMAP sync and deploy signoff if code changes | 75% | In progress |

## Implementation Tasks

### P14.1: Create A Focused Realtime Invalidation Layer For `/app/tickets`

**Files:**

- Modify: `webapp/src/pages/tickets/list-page.tsx`
- Optional create if the effect gets too large: `webapp/src/pages/tickets/use-ticket-workspace-realtime.ts`
- Test: `webapp/src/pages/tickets/list-page.test.tsx`

- [ ] Add `getSharedWebRealtimeClient` import to the `/app/tickets` page or encapsulate it in a local hook.
- [ ] Subscribe only when `selectedTicketId` is non-empty.
- [ ] Store the current selected ticket in a ref, mirroring the safe pattern from `webapp/src/features/queues/support-workspace.tsx`.
- [ ] On ticket change, unsubscribe the previous ticket before subscribing the next one.
- [ ] On unmount, unsubscribe cleanly.
- [ ] Ignore messages whose `message.ticketId` does not match the currently selected ticket.
- [ ] Treat both `ticket_event` and `operation_updated` as invalidation signals.

Expected invalidated/refetched query keys:

```ts
["tickets-workspace", selectedTicketId]
["tickets-workspace-timeline", selectedTicketId]
["tickets-workspace-queue"]
["tickets-workspace-passport-evidence-candidates", selectedTicketId]
```

Notes:

- `["tickets-workspace-timeline", selectedTicketId]` should be invalidated by prefix so the active filter (`messages`, `diagnostics`, etc.) refreshes without knowing the exact selected tab.
- Evidence candidate refresh can be limited to active candidate/passport query state; invalidating the key is safe because disabled queries will not fetch.
- Keep manual `refreshSelectedTicketData()` as the common forced refresh helper where useful.

### P14.2: Add Realtime-Aware Fallback Polling Without Creating Excess Load

**Files:**

- Modify: `webapp/src/pages/tickets/list-page.tsx`
- Optional modify: `webapp/src/shared/realtime/client.ts` if connection-state exposure is needed
- Test: `webapp/src/pages/tickets/list-page.test.tsx`

- [ ] Keep existing `SUPPORT_OPERATION_REFRESH_MS = 2_500` for active operations.
- [ ] Add a slower selected-ticket fallback interval, recommended `SUPPORT_SELECTED_TICKET_FALLBACK_REFRESH_MS = 15_000`.
- [ ] Apply fallback polling to selected `workspaceQuery` when a ticket is selected and there are no live operations.
- [ ] Apply fallback polling to active `timelineQuery` when a non-`all` filter is active and there are no live operations.
- [ ] Avoid polling disabled queries.
- [ ] If realtime client connection state is exposed later, use fallback only while disconnected/degraded; first implementation may use bounded always-on selected-ticket fallback for simplicity.

Acceptance:

- Incoming messages appear without manual refresh even if WS is temporarily unavailable, with at most fallback interval delay.
- Active operations still refresh quickly.
- Queue polling remains at the existing `SUPPORT_QUEUE_REFRESH_MS` cadence.

### P14.3: Audit Backend Producers Instead Of Adding Duplicate Endpoints

**Files:**

- Inspect/possibly modify: `server/web_api/support_handlers.py`
- Inspect/possibly modify: `server/tickets/handlers.py`
- Inspect/possibly modify: `server/tickets/events.py`
- Inspect/possibly modify: operation result producers in `server/websocket/command_result_components.py`, `server/websocket/outbox_ingest_components.py`, `server/tools/service.py`
- Test: `server/tests/test_web_support_api.py`
- Test: `server/tests/test_web_realtime_api.py`
- Test: `server/tests/test_ui_transport_v3.py`

- [ ] Confirm typed support message route emits `ticket_event_committed` after commit.
- [ ] Confirm requester/public message route emits `ticket_event_committed` after commit for the same ticket.
- [ ] Confirm internal note route emits `ticket_event_committed` after commit when it creates a timeline-visible event for support.
- [ ] Confirm operation started/result/completed paths emit either `ticket_event_committed`, `operation_updated`, or both where expected.
- [ ] If a producer writes `ticket_events` without push, add `_push_ticket_event(...)` or the existing appropriate publisher after commit.
- [ ] Do not change event payload shape unless a failing test proves the bridge cannot route the event.

Acceptance:

- Server producers that affect `/app/tickets` central timeline have a push path.
- No double-push for the same event from the same producer.
- Existing server websocket tests still pass.

### P14.4: Add Tests Around New `/app/tickets` Realtime Behavior

**Files:**

- Modify: `webapp/src/pages/tickets/list-page.test.tsx`
- Possibly reuse patterns from: `webapp/src/features/queues/support-workspace.test.tsx`

- [ ] Mock `getSharedWebRealtimeClient()` in `list-page.test.tsx`.
- [ ] Assert selected ticket subscription is created for `/app/tickets/ticket-1`.
- [ ] Assert the page unsubscribes when route changes from `ticket-1` to `ticket-2`.
- [ ] Assert `ticket_event` with `eventType: "chat_message"` invalidates/refetches selected workspace, active timeline filter and queue data.
- [ ] Assert `operation_updated` invalidates/refetches selected workspace/timeline and keeps diagnostics visible after tool result.
- [ ] Assert realtime event for a non-selected ticket does not refetch selected workspace.
- [ ] Assert own `postSupportTicketMessage` path still clears composer and triggers explicit refresh.

Expected command:

```powershell
python scripts/bootstrap_web_toolchain.py
pnpm --dir webapp exec vitest run src/pages/tickets/list-page.test.tsx src/shared/realtime/client.test.ts --run
```

### P14.5: Live Browser Verification Scenario

**Files:**

- No source changes required unless checks expose bugs.

- [ ] Deploy only after local tests/build pass and a commit exists.
- [ ] Start the remote server through canonical scripts.
- [ ] Open `http://192.168.100.17:8666/admin` and navigate to `/app/tickets`.
- [ ] Open ticket `T-000520` or a fresh equivalent test ticket.
- [ ] From a second browser/API/session, create a public/requester-visible message.
- [ ] Verify the message appears in the timeline without pressing refresh.
- [ ] Verify the next action/SLA block updates if the message affects first-response/next-action state.
- [ ] Run a safe low-risk diagnostic/tool on an online test device.
- [ ] Verify `Tool Call Started` and result/final status replace `Нет результата` without page reload.
- [ ] Switch timeline tabs and verify active tab refreshes correctly.
- [ ] Temporarily interrupt/reconnect WS if practical, then verify catch-up refetch after reconnect or fallback polling.

Expected remote/browser checks:

```powershell
python scripts/release_server_to_remote.py --leave-running
python scripts/manage_remote_stack.py smoke server
pnpm --dir webapp run check:remote:webapp -- --base-url http://192.168.100.17:8666
```

Browser canonical URL:

```text
http://192.168.100.17:8666/admin
```

### P14.6: Documentation, Plan Status And Final Signoff

**Files:**

- Modify if code changes realtime behavior: `server/docs/TICKET_SYSTEM.md`
- Modify if typed web realtime docs need a note: `server/docs/CODEMAP.md`
- Modify if navigation/check docs change: `docs/QUICK_LOOKUP.md`
- Modify: `PLANS.md`

- [ ] Update this P14 progress table after every implementation checkpoint.
- [ ] If `/app/tickets` becomes the canonical support realtime consumer, note it in `server/docs/CODEMAP.md`.
- [ ] If browser/live check steps become reusable, add a compact note to `docs/QUICK_LOOKUP.md`.
- [ ] Run `python scripts/verify_workspace.py`.
- [ ] Run targeted server realtime/support tests if backend producer code changes.
- [ ] Run webapp tests and build.
- [ ] Commit only the files touched by this slice.
- [ ] Deploy and perform browser signoff if the user asks to ship it to the stand.

## Verification Matrix

Minimum before implementation completion:

```powershell
python scripts/verify_workspace.py
python scripts/bootstrap_web_toolchain.py
pnpm --dir webapp exec vitest run src/pages/tickets/list-page.test.tsx src/shared/realtime/client.test.ts --run
pnpm --dir webapp run build
```

If backend producer paths are changed:

```powershell
python -m pytest server/tests/test_web_realtime_api.py server/tests/test_ui_transport_v3.py -q --tb=short
python -m pytest server/tests/test_web_support_api.py -k "message or timeline or operation" -q --tb=short
```

Remote/live signoff after commit/deploy:

```powershell
python scripts/release_server_to_remote.py --leave-running
python scripts/manage_remote_stack.py smoke server
pnpm --dir webapp run check:remote:webapp -- --base-url http://192.168.100.17:8666
```

Manual browser checklist:

- `/app/tickets` selected ticket receives external message without manual refresh.
- Composer still clears and refreshes after own public reply/internal note.
- First-response SLA/next action stops or changes after a qualifying public support reply.
- Diagnostic started/result cards move from accepted/running/no-result to final result without page reload.
- Queue row count/unread/requester reply indicator updates after incoming message.
- Realtime subscription does not subscribe to every visible row.
- Route change from one ticket to another does not leak old subscription.

## Risks And Guards

- **Duplicate refetch storms:** invalidate by selected-ticket keys and avoid all-row subscriptions.
- **Stale closure over selected ticket:** use `selectedTicketIdRef` or local hook state to compare current route before invalidating selected-ticket detail.
- **Timeline tab mismatch:** invalidate timeline query by prefix, not only the current exact filter.
- **Lost events during reconnect:** first implementation uses refetch-after-reconnect or fallback polling; later improvement can add event-id catch-up if needed.
- **Backend double push:** audit before modifying producers; do not add push where an existing service already publishes after commit.
- **Manual-refresh regression:** keep existing refresh button and `refreshSelectedTicketData()` path intact.

## Handoff

## P14 Execution Notes

Completed locally:

- Added selected-ticket realtime subscription to `webapp/src/pages/tickets/list-page.tsx`.
- Reused `getSharedWebRealtimeClient().subscribeTicket(...)`; no new transport was added.
- Invalidates selected workspace, active timeline queries, queue data and passport evidence candidates on selected-ticket `ticket_event` / `operation_updated`.
- Keeps existing fast polling for active operations and adds bounded selected-ticket fallback polling for non-operation message catch-up.
- Added tests in `webapp/src/pages/tickets/list-page.test.tsx` for selected-ticket subscription, selected-only invalidation, active standalone timeline refresh and unsubscribe on ticket change.
- Backend producer audit found existing push paths in `server/web_api/support_handlers.py`, `server/tickets/handlers.py`, `server/tools/service.py`, `server/websocket/command_result_components.py`, `server/websocket/outbox_ingest_components.py` and `server/app/services/operation_service.py`; no backend code change was needed.
- Remote live check showed public support messages now appear in the selected ticket without manual refresh in under one second.
- Remote operation check found a second root cause for diagnostics: the central `Все` timeline used the aggregate `/workspace` timeline, while fresh operation results were present in the typed `/timeline?filter=diagnostics` endpoint. The page now loads `filter=all` through the typed timeline endpoint as well, with aggregate timeline as loading fallback.
- Added a regression test that the `Все` timeline calls `fetchSupportTicketTimeline(ticketId, "all")` and refreshes it on `operation_updated`.
- Follow-up remote check found the server `filter=all` timeline could still truncate fresh server-side operation events on tickets with long agent history. `_build_support_timeline_payload()` now uses expanded prefetch for every filter and returns the latest `limit` matching support events in chronological order.
- Added a backend regression test for long agent history plus a fresh `tool_call_result` server event.

Verification completed:

```powershell
pnpm --dir webapp exec vitest run src/pages/tickets/list-page.test.tsx --run -t "all timeline"
pnpm --dir webapp exec vitest run src/pages/tickets/list-page.test.tsx --run
pnpm --dir webapp exec vitest run src/pages/tickets/list-page.test.tsx src/shared/realtime/client.test.ts --run
pnpm --dir webapp run build
python -m pytest server\tests\test_web_support_api.py -k "all_timeline_keeps_recent or ticket_timeline_endpoint_filters_normalized_events" -q --tb=short
python -m pytest server\tests\test_web_realtime_api.py server\tests\test_ui_transport_v3.py -q --tb=short
python -m pytest server\tests\test_web_support_api.py -k "message or timeline or operation" -q --tb=short
```

Note: an earlier parallel backend pytest attempt produced DB deadlock/connection-closed errors because two DB-backed suites cleaned the shared test database concurrently. The same suites passed when rerun sequentially.

Next implementation checkpoint: run final workspace verification, then remote deploy/browser live check if the user wants this shipped to the stand in the same slice.

---

# Admin Observer Explainable Trace Layer Plan

> Active slice refreshed 2026-05-09. This replaces the previous observer modernization checklist. Earlier completed work (ticket-code search, trace cards with `T-000520`, typed trace-detail route) remains the baseline; this plan focuses on making every operation/error trace explainable for an operator.

**Goal:** make `/app/admin/observer` answer four questions without reading UUIDs: what started, who/what started it, why it failed, and what the operator should do next.

**Architecture:** add a server-side explainability projection on top of existing observer traces/spans/operations/events. Keep raw trace/span data intact for debug mode, but expose compact typed fields for launch source, actor, tool/module labels, error diagnosis, launch path, next actions, and stage semantics. React should render those fields first and keep raw ids/details behind an advanced/debug affordance.

**Tech Stack:** Python 3, aiohttp typed web API, SQLAlchemy async models/repos, observer projection in `server/observer/service.py`, admin DTO/mapping in `server/web_api/*`, module/tool metadata from manifests/tool catalog, React/Vite admin UI in `webapp/src/features/tech/*`.

---

## Current Analysis

- Baseline from the previous observer slice is partially done: `/api/web/admin/observer/*` already enriches traces with `ticket_code`, ticket title/status/priority/queue, device hostname/label, operation labels and `display_title` / `display_subtitle`.
- Search by ticket number now works when `observer_traces.attrs_json.ticket_code` is present, including `T-000520`.
- The current detail still exposes technical spans too directly: `operation.tool_call`, `operation.stage.queued`, `operation.stage.failed` are visible before a plain-language diagnosis.
- `operation.stage.queued` currently inherits the terminal operation status through `_build_operation_stage_spans()`, so a queued stage can appear red even when the real failure happened later. For `T-000520`, that made `queued` look broken although the root cause was `AGENT_NOT_CONNECTED` before dispatch.
- Operation source is inferable but not first-class: `actor_role` exists in `operations` and `tool_call_started.payload`, `playbook_run.trigger_type` exists for playbook paths, form triggers and diagnostic policy write `playbook_started` / `diagnostic_autorun_*`, retries have `retry_of_operation_id`, but the observer DTO does not normalize this into `launch_source`.
- Human actor is incomplete: `actor_role=admin/support` is visible in raw attrs, but `actor_id` / display name is not consistently captured in operation or event payloads. The first implementation should surface what exists and add non-breaking fields where support/admin run handlers can provide them.
- Tool/module labels should not be hardcoded for `system.collect`. Current sources include builtin tool specs (`pc_agent/modules/impl/*`), server module manifest JSON (`modules` table / `server/modules/workbench_service.py`), support tool catalog metadata, presets, params schema, output contract and risk metadata. The observer projection should resolve labels from these sources and fall back safely to `tool_name`.
- Error signatures already contain machine fields (`error_kind`, `failure_stage`, `message_norm`) and operation rows contain `error_code` / `error_message`; there is no canonical human diagnosis layer yet.
- The GUI has no clear separation between operator summary and raw technical data. It needs an explanation block above spans and a raw/debug mode below.

## Scope

- Backend observer explainability projection for operation-bound and ticket-root traces.
- Typed admin observer DTOs and API responses.
- React observer workbench trace list/detail/signature rows.
- Tool/module metadata lookup from manifests/catalogs for generic module labels and presets.
- Observer docs/CODEMAP updates because this changes trace-visible API semantics.
- Tests for `T-000520`-style `AGENT_NOT_CONNECTED`, manual launch, auto/playbook/retry classification and stage coloring.

## Non-Goals

- Do not change operation dispatch, retry, consent, policy enforcement, Protocol V3, agent command payloads or ticket workflow state.
- Do not delete raw ids, raw spans or raw attrs. Move them behind debug/technical sections.
- Do not make observer mutate tickets/devices/modules.
- Do not build a full CMDB/inventory replacement inside observer.
- Do not hardcode `system.collect`; the label/preset mechanism must work for all tools/modules with metadata.

## Status

Overall progress: **65% for refreshed explainability slice**.

Working mode: **Execute / Boundary / Observer UI**.

Change classification: **cross-cutting observer display contract**. The slice touches observer projection, typed web DTOs, React UI, docs and tests, but should not change runtime execution semantics.

## Phase Progress

| Phase | Scope | Progress | Status |
|---|---|---:|---|
| E0 | Replace stale observer plan with explainable trace-layer plan | 100% | Completed |
| E1 | Backend launch-source and actor projection | 70% | Implemented for operation-bound/manual/retry/playbook/system heuristics; config refs remain later |
| E2 | Generic tool/module metadata labels and preset summaries | 55% | Implemented from current device toolset snapshots with fallback; broader manifest/catalog backfill remains later |
| E3 | Human error diagnosis and next-action catalog | 60% | Implemented initial catalog for agent offline, timeout and policy denied |
| E4 | Stage semantics and span status correction | 100% | Implemented |
| E5 | Typed DTO/API integration and search/list enrichments | 60% | Detail DTO implemented; list badges/latest human error remain later |
| E6 | React trace list/detail UI and raw/debug mode | 55% | Explanation block implemented; dedicated raw/debug toggle remains later |
| E7 | Filters, badges and human timeline | 0% | Pending |
| E8 | Tests, docs, browser/live verification | 50% | Focused tests/docs in progress; full verify and live T-000520 check pending |

## Implementation Checkpoint 2026-05-09

Completed in the first execution slice:

- Added typed `explanation` to admin observer trace detail and compatibility `trace-detail` payloads.
- Added launch-source, actor, tool/module/preset, human diagnosis, launch path, next-action, agent status and debug-ref fields.
- Corrected operation stage projection so intermediate `queued` stages are not rendered as separate errors after a later terminal failure.
- Added stage DTO fields: `stage_label`, `stage_state`, `stage_note`, `is_failure_stage`.
- Updated `/app/admin/observer` trace detail to render the explanation block before technical spans.
- Added backend regression coverage for a `T-000520`-style manual `AGENT_NOT_CONNECTED` operation and frontend coverage for the explanation block.

Still open for the next slice:

- Trace-list badges/filters for launch source, autorun, retry and agent-offline.
- Dedicated raw/debug mode toggle for UUIDs, attrs and span internals.
- Broader auto-run configuration refs: form trigger, diagnostic policy and playbook trigger labels.
- Broader tool metadata backfill from server module manifests when the device has no current toolset snapshot.

## Required Product Behavior

Observer detail must show, above technical spans:

- **Источник запуска:** `Ручной запуск`, `Автозапуск формы`, `Diagnostic policy`, `Playbook`, `Retry`, `System`.
- **Запустил:** display name if available, otherwise `admin`, `support`, `system`, `playbook`, or `unknown` with role badge.
- **Понятный диагноз:** examples: `Агент на устройстве не подключен. Команда не была отправлена.`, `Агент не ответил за N секунд.`, `Запуск запрещён политикой.`
- **Путь запуска:** `Тикет T-000520 -> ручной запуск инструмента -> Сбор диагностики -> агент offline -> failed`.
- **Что делать дальше:** contextual actions such as check agent connection, open inventory device, open ticket, inspect policy, open playbook run, retry if allowed.
- **Tool/module label:** derive from manifest/catalog metadata for every tool/module, not only `system.collect`. Include preset/params summary when metadata allows it.
- **Technical details:** raw `trace_id`, `operation_id`, `span_id`, `source_ref`, `attrs_json` remain available in raw/debug mode.

## Backend Design

### E1: Launch Source And Actor Projection

**Files to inspect/modify:**

- `server/observer/service.py`
- `server/web_api/admin_handlers.py`
- `server/web_api/dto/admin.py`
- `server/tools/service.py`
- `server/web_api/support_handlers.py`
- `server/api/operations.py`
- `server/playbooks/form_triggers.py`
- `server/app/services/playbook_engine.py`
- `server/app/db/models.py`
- `server/tests/test_observer_v2_api.py`

**Fields to add to typed trace/operation explanation DTOs:**

- `launch_source: "manual" | "form_autorun" | "diagnostic_policy" | "playbook" | "retry" | "system" | "unknown"`
- `launch_source_label: str`
- `launch_trigger_type: str | null`
- `launch_config_label: str | null`
- `launch_config_ref: dict | null`
- `actor_role: str | null`
- `actor_id: str | null`
- `actor_display_name: str | null`
- `actor_label: str`
- `is_autorun: bool`
- `is_retry: bool`
- `retry_of_operation_id: str | null`

**Classification rules:**

- `retry_of_operation_id` present -> `retry`.
- `playbook_run_id` or matching `playbook_run.operation_id/context_json` -> `playbook`.
- `playbook_started.payload.source == diagnostic_policy` or trigger `diagnostic_policy_auto_run` -> `diagnostic_policy`.
- `playbook_started.payload.source == request_form` or `request_form_playbook_triggers` match -> `form_autorun`.
- `tool_call_started.payload.actor_role in admin/support` without playbook/autopolicy markers -> `manual`.
- server maintenance/runtime roots without ticket actor -> `system`.
- Otherwise `unknown`, with raw hints preserved for debug.

**Acceptance:**

- `T-000520` operation `d2a8198f-...` is classified as `manual`, label `Ручной запуск`, actor `admin`, not auto.
- Form/playbook auto-runs show which trigger/config started them.
- Retries link back to source operation.
- No N+1 queries: batch-load operations, events and playbook runs for visible traces.

### E2: Generic Tool/Module Metadata Labels

**Files to inspect/modify:**

- `shared/tool_contracts.py`
- `server/modules/workbench_service.py`
- `server/modules/handlers.py`
- `server/web_api/support_handlers.py`
- `server/observer/service.py`
- `server/web_api/admin_handlers.py`
- `pc_agent/core/tools.py`
- `pc_agent/modules/impl/system.py`
- `server/tests/test_observer_v2_api.py`

**Fields to add:**

- `tool_label: str | null`
- `module_label: str | null`
- `tool_description: str | null`
- `module_description: str | null`
- `tool_risk_label: str | null`
- `preset_id: str | null`
- `preset_label: str | null`
- `params_summary: list[str]`
- `result_summary_human: str | null`

**Metadata lookup order:**

1. Tool catalog / support tools payload if available for the device/tool.
2. Server module manifest JSON: `tools[].name`, `tools[].description`, `presets[]`, `params_schema`, `output_contract`, `risk_level`.
3. Builtin agent tool specs from registered metadata when surfaced through toolset snapshots.
4. Fallback: split `module.tool` into module and tool ids.

**Acceptance:**

- `system.collect` with `{preset_id: "minimal"}` renders as `Сбор диагностики: minimal` and summary like `CPU + память` based on preset metadata.
- Other tools render labels/descriptions from their manifest/spec without hardcoded observer UI branches.
- If metadata is missing, observer still shows stable `module.tool` fallback and does not break the trace detail.

### E3: Human Error Diagnosis And Next Actions

**Files to inspect/modify:**

- `server/observer/service.py`
- `server/web_api/admin_handlers.py`
- `server/web_api/dto/admin.py`
- `server/tools/handlers.py`
- `server/api/operations.py`
- `webapp/src/features/tech/api.ts`
- `webapp/src/features/tech/observer-workbench-api.ts`

**Fields to add:**

- `error_code: str | null`
- `error_label: str | null`
- `error_diagnosis: str | null`
- `error_explanation: str | null`
- `failure_stage_label: str | null`
- `dispatch_state_label: str | null`
- `next_actions: list[{label, kind, href?, disabled_reason?}]`
- `agent_last_seen_at: str | null`
- `agent_online_label: str | null`

**Minimum diagnosis catalog:**

- `AGENT_NOT_CONNECTED`: `Агент на устройстве не подключен. Команда не была отправлена.` Next actions: open device, check last handshake, start/connect agent, retry if policy allows.
- `TIMEOUT` / `WS_COMMAND_TIMEOUT` / `MODULE_INSTALL_TIMEOUT`: `Агент не ответил за отведённое время.` Include timeout if known.
- `POLICY_DENIED` / policy reason: `Запуск запрещён политикой.` Include required role/consent when available.
- `MODULE_NOT_ON_SERVER`: `Модуль не найден на сервере.` Link module registry if possible.
- `CONSENT_REQUIRED` / `waiting_consent`: `Нужно согласие пользователя перед запуском.` Link consent operation if available.
- Unknown errors: show sanitized `error_message`, signature and debug link without leaking raw payloads.

**Acceptance:**

- Detail top card shows one clear reason line before span list.
- Error list and trace list show `latest_error_label` / `error_diagnosis`, not just `error`.
- Next actions are contextual and safe; no action bypasses existing permission/policy checks.

### E4: Stage Semantics And Span Status Correction

**Files to inspect/modify:**

- `server/observer/service.py`
- `server/web_api/dto/admin.py`
- `server/web_api/admin_handlers.py`
- `webapp/src/features/tech/observer-quick-panel.tsx`
- `server/tests/test_observer_v2_api.py`

**Required behavior:**

- Intermediate stages (`queued`, `sent`, `accepted`, `running`) should not automatically be `error` only because the operation terminal status is `failed`.
- If an operation fails before dispatch, `queued` should render as `passed_before_failure` / `До ошибки`, while terminal `failed` and operation root are error.
- Stage DTO should include `stage_label`, `stage_state`, `stage_note`, `is_failure_stage`.

**Acceptance:**

- For `T-000520`, `operation.stage.queued` is not presented as a separate failure; `operation.stage.failed` carries the failure.
- Existing signatures/degradations still count the operation error once.
- Tests cover queued->failed without sent/accepted/started.

### E5: Typed API Shape And Backward Compatibility

**Files to inspect/modify:**

- `server/web_api/dto/admin.py`
- `server/web_api/admin_handlers.py`
- `webapp/src/features/tech/api.ts`
- `webapp/src/features/tech/observer-workbench-api.ts`
- `server/tests/test_web_admin_api.py`
- `webapp/src/features/tech/observer-workbench-api.test.ts`

**Acceptance:**

- Existing fields remain backward-compatible.
- New `explanation` object is present on trace detail and compact equivalent fields are present on trace list rows.
- `readTypedOrLegacyOk` behavior remains valid for typed/legacy detail endpoints.
- API tests assert manual/offline explanation for a synthetic operation.

## UI Design

### E6: Trace List And Detail Explanation UI

**Files to inspect/modify:**

- `webapp/src/features/tech/observer-quick-panel.tsx`
- `webapp/src/features/tech/observer-trace-drilldown.tsx`
- `webapp/src/features/tech/api.ts`
- `webapp/src/pages/admin/index.test.tsx`
- `webapp/src/features/tech/observer-quick-panel.test.tsx`

**Required layout:**

- Trace list row: title, ticket/device/tool, launch-source badge, actor badge, latest human error, duration/age, raw trace id secondary.
- Detail hero: `Причина ошибки`, `Путь запуска`, `Запустил`, `Устройство/агент`, `Что делать дальше`.
- Technical spans section below: grouped timeline with failure stage highlighted.
- Raw/debug toggle: reveals UUIDs, `attrs_json`, `source_ref`, `span_id`, `error_signature`.

**Acceptance:**

- Operator can understand `T-000520` without opening raw attrs.
- UUIDs are copyable but no longer the primary visual object.
- Console has no new errors.

### E7: Badges, Filters And Human Timeline

**Files to inspect/modify:**

- `webapp/src/features/tech/observer-quick-panel.tsx`
- `webapp/src/features/tech/api.ts`
- `server/observer/service.py`
- `server/web_api/admin_handlers.py`

**Badges:**

- `ручной`, `авто`, `diagnostic policy`, `playbook`, `retry`, `system`
- `agent offline`, `не отправлено агенту`, `timeout`, `policy denied`
- `debug/raw available`

**Filters:**

- errors only
- manual launches
- autoruns
- offline agent
- playbook
- retry
- system

**Human timeline examples:**

- `14:31 admin запустил диагностику.`
- `14:31 сервер проверил подключение агента.`
- `14:31 агент не подключен, команда не отправлена.`
- `14:31 операция завершена ошибкой.`

**Acceptance:**

- Filters are backed by typed query params where practical, or client-side only for already loaded detail lists if backend filtering would be too broad for the first slice.
- Human timeline is generated from normalized explanation fields, not from brittle string parsing of raw span names.

## Verification Matrix

Minimum local verification:

```powershell
python scripts/verify_workspace.py
python scripts/bootstrap_web_toolchain.py
python -m pytest server/tests/test_observer_v2_api.py -q --tb=short
python -m pytest server/tests/test_web_admin_api.py -k "observer" -q --tb=short
pnpm --dir webapp exec vitest run src/pages/admin/index.test.tsx src/features/tech/observer-quick-panel.test.tsx src/features/tech/observer-workbench-api.test.ts --run
pnpm --dir webapp run build
```

Targeted live/browser verification:

```powershell
python scripts/manage_remote_stack.py start server
python scripts/manage_remote_stack.py smoke server
pnpm --dir webapp run check:remote:webapp -- --base-url http://192.168.100.17:8666
```

Manual live checklist:

- Open `http://192.168.100.17:8666/admin`, navigate to `/app/admin/observer`.
- Search `T-000520`.
- Open trace `5bdd530e-c652-46b3-b307-15f05a580b34`.
- Confirm failed operation `d2a8198f-69e1-47b0-a56b-4a438d176fe6` shows `Ручной запуск`, `Запустил: admin`, `Агент на устройстве не подключен. Команда не была отправлена.`
- Confirm launch path reads like `Тикет T-000520 -> ручной запуск инструмента -> Сбор диагностики -> агент offline -> failed`.
- Confirm `queued` is not shown as a separate red failure.
- Confirm raw/debug mode still exposes `operation.tool_call`, `operation.stage.failed`, UUIDs and attrs.
- Stop the remote server after checks unless explicitly asked to keep it running:

```powershell
python scripts/manage_remote_stack.py stop server
```

## Documentation Updates Required If Code Changes

- `server/docs/OBSERVER_LAYER.md`: explain new explanation projection, launch source taxonomy, stage semantics and raw/debug layering.
- `server/docs/OBSERVER_AUTHORING_RULES.md`: require future dangerous flows to provide enough actor/source/error context for observer explanation.
- `server/docs/CODEMAP.md`: update observer/web API entries and module metadata lookup path.
- `docs/QUICK_LOOKUP.md`: add operator checklist for observer incident triage.
- `scripts/navigation_catalog.py`: update observer topic aliases/checks if new files/helpers are added.

## Risks And Guards

- **Incorrect source attribution:** use explicit markers first (`retry_of_operation_id`, `playbook_run_id`, `playbook_started`, diagnostic policy payload), then fallback to actor role. Never guess auto-run from tool name alone.
- **Hardcoded tool labels:** use manifest/catalog metadata lookup; hardcoded labels are allowed only as fallback for missing metadata and should live in one backend helper, not in React.
- **DTO bloat:** trace lists get compact explanation fields; full next actions/raw details live in detail endpoint.
- **N+1 performance:** batch-load tickets, devices, operations, events, playbook runs and module/tool metadata.
- **Privacy/security:** sanitize error messages and params summaries; do not expose raw tokens, file paths, consent tokens or internal auth data.
- **Regression in developer diagnostics:** raw/debug mode must preserve IDs and attrs for engineers.
- **Misleading stage colors:** stage status must reflect stage outcome, not blindly mirror terminal operation status.

## Handoff

Start implementation with backend tests for `T-000520`-style manual offline operation, auto/playbook/retry classification and queued-stage semantics. Then add the projection helpers and DTO fields, then update React rendering. Do not start by changing only CSS/labels; the UI must receive normalized explanation data from the typed observer boundary.
