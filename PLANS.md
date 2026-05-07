# Observer Layer Trace Clarity Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `pc-client-observer-diagnostics` first, then use `superpowers:executing-plans` or the project safe workflow to execute this plan task by task. Keep this file current after each checkpoint.

**Goal:** Make the existing observer layer clearer and more actionable for `/app/tickets`, operations, retries, passport/evidence flows and admin diagnostics without turning observer into a business source of truth.

**Architecture:** Keep observer as a technical overlay over committed source rows: `operations`, `ticket_events`, `device_events`, `agent_runtime_audit`, `agent_observer_events`, playbook run/steps and agent action traces. Strengthen trace continuity through ticket-root traces and linked child operation/playbook traces, expose compact typed summaries to `/app/tickets`, and keep deep investigation in `/app/admin/observer`.

**Tech Stack:** aiohttp web API, SQLAlchemy async repos, Pydantic DTOs, `server/observer/service.py`, `server/observer/runtime.py`, React 19, Vite, TypeScript, Tailwind v4, TanStack Query, existing `/api/web/support/*` and `/api/web/admin/observer/*` contracts.

---

## Status

Created: 2026-05-07.

Current active plan: **P9 Support Workspace Data Hygiene And Final Polish**.

Current progress:

- P8.1 Contract audit and trace-continuity baseline: **completed locally**.
- P8.2 Backend typed observer summary depth: **completed locally**.
- P8.3 Support action trace continuity cleanup: **completed locally**.
- P8.4 Operation/retry/playbook trace relation UI: **completed locally**.
- P8.5 `/app/tickets` Observer diagnostic card: **completed locally**.
- P8.6 Admin Observer deep-link refinement: **completed locally**.
- P8.7 Observer documentation and CODEMAP sync: **completed locally**.
- P8.8 Local verification, browser signoff, commit and optional deploy: **completed with noted CI-suite agent_ws hang**.
- P8.9 CI-suite agent_ws hang follow-up: **new residual reliability task**.
- P9.1 Hide internal/test queue and smart-view navigation noise in `/app/tickets`: **completed locally**.

P9 target after completion:

- Typed/backend gap: **0-1%**.
- Backend/domain gap: **1-3%**.
- UI/page polish gap: **1-2%**.

P9 scope:

- Keep ticket access and search behavior unchanged.
- Hide clearly internal navigation artifacts such as `Stage ...`, `Stage27 ...`, `Codex OLA ...` and `Live L1 ...` from workspace queue/smart-view navigation.
- Preserve legitimate custom smart views and production queues.
- Verify summary, queue payloads, and workspace regression tests.

P9 functional benefit:

- `/app/tickets` left column becomes operator-focused instead of mixing production work queues with test/stage fixtures.
- Search can still find accessible tickets from internal queues when needed, so this is UI data hygiene rather than permission or routing logic.
- Future support-browser signoff should be easier because noisy one-off queues no longer dominate the sidebar.

P9.1 local verification:

- `python -m pytest server\tests\test_web_support_api.py -k "workspace_summary or internal_navigation_noise or published_custom_smart_view or queue_returns_typed_scope" -q --tb=short` -> `4 passed, 49 deselected`.
- `python scripts\verify_workspace.py` -> passed.

Latest local verification:

- `python -m pytest server\tests\test_web_support_api.py::test_web_support_ticket_detail_includes_observer_summary server\tests\test_web_support_api.py::test_web_support_lifecycle_event_uses_existing_ticket_root_trace server\tests\test_web_support_api.py::test_web_support_worklog_action_uses_web_support_boundary server\tests\test_web_support_api.py::test_web_support_status_action_returns_typed_result_and_updates_ticket server\tests\test_web_support_api.py::test_web_support_ticket_mutation_aliases_update_ticket_through_typed_boundary -q --tb=short` -> `5 passed`.
- `python -m pytest server\tests\test_operation_retry.py -q --tb=short` -> `4 passed`.
- `python -m pytest server\tests\test_observer_diagnostics_api.py -k "ticket" -q --tb=short` -> `2 passed, 2 deselected`.
- `pnpm --dir webapp exec vitest run src\features\queues\support-workspace-mappers.test.ts src\pages\tickets\list-page.test.tsx --run` -> `34 passed`.
- `pnpm --dir webapp run build` -> passed.
- `python scripts\verify_workspace.py` -> passed after updating observer docs and `scripts/navigation_catalog.py`.
- `python scripts\build_context_index.py --force` -> passed.
- `python -m pytest server\tests\test_web_support_api.py::test_web_support_ticket_detail_includes_observer_summary server\tests\test_web_support_api.py::test_web_support_ticket_detail_marks_retry_operation_trace_relation -q --tb=short` -> `2 passed`.
- `pnpm --dir webapp exec vitest run src\features\queues\support-workspace-mappers.test.ts src\pages\tickets\list-page.test.tsx --run` -> `34 passed` after P8.4.
- `pnpm --dir webapp run build` -> passed after P8.4.
- `python scripts\verify_workspace.py` -> passed after P8.4.
- `pnpm --dir webapp exec vitest run src\features\queues\support-workspace-mappers.test.ts src\pages\tickets\list-page.test.tsx --run` -> `36 passed` after P8.5.
- `pnpm --dir webapp run build` -> passed after P8.5.
- `python scripts\build_context_index.py --force` -> passed after P8.5.
- `python scripts\verify_workspace.py` -> passed after P8.5.
- `pnpm --dir webapp exec vitest run src\features\queues\support-workspace-mappers.test.ts src\pages\tickets\list-page.test.tsx src\features\tech\observer-workbench-api.test.ts src\features\tech\observer-quick-panel.test.tsx --run` -> `42 passed` after P8.6.
- `pnpm --dir webapp run build` -> passed after P8.6.
- `python scripts\build_context_index.py --force` -> passed after P8.7.
- `python scripts\verify_workspace.py` -> passed after P8.7.
- `python scripts\bootstrap_web_toolchain.py` -> passed after P8.8 local signoff.
- `python -m pytest server\tests\test_web_support_api.py -k "observer or trace or retry or worklog or status" -q --tb=short` -> `10 passed, 42 deselected` after P8.8.
- `python -m pytest server\tests\test_observer_diagnostics_api.py -q --tb=short` -> `4 passed` after P8.8.
- `python -m pytest server\tests\test_operation_retry.py -q --tb=short` -> `4 passed` after P8.8.
- `pnpm --dir webapp exec vitest run src\features\queues\support-workspace-mappers.test.ts src\pages\tickets\list-page.test.tsx src\features\tech\observer-workbench-api.test.ts src\features\tech\observer-quick-panel.test.tsx --run` -> `42 passed` after P8.8.
- `pnpm --dir webapp run build` -> passed after P8.8.
- `python scripts\build_context_index.py --force` -> passed after P8.8.
- `python scripts\verify_workspace.py` -> passed after P8.8.
- `git commit -m "server: clarify support observer traces"` -> `3e2bc2a`.
- `python scripts\run_ci_suite.py` -> partial: `verify_workspace`, webapp bundle, server no-db and DB/API slices passed; DB/API reported `500 passed, 176 deselected`; agent_ws slice hung after `test_tool_dispatch_failure.py::test_dispatch_failure_materializes_failed_operation_and_trace PASSED [72%]` and was stopped manually. No green `summary.json` was produced for `3e2bc2a`.
- `python scripts\deploy_workspace_to_remote.py --skip-ci-check` -> deployed `3e2bc2a` to `/var/chat_bot/pc_client`.
- `python scripts\release_server_to_remote.py --skip-ci-check --leave-running --smoke-attempts 6 --smoke-delay 5` -> release completed; smoke passed on attempt 2 with `/api/health -> 200`.
- Browser signoff on `http://192.168.100.17:8666/admin` -> `/app/tickets` checked at `1366x900` and `1920x1080`, no horizontal overflow, no newly captured console errors, Observer card/SLA/passport visible, dark theme toggle works.
- Browser signoff for `/app/admin/observer?trace_id=506a6fbc-ab76-4bed-8a41-1a90f7679d29` -> Observer page opened with the requested trace id in URL/context, no horizontal overflow, no newly captured console errors.

Implemented in P8.1-P8.3:

- `server/web_api/support_handlers.py` no longer passes ad-hoc random trace ids for support lifecycle events such as passport evidence, worklog, chat, queue, priority, reroute and approval decisions.
- Operation-bound tool consent trace remains a deliberate child execution trace.
- `server/tests/test_web_support_api.py` now protects ticket-root continuity for an existing root trace.
- `server/tests/test_operation_retry.py` now uses an explicit queued-ticket fixture and asserts `operation_retried` resolves to the retry operation trace.

Implemented in P8.2:

- `ObserverOverlayService.get_ticket_observer_summary()` now returns compact support-facing observer data: root trace URL/status/kind, `health_label`, latest error label/stage/time, top signature, compact related/active/error traces and compact recent occurrences.
- `server/web_api/dto/support.py` exposes strict typed DTOs for compact observer traces, signatures and occurrences.
- `GET /api/web/support/tickets/{ticket_id}` embeds the compact observer payload for `/app/tickets`.
- `webapp/src/features/queues/api.ts` knows the extended observer contract.
- Observer docs, CODEMAP, QUICK_LOOKUP and navigation catalog are synced.

Implemented in P8.4:

- `SupportTicketOperationSnapshot` now exposes operation trace relation fields for `/app/tickets`: `trace_relation`, `root_trace_id`, `root_trace_url`, `trace_url`, `retry_of_operation_id` and `retry_source_trace_id`.
- `server/web_api/support_handlers.py` derives whether an operation trace is the ticket root, a child operation trace, a retry child trace, a playbook child trace or unknown.
- Retry operation snapshots prefetch the source operation trace so the UI can show retry lineage without opening raw JSON.
- `/app/tickets` operation cards now label trace links as `Root trace тикета`, `Трасса операции`, `Повтор операции` or `Трасса playbook`, and show a separate root trace link where useful.
- Backend and frontend tests cover the new relation metadata and visible links.

Implemented in P8.5:

- `webapp/src/features/queues/support-workspace-model.ts` now has a typed `SupportWorkspaceObserverDiagnostic` model for support-facing observer summaries.
- `mapWorkspaceObserver()` converts the compact backend observer payload into operator-readable labels, tones, root trace metadata, latest error, top signature, compact trace rows and recent occurrences.
- `/app/tickets` context sidebar now renders `ObserverDiagnosticCard` with health, counters, root trace link, quiet empty state, latest error/top signature and trace deep links.
- Mapper and page tests cover the observer diagnostic card and compact mapping.

Implemented in P8.6:

- `/app/admin/observer?trace_id=...` now opens the traces tab, selects that trace, clears local filters that could hide it and requests the typed traces endpoint with `trace_id`.
- `fetchObserverWorkbenchTraces()` accepts `traceId`, `ticketId` and `operationId` so support/admin deep links can narrow the server-side trace selection.
- Selecting a trace inside the observer workbench keeps `trace_id` in the URL; selecting from trace links clears stale `ticket_id`/`operation_id` query params.
- Focused tests cover URL serialization and the `trace_id` deep-link render path.

Implemented in P8.7:

- `docs/QUICK_LOOKUP.md` documents P8.1/P8.2, P8.4, P8.5 and P8.6 support/admin observer behavior.
- `server/docs/OBSERVER_LAYER.md` documents compact support observer payloads, operation/retry trace relation metadata and `/app/admin/observer?trace_id=...` deep links.
- `server/docs/OBSERVER_AUTHORING_RULES.md` documents support lifecycle trace continuity and repo-resolved passport evidence events.
- `server/docs/CODEMAP.md` and `scripts/navigation_catalog.py` point future workers to the updated typed support/admin observer surfaces.

Previous `/app/tickets` hardening baseline:

- P0-P7 support workspace slices are implemented, committed and deployed during the previous stage.
- `/app/tickets` has the accepted three-column SaaS operator workspace, dark/light theme, typed action controls, SLA/OLA, tools/playbooks, knowledge diagnostics, passport evidence/worklog and guarded resolution close flow.
- Last deployed support-workspace commits include:
  - `30b749c webapp: add guarded support resolution close flow`
  - `e9528ca webapp: improve passport focus light theme`
- The Linux stand was released and browser-signed off for the previous page scope, then the remote server was stopped.

Observer baseline from analysis:

- Observer layer already exists and is not a stub.
- Ticket-root anchor exists: `tickets.observer_root_trace_id`.
- Projection/storage exists:
  - `observer_traces`
  - `observer_spans`
  - `observer_span_links`
  - `observer_error_occurrences`
  - `observer_error_signatures`
- Main backend implementation:
  - `server/observer/service.py`
  - `server/observer/runtime.py`
  - `server/app/repos/ticket_events_repo.py`
  - `server/app/repos/agent_observer_events_repo.py`
- Support detail aggregate already embeds observer summary through `ObserverOverlayService.get_ticket_observer_summary(ticket_id)`.
- `/app/tickets` already renders an Observer block, but it is still too technical and shallow for an operator:
  - trace count;
  - active trace count;
  - error trace count;
  - signature count;
  - root trace id;
  - summary endpoint.
- Operation cards already expose `trace_id`, details URL and lifecycle action metadata.
- Retry endpoint already writes `operation_retried` and preserves retry lineage through `retry_of_operation_id`.

Current observer readiness estimate:

- Backend observer coverage: **85-90%**.
- Trace continuity and causality clarity: **75-85%**.
- `/app/tickets` operator usefulness: **55-65%**.
- Admin diagnostics depth: **80-88%**.
- Documentation alignment for the latest support-workspace observer usage: **70-80%**.

Target after this plan:

- Backend observer coverage for ticket/workspace/operation flows: **95-98%**.
- Trace continuity and causality clarity: **95%+**.
- `/app/tickets` operator usefulness: **90-95%**.
- Admin diagnostics depth for ticket-bound flows: **90-95%**.
- Documentation alignment: **100% for modified observer surfaces**.

## Scope

In scope:

- Ticket-root trace continuity for support workspace actions.
- Typed support observer payload depth.
- `/app/tickets` observer UI readability and diagnostic value.
- Operation, retry and playbook trace links.
- Passport/evidence/worklog observer provenance visibility.
- Admin observer trace detail affordances when reached from a support ticket.
- Focused backend/frontend tests.
- Documentation updates required by project canon:
  - `server/docs/OBSERVER_LAYER.md`
  - `server/docs/OBSERVER_AUTHORING_RULES.md`
  - `server/docs/CODEMAP.md`
  - `docs/QUICK_LOOKUP.md`
  - `scripts/navigation_catalog.py` if route/navigation surfaces change.

Out of scope:

- Replacing helpdesk business state with observer state.
- Changing SLA/OLA, assignment, queue routing or ticket closure policies.
- Creating fake diagnostic events or fake KB/AI explanations.
- Full observability platform redesign.
- Long-term storage/retention overhaul unless an existing bug is found.
- New external tracing vendor integration.

## Decisions

- Observer remains an overlay. Ticket workflow and closure policy remain the source of truth.
- `/app/tickets` should show operator-readable observer conclusions, not raw trace dumps.
- `/app/admin/observer` remains the deep diagnostics workspace.
- Ticket-bound support actions should use the ticket-root trace unless there is a deliberate child execution trace, in which case it must be linked to the ticket root.
- Random ad-hoc `uuid.uuid4()` trace ids in support action handlers should be removed or made explicit through `TicketEventsRepo.resolve_ticket_trace_id`.
- Operation/playbook traces can remain child traces, but the UI and backend detail must make the causal relation visible.
- Error signatures shown in `/app/tickets` must be source-backed and scoped clearly: global count versus ticket-local count.

## Functional Improvements We Will Get

1. **Clearer operator diagnosis in the ticket**
   - The operator sees the latest failed stage, top signature and whether the problem is active, recurring or already terminal.
   - The Observer block becomes a compact diagnostic card instead of a raw counter panel.

2. **Trace continuity across support actions**
   - Status changes, queue changes, worklog, evidence, resolution submit, retry and tool results will be easier to follow inside one ticket-root story.
   - Random-looking trace fragmentation will be removed from support action code.

3. **Better operation and retry investigation**
   - A failed operation card will show whether the trace is the ticket root, an operation child trace or a linked retry trace.
   - Retry lineage will be visible to both the timeline and observer detail.

4. **More useful signatures**
   - `/app/tickets` can show the most relevant ticket-local signature without sending the operator into the admin workbench first.
   - Admin can still open full trace detail for spans, links and occurrences.

5. **Better handoff between support and tech/admin**
   - Support can copy/open a concrete trace URL.
   - Admin observer workbench receives enough context to land on the right trace instead of requiring manual search.

6. **Cleaner docs and future authoring rules**
   - New dangerous/support-visible flows get clear instrumentation rules.
   - Future module/tool/playbook authors know when to continue ticket-root trace and when to create linked child traces.

## File Map

Backend observer core:

- `server/observer/service.py`
  - Extend compact ticket observer summary and trace relation metadata.
  - Add helper serialization for ticket-local top signatures and recent failed trace summaries.
- `server/observer/runtime.py`
  - Verify no change is required for hot refresh; update only if new projection source needs runtime refresh.
- `server/app/repos/ticket_events_repo.py`
  - Reuse `ensure_ticket_observer_root_trace_id` and `resolve_ticket_trace_id`.
  - Add tests if trace continuity behavior needs stronger guarantees.
- `server/web_api/support_handlers.py`
  - Replace unclear support-action `trace_id=str(uuid.uuid4())` usage with explicit ticket-root trace resolution.
  - Extend aggregate support detail observer payload.
- `server/web_api/dto/support.py`
  - Add typed DTO fields for compact observer diagnostics.
- `server/web_api/admin_handlers.py`
  - Modify only if admin trace links need an additional typed URL or filter parameter.

Frontend support workspace:

- `webapp/src/features/queues/api.ts`
  - Extend typed observer summary contract.
- `webapp/src/features/queues/support-workspace-mappers.ts`
  - Map observer backend payload into operator-readable labels.
- `webapp/src/features/queues/support-workspace-model.ts`
  - Add view-model types only if the current model cannot hold the new observer card data cleanly.
- `webapp/src/features/queues/support-workspace.tsx`
  - Redesign the Observer block into a compact diagnostic card.
- `webapp/src/pages/tickets/list-page.tsx`
  - Wire trace links, selected ticket observer state, error/empty states and menu actions.
- `webapp/src/styles.css` or existing support workspace CSS file if needed
  - Add only scoped classes/tokens needed for the observer card.

Tests:

- `server/tests/test_web_support_api.py`
  - Support detail observer aggregate contract.
  - Support action trace continuity.
- `server/tests/test_observer_diagnostics_api.py`
  - Ticket-local signature counts, related trace summaries and root trace detail.
- `server/tests/test_operation_retry.py`
  - Retry lineage event trace relation if not already covered deeply enough.
- `webapp/src/features/queues/support-workspace-mappers.test.ts`
  - Observer payload mapping.
- `webapp/src/pages/tickets/list-page.test.tsx`
  - Observer card rendering, trace links, empty/error states.

Docs:

- `server/docs/OBSERVER_LAYER.md`
- `server/docs/OBSERVER_AUTHORING_RULES.md`
- `server/docs/CODEMAP.md`
- `docs/QUICK_LOOKUP.md`
- `docs/CONTEXT_INDEX.md` only if indexing/navigation rules change.
- `scripts/navigation_catalog.py` only if route/catalog entries change.

## Implementation Plan

### P8.1 Contract Audit And Trace Continuity Test Baseline

Goal: prove the current behavior before changing it and lock the intended trace-continuity contract in focused tests.

Status: **completed locally, 2026-05-07**.

Steps:

- [x] Re-run context intake for this exact implementation slice.

```powershell
.\scripts\bootstrap_shell_utf8.ps1
python scripts\task_intake.py --task "Observer trace clarity for support workspace ticket-root actions and operation retry links"
```

Expected:

- Task mode points to server/webapp or internal web platform.
- Plan remains required.
- Observer docs and support handlers appear in relevant files.

- [x] Search current support action event writes.

```powershell
rg -n "trace_id=str\(uuid\.uuid4\(\)\)|trace_id=uuid\.uuid4\(\)|add_event\(" server\web_api\support_handlers.py -S
```

Expected:

- All support action event writes are identified.
- Any deliberately operation-bound event is separated from generic support lifecycle events.

- [x] Add a backend test proving support-originated ticket lifecycle actions land on the ticket root trace.

Target file:

- `server/tests/test_web_support_api.py`

Behavior to cover:

- Create or load a support ticket with `observer_root_trace_id`.
- Perform one server-originated support lifecycle mutation through a web support endpoint, for example queue/status/priority/worklog depending on available fixture helpers.
- Assert the inserted `TicketEvent.trace_id` equals the ticket root trace id for non-operation lifecycle events.

Expected test command:

```powershell
python -m pytest server\tests\test_web_support_api.py -k "observer or trace" -q --tb=short
```

Expected first result before implementation:

- The new test may fail if a path does not resolve to ticket-root trace clearly.
- Existing observer tests remain green.

- [x] Add or update a retry observer relation test.

Target file:

- `server/tests/test_operation_retry.py`

Behavior to cover:

- Original failed operation has a trace id.
- Retry creates a new operation with `retry_of_operation_id`.
- `operation_retried` event has `operation_id` of the retry operation.
- Event trace relation is deterministic:
  - operation-bound event resolves to the retry operation trace;
  - ticket lifecycle event remains on ticket-root trace.

Expected command:

```powershell
python -m pytest server\tests\test_operation_retry.py -q --tb=short
```

Completion criteria:

- We know exactly which support action paths need code changes.
- Trace-continuity behavior is protected by failing or passing tests.

### P8.2 Backend Typed Observer Summary Depth

Goal: expose a compact, source-backed observer summary that is useful to `/app/tickets` without requiring full trace detail fetches.

Status: **completed locally, 2026-05-07**.

Backend contract additions:

- `summary.root_trace_url`
- `summary.root_trace_status`
- `summary.root_kind`
- `summary.latest_error_at`
- `summary.latest_error_label`
- `summary.latest_error_stage`
- `summary.top_signature`
- `summary.has_active_operation`
- `summary.health_label`
- `related_traces_compact`
- `active_traces_compact`
- `error_traces_compact`
- `recent_occurrences_compact`

Suggested DTO shape:

```python
class SupportTicketObserverSignature(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error_signature: str
    title: str | None = None
    severity: str | None = None
    ticket_occurrences_count: int = 0
    global_occurrences_count: int | None = None
    last_seen_at: str | None = None


class SupportTicketObserverTraceCompact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trace_id: str
    root_kind: str | None = None
    status: str | None = None
    title: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    error_count: int = 0
    operation_id: str | None = None
    tool_name: str | None = None
    playbook_id: str | None = None
    trace_url: str | None = None


class SupportTicketObserverOccurrenceCompact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error_signature: str | None = None
    message: str | None = None
    stage: str | None = None
    severity: str | None = None
    trace_id: str | None = None
    created_at: str | None = None
    trace_url: str | None = None
```

Files:

- Modify: `server/web_api/dto/support.py`
- Modify: `server/observer/service.py`
- Modify: `server/web_api/support_handlers.py`
- Test: `server/tests/test_web_support_api.py`
- Test: `server/tests/test_observer_diagnostics_api.py`

Steps:

- [x] Extend `ObserverOverlayService.get_ticket_observer_summary()` return dict with compact fields derived from already-loaded `root_trace`, `related_traces`, `signatures` and `recent_occurrences`.
- [x] Keep the existing `summary` fields unchanged for backward compatibility.
- [x] Add DTOs with `extra="forbid"` to prevent untyped drift.
- [x] Serialize admin trace URLs as webapp URLs, for example:

```text
/app/admin/observer?trace_id=<trace_id>
```

- [x] Define `health_label` on the backend as a conservative derived label:
  - `running` when active traces exist;
  - `error` when error traces or signatures exist;
  - `ok` when traces exist and no active/error traces exist;
  - `empty` when no trace exists.
- [x] Add backend tests for this slice:
  - typed support detail includes the richer observer summary fields;
  - compact trace URLs are present when a root trace exists;
  - existing ticket-local signature count coverage remains in `test_observer_diagnostics_api.py`.

Expected commands:

```powershell
python -m pytest server\tests\test_web_support_api.py::test_web_support_ticket_detail_includes_observer_summary -q --tb=short
python -m pytest server\tests\test_observer_diagnostics_api.py -k "ticket" -q --tb=short
```

Completion criteria:

- `/api/web/support/tickets/{ticket_id}` returns richer typed observer data.
- Existing frontend remains compatible while new fields are available.

### P8.3 Support Action Trace Continuity Cleanup

Goal: remove unclear random trace assignment from support action handlers and make ticket-root continuity explicit.

Status: **completed locally, 2026-05-07**.

Files:

- Modify: `server/web_api/support_handlers.py`
- Modify only if needed: `server/app/repos/ticket_events_repo.py`
- Test: `server/tests/test_web_support_api.py`

Steps:

- [x] Evaluate whether a local helper is needed in `support_handlers.py`; it was not needed because omitting `trace_id` lets `TicketEventsRepo.add_event()` resolve ticket-root trace at every cleaned lifecycle callsite.

```python
async def _ticket_root_trace_id(repo: TicketEventsRepo, ticket_id: str) -> str:
    return await repo.ensure_ticket_observer_root_trace_id(ticket_id)
```

- [x] Replace generic lifecycle event writes that currently pass `trace_id=str(uuid.uuid4())` with one of:
  - omit `trace_id` and let `TicketEventsRepo.add_event()` resolve the ticket root;
  - pass the explicit value from `ensure_ticket_observer_root_trace_id()` when readability is better.
- [x] Keep operation-bound events using `operation_id` so `TicketEventsRepo.resolve_ticket_trace_id()` can resolve to operation trace.
- [x] Do not change event payloads except adding explicit observer provenance when useful.
- [x] Add focused tests for the first cleanup slice:
  - status changed;
  - queue changed;
  - priority changed;
  - worklog added with existing ticket-root trace;
  - operation retried remains operation-bound.

Expected command:

```powershell
python -m pytest server\tests\test_web_support_api.py -k "trace or observer or worklog or status" -q --tb=short
```

Completion criteria:

- No generic support lifecycle action creates a misleading unrelated trace id.
- Operation-bound events still resolve through operation trace ids.

### P8.4 Operation, Retry And Playbook Trace Relations

Goal: make relation between ticket root, operation trace, retry trace and playbook trace visible in backend payloads and UI.

Status: **completed locally, 2026-05-07**.

Files:

- Modify: `server/observer/service.py`
- Modify: `server/web_api/support_handlers.py`
- Modify: `server/web_api/dto/support.py`
- Modify: `webapp/src/features/queues/api.ts`
- Modify: `webapp/src/features/queues/support-workspace-mappers.ts`
- Modify: `webapp/src/pages/tickets/list-page.tsx`
- Test: `server/tests/test_operation_retry.py`
- Test: `webapp/src/features/queues/support-workspace-mappers.test.ts`
- Test: `webapp/src/pages/tickets/list-page.test.tsx`

Steps:

- [x] Add compact operation trace relation fields where operation snapshots/timeline cards are built:
  - `trace_relation`: `ticket_root | operation_child | retry_child | playbook_child | unknown`
  - `root_trace_id`
  - `root_trace_url`
  - `trace_url`
  - `retry_of_operation_id`
  - `retry_source_trace_id`
- [x] Prefer deriving relation server-side where source data is available.
- [x] Keep frontend fallback conservative if old payload lacks new fields.
- [x] In operation card metadata, replace short raw `Trace: abc123` only display with:
  - `Трасса операции`;
  - `Root trace тикета`;
  - `Повтор операции`;
  - `Трасса playbook`.
- [x] Add mapper tests for relation labels and retry lineage mapping.
- [x] Add UI tests that operation cards show observer trace links and root trace links when available.

Expected commands:

```powershell
python -m pytest server\tests\test_operation_retry.py -q --tb=short
pnpm --dir webapp exec vitest run src\features\queues\support-workspace-mappers.test.ts src\pages\tickets\list-page.test.tsx -t "observer" --run
```

Completion criteria:

- Operator can distinguish ticket root trace from operation child trace.
- Retry lineage is visible without opening raw JSON.

Verification:

- `python -m pytest server\tests\test_web_support_api.py::test_web_support_ticket_detail_includes_observer_summary server\tests\test_web_support_api.py::test_web_support_ticket_detail_marks_retry_operation_trace_relation -q --tb=short` -> `2 passed`.
- `pnpm --dir webapp exec vitest run src\features\queues\support-workspace-mappers.test.ts src\pages\tickets\list-page.test.tsx --run` -> `34 passed`.
- `pnpm --dir webapp run build` -> passed.
- `python scripts\verify_workspace.py` -> passed.

### P8.5 `/app/tickets` Observer Diagnostic Card

Goal: redesign the existing Observer block into a compact support-facing diagnostic card.

Status: **completed locally, 2026-05-07**.

Files:

- Modify: `webapp/src/features/queues/api.ts`
- Modify: `webapp/src/features/queues/support-workspace-mappers.ts`
- Modify: `webapp/src/features/queues/support-workspace.tsx`
- Modify: `webapp/src/pages/tickets/list-page.tsx`
- Modify scoped CSS only if needed.
- Test: `webapp/src/features/queues/support-workspace-mappers.test.ts`
- Test: `webapp/src/pages/tickets/list-page.test.tsx`

Card content:

- Health strip:
  - `Норма`
  - `Есть активные операции`
  - `Есть ошибки`
  - `Нет трасс`
- Key facts:
  - root trace compact id;
  - total traces;
  - active traces;
  - error traces;
  - signatures.
- Latest problem:
  - latest error label;
  - stage;
  - time;
  - top signature with ticket-local count.
- Actions:
  - `Открыть трассу`
  - `Открыть observer`
  - `Скопировать trace id` if an existing copy pattern exists; otherwise use a plain selectable code value.

UX rules:

- The card must be useful to L1 support without requiring knowledge of tracing internals.
- Keep raw ids secondary.
- Do not show scary red state when there is no error, even if traces exist.
- If no trace exists, show a quiet empty state: `Трасса ещё не создана. Она появится после первого события или операции по тикету.`
- If observer endpoint fails, show compact error state and keep the rest of the ticket usable.

Steps:

- [x] Extend frontend types for new observer fields.
- [x] Add mapper helpers:
  - `observerHealthLabel()`
  - `observerHealthTone()`
  - `observerStatusLabel()`
  - `mapObserverTrace()`
  - `mapWorkspaceObserver()`
- [x] Replace current raw Observer block with the new diagnostic card in `/app/tickets`.
- [x] Add trace action links using server-provided URLs.
- [x] Add focused mapper/page tests for:
  - compact observer mapping;
  - error/signature observer;
  - root trace link;
  - trace-row deep link;
  - quiet no-trace state through the default fixture path.

Expected commands:

```powershell
pnpm --dir webapp exec vitest run src\features\queues\support-workspace-mappers.test.ts src\pages\tickets\list-page.test.tsx --run
pnpm --dir webapp run build
```

Completion criteria:

- `/app/tickets` no longer exposes only raw observer counters.
- Operator has a clear next diagnostic action from the ticket page.

Verification:

- `pnpm --dir webapp exec vitest run src\features\queues\support-workspace-mappers.test.ts src\pages\tickets\list-page.test.tsx --run` -> `36 passed`.
- `pnpm --dir webapp run build` -> passed.

### P8.6 Admin Observer Deep-Link Refinement

Goal: make the transition from support ticket to admin observer workbench precise.

Status: **completed locally, 2026-05-07**.

Files:

- Inspect first: `webapp/src/features/tech/*`
- Inspect first: `webapp/src/pages/admin/*` or current admin observer route files found by `rg`.
- Modify only if current admin observer does not already honor `trace_id`, `ticket_id`, `root_kind` query params.
- Test existing admin observer frontend tests if present.

Steps:

- [x] Verify `/app/admin/observer?trace_id=<trace_id>` opens the trace detail or filters directly to the trace.
- [x] Verify `/app/admin/observer?ticket_id=<ticket_id>` filters related traces for that ticket.
- [x] If unsupported, add query-param initialization to the admin observer page:
  - `trace_id` opens detail;
  - `ticket_id` sets ticket filter;
  - `root_kind` sets root kind filter.
- [x] Add a focused test for query-param handling.
- [x] Keep support-workspace links aligned with actual admin behavior.

Expected browser check:

```text
http://192.168.100.17:8666/admin/app/admin/observer?trace_id=<trace_id>
```

or the actual app route used by the deployed admin shell.

Completion criteria:

- The support operator/admin handoff link lands on the intended trace context.

Verification:

- `pnpm --dir webapp exec vitest run src\features\tech\observer-workbench-api.test.ts src\features\tech\observer-quick-panel.test.tsx --run` -> `6 passed`.
- `pnpm --dir webapp exec vitest run src\features\queues\support-workspace-mappers.test.ts src\pages\tickets\list-page.test.tsx src\features\tech\observer-workbench-api.test.ts src\features\tech\observer-quick-panel.test.tsx --run` -> `42 passed`.
- `pnpm --dir webapp run build` -> passed.

### P8.7 Observer Documentation And CODEMAP Sync

Goal: keep project documentation aligned with trace-visible behavior.

Status: **completed locally, 2026-05-07**.

Files:

- Modify: `server/docs/OBSERVER_LAYER.md`
- Modify: `server/docs/OBSERVER_AUTHORING_RULES.md`
- Modify: `server/docs/CODEMAP.md`
- Modify: `docs/QUICK_LOOKUP.md`
- Modify only if needed: `scripts/navigation_catalog.py`
- Modify only if needed: `docs/CONTEXT_INDEX.md`

Steps:

- [x] Update `OBSERVER_LAYER.md` with:
  - support-workspace observer summary fields;
  - ticket-root versus operation-child trace rule;
  - retry lineage visibility;
  - `/app/tickets` compact observer card.
- [x] Update `OBSERVER_AUTHORING_RULES.md` with:
  - support action trace continuity rule;
  - no random trace ids for ticket lifecycle events;
  - when to use span links for child operation/playbook traces.
- [x] Update `server/docs/CODEMAP.md` with changed DTO/routes/services.
- [x] Update `docs/QUICK_LOOKUP.md` so future workers know observer support workspace entrypoints.
- [x] Run context index rebuild if docs/navigation changed:

```powershell
python scripts\build_context_index.py --force
```

Completion criteria:

- Observer docs describe the implemented behavior, not the old shallow summary.
- Future agents can find the trace path from support page to observer backend.

Verification:

- `python scripts\build_context_index.py --force` -> passed.
- `python scripts\verify_workspace.py` -> passed.

### P8.8 Local Verification, Browser Signoff, Commit And Optional Deploy

Goal: prove the observer changes are safe and production-ready.

Status: **completed, 2026-05-07, with CI-suite agent_ws hang tracked as P8.9**.

Local gates:

```powershell
.\scripts\bootstrap_shell_utf8.ps1
python scripts\verify_workspace.py
python scripts\bootstrap_web_toolchain.py
pnpm --dir webapp run build
```

Focused backend gates:

```powershell
python -m pytest server\tests\test_web_support_api.py -k "observer or trace or retry or worklog or status" -q --tb=short
python -m pytest server\tests\test_observer_diagnostics_api.py -q --tb=short
python -m pytest server\tests\test_operation_retry.py -q --tb=short
```

Focused frontend gates:

```powershell
pnpm --dir webapp exec vitest run src\features\queues\support-workspace-mappers.test.ts src\pages\tickets\list-page.test.tsx --run
```

Browser signoff:

- Deploy only after local gates pass.
- Use canonical server URL:

```text
http://192.168.100.17:8666/admin
```

- Check `/app/tickets` at:
  - 1366px dark;
  - 1366px light;
  - 1920px dark;
  - 1920px light.
- Verify:
  - observer card fits without horizontal overflow;
  - no overlap with SLA/OLA/tools/passport sections;
  - long signature text wraps cleanly;
  - trace links are visible and do not look like primary destructive actions;
  - no console errors;
  - center timeline remains scrollable;
  - right sidebar remains scrollable;
  - admin observer deep-link opens the expected trace/filter.

Commit:

```powershell
git status --short
git add server webapp docs scripts PLANS.md
git commit -m "feat: clarify support observer traces"
```

Remote release:

```powershell
python scripts\deploy_workspace_to_remote.py
python scripts\release_server_to_remote.py --skip-ci-check --leave-running --smoke-attempts 6 --smoke-delay 5
python scripts\manage_remote_stack.py --remote altserver@192.168.100.17 smoke server
```

Post-signoff cleanup:

```powershell
python scripts\manage_remote_stack.py --remote altserver@192.168.100.17 stop server
python scripts\manage_remote_stack.py --remote altserver@192.168.100.17 status server
```

Completion criteria:

- All local tests/build checks pass. **Completed locally 2026-05-07.**
- Browser signoff passes. **Completed on remote stand 2026-05-07.**
- Commit exists. **Completed: `3e2bc2a server: clarify support observer traces`.**
- Remote deploy is optional unless requested for this slice; if deployed, smoke/browser signoff passes and server is stopped unless user asks to keep it running. **Deploy/smoke/browser completed; stop server after final status capture.**

CI-suite note:

- The canonical CI artifact gate was attempted before deploy.
- The no-db and DB/API slices passed, including `500 passed, 176 deselected` for DB/API.
- The `agent_ws` slice hung without output after 72%; deploy used the explicit project-supported `--skip-ci-check` bypass.
- This is not a blocker for the observer UI/browser signoff, but it must be investigated before treating full release-control CI as healthy.

### P8.9 CI-Suite Agent_WS Hang Follow-Up

Goal: restore reliable green CI artifacts for release-control deploys.

Status: **completed, 2026-05-08**.

Known symptom:

- `python scripts\run_ci_suite.py` starts `python -m pytest server/tests -m "not manual and agent_ws"`.
- The slice reached `test_tool_dispatch_failure.py::test_dispatch_failure_materializes_failed_operation_and_trace PASSED [72%]`.
- No new log output was written after that point; the next collected test is `test_tool_started_event.py::test_tool_call_started_created_before_command`.
- `run_ci_suite.py` passed `idle_timeout_seconds=None` to all pytest steps, so the documented/CLI idle timeout was ignored for `server_pytest_agent_ws`.
- The first observed "hang" happened after the Codex shell command hit its own 20 minute timeout; the CI child processes kept running and no green artifact could be written.

Focused findings:

- `python -m pytest server\tests\test_tool_started_event.py::test_tool_call_started_created_before_command -vv --tb=short` -> `1 passed`.
- `python -m pytest server\tests\test_tool_dispatch_failure.py::test_dispatch_failure_materializes_failed_operation_and_trace server\tests\test_tool_started_event.py::test_tool_call_started_created_before_command -vv --tb=short --durations=10` -> `2 passed`.
- `python -m pytest server/tests -m "not manual and agent_ws" -vv --tb=short --durations=30` -> `29 passed, 647 deselected`.
- `python -m pytest scripts\test_run_ci_suite.py -q --tb=short` -> `8 passed`.
- `python -m pytest server/tests -m "not manual and agent_ws" -q --tb=short --durations=20` -> `29 passed, 647 deselected`.

Implemented fix:

- `scripts/run_ci_suite.py` now applies `args.idle_timeout` to all pytest steps, not just `verify_workspace` and `build_webapp_bundle`.
- `scripts/test_run_ci_suite.py` now asserts the pytest layers receive the default idle timeout.
- `docs/QUICK_LOOKUP.md` and `docs/TESTING_RULES.md` now document that pytest CI layers use the configured idle timeout.

Full CI verification:

- `python scripts\run_ci_suite.py` for `337ad6d2aff6072ce1804677f250a61ee3c54a1b` -> green.
- `server_pytest_agent_ws` in the full suite: `29 passed, 647 deselected`, duration `389.127s`, idle timeout enabled at `600s`.
- `server_pytest_db_api`: `500 passed, 176 deselected`, duration `2492.434s`.
- `pc_agent_pytest`: `190 passed, 4 deselected`.

Historical reproduction commands:

```powershell
python -m pytest server\tests\test_tool_started_event.py -q --tb=short
python -m pytest server\tests\test_tool_started_event.py::test_tool_call_started_created_before_command -vv --tb=short
python scripts\run_ci_suite.py --idle-timeout 600
```

Completion criteria:

- The suspected hanging test is either fixed or ruled out. **Completed: ruled out by focused and full `agent_ws` runs.**
- `run_ci_suite.py` produces `artifacts\ci\<commit>\summary.json` without manual intervention. **Completed for `337ad6d`.**
- Release deploy can run without `--skip-ci-check`. **Completed for commits with green artifact; rerun full CI after any new commit before release.**

## Acceptance Criteria

The observer layer plan is complete when:

- `/app/tickets` shows a clear Observer diagnostic card, not only raw counters.
- Ticket-root trace id is stable and support lifecycle events use it consistently.
- Operation, retry and playbook traces are visibly related to the ticket root.
- Top signature and latest error are available in typed support detail payload.
- Observer empty/error states are handled without breaking the ticket workspace.
- Admin observer deep-links from the ticket land on the intended trace context.
- Backend tests cover trace continuity and compact observer payload.
- Frontend tests cover observer mapping and rendering.
- Observer docs and CODEMAP are updated with the new trace rules.
- Existing ticket business logic, operation retry/cancel, passport, SLA/OLA and knowledge behavior remain intact.

## Risks

- Over-instrumentation can make observer look like the source of business truth. Mitigation: keep business decisions in ticket services and closure/workflow policy.
- Too much trace detail in `/app/tickets` can overload L1 operators. Mitigation: show compact diagnosis and link to admin workbench for deep details.
- Changing trace id behavior can affect existing observer tests. Mitigation: add tests before replacing random trace ids.
- Operation-bound events must not be forced onto ticket root if they need operation trace detail. Mitigation: keep `operation_id` on operation events and rely on repo resolution.
- Admin observer route behavior may already support query params. Mitigation: inspect before modifying.

## Handoff

Recommended next action: for the next release/deploy, run `python scripts\run_ci_suite.py` on the final commit, then deploy without `--skip-ci-check`.

Next commands:

```powershell
python scripts\run_ci_suite.py
python scripts\deploy_workspace_to_remote.py
python scripts\release_server_to_remote.py --leave-running --smoke-attempts 6 --smoke-delay 5
```

Expected first checkpoint:

- Green CI artifact exists for the final commit.
- Deploy/release scripts pass without `--skip-ci-check`.
- Remote smoke and browser checks are run for UI-facing changes.
