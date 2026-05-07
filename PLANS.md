# Support Workspace Final Hardening Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:executing-plans` or the project safe workflow to execute this plan task by task. Keep this file current after each checkpoint.

**Goal:** Close the remaining `/app/tickets` support workspace gaps to 100% readiness: typed/backend gap from 1-2% to 0%, backend/domain gap from 3-5% to 0%, and UI polish gap from 1-3% to 0%.

**Architecture:** Keep `/app/tickets` as the canonical operator workspace. Reuse the existing React/Vite/Tailwind page, typed `/api/web/support/*` boundary, ticket domain services, operation lifecycle APIs, knowledge provider, registry context and passport APIs. Do not replace working business logic; add typed DTO depth, domain adapters and focused UI polish only where the current page still has shallow behavior.

**Tech Stack:** React 19, Vite, TypeScript, Tailwind v4, TanStack Query, lucide-react, aiohttp typed web API, Pydantic DTOs, existing ticket/operation/knowledge/passport services.

---

## Status

Created: 2026-05-07.

Current baseline:

- P0-P5 for `/app/tickets` are implemented and release/browser-signed off.
- Live verification passed for the current page core flows: 3-column layout, topbar, work slices, queue list, selected ticket workspace, timeline tabs, composer, `Ещё` dialogs, right context tabs, SLA/OLA, knowledge, passport and not-found state.
- Dedicated live mutation ticket used in signoff: `T-000518`, id `e72c31d5-2f1c-4812-ac37-cd420b06be05`.
- Last live limitation: safe tool/playbook run was not executed because the test ticket was bound to an offline/unbound device; evidence/worklog mutation depth needs a targeted closure-blocker fixture.

Remaining gaps:

- Typed/backend gap: **1-2%**.
  - Mainly final typed response consistency for operation retry/cancel/details, knowledge provider diagnostics and edge-state errors.
- Domain gap: **3-5%**.
  - Mainly retry semantics, operation retry/cancel policy, online low-risk tool signoff, and external KB/provider depth beyond current source-visible catalog.
- UI polish gap: **1-3%**.
  - Mainly final live fixture coverage, role/permission disabled affordances, long-data polish and screenshot signoff after the final domain slices.

Target completion after this plan: **100% for the current `/app/tickets` page scope**.

## Scope

In scope:

- `/app/tickets` and `/app/tickets/:ticketId`.
- Typed web support API responses used by this page.
- Operation details/retry/cancel controls where existing lifecycle and RBAC allow them.
- External/searchable knowledge depth while preserving AI beta as non-authoritative guidance.
- Closure/passport evidence/worklog live fixture and final UI polish.
- Browser signoff on `http://192.168.100.17:8666/admin`.

Out of scope:

- Replacing ticket workflow/status/SLA/OLA/assignment/routing logic.
- Creating a second workspace under `/app/support`.
- Fake KB, fake evidence, fake operation results or bypassed permissions.
- Broad redesign beyond the accepted SaaS workspace visual structure.

## Functional Improvements We Will Get

1. **Reliable operation actions for operators**
   - Operators will see when an operation can be retried, canceled or only inspected.
   - Retry/cancel buttons will follow backend lifecycle and RBAC instead of being cosmetic.
   - Operation details will expose structured metadata consistently, which makes diagnostics easier to audit.

2. **Deeper knowledge suggestions**
   - Knowledge recommendations will come from a clearer provider contract instead of shallow fallback behavior.
   - Similar tickets/articles will carry source, match reason, provider/version and confidence diagnostics.
   - AI beta remains secondary and source-backed, so it helps triage without pretending to be authoritative.

3. **Better real-world closure flow**
   - Evidence/worklog/passport actions will be checked against a live closure-blocker test ticket.
   - Operators will have a clearer path from blocker to the exact action needed to close the ticket.
   - Passport readiness will become more trustworthy because it is verified against real mutations.

4. **Cleaner permission and edge-state behavior**
   - Disabled controls will explain whether the cause is role, permission, offline device, install requirement, missing consent or lifecycle state.
   - Permission-denied API responses should not crash the page.
   - Not-found, empty, offline, no-deadline and long-data states stay readable.

5. **Final production confidence**
   - The remaining percent is not about making the page "less visual"; it is about proving that rare but important production flows behave correctly.
   - After this plan, the current page can be treated as complete for the agreed scope.

## Implementation Plan

### P6.1 Typed Operation Action Contract

Status: **completed locally, 2026-05-07**.

Implementation notes:

- Existing operation details and cancel APIs were found: `GET /api/operations/{operation_id}` and `POST /api/operations/{operation_id}/cancel`.
- No safe first-class operator retry API exists yet; retry is now represented explicitly as lifecycle metadata with `can_retry=false` and a typed disabled reason instead of a cosmetic button.
- Backend DTOs now expose operation action fields for snapshot/timeline cards: `can_retry`, `can_cancel`, `retry_url`, `cancel_url`, `retry_disabled_reason`, `cancel_disabled_reason`, `policy_labels`.
- Frontend operation cards now consume typed action fields instead of deriving cancel/retry affordances only from local status guesses.
- Focused verification passed:
  - `python -m pytest server/tests/test_web_support_api.py::test_web_support_ticket_detail_includes_observer_summary server/tests/test_web_support_api.py::test_web_support_ticket_detail_timeline_includes_normalized_lifecycle_events -q` -> `2 passed`
  - `pnpm --dir webapp test -- support-workspace-mappers.test.ts list-page.test.tsx` -> `32 passed`

Goal: close the typed/backend gap for operation details, retry and cancel surfaces.

Files to inspect and likely modify:

- `server/web_api/support_handlers.py`
- `server/web_api/dto/support.py`
- `server/operations/` or existing operation lifecycle modules found through CODEMAP/search.
- `webapp/src/features/queues/api.ts`
- `webapp/src/features/queues/support-workspace-mappers.ts`
- `webapp/src/pages/tickets/list-page.tsx`
- Existing focused tests under `server/tests/` and `webapp/src/**`.

Steps:

- [x] Run context search for existing operation detail, retry and cancel APIs.
- [x] Add or tighten typed DTO fields:
  - `operation_id`
  - `status`
  - `can_retry`
  - `can_cancel`
  - `retry_reason`
  - `cancel_reason`
  - `details_url`
  - `policy_labels`
  - `disabled_reason`
- [x] Ensure DTOs are derived from existing operation lifecycle and RBAC rules, not frontend guesses.
- [x] Add focused backend tests for:
  - completed failed operation can expose retry if policy allows;
  - running cancelable operation exposes cancel;
  - completed/succeeded operation is not cancelable;
  - denied permission returns structured denial.
- [x] Update frontend API types and mapper so operation cards consume typed fields.
- [x] Update operation UI actions to show retry/cancel/details only when typed contract allows them.
- [x] Verify with focused pytest and focused Vitest.
- [ ] Verify production build and workspace verification.

Expected result:

- Typed/backend gap reduces from 1-2% to about 0.5-1%.
- Operators get trustworthy retry/cancel/details affordances.

### P6.2 Domain Retry And Online Low-Risk Tool Signoff

Goal: close most of the domain gap around operation retry semantics and safe live tool execution.

Status: **partially completed / blocked for safe retry, 2026-05-07**.

Implementation notes:

- Existing cancel flow is first-class and lifecycle-aware.
- Operator retry cannot be safely implemented by cloning old `device_outbox` payloads: the legacy `/api/operations/*` layer does not carry enough typed risk/policy context to prove that a retry is low-risk.
- Current production-safe behavior is therefore explicit: retryable failed operations expose `retryable=true`, `can_retry=false`, and `retry_disabled_reason=retry_endpoint_unavailable`.
- Remote server was checked before live signoff and is currently stopped: `python scripts\manage_remote_stack.py status server` -> `server: stopped`.
- Live low-risk tool signoff still requires deploying the current branch and selecting/creating an online test device/ticket.

Files to inspect and likely modify:

- Existing operation service/repo modules discovered in P6.1.
- Existing tool/playbook run handlers under `server/web_api/support_handlers.py`.
- Existing operation tests under `server/tests/`.
- `webapp/src/pages/tickets/list-page.tsx`.

Steps:

- [ ] Create or select a dedicated `LIVE-SIGNOFF-ONLINE-*` ticket bound to an online low-risk test device.
- [ ] Identify one safe read-only tool or playbook:
  - risk `safe_read`;
  - no consent required;
  - allowed for support/admin;
  - no destructive side effects.
- [x] Confirm retry is not backed by a safe first-class operator API.
- [x] Avoid adding an unsafe typed web alias until retry can pass risk/policy checks without duplicating lifecycle logic.
- [x] Keep cancel visible only for running/cancelable operations.
- [ ] Run one safe tool/playbook on the dedicated live test ticket.
- [ ] Confirm:
  - operation-running state appears in the right panel;
  - timeline receives start/result events;
  - result card shows structured steps/details;
  - details action opens or fetches operation details;
  - retry/cancel affordances match lifecycle state.
- [ ] Record the live ticket id and operation id in this plan.

Expected result:

- Domain gap reduces from 3-5% to about 1.5-2%.
- Tool/playbook behavior is proven beyond disabled/offline states.

### P6.3 External KB Provider Depth

Goal: close the knowledge part of the domain gap without weakening the current source-visible AI beta design.

Status: **completed locally, 2026-05-07**.

Implementation notes:

- Existing local catalog/manual KB/similar-ticket provider was kept as the source of truth.
- Diagnostics now include `provider_status`, `external_provider_status`, `fallback_reason`, `catalog_entry_count`, and `query_tokens`.
- The UI knowledge tab surfaces provider/catalog/external-KB state compactly beside source and confidence.
- Focused verification passed:
  - `python -m pytest server/tests/test_support_knowledge_provider.py server/tests/test_web_support_api.py::test_web_support_ticket_knowledge_suggestions_returns_sources_and_workspace_payload server/tests/test_web_support_api.py::test_web_support_ticket_knowledge_suggestions_uses_catalog_search_without_manual_links -q` -> `7 passed`
  - `pnpm --dir webapp test -- support-workspace-mappers.test.ts list-page.test.tsx` -> `32 passed`

Files to inspect and likely modify:

- Existing knowledge provider modules under `server/tickets/`, `server/web_api/` or provider paths found through search.
- `server/web_api/support_handlers.py`
- `server/web_api/dto/support.py`
- `server/tests/test_web_support_api.py` or focused knowledge tests.
- `webapp/src/features/queues/support-workspace-mappers.ts`
- `webapp/src/pages/tickets/list-page.tsx`

Steps:

- [x] Inspect current provider contract for catalog search, manual KB links and similar-ticket suggestions.
- [x] Add typed provider diagnostics where missing:
  - provider name;
  - provider version;
  - source counts;
  - query tokens/signals;
  - match reasons;
  - confidence;
  - fallback reason.
- [x] Add a deeper searchable provider path if existing storage/index is available.
- [x] If external KB storage is not configured on the stand, keep the provider contract real but return an explicit `provider_unavailable` diagnostic instead of fake content.
- [x] Add backend tests for:
  - linked KB article suggestions;
  - similar-ticket suggestions;
  - empty provider response;
  - provider-unavailable response;
  - AI beta sources never empty when AI text is present.
- [x] Update UI to show source/provider diagnostics compactly in the knowledge tab.
- [ ] Verify the knowledge tab in dark/light themes with at least one ticket that has suggestions and one that has none.

Expected result:

- Domain gap reduces from about 1.5-2% to about 0.5-1%.
- Knowledge suggestions become auditable and production-safe.

### P6.4 Closure Fixture And Evidence/Worklog Live Proof

Goal: prove the final passport/evidence/worklog closure path with a dedicated test ticket.

Status: **completed locally / live proof pending deploy, 2026-05-07**.

Implementation notes:

- Existing closure guidance already has central blocker actions for evidence and worklog.
- Existing passport/evidence endpoints and legacy worklog endpoint are wired into `/app/tickets`.
- Focused backend verification passed:
  - `python -m pytest server/tests/test_ticket_passport_web_api.py server/tests/test_ticket_evidence_service.py::test_evidence_service_collects_worklog_approval_chat_and_observer_candidates server/tests/test_web_support_api.py::test_web_support_ticket_workspace_exposes_actionable_closure_plan -q` -> `9 passed`
- Focused frontend verification passed:
  - `pnpm --dir webapp test -- list-page.test.tsx` -> `21 passed`
- Dedicated remote live fixture still requires deploy/start of the remote server, because the server is currently stopped.

Files to inspect and likely modify:

- Existing passport/evidence/worklog endpoints in `server/web_api/support_handlers.py`.
- Existing closure/passport services under `server/tickets/`.
- `webapp/src/features/queues/api.ts`
- `webapp/src/pages/tickets/list-page.tsx`
- Focused frontend and backend tests around passport/evidence/worklog.

Steps:

- [ ] Create or identify a dedicated `LIVE-SIGNOFF-CLOSURE-*` ticket with closure blockers.
- [ ] Ensure the ticket has blockers that include evidence and worklog target actions.
- [ ] Click central closure blocker action `Добавить evidence`.
- [ ] Confirm right passport tab focuses the blocker and shows evidence candidates/manual evidence form.
- [ ] Link one safe existing evidence candidate or submit one manual evidence item through the existing API.
- [ ] Confirm blocker/readiness updates after refetch.
- [ ] Click `Добавить worklog`.
- [ ] Submit a small worklog on the test ticket.
- [ ] Confirm passport/evidence flow sees the worklog after refetch.
- [ ] Add or update focused tests if any mapper/UI behavior needed adjustment.

Expected result:

- Domain gap reduces to 0-0.5%.
- Passport readiness becomes live-proven, not only visually verified.

### P6.5 Final UI Polish And Role Matrix

Goal: close the final UI polish gap and record production signoff.

Files to inspect and likely modify:

- `webapp/src/pages/tickets/list-page.tsx`
- `webapp/src/features/queues/support-workspace-mappers.ts`
- shared UI primitives only if a real reusable bug is found.

Steps:

- [ ] Re-run desktop checks at 1366, 1440 and 1920 in dark and light themes.
- [ ] Verify:
  - no horizontal overflow;
  - topbar remains fixed;
  - columns scroll independently;
  - long subjects, long queue names, long requester names and technical IDs do not overlap controls;
  - disabled tool/action reasons are readable;
  - dialogs fit at 1366 width;
  - composer remains reachable after long timeline scroll.
- [ ] Verify role/permission coverage:
  - support L1 normal read/comment/action surface;
  - support without high-risk permission sees high-risk tool disabled/denied;
  - admin shell still routes into support workspace;
  - permission-denied API response renders an error/disabled state, not a crash.
- [ ] Patch only concrete defects found in this pass.
- [ ] Capture final screenshot names in this plan.

Expected result:

- UI polish gap reduces from 1-3% to 0%.
- Final page behavior is production-ready for the agreed desktop support-workspace scope.

## Verification Gates

Local gates:

```powershell
.\scripts\bootstrap_shell_utf8.ps1
python scripts\verify_workspace.py
python scripts\bootstrap_web_toolchain.py
pnpm --dir webapp run build
```

Focused backend gates:

```powershell
python -m pytest server\tests\test_web_support_api.py -q --tb=short
```

Focused frontend gates:

```powershell
pnpm --dir webapp exec vitest run src\features\queues\support-workspace-mappers.test.ts src\pages\tickets\list-page.test.tsx
```

Release and remote gates:

```powershell
python scripts\deploy_workspace_to_remote.py
python scripts\release_server_to_remote.py --skip-ci-check --leave-running --smoke-attempts 6 --smoke-delay 5
python scripts\manage_remote_stack.py --remote altserver@192.168.100.17 smoke server
```

Browser gates:

- Open `http://192.168.100.17:8666/admin`.
- Confirm redirect into `/app/tickets` or `/app/tickets/:ticketId`.
- Check normal ticket, online tool test ticket and closure blocker test ticket.
- Capture dark/light screenshots at 1366 and 1920.
- Confirm console has no unexpected errors. Known acceptable noise must be recorded explicitly.
- Stop remote server after signoff:

```powershell
python scripts\manage_remote_stack.py --remote altserver@192.168.100.17 stop server
python scripts\manage_remote_stack.py --remote altserver@192.168.100.17 status server
```

## Completion Definition

The plan is complete when:

- Typed/backend gap is 0% for the current `/app/tickets` scope.
- Domain gap is 0% for agreed operation retry/external KB/passport evidence-worklog depth.
- UI polish gap is 0% for desktop operator workspace widths 1366-1920.
- Existing business logic and legacy ticket routes are not broken.
- Local tests/build/verification pass.
- Linux stand smoke passes.
- Browser signoff passes on the three critical scenarios:
  - ordinary selected ticket;
  - online low-risk tool/playbook ticket;
  - closure blocker evidence/worklog ticket.
- Remote server is stopped after verification.

## Risks And Decisions

- Retry/cancel must use existing operation lifecycle rules. Do not invent client-side state transitions.
- External KB depth must be honest. If no external provider is configured, expose `provider_unavailable` instead of returning fake articles.
- Tool/playbook live run must use a safe read-only test operation only.
- Evidence/worklog proof must use a dedicated test ticket only.
- Any permission-denied state should be visible and explainable, not hidden behind a silent no-op.

## Handoff

Recommended next step: execute **P6.1 Typed Operation Action Contract**.

Start commands:

```powershell
.\scripts\bootstrap_shell_utf8.ps1
python scripts\task_intake.py
python scripts\bootstrap_web_toolchain.py
rg -n "operation.*retry|retry.*operation|cancel.*operation|operation.*details|tools/run|playbooks/run" server webapp
```

Expected first checkpoint:

- Exact existing operation APIs and services identified.
- Decision recorded whether retry/cancel need only typed DTO surfacing or a new typed web alias.
- Failing focused tests written for allowed/denied retry and cancel states.
