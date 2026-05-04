# Service Desk Live Acceptance Test Plan

> For agentic workers: use `superpowers:executing-plans` for each stage and keep this file current after every verified checkpoint. This is the active long-horizon plan for live testing the full configurable service desk model in `pc_client`.

## Status

Created: 2026-05-03.

Last updated: 2026-05-04, Stage 33A backend slice deployed and live-checked on `#T-000512` and `#T-000513`: structured evidence contract, ticket-scoped passport operations, evidence candidates/link API and closure evidence verification are active on the Linux stand.

Current plan completion: 99.3%; passport/evidence remains an open product-quality track before final acceptance.

Current execution mode: Stage 33A backend implementation. Stage 32C is deployed and re-checked: playbooks with missing tools/params are blocked before enqueue, ticket playbook failures are visible, operations are ticket-scoped in support UI, internal SLA/OLA pause/resume noise is hidden from requester chat, and taking work auto-assigns support actor where allowed. Current backend work deliberately excludes visual redesign and focuses on making passport/evidence usable, traceable and closure-grade.

This plan replaces the first live acceptance outline with a smaller-stage, wider-coverage campaign. The implementation and hardening work before this plan is treated as complete. This plan is only for live acceptance testing, evidence gathering, defect isolation, focused fixes, re-checks and final confidence scoring across the whole ticket system.

## Goal

Verify in live conditions that the full configurable service desk model works end to end on real tickets and real settings: request templates, dynamic forms, workflow, priority, SLA, OLA, routing, approvals, diagnostics, notifications, visibility, smart views, closure rules, passport/reporting, agent GUI create flow, observer traces and RBAC.

## Acceptance Strategy

- Live evidence is the primary acceptance source.
- Autotests are used for baseline readiness, regression isolation after a found bug, and verification of code fixes.
- A stage is not marked complete until its evidence is recorded and any limits are explicitly listed.
- If a test requires user attention or cannot be made reliable through automation, it must be recorded in `User Attention Checks` with exact steps and expected result.
- The observer layer is part of the acceptance surface. Missing trace roots, missing operation spans, missing agent action correlation, or silent dangerous-flow gaps are defects.
- If observer behavior itself is defective, modify observer code or docs as needed, then verify the same live scenario again.
- Every defect fix follows: capture live evidence, add or update focused regression test where realistic, fix smallest ownership zone, run focused tests, redeploy if needed, repeat the live scenario.

## Progress Accounting

Progress is tracked by weighted stage points. Update `Current plan completion` after every verified stage.

- Total: 100 points.
- Stages 0-7: readiness and fixture setup, 18 points.
- Stages 8-22: live process behavior, 48 points.
- Stages 23-29: cross-cutting acceptance, 20 points.
- Stages 30-33: final browser signoff, cleanup and scoring, 14 points.

A stage can be:

- `[ ]` not started
- `[~]` in progress or partially blocked
- `[x]` complete with evidence
- `[!]` failed, defect captured and not yet rechecked
- `[U]` requires user attention before final confidence

## Source Of Truth And Constraints

- Work only in `C:\Users\admin-2\CodexProjects\pc_client`.
- Do not edit `\\192.168.100.17\NTFS_Share\pc_client` directly.
- Use remote Linux copy `/var/chat_bot/pc_client` only as deploy/live stand.
- Use project scripts for deploy and lifecycle.
- Browser checks use only `http://192.168.100.17:8666/admin` and linked `/app/*` routes.
- For webapp commands, first run `python scripts/bootstrap_web_toolchain.py`.
- Do not expose raw tokens or secrets in logs, screenshots or artifacts.
- Prefix disposable live entities with `codex-live-acceptance-20260503`.
- Every created ticket/template/policy/smart view must be listed in the final evidence summary for cleanup.
- Generated artifacts stay under ignored `artifacts/*` folders and are not committed.
- Remote server is stopped at the end unless the user explicitly asks to leave it running.

## Canonical Documents

Read or refresh these before changing code or executing a related stage:

- `AGENTS.md`
- `docs/CODEX_WORKFLOW.md`
- `docs/ARCHITECTURE_BOUNDARIES.md`
- `docs/CONTEXT_INDEX.md`
- `docs/QUICK_LOOKUP.md`
- `docs/LOCAL_WORKFLOW.md`
- `server/docs/CODEMAP.md`
- `pc_agent/docs/CODEMAP.md`
- `server/docs/TICKET_SYSTEM.md`
- `server/docs/OBSERVER_LAYER.md`
- `server/docs/OBSERVER_AUTHORING_RULES.md`
- `pc_agent/docs/AGENT_RUNTIME_ALWAYS_ON.md`

## Scope

### Remote Live Stand

- `http://192.168.100.17:8666/admin`
- `/app/admin/forms`
- `/app/settings`
- `/app/tickets`
- `/app/tickets/:ticketId`
- `/app/admin/observer`
- `/app/admin/access`
- `/app/admin/inventory`
- `/app/admin/playbooks`
- `/app/ticket` and `/app/ticket/:ticketId` when requester behavior is involved
- `/help` only if the legacy requester path remains involved in the live flow

### Server Domains

- `server/tickets/*`
- `server/web_api/settings_handlers.py`
- `server/web_api/support_handlers.py`
- `server/web_api/admin_handlers.py`
- `server/web_api/access_handlers.py`
- `server/observer/*`
- `server/tools/*`
- `server/playbooks/*`
- `server/app/repos/*`
- `server/websocket/*`

### Agent Domains

- `pc_agent/ui_gui/*`
- `pc_agent/ui_bridge/*`
- `pc_agent/ws_agent.py`
- `pc_agent/ws_agent_runtime_helpers.py`
- `pc_agent/core/orchestrator.py`
- `pc_agent/core/action_trace.py`
- `pc_agent/ui_gui/server_api.py`

### Webapp Domains

- `webapp/src/pages/settings/index.tsx`
- `webapp/src/pages/tickets/list-page.tsx`
- `webapp/src/pages/tickets/detail-page.tsx`
- `webapp/src/pages/admin/*`
- `webapp/src/features/forms-builder/*`
- `webapp/src/features/playbooks/*`
- `webapp/src/features/access-control/*`
- relevant typed API clients under `webapp/src/features/*`

### Scripts And Artifacts

- `scripts/task_intake.py`
- `scripts/build_context_pack.py`
- `scripts/search_context_index.py`
- `scripts/verify_workspace.py`
- `scripts/docs_inventory.py`
- `scripts/bootstrap_web_toolchain.py`
- `scripts/release_server_to_remote.py`
- `scripts/manage_remote_stack.py`
- `scripts/manage_local_agent.py`
- `scripts/run_observer_canary_suite.py`
- `scripts/helpdesk_data_cleanup.py`
- `artifacts/live_checks/`
- `artifacts/browser_checks/live-acceptance/`
- `artifacts/observer_canaries/live-acceptance/`
- `artifacts/diagnostics/`

## Test Data Model

Use these scenario ids and names:

- `codex-live-acceptance-incident-website`
  - Ticket type: `incident`
  - Request template: `Live: Не открывается сайт`
  - Diagnostics: website/DNS style playbook, consent required
  - Expected policy chain: form, workflow, priority, routing, SLA, OLA, diagnostics, closure, visibility, notification

- `codex-live-acceptance-access`
  - Ticket type: `access_request`
  - Request template: `Live: Нужен доступ к системе`
  - Approval required
  - Diagnostics disabled
  - Expected policy chain: form, workflow, priority, routing, SLA, approval, closure, visibility, notification

- `codex-live-acceptance-consultation`
  - Ticket type: `consultation`
  - Request template: `Live: Консультация по рабочему месту`
  - Simple workflow
  - Requester reply path required
  - Expected policy chain: form, workflow, routing, SLA, closure, visibility

- `codex-live-acceptance-change`
  - Ticket type: `change_request`
  - Request template: `Live: Изменение конфигурации`
  - Approval and scheduled state required
  - Expected policy chain: form, workflow, priority, routing, SLA/OLA, approval, closure, reporting

Minimum live ticket set:

- `T-LIVE-01`: incident website, normal path with diagnostics and successful closure.
- `T-LIVE-02`: incident website, high impact/urgency path with P0/P1 SLA/OLA risk.
- `T-LIVE-03`: access request, approve path.
- `T-LIVE-04`: access request, reject path with required rejection comment.
- `T-LIVE-05`: consultation, requester reply and `waiting_user` pause/resume path.
- `T-LIVE-06`: change request, scheduled and `waiting_approval` path.
- `T-LIVE-07`: negative create/transition/RBAC ticket.
- `T-LIVE-08`: agent GUI-created ticket using current published template.
- `T-LIVE-09`: diagnostic failure or consent-denied ticket.
- `T-LIVE-10`: requester-safe visibility/passport export ticket.

## Evidence Artifacts

Write generated evidence only into ignored artifact folders:

- `artifacts/live_checks/service_desk_live_acceptance_YYYYMMDD.json`
- `artifacts/live_checks/service_desk_live_acceptance_YYYYMMDD.md`
- `artifacts/browser_checks/live-acceptance/`
- `artifacts/observer_canaries/live-acceptance/`
- `artifacts/diagnostics/live_acceptance_logs_YYYYMMDD.txt`

Evidence summary must include:

- branch and commit hash
- local git status before and after
- deploy command and result
- remote health result
- created template/policy/smart-view ids and versions
- created ticket ids and access codes where safe
- scenario id per ticket
- expected vs actual policy chain
- SLA/OLA timer facts
- workflow transition facts
- approval facts
- diagnostic operation ids and trace ids
- observer root ids, span counts and agent action correlation
- closure/passport facts
- browser paths checked
- console errors count
- agent instance name, ui port and log safety result
- defects found, severity and reproduction command
- user-attention checks still open
- cleanup status

## User Attention Checks

This section must be updated during execution. Do not mark final completion until each item is either completed by the user or explicitly accepted as residual risk.

- [U] Agent GUI visual flow: Stage 29 exercised the live GUI-owned automation surface for profile selection, form-pack refresh, create, attachment, add-message and post-create state; user live QA on `3.1.28` confirmed consent hint, confirmation emphasis, assignment/SLA/diagnostics visibility and system event localization needed follow-up. Agent `3.1.29` is live on `AD-MAIN`; needs user visual confirmation.
- [x] Tray/minimize behavior: Stage 29 verified runtime behavior and user live QA confirmed tray works.
- [ ] External notification channels: user may need to confirm real email/Telegram/VK Teams delivery if providers are unavailable or disabled on the stand.
- [ ] Long calendar boundary behavior: user may need to accept simulated clock/API evidence instead of waiting real business hours.
- [U] Real requester-device consent prompt: Stage 23 verified server-side support consent gating and deny path live, but user live QA on `T-000509` saw `diagnostic autorun skipped` and no consent prompt. Root cause was a ticket created with `diagnostic_consent.granted=false`; agent `3.1.28` blocked silent submit and `3.1.29` adds an explicit required-action hint. Needs a new ticket from updated agent to verify the corrected live path.
- [x] Ticket requester messages: user live QA confirms messages are visible.
- [ ] External notifications: user explicitly deferred notification checks for now; do not block the current bugfix gate on provider delivery.

## Current Bugfix Gate

Opened: 2026-05-04 after user live QA.

Do these before final cleanup, scoring, or any broad visual redesign:

1. `BUG-508-REQUESTER-CLOSE`: `#T-000508` / requester confirmation UX.
   - Symptom: requester sees resolved ticket and support instruction, but the close/confirm action is visually unclear; screenshot shows `Подтвердить` looking disabled while `Отклонить` is visible.
   - Expected: resolved requester view has an obvious primary action, e.g. `Подтвердить и закрыть обращение`, with enabled styling and clear disabled/loading states.
   - Scope: requester browser path (`/help` legacy and `/app/ticket` React path if both are reachable) plus agent GUI resolved-ticket prompt if the same visual pattern applies.
   - 2026-05-04 fix/deploy: legacy `/help` and React requester page render `confirmation_request` as primary `Подтвердить и закрыть` plus `Отклонить решение` and submit structured `confirmation_response`; agent GUI resolved prompt now uses clearer labels/min widths. Remote live browser re-check passed for `#T-000508`; I did not click the button to avoid closing the user's real ticket.

2. `BUG-509-DIAGNOSTIC-CONSENT`: `#T-000509` / diagnostic consent auto-run.
   - Symptom: incident with user consent produces `diagnostic autorun skipped`; repeated run does not produce consent prompt.
   - Expected: if policy requires requester/device consent, the requester sees a clear consent request and support sees `waiting_consent`; if the policy intentionally blocks auto-run, UI must explain the exact reason and provide the correct next action.
   - Scope: `server/tickets/diagnostic_policy.py`, support playbook launch/consent routes, requester/agent consent prompt path, observer trace for skipped vs waiting consent.
   - 2026-05-04 evidence/fix: `#T-000509` stored `diagnostic_consent.granted=false`, so the server correctly emitted `diagnostic_autorun_skipped(reason=consent_required)` before operation creation. Agent create dialog/wizard now blocks silent submit when a template requires requester-device diagnostic consent but the checkbox is not checked; compiled agent `3.1.28` was built, `--verify` passed, uploaded as `windows_amd64/stable/3.1.28` and assigned in rollout policy. New-ticket live re-check remains pending because the current Windows agent was offline for immediate WS update.

3. `BUG-AGENT-CHAT-ORDER`: agent GUI ticket chat order.
   - Symptom: support chat messages are displayed in reverse chronological order.
   - Expected: oldest messages above, newest below, scroll sticks to latest only when user is near the bottom; history prepend must not invert current messages.
   - Scope: `pc_agent/ui_gui/chat_panel.py` timeline merge/render helpers and focused GUI helper tests.
   - 2026-05-04 local fix: support detail API no longer reverses the already chronological event page; React support detail now treats the last timeline item as the latest event. Agent GUI timeline code was inspected and keeps append chronological; live GUI re-check still pending.

4. `BUG-AGENT-GUI-LAYOUT`: agent GUI layout overflow.
   - Symptom: fields and controls shift/overflow in the user agent GUI.
   - Expected: request wizard, chat/detail pane and action rows remain readable at common Windows window sizes; long Russian labels wrap without covering adjacent controls.
   - Scope: `pc_agent/ui_gui/chat_panel.py`, theme/QSS helpers, any small widget layout helpers; avoid broad visual redesign in this bugfix gate.
   - 2026-05-04 local fix: resolved confirmation row wraps prompt text and gives action buttons stable minimum widths; diagnostic consent label is clearer. Follow-up `3.1.29` makes the confirmation card more prominent and the diagnostic consent hint explicit. Broader GUI overflow remains a user-attention visual check after rollout.

5. `BUG-SUPPORT-WORKSPACE-DISCOVERY`: support workspace lacks intuitive process visibility.
   - Symptom: many panels exist, but the operator cannot easily see where the active process state, SLA, OLA, playbooks, consent, evidence and closure action live.
   - Expected for current bugfix gate: do not redesign yet; only document the element inventory and preserve it for the future redesign plan.
   - Scope: plan/design inventory only until the explicit redesign stage begins.

6. `BUG-AGENT-CONSENT-HINT`: consent checkbox exists but is not clearly marked as required.
   - Symptom: in agent create flow the checkbox is present, but the user has no clear visual instruction that it must be checked.
   - Expected: required diagnostic consent is labelled as mandatory, has a visible hint, blocks submit until checked, and the error text says exactly what to do.
   - 2026-05-04 local fix: `3.1.29` adds explicit mandatory wording and a highlighted hint in both create dialog and wizard.

7. `BUG-AGENT-ASSIGNMENT-SLA-DIAGNOSTICS`: agent detail does not explain work owner, deadlines or diagnostics.
   - Symptom: `#T-000511` was closed correctly, but agent detail showed no useful diagnostic block, SLA/deadline status was unclear, and executor looked missing.
   - Evidence: DB shows `#T-000511` has no personal `assignee_id`, status was moved to `in_progress` by support actor `op1`; SLA started/stopped successfully; diagnostics were skipped with `reason=priority_not_allowed` because the network diagnostic policy auto-runs only for `P0/P1/P2`, while the ticket was `P3`.
   - Expected: agent detail shows "not personally assigned, in work by support/op1" when applicable, deadline status with stopped/no-breach facts, and a visible diagnostic summary explaining why no diagnostic result exists.
   - 2026-05-04 local fix: `3.1.29` adds assignment fallback, deadline status summary and diagnostics summary from ticket events/custom fields.

8. `BUG-AGENT-EVENT-LOCALIZATION`: agent chat system events are raw/non-Russian.
   - Symptom: chat shows raw labels such as `status changed` and generic notifications that do not explain what changed.
   - Expected: system events are Russian, state the actual transition or diagnostic reason, and avoid raw event names for normal users.
   - 2026-05-04 local fix: `3.1.29` localizes status, queue, SLA stop/start, OLA stop and diagnostic skipped events.

9. `BUG-AGENT-CONFIRMATION-EMPHASIS`: resolution confirmation exists but is visually weak.
   - Symptom: user sees the confirmation controls, but the block is not visually obvious and the primary action can look disabled.
   - Expected: confirmation is a highlighted card with a clear heading and large primary/secondary actions.
   - 2026-05-04 local fix: `3.1.29` styles the confirmation block as an emphasized card and increases action button size/contrast.

## Live Fixture Manifest

Locked on 2026-05-03 after Stage 6 collision check.

Entity prefix: `codex-live-acceptance-20260503`.

Form/template/policy code prefix: `codex_live_acceptance_20260503`. The web form-pack validator requires latin `snake_case` keys, so live form schemas and request templates use this underscore prefix even though the human artifact prefix remains hyphenated.

Ticket types:

- `codex-live-acceptance-20260503-incident`
- `codex-live-acceptance-20260503-access`
- `codex-live-acceptance-20260503-consultation`
- `codex-live-acceptance-20260503-change`

Form schemas:

- `codex_live_acceptance_20260503_incident_schema`
- `codex_live_acceptance_20260503_access_schema`
- `codex_live_acceptance_20260503_consultation_schema`
- `codex_live_acceptance_20260503_change_schema`

Request templates:

- `codex_live_acceptance_20260503_incident_website` -> `Live: Не открывается сайт`
- `codex_live_acceptance_20260503_access` -> `Live: Нужен доступ к системе`
- `codex_live_acceptance_20260503_consultation` -> `Live: Консультация по рабочему месту`
- `codex_live_acceptance_20260503_change` -> `Live: Изменение конфигурации`

Policy codes:

- workflow: `codex_live_acceptance_20260503_workflow_incident`, `codex_live_acceptance_20260503_workflow_approval`, `codex_live_acceptance_20260503_workflow_simple`, `codex_live_acceptance_20260503_workflow_change`
- priority: `codex_live_acceptance_20260503_priority`
- routing: `codex_live_acceptance_20260503_routing`
- SLA: `codex_live_acceptance_20260503_sla`
- OLA: `codex_live_acceptance_20260503_ola`
- approval: `codex_live_acceptance_20260503_approval_access`, `codex_live_acceptance_20260503_approval_change`
- diagnostic: `codex_live_acceptance_20260503_diagnostic_website`
- closure: `codex_live_acceptance_20260503_closure`
- visibility: `codex_live_acceptance_20260503_visibility`
- notification: `codex_live_acceptance_20260503_notification`
- reporting: `codex_live_acceptance_20260503_reporting`

Smart views:

- `codex_live_acceptance_20260503_smart_view_active`
- `codex_live_acceptance_20260503_smart_view_risk`

Tickets:

- `T-LIVE-01` incident website normal diagnostics closure path.
- `T-LIVE-02` incident website P0/P1 SLA/OLA risk and closure evidence block.
- `T-LIVE-03` access approval approve path.
- `T-LIVE-04` access approval reject path with required comment.
- `T-LIVE-05` consultation requester reply and `waiting_user` pause/resume.
- `T-LIVE-06` change request scheduled and `waiting_on_approval`.
- `T-LIVE-07` negative create/transition/RBAC evidence.
- `T-LIVE-08` agent GUI-created ticket.
- `T-LIVE-09` diagnostic failure or consent-denied path.
- `T-LIVE-10` requester-safe visibility/passport export path.

Cleanup strategy:

- Keep created tickets as evidence until final summary is generated.
- Deactivate disposable request templates, policies and smart views through supported API paths during Stage 33.
- Do not delete historical evidence artifacts.
- Do not mutate pre-existing non-prefixed live records as part of this campaign.

## Stage Plan

### Stage 0: Workspace And Plan Readiness (2 points)

- [x] Run `.\scripts\bootstrap_shell_utf8.ps1`.
- [x] Confirm local workspace path is `C:\Users\admin-2\CodexProjects\pc_client`.
- [x] Run `git status --short`.
- [x] Confirm generated artifact folders are ignored.
- [x] Record baseline commit and dirty state.
- Evidence: branch `codex/helpdesk-process-model`, HEAD `9cb5ea6`, dirty state only `M PLANS.md`; `.gitignore` covers `artifacts/live_checks/`, `artifacts/browser_checks/`, `artifacts/diagnostics/`, `artifacts/observer_canaries/`.
- User attention: none.

### Stage 1: Context Retrieval And Routing (2 points)

- [x] Run `python scripts/task_intake.py --task "live acceptance test full service desk tickets settings SLA OLA approvals diagnostics observer agent GUI"`.
- [x] Run `python scripts/build_context_pack.py --topic "live acceptance test full service desk tickets settings SLA OLA approvals diagnostics observer agent GUI"`.
- [x] Run `python scripts/search_context_index.py "request_template workflow_profile sla_policy ola_policy approval_policy diagnostic_policy closure_policy observer"`.
- [x] Read canonical docs listed above for touched domains.
- Evidence: context index rebuilt with `python scripts/build_context_index.py --force` because `PLANS.md` made it stale; context pack matched `agent_runtime`, `web_platform`, `observer`, `tickets`, `ui_agent`; `python scripts/diff_context.py` confirmed only `PLANS.md` is changed.
- User attention: none.

### Stage 2: Local Baseline Verification (4 points)

- [x] Run `python scripts/verify_workspace.py`.
- [x] Run `python scripts/docs_inventory.py --check-links`.
- [x] Run focused server pytest:
  `python -m pytest server\tests\test_web_settings_api.py server\tests\test_web_support_api.py server\tests\test_ticket_workflow_profiles.py server\tests\test_ticket_approval_policy.py server\tests\test_ticket_notification_policy.py server\tests\test_ticket_visibility_policy.py server\tests\test_ticket_passport_service.py server\tests\test_ticket_closure_policy.py server\tests\test_helpdesk_policy_registry.py -q --tb=short`
- [x] Run focused agent pytest:
  `python -m pytest pc_agent\tests\test_chat_panel_helpers.py pc_agent\tests\test_ticket_api_client_attachments.py -q --tb=short`
- [x] Run webapp focused tests after bootstrap:
  `pnpm --dir webapp test src\pages\settings\index.test.tsx src\features\forms-builder\forms-builder-panel.test.tsx src\pages\tickets\detail-page.test.tsx src\pages\tickets\list-page.test.tsx`
- Evidence: `verify_workspace.py` passed; `docs_inventory.py --check-links` passed; focused server pytest `121 passed in 543.60s`; focused agent pytest `67 passed in 0.68s`; webapp vitest first run `3 files / 45 tests passed`, then corrected missing `src\pages\tickets\list-page.test.tsx` run `1 file / 1 test passed`.
- User attention: none.

### Stage 3: Remote Deploy And Health (3 points)

- [x] Run `python scripts\release_server_to_remote.py --allow-local-dirty --skip-ci-check --leave-running --smoke-attempts 5 --smoke-delay 3`.
- [x] Run `python scripts\manage_remote_stack.py status control`.
- [x] Run `python scripts\manage_remote_stack.py smoke server`.
- [x] Record remote build/commit and service status.
- Evidence: release flow deployed commit `9cb5ea6`, built webapp bundle successfully, remote fast-forwarded branch `codex/helpdesk-process-model`, control running pid `3052501`, server running pid `3052545`, smoke `/api/health -> 200` after retry during startup and again as an explicit Stage 3 command.
- User attention: none.

### Stage 4: Browser Session And Console Baseline (2 points)

- [x] Open `http://192.168.100.17:8666/admin`.
- [x] Check `/app/admin/forms`.
- [x] Check `/app/settings`.
- [x] Check `/app/tickets`.
- [x] Check `/app/admin/observer`.
- [x] Capture active-tab console and network errors before test data creation.
- Evidence: admin login succeeded with the documented admin dev credential from project runbooks; fresh route pass found `0` new console errors and `0` HTTP errors for `/admin`, `/app/admin/forms`, `/app/settings`, `/app/tickets`, `/app/admin/observer`; screenshots saved under `artifacts/browser_checks/live-acceptance/stage4-*.png`.
- Defect handled: P2 live mismatch found because the login page hinted obsolete fixture credentials for admin/support. Root cause was static text in `webapp/src/features/auth/login-page.tsx`; regression added in `webapp/src/app/router.test.tsx`; `pnpm --dir webapp test src\app\router.test.tsx` passed `5 passed`; `python scripts\verify_workspace.py` passed after each fix; commits `155cf46` and `3ea676c` were deployed, and the live login page now shows the working fixture accounts.
- User attention: none.

### Stage 5: Auth, RBAC Actor Matrix And Safe Test Users (3 points)

- [x] Inventory available admin/support/requester identities without exposing secrets.
- [x] Confirm admin can publish settings.
- [x] Confirm support can operate tickets.
- [x] Confirm requester path can create or view requester-safe tickets.
- [x] Confirm negative actor paths can be tested without damaging existing users.
- Evidence: admin session login returned role `admin`, workspaces `admin/support`, `31` permissions and `200` for admin forms/settings/support queue/observer quick; live support account `op1` returned role `support`, workspace `support`, `17` permissions, `200` for support queue/settings and `403` for admin forms/observer quick; obsolete `support` login is not valid on the stand and was removed from the UI hint; requester/public surface returned `200` for `/app/help` and `/public_api/ticket_forms/current`, while protected `/api/ticket_forms/current` returned `401` without auth.
- User attention: none.

### Stage 6: Existing Data Inventory And Collision Check (2 points)

- [x] Inventory existing published request templates and policy registry.
- [x] Confirm no disposable id collision for `codex-live-acceptance-20260503`.
- [x] Run read-only cleanup scan if needed:
  `python scripts/helpdesk_data_cleanup.py`
- [x] Record existing operational noise that should not be counted as new defect.
- Evidence: admin API inventory returned `200` for `/api/web/admin/forms/current`, `/api/web/admin/helpdesk-model/policies`, `/api/web/settings`, `/api/web/support/queue`; `codex-live-acceptance-20260503` prefix occurrences were `0` in all four payloads. Local cleanup scan could not connect to Postgres from Windows (`ConnectionRefused` to local `127.0.0.1:5432`), so the same read-only script was run on remote host; remote dry-run succeeded with `73` findings, report paths `/var/chat_bot/pc_client/artifacts/diagnostics/helpdesk_data_cleanup_20260503_054510.json` and `.md`, by issue `mojibake=20`, `placeholder=33`, `sensitive_token_like=20`. These are baseline historical noise before live data creation.
- User attention: none.

### Stage 7: Fixture Design Lock (2 points)

- [x] Lock exact disposable ticket types, templates, form fields, policy codes and smart view ids.
- [x] Lock scenario-to-ticket mapping `T-LIVE-01` through `T-LIVE-10`.
- [x] Confirm cleanup/deactivation strategy before publishing.
- Evidence: `Live Fixture Manifest` section in this plan; Stage 6 collision check showed `0` prefix occurrences before publication.
- User attention: none.

### Stage 8: Publish Ticket Types And Form Schemas (3 points)

- [x] Publish or update disposable ticket types for incident, access request, consultation and change request.
- [x] Publish form schemas with required, conditional, picker, date/datetime, multi-select and file fields.
- [x] Verify schema versions and field metadata.
- [x] Verify invalid field mapping is rejected.
- Evidence: active ticket types `codex-live-acceptance-20260503-incident`, `codex-live-acceptance-20260503-access`, `codex-live-acceptance-20260503-consultation`, `codex-live-acceptance-20260503-change` are version `1.0.1`; active form schemas are `codex_live_acceptance_20260503_access_schema` `1.0.1`, `codex_live_acceptance_20260503_consultation_schema` `1.0.1`, `codex_live_acceptance_20260503_change_schema` `1.0.1`, and `codex_live_acceptance_20260503_incident_schema` `1.0.3`. Incident schema covers `url`, `multi_select`, `department_picker`, conditional required department, `file`, diagnostic/priority/routing/closure/display process mappings and UTF-8 Russian labels. Negative invalid condition field returned `400` with `form condition references unknown field 'missing_field'`. Evidence artifacts: `artifacts/live_checks/stage8_form_schemas_20260503.json`, `artifacts/live_checks/stage8_form_schemas_incident_retry_20260503.json`, `artifacts/live_checks/stage8_incident_schema_v3_utf8_20260503.json`, `artifacts/live_checks/stage8_registry_verify_final_20260503.json`, `artifacts/live_checks/stage8_utf8_final_assert_20260503.json`.
- Test harness note: PowerShell here-string publication corrupted Russian literals into `?` for one intermediate incident version; active version `1.0.3` was republished from a UTF-8 file and verified clean. Future live payloads with Russian text should come from UTF-8 files or use escaped JSON, not ad-hoc PowerShell here-strings.
- User attention: none.

### Stage 9: Publish Request Templates (3 points)

- [x] Publish `Live: Не открывается сайт`.
- [x] Publish `Live: Нужен доступ к системе`.
- [x] Publish `Live: Консультация по рабочему месту`.
- [x] Publish `Live: Изменение конфигурации`.
- [x] Verify active/draft flags and template version reload in `/app/admin/forms`.
- [x] Verify inactive template is unavailable for creation.
- Evidence: live API publication succeeded for `codex_live_acceptance_20260503_incident_website` version `1.0.1` with schema `codex_live_acceptance_20260503_incident_website_form` `1.0.1`, policies `priority/routing/sla/ola/diagnostic/closure/visibility/notification/reporting`; `codex_live_acceptance_20260503_access` version `1.0.2`, schema `1.0.2`, policies `priority/routing/sla/approval/closure/visibility/notification/reporting`; `codex_live_acceptance_20260503_consultation` version `1.0.2`, schema `1.0.2`, policies `priority/routing/sla/closure/visibility/notification/reporting`; `codex_live_acceptance_20260503_change` version `1.0.2`, schema `1.0.2`, policies `priority/routing/sla/ola/approval/closure/visibility/notification/reporting`. Registry verification found exactly 4 active live templates and 3 inactive superseded live versions (`access/change/consultation` `1.0.1`), so active catalog excludes stale versions. `/app/admin/forms` loaded after publication with `0` console errors and all captured non-static network requests returned `200`; screenshot saved to `artifacts/browser_checks/live-acceptance/stage9-admin-forms.png`. Evidence artifacts: `artifacts/live_checks/stage9_request_templates_20260503.json`, `artifacts/live_checks/stage9_registry_verify_final_20260503.json`.
- Defects handled: P2 contract bug fixed because `AdminFormsSaveFormRequest` rejected structured `sla_policy`/`reporting_policy` even though the handler and UI expected them; regression extended in `server/tests/test_helpdesk_policy_registry.py`, DTO/serializer/docs fixed in commit `03cead0`. P2 extended-field bug fixed because publish-from-form dropped `multi_select` options before form validation; regression extended and serializer/docs fixed in commit `d0c10f7`. Both commits were deployed to the Linux stand and smoke passed.
- User attention: none.

### Stage 10: Publish Workflow, Priority And Routing Policies (4 points)

- [x] Publish workflow profiles with allowed transitions and required fields/comments/evidence.
- [x] Publish priority matrix with impact/urgency and manual override reason requirement.
- [x] Publish routing policy with default queue, first-match rules, diagnostic reroute rules and anti-loop guard.
- [x] Verify invalid workflow transition config fails.
- [x] Verify invalid routing loop or unsupported target fails.
- Evidence: live workflow profiles saved for `codex-live-acceptance-20260503-incident`, `codex-live-acceptance-20260503-access`, `codex-live-acceptance-20260503-consultation`, `codex-live-acceptance-20260503-change`, including required create/resolve fields, public/internal comment gates, evidence gates, SLA pause/resume/stop action markers, approval action markers and requester-replied auto transitions. Invalid workflow transition to `definitely_not_a_status` returned `400` with `VALIDATION_ERROR`. Published `codex_live_acceptance_20260503_stage10_priority_policy` through version `1.0.4`, active matrix maps impact/urgency to P0-P3 and requires manual override reason for `admin/queue_lead`. Published `codex_live_acceptance_20260503_stage10_routing_policy` through active rollback version `1.0.6`; diff between live versions reported `config.max_auto_reroutes` change, deactivate set v2 inactive, rollback published a new active version. Evidence artifacts: `artifacts/live_checks/stage10_policy_workflow_20260503.json`, `artifacts/live_checks/stage10_registry_verify_20260503.json`.
- Defect handled: P2 live validation gap fixed because direct routing policy publication accepted impossible targets (`default_queue_id=-999`, `then.queue_id=-999`) and negative `max_auto_reroutes`. Focused regression added in `server/tests/test_helpdesk_policy_registry.py`; repo-level routing policy validation added in `server/app/repos/helpdesk_policy_repo.py`; `python -m pytest server\tests\test_helpdesk_policy_registry.py::test_web_admin_publish_routing_policy_rejects_invalid_targets server\tests\test_helpdesk_policy_registry.py::test_web_admin_helpdesk_policy_lifecycle_endpoints -q --tb=short` passed `2 passed`; `python scripts\verify_workspace.py` passed; commit `bbfa79e` deployed to Linux and smoke passed. Re-run live invalid routing now returns `400` (`routing policy default_queue_id must be positive integer`), and the previously accepted invalid policy version was deactivated.
- User attention: none.

### Stage 11: Publish SLA, OLA And Calendar Policies (4 points)

- [x] Publish SLA first-response and resolution targets for P0-P3.
- [x] Publish OLA queue ack and processing targets.
- [x] Configure warning and breach actions.
- [x] Verify 5x8 and 24x7 calendar behavior through deterministic API facts where possible.
- [x] Verify invalid target/calendar shape fails.
- Evidence: `artifacts/live_checks/stage11_sla_ola_calendar_20260503.json`; calendar SLA policy `codex_live_acceptance_20260503_stage11_calendar_sla_policy` published as 24x7 version `1.0.5` and 5x8 version `1.0.6`; preview template `site_system` returned 24x7 first response due `2026-05-03T10:37:09.176895+00:00` and 5x8 first response due `2026-05-04T13:00:00+00:00`; 5x8 first response delta `94970` seconds and resolution delta `728570` seconds; live incident SLA `codex_live_acceptance_20260503_incident_website_sla_policy` active version `1.0.10`; live incident OLA `codex_live_acceptance_20260503_incident_website_ola_policy` active version `1.0.7`; invalid SLA now returns `400` (`sla policy targets.first_response.P1 must be duration`); invalid OLA now returns `400` (`ola policy targets.ack.P1 must be duration`).
- Defect handled: P2 live settings validation gap found because standalone policy publish accepted malformed SLA/OLA targets and calendar shape; regression tests added in `server/tests/test_helpdesk_policy_registry.py`, validator fixed in `server/app/repos/helpdesk_policy_repo.py`, focused registry suite `22 passed`, `python scripts\verify_workspace.py` passed, commit `70fd283` deployed and live re-check passed.
- User attention: none for this stage; long calendar boundary is covered by deterministic preview evidence rather than waiting real business hours.

### Stage 12: Publish Approval, Closure, Visibility, Notification And Reporting Policies (4 points)

- [x] Publish approval policies for approve, reject and timeout/escalation-visible paths.
- [x] Publish closure policy requiring resolution facts, evidence, worklog and requester confirmation where applicable.
- [x] Publish visibility policy hiding OLA internals, raw diagnostics and internal notes from requester.
- [x] Publish notification policy with recipient/action previews.
- [x] Publish reporting/passport policy with public/internal export rules.
- [x] Verify invalid approver source and invalid visibility path fail safely.
- Evidence: `artifacts/live_checks/stage12_governance_policies_20260503.json`; approval policies `codex_live_acceptance_20260503_access_approval_policy` and `codex_live_acceptance_20260503_change_approval_policy` active version `1.0.4`; closure, visibility, notification and reporting policies for `codex_live_acceptance_20260503_incident_website` active version `1.0.3`; invalid approval source now returns `400` (`approval policy approver_source.type is unsupported`); invalid requester visibility path now returns `400` (`visibility policy hide_from_requester[0] contains empty path`); previously accepted invalid versions were deactivated.
- Defect handled: P2 live settings validation gap found because standalone policy publish accepted an unsupported approval source and malformed visibility paths; regression tests added in `server/tests/test_helpdesk_policy_registry.py`, validator fixed in `server/app/repos/helpdesk_policy_repo.py`, focused registry suite `24 passed`, `python scripts\verify_workspace.py` passed, commit `68b4958` deployed and live re-check passed.
- User attention: external notification delivery is not verified in this stage because providers are unavailable/disabled; delivery itself remains in the existing User Attention Checks item for external notification channels.

### Stage 13: Publish Smart Views And Queue Slices (3 points)

- [x] Publish or verify built-in smart views: SLA risk, OLA risk, unassigned, requester replied, stale waiting, waiting approval, diagnostics failed, mass incident candidates.
- [x] Publish one custom disposable smart view.
- [x] Verify invalid custom smart view is rejected.
- [x] Verify smart views are filters, not ownership queues.
- Evidence: `artifacts/live_checks/stage13_smart_views_20260503.json`; required built-ins present in `filters.smart_view_options` and `summary.smart_view_counts`; custom `codex_live_acceptance_20260503_stage13_open_operational_smart_view` published as version `1.0.1`, count `275` with API `limit=300`; invalid `raw_sql` custom view rejected with HTTP 400; `scope=all` and `scope=mine` both combine with the custom smart view, proving smart views remain filters rather than ownership queues; browser verified `/app/tickets` with custom slice visible and selected, network queue calls 200, console warnings/errors 0, screenshot `artifacts/browser_checks/live-acceptance/stage13-tickets-smart-views.png`.
- User attention: none expected.

### Stage 14: Server/API Ticket Creation Matrix (4 points)

- [x] Create `T-LIVE-01` through server/API using incident website template.
- [x] Create `T-LIVE-02` through server/API using high impact/urgency incident values.
- [x] Create `T-LIVE-03` through server/API using access request approve path.
- [x] Create `T-LIVE-04` through server/API using access request reject path.
- [x] Create `T-LIVE-05` through requester/server path using consultation template.
- [x] Create `T-LIVE-06` through server/API using change request template.
- [x] Create `T-LIVE-07` negative/invalid attempt.
- Evidence: `artifacts/live_checks/stage14_ticket_creation_matrix_20260503.json`; created ticket ids `T-LIVE-01=838d4fe4-e116-4e11-89e0-1a2ab1179f0c`, `T-LIVE-02=650e5ee8-a73d-4138-9efc-998b0fde0b19`, `T-LIVE-03=428f44e5-dda1-45a4-9f99-387e30eaba2a`, `T-LIVE-04=c93e7ecc-146c-4444-9ead-d5a34690e9d4`, `T-LIVE-05=df6a853c-26c0-41e8-bdd2-7ca78470c45b`, `T-LIVE-06=241f3d63-e571-41e2-8f2b-e8a1cb64502d`; negative `T-LIVE-07` returned HTTP 400 `validation_error`.
- User attention: none expected.

### Stage 15: Dynamic Form Behavior And Requester-Safe Create Results (3 points)

- [x] Verify hidden conditional fields are not required.
- [x] Verify visible conditional fields become required.
- [x] Verify file fields preserve attachment metadata.
- [x] Verify picker fields preserve selected registry values.
- [x] Verify `process_mapping` feeds impact, urgency, routing and diagnostic params.
- [x] Verify requester-safe response exposes access code, next action and safe due dates.
- [x] Verify raw SLA/OLA/internal policy ids do not appear in requester-facing text.
- Evidence: live API harness `artifacts/live_checks/stage15_dynamic_form_requester_safe_20260503.json`; requester browser screenshot `artifacts/browser_checks/live-acceptance/stage15-requester-safe.png`; final live ticket `a3a865d7-e2af-4dbd-8661-ff46ef073397` / `T-000381`; hidden conditional accepted with ticket `fdaaa47d-0c23-4f52-ac82-d9af0e99cd33`; visible conditional missing returned 400 with `stage15_conditional_detail: Укажите детализацию`; file metadata preserved as `stage15/live-proof.txt` / `live-proof.txt`; picker value preserved as `network`; priority computed `P0`; support queue `servicedesk_l1`; routing source `request_template.routing_policy`; diagnostic playbook mapping `diagnose.website`; requester leak scan `policy_leaks: []`; browser meta shows public label, next action and first-response/resolution due dates.
- Defects fixed during stage: legacy requester `/help` showed raw `status` instead of public requester-safe status/deadlines; fixed in commit `34863f9 server: show requester-safe ticket meta`. Full CI later exposed notification channel audit noise for event-local disabled channels; fixed in commit `0c9482a server: ignore unconfigured disabled notification channels`.
- Verification: `node --check server/help.js`; `python scripts/verify_workspace.py`; focused pytest for static pages, visibility/workflow, Stage8 notification and notification-policy tests; full `python scripts/run_ci_suite.py` green for commit `0c9482aea3175f157048703c4feb69a8d93b6927`; `python scripts/release_server_to_remote.py --allow-local-dirty --leave-running` completed remote smoke; Stage 15 live harness re-run after deploy passed.
- User attention: none.

### Stage 16: Ticket Snapshot And Policy Chain Integrity (3 points)

- [x] For each post-fix created ticket, verify stored request template id/version.
- [x] Verify form schema id/version.
- [x] Verify workflow, priority, routing, SLA, OLA, approval, diagnostic, closure, visibility, notification and reporting refs where applicable.
- [x] Verify historical snapshots stay stable after active policy reload.
- Evidence: `artifacts/live_checks/stage16_ticket_policy_chain.py`, `artifacts/live_checks/stage16_policy_chain_integrity_20260503.json`.
- Live ticket: `bb0c2d18-6c3d-4124-968a-0cfa9478ca06` / template `codex_live_acceptance_20260503_stage16_snapshot`, request template version `1.0.1`, form schema version `1.0.1`, policy refs for approval, closure, diagnostic, notification, OLA, priority, reporting, routing, SLA and visibility.
- Historical reload check: after publishing active template/policy version `1.0.2`, the created ticket request-template snapshot hash stayed unchanged.
- Defect fixed: registry-backed semver versions such as `1.0.x` were previously dropped by `server/tickets/form_catalog.py` / `server/tickets/request_template_submission.py`; fixed in commit `488b5c5 server: snapshot registry template versions`, covered by `server/tests/test_helpdesk_policy_registry.py::test_web_admin_publish_from_form_creates_form_schema_reference` and `server/tests/test_ticket_form_packs.py`.
- Limitation: Stage 14/15 tickets created before the fix still have missing `request_template_version` / `form_schema_version` in their historical snapshots and were intentionally not backfilled; the live evidence records 8 such pre-fix rows under `legacy_pre_fix_version_gaps_not_backfilled`.
- User attention: none expected.

### Stage 17: Workflow Happy Paths (4 points)

- [x] Run `T-LIVE-01` through `new -> queued -> assigned -> in_progress -> waiting_user -> in_progress -> resolved -> closed`.
- [x] Exercise `T-LIVE-06` scheduled attempt from the waiting approval path; live API returned `400` because approvals had already timed out and no support approval decision endpoint exists.
- [x] Verify audit/timeline records old status, new status, actor, reason/comment, required fields snapshot and configured action markers.
- [x] Verify internal status can differ from public status.
- Evidence: `artifacts/live_checks/stage17_workflow_happy_paths.py`, `artifacts/live_checks/stage17_workflow_happy_paths_20260503.json`.
- Live result: `T-LIVE-01` / `T-000366` final status `closed`; observed expected transitions `queued -> assigned`, `assigned -> in_progress`, `in_progress -> waiting_on_user`, `waiting_on_user -> in_progress`, `in_progress -> resolved`, `resolved -> closed`; status timeline count `7`; internal/public status difference verified.
- Defect fixed during stage: official-passport closure gate blocked `resolved` because passport `user_result` was only persisted by the same transition and reporting-only `automated_checks` / `approvals` sections were treated as blocking facts even when not applicable. Fixed in commit `90d7e8b server: relax passport closure gate for live workflow`.
- T-LIVE-06 limitation: scheduled transition remains blocked by approval policy after timed-out approvals; carry this evidence into Stage 18 negative gates and a later approval-action/API follow-up if a full positive approval path is required.
- User attention: none expected for Stage 17; no manual action needed.

### Stage 18: Workflow Negative Gates And RBAC (4 points)

- [x] Verify `queued -> assigned` requires queue/assignee.
- [x] Verify `in_progress -> waiting_user` requires public question.
- [x] Verify `in_progress -> resolved` requires resolution code and public summary.
- [x] Verify missing evidence blocks governed priority where configured.
- [x] Verify wrong role is denied.
- [x] Verify invalid transition is denied.
- Evidence: `artifacts/live_checks/stage18_workflow_negative_gates.py`, `artifacts/live_checks/stage18_workflow_negative_gates_20260503.json`, `artifacts/browser_checks/live-acceptance/stage18-workflow-negative-gates-support-hints.png`.
- Live result: 8 negative checks passed on real tickets. `queued -> assigned` without assignee returned `400 WORKFLOW_POLICY_BLOCKED`; `in_progress -> waiting_on_user` without public question returned `400 WORKFLOW_POLICY_BLOCKED`; `in_progress -> resolved` without `resolution_code` / `public_summary` returned `400 WORKFLOW_POLICY_BLOCKED`; high-priority resolved without evidence returned `400`; invalid `queued -> closed` returned `400`; temporary auditor status change returned `403 ticket.status.change`; `T-LIVE-06` scheduled attempt remains safely blocked at workflow `planned_at` before the later approval path.
- Browser/support UI hint: real ticket `T-000399` showed the resolved transition preview with closure checklist `Не хватает: 4`, including `Код решения`, `Публичный итог для заявителя`, internal summary, worklog, and server-side guard reminder; browser console errors: `0`.
- Defect fixed during stage: live workflow allowed `queued -> assigned` when `assignee_id` was missing because the incident profile had an assigned transition but no invariant. Added regression `test_workflow_blocks_assigned_status_without_assignee`, enforced the built-in assigned status invariant in `server/tickets/workflow_service.py`, updated docs/CODEMAP/navigation, verified focused suite `18 passed`, full CI green, and deployed commit `96fb3aa server: enforce assigned ticket invariant`.
- User attention: none expected.

### Stage 19: Priority And Routing Acceptance (4 points)

- [x] Verify `T-LIVE-01` computed priority from impact/urgency.
- [x] Verify `T-LIVE-02` escalates to P0/P1.
- [x] Verify manual priority override requires reason.
- [x] Verify requester cannot override priority.
- [x] Verify default queue applies when no rule matches.
- [x] Verify high-impact website incident routes to expected queue.
- [x] Verify access request routes to expected access/service-owner queue.
- Evidence: `artifacts/live_checks/stage19_priority_routing_acceptance.py`, `artifacts/live_checks/stage19_priority_routing_acceptance_20260503.json`.
- Live result: 8 priority/routing checks passed. `T-LIVE-01` (`T-000366`) computed `P3` from impact/urgency; `T-LIVE-02` (`T-000367`) escalated to `P0` / legacy `P1`; manual priority without reason returned `400`; public requester manual override returned `400`; admin manual override with explicit reason created `T-000410` as effective `P1` with `priority_source=support_override` and a `priority_overridden` audit event. Default route, high-impact website incident and access request all routed to `servicedesk_l1` with routing source `request_template.routing_policy.default_queue`.
- Defects fixed during stage: `/api/tickets/create` and `/api/tickets/create/preview` did not pass manual override fields into the priority policy fallback, so override gates were not enforced from the create API; fixed in commit `834cebd server: enforce manual priority override gates`. Legacy/public policies without explicit `manual_override.allowed_roles` allowed public/requester override; fixed in commit `bc29431 server: block requester priority overrides`.
- Verification: focused regression `python -m pytest server/tests/test_ticket_form_packs.py::test_create_ticket_manual_priority_override_requires_reason server/tests/test_ticket_form_packs.py::test_create_ticket_manual_priority_override_rejects_requester_role server/tests/test_ticket_form_packs.py::test_public_create_ticket_manual_priority_override_rejects_legacy_policy_without_role_list server/tests/test_ticket_form_packs.py::test_public_create_ticket_manual_priority_override_rejects_requester -q --tb=short` passed; `python scripts/verify_workspace.py` passed before each deploy; both fixes were deployed to Linux with remote smoke. Full CI artifact was intentionally skipped for these two commits (`--skip-ci-check`) and remains a later broad verification item.
- User attention: none expected.

### Stage 20: SLA Timer Acceptance (4 points)

- [x] Verify SLA starts at ticket creation.
- [x] Verify first response SLA stops at first public support reply.
- [x] Verify resolution SLA stops at resolved/closed.
- [x] Verify `waiting_user` pause/resume.
- [x] Verify `waiting_approval` pause/resume where configured.
- [x] Verify warning/risk/breach timestamps and events.
- [x] Verify SLA risk smart view includes near-breach ticket.
- Evidence: `artifacts/live_checks/stage20_sla_timer_acceptance.py`, `artifacts/live_checks/stage20_sla_timer_acceptance_20260503.json`; live tickets `cd50469a-7ae2-473e-946c-75da5246bb1b` (lifecycle) and `11d7585e-744f-4c9e-9b3c-1355641224cd` (risk); 7/7 live checks passed: start, first response stop, waiting-user pause/resume, waiting-approval pause/resume, resolution stop, warning/risk smart view, breach timestamps/events.
- Defects fixed during stage: `2ee098d server: honor live SLA policy triggers` normalized standalone SLA aliases and workflow resume triggers; `391c6d8 server: honor SLA pause target status` made workflow pass transition target status into SLA pause/resume and added `sla_paused_at` / `sla_paused_seconds` to `GET /api/tickets/{ticket_id}/sla`.
- Verification: focused pytest `server/tests/test_ticket_sla_calendar.py::test_sla_policy_accepts_live_status_and_resolution_aliases`, `server/tests/test_ticket_workflow_profiles.py::test_workflow_passes_transition_trigger_to_sla_resume`, `server/tests/test_ticket_workflow_profiles.py::test_workflow_passes_target_status_to_sla_pause`, `server/tests/test_ticket_sla_calendar.py::test_sla_stop_conditions_control_frt_and_resolution_stop` passed; `python scripts/verify_workspace.py` passed; remote release smoke passed after deploy. Full CI artifact was intentionally skipped in release with `--skip-ci-check`.
- User attention: no manual action required for this stage. Limitation: warning/breach timing was compressed by deterministic due-date manipulation on the live stand, then processed by the real `TicketSlaWatchdog.force_check` path; this is not an hours-long wall-clock proof.

### Stage 21: OLA Timer Acceptance (4 points)

- [x] Verify OLA starts on queue assignment and queue change.
- [x] Verify OLA ack stops on assignee set or `in_progress`.
- [x] Verify OLA processing stops on queue change, resolved, closed or handoff.
- [x] Verify warning recipients and breach action dispatch.
- [x] Verify OLA risk smart view includes queue-risk ticket.
- [x] Verify requester view does not expose OLA internals.
- Evidence: `artifacts/live_checks/stage21_ola_timer_acceptance.py`, `artifacts/live_checks/stage21_ola_timer_acceptance_20260503.json`; live tickets `9c933039-2d97-4d7f-9d80-ce9a9ccb94a3` (lifecycle), `f0d98a1b-c855-4d0b-88d0-b183586ac47f` (risk/breach) and `4f80beed-1b43-4d51-a18f-a19531edc485` (requester visibility); 8/8 live checks passed: OLA start, ack stop, pause/resume on vendor wait, processing stop/restart on queue handoff, processing stop on resolved, OLA-risk smart view, breach timestamps/events/policy actions and requester redaction.
- Defects fixed during stage: `b25ee75 server: honor OLA workflow pause triggers` makes workflow OLA hooks pass target status into pause checks and configured transition trigger such as `vendor_replied` into resume checks before the final `ticket.status` write. Regression tests cover target-status pause and transition-trigger resume.
- Verification: RED tests first failed for OLA pause/resume; focused pytest `python -m pytest server/tests/test_ticket_ola_policy.py server/tests/test_ticket_workflow_profiles.py -q --tb=short` passed with 27/27; `python scripts/verify_workspace.py` passed; remote release smoke passed after deploy; repeated live harness passed. Full CI artifact was intentionally skipped in release with `--skip-ci-check`.
- User attention: no manual action required for this stage. Limitations: OLA risk and breach timing was compressed by deterministic due-date manipulation on the live stand, then processed by the real `check_ola_breaches` path; current OLA runtime has breach-action dispatch but no separate warning-before timer, so the warning-recipient item is covered by breach policy-action notification evidence rather than an independent OLA warning event.

### Stage 22: Approval Policy Acceptance (4 points)

- [x] Verify `T-LIVE-03` creates approval with expected approver source.
- [x] Approve `T-LIVE-03` and verify audit, transition, notification and passport evidence.
- [x] Verify `T-LIVE-04` rejects without comment is denied.
- [x] Reject `T-LIVE-04` with comment and verify safe requester text.
- [x] Verify `any_one`, `all` and `sequential` modes where configured.
- [x] Verify non-approver cannot approve.
- Evidence: `artifacts/live_checks/stage22_approval_policy_acceptance.py`, `artifacts/live_checks/stage22_approval_policy_acceptance_20260503.json`; live tickets `3c5217d5-00f7-4e24-942a-8fc3e8ca8728` (`any_one` approve), `92b0a010-1486-46a6-85a5-0ec4c80e67e9` (reject/comment/requester-safe), `bd27ff59-9f31-4529-9387-564c13b1fae4` (`all`), `c13f928c-3c68-4658-a73c-a2c1d30433d2` (`sequential`) and `81c17803-0e8c-45ab-b5f0-1701a56a7b07` (non-approver negative). 7/7 live checks passed: approver source, approve audit/event/notification/passport, reject comment gate, requester-safe reject projection, `all` blocking until every approval, `sequential` current-approver advancement and non-approver denial.
- Defects fixed during stage: `21a15af server: add support approval decisions` added typed support approval decision route, approver/current-approval enforcement, reject-comment validation, sequential advancement, `approval_approved` / `approval_rejected` events and notification-policy aliases. The first live harness run also corrected its requester-safe assertion to inspect actual payload fields rather than visibility metadata.
- Verification: RED route tests first failed with `404`; focused regression `python -m pytest server/tests/test_web_support_api.py::test_web_support_approval_decision_approves_and_notifies server/tests/test_web_support_api.py::test_web_support_approval_decision_reject_requires_comment server/tests/test_web_support_api.py::test_web_support_approval_decision_rejects_non_approver -q --tb=short` passed; broader focused approval check passed 17/17; `python scripts/verify_workspace.py` passed before deploy; remote release smoke passed; repeated live harness passed. Full CI artifact was intentionally skipped in release with `--skip-ci-check`.
- User attention: no manual action required for this stage. Limitation: this stage verified the approval decision API and support/passport/requester projections; browser UX screenshots for approval controls remain part of the later final browser signoff stage.

### Stage 23: Diagnostics, Consent And Module Operations (5 points)

- [x] For `T-LIVE-01`, run suggested diagnostic playbook with consent.
- [x] For `T-LIVE-09`, verify consent denied or diagnostic failure path.
- [x] Verify consent is required before requester-device/high-risk tool where configured.
- [x] Verify ticket status remains workflow-owned while operation status changes independently.
- [x] Verify operation id is stable and visible.
- [x] Verify diagnostic result attaches to timeline and passport evidence when configured.
- [x] Verify reroute by diagnostic result.
- Evidence: `artifacts/live_checks/stage23_diagnostics_consent_acceptance.py`, `artifacts/live_checks/stage23_diagnostics_consent_acceptance_20260503.json`; final live safe ticket `8f003709-cfc3-4064-9f46-ad1ee8dc9c08`, high-risk autorun-skip ticket `021f3f75-6118-46e9-b443-3e93bc7515f4`; safe playbook operation `71caf280-a6cf-414f-818f-b961cd0d703a` reached `succeeded`; DNS diagnostic operation `e4375eea-374a-4664-860e-565c8e3fddf8` returned `DNS_RESOLUTION_FAILED`, left ticket status `in_progress`, rerouted queue `7 -> 8`, emitted `diagnostic_result_classified` / `routing_applied` / `queue_changed`, and materialized passport evidence `source_ref=operation:e4375eea-374a-4664-860e-565c8e3fddf8`; consent-required tool operation `f54ec3c9-683c-417b-80a0-4effee16e78d` stayed `waiting_consent` and then moved to `denied` after live deny API call; high-risk diagnostic autorun emitted `diagnostic_autorun_skipped` with reason `high_risk_consent_required`.
- Defects fixed during stage: `587022f server: enforce support tool consent gate` made typed support tool actions evaluate tool metadata through `PolicyEngine`, create `waiting_consent` operations without dispatch and return `dispatch_status=waiting_consent`. Live reproduction before the fix showed `observer_canary_0167a492.consent_probe` advertised `requires_consent=true` but dispatching as `accepted`; deny then failed with `INVALID_STATUS`.
- Verification: RED regression first failed because `run_tool` was dispatched before consent; focused tests passed (`test_web_support_tool_action_keeps_consent_required_tool_waiting`, adjacent support tool tests and `server/tests/test_tools_async_response_contract.py`, 7/7); `python scripts/verify_workspace.py` passed; `python scripts/release_server_to_remote.py --allow-local-dirty --skip-ci-check --leave-running --smoke-attempts 8 --smoke-delay 3` completed and remote smoke passed; repeated Stage 23 live harness passed. Full CI artifact was intentionally skipped in release with `--skip-ci-check`.
- User attention: real requester-device prompt UX was not clicked in a local GUI/browser prompt; server-side consent gate, support deny path and high-risk autorun skip are verified live. Passport generation was performed as admin because the disposable support user lacked passport manage permission; this does not affect diagnostic evidence materialization but is recorded as a test-role limitation.

### Stage 24: Observer Trace Acceptance (5 points)

- [x] Verify ticket root trace exists for created tickets.
- [x] Verify operation spans exist for diagnostics and tool runs.
- [x] Verify module/tool entry breadcrumb exists.
- [x] Verify command/result correlation exists.
- [x] Verify compact agent action rows are visible with `include_agent_actions=1`.
- [x] Verify dangerous-flow gaps are not present.
- [x] Run `python scripts\run_observer_canary_suite.py` if relevant to changed or suspicious observer behavior.
- [x] Browser check `/app/admin/observer` for runtime status, trace visibility and console errors.
- Evidence: `python artifacts\live_checks\stage24_observer_trace_acceptance.py` passed 13/13 checks and wrote `artifacts/live_checks/stage24_observer_trace_acceptance_20260504.json`; ticket root trace `37450ccd-8034-4dc7-a36e-8368f9a9943a` for ticket `8f003709-cfc3-4064-9f46-ad1ee8dc9c08`; DNS operation `e4375eea-374a-4664-860e-565c8e3fddf8`; DNS bundle has 27 spans and 8 compact agent action rows; denied consent operation `f54ec3c9-683c-417b-80a0-4effee16e78d` has `operation.stage.denied` without sent/accepted/succeeded dispatch stages; high-risk autorun skip ticket `021f3f75-6118-46e9-b443-3e93bc7515f4` has trace-visible `ticket.diagnostic_autorun_skipped`.
- Observer canary: first full run `artifacts/observer_canaries/stage24_observer_canary_20260504_rerun.json` exposed a real registry gap: local/current agent version `3.1.26` was present for `windows_amd64` but missing for `linux_alt_x86_64`. Fixed operationally by building Linux PyInstaller artifacts on `/var/chat_bot/pc_client`, verifying the isolated binary with `--verify`, packaging `pc_agent-linux_alt_x86_64-3.1.26.tar.gz` and uploading it to `/api/agent_builds/upload` as `linux_alt_x86_64/stable/3.1.26` (`sha256=c3a1ca79b5ea9858425f89635bd91dd1319f5c272c6b37d8972ad3f8fe882281`, size `109329129`). Re-run `artifacts/observer_canaries/stage24_observer_canary_20260504_after_linux_build.json` passed 19/19 scenarios.
- Browser evidence: `/app/admin/observer` opened in browser fallback after Browser Use runtime navigation failed with local app-server path error; Playwright MCP verified runtime `ok`, search by trace `37450ccd-8034-4dc7-a36e-8368f9a9943a` narrowed traces to 1, detail showed 27 spans, evidence sources `ticket_events=18` / `operations=2`, bundle coverage `agent_actions=8`, `runtime_audit=30`, `recent_logs=15`, related traces `1`, command/result spans and agent action rows. Console check reported 0 warnings and 0 errors; screenshot saved as `stage24-admin-observer-trace.png` by the browser tool.
- User attention: none expected.

### Stage 25: Notification And Recipient Action Acceptance (3 points)

- [x] Verify notification policy events: created, assigned, waiting_user, requester_replied, SLA warning, SLA breach, OLA warning/breach, approval created/approved/rejected, diagnostic completed/failed, resolved, closed.
- [x] Verify recipients: requester, assignee, queue, queue lead, admin, watchers and external group/provider where configured.
- [x] Verify disabled/unavailable external channels leave audit evidence.
- [x] Verify per-recipient preferences remain final filter.
- Evidence: `python artifacts\live_checks\stage25_notification_acceptance.py` passed 7/7 checks and wrote `artifacts/live_checks/stage25_notification_acceptance_20260504.json`; live ticket `005354eb-b289-45b1-8e3a-0c45c86d3516`, muted-ticket preferences check, queue `codex_live_acceptance_stage25_1777870773`, actors `stage25_requester_1777870773`, `stage25_assignee_1777870773`, `stage25_queue_member_1777870773`, `stage25_queue_lead_1777870773`, `stage25_watcher_1777870773`, `stage25_muted_1777870773`.
- Bug fixed during stage: live `POST /api/web/notifications/preferences` returned 500 after persisting because `handle_notification_preferences_post` returned raw `TicketNotificationPref` ORM object. Added regression `test_notification_preferences_post_returns_serialized_payload`, changed the handler to return plain JSON fields, updated docs/navigation, committed `9efd433 server: serialize notification preferences response`, deployed that commit to `/var/chat_bot/pc_client`, restarted the server and re-ran smoke successfully.
- Verification: RED regression failed with HTTP 500 before the fix; after fix `python -m pytest server\tests\test_stage8.py::test_notification_preferences_post_returns_serialized_payload -q --tb=short` passed; focused notification suite `python -m pytest server\tests\test_stage8.py server\tests\test_ticket_notification_policy.py server\tests\test_ticket_ola_policy.py -q --tb=short` passed 30/30; `python scripts\verify_workspace.py` passed; remote smoke passed; repeated Stage 25 live harness passed.
- User attention: real delivery through production external providers (email/Telegram/VK Teams/SMS) still needs manual/provider-side confirmation; this stage verified provider preview calls and DB audit rows with an injectable live harness provider, plus disabled/unavailable channel evidence.

### Stage 26: Visibility And Requester Projection Acceptance (3 points)

- [x] Verify requester cannot see internal notes.
- [x] Verify requester cannot see OLA details.
- [x] Verify requester cannot see raw diagnostics.
- [x] Verify requester cannot see internal queue comments.
- [x] Verify support can inspect support-safe internal details.
- [x] Verify public status mapping is requester-safe.
- [x] Verify `T-LIVE-10` requester/passport export hides internal sections.
- Evidence: `python artifacts\live_checks\stage26_visibility_requester_projection.py` passed 6/6 checks after redeploy and wrote `artifacts/live_checks/stage26_visibility_requester_projection_20260504.json`; final live ticket `ac4f6b84-b200-4e9b-9320-8fee605b6b67`, access code `MW6CGMHM`, support actor `stage26_support_1777872238`.
- Browser evidence: requester `/app/ticket/ac4f6b84-b200-4e9b-9320-8fee605b6b67?code=MW6CGMHM` rendered public label `Заявка в работе`, contained no raw `waiting_on_internal_team` and no stage secret markers; screenshot saved as `artifacts/live_checks/stage26_requester_ticket_20260504.png`. Support `/app/tickets/ac4f6b84-b200-4e9b-9320-8fee605b6b67` opened after support web-session login, showed the live ticket and support-only internal markers, and browser console reported 0 warnings/errors; screenshot saved as `artifacts/live_checks/stage26_support_ticket_20260504.png`. Browser Use runtime could not attach due local app-server path failure, so browser verification used Playwright MCP against the same remote URL.
- Bug fixed during stage: support `GET /api/tickets/{ticket_id}/snapshot` returned 500 when relation collections contained `TicketWatcher` ORM rows. Added regression `test_support_snapshot_serializes_ticket_relation_collections`, serialized `watchers`, `links`, `kb_links` and `worklogs` as JSON-safe DTOs before visibility projection, updated docs/navigation, committed `9aa0084 server: serialize ticket snapshot relations`, deployed and smoke-checked the server.
- Bug fixed during stage: requester React page rendered raw internal `ticket.status` (`waiting_on_internal_team`) in badge/sidebar instead of requester-safe public status. Added `index.status.test.tsx`, extended requester ticket type fields, rendered `public_status_label -> requester_status_label -> status_label -> status`, committed `c6d8efe webapp: show requester-safe ticket status`, released rebuilt webapp bundle to the remote stand and re-ran live/browser checks.
- Verification: RED server regression failed with `TypeError: Object of type TicketWatcher is not JSON serializable`; after fix `pytest server/tests/test_ticket_queue_routing_contracts.py::test_support_snapshot_serializes_ticket_relation_collections -q` passed and full `server/tests/test_ticket_queue_routing_contracts.py` passed 12/12. RED requester UI test first failed because DOM showed `waiting_on_internal_team`; after fix `pnpm --dir webapp exec vitest run src/pages/requester-ticket/index.status.test.tsx` passed and `pnpm --dir webapp exec vitest run src/pages/requester-ticket` passed 3/3. `pnpm --dir webapp run build`, `python scripts\verify_workspace.py`, `python scripts\release_server_to_remote.py --allow-local-dirty --skip-ci-check --leave-running` and remote smoke passed. Full CI artifact was intentionally skipped in release with `--skip-ci-check`.
- User attention: none expected.

### Stage 27: Smart Views And Support Queue Acceptance (3 points)

- [x] Verify each built-in smart view count matches list results.
- [x] Verify custom smart view count and sorting.
- [x] Verify support list filters by status, queue, priority, due/risk and search where supported.
- [x] Verify queue counters do not include closed/canceled unless configured.
- [x] Browser check `/app/tickets`, open ticket from smart view, use back navigation.
- Evidence: `python artifacts\live_checks\stage27_smart_views_support_queue.py` passed 33/33 checks and wrote `artifacts/live_checks/stage27_smart_views_support_queue_20260504.json`; support actor `stage27_support_1777875791`; queue `codex_live_acceptance_stage27_1777875791`; custom smart view `codex_stage27_custom_deadline_1777875791`. The harness verified built-in and custom `summary.smart_view_counts` match selected list `visible_count`, expected target tickets appear in each smart view, closed/canceled signal tickets are excluded from open-only smart views, support actor queue access is scoped, status/scope/search filters work, and custom smart-view due/risk sorting returns `Stage27 custom due early` before `Stage27 custom due late`.
- Browser evidence: `/app/tickets` loaded as `stage27_support_1777875791`; custom smart view `Stage27 custom deadline 1777875791` showed count `2` and rendered `Stage27 custom due early` before `Stage27 custom due late`; clicking the early row opened `/app/tickets/9879f236-b50e-4e51-9dba-0f7b10da7419`; `Назад` returned to `/app/tickets`. Screenshots: `artifacts/live_checks/stage27_support_custom_view_20260504.png`, `artifacts/live_checks/stage27_support_ticket_detail_20260504.png`, `artifacts/live_checks/stage27_support_back_navigation_20260504.png`; browser evidence JSON: `artifacts/live_checks/stage27_browser_evidence_20260504.json`. Browser Use runtime could initialize but failed to navigate through the in-app app-server path, so browser verification used Playwright MCP against the same remote URL.
- Bug fixed during stage: published custom smart-view `sort_json` was validated and stored but ignored by `GET /api/web/support/queue`, leaving results in base `updated_at desc` order. Live harness reproduced `late -> early`; RED regression in `server/tests/test_web_support_api.py::test_web_support_queue_applies_published_custom_smart_view` failed on that order. `server/web_api/support_handlers.py` now applies selected custom view sort after smart-view filtering and before scope/status/query slicing; docs/navigation updated; commit `83324aa server: apply custom smart view sorting`; full CI artifact `artifacts/ci/83324aa70597b605f54cbbedef1b3b82df9777ac/summary.json` is green and remote deployed at `83324aa`.
- Limitation: `GET /api/web/support/queue` exposes `scope`, `status`, `smart_view` and `query`; there are no dedicated `queue` or `priority` query params. Queue behavior was verified through support-actor access isolation and custom smart-view queue/filter capability; priority was covered as setup/response context, not as a direct support queue query filter.
- User attention: none expected.

### Stage 28: Closure, Passport And Reporting Acceptance (4 points)

- [x] Attempt to close `T-LIVE-02` without required P0/P1 evidence and verify block.
- [x] Add required facts: resolution code, public summary, internal summary if required, diagnostic evidence, approval evidence if used, operation log and worklog.
- [x] Resolve and close.
- [x] Verify SLA/OLA stop.
- [x] Verify closure audit.
- [x] Verify passport includes solution summary, evidence and export preview.
- [x] Verify invalid resolution code is rejected.
- Evidence: `python artifacts\live_checks\stage28_closure_passport_reporting.py` produced raw first-pass evidence `artifacts/live_checks/stage28_closure_passport_reporting_20260504.json`; after the OLA fix and live recheck the final combined artifact is `artifacts/live_checks/stage28_closure_passport_reporting_final_20260504.json`. Live ticket `T-LIVE-02` is `650e5ee8-a73d-4138-9efc-998b0fde0b19` / `T-000367`, final status `closed`, resolution code `fixed`, requester summary and internal summary present, diagnostic operation evidence and worklog present, approved approval fact attached for reporting/passport coverage, and passport export preview includes required sections.
- Gate results: pre-evidence resolve/close was blocked by the workflow evidence guard before the closure policy whitelist was reached; the same closure requirements payload exposed missing P0 evidence. After required evidence was added, invalid resolution code was rejected by closure policy with `CLOSURE_POLICY_BLOCKED`, and resolving without official passport was blocked until the passport was generated.
- Bug fixed during stage: live closure stopped SLA but did not stop OLA processing for a legacy published policy with list-style `stop_conditions=["ticket_resolved","ticket_closed"]`. Root cause was `server/tickets/ola_service.py` assuming dict-shaped stop conditions and missing the `ticket_resolved` / `ticket_closed` aliases. Added RED regression `test_ola_processing_stop_accepts_legacy_alias_list_conditions`, fixed alias/list handling, updated docs/navigation, committed `8fa665f server: support legacy OLA stop aliases`, deployed, and rechecked the same live ticket. Recheck artifact: `artifacts/live_checks/stage28_ola_stop_recheck_after_fix_20260504.json`, with `ola_processing_at` set and `ola_processing_stopped` event present.
- Browser evidence: support detail `/app/tickets/650e5ee8-a73d-4138-9efc-998b0fde0b19` opened as the Stage 28 support actor, showed `Закрыта`, terminal transitions disabled, `Passport 7/7`, `P0`, and `Stage28 diagnostic evidence` / `stage28.diagnostic.confirm_fix` in the operational card. Screenshots: `artifacts/live_checks/stage28_support_passport_20260504.png`, `artifacts/live_checks/stage28_support_closed_ticket_20260504.png`; browser evidence JSON: `artifacts/live_checks/stage28_browser_evidence_20260504.json`. Browser Use runtime failed to navigate because the local app-server path was missing, so browser verification used Playwright MCP against the same remote URL; fresh console check after re-login reported 0 errors.
- Verification: RED OLA regression failed with `AttributeError: 'list' object has no attribute 'get'`; after the fix `python -m pytest server\tests\test_ticket_ola_policy.py -q --tb=short` passed 8/8, `python scripts\verify_workspace.py` passed, remote release deployed commit `8fa665f` and smoke passed, live OLA recheck passed, and the final combined Stage 28 artifact reports 10/10 checks passed.
- User attention: none expected.

### Stage 29: Agent Runtime And GUI Live Acceptance (8 points)

- [x] Start or connect a live isolated agent path:
  `python scripts/manage_local_agent.py start codex-live-acceptance-agent --gui --ui-port 8786 --ws-url ws://192.168.100.17:8666/ws --api-url http://192.168.100.17:8666/api`
- [x] Verify `GET http://127.0.0.1:8786/ui/agent/status`.
- [x] Verify agent can fetch current form pack/templates.
- [x] Create `T-LIVE-08` from agent GUI using a current published template.
- [x] Create or preview a schema-backed disposable template from agent path if supported.
- [x] Verify GUI form behavior: required fields, conditional fields, picker fields, file attachment path, diagnostic consent wording and server-preview fallback.
- [x] Verify post-create result panel: access code, next action, expected due dates, open ticket action, add message action, create another action and no raw SLA/OLA/internal policy jargon.
- [x] Verify server receives request template snapshot, form schema snapshot, priority/routing decision, requester/device identity and attachment message reference if used.
- [x] Verify agent logs do not leak token and do not show unexpected tracebacks.
- [x] Verify controlled shutdown through `POST /ui/agent/shutdown` unless leaving the agent running is explicitly needed for a later stage.
- Evidence: isolated source-mode GUI agent `codex-live-acceptance-agent` started on UI port `8786` with issued machine/device id `043a94bf-0077-5ffe-a1b4-419964d69df9`, version `3.1.26`, `connection_state=connected`, `ui_bridge_running=true`, and recommended stable build `3.1.26` / `same_version`. The check intentionally used the source runtime, not the compiled launcher build, so no compiled agent refresh was required for this stage.
- Evidence artifacts: `artifacts/live_checks/stage29_agent_form_pack_20260504.json`, `artifacts/live_checks/stage29_agent_ticket_create_result_20260504.json`, `artifacts/live_checks/stage29_agent_ticket_snapshot_20260504.json`, `artifacts/live_checks/stage29_agent_add_message_20260504.json`, `artifacts/live_checks/stage29_agent_window_close_runtime_20260504.json`, `artifacts/live_checks/stage29_agent_logs_collect_20260504.json`, `artifacts/live_checks/stage29_agent_shutdown_20260504.json`, final checker `artifacts/live_checks/stage29_agent_runtime_gui_final_20260504.json`.
- Live result: created `T-LIVE-08` as `046398cc-8414-44c4-bc7c-dbb826ce4bc3` / `T-000507` through the GUI automation surface from current template `site_system` (`Сайт / система`, form-pack version `1.0.14`). Server snapshot contains request template/form data, dynamic field summary including conditional `url`/`pc_name`/`affected_scope`, priority decision `priority_class=P0`, routing decision to queue `servicedesk_l1`, requester profile, device identity, public access code, requester-safe status, attachment message with `attachment_count=1`, and a post-create follow-up message from the agent.
- Runtime result: `window.close` hid the main window but did not stop the runtime; `GET /ui/agent/status` still returned `connected` and `ui_bridge_running=true`, then `window.show` restored the GUI state. Controlled shutdown through `POST /ui/agent/shutdown` returned `accepted=true`, and `python scripts\manage_local_agent.py status codex-live-acceptance-agent` reported stopped.
- Verification: `python -m pytest pc_agent\tests\test_ui_api_server_shutdown.py pc_agent\tests\test_runtime_logging.py -v --tb=short` passed 8/8; remote smoke passed before shutdown; final checker reports 16/16 Stage 29 checks passed, no raw token hits in local agent logs/action trace, and no unexpected tracebacks. No product bug fix was needed in this stage.
- User attention: exact native Qt wizard pixel/keyboard usability and visible tray menu clicks remain in `User Attention Checks`. The live automation surface verified the functional GUI-owned path, not every manual click target. Diagnostic consent wording was not expected for selected current template `site_system` because its live template has no diagnostic consent policy.

### Stage 30: Security, Token And Log Safety Acceptance (4 points)

- [x] Verify no raw token in server logs.
- [x] Verify no raw token in agent logs.
- [x] Verify artifacts redact token-like values.
- [x] Verify unknown template, inactive template, stale policy version if relevant, invalid queue id and invalid approval actor are rejected safely.
- [x] Verify diagnostics cannot run against unauthorized device/ticket context.
- Evidence: `artifacts/live_checks/stage30_security_token_log_safety_20260504.json` and redacted server log excerpt `artifacts/live_checks/stage30_server_logs_redacted_20260504.txt`.
- Live result: Stage 30 initially found a real security defect: an agent token for a different device could reach `/api/tools/run` dispatch for `screen.collect` on T-LIVE-08's device and failed only because the target agent was offline. Fixed in commit `6bb2059 server: reject agent tool runs for other devices`, adding a pre-dispatch `AuthContext.actor_id` vs `device_id` guard for `actor_role=agent` and regression coverage in `server/tests/test_tools_async_response_contract.py`.
- Re-check result: after remote release to Linux and smoke, the same live negative scenario returned 403 `DEVICE_CONTEXT_MISMATCH`; no raw Stage 29 or Stage 30 agent token was found in server logs, local agent logs, action trace or generated artifacts. Other negative checks passed: no-token protected API 401 `AUTH_REQUIRED`, unknown/inactive template 400 validation, invalid routing rule 400 `VALIDATION_ERROR`, stale policy rollback 400 `VALIDATION_ERROR`, invalid approval actor 403 `APPROVAL_ACTOR_MISMATCH`.
- Verification: `python -m pytest server\tests\test_tools_async_response_contract.py -q` passed 5/5; `python -m pytest server\tests\test_tools_async_response_contract.py server\tests\test_tool_dispatch_failure.py -q` passed 7/7; `python -m pytest server\tests\test_tool_started_event.py::test_tool_call_started_created_before_command -q` passed; `python scripts\verify_workspace.py` passed; `python scripts\release_server_to_remote.py --allow-local-dirty --skip-ci-check --leave-running --smoke-attempts 5 --smoke-delay 3` completed and remote smoke passed.
- User attention: none.

### Stage 31: Browser UX And Console Signoff (5 points)

- [x] Browser check `/admin`.
- [x] Browser check `/app/admin/forms`.
- [x] Browser check `/app/settings`.
- [x] Browser check `/app/tickets`.
- [x] Browser check representative ticket details: incident, access request, consultation and change request.
- [x] Browser check `/app/admin/observer`.
- [x] Browser check requester/public path if used.
- [x] Verify no overlapping text.
- [x] Verify long Russian labels fit.
- [x] Verify buttons and controls are understandable.
- [x] Verify compact panels do not use hero-scale text.
- [x] Verify no raw internal policy ids leak to requester-facing UI.
- [x] Capture screenshots, console and network summary.
- Evidence: `artifacts/live_checks/stage31_browser_20260504/stage31_browser_ux_console_20260504.json` and screenshots in the same folder. Final live harness checked 13 canonical browser pages against `http://192.168.100.17:8666`: 0 console errors, 0 console warnings, 0 page errors, 0 network errors, 0 pages with horizontal overflow, 0 missing expected text entries, and no requester-facing internal policy term hits. Full-page forms-builder recheck captured `desktop_admin_forms_full_after2.png`; remaining DOM clipped candidates are expected `<select>` scrollWidth noise from long option labels, not visible overlap.
- Defects fixed and rechecked live: `088cff1 webapp: contain workspace layout overflow`, `fa9b888 webapp: prevent ticket detail mobile overflow`, `ee5341a webapp: stabilize forms builder responsive grids`.
- Verification: `pnpm --dir webapp run build` passed after each UI fix; focused webapp tests passed (`src\features\forms-builder\forms-builder-panel.test.tsx`, 27 tests) after the final forms-builder fix; `python scripts\release_server_to_remote.py --allow-local-dirty --skip-ci-check --leave-running --smoke-attempts 5 --smoke-delay 3` completed after each deployed fix and remote smoke passed. Final Stage 31 browser harness passed after committed release at `ee5341a`.
- Tooling note: the in-app Browser Use runtime could not start from the UNC cwd, so Stage 31 live browser automation used Playwright Chromium from the project webapp toolchain against the same canonical remote URL.
- User attention: none required for automated acceptance; only subjective visual preference review remains optional.

### Stage 32: Current Live Bugfix Gate (5 points)

Priority order is strict. Do not start broad visual redesign until this gate is complete.

- [x] Register user live QA findings as defects:
  - `BUG-508-REQUESTER-CLOSE`, ticket `#T-000508`.
  - `BUG-509-DIAGNOSTIC-CONSENT`, ticket `#T-000509`.
  - `BUG-AGENT-CHAT-ORDER`.
  - `BUG-AGENT-GUI-LAYOUT`.
  - `BUG-SUPPORT-WORKSPACE-DISCOVERY` as redesign input only.
- [x] Reproduce `BUG-508-REQUESTER-CLOSE` live:
  - Open requester/public path for `#T-000508`.
  - Confirm whether the affected surface is legacy `/help`, React `/app/ticket`, agent GUI, or more than one.
  - Capture screenshot and DOM/widget state.
  - Expected: primary confirm action is visible, enabled and named as closure action.
- [x] Add focused regression for `BUG-508-REQUESTER-CLOSE`:
  - React requester path: `webapp/src/pages/requester-ticket/index.test.tsx` if `/app/ticket` is affected.
  - Legacy path: browser/live check or JS-level coverage for `server/help.js` if `/help` is affected.
  - Agent GUI path: `pc_agent/tests/test_chat_panel_helpers.py` or a small helper-level test if Qt full UI is not practical.
- [x] Fix `BUG-508-REQUESTER-CLOSE` in the smallest ownership zone and live re-check `#T-000508`.
  - Local fix and focused regression pass; remote live browser re-check passed on legacy `/help` and React `/app/ticket` for `#T-000508`; confirm/reject controls are visible and enabled.
- [x] Reproduce `BUG-509-DIAGNOSTIC-CONSENT` live:
  - Inspect `#T-000509` ticket snapshot, `custom_fields.diagnostic_consent`, request template diagnostic policy and created events.
  - Query operations/playbook runs for the ticket and identify whether the server created `waiting_consent`, skipped before operation creation, or support launch skipped dispatch.
  - Capture observer trace or absence of trace for `diagnostic_policy_auto_run`.
- [x] Add focused regression for `BUG-509-DIAGNOSTIC-CONSENT`:
  - Use or extend `server/tests/test_ticket_diagnostic_policy.py` for auto-run consent gates.
  - Use or extend `server/tests/test_web_support_api.py` for support-initiated consent-required diagnostic run.
  - If agent/requester prompt path is affected, add agent GUI/server API helper coverage.
- [x] Fix `BUG-509-DIAGNOSTIC-CONSENT`:
  - If consent was not granted at create time, surface a clear requester/support next action instead of opaque `diagnostic autorun skipped`.
  - If the policy should request consent, create a `waiting_consent` operation and make the prompt reachable.
  - Preserve observer trace visibility for both skipped and waiting-consent branches.
  - Implemented as an agent-side create guard: required requester-device diagnostic consent cannot be submitted unchecked, preventing silent `diagnostic_autorun_skipped(consent_required)` tickets.
- [U] Live re-check `#T-000509` successor ticket:
  - Create a new ticket from updated agent `3.1.29` with the same diagnostic-consent template; old `#T-000509` cannot prove the fix because it was already created with `granted=false`.
  - Verify the user sees the required consent checkbox and cannot submit while it is unchecked.
  - Verify that after checking consent the ticket stores `diagnostic_consent.granted=true`.
  - Verify support sees the same state in ticket detail/playbook panel.
  - Verify operation status and observer trace are consistent.
- [~] Reproduce `BUG-AGENT-CHAT-ORDER` in the local/live agent GUI:
  - Use a ticket with at least three public/support messages in known chronological order.
  - Capture visible order and scroll behavior.
- [x] Add focused regression for `BUG-AGENT-CHAT-ORDER` around support/detail timeline ordering in `server/tests/test_web_support_api.py`.
- [x] Fix `BUG-AGENT-CHAT-ORDER` and re-check support workspace ordering.
  - Support API/web order fixed and tested; browser re-check for `#T-000508` shows chronological order. Native agent GUI order still needs user visual confirmation after `3.1.29`.
- [~] Reproduce `BUG-AGENT-GUI-LAYOUT` at common Windows sizes:
  - Request wizard with long Russian labels and picker/file/date fields.
  - Ticket detail/chat with resolved confirmation row.
  - Attachment row and screenshot/video controls.
- [~] Add focused helper/screenshot checks where practical for `BUG-AGENT-GUI-LAYOUT`; otherwise record exact manual viewport sizes and screenshots.
- [~] Fix `BUG-AGENT-GUI-LAYOUT` with scoped layout/QSS changes only; avoid redesigning the whole GUI in this gate.
  - Scoped resolved prompt/consent-label fixes are local; broader visual overflow remains user-attention after compiled agent rollout.
- [x] Run verification:
  - `python scripts\verify_workspace.py`
  - focused server tests for diagnostic consent fix
  - focused webapp/requester tests for closure UX fix
  - focused pc_agent tests for chat ordering/layout helpers
  - rebuild agent if compiled agent behavior changed
  - deploy/release and live re-check affected tickets
  - Evidence: `verify_workspace`, focused server/webapp/agent tests, `pnpm build`, full CI artifact for commit `84f42621f801f8407c8fe70163be16d857d7600a`, remote release smoke, compiled `pc_agent.exe --verify`.
- [x] Commit each defect fix separately when practical.
  - Commit `84f4262 service-desk: fix requester confirmation and consent UX`.
- [ ] Update docs/CODEMAP only if contracts, routes, protocol, observer behavior or file ownership changed.
- Evidence: defect table, screenshots, test commands, live re-check for `#T-000508`, agent build/upload/rollout status, commit hashes.
- User attention: user should re-open `#T-000508` to confirm the visual experience if desired, and create a fresh `#T-000509`-style ticket from updated agent `3.1.29` to confirm diagnostic consent because the original ticket was created with `granted=false`.

### Stage 32B: Agent GUI Follow-Up Bugfix Gate (3 points)

- [x] Reproduce root cause from `#T-000511` live data:
  - Diagnostics: `diagnostic_autorun_skipped(reason=priority_not_allowed)` because network auto-run priority list is `P0/P1/P2` and ticket is `P3`.
  - Assignment: personal `assignee_id` is empty; support actor `op1` moved the ticket into work.
  - SLA/deadline data exists and stopped without breach, but agent detail did not explain it.
- [x] Add focused agent GUI helper regressions for consent hint, assignment fallback, deadline summary, diagnostics summary and Russian event text.
- [x] Implement scoped agent GUI fixes in `pc_agent/ui_gui/chat_panel.py`.
- [x] Run focused and relevant agent tests.
  - `python -m pytest pc_agent/tests/test_chat_panel_helpers.py pc_agent/tests/test_ticket_api_client_attachments.py::test_create_ticket_sends_diagnostic_consent -q --tb=short` passed: 63 tests.
  - `python -m py_compile pc_agent/ui_gui/chat_panel.py` passed.
  - `python scripts/verify_workspace.py` passed.
- [x] Build Windows agent `3.1.29`, run compiled `--verify`, upload and assign rollout.
  - ZIP `pc_agent-windows_amd64-3.1.29.zip`, size `98282431`, sha256 `1c761b854f4fd6e43e8afcecdb5fa8b22c3c89db12e815fe4ac5564a74e58550`.
  - Rollout policy `windows_amd64/stable` assigned to `3.1.29`.
  - Live update operation `3696e17a-dc0e-4ad7-aac7-ba884d3f4d31` succeeded; `AD-MAIN` handshake now reports `agent_version=3.1.29`.
- [U] User live re-check after `3.1.29`:
  - Create a new diagnostic-consent ticket and confirm the consent hint is obvious.
  - Open `#T-000511` or a similar ticket and confirm executor/work owner, deadlines and diagnostics are readable.
  - Resolve a ticket and confirm the confirmation card is visually obvious.
  - Confirm system timeline events are Russian and explain the actual change.

### Stage 32C: Support Playbook/Diagnostics Live Bugfix Gate (2 points)

- [x] Reproduce root cause from `#T-000512` and `#T-000513` live data:
  - Manual support playbook runs `26-29` failed quickly with `STEP_FAILED` and step errors `MODULE_NOT_ON_SERVER` for `ip_address.get_ip` / `diag.logs.collect`.
  - `network.ping` also returned `ok=false`, `MISSING_TARGET`, but operation status still displayed as `succeeded`.
  - Support UI mixed device-wide recent operations with ticket-scoped operations, making old runs look like they belonged to a new ticket.
  - Diagnostic policy auto-run for `#T-000512` referenced `diagnose.website`, but the published playbook key was not present; the skip was not recorded.
  - Requester/agent event feed exposed internal `sla_paused` / `ola_paused` noise.
- [x] Add focused regressions for playbook readiness and logical operation result display.
  - `server/tests/test_support_playbook_readiness.py` covers missing tools, missing required params and `ok=false` display.
- [x] Implement scoped fixes:
  - Support playbook payload now includes missing tools, missing required params and recent ticket playbook runs with step errors.
  - Support playbook run route blocks `PLAYBOOK_PREFLIGHT_BLOCKED` before enqueue when required tools/params are not available.
  - Ticket automation panel shows ticket playbook failures and ticket-scoped operations instead of raw device-wide history.
  - Requester/agent visibility hides SLA/OLA pause/resume internals.
  - Moving a ticket to `in_progress` from support assigns the support actor when queue rules allow it.
  - Diagnostic auto-run records `diagnostic_autorun_skipped(reason=playbook_not_published)` when a policy references a missing published playbook key.
- [x] Local verification:
  - `python -m pytest server\tests\test_support_playbook_readiness.py server\tests\test_web_support_api.py -q --tb=short` passed: 38 tests.
  - `pnpm --dir webapp exec vitest run src/pages/tickets/detail-page.test.tsx` passed: 14 tests.
  - `pnpm --dir webapp exec tsc --noEmit` passed.
  - `python -m py_compile server\web_api\support_handlers.py server\playbooks\form_triggers.py server\tickets\handlers.py pc_agent\ui_gui\chat_panel.py` passed.
- [x] Full CI/deploy/live verification:
  - `python scripts\run_ci_suite.py` produced green artifact for commit `ba68bc1fb92ace2d75e5cc7830f8b5007fb7a4bf`.
  - `python scripts\release_server_to_remote.py` deployed the commit and bundled webapp to `/var/chat_bot/pc_client`.
  - `python scripts\manage_remote_stack.py smoke server` passed after startup readiness.
  - Browser/API live check on `#T-000513` confirmed the selected broken playbook is disabled, `POST /playbooks/run` returns `409 PLAYBOOK_PREFLIGHT_BLOCKED`, and the UI shows missing `ip_address.get_ip`, `diag.logs.collect` and `network.ping.target`.
  - Browser/API live check on `#T-000512` confirmed old failed runs are visible under recent ticket playbooks with step errors.
- [U] User live re-check after deploy:
  - Open `#T-000512` / `#T-000513` or create a fresh diagnostic ticket.
  - Confirm the selected playbook is disabled with explicit missing tools/params instead of only saying "Плейбук поставлен в очередь выполнения".
  - Confirm "Операции этого тикета" no longer shows unrelated device operations.
  - Confirm SLA/OLA pause/resume no longer appears in requester/agent chat.

### Stage 33A: Passport / Evidence Functional Build-Out Plan (8 points)

Purpose: turn the current generated passport into an operator-usable official resolution dossier. The passport must show which facts are missing, where each fact can come from, how to create/link evidence, which evidence satisfies closure/reporting policy, and which parts are safe for requester/export.

Backend execution status, 2026-05-04:

- Implemented locally:
  - migration `069` extends `ticket_evidence_items` with source/fact/artifact/verification/export metadata;
  - `TicketPassportRepo.add_evidence()` is idempotent by ticket/source/fact;
  - passport generation no longer falls back to unrelated device-wide operations and can include operations linked through playbook context;
  - diagnostic-policy evidence materialization writes structured operation evidence;
  - `TicketEvidenceService` collects ticket-scoped operation/artifact candidates and links candidates into accepted evidence;
  - typed backend API now exposes `GET /api/web/support/tickets/{ticket_id}/passport/evidence-candidates` and `POST /api/web/support/tickets/{ticket_id}/passport/evidence/link`;
  - closure policy ignores rejected/archived/superseded evidence.
- Verified on Linux stand:
  - release `cd5271d` deployed with migration `069`;
  - smoke passed on `http://192.168.100.17:8666/api/health`;
  - `#T-000513` before refresh had polluted passport `source_operation_ids=10`; after refresh with the new backend it had `source_operation_ids=1` and only ticket-scoped evidence candidate `operation:8bcdf81d-167e-42d9-8c9d-2be3d0da505e`;
  - `#T-000513` evidence candidate link endpoint created accepted structured evidence `id=16` with `source_kind=operation`, `required_fact=automated_checks`, and repeated link stayed idempotent with `evidence_count=1`;
  - `#T-000512` refresh exposed 4 ticket-scoped operation candidates and did not require device-wide fallback.
- Still backend-open:
  - worklog, approval, chat-message and observer-trace candidates;
  - stale passport detection after new source/evidence changes;
  - verify/reject/archive update endpoint;
  - browser UI re-check after the later visual workspace work.

Current context and confirmed gaps:

- Data model exists but is thin:
  - `server/app/db/models.py`: `TicketResolutionPassport`, `TicketEvidenceItem`, `TicketActionLog`, `TicketApproval`, `TicketRelatedObject`.
  - `TicketEvidenceItem` currently stores only `evidence_type`, `source_ref`, `title`, `summary`, `visibility`, `created_by`, `created_at`.
  - Missing: source kind/source id normalization, artifact/file linkage, required fact linkage, verification status, captured timestamp, public/internal summaries, hash/size/mime metadata, redaction/export flags, stale status and superseded evidence.
- Service exists but mixes source quality:
  - `server/tickets/passport_service.py` generates sections and `requirements.missing_facts`.
  - `_load_operations(ticket_id, device_id)` falls back to recent device-wide operations when ticket operations are missing. Live `#T-000513` showed the result: passport had `evidenceCount=0`, `missing_facts=[]`, but `automated_checks` included device/update/no-target operations that are not clear evidence for the ticket.
  - Playbook operations linked by `PlaybookRun.context_json.ticket_id` are not first-class passport sources yet.
  - Existing chat attachments/artifacts are displayed in ticket files but are not first-class evidence candidates.
- UI exists but is not operational:
  - `webapp/src/pages/tickets/detail-page.tsx` passport tab can generate/refresh/print and shows section cards plus counts.
  - It does not show an evidence table, source previews, attach/link actions, required-fact coverage, "create evidence for this missing fact", or why a fact is accepted/rejected.
  - `webapp/src/pages/tickets/passport-print-page.tsx` prints sections and counts, not the evidence appendix.
- Policy hooks exist but need a stronger contract:
  - `server/tickets/closure_policy.py` can block on evidence, operation logs, approvals and official passport.
  - `server/tickets/diagnostic_policy.py` can materialize diagnostic operation evidence when `attach_results.as_evidence=true`.
  - `webapp/src/features/forms-builder/forms-builder-panel.tsx` already has closure/reporting/evidence policy controls, but the passport UI does not explain how those policies map to evidence actions.

Target functional model:

- Passport sections remain stable:
  - `requester`, `problem`, `affected_object`, `automated_checks`, `operator_checks`, `changes_made`, `approvals`, `evidence`, `user_result`, `internal_result`, `repeat_guidance`.
- Evidence becomes a typed dossier item:
  - `diagnostic_result`: terminal operation/playbook result.
  - `operation_log`: operation/run log or observer trace proving an action happened.
  - `screenshot` / `video` / `file_attachment`: artifact uploaded by requester/support/agent.
  - `chat_message`: public/internal message selected as proof.
  - `worklog`: operator work record.
  - `approval`: approved decision record.
  - `observer_trace`: trace/signature/degradation evidence.
  - `manual_note`: support-entered proof with no artifact.
  - `resolution_summary`: public/internal resolution text.
  - `requester_confirmation`: user's accept/reject/autoclose decision.
- Source refs must be deterministic and clickable where possible:
  - `operation:<operation_id>`
  - `playbook_run:<id>`
  - `playbook_step:<id>`
  - `event:<ticket_event_id>`
  - `artifact:<artifact_id>`
  - `approval:<id>`
  - `worklog:<id>`
  - `trace:<trace_id>`
  - `ticket:<field_name>`
- Missing facts must become actionable:
  - Each missing fact includes label, severity, required section, accepted evidence types, source candidates, recommended actions and whether it blocks closure.
  - Example: `evidence` -> actions: link completed diagnostic result, attach screenshot/file, add manual note, run safe diagnostic playbook if available.
  - Example: `user_result` -> action: fill requester-visible resolution summary in status transition or passport editor.
  - Example: `operator_checks` -> action: add worklog/internal note or link tool result.

Implementation plan:

- [x] Stage 33A.1 - Contract and schema decision.
  - Files to inspect/update: `server/app/db/models.py`, migration after `068`, `server/app/repos/ticket_passport_repo.py`, `server/web_api/dto/support.py`, `webapp/src/features/queues/api.ts`.
  - Decide whether to extend `ticket_evidence_items` in place or add `metadata_json` + indexed columns.
  - Required minimum fields:
    - `source_kind`, `source_id`, `required_fact`, `section_key`, `artifact_id`, `verification_status`, `verified_by`, `verified_at`, `captured_at`, `public_summary`, `internal_summary`, `metadata_json`, `export_visibility`.
  - Add unique/idempotency rule for `(ticket_id, evidence_type, source_kind, source_id, required_fact)` where source is present.
  - Regression tests:
    - evidence can be inserted idempotently by source;
    - artifact metadata is retained;
    - old rows without new fields still serialize.
  - 2026-05-04 backend result: migration `069`, ORM model, repo, DTO and API contract fields are in place.

- [ ] Stage 33A.2 - Evidence candidate collector.
  - Create or split into `server/tickets/evidence_service.py` instead of expanding `passport_service.py`.
  - Collect candidates from:
    - ticket-scoped `Operation.ticket_id`;
    - playbook operations through `PlaybookRun.context_json.ticket_id`;
    - `TicketEvent` chat/tool/status/passport/closure events;
    - uploaded artifacts/attachments from timeline payloads;
    - `TicketWorklog`;
    - `TicketApproval`;
    - observer root/related traces for the ticket;
    - ticket fields: requester, title, description, affected device/asset/service, resolution summaries, root cause.
  - Remove passport's device-wide operation fallback. Device-wide operations may appear only as explicit candidate suggestions with `source_quality=weak`, never as accepted evidence.
  - Regression tests:
    - `#T-000513`-style ticket with no ticket-bound operation does not import unrelated device operations;
    - playbook run operations linked by context are collected;
    - uploaded artifacts are offered as candidates.
  - 2026-05-04 backend slice complete for ticket-scoped operations, playbook-context operations and artifacts. Worklog, approval, chat-message and observer-trace candidates remain open.

- [ ] Stage 33A.3 - Missing fact engine.
  - Extend `_build_passport_requirements()` into a policy-aware fact coverage engine.
  - Output shape should include:
    - `required_fact`, `section_key`, `source`, `current_value`, `requester_visible_label`, `severity`;
    - `accepted_evidence_types`;
    - `candidate_count`;
    - `recommended_actions`;
    - `blocking_for_closure`;
    - `satisfied_by_evidence_ids`.
  - Applicability rules:
    - `automated_checks` blocks only if module/playbook/tool use is expected or actually happened.
    - `approvals` blocks only if approval policy was used or an approval exists.
    - `evidence` blocks when reporting/closure policy requires it, priority requires it, or an official passport requires evidence.
    - `user_result` may be satisfied by the current resolve transition public summary.
  - Regression tests:
    - non-applicable automated/approval sections are warnings, not closure blockers;
    - missing evidence gives actionable recommended actions;
    - transition summaries satisfy `user_result` during resolve.

- [ ] Stage 33A.4 - Evidence creation/linking API.
  - Extend `POST /api/web/support/tickets/{ticket_id}/passport/evidence`.
  - Add endpoints if cleaner:
    - `GET /api/web/support/tickets/{ticket_id}/passport/evidence-candidates`;
    - `POST /api/web/support/tickets/{ticket_id}/passport/evidence/link`;
    - `PATCH /api/web/support/tickets/{ticket_id}/passport/evidence/{evidence_id}`;
    - optional `DELETE`/archive endpoint with audit, not hard delete.
  - Actions must support:
    - create manual evidence;
    - link existing operation/playbook step/trace/message/worklog/approval/artifact;
    - attach evidence to a required fact;
    - mark evidence public/internal/export-hidden;
    - verify/reject evidence with reason.
  - RBAC:
    - create/link/verify requires `ticket.passport.manage`;
    - read is allowed to support/admin/auditor;
    - requester-safe projection must never expose internal evidence unless policy says so.
  - Events:
    - write `passport_evidence_added`, `passport_evidence_linked`, `passport_evidence_verified`, `passport_evidence_rejected`, `passport_evidence_archived`.
  - 2026-05-04 backend slice complete for create manual evidence, candidate listing and source linking. Verify/reject/archive update endpoints remain open.

- [ ] Stage 33A.5 - Passport generation and stale detection.
  - `TicketPassportService.generate()` must:
    - materialize diagnostic/playbook evidence only from ticket-linked sources;
    - generate sections from structured accepted evidence where available;
    - preserve manual section edits separately from generated text;
    - mark passport `stale=true` when source events/operations/evidence changed after generation;
    - store source coverage in `source_payload.source_counts`.
  - `TicketPassportRepo.update_passport_sections()` should support all editable sections or a controlled subset with clear payload names.
  - Regression tests:
    - refresh creates new version and previous manual edits are either carried forward or explicitly marked superseded;
    - stale flag changes after new evidence/action;
    - generated evidence section lists evidence titles/source refs, not just a count.

- [ ] Stage 33A.6 - Closure policy integration.
  - Update `server/tickets/closure_policy.py` so closure checks use the same fact coverage/evidence service as the UI.
  - The support status panel must receive a precise closure checklist:
    - missing public summary;
    - missing internal summary;
    - missing evidence for priority;
    - missing operation log because module/playbook was used;
    - missing approved approval;
    - missing official passport or stale passport.
  - Regression tests:
    - closure block message includes the exact missing fact keys;
    - accepted evidence unblocks closure;
    - rejected/archived evidence does not unblock closure.
  - 2026-05-04 backend slice complete for rejected/archived/superseded evidence exclusion. Exact support-panel message wiring remains open.

- [ ] Stage 33A.7 - Support UI passport redesign inside current workspace.
  - Modify `webapp/src/pages/tickets/detail-page.tsx` and focused tests.
  - Required UI blocks:
    - top status: `missing/draft/stale/ready/blocking`;
    - "Чего не хватает" checklist with action buttons per fact;
    - "Доказательства" table/cards with type, source, linked fact, status, visibility, created_by, created_at;
    - "Кандидаты" drawer: operations, playbook runs/steps, files, messages, approvals, worklogs, observer traces;
    - manual evidence form;
    - section editor for user/internal result, operator checks, changes made, repeat guidance;
    - export visibility preview;
    - print/PDF with evidence appendix.
  - UX rules:
    - no raw `ticket_evidence_items` as the main user label;
    - Russian labels must be clear and mojibake-free;
    - no "hung" state: every loading/candidate/generate action must have success/error/empty state.
  - Frontend tests:
    - renders missing facts with action buttons;
    - links candidate evidence;
    - shows stale passport warning;
    - print page includes evidence appendix.

- [ ] Stage 33A.8 - Forms builder/reporting policy mapping.
  - Keep current low-code redesign deferred, but make existing policy controls honest.
  - Files: `webapp/src/features/forms-builder/forms-builder-panel.tsx`, `server/web_api/admin_handlers.py`, `server/tickets/helpdesk_policy_runtime.py`.
  - Ensure reporting policy can define:
    - required sections;
    - required evidence types per section;
    - export hidden sections;
    - whether official passport is required before resolve/close;
    - knowledge draft hints;
    - requester-visible evidence policy.
  - Add validation so policy cannot require unsupported evidence types without warning.

- [ ] Stage 33A.9 - Agent/requester evidence path.
  - Agent-created ticket attachments already upload artifacts; plan must link those artifacts as evidence candidates.
  - Public/requester chat attachments should also become candidates, but not accepted evidence automatically unless policy allows requester-provided evidence.
  - Agent GUI should not need full passport management now, but ticket detail should show whether evidence is needed and which uploaded files may satisfy it.
  - Tests: `pc_agent/tests/test_chat_panel_helpers.py` for evidence-needed copy and attachment refs.

- [ ] Stage 33A.10 - Observer and audit.
  - Update observer docs if evidence uses observer traces as proof.
  - Add trace correlation for evidence link/verify events where possible.
  - Evidence source provenance must be inspectable from support UI and API.
  - Docs to update:
    - `docs/QUICK_LOOKUP.md`;
    - `server/docs/CODEMAP.md`;
    - `server/docs/DIAGNOSTIC_PLAYBOOKS.md`;
    - `server/docs/OBSERVER_LAYER.md` if observer traces become evidence sources;
    - `scripts/navigation_catalog.py`.

Verification plan:

- Local tests:
  - `python scripts\verify_workspace.py`
  - `python -m pytest server\tests\test_ticket_passport_service.py server\tests\test_ticket_closure_policy.py server\tests\test_web_support_api.py -q --tb=short`
  - new `server\tests\test_ticket_evidence_service.py -q --tb=short`
  - `pnpm --dir webapp exec vitest run src/pages/tickets/detail-page.test.tsx src/pages/tickets/passport-print-page.test.tsx`
  - `pnpm --dir webapp run build`
- Live checks:
  - Open `#T-000512`: generate passport and confirm failed playbook runs can be linked as evidence or shown as rejected/failed evidence candidates.
  - Open `#T-000513`: confirm unrelated device-wide operations no longer appear as accepted automated checks.
  - Create a fresh diagnostic ticket with consent and at least one attachment; confirm attachment and diagnostic result appear as evidence candidates.
  - Try resolve before evidence: support UI and server must show exact missing facts.
  - Link evidence and resolve: closure must pass.
  - Print passport: evidence appendix must include source refs and visibility/export status.

User attention checks for this stage:

- Confirm the business wording of passport sections: whether `changes_made`, `operator_checks`, `internal_result` and `user_result` are the right names for your support process.
- Confirm which evidence types are acceptable for official closure: screenshot, video, diagnostic result, worklog, approval, observer trace, requester confirmation.
- Confirm which evidence can be visible to the requester and which must remain internal.
- Confirm whether official passport should be required before `resolved`, before `closed`, or only for selected priorities/types.

### Stage 33: Cleanup, Final Evidence And Score (4 points)

- [ ] Generate `artifacts/live_checks/service_desk_live_acceptance_YYYYMMDD.md`.
- [ ] Generate `artifacts/live_checks/service_desk_live_acceptance_YYYYMMDD.json`.
- [ ] List all created disposable templates, policies, smart views, tickets and artifacts.
- [ ] Decide cleanup strategy: keep tickets as evidence, deactivate disposable templates, remove temporary preferred pack entries if created.
- [ ] Run cleanup or deactivation through supported API/scripted path only.
- [ ] Re-run `python scripts\manage_remote_stack.py smoke server`.
- [ ] Browser re-check `/app/tickets` and `/app/admin/forms`.
- [ ] Stop remote server with `python scripts\manage_remote_stack.py stop server` unless user asked to leave it running.
- [ ] Confirm stopped through status.
- [ ] Run final `git status --short`.
- [ ] Update this plan with completion percentage, passed stages, defects found, blocked items, user-attention checks and final system maturity estimate.
- Evidence: final summary files, cleanup result, stopped status.
- User attention: user must review any remaining `[U]` item before final confidence can be called complete.

### Deferred Stage 34: Support Workspace Visual Redesign Plan (not part of current bugfix gate)

Start only after Stage 32 is fixed and rechecked.

- [ ] Inventory all existing support workspace elements that must survive redesign:
  - queue/list, filters, smart views and unread counters;
  - ticket identity, requester, device, queue, assignee, status and priority;
  - public chat, internal notes, worklog and attachments;
  - workflow transitions, blocked transition reasons and closure requirements;
  - SLA, OLA, risk/breach/paused/stopped facts;
  - approvals and current approver state;
  - diagnostics/playbooks, required tools, consent state and operations;
  - observer trace, audit/history/timeline and passport/reporting;
  - requester-safe/public projection and close/confirm state.
- [ ] Write a separate redesign spec before implementation:
  - target layout: sticky ticket header, central chat, right process sidebar, action bar;
  - operator task model: triage, diagnose, ask user, wait, resolve, close;
  - responsive behavior for desktop and narrow screens;
  - permission/RBAC disabled states and dangerous action confirmations.
- [ ] Build mock-first or behind a feature branch; do not mix this with live bug fixes.
- [ ] Verify with Playwright screenshots and real live tickets after implementation.

### Deferred Stage 35: Low-Code Form Constructor Redesign Plan (not part of current bugfix gate)

Start only after Stage 32 is fixed and after the support workspace redesign direction is accepted.

- [ ] Inventory existing forms-builder capabilities that must survive redesign:
  - fields, field types, required rules, conditional visibility and process mapping;
  - request template publication and form schema versions;
  - workflow, priority, routing, SLA, OLA, approval, diagnostic, closure, visibility, notification and reporting policies;
  - policy diff, rollback, deactivate and publish impact preview;
  - smart views and requester-safe visibility settings.
- [ ] Redesign as low-code blocks:
  - `Form Fields` block;
  - `Visibility Conditions` block;
  - `Workflow` block;
  - `Priority And Routing` block;
  - `SLA/OLA` block;
  - `Approval` block;
  - `Diagnostics And Playbooks` block;
  - `Closure And Passport` block;
  - `Requester Visibility` block;
  - `Publish And Validate` block.
- [ ] Reuse the existing playbook-builder mental model where useful: palette, canvas, selected block inspector, validation summary and preview.
- [ ] Keep JSON advanced mode as an escape hatch, not as the primary UI.
- [ ] Verify with live publish/edit/rollback on disposable templates only.

## Verification Matrix

Minimum local command set before final completion claim:

```powershell
.\scripts\bootstrap_shell_utf8.ps1
python scripts\verify_workspace.py
python scripts\docs_inventory.py --check-links
python scripts\bootstrap_web_toolchain.py
python -m pytest server\tests\test_web_settings_api.py server\tests\test_web_support_api.py server\tests\test_ticket_workflow_profiles.py server\tests\test_ticket_approval_policy.py server\tests\test_ticket_notification_policy.py server\tests\test_ticket_visibility_policy.py server\tests\test_ticket_passport_service.py server\tests\test_ticket_closure_policy.py server\tests\test_helpdesk_policy_registry.py -q --tb=short
python -m pytest pc_agent\tests\test_chat_panel_helpers.py pc_agent\tests\test_ticket_api_client_attachments.py -q --tb=short
pnpm --dir webapp test src\pages\settings\index.test.tsx src\features\forms-builder\forms-builder-panel.test.tsx src\pages\tickets\detail-page.test.tsx src\pages\tickets\list-page.test.tsx
python scripts\release_server_to_remote.py --allow-local-dirty --skip-ci-check --leave-running --smoke-attempts 5 --smoke-delay 3
python scripts\manage_remote_stack.py smoke server
```

Minimum browser/live paths before final completion claim:

```text
http://192.168.100.17:8666/admin
http://192.168.100.17:8666/app/admin/forms
http://192.168.100.17:8666/app/settings
http://192.168.100.17:8666/app/tickets
http://192.168.100.17:8666/app/tickets/:ticketId
http://192.168.100.17:8666/app/admin/observer
http://192.168.100.17:8666/app/admin/access
http://192.168.100.17:8666/app/admin/playbooks
```

Minimum live scenario coverage before final completion claim:

- request template settings create/edit/reload
- form conditional fields and process mapping
- ticket create from server/API
- ticket create from browser/requester path
- ticket create from agent GUI
- workflow happy path
- workflow negative gates
- priority compute and manual override
- routing and diagnostic rerouting
- SLA start/pause/resume/stop/warning/breach
- OLA start/pause/stop/risk
- approval approve/reject/timeout-visible path where practical
- diagnostics with consent
- observer trace and agent action correlation
- notification recipient/action audit
- visibility/requester-safe projection
- smart views and queue counts
- closure blocking and successful passport
- RBAC negative cases
- browser UX/console signoff
- cleanup/deactivation

## Current State

- Implementation/hardening plan is complete and committed.
- Latest known plan/tooling commit before the live plan: `30e1db8 scripts: add local context index workflow`.
- Generated live/browser/diagnostic/release artifacts are ignored through `.gitignore`.
- Stages 0-31 are verified, but user live QA reopened the active gate with concrete defects in requester closure UX, diagnostic consent, agent chat ordering and agent GUI layout.
- Stage 32 is now the current execution stage and must be completed before Stage 33 cleanup/final score.
- Support workspace visual redesign and low-code form constructor redesign are explicitly deferred to Stages 34-35 and must not be mixed with the current bugfix gate.
- Current open user-attention risks and confirmed user checks are listed in `User Attention Checks`.

## Handoff

Recommended execution order is strict:

1. Stages 0-7 prove the workspace, context, remote stand, browser baseline, actor model and fixture design.
2. Stages 8-13 publish the disposable service desk model and negative settings validation.
3. Stages 14-22 exercise ticket creation, policy snapshots, workflow, priority/routing, SLA/OLA and approvals.
4. Stages 23-30 exercise diagnostics, observer, notifications, visibility, smart views, closure/passport, agent GUI and security.
5. Stage 31 performs final browser UX and console signoff.
6. Stage 32 fixes current user-reported live defects: `#T-000508`, `#T-000509`, agent chat ordering and agent GUI layout.
7. Stage 33 summarizes evidence, cleans/deactivates disposable entities, stops the server and updates the final score.
8. Stages 34-35 are deferred redesign planning tracks for support workspace and low-code form constructor; start them only after the current bugfix gate is closed.

Do not skip cleanup/evidence summary. Without a clear created-entity list, the live test campaign is not complete.
