# Support Workspace Adaptive Modes

## Goal

Improve the existing support workspace without replacing the current interface or business logic. Add adaptive operator modes:

- `ticket`: current ticket, timeline and composer remain the primary work area.
- `queue`: queue triage expands into a dense table with selected ticket preview.
- `tools`: tools, operations and remote assist get a wider workspace.
- `sla`: SLA/OLA timers and escalation state get an analytic workspace.
- `passport`: resolution passport gets a structured closing workspace.

## Boundaries

- Work only in the local Windows copy: `C:\Users\admin-2\CodexProjects\pc_client`.
- Preserve existing APIs and permission boundaries.
- Reuse current queue/workspace payloads before adding backend endpoints.
- Keep the current dark design system.
- Do not rewrite ticket messages, diagnostics, SLA, remote assist or passport flows.

## Current Findings

- Main route owner: `webapp/src/pages/tickets/list-page.tsx`.
- Existing state already covers selected ticket, scope, smart view, active queue, right tab, timeline filter, composer and column resize.
- Existing right tabs already cover `context`, `sla`, `tools`, `knowledge`, `passport`.
- Existing endpoints are enough for the first frontend slice:
  - `GET /api/web/support/queue`
  - `GET /api/web/support/tickets/{ticket_id}/workspace`
  - `GET /api/web/support/tickets/{ticket_id}/timeline`
  - `GET /api/web/support/tickets/{ticket_id}/tools`
  - `GET /api/web/support/tickets/{ticket_id}/playbooks`
  - `GET /api/web/support/tickets/{ticket_id}/passport`
  - `POST /api/operations/{operation_id}/cancel`
  - `POST /api/operations/{operation_id}/retry`
- No backend change was needed for the first implementation pass.

## Implemented

- [x] Added `WorkspaceMode` and layout/localStorage helpers in `webapp/src/pages/tickets/workspace-types.ts`.
- [x] Added mode-aware grid presets and root `data-mode`.
- [x] Preserved existing manual column resize in `ticket` mode.
- [x] Added Escape return from expanded modes to `ticket`.
- [x] Added `Развернуть очередь` and Queue Mode table.
- [x] Added selected ticket preview for Queue Mode.
- [x] Clicking a ticket opens Ticket Mode.
- [x] Right tabs for `Инструменты`, `SLA`, `Паспорт` switch to expanded modes.
- [x] Added `Вернуться к чату` in expanded modes.
- [x] Added expanded Tools framing with quick tabs and operations table.
- [x] Added expanded SLA overview cards derived from existing timers.
- [x] Added expanded Passport section grid and readiness framing.
- [x] Added transition CSS for mode grid changes.
- [x] Added regression tests for mode switching and localStorage restore.
- [x] Persisted active right tab, selected smart view and selected queue.
- [x] Added regression tests for restored right tab and queue filters.
- [x] Extracted new mode-specific helper components from `list-page.tsx`:
  - `expanded-workspace-header.tsx`
  - `operations-table.tsx`
  - `queue-explorer.tsx`
  - `ticket-preview-panel.tsx`
  - `workspace-component-utils.ts`
- [x] Added interactive Tools Mode tabs:
  - Быстрые
  - Playbook
  - Удалённая помощь
  - Операции
  - История
- [x] Added interactive SLA Mode tabs:
  - SLA обзор
  - OLA
  - Эскалации
  - История сроков
- [x] Added interactive Passport Mode tabs:
  - Секции
  - Доказательства
  - Операции
  - Готовность

## Files Changed

- `webapp/src/pages/tickets/list-page.tsx`
- `webapp/src/pages/tickets/list-page.test.tsx`
- `webapp/src/pages/tickets/workspace-types.ts`
- `webapp/src/pages/tickets/components/expanded-workspace-header.tsx`
- `webapp/src/pages/tickets/components/operations-table.tsx`
- `webapp/src/pages/tickets/components/queue-explorer.tsx`
- `webapp/src/pages/tickets/components/ticket-preview-panel.tsx`
- `webapp/src/pages/tickets/components/workspace-component-utils.ts`
- `webapp/src/styles.css`
- `PLANS.md`

## Verification

- [x] `pnpm --dir webapp exec vitest run src/pages/tickets/list-page.test.tsx`
- [x] `pnpm --dir webapp run build`
- [x] `python scripts/verify_workspace.py`
- [x] Re-ran the same three checks after the persistence slice.
- [x] Re-ran the same three checks after component extraction.
- [x] Re-ran the same three checks after interactive Tools Mode tabs.
- [x] Re-ran the same three checks after interactive SLA/Passport Mode tabs.
- [ ] Browser verification on `http://192.168.100.17:8666/admin` after deploy/release to the remote stand.

## Remaining TODO

- Add deeper SLA policy details and passport edit forms when backend exposes more normalized workspace data.
- Add browser verification after the user asks to deploy this branch to the remote stand.

## Manual Check After Deploy

1. Open `http://192.168.100.17:8666/admin`.
2. Open support workspace and select a ticket.
3. Confirm default `ticket` mode keeps header, next action, timeline and composer.
4. Click `Развернуть очередь`; confirm queue table and preview appear.
5. Select a queue row; confirm preview changes without full chat takeover.
6. Click `Открыть тикет`; confirm return to ticket mode.
7. Click `Инструменты`; confirm tools mode expands and operations are readable.
8. Click `SLA`; confirm expanded SLA overview appears.
9. Click `Паспорт`; confirm passport sections and readiness appear.
10. Click `Вернуться к чату` and press Esc from expanded modes; confirm both return to ticket mode.
