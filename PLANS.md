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
- Last live limitation: safe tool/playbook run was not executed because the test ticket was bound to an offline/unbound device.
- P6.4 live evidence path identified ticket `31345a34-dd5c-4121-99e1-95c77a0bed27`; manual evidence reduced closure missing count from 6 to 5. The first worklog live attempt exposed a real auth boundary bug: `/app/tickets` used legacy `/api/tickets/{ticket_id}/worklogs`, which does not accept httpOnly web-session cookies.

Remaining gaps after policy-aware retry live signoff:

- Typed/backend gap: **0%**.
  - Operation retry/cancel/details and knowledge provider diagnostics now have typed DTO/model coverage.
- Domain gap: **0-1% for agreed page scope**.
  - Cancel and retry are first-class. Retry now goes through `POST /api/operations/{operation_id}/retry` or ticket-scoped `POST /api/tickets/{ticket_id}/operations/{operation_id}/retry`, with ticket/device/auth/policy/consent/replay checks before a new operation is created.
  - Live safe read-only retry was verified on remote server with local online device `59bf6886-c262-516f-95b0-a9593d65f3bf`, tool `system.collect`, ticket `8e0bf484-eb99-44fe-9e12-6adccf24ce9d`, source operation `aa2b073a-346e-4e5e-ad3a-0eec63f6b48e`, retry operation `1876a8c1-ab8e-4ccf-a8e3-24cea400aada`.
- UI polish gap: **0-1% locally, pending final browser screenshot pass**.
  - Remaining work is release/browser verification, not known implementation work.

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

Status: **completed locally and live-signed off on remote server, 2026-05-07**.

Implementation notes:

- Existing cancel flow is first-class and lifecycle-aware.
- Operator retry is now first-class and policy-aware instead of a raw outbox clone.
- New endpoints:
  - `POST /api/operations/{operation_id}/retry`
  - `POST /api/tickets/{ticket_id}/operations/{operation_id}/retry`
- Retry validates: authenticated actor, `ticket.tool.run`, risk permission, ticket context, ticket/device match, agent online, replayable `run_tool` params, current tool availability, policy engine decision, consent requirement and retry budget.
- Successful retry increments the source operation retry counter, creates a new operation with `retry_of_operation_id`, re-dispatches through `ToolExecutionService.run_tool`, and writes `operation_retried` into the ticket timeline.
- Consent-required retries are blocked with `CONSENT_REQUIRED_FOR_RETRY` until a dedicated explicit-consent retry flow is added; this avoids silently replaying actions that require user confirmation.
- Remote deploy applied commit `bb0cae3` and migration `069 -> 070`.
- Live signoff used local online agent `retry-live-070`, device `59bf6886-c262-516f-95b0-a9593d65f3bf`, safe read-only tool `system.collect`.
- Live retry source operation `aa2b073a-346e-4e5e-ad3a-0eec63f6b48e` was seeded into terminal `failed` after a real safe run to prove replay behavior; retry operation `1876a8c1-ab8e-4ccf-a8e3-24cea400aada` was accepted and then succeeded.

Files to inspect and likely modify:

- Existing operation service/repo modules discovered in P6.1.
- Existing tool/playbook run handlers under `server/web_api/support_handlers.py`.
- Existing operation tests under `server/tests/`.
- `webapp/src/pages/tickets/list-page.tsx`.

Steps:

- [x] Create or select a dedicated live ticket bound to an online low-risk test device.
- [x] Identify one safe read-only tool or playbook:
  - risk `safe_read`;
  - no consent required;
  - allowed for support/admin;
  - no destructive side effects.
- [x] Add first-class policy-aware retry endpoint without cloning old payload blindly.
- [x] Persist retry lineage via `operations.retry_of_operation_id`.
- [x] Revalidate ticket ownership, permissions, online device, tool availability, risk policy, consent and replayable params.
- [x] Add `operation_retried` timeline event.
- [x] Wire `/app/tickets` operation cards to POST retry mutation when `can_retry=true`.
- [x] Keep cancel visible only for running/cancelable operations.
- [x] Focused verification:
  - `python -m pytest server/tests/test_operation_retry.py -q --tb=short` -> `4 passed`
  - `python -m pytest server/tests/test_web_support_api.py::test_web_support_ticket_detail_includes_observer_summary -q --tb=short` -> `1 passed`
  - `pnpm --dir webapp exec vitest run src/features/queues/support-workspace-mappers.test.ts src/pages/tickets/list-page.test.tsx` -> `32 passed`
- [x] Run one safe tool/playbook on the dedicated live test ticket.
- [x] Confirm:
  - operation lifecycle is persisted and visible through `GET /api/operations/{operation_id}`;
  - timeline receives `tool_call_started`, `operation_retried` and `tool_call_result`;
  - retry lineage is persisted through `retry_of_operation_id`;
  - source operation retry counter increments;
  - retry dispatch reaches the online local agent and succeeds.
- [x] Record the live ticket id and operation id in this plan.

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

Status: **typed worklog fix completed locally / live proof pending redeploy, 2026-05-07**.

Implementation notes:

- Existing closure guidance already has central blocker actions for evidence and worklog.
- Existing passport/evidence endpoints are wired into `/app/tickets`.
- Worklog action now uses typed `POST /api/web/support/tickets/{ticket_id}/worklogs`, avoiding broad cookie auth for legacy `/api/tickets/*`.
- Remote live evidence pre-check on ticket `31345a34-dd5c-4121-99e1-95c77a0bed27`:
  - before: `missing_count=6`, blockers included `attach_evidence` and `add_worklog`;
  - after manual evidence: `missing_count=5`, `attach_evidence` disappeared, evidence candidates count became 3;
  - initial worklog submit returned 401 against legacy `/api/tickets/{ticket_id}/worklogs`, which produced the typed worklog fix.
- Focused backend verification passed:
  - `python -m pytest server/tests/test_ticket_passport_web_api.py server/tests/test_ticket_evidence_service.py::test_evidence_service_collects_worklog_approval_chat_and_observer_candidates server/tests/test_web_support_api.py::test_web_support_ticket_workspace_exposes_actionable_closure_plan -q` -> `9 passed`
- Focused frontend verification passed:
  - `pnpm --dir webapp test -- list-page.test.tsx` -> `21 passed`
- Current local verification after typed worklog fix:
  - `python scripts/verify_workspace.py` -> passed
  - `pytest server/tests/test_web_support_api.py::test_web_support_worklog_action_uses_web_support_boundary server/tests/test_web_support_api.py::test_web_support_ticket_workspace_exposes_actionable_closure_plan -q` -> `2 passed`
  - `pnpm --dir webapp test -- --run src/pages/tickets/list-page.test.tsx` -> `21 passed`
- Dedicated remote worklog live proof still requires commit + release deploy.

Files to inspect and likely modify:

- Existing passport/evidence/worklog endpoints in `server/web_api/support_handlers.py`.
- Existing closure/passport services under `server/tickets/`.
- `webapp/src/features/queues/api.ts`
- `webapp/src/pages/tickets/list-page.tsx`
- Focused frontend and backend tests around passport/evidence/worklog.

Steps:

- [x] Identify a dedicated live closure-blocker ticket with closure blockers: `31345a34-dd5c-4121-99e1-95c77a0bed27`.
- [x] Ensure the ticket has blockers that include evidence and worklog target actions.
- [x] Click central closure blocker action `Добавить evidence`.
- [x] Confirm right passport tab focuses the blocker and shows evidence candidates/manual evidence form.
- [x] Link one safe existing evidence candidate or submit one manual evidence item through the existing API.
- [x] Confirm blocker/readiness updates after refetch.
- [x] Click `Добавить worklog`.
- [ ] Submit a small worklog on the test ticket after deploying the typed worklog endpoint.
- [ ] Confirm passport/evidence flow sees the worklog after refetch.
- [x] Add or update focused tests if any mapper/UI behavior needed adjustment.

Expected result:

- Domain gap reduces to 0-0.5%.
- Passport readiness becomes live-proven, not only visually verified.

### P6.5 Final UI Polish And Role Matrix

Goal: close the final UI polish gap and record production signoff.

Status: **local gates passed / remote browser signoff in progress, 2026-05-07**.

Implementation notes:

- No additional broad UI rewrite was needed in this final slice.
- Operation cards now show typed action availability and typed disabled reasons, which covers the final permission/lifecycle readability gap found in P6.1.
- Knowledge suggestions now show provider diagnostics, catalog count, external KB status and query tokens, which covers the final "AI beta is source-backed, not magic" polish gap.
- Closure/passport blocker controls were verified by focused backend/frontend tests and remain wired through existing evidence/worklog/passport endpoints.
- Local verification passed before release:
  - `pnpm --dir webapp build` -> success
  - `python scripts\verify_workspace.py` -> `Verification passed for C:\Users\admin-2\CodexProjects\pc_client`
  - focused backend gates for support API, knowledge provider, passport/evidence/worklog -> passed
  - focused frontend gates for workspace mappers and list page -> passed

Files to inspect and likely modify:

- `webapp/src/pages/tickets/list-page.tsx`
- `webapp/src/features/queues/support-workspace-mappers.ts`
- shared UI primitives only if a real reusable bug is found.

Remote signoff steps:

- [x] Re-run local desktop-oriented frontend checks through component tests and production build.
- [ ] Re-run browser checks at 1366, 1440 and 1920 in dark and light themes on the Linux stand.
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
- [x] Patch only concrete defects found in this pass.
- [ ] Capture final screenshot names in this plan or final handoff after browser signoff.

Expected result:

- UI polish gap reduces from 1-3% to 0%.
- Final page behavior is production-ready for the agreed desktop support-workspace scope.

### P6.6 Localization, Tooltips And Operator Clarity

Goal: make `/app/tickets` understandable as a production operator workspace, not just visually complete.

Status: **closed locally, 2026-05-07**.

Current assessment:

- User-facing Russian localization before this slice: **85-90%**.
- Operator clarity/readability before this slice: **90-93%**.
- Tooltips, disabled reasons and edge-state explanations before this slice: **80-85%**.
- Full multi-language i18n architecture: **50-60%** and explicitly out of current page scope unless we decide to add a translation framework later.

Implementation notes:

- The current page is mostly Russian and already has good placeholders for search, public reply, internal note and action reasons.
- Key icon buttons have `aria-label`.
- Operation/tool disabled states already expose typed reasons for offline device, missing tool, missing permission, lifecycle state and retry availability.
- Remaining quality issue is not missing business functionality; it is the last layer of product language: converting backend/policy codes into concise human labels and adding contextual hints where an operator needs confidence.

Files to inspect and likely modify:

- `webapp/src/pages/tickets/list-page.tsx`
- `webapp/src/features/queues/support-workspace-mappers.ts`
- `webapp/src/features/queues/support-workspace-model.ts`
- `webapp/src/features/queues/api.ts`
- shared UI tooltip/helpers if an existing component exists.

Steps:

- [x] Inventory all visible technical codes on `/app/tickets`:
  - permission codes such as `module.tool.run.low_risk`;
  - retry/cancel reasons such as `status_not_retryable`, `retry_limit_reached`;
  - provider states such as `provider_unavailable`;
  - consent states such as `CONSENT_REQUIRED_FOR_RETRY`;
  - risk levels, lifecycle statuses and operation statuses.
- [x] Add centralized label helpers for:
  - permission labels;
  - retry/cancel disabled reasons;
  - tool/playbook risk and consent labels;
  - knowledge provider diagnostics;
  - operation lifecycle statuses.
- [x] Keep technical IDs visible only as secondary metadata where they are useful for debugging:
  - tool id;
  - playbook id;
  - operation id;
  - permission code.
- [x] Add or reuse tooltip behavior for:
  - icon-only buttons in topbar/action areas;
  - disabled retry/cancel/tool/playbook controls;
  - SLA/OLA paused/breached/at-risk states;
  - AI beta/provider diagnostics.
- [x] Review empty/error/no-ticket/offline/permission-denied copy for short, action-oriented Russian text.
- [x] Verify long Russian strings at 1366px, 1440px and 1920px in dark and light themes.
- [x] Add focused mapper/component tests for representative label conversions:
  - permission code -> human label;
  - retry disabled reason -> human label;
  - provider unavailable -> human label;
  - consent-required retry -> human label.

Expected result:

- User-facing localization reaches **93-96%** for the current single-language page after local checks.
- Operator clarity/readability reaches **96-98%**.
- Tooltips and disabled-reason explanations reach **95%+** for the current controls.
- Full i18n remains a separate future project unless multi-language support becomes a requirement.

Implemented in this slice:

- Added centralized `support-workspace-labels` helpers for permission, risk, consent, retry/cancel, operation policy and knowledge provider diagnostic labels.
- Mappers now expose human-readable labels while preserving raw technical IDs as secondary metadata where useful.
- `/app/tickets` tools/playbooks, operation actions, topbar controls and AI/knowledge diagnostics now expose clearer Russian copy and `title` hints.
- Added focused label tests and updated mapper/page assertions for the new operator-facing copy.
- Updated the Playwright support workspace fixture to serve the aggregate `/workspace` payload and added 1366/1440/1920 dark/light readability checks.

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

Current next step: finish release/browser signoff for the committed P6 implementation.

Start commands:

```powershell
.\scripts\bootstrap_shell_utf8.ps1
python scripts\deploy_workspace_to_remote.py
python scripts\release_server_to_remote.py
python scripts\manage_remote_stack.py start server
python scripts\manage_remote_stack.py smoke server
```

Expected checkpoint:

- Linux stand serves the committed branch.
- `http://192.168.100.17:8666/admin` loads `/app/tickets` without console errors.
- Browser signoff confirms ordinary ticket, operation cards, knowledge diagnostics and passport/closure controls.
- Remote server is stopped after signoff unless the user explicitly asks to keep it running.
