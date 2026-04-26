# Ticket Status And Work Visibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a production-grade ticket lifecycle where requester, support, observer and reports always show who owns the next action, what is happening now, why a ticket is waiting, and what evidence supports closure.

**Architecture:** Extend the existing ticket domain instead of replacing it: add explicit workflow fields and wait/evidence tables, expand the canonical FSM, expose typed DTOs through `/api/web/*`, then update React, legacy requester UI and agent GUI against the same contracts. Keep operations as an execution substate, observer as a trace overlay, and request forms/routing as contextual inputs.

**Tech Stack:** Python aiohttp, SQLAlchemy/Alembic, PostgreSQL JSONB, pytest, React + TypeScript + TanStack Query, Playwright, project deploy scripts.

---

## Current Baseline

- Canonical statuses currently live in `server/tickets/statuses.py`: `new`, `triaged`, `in_progress`, `waiting_on_user`, `waiting_on_vendor`, `resolved`, `closed`.
- Workflow transitions currently live in `server/tickets/workflow_service.py`.
- Ticket storage already includes SLA/OLA, queue, assignee, priority, resolution, root cause and `observer_root_trace_id` in `server/app/db/models.py`.
- Ticket events are the append-only history source in `ticket_events`; chat messages are stored as `event_type="chat_message"`.
- Typed support detail is in `server/web_api/support_handlers.py` and `server/web_api/dto/support.py`.
- React support workspace is in `webapp/src/features/queues/support-workspace.tsx`.
- Requester-facing legacy ticket UI is in `server/ticket.js`; agent GUI labels are in `pc_agent/ui_gui/ticket_format.py` and `pc_agent/ui_gui/chat_panel.py`.

## Target Product Contract

### Internal Statuses

Use these canonical status values in the database and API:

| Status | Meaning | Default next action owner |
|---|---|---|
| `new` | Ticket created and not classified | `support` |
| `queued` | Routed to queue, not assigned | `support` |
| `assigned` | Responsible operator exists, active work not started | `support` |
| `in_progress` | Support is actively working | `support` |
| `waiting_on_user` | Requester must answer or confirm | `requester` |
| `waiting_on_internal_team` | Another internal queue/team owns the next action | `internal_team` |
| `waiting_on_vendor` | External contractor/provider/vendor is being waited on | `vendor` |
| `waiting_on_approval` | Approver must approve or reject | `approver` |
| `scheduled` | Work is planned for a known time/window | `support` |
| `resolved` | Support marked as solved, waiting confirmation/autoclose policy | `requester` |
| `closed` | Lifecycle completed | `none` |
| `canceled` | Ticket invalid, duplicate or no longer relevant | `none` |

### Requester Status Mapping

Expose a requester-safe status block in API payloads:

| Internal statuses | Requester status | Label |
|---|---|---|
| `new`, `queued`, `assigned` | `accepted` | requester-facing "ticket accepted" label |
| `in_progress`, `scheduled`, `waiting_on_internal_team`, `waiting_on_vendor`, `waiting_on_approval` | `in_work` | requester-facing "ticket in work" label |
| `waiting_on_user` | `needs_requester` | requester-facing "your answer is needed" label |
| `resolved` | `review_solution` | requester-facing "review the solution" label |
| `closed` | `closed` | requester-facing "closed" label |
| `canceled` | `canceled` | requester-facing "canceled" label |

### New Ticket Fields

Add to `tickets`:

- `status_reason TEXT NULL`
- `next_action_owner VARCHAR(30) NOT NULL DEFAULT 'support'`
- `next_action_due_at TIMESTAMP WITH TIME ZONE NULL`
- `scheduled_for TIMESTAMP WITH TIME ZONE NULL`
- `canceled_at TIMESTAMP WITH TIME ZONE NULL`
- `canceled_reason TEXT NULL`
- `resolution_summary TEXT NULL`
- `requester_visible_resolution TEXT NULL`
- `closure_feedback JSONB NOT NULL DEFAULT '{}'::jsonb`
- `evidence_policy JSONB NOT NULL DEFAULT '{}'::jsonb`

Add new tables:

- `ticket_waits`: durable wait ledger for user/vendor/internal/approval pauses.
- `ticket_evidence`: closure evidence and operation/artifact references.
- `ticket_approvals`: simple approval workflow state.
- `ticket_status_transition_rules`: optional admin-visible transition catalog seeded from code.

---

## Files And Responsibilities

- `server/tickets/statuses.py`: canonical statuses, labels, requester mapping, next-action owner derivation, status reason validation.
- `server/tickets/workflow_service.py`: FSM transitions and side effects.
- `server/tickets/wait_service.py`: start/end wait rows and SLA/OLA pause linkage.
- `server/tickets/resolution_policy_service.py`: enforce resolution fields and evidence policy.
- `server/tickets/passport_service.py`: ticket passport/dossier assembly.
- `server/app/db/models.py`: SQLAlchemy models for new fields/tables.
- `server/app/db/migrations/versions/<new>_ticket_work_visibility.py`: schema migration and backfill.
- `server/app/api/serializers.py`: legacy and shared ticket payload fields.
- `server/tickets/handlers.py`: legacy requester/support API status, message, close, passport and evidence endpoints.
- `server/web_api/dto/support.py`: typed support DTOs for status, next action, SLA/OLA, evidence, passport summary.
- `server/web_api/support_handlers.py`: typed support queue/detail/actions payloads.
- `server/web_api/settings_handlers.py` and `server/tickets/admin_config_handlers.py`: status reason, resolution and evidence policy settings.
- `server/web_api/reports_handlers.py`: metrics for next-action owner, waits and reopened/resolution quality.
- `webapp/src/features/queues/api.ts`: TypeScript API contract.
- `webapp/src/features/queues/support-workspace.tsx`: operator UX, filters, right context panel, closure modal.
- `webapp/src/pages/tickets/detail-page.tsx`: requester view with public status mapping and next action.
- `server/ticket.js`: legacy requester shell parity.
- `pc_agent/ui_gui/ticket_format.py`, `pc_agent/ui_gui/chat_panel.py`, `pc_agent/ui_gui/server_api.py`: local requester GUI status mapping and confirmation flow.
- `server/docs/TICKET_SYSTEM.md`, `server/docs/CODEMAP.md`, `docs/QUICK_LOOKUP.md`, `docs/ARCHITECTURE_BOUNDARIES.md`: docs sync.

---

### Task 0: Preflight And Context Lock

**Files:**
- Read: `AGENTS.md`
- Read: `docs/QUICK_LOOKUP.md`
- Read: `docs/ARCHITECTURE_BOUNDARIES.md`
- Read: `server/docs/TICKET_SYSTEM.md`
- Read: `server/docs/OBSERVER_LAYER.md`
- Modify: `PLANS.md`

- [ ] **Step 1: Bootstrap UTF-8 shell**

Run:

```powershell
.\scripts\bootstrap_shell_utf8.ps1
```

Expected: output contains `PowerShell UTF-8 bootstrap applied.`

- [ ] **Step 2: Refresh task intake**

Run:

```powershell
python scripts/task_intake.py --task "ticket status lifecycle next_action_owner requester status mapping evidence closure passport support visibility live testing"
```

Expected: output names ticket/helpdesk, web boundary, docs and verification targets.

- [ ] **Step 3: Bootstrap frontend toolchain before web commands**

Run:

```powershell
python scripts/bootstrap_web_toolchain.py
```

Expected: local Node.js 24.15.0, corepack and pnpm 10.33.0 are ready.

- [ ] **Step 4: Record active work in PLANS.md**

Add a short `Status: in progress` entry referencing this plan, current branch, and first implementation phase. Keep detailed steps in this file.

---

### Task 1: Data Model And Migration

**Files:**
- Modify: `server/app/db/models.py`
- Create: `server/app/db/migrations/versions/<revision>_ticket_work_visibility.py`
- Test: `server/tests/test_ticket_work_visibility_schema.py`

- [ ] **Step 1: Write schema tests**

Create tests that verify:

```python
async def test_ticket_work_visibility_columns_exist(test_engine):
    async with test_engine.begin() as conn:
        rows = await conn.exec_driver_sql(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'tickets'
              AND column_name IN (
                'status_reason',
                'next_action_owner',
                'next_action_due_at',
                'scheduled_for',
                'canceled_at',
                'canceled_reason',
                'resolution_summary',
                'requester_visible_resolution',
                'closure_feedback',
                'evidence_policy'
              )
            """
        )
        assert {row[0] for row in rows} == {
            'status_reason',
            'next_action_owner',
            'next_action_due_at',
            'scheduled_for',
            'canceled_at',
            'canceled_reason',
            'resolution_summary',
            'requester_visible_resolution',
            'closure_feedback',
            'evidence_policy',
        }
```

Also assert tables `ticket_waits`, `ticket_evidence`, `ticket_approvals`, and `ticket_status_transition_rules` exist.

- [ ] **Step 2: Run schema tests red**

Run:

```powershell
python -m pytest server/tests/test_ticket_work_visibility_schema.py -q --tb=short
```

Expected: fails because columns/tables do not exist.

- [ ] **Step 3: Add SQLAlchemy fields and models**

Update `Ticket` with the fields listed in `New Ticket Fields`.

Add model classes:

```python
class TicketWait(Base):
    __tablename__ = "ticket_waits"
    id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id = mapped_column(String(36), sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"), nullable=False, index=True)
    wait_type = mapped_column(String(30), nullable=False)
    reason = mapped_column(Text, nullable=True)
    related_party = mapped_column(Text, nullable=True)
    started_at = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    ended_at = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    started_by = mapped_column(Text, nullable=True)
    ended_by = mapped_column(Text, nullable=True)
    source_status = mapped_column(String(30), nullable=True)
    target_status = mapped_column(String(30), nullable=True)
```

Create equivalent SQLAlchemy models for evidence, approvals and transition rules with tight indexes on `ticket_id`, open waits and active approvals.

- [ ] **Step 4: Add migration and backfill**

Backfill current tickets:

```sql
UPDATE tickets
SET next_action_owner = CASE
    WHEN status = 'waiting_on_user' THEN 'requester'
    WHEN status = 'waiting_on_vendor' THEN 'vendor'
    WHEN status = 'resolved' THEN 'requester'
    WHEN status IN ('closed') THEN 'none'
    ELSE 'support'
END
WHERE next_action_owner IS NULL OR next_action_owner = '';
```

Backfill old `triaged` rows as `assigned` when `assignee_id IS NOT NULL`, otherwise `queued`, after the application code supports aliases.

- [ ] **Step 5: Run schema tests green**

Run:

```powershell
python -m pytest server/tests/test_ticket_work_visibility_schema.py -q --tb=short
```

Expected: pass.

---

### Task 2: Status Catalog, Mapping And Compatibility

**Files:**
- Modify: `server/tickets/statuses.py`
- Modify: `server/app/api/serializers.py`
- Test: `server/tests/test_ticket_status_catalog.py`

- [ ] **Step 1: Write status catalog tests**

Assert:

- all 12 internal statuses normalize correctly;
- legacy `triaged` normalizes to `assigned` when used in payload compatibility;
- requester mapping returns `accepted`, `in_work`, `needs_requester`, `review_solution`, `closed`, `canceled`;
- `next_action_owner_for_status()` returns the table values from `Target Product Contract`.

- [ ] **Step 2: Implement status helpers**

Add constants:

```python
CANONICAL_STATUSES = (
    "new",
    "queued",
    "assigned",
    "in_progress",
    "waiting_on_user",
    "waiting_on_internal_team",
    "waiting_on_vendor",
    "waiting_on_approval",
    "scheduled",
    "resolved",
    "closed",
    "canceled",
)
```

Add:

- `requester_status_for_internal(status: str) -> dict[str, str]`
- `next_action_owner_for_status(status: str) -> str`
- `is_waiting_status(status: str | None) -> bool`
- `is_terminal_status(status: str | None) -> bool`
- `status_label_ru(status: str | None) -> str`

- [ ] **Step 3: Serialize new status blocks**

In `ticket_to_dict`, include:

```python
"status_reason": getattr(ticket, "status_reason", None),
"next_action_owner": getattr(ticket, "next_action_owner", None),
"next_action_due_at": _iso(getattr(ticket, "next_action_due_at", None)),
"requester_status": requester_status_for_internal(getattr(ticket, "status", None)),
"scheduled_for": _iso(getattr(ticket, "scheduled_for", None)),
"canceled_at": _iso(getattr(ticket, "canceled_at", None)),
"canceled_reason": getattr(ticket, "canceled_reason", None),
"resolution_summary": getattr(ticket, "resolution_summary", None),
"requester_visible_resolution": getattr(ticket, "requester_visible_resolution", None),
```

- [ ] **Step 4: Run focused tests**

Run:

```powershell
python -m pytest server/tests/test_ticket_status_catalog.py server/tests/test_ticket_create_contracts.py -q --tb=short
```

Expected: pass after adjusting old `triaged` expectations to `queued` or `assigned`.

---

### Task 3: Workflow FSM And Side Effects

**Files:**
- Modify: `server/tickets/workflow_service.py`
- Create: `server/tickets/wait_service.py`
- Modify: `server/tickets/sla_service.py`
- Modify: `server/tickets/ola_service.py`
- Test: `server/tests/test_ticket_workflow_visibility.py`

- [ ] **Step 1: Write FSM tests**

Cover:

- `new -> queued -> assigned -> in_progress -> resolved -> closed`
- `in_progress -> waiting_on_user -> assigned` after requester reply
- `in_progress -> waiting_on_internal_team -> assigned`
- `in_progress -> waiting_on_vendor -> assigned`
- `in_progress -> waiting_on_approval -> in_progress`
- `waiting_on_approval -> canceled`
- `in_progress -> scheduled -> in_progress`
- `resolved -> in_progress` when requester rejects
- terminal `closed` and `canceled` cannot transition except admin reopen path if deliberately supported.

- [ ] **Step 2: Implement wait service**

`TicketWaitService.start_wait()` creates one open wait row per ticket and closes an existing open wait first.

`TicketWaitService.end_open_wait()` sets `ended_at`, `ended_by` and emits `ticket_wait_ended`.

Status transitions into waiting statuses call `start_wait`; transitions out call `end_open_wait`.

- [ ] **Step 3: Update workflow transition result**

Every status transition updates:

- `status`
- `status_reason`
- `next_action_owner`
- `next_action_due_at`
- lifecycle timestamps
- wait rows
- SLA pause/resume
- OLA ack/processing as applicable

Every event payload includes:

```python
{
    "from_status": from_status,
    "to_status": to_status,
    "status_reason": reason or "",
    "next_action_owner": next_action_owner,
    "next_action_due_at": next_action_due_at.isoformat() if next_action_due_at else None,
    "actor_id": actor_id,
    "actor_role": actor_role,
    "source": source,
}
```

- [ ] **Step 4: Run workflow tests**

Run:

```powershell
python -m pytest server/tests/test_ticket_workflow_visibility.py server/tests/test_ticket_create_contracts.py -q --tb=short
```

Expected: pass.

---

### Task 4: Resolution Governance, Evidence And Passport

**Files:**
- Modify: `server/tickets/resolution_policy_service.py`
- Create: `server/tickets/passport_service.py`
- Modify: `server/tickets/handlers.py`
- Modify: `server/web_api/support_handlers.py`
- Test: `server/tests/test_ticket_resolution_governance.py`
- Test: `server/tests/test_ticket_passport_api.py`

- [ ] **Step 1: Write resolution governance tests**

Assert resolving requires:

- active `resolution_code`;
- `resolution_summary`;
- `requester_visible_resolution`;
- evidence when category/request type policy requires it;
- vendor reference when `status_reason` indicates vendor handoff;
- approval row when `waiting_on_approval` was used.

- [ ] **Step 2: Implement evidence APIs**

Add endpoints:

- `POST /api/tickets/{ticket_id}/evidence`
- `GET /api/tickets/{ticket_id}/evidence`
- typed support aliases under `/api/web/support/tickets/{ticket_id}/evidence`

Evidence item fields:

- `evidence_type`
- `summary`
- `artifact_id`
- `operation_id`
- `visibility`
- `created_by`
- `created_at`

- [ ] **Step 3: Implement passport service**

`TicketPassportService.build(ticket_id)` returns:

- requester and registry context;
- location and device context;
- request form rows;
- status lifecycle;
- waits with durations;
- public messages summary;
- internal worklog summary;
- operations and diagnostic evidence;
- approvals;
- resolution and closure feedback;
- repeat instructions.

Add:

- `GET /api/tickets/{ticket_id}/passport`
- `GET /api/web/support/tickets/{ticket_id}/passport`

- [ ] **Step 4: Run governance tests**

Run:

```powershell
python -m pytest server/tests/test_ticket_resolution_governance.py server/tests/test_ticket_passport_api.py -q --tb=short
```

Expected: pass.

---

### Task 5: Typed Support API And Queue Filters

**Files:**
- Modify: `server/web_api/dto/support.py`
- Modify: `server/web_api/support_handlers.py`
- Modify: `server/app/api/serializers.py`
- Test: `server/tests/test_web_support_api.py`

- [ ] **Step 1: Extend DTO tests**

Assert queue items include:

- `requester_status`
- `next_action_owner`
- `next_action_due_at`
- `status_reason`
- `sla_state`
- `ola_state`
- `latest_ticket_operation`

Assert detail payload includes:

- `work_state`
- `sla`
- `ola`
- `waits`
- `evidence`
- `passport`
- `closure`
- `registry`
- `request_form`

- [ ] **Step 2: Add action filters**

Support queue filters:

- `my_active`
- `action_required`
- `requester_replied`
- `sla_risk`
- `waiting_requester`
- `waiting_internal`
- `waiting_vendor`
- `waiting_approval`
- `unassigned`
- `reopened`
- `mass_or_similar`

- [ ] **Step 3: Restrict latest operations to current ticket first**

In support snapshot, query recent operations by `ticket_id` before falling back to device operations. Label fallback rows as `scope="device"` so the UI does not confuse unrelated device work with current ticket work.

- [ ] **Step 4: Run API tests**

Run:

```powershell
python -m pytest server/tests/test_web_support_api.py server/tests/test_ticket_queue_routing_contracts.py -q --tb=short
```

Expected: pass.

---

### Task 6: React Support Workspace Product UI

**Files:**
- Modify: `webapp/src/features/queues/api.ts`
- Modify: `webapp/src/features/queues/support-workspace.tsx`
- Modify: `webapp/src/features/queues/support-workspace.test.tsx`
- Modify: `webapp/tests/support-workspace.spec.ts`
- Modify: `webapp/tests/fixtures/support_fixture_server.py`

- [ ] **Step 1: Update TypeScript contract**

Add typed structures for:

- `requester_status`
- `work_state`
- `sla`
- `ola`
- `waits`
- `evidence`
- `passport`
- `closure`
- `latest_operations.scope`

- [ ] **Step 2: Rebuild queue UI around next action**

Add queue chips and counters for the filters in Task 5. Each row must show:

- internal status;
- requester-safe status;
- next action owner;
- next action due;
- SLA/OLA risk;
- unread requester messages.

- [ ] **Step 3: Rebuild right context panel**

Panel blocks:

- requester;
- location;
- device;
- affected service/system;
- queue and assignee;
- SLA/OLA;
- waits;
- request form;
- similar/linked tickets;
- knowledge/evidence;
- latest ticket operations;
- observer trace.

- [ ] **Step 4: Add closure modal**

Before `resolved`, require:

- resolution code;
- resolution summary;
- requester-visible resolution;
- evidence attachment/operation when policy requires it.

- [ ] **Step 5: Run React checks**

Run:

```powershell
pnpm --dir webapp run test -- support-workspace
pnpm --dir webapp run build
```

Expected: tests and build pass.

---

### Task 7: Requester UI And Agent GUI

**Files:**
- Modify: `webapp/src/pages/tickets/detail-page.tsx`
- Modify: `server/ticket.js`
- Modify: `server/ticket.html`
- Modify: `pc_agent/ui_gui/ticket_format.py`
- Modify: `pc_agent/ui_gui/chat_panel.py`
- Modify: `pc_agent/ui_gui/server_api.py`
- Test: `pc_agent/tests/test_ticket_api_client_attachments.py`
- Test: `pc_agent/tests/test_support_chat_reliability.py`
- Test: `webapp/src/pages/tickets/detail-page.test.tsx`

- [ ] **Step 1: Show requester-safe status**

Requester-facing surfaces must display `requester_status.label`, not raw internal status, while support/admin surfaces still display both.

- [ ] **Step 2: Add "What is needed from you" block**

Show this block when:

- `next_action_owner == "requester"`;
- `requester_status.code == "needs_requester"`;
- `requester_status.code == "review_solution"`.

- [ ] **Step 3: Keep internal notes and technical operations hidden**

Requester surfaces show public messages, public evidence summaries and soft operation labels such as "the specialist is running device diagnostics", not raw internal logs.

- [ ] **Step 4: Run requester and agent tests**

Run:

```powershell
python -m pytest pc_agent/tests/test_ticket_api_client_attachments.py pc_agent/tests/test_support_chat_reliability.py -q --tb=short
pnpm --dir webapp run test -- detail-page
```

Expected: pass.

---

### Task 8: Observer, Reports And Settings Integration

**Files:**
- Modify: `server/observer/service.py`
- Modify: `server/tech/handlers.py`
- Modify: `server/web_api/reports_handlers.py`
- Modify: `server/web_api/settings_handlers.py`
- Modify: `webapp/src/pages/reports/index.tsx`
- Modify: `webapp/src/pages/settings/index.tsx`
- Test: `server/tests/test_observer_v2_api.py`
- Test: `server/tests/test_web_reports_api.py`
- Test: `server/tests/test_web_settings_api.py`

- [ ] **Step 1: Observer summary includes work visibility**

Ticket observer summary should expose:

- active status;
- next action owner;
- open wait count;
- active operation count;
- latest status transition;
- evidence count;
- policy violations if closure was attempted and rejected.

- [ ] **Step 2: Reports include work visibility metrics**

Reports add:

- backlog by internal status;
- backlog by requester status;
- next action owner distribution;
- average wait durations by wait type;
- reopened rate;
- resolution code distribution;
- closure feedback distribution.

- [ ] **Step 3: Settings include catalogs**

Settings allow admin to manage:

- status reason catalog per waiting status;
- resolution codes;
- evidence rules per request kind/category;
- approval requirement rules.

- [ ] **Step 4: Run observer/report/settings tests**

Run:

```powershell
python -m pytest server/tests/test_observer_v2_api.py server/tests/test_web_reports_api.py server/tests/test_web_settings_api.py -q --tb=short
```

Expected: pass.

---

### Task 9: Documentation And CODEMAP Sync

**Files:**
- Modify: `server/docs/TICKET_SYSTEM.md`
- Modify: `server/docs/CODEMAP.md`
- Modify: `server/docs/OBSERVER_LAYER.md`
- Modify: `server/docs/OBSERVER_AUTHORING_RULES.md`
- Modify: `docs/QUICK_LOOKUP.md`
- Modify: `docs/ARCHITECTURE_BOUNDARIES.md`
- Modify: `scripts/navigation_catalog.py`
- Modify: `PLANS.md`

- [ ] **Step 1: Update ticket system doc**

Document:

- internal statuses;
- requester mapping;
- FSM transitions;
- `next_action_owner`;
- `status_reason`;
- wait ledger;
- evidence policy;
- closure/passport flow;
- test and live verification commands.

- [ ] **Step 2: Update observer docs**

Document that ticket-root traces include lifecycle, waits, evidence and operation substate. State that operation status is not a ticket status.

- [ ] **Step 3: Update navigation**

Ensure `task_intake.py` and context search route future ticket-status tasks to:

- `server/tickets/statuses.py`
- `server/tickets/workflow_service.py`
- `server/tickets/wait_service.py`
- `server/tickets/resolution_policy_service.py`
- `server/web_api/support_handlers.py`
- `webapp/src/features/queues/support-workspace.tsx`

- [ ] **Step 4: Run docs checks**

Run:

```powershell
python scripts/docs_inventory.py --check-links
python scripts/verify_workspace.py
```

Expected: both pass.

---

### Task 10: Full Verification, Deploy And Live Testing

**Files:**
- Use: `scripts/run_ci_suite.py`
- Use: `scripts/release_server_to_remote.py`
- Use: `scripts/manage_remote_stack.py`
- Use: `webapp/scripts/remote-browser-signoff.mjs`

- [ ] **Step 1: Run focused server tests**

Run:

```powershell
python -m pytest server/tests/test_ticket_status_catalog.py server/tests/test_ticket_work_visibility_schema.py server/tests/test_ticket_workflow_visibility.py server/tests/test_ticket_resolution_governance.py server/tests/test_ticket_passport_api.py server/tests/test_web_support_api.py server/tests/test_ticket_create_contracts.py server/tests/test_ticket_queue_routing_contracts.py -q --tb=short
```

Expected: pass.

- [ ] **Step 2: Run frontend tests and build**

Run:

```powershell
pnpm --dir webapp run test
pnpm --dir webapp run build
```

Expected: pass.

- [ ] **Step 3: Run workspace verification**

Run:

```powershell
python scripts/verify_workspace.py
```

Expected: pass.

- [ ] **Step 4: Run CI suite before release**

Run:

```powershell
python scripts/run_ci_suite.py
```

Expected: pass or produce a documented failure that is fixed before deploy.

- [ ] **Step 5: Release to remote through project scripts**

Run:

```powershell
python scripts/release_server_to_remote.py
```

Expected: deploy script completes and remote stack is ready for smoke.

- [ ] **Step 6: Remote smoke**

Run:

```powershell
python scripts/manage_remote_stack.py status control
python scripts/manage_remote_stack.py smoke server
```

Expected: control status and server smoke pass.

- [ ] **Step 7: Live browser testing**

Use only:

```text
http://192.168.100.17:8666/admin
```

Browser checks:

- login redirects to `/app/tickets`;
- queue filters show action owner/status groups;
- opening a ticket shows requester, device, queue, SLA/OLA, waits, operations, observer and request form;
- move ticket through `new -> queued -> assigned -> in_progress`;
- move to `waiting_on_user`, send requester reply, verify return to `assigned`;
- move to `waiting_on_vendor` with `status_reason`, verify queue filter;
- run a diagnostic tool and verify operation appears as operation substate, not ticket status;
- attempt resolve without required fields, verify blocked;
- resolve with resolution code, public summary and evidence;
- confirm as requester and verify `closed`;
- reject as requester and verify ticket returns to work;
- open passport and verify lifecycle/evidence/waits are present.

- [ ] **Step 8: Stop remote server after checks**

Run:

```powershell
python scripts/manage_remote_stack.py stop server
```

Expected: server stops unless the user explicitly asks to leave it running.

---

## Rollout Strategy

1. **Compatibility phase:** accept old `triaged` and `waiting_on_vendor`; serialize both old and new labels where needed.
2. **Migration phase:** backfill `triaged` to `queued`/`assigned`, populate `next_action_owner`.
3. **UI phase:** expose new fields in typed support and requester surfaces while keeping legacy endpoints stable.
4. **Governance phase:** enforce resolution/evidence rules after support UI can satisfy them.
5. **Reporting phase:** update dashboards after data starts accumulating.

## Risks And Controls

- Status migration can break old UI assumptions. Control: compatibility aliases and focused tests for legacy `/ticket`, agent GUI and typed React.
- Evidence enforcement can block operators. Control: ship in warn mode first, then enforce per request kind.
- Operation rows may show unrelated device work. Control: ticket-scoped operation query first, device fallback explicitly labeled.
- SLA/OLA pause semantics can regress. Control: wait ledger tests must assert due dates and pause seconds.
- Browser UX can pass API tests but confuse users. Control: required live browser checklist on `http://192.168.100.17:8666/admin`.

## Completion Criteria

- All new statuses are represented in DB, API, support UI, requester UI and agent GUI.
- Every active ticket has a meaningful `next_action_owner`.
- Waiting tickets have a durable open `ticket_waits` row and a visible `status_reason`.
- Requesters see simplified statuses, never raw internal workflow complexity.
- Support sees internal status, requester status, next action, SLA/OLA, waits, operations, evidence and observer context.
- Resolving a governed ticket requires resolution code, summaries and evidence.
- Ticket passport is available through API and support UI.
- Focused tests, frontend tests, `verify_workspace.py`, CI suite and live browser checks pass.
- Docs and CODEMAP are synced.
