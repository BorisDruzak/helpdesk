# Service Desk Live Acceptance Test Plan

> For agentic workers: use `superpowers:executing-plans` for each slice and keep this file current after every verified checkpoint. This is the active long-horizon plan for live testing the full configurable service desk model in `pc_client`.

## Status

Created: 2026-05-03.

Last updated: 2026-05-03, initial live acceptance plan.

Current plan completion: 0.0%.

This plan replaces the completed service-desk hardening plan. The previous implementation and hardening work is treated as complete. This plan is only for live acceptance testing, evidence gathering, defect isolation and final confidence scoring across the whole ticket system.

## Goal

Verify in live conditions that the full service desk model works end to end on real tickets and real settings: request templates, dynamic forms, workflow, priority, SLA, OLA, routing, approvals, diagnostics, notifications, visibility, smart views, closure rules, passport/reporting, agent GUI create flow, observer traces and RBAC.

## Success Criteria

The live test campaign is complete only when all of these are true:

- A disposable but realistic set of request templates and policies is created on the remote stand.
- Tickets are created through server UI/API and agent GUI paths.
- Each ticket keeps the expected template, schema and policy snapshot.
- Workflow transitions enforce required fields, comments, evidence and role gates.
- Priority, routing, SLA and OLA decisions are visible, deterministic and auditable.
- SLA/OLA timers, warning/risk/breach views and pause/resume/stop behavior are verified on live tickets.
- Approvals work through approve, reject and timeout/escalation-visible paths.
- Diagnostics run as operations separate from ticket status and attach results to timeline/passport/observer.
- Closure policy blocks incomplete important tickets and allows closure when required facts are present.
- Requester-visible projections hide internal fields, OLA internals, raw diagnostics and internal notes.
- Notification recipient/action previews and audit records match the configured policies.
- Smart views show the right slices and do not behave like ownership queues.
- Agent GUI can create a ticket from current published templates and display a requester-safe result.
- Observer layer shows trace roots, spans and operation lifecycle without trace-visible gaps.
- Browser checks on `http://192.168.100.17:8666/admin` and relevant `/app/*` routes show no active-tab console errors.
- Generated artifacts are stored under ignored `artifacts/*` folders and not committed.
- Remote server is stopped at the end unless the user explicitly asks to leave it running.

## Scope

### In Scope

- Remote live stand:
  - `http://192.168.100.17:8666/admin`
  - `/app/admin/forms`
  - `/app/settings`
  - `/app/tickets`
  - `/app/tickets/:ticketId`
  - `/app/admin/observer`
  - `/help` if requester portal behavior is involved

- Server domains:
  - `server/tickets/*`
  - `server/web_api/settings_handlers.py`
  - `server/web_api/support_handlers.py`
  - `server/web_api/admin_handlers.py`
  - `server/observer/*`
  - `server/tools/*`
  - `server/app/repos/*`

- Agent domains:
  - `pc_agent/ui_gui/*`
  - `pc_agent/ui_bridge/*`
  - `pc_agent/ws_agent.py`
  - `pc_agent/core/orchestrator.py`
  - `pc_agent/core/action_trace.py`

- Webapp:
  - `webapp/src/pages/settings/index.tsx`
  - `webapp/src/pages/tickets/list-page.tsx`
  - `webapp/src/pages/tickets/detail-page.tsx`
  - `webapp/src/features/forms-builder/*`
  - relevant typed API clients under `webapp/src/features/*`

- Scripts and artifacts:
  - `scripts/verify_workspace.py`
  - `scripts/bootstrap_web_toolchain.py`
  - `scripts/release_server_to_remote.py`
  - `scripts/manage_remote_stack.py`
  - `scripts/run_observer_canary_suite.py`
  - `scripts/helpdesk_data_cleanup.py`
  - `artifacts/live_checks/`
  - `artifacts/browser_checks/`
  - `artifacts/observer_canaries/`
  - `artifacts/diagnostics/`

### Out Of Scope

- New product features unless a live test exposes a blocking defect.
- Manual DB edits outside project scripts or controlled API calls.
- Permanent production-like seed data.
- Changing historical tickets except through an explicit cleanup slice.
- Publishing generated artifacts to Git.

## Constraints

- Work only in `C:\Users\admin-2\CodexProjects\pc_client`.
- Do not edit `\\192.168.100.17\NTFS_Share\pc_client` directly.
- Use remote Linux copy `/var/chat_bot/pc_client` only as deploy/live stand.
- Use project scripts for deploy and lifecycle.
- Use Browser Canon: browser checks only against `http://192.168.100.17:8666/admin` and linked `/app/*` routes.
- For webapp commands, first run `python scripts/bootstrap_web_toolchain.py`.
- Do not expose raw tokens or secrets in artifacts.
- Prefix all disposable live entities with `codex-live-acceptance-20260503`.
- Every created ticket/template/policy must be listed in the live evidence summary for cleanup.
- Do not commit generated artifacts.
- If defects are found, isolate them with focused tests before code changes where realistic.

## Decisions

- The campaign tests the whole system as a process engine, not individual isolated widgets.
- Disposable live settings are preferred over mutating existing operator templates.
- Every live ticket must be tied to an explicit scenario id.
- Evidence is more important than volume. A smaller number of carefully traced tickets is better than many weak smoke checks.
- API checks verify data contracts; browser checks verify operator/requester usability; observer checks verify traceability.
- Agent GUI live checks are required for at least one current preferred template and one schema-backed disposable template.
- Cleanup is a planned final slice, but test artifacts may remain until evidence is summarized.

## Test Data Model

Use these scenario ids and names:

- `codex-live-acceptance-incident-website`
  - Ticket type: `incident`
  - Request template: "Live: Не открывается сайт"
  - Diagnostics: website/DNS style playbook, consent required
  - Expected policy chain: form, workflow, priority, routing, SLA, OLA, diagnostics, closure, visibility, notification

- `codex-live-acceptance-access`
  - Ticket type: `access_request`
  - Request template: "Live: Нужен доступ к системе"
  - Approval required
  - Diagnostics disabled
  - Expected policy chain: form, workflow, priority, routing, SLA, approval, closure, visibility, notification

- `codex-live-acceptance-consultation`
  - Ticket type: `consultation`
  - Request template: "Live: Консультация по рабочему месту"
  - Simple workflow
  - No OLA escalation requirement
  - Expected policy chain: form, workflow, routing, SLA, closure, visibility

- `codex-live-acceptance-change`
  - Ticket type: `change_request`
  - Request template: "Live: Изменение конфигурации"
  - Approval and scheduled state required
  - Expected policy chain: form, workflow, priority, routing, SLA/OLA, approval, closure, reporting

Minimum live ticket set:

- `T-LIVE-01`: incident website, normal path with diagnostics and successful closure.
- `T-LIVE-02`: incident website, high impact/urgency path with P0/P1 SLA/OLA risk.
- `T-LIVE-03`: access request, approve path.
- `T-LIVE-04`: access request, reject path with required rejection comment.
- `T-LIVE-05`: consultation, requester reply and waiting_user pause/resume path.
- `T-LIVE-06`: change request, scheduled/waiting_approval path.
- `T-LIVE-07`: invalid/negative ticket create or transition attempt for validation/RBAC evidence.
- `T-LIVE-08`: agent GUI-created ticket using current published template.

## Evidence Artifacts

Write only generated evidence into ignored artifact folders:

- `artifacts/live_checks/service_desk_live_acceptance_YYYYMMDD.json`
- `artifacts/live_checks/service_desk_live_acceptance_YYYYMMDD.md`
- `artifacts/browser_checks/live-acceptance/`
- `artifacts/observer_canaries/live-acceptance/`
- `artifacts/diagnostics/live_acceptance_logs_YYYYMMDD.txt`

Evidence summary must include:

- branch and commit hash
- deploy command and result
- remote health result
- created templates/policies ids and versions
- created ticket ids
- scenario id per ticket
- expected vs actual policy chain
- SLA/OLA timer facts
- workflow transition facts
- approval facts
- diagnostic operation ids and trace ids
- closure/passport facts
- browser paths checked
- console errors count
- defects found, with severity and reproduction command
- cleanup status

## Slice 0: Baseline, Context And Live Stand Readiness

- [ ] Run intake and context retrieval:
  - `python scripts/task_intake.py --task "live acceptance test full service desk tickets settings SLA OLA approvals diagnostics observer agent GUI"`
  - `python scripts/build_context_pack.py --topic "live acceptance test full service desk tickets settings SLA OLA approvals diagnostics observer agent GUI"`
  - `python scripts/search_context_index.py "request_template workflow_profile sla_policy ola_policy approval_policy diagnostic_policy closure_policy observer"`
- [ ] Read canonical docs:
  - `AGENTS.md`
  - `docs/CODEX_WORKFLOW.md`
  - `docs/ARCHITECTURE_BOUNDARIES.md`
  - `docs/CONTEXT_INDEX.md`
  - `docs/QUICK_LOOKUP.md`
  - `server/docs/CODEMAP.md`
  - `pc_agent/docs/CODEMAP.md`
  - `server/docs/TICKET_SYSTEM.md`
  - `server/docs/OBSERVER_LAYER.md`
  - `server/docs/OBSERVER_AUTHORING_RULES.md`
- [ ] Confirm git state is suitable:
  - `git status --short`
  - Expected: clean or only intentional plan changes.
- [ ] Run local baseline:
  - `python scripts/verify_workspace.py`
  - `python scripts/docs_inventory.py --check-links`
- [ ] Bootstrap web toolchain:
  - `python scripts/bootstrap_web_toolchain.py`
- [ ] Run focused local test baseline:
  - `python -m pytest server\tests\test_web_settings_api.py server\tests\test_web_support_api.py server\tests\test_ticket_workflow_profiles.py server\tests\test_ticket_approval_policy.py server\tests\test_ticket_notification_policy.py server\tests\test_ticket_visibility_policy.py server\tests\test_ticket_passport_service.py server\tests\test_ticket_closure_policy.py server\tests\test_helpdesk_policy_registry.py -q --tb=short`
  - `python -m pytest pc_agent\tests\test_chat_panel_helpers.py pc_agent\tests\test_ticket_api_client_attachments.py -q --tb=short`
  - `pnpm --dir webapp test src\pages\settings\index.test.tsx src\features\forms-builder\forms-builder-panel.test.tsx src\pages\tickets\detail-page.test.tsx src\pages\tickets\list-page.test.tsx`
- [ ] Deploy verified state to remote:
  - `python scripts\release_server_to_remote.py --allow-local-dirty --skip-ci-check --leave-running --smoke-attempts 5 --smoke-delay 3`
- [ ] Confirm remote health:
  - `python scripts\manage_remote_stack.py status control`
  - `python scripts\manage_remote_stack.py smoke server`
- [ ] Open browser baseline:
  - `/admin`
  - `/app/admin/forms`
  - `/app/settings`
  - `/app/tickets`
  - `/app/admin/observer`
- [ ] Record baseline evidence and any existing operational noise.

## Slice 1: Live Settings Fixture Creation

- [ ] Inventory existing published request templates and policy registry through API/UI.
- [ ] Confirm disposable ids do not already exist.
- [ ] Create or publish `codex-live-acceptance-incident-website` request template:
  - classification: `incident`, category `network`, subcategory `website_unavailable`
  - form fields: URL, affected scope, started at, error text, screenshot/file, workaround available, consent
  - workflow: incident default with waiting_user, waiting_internal, resolved, closed
  - priority: impact/urgency matrix and manual override reason required
  - SLA: first response and resolution targets by P0-P3
  - OLA: queue ack and processing targets
  - routing: L1 fallback, networks for DNS/connectivity, systems for HTTP 500, security/servers for TLS
  - diagnostics: suggested website/DNS playbook, consent required
  - closure: resolution code, public summary and evidence for P0/P1
  - visibility: requester-safe status mapping, hide OLA/raw diagnostics/internal notes
- [ ] Create or publish `codex-live-acceptance-access` request template:
  - classification: `access_request`
  - form fields: system, role, business reason, manager, desired date
  - approval: service owner or manager, reject comment required
  - diagnostics disabled
  - closure requires approval and action log
- [ ] Create or publish `codex-live-acceptance-consultation` request template:
  - classification: `consultation`
  - simpler form and workflow
  - requester reply path required
- [ ] Create or publish `codex-live-acceptance-change` request template:
  - classification: `change_request`
  - scheduled status and approval step
  - closure/reporting requires change outcome summary
- [ ] Validate settings reload:
  - refresh `/app/admin/forms`
  - refresh `/app/settings`
  - confirm every disposable template remains active or draft according to scenario
- [ ] Negative settings validation:
  - invalid form field mapping fails
  - invalid workflow transition fails
  - invalid SLA/OLA target/calendar shape fails
  - invalid approval approver source fails
  - invalid routing loop or unsupported path fails
- [ ] Record policy ids, versions, active flags and screenshots.

## Slice 2: Request Form And Ticket Creation Acceptance

- [ ] Create `T-LIVE-01` through server/API using incident website template.
- [ ] Create `T-LIVE-02` through server/API using high impact/urgency incident values.
- [ ] Create `T-LIVE-03` through server/API using access request approve path.
- [ ] Create `T-LIVE-04` through server/API using access request reject path.
- [ ] Create `T-LIVE-05` through requester/server path using consultation template.
- [ ] Create `T-LIVE-06` through server/API using change request template.
- [ ] Verify each created ticket stores:
  - request template id and version
  - form schema id and version
  - workflow profile id
  - priority policy id
  - routing policy id
  - SLA policy id
  - OLA policy id if applicable
  - approval policy id if applicable
  - diagnostic policy id if applicable
  - closure policy id
  - visibility/notification policy ids
- [ ] Verify dynamic form behavior:
  - hidden conditional fields are not required
  - visible conditional fields become required
  - file fields and picker fields preserve values
  - process_mapping feeds impact/urgency/routing/diagnostic params
- [ ] Verify requester-safe response:
  - access code visible
  - next action visible
  - expected response/resolution due dates visible
  - no raw SLA/OLA/internal policy ids in requester text
- [ ] Negative create tests:
  - missing required field rejected
  - invalid select option rejected
  - inactive template unavailable
  - old `form_key` compatibility still works if applicable
- [ ] Record ticket ids and raw API snippets in evidence.

## Slice 3: Workflow Transition And Status Acceptance

- [ ] For `T-LIVE-01`, run happy-path incident workflow:
  - `new -> queued`
  - `queued -> assigned`
  - `assigned -> in_progress`
  - `in_progress -> waiting_user`
  - requester reply triggers or allows `waiting_user -> in_progress`
  - `in_progress -> resolved`
  - requester confirmation or autoclose path to `closed`
- [ ] Verify transition gates:
  - `queued -> assigned` requires queue/assignee
  - `in_progress -> waiting_user` requires public question
  - `in_progress -> resolved` requires resolution code and public summary
  - `resolved -> closed` follows closure policy
- [ ] For `T-LIVE-06`, verify change workflow:
  - scheduled state is reachable only through allowed transition
  - waiting approval state uses approval policy
  - rejected approval cannot move to resolved without correction
- [ ] Verify status projection:
  - internal status can differ from public status
  - requester sees "Заявка в работе" style public mapping, not internal queue details
- [ ] Verify audit/timeline:
  - old status
  - new status
  - actor
  - reason/comment
  - required fields snapshot
  - configured action markers
- [ ] Negative transition tests:
  - wrong role denied
  - missing required comment denied
  - missing evidence denied for priority where required
  - invalid transition denied
- [ ] Record transition matrix evidence.

## Slice 4: Priority, Routing And Queue Acceptance

- [ ] Verify `T-LIVE-01` computed priority from impact/urgency.
- [ ] Verify `T-LIVE-02` escalates to P0/P1 according to configured high impact/urgency and modifiers.
- [ ] Verify stored priority fields:
  - impact
  - urgency
  - importance if present
  - computed_priority
  - manual_priority
  - effective_priority
  - priority_source
  - priority_reason
- [ ] Test manual priority override:
  - allowed support/lead/admin role can override with reason
  - override without reason rejected
  - requester role cannot override
  - audit contains previous and new priority
- [ ] Verify initial routing:
  - default queue applied when no rule matches
  - incident website high impact routes to expected queue
  - access request routes to access/service-owner queue
- [ ] Verify rerouting by diagnostic result:
  - DNS failure moves/suggests networks
  - HTTP 500 moves/suggests information systems
  - TLS error moves/suggests security/servers
- [ ] Verify anti-loop constraints:
  - max auto reroutes honored
  - manually locked assignee prevents automatic reroute
  - reroute after manual assignment requires reason or is skipped/audited
- [ ] Verify support list and ticket detail show queue/assignee/routing reason.
- [ ] Record queue state and routing decision facts.

## Slice 5: SLA And OLA Timer Acceptance

- [ ] Verify SLA starts at ticket creation for each scenario where enabled.
- [ ] Verify first response SLA stops at first public support reply.
- [ ] Verify resolution SLA stops at resolved/closed.
- [ ] Verify waiting statuses pause/resume:
  - `waiting_user` pauses SLA/OLA where configured
  - requester reply resumes
  - `waiting_approval` pauses where configured
  - approval resumes
  - `waiting_vendor` behavior follows configured external wait flag
- [ ] Verify calendar behavior:
  - 5x8 calendar excludes non-working time
  - 24x7 calendar behaves continuously if configured
  - calendar JSON warning from previous cleanup does not reappear as a live blocker
- [ ] Verify OLA starts on queue assignment and queue change.
- [ ] Verify OLA ack stops on assignee set or in_progress.
- [ ] Verify OLA processing stops on queue change, resolved, closed or handoff.
- [ ] Verify warning and breach actions:
  - warning timestamps are computed
  - warning recipients are resolved
  - breach event/audit created
  - escalation action is outside event payload
- [ ] Verify UI:
  - SLA risk smart view includes near-breach ticket
  - OLA risk smart view includes queue-risk ticket
  - ticket detail shows internal support timer details
  - requester view shows only safe due information
- [ ] Record timer snapshots before and after transitions.

## Slice 6: Approval Policy Acceptance

- [ ] For `T-LIVE-03`, verify access approval creation:
  - approver source resolved
  - current approver visible to support
  - requester-safe waiting approval status visible
  - due/reminder/escalation timestamps visible
- [ ] Approve `T-LIVE-03`:
  - approval audit recorded
  - transition moves to configured status
  - notification action generated
  - passport includes approval evidence
- [ ] For `T-LIVE-04`, reject approval:
  - reject without comment rejected
  - reject with comment accepted
  - ticket moves to configured reject transition
  - requester-safe rejection text does not expose internal policy internals
- [ ] Verify approval modes where available:
  - any_one
  - all
  - sequential if configured
- [ ] Verify timeout/escalation visibility:
  - reminder event/audit visible
  - escalation recipient/action visible
  - no hidden silent failure for unavailable external channel
- [ ] Verify RBAC:
  - non-approver cannot approve
  - support/admin visibility differs from requester visibility
- [ ] Record approval lifecycle facts.

## Slice 7: Diagnostics, Modules And Observer Acceptance

- [ ] For `T-LIVE-01`, run suggested diagnostic playbook with consent.
- [ ] Verify consent:
  - required before requester-device/high-risk tool
  - consent decision stored
  - denied consent blocks auto-run or high-risk step
- [ ] Verify operation model:
  - ticket status remains `in_progress` or configured workflow status
  - operation status moves through queued/running/succeeded/failed
  - operation id is stable and visible
- [ ] Verify observer trace:
  - root trace exists
  - operation spans exist
  - module/tool entry breadcrumb exists
  - command/result correlation exists
  - dangerous flow, if any, is visible in observer
- [ ] Verify diagnostic result attachment:
  - timeline event created
  - passport evidence created when configured
  - raw diagnostic hidden from requester if visibility policy says so
  - support can inspect raw/internal diagnostic facts
- [ ] Verify reroute by diagnostic result.
- [ ] Run observer canary suite if relevant:
  - `python scripts\run_observer_canary_suite.py`
- [ ] Browser check `/app/admin/observer`:
  - runtime status ok
  - trace visible
  - no active-tab console errors
- [ ] Record trace ids, operation ids and screenshots.

## Slice 8: Notification, Recipient Actions And Visibility Acceptance

- [ ] Verify notification policy events:
  - created
  - assigned
  - waiting_user
  - requester_replied
  - SLA warning
  - SLA breach
  - OLA warning/breach if configured
  - approval created/approved/rejected
  - diagnostic completed/failed
  - resolved
  - closed
- [ ] Verify recipient resolution:
  - requester
  - assignee
  - queue
  - queue lead
  - admin if configured
  - watchers if configured
  - external groups or provider channels if configured
- [ ] Verify external delivery action model:
  - escalation/recipient actions are represented outside event payload
  - disabled/unavailable channels leave audit evidence
  - per-recipient preferences remain final filter
- [ ] Verify visibility policy:
  - public status mapping
  - requester cannot see internal_notes
  - requester cannot see OLA details
  - requester cannot see raw diagnostics
  - requester cannot see internal queue comments
  - support can see support-safe internal detail
  - passport export obeys visibility rules
- [ ] Browser check previews:
  - settings/form builder requester/support preview
  - ticket detail requester-safe vs support-safe fields where available
- [ ] Record recipient/action and visibility evidence.

## Slice 9: Smart Views And Support Queue Acceptance

- [ ] Verify built-in smart views:
  - SLA risk
  - OLA risk
  - unassigned
  - requester replied
  - stale waiting
  - waiting approval
  - diagnostics failed
  - mass incident candidates
- [ ] Verify smart views are saved filters, not ownership queues.
- [ ] Verify custom smart view publication:
  - valid filter accepted
  - invalid filter rejected with actionable message
  - sort order applied
  - counts match list results
- [ ] Verify support ticket list:
  - filter by status
  - filter by queue
  - filter by priority
  - filter by due/risk
  - search by access code/title/requester where supported
- [ ] Verify queue counters do not include closed/canceled unless configured.
- [ ] Browser check `/app/tickets`:
  - switch views
  - open ticket from smart view
  - back navigation keeps context where expected
  - console errors 0
- [ ] Record list screenshots and API count facts.

## Slice 10: Closure, Passport And Reporting Acceptance

- [ ] Attempt to close `T-LIVE-02` without required P0/P1 evidence:
  - expected: blocked
  - missing facts report visible
  - requester-safe label available
  - blocking severity clear
- [ ] Add required facts:
  - resolution code
  - public summary
  - internal summary if required
  - diagnostic evidence
  - approval evidence if used
  - operation log if module used
  - worklog if required
- [ ] Resolve and close:
  - transition succeeds
  - SLA/OLA stop correctly
  - closure audit recorded
  - passport includes solution summary and evidence
- [ ] Verify requester confirmation:
  - required confirmation path
  - negative feedback reopens if configured
  - autoclose after days represented if configured
- [ ] Verify allowed resolution codes:
  - valid code accepted
  - invalid code rejected
- [ ] Verify reporting/passport export preview:
  - public sections visible
  - internal-only sections hidden from requester
  - long Russian text does not break UI
  - attachments/evidence are represented
- [ ] Record passport/export evidence.

## Slice 11: Agent GUI Live Acceptance

- [ ] Start or connect a live agent path according to project runtime rules.
- [ ] Verify agent can fetch current form pack/templates.
- [ ] Create `T-LIVE-08` from agent GUI using a current published template.
- [ ] Create or preview a schema-backed disposable template from agent path if supported.
- [ ] Verify GUI form behavior:
  - required fields
  - conditional fields
  - picker fields
  - file attachment path
  - diagnostic consent wording
  - server-preview fallback
- [ ] Verify post-create result panel:
  - access code
  - next action
  - expected due dates
  - open ticket action
  - add message action
  - create another action
  - no raw SLA/OLA/internal policy jargon
- [ ] Verify server receives correct context:
  - request template snapshot
  - form schema snapshot
  - priority/routing decision
  - requester/device identity
  - attachment message reference if used
- [ ] Verify agent logs do not leak token and do not show unexpected tracebacks.
- [ ] Record GUI screenshots or text evidence and created ticket id.

## Slice 12: RBAC, Security And Negative Live Acceptance

- [ ] Verify settings/admin permissions:
  - non-admin cannot publish policies/templates
  - admin can publish
  - invalid payload rejected with safe error
- [ ] Verify support permissions:
  - requester cannot assign queue
  - requester cannot override priority
  - requester cannot view OLA/raw diagnostics/internal notes
  - support can perform allowed workflow transitions
  - queue lead/admin can perform configured elevated actions
- [ ] Verify approval permissions:
  - only approver or admin path can approve, according to policy
  - reject comment required when configured
- [ ] Verify diagnostics permissions:
  - high-risk tool requires consent/role
  - operation cannot be run against unauthorized device/ticket context
- [ ] Verify token/log safety:
  - no raw token in server logs
  - no raw token in agent logs
  - artifacts redact sensitive values
- [ ] Verify API negative cases:
  - unknown template
  - inactive template
  - stale policy version if relevant
  - invalid workflow transition
  - invalid queue id
  - invalid approval actor
- [ ] Record negative test evidence.

## Slice 13: Browser UX And Console Signoff

- [ ] Browser check `/admin`.
- [ ] Browser check `/app/admin/forms`.
- [ ] Browser check `/app/settings`.
- [ ] Browser check `/app/tickets`.
- [ ] Browser check each representative ticket detail:
  - incident
  - access request
  - consultation
  - change request
- [ ] Browser check `/app/admin/observer`.
- [ ] Browser check requester/public path if used.
- [ ] Verify UI quality:
  - no overlapping text
  - long Russian labels fit
  - buttons and controls are understandable
  - compact panels do not use hero-scale text
  - no raw internal policy ids leak to requester-facing UI
  - empty/error/loading states are coherent
- [ ] Capture screenshots into `artifacts/browser_checks/live-acceptance/`.
- [ ] Capture browser console and network summary.
- [ ] Record all active-tab console errors and decide blocker/non-blocker.

## Slice 14: Cleanup, Evidence Review And Final Score

- [ ] Generate live acceptance summary:
  - `artifacts/live_checks/service_desk_live_acceptance_YYYYMMDD.md`
  - `artifacts/live_checks/service_desk_live_acceptance_YYYYMMDD.json`
- [ ] List all created disposable templates, policies, tickets and artifacts.
- [ ] Decide cleanup strategy:
  - keep tickets as evidence with clear prefix
  - deactivate disposable templates
  - remove temporary preferred pack entries if created
  - do not delete evidence before summary is complete
- [ ] Run cleanup or deactivation through supported API/scripted path only.
- [ ] Re-run targeted smoke:
  - `python scripts\manage_remote_stack.py smoke server`
  - browser `/app/tickets`
  - browser `/app/admin/forms`
- [ ] Stop remote server:
  - `python scripts\manage_remote_stack.py stop server`
  - confirm stopped through status
- [ ] Final local status:
  - `git status --short`
  - generated artifacts ignored
  - only intentional plan/docs/code fixes staged or committed
- [ ] Update this plan:
  - completion percentage
  - passed slices
  - defects found
  - blocked items
  - final system maturity estimate
- [ ] Commit plan/evidence references and any code fixes separately from generated artifacts.

## Defect Handling Rules

If a live slice finds a defect:

- [ ] Capture scenario id, ticket id, request payload, expected result and actual result.
- [ ] Capture UI screenshot or API response.
- [ ] Capture relevant server/agent/observer log lines with tokens redacted.
- [ ] Classify severity:
  - P0: data loss, security leak, impossible core ticket flow, raw token leak
  - P1: wrong workflow/SLA/approval/closure decision, requester sees internal data, diagnostic trace missing
  - P2: UI inconsistency, missing preview, non-blocking notification/action issue
  - P3: cosmetic, wording, non-critical artifact cleanup
- [ ] Add or update focused regression test before code fix where realistic.
- [ ] Fix in the smallest ownership zone.
- [ ] Run focused tests plus relevant live re-check.
- [ ] Update docs/CODEMAP if contract, route, structure or workflow changed.
- [ ] Commit defect fix separately from plan-only updates when practical.

## Verification Matrix

Minimum command set before final completion claim:

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
```

Minimum live scenario coverage before final completion claim:

- request template settings create/edit/reload
- form conditional fields and process mapping
- ticket create from server/API
- ticket create from agent GUI
- workflow happy path
- workflow negative gates
- priority compute and manual override
- routing and rerouting
- SLA start/pause/resume/stop/warning/breach
- OLA start/pause/stop/risk
- approval approve/reject
- diagnostics with consent
- observer trace
- notification recipient/action audit
- visibility/requester-safe projection
- smart views
- closure blocking and successful passport
- RBAC negative cases
- cleanup/deactivation

## Current State

- Implementation/hardening plan is complete and committed.
- Latest plan/tooling commit before this live plan: `30e1db8 scripts: add local context index workflow`.
- Generated live/browser/diagnostic/release artifacts are ignored through `.gitignore`.
- This plan has not yet executed any live acceptance slice.

## Handoff

Recommended execution order is strict:

1. Slice 0 proves the stand and local workspace are ready.
2. Slice 1 creates controlled disposable settings.
3. Slices 2-12 exercise the service desk process from creation to closure across server, web UI, agent GUI, observer and security boundaries.
4. Slice 13 performs browser UX signoff across the real operator pages.
5. Slice 14 summarizes evidence, cleans/deactivates disposable entities, stops the server and updates the final score.

Do not skip cleanup/evidence summary. Without a clear created-entity list, the live test campaign is not complete.
