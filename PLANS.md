# Observer Layer Trace Clarity Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `pc-client-observer-diagnostics` first, then use `superpowers:executing-plans` or the project safe workflow to execute this plan task by task. Keep this file current after each checkpoint.

**Goal:** Make the existing observer layer clearer and more actionable for `/app/tickets`, operations, retries, passport/evidence flows and admin diagnostics without turning observer into a business source of truth.

**Architecture:** Keep observer as a technical overlay over committed source rows: `operations`, `ticket_events`, `device_events`, `agent_runtime_audit`, `agent_observer_events`, playbook run/steps and agent action traces. Strengthen trace continuity through ticket-root traces and linked child operation/playbook traces, expose compact typed summaries to `/app/tickets`, and keep deep investigation in `/app/admin/observer`.

**Tech Stack:** aiohttp web API, SQLAlchemy async repos, Pydantic DTOs, `server/observer/service.py`, `server/observer/runtime.py`, React 19, Vite, TypeScript, Tailwind v4, TanStack Query, existing `/api/web/support/*` and `/api/web/admin/observer/*` contracts.

---

## Status

Created: 2026-05-07.

Current active plan: **P13 Support Workspace Shell Navigation Closure**.

Current progress:

- P8.1 Contract audit and trace-continuity baseline: **completed locally**.
- P8.2 Backend typed observer summary depth: **completed locally**.
- P8.3 Support action trace continuity cleanup: **completed locally**.
- P8.4 Operation/retry/playbook trace relation UI: **completed locally**.
- P8.5 `/app/tickets` Observer diagnostic card: **completed locally**.
- P8.6 Admin Observer deep-link refinement: **completed locally**.
- P8.7 Observer documentation and CODEMAP sync: **completed locally**.
- P8.8 Local verification, browser signoff, commit and optional deploy: **completed with noted CI-suite agent_ws hang**.
- P8.9 CI-suite agent_ws hang follow-up: **completed 2026-05-08; idle-timeout wiring fixed and green artifact proven for earlier commit**.
- P9.1 Hide internal/test queue and smart-view navigation noise in `/app/tickets`: **completed locally**.
- P10.1 Green CI artifact for current support-workspace branch head: **completed for release HEAD `1c819d7046b4382d498b0b265b26665cb011b4ed`; full CI summary is green**.
- P10.2 Ticket hide/archive/delete model for `/app/tickets`: **completed locally; targeted backend/frontend checks green 2026-05-08**.
- P10.3 Consent-required retry flow policy refinement: **completed locally; targeted backend/frontend checks green 2026-05-08**.
- P10.4 Final release/browser/agent signoff: **completed on stand with explicit CI-bypass caveat 2026-05-08**.
- P10.5 Final no-bypass release/browser/agent signoff: **completed 2026-05-08 for runtime release HEAD `1c819d7046b4382d498b0b265b26665cb011b4ed`; server stopped after checks**.
- P11.1 Agent GUI duplicate taskbar windows root cause and source fix: **completed locally 2026-05-08**.
- P12.1 Manual QA bug intake for ticket `T-000520`: **completed locally; user-reported live issues captured and mapped 2026-05-08**.
- P12.2 SLA/next-action refresh after public reply: **completed locally; backend workspace now serializes `first_response_at` and stops first-response timer, frontend force-refetches selected data after send**.
- P12.3 Live operation refresh for diagnostics: **completed locally; selected workspace/timeline short-poll while operations are active**.
- P12.4 Reply controls clarity: **completed locally; top reply action focuses composer and composer remains the only send control**.
- P12.5 `/app/support` support entry handoff: **completed locally; router test covers redirect to `/app/tickets`**.
- P12.6 Observer root trace open target: **completed locally; mapper hardens trace URLs to `/app/admin/observer?trace_id=...`**.
- P12.7 Explicit tool/module/playbook picker: **completed locally; central diagnostics opens right tools launcher and requires explicit selection before run**.
- P13.1 `/app/tickets` topbar support navigation and logout: **completed locally; focused React test, production build and `verify_workspace.py` are green**.

## P13 Support Workspace Shell Navigation Closure

**Goal:** make `/app/tickets` feel connected to the broader support workspace even though it intentionally bypasses the generic `AppShell` for the dense 3-column operator layout.

**Classification:** local frontend UI/auth flow change. Touches only React `/app/tickets` topbar behavior and its focused tests; no backend/API contract change.

### P13.1 Add Support Navigation And Logout

**Files/areas:**

- `webapp/src/pages/tickets/list-page.tsx`
- `webapp/src/pages/tickets/list-page.test.tsx`

**Steps:**

- Add explicit topbar navigation links: `Тикеты`, `Отчёты`, `Знания`, `Настройки`.
- Add logout control next to the operator avatar using existing `useSession().logout()` and redirect to `/app/login`.
- Keep the layout dense enough for desktop support widths and preserve dark/light theme styling.
- Add focused React test for nav hrefs and logout redirect.

**Acceptance:**

- `/app/tickets` no longer feels isolated from the support workspace.
- The operator can log out from the ticket workspace without going to another page.
- Focused frontend test and build pass.

## P12 Support Workspace Manual QA Bugfixes

**Goal:** close manual QA bugs found on `/app/tickets` for ticket `T-000520`: stale SLA/next-action state after public replies, delayed diagnostic result rendering, confusing duplicate reply controls, incomplete support navigation handoff, wrong Observer root-trace link behavior, and lack of explicit module/playbook selection before diagnostics run.

**Classification:** cross-cutting UI/API bugfix. Touches React `/app/tickets`, typed support API contracts, operation/playbook launch UX, SLA/timeline serialization and Observer deep-link behavior. No new destructive ticket behavior and no hard-delete scope.

**Current hypothesis map:**

- SLA/next action after public reply: either backend does not stop/serialize first-response SLA for the typed `/workspace` payload after `POST /api/web/support/tickets/{ticket_id}/messages`, or React invalidates cache but keeps stale aggregate/timer state long enough to show the old first-action card.
- Diagnostic result delay: operation start mutation invalidates once, but the page does not poll selected ticket workspace/timeline while an operation is `accepted/queued/running/sent/waiting_consent`; if realtime event is missed, the UI stays on `Нет результата` until manual refresh.
- Duplicate reply controls: the top `Ответить` button is a mode/focus action, while the composer `Отправить` button is the real submit action. This is functionally ambiguous and makes one control feel broken.
- `/app/tickets` support navigation: `/app/support` redirects to `/app/tickets`, but legacy/main support links or shell navigation may still not land on the new workspace consistently.
- Root trace link: Observer card/button must open `/app/admin/observer?trace_id=...`, not the ticket route. Need verify whether the wrong target is produced by backend `root_trace_url` or frontend fallback.
- Diagnostics picker: central `Запустить диагностику` currently uses the first runnable tool/playbook path. Operators need an explicit chooser for modules/tools/playbooks and visible params/readiness before dispatch.

### P12.1 Reproduce And Capture Evidence

**Files/areas:**

- Inspect: `webapp/src/pages/tickets/list-page.tsx`
- Inspect: `webapp/src/features/queues/api.ts`
- Inspect: `webapp/src/features/queues/support-workspace-mappers.ts`
- Inspect: `server/web_api/support_handlers.py`
- Inspect/tests: `server/tests/test_web_support_api.py`
- Inspect/tests: `webapp/src/pages/tickets/list-page.test.tsx`, `webapp/src/features/queues/support-workspace-mappers.test.ts`

**Steps:**

- Start stand or use current live stand through project scripts only.
- Open `http://192.168.100.17:8666/app/tickets/T-000520`.
- Capture before/after payloads:
  - `GET /api/web/support/tickets/{ticket_id}/workspace`
  - `GET /api/web/support/tickets/{ticket_id}/timeline?filter=all`
  - `GET /api/web/support/tickets/{ticket_id}/timeline?filter=diagnostics`
- Send a public reply and compare `first_response_at`, `first_response_due_at`, `sla_ola.first_response`, `next_action`, timeline events and queue row countdown.
- Run a low-risk diagnostic and watch network/realtime: verify whether result payload arrives through websocket, polling, or only after full reload.
- Click Observer `Root trace -> Открыть` and record final URL.

**Acceptance:**

- Each bug has a concrete source: backend stale first-response serialization, frontend cache/polling, wrong mapper URL, or UX-only ambiguity.
- The tasks below are refined if evidence contradicts a hypothesis.

**Status 2026-05-08:** completed by code inspection plus targeted tests. Live browser verification on stand is still pending after deploy.

### P12.2 Fix SLA And Next-Action Refresh After Public Reply

**Planned behavior:**

- After a public support reply, the first-response SLA must disappear from the `next action / first action` focus if it has been satisfied.
- The next-action panel may still show support work if status requires support, but the label/hint must no longer imply `answer first` when `first_response_at` is set.
- The page must refresh selected workspace, selected timeline and queue row immediately after message mutation, not wait for the 15s queue poll.

**Implementation outline:**

- Backend: verify `POST /api/web/support/tickets/{ticket_id}/messages` calls the same SLA first-response close path as legacy/public support comments.
- Backend serializer: ensure `/workspace` and `/timeline` expose the updated first-response state from fresh DB rows after mutation.
- Frontend: after `messageMutation` success, force `refetchQueries` or `invalidate+refetch` for:
  - `["tickets-workspace", selectedTicketId]`
  - `["tickets-workspace-timeline", selectedTicketId]`
  - `["tickets-workspace-queue"]`
- Mapper: when `first_response_at` exists or first-response timer is stopped, choose resolution/OLA/current next-action timer instead of first-response timer for the focus card.

**Tests:**

- Add/extend server test around `POST /api/web/support/tickets/{ticket_id}/messages` -> workspace payload no longer presents active first-response as the primary countdown.
- Add/extend mapper test for `public reply already sent` -> next action does not show first-response timer as active.
- Add/extend React test proving public message success refetches workspace/timeline/queue.

**Status 2026-05-08:** completed locally.

- Backend `SupportTicketDetail` now includes `first_response_at`.
- `/workspace` `sla_ola.first_response` returns inactive `unknown` timer when `first_response_at` is set.
- Frontend mapper skips first-response as next-action due date once first response is satisfied.
- Message mutation uses active `refetchQueries` for selected workspace, selected timeline and queue.

### P12.3 Live Operation Refresh For Diagnostics

**Planned behavior:**

- After starting a diagnostic, timeline must show queued/accepted immediately.
- While any selected-ticket operation is active (`accepted`, `queued`, `running`, `sent`, `waiting_consent`), `/app/tickets` must poll selected workspace/timeline/tools every 2-3 seconds.
- When operation reaches a terminal state, result card must update automatically and polling can fall back to normal cadence.

**Implementation outline:**

- Frontend: derive `activeOperations.length` from the mapped workspace payload.
- Add conditional `refetchInterval` to `workspaceQuery` and selected `timelineQuery`.
- After tool/playbook run success, set `timelineFilter` to `diagnostics` or keep current tab but refetch all selected-ticket data immediately.
- Keep realtime invalidation as an accelerator, not the only refresh mechanism.
- Backend: if accepted operation rows lack enough status/result data in aggregate `/workspace`, extend existing serializer rather than adding a new endpoint.

**Tests:**

- React test: active operation enables short polling/refetch interval and terminal operation disables it.
- React test: tool/playbook run invalidates/refetches workspace and diagnostics timeline.
- Server test only if serializer lacks terminal result fields.

**Status 2026-05-08:** completed locally.

- `workspaceQuery` short-polls every 2.5s while selected ticket has active operations.
- Filtered `timelineQuery` short-polls during active operations.
- Tool/playbook run success switches to diagnostics timeline and refetches selected data.

### P12.4 Clarify Reply Controls

**Planned behavior:**

- Top action bar must not look like a second submit button.
- Keep one actual submit action in composer: `Отправить`.
- Top `Ответить` becomes a navigation/focus action, for example `К ответу`, or it remains `Ответить` but scrolls/focuses the composer and visibly selects `Публичный ответ`.
- Internal note action similarly focuses composer in internal mode when permission allows; otherwise disabled with a clear tooltip/reason.

**Implementation outline:**

- Add a composer ref in `list-page.tsx`.
- Top actions call `setComposerMode(...)` and focus/scroll the textarea.
- Rename/tooltip top actions to distinguish `prepare reply` vs `send`.
- Add test ids for top reply action and composer textarea.

**Tests:**

- React test: clicking top reply focuses composer and does not send.
- React test: composer send remains disabled until text is entered, then calls message API.

**Status 2026-05-08:** completed locally.

- Top action is now `К ответу`, selects public composer and focuses the textarea.
- Internal note top action selects/focuses internal composer when permitted.

### P12.5 Connect `/app/tickets` With Main Support Entry Points

**Planned behavior:**

- All support-shell `Тикеты/Support workspace` entry points should land on `/app/tickets`.
- `/app/support` remains a redirect to `/app/tickets`.
- If a legacy/main support route still exists in navigation or links, add a clear `Открыть новое рабочее место` handoff or redirect only where safe.

**Implementation outline:**

- Audit `webapp/src/app/navigation.tsx`, `webapp/src/app/router.tsx`, shell/sidebar/topbar links and legacy support links.
- Keep route compatibility; do not remove legacy ticket detail pages used by requester/public flows.
- Add route/navigation tests for support workspace entry points.

**Tests:**

- Router test: `/app/support` redirects to `/app/tickets`.
- Navigation test: support ticket nav item points to `/app/tickets`.
- Browser check: main support nav opens the new 3-column workspace.

**Status 2026-05-08:** completed locally for route compatibility. Browser shell verification is pending after deploy.

### P12.6 Fix Observer Root Trace Open Target

**Planned behavior:**

- Observer root trace `Открыть` opens admin observer workbench with trace context: `/app/admin/observer?trace_id=<id>`.
- It must never navigate to the current ticket detail route unless no trace exists and the UI explicitly labels that fallback.

**Implementation outline:**

- Verify backend `root_trace_url`, `trace_url` and related trace URL generation in `server/web_api/support_handlers.py` / observer summary serializer.
- Harden frontend mapper: if URL is missing but `trace_id` exists, synthesize `/app/admin/observer?trace_id=...`; if URL points to `/app/tickets`, treat it as invalid for Observer CTA and replace with admin observer URL.
- Rename CTA tooltip to `Открыть в Observer`.

**Tests:**

- Mapper test: root trace with `trace_id` and bad/missing URL maps to `/app/admin/observer?trace_id=...`.
- Browser/live check: click opens observer tab, not ticket page.

**Status 2026-05-08:** completed locally.

- Mapper synthesizes `/app/admin/observer?trace_id=...` for root/related traces.
- Bad `/app/tickets` observer URLs are replaced when a trace id exists.

### P12.7 Add Explicit Tool/Module/Playbook Picker

**Planned behavior:**

- Central `Запустить диагностику` opens the right `Инструменты` tab and a picker/drawer, not an automatic first-tool launch.
- The picker lists:
  - playbooks;
  - tools/modules;
  - enabled/disabled state and reason;
  - risk/consent labels;
  - preset/params when available.
- Operator chooses a concrete module/tool/playbook and then confirms `Запустить`.
- The right `Инструменты` tab remains the persistent place for operation history plus available automation.

**Implementation outline:**

- Frontend: introduce `selectedAutomationItem` state and a compact launch drawer/panel inside `list-page.tsx` or split into `TicketAutomationLauncher`.
- Reuse existing `postSupportTicketToolRun`, `postSupportTicketPlaybookRun`, `tool-param-fields.ts` and `SupportWorkspaceToolItem` mappers.
- Support params:
  - default preset params prefilled;
  - editable primitive params if metadata is available;
  - disabled confirm with reason if tool/playbook not runnable.
- Backend only if current `/tools` or `/playbooks` payload lacks required param metadata for existing modules.

**Tests:**

- Mapper test for tools/playbooks enabled/disabled labels.
- React test: central diagnostic button opens picker, no API call yet.
- React test: selecting a specific tool calls `/api/web/support/tickets/{ticket_id}/tools/run` with its id/preset/params.
- React test: selecting a playbook calls `/api/web/support/tickets/{ticket_id}/playbooks/run`.

**Status 2026-05-08:** completed locally for explicit selection and low-risk tool launch.

- Central diagnostics button opens the right `Инструменты` tab launcher.
- The launcher lists playbooks/tools with disabled reasons and requires `Выбрать` + explicit run.
- Tool run uses the selected tool and first preset params if present.
- Playbook run uses the selected playbook version id.

### P12.8 Verification, Release And Manual QA

**Local checks:**

- `python scripts/verify_workspace.py`
- `pnpm --dir webapp test -- --run webapp/src/pages/tickets/list-page.test.tsx webapp/src/features/queues/support-workspace-mappers.test.ts`
- Targeted server tests in `server/tests/test_web_support_api.py` around messages/SLA, workspace aggregate, tools/playbooks run and observer URL.
- `pnpm --dir webapp build`

**Verification 2026-05-08 so far:**

- `pnpm --dir webapp test -- --run src/features/queues/support-workspace-mappers.test.ts src/pages/tickets/list-page.test.tsx` -> 41 passed.
- `pnpm --dir webapp test -- --run src/app/router.test.tsx` -> 6 passed.
- `pytest server/tests/test_web_support_api.py::test_web_support_ticket_workspace_stops_first_response_timer_after_reply -q` -> 1 passed.
- `pnpm --dir webapp run build` -> passed.
- `python scripts\verify_workspace.py` -> passed after updating `docs/QUICK_LOOKUP.md` and `scripts/navigation_catalog.py`.

**Live checks:**

- Release through no-bypass path only after green CI artifact.
- Browser test `http://192.168.100.17:8666/app/tickets/T-000520`:
  - public reply updates first-response/next-action without reload;
  - diagnostic result appears without reload;
  - top reply action focuses composer, composer send is the only submit;
  - `/app/support` and main nav land on `/app/tickets`;
  - Observer opens `/app/admin/observer?trace_id=...`;
  - tool/playbook picker can run selected low-risk item.
- Stop server after checks unless explicitly asked to keep it running.

**Resolved product answers 2026-05-08:**

1. `/app/support` and the broader support shell entries near settings/navigation must connect to the new `/app/tickets` workspace, not only the standalone tickets page.
2. Diagnostics picker is confirmed as right `Инструменты` tab + inline drawer/panel. The central action should focus that picker instead of launching the first available diagnostic automatically.

## P11 Agent GUI Duplicate Taskbar Windows

**Goal:** remove confusing extra `pc_agent` taskbar/Alt-Tab windows when the compiled Windows agent is running, without changing the always-on launcher/runtime model.

**Findings so far:**

- Live process tree shows one real `pc_agent.exe` process under the launcher.
- The two visible `launcher.exe` rows are parent/child around the onefile launcher and have no GUI windows.
- Win32 window enumeration shows two extra visible top-level Qt windows titled `pc_agent`, both `136x56`, no owner/parent, inside the single agent process.
- The matching code path is the recording STOP overlay in `pc_agent/ui_gui/main_window.py::_show_stop_button()`, which creates a standalone `QWidget` with `Qt.Window`.
- After launching the source copy as `3.1.30`, user still saw blank `python` Taskbar/Alt-Tab windows. Current Win32 enumeration shows a Qt `_q_titlebar` helper window in the agent process; the matching code path is `window_chrome.py` calling native `startSystemMove()` / `startSystemResize()`.
- After removing native move/resize calls, live source-run inspection still reproduced two visible `python` windows. Qt top-level diagnostics mapped both HWNDs to orphan `QLabel("")` widgets: `sidebar_title_label` and `sidebar_subtitle_label` were created without parent, never added to a layout, then made visible by `_set_sidebar_expanded()`.

**Plan:**

- Add a regression test that the STOP overlay uses a tool/owned window flag instead of a normal app window.
- Change `_show_stop_button()` so the overlay is not a normal taskbar/Alt-Tab window and has an explicit object/title.
- Add a regression test that frameless chrome does not call Qt native move/resize helpers, then keep drag/resize on the manual fallback.
- Add a regression test that the sidebar header does not create unused parentless blank labels, then remove the orphan labels and their `setVisible()` calls.
- Keep launcher behavior unchanged unless new evidence shows it is launching duplicate independent runtime instances.
- Verify with focused GUI/static tests, runtime tests, and `python scripts/verify_workspace.py`.

**Acceptance:**

- Compiled agent still has one real `pc_agent.exe` runtime.
- Recording STOP overlay can appear without creating taskbar entries titled `pc_agent`.
- Frameless chrome does not create `_q_titlebar` helper windows titled `python`.
- The sidebar header does not create orphan blank `QLabel` top-level windows, and live source-run Win32 inspection reports `bad_count=0` for visible default-title Qt app windows.
- Launcher parent/child behavior is documented in the final report as expected PyInstaller onefile behavior, not an agent duplicate.

**Verification 2026-05-08:**

- Live Windows inspection of the already-running `3.1.29` binary: one `pc_agent.exe` process, two visible `launcher.exe` parent/child processes, and two extra top-level Qt windows titled `pc_agent` inside the single agent process.
- Red test before fix: `python -m pytest pc_agent\tests\test_main_window_runtime_windows.py -q --tb=short` -> failed because STOP overlay was `WindowType.Window`.
- Green focused tests after fix: `python -m pytest pc_agent\tests\test_main_window_runtime_windows.py -q --tb=short` -> 1 passed; `python -m pytest pc_agent\tests\test_main_window_update_status.py -q --tb=short` -> 3 passed; `python -m pytest pc_agent\tests\test_ui_api_server_shutdown.py -v --tb=short` -> 6 passed; `python -m pytest pc_agent\tests\test_runtime_logging.py -v --tb=short` -> 2 passed.
- Second red test after source-run report: `python -m pytest pc_agent\tests\test_main_window_runtime_windows.py -q --tb=short` -> failed because `window_chrome.py` still used `startSystemMove`.
- Second green focused test: `python -m pytest pc_agent\tests\test_main_window_runtime_windows.py -q --tb=short` -> 2 passed after removing native Qt move/resize helper calls.
- Third red test after source-run report: `python -m pytest pc_agent\tests\test_main_window_runtime_windows.py -q --tb=short` -> failed because the sidebar still created `sidebar_title_label` / `sidebar_subtitle_label` as parentless blank labels and toggled them visible.
- Third green focused test: `python -m pytest pc_agent\tests\test_main_window_runtime_windows.py -q --tb=short` -> 3 passed after removing the orphan sidebar labels.
- Live source-run Win32 verification after final fix: one visible `Maria Agent v3.1.30` `Qt6102QWindowIcon`, no visible `python` / `pc_agent` `Qt6102QWindowIcon` helper windows (`bad_count=0`).
- Focused runtime suite after final fix: `python -m pytest pc_agent\tests\test_main_window_runtime_windows.py pc_agent\tests\test_main_window_update_status.py pc_agent\tests\test_ui_api_server_shutdown.py pc_agent\tests\test_runtime_logging.py -v --tb=short` -> 14 passed.
- Agent baseline after final fix: `python -m pytest pc_agent\tests -m "not manual" -v --tb=short` -> 193 passed, 4 deselected.
- Workspace/docs after final fix: `python scripts\verify_workspace.py` -> passed; `python -m pytest scripts\test_navigation_catalog.py scripts\test_task_intake.py -q --tb=short` -> 21 passed; `python scripts\docs_inventory.py --check-links` -> all local markdown links valid; `python scripts\build_context_index.py --force` -> rebuilt.

## P10 Support Workspace Tail Closure

**Goal:** close the last 1-2% of `/app/tickets` readiness by removing CI/release bypasses, adding first-class ticket hide/archive controls, and finalizing retry consent policy.

**Architecture:** keep destructive ticket changes out of the existing visual navigation hygiene. Introduce explicit ticket lifecycle visibility controls through typed backend APIs, audit/timeline events, permissions and UI affordances. Do not implement hard delete; reversible archive/hide are the supported operator/admin cleanup tools.

**Tech Stack:** aiohttp typed web API, SQLAlchemy async repos/models, Alembic if schema changes are needed, `TicketEventsRepo`, React 19/Vite/TanStack Query/Tailwind in `webapp/src/pages/tickets/*`, existing support workspace mappers and tests.

### P10 Readiness Target

- Typed/backend gap after P10: **0%** for planned support workspace contracts.
- Backend/domain gap after P10: **0-1%**, only future external KB/provider depth out of scope.
- UI/page polish gap after P10: **0-1%**, only optional cosmetic tuning out of scope.
- Release confidence: **green CI artifact required**, no `--skip-ci-check` for final signoff.

### P10.1 Green CI Artifact

**Purpose:** remove the current release caveat caused by using `--skip-ci-check` for commits `de36a56`, `eb83af1`, `439b391`.

**Status 2026-05-08:** completed for runtime release HEAD `1c819d7046b4382d498b0b265b26665cb011b4ed`. The earlier red `run_ci_suite.py` artifact used an intentionally short `--server-pytest-timeout 420`, while the DB/API layer normally needs about 40-42 minutes. The final HEAD now has a green canonical CI artifact, and the final stand release was performed without `--skip-ci-check`.

**Files/Commands:**

- Run: `python scripts/run_ci_suite.py`
- If local full suite hangs again in `agent_ws`, run the project fallback: `python scripts/run_ci_in_temp_workspace.py`
- Inspect generated artifact under `artifacts/ci/<HEAD_SHA>/summary.json`
- If a hang reproduces, investigate only the hanging slice and update `PLANS.md` with exact failing/hanging test, not a generic note.

**Acceptance:**

- `artifacts/ci/1c819d7046b4382d498b0b265b26665cb011b4ed/summary.json` exists and has `status=green`.
- Final deploy/release ran without `--skip-ci-check` in P10.5.

**Verification 2026-05-08:**

- `python scripts/verify_workspace.py` -> passed.
- `pnpm --dir webapp build` -> passed.
- `pytest server/tests/test_operation_retry.py -q` -> 5 passed.
- `pytest server/tests/test_web_support_api.py -k "hide_removes_ticket_from_queue or archive_is_admin_only or cleanup_noise_hides or support_ticket_detail_includes_observer_summary or support_ticket_detail_marks_retry_operation_trace_relation or support_ticket_detail_timeline_includes_normalized_lifecycle_events or support_ticket_detail_exposes_template_visibility_policy or worklog_action_uses_web_support_boundary or lifecycle_event_uses_existing_ticket_root_trace or status_action_returns_typed_result" -q` -> 10 passed, 46 deselected.
- `pnpm --dir webapp test -- --run src/features/queues/support-workspace-mappers.test.ts src/pages/tickets/list-page.test.tsx` -> 37 passed.
- `python scripts/run_ci_suite.py --commit HEAD --verify-timeout 180 --web-build-timeout 240 --server-pytest-timeout 420 --pc-agent-pytest-timeout 420 --idle-timeout 180` -> red artifact under `artifacts/ci/HEAD`: `verify_workspace`, `build_webapp_bundle`, `server_pytest_no_db` passed; `server_pytest_db_api` timed out at 420 seconds.
- `python -m pytest server/tests/test_helpdesk_policy_registry.py::test_web_admin_publish_policy_creates_version_and_audit -vv -s --tb=short --durations=20` -> 1 passed in 9.77s; the previously visible stop point is not a hanging test.
- `python -m pytest server/tests/test_helpdesk_policy_registry.py -m "not manual and not no_db and not agent_ws" -vv --tb=short --durations=80` -> 25 passed in 162.94s.
- `python -m pytest server/tests -m "not manual and not no_db and not agent_ws" -vv --durations=80 --junitxml artifacts/diagnostics/junit-server-db-api-head-check.xml` -> 504 passed, 177 deselected, 1 warning in 2493.44s. Conclusion: DB/API layer is healthy but too long for a 420 second timeout.

### P10.2 Ticket Hide / Archive / Delete Model

**Purpose:** give operators/admins real controls to remove noisy or obsolete tickets from the active workspace without deleting business history by accident.

**Default policy to implement unless user overrides:**

- `hide from workspace`: reversible global per-ticket visibility flag for all support users.
- `archive`: reversible global active-list removal for closed/test/noise tickets, keeps detail page and audit history, admin-only.
- `hard delete`: explicitly out of scope and not needed.

**Backend plan:**

**Implemented 2026-05-08:** existing `tickets.archived_at` is reused, and hidden/archive metadata is stored in `tickets.custom_fields.support_workspace_visibility`, so no Alembic migration was needed. Added typed support actions `hide`, `unhide`, `archive`, `unarchive` plus `POST /api/web/support/workspace/cleanup-noise`; default queue/summary filtering excludes hidden and archived tickets, while `include_archived=1` and backend-only `include_hidden=1` remain explicit escape hatches. Hard delete remains intentionally unavailable.

- Inspect current ticket model for existing fields first:
  - `Ticket.archived_at`, `Ticket.deleted_at`, `Ticket.custom_fields`, status terminal fields, or existing cleanup/visibility helpers.
  - likely files: `server/app/db/models.py`, `server/tickets/handlers.py`, `server/tickets/visibility_policy.py`, `server/web_api/support_handlers.py`, `server/web_api/dto/support.py`.
- No migration is needed for this slice because `Ticket.archived_at` and `Ticket.custom_fields` already cover the accepted product behavior.
- Add typed actions:
  - `POST /api/web/support/tickets/{ticket_id}/hide`
  - `POST /api/web/support/tickets/{ticket_id}/unhide`
  - `POST /api/web/support/tickets/{ticket_id}/archive`
  - `POST /api/web/support/tickets/{ticket_id}/unarchive`
  - `POST /api/web/support/workspace/cleanup-noise`
  - Do not add hard-delete endpoints.
- Add request DTOs:
  - `{ "reason": "string", "scope": "workspace|global" }` for hide/archive.
  - response uses existing typed mutation result shape where possible.
- Add permission checks:
  - support/admin can use global hide/unhide if they can open the ticket.
  - admin only can archive/unarchive.
  - no hard delete permission or endpoint in this slice.
- Add timeline/audit events:
  - `ticket_hidden_from_workspace`
  - `ticket_unhidden_from_workspace`
  - `ticket_archived_from_workspace`
  - `ticket_unarchived_from_workspace`
- Ensure list APIs default to active only:
  - `/api/web/support/queue`
  - `/api/web/support/workspace/summary`
  - aggregate workspace should still load direct ticket detail by id, with archived/hidden banner.
- Add query escape hatches:
  - `include_hidden=1`
  - `include_archived=1`
  - only for permitted roles.

**Frontend plan:**

**Implemented 2026-05-08:** `/app/tickets` now passes `include_archived=1` only when the operator toggles `Показывать архив`; the `Ещё` menu exposes hide/unhide for support/admin and archive/unarchive for admin; hidden/archived tickets get compact badges in the list/detail header; and a separate `Скрыть test` action calls the cleanup endpoint for obvious live/stage/test rows.

- Add visible controls under the ticket action menu `Ещё`:
  - `Скрыть из рабочего списка`
  - `Вернуть в рабочий список`
  - `Архивировать`
  - `Вернуть из архива`
- Add confirmation modal/drawer:
  - required reason for archive.
  - warning that archive keeps history and does not hard-delete data.
- Add archived/hidden banner in center ticket header:
  - `Скрыт из рабочего списка`
  - `В архиве`
- Add left worklist filter toggle or compact menu:
  - `Показывать скрытые`
  - `Показывать архив`
  - default off.
- Add cleanup action:
  - separate `Скрыть live/test тикеты` button/action.
  - it should hide obvious `Stage...`, `Live...`, `...Test...` ticket rows using the same conservative artifact matching as queue navigation hygiene.
- Do not hide internal notes or timeline; status/history must remain visible on direct open.

**Tests:**

- Backend:
  - hide removes ticket from `/api/web/support/queue` by default.
  - direct `/workspace` detail still opens hidden ticket and marks state.
  - `include_hidden=1` returns hidden ticket for permitted actor.
  - archive removes ticket from queue/summary by default.
  - unarchive restores it.
  - permission denial returns typed `required_permission`.
  - timeline contains hide/archive events.
- Frontend:
  - mapper preserves `hidden`/`archived` flags.
  - `Ещё` menu renders controls according to permissions/state.
  - confirmation requires reason for archive.
  - queue refresh removes archived/hidden ticket.

**Acceptance:**

- Operators can clean active workspace without data loss. **Done locally.**
- Admin can restore archived tickets; archive is admin-only. **Done locally.**
- No existing ticket messages/events/passport evidence are deleted by hide/archive. **Done locally.**
- Hard delete remains intentionally unavailable. **Done locally.**
- Remaining before release: full CI artifact, remote deploy and browser signoff.

**Verification 2026-05-08:**

- `pytest server/tests/test_web_support_api.py -q` -> 56 passed.
- `pytest server/tests/test_web_support_api.py -k "hide_removes_ticket_from_queue or archive_is_admin_only or cleanup_noise_hides" -q` -> 3 passed.
- `pnpm --dir webapp test -- --run src/features/queues/api.test.ts src/features/queues/support-workspace-mappers.test.ts src/pages/tickets/list-page.test.tsx` -> 40 passed.
- `pnpm --dir webapp build` -> passed.
- `python scripts/verify_workspace.py` -> passed.

### P10.3 Consent-Required Retry Flow

**Purpose:** close the remaining domain gap around retrying tools/playbooks that require requester/operator consent.

**Implemented 2026-05-08:** `POST /api/operations/{operation_id}/retry` now treats consent-required retries as first-class operations instead of returning `CONSENT_REQUIRED_FOR_RETRY`. After the normal ticket/device/auth/tool/policy/replay checks pass, the endpoint creates a new `waiting_consent` retry operation linked by `retry_of_operation_id`, stores replay params in a `tool_call_started` event for later approval, writes `operation_retry_consent_requested`, and does not dispatch to the agent until `/approve` is called. `/app/tickets` labels these operation cards as consent-aware and shows `Запросить согласие и повторить`.

**Decision accepted before implementation:**

- Whether retry of `requires_consent=true` operations should create a new `waiting_consent` operation automatically or open a consent modal first.

**Default safe policy to implement unless user overrides:**

- Low-risk no-consent retry: immediate retry if policy/device/tool/replayable params pass.
- Consent-required retry: immediately create a new operation in `waiting_consent`, write `operation_retry_consent_requested`, and do not dispatch to agent until consent is approved.
- High-risk retry: disabled unless actor has high-risk permission and explicit confirm reason.

**Backend plan:**

- Extend existing retry endpoint:
  - `POST /api/operations/{operation_id}/retry`
  - ticket-scoped alias remains supported.
- Add response fields if missing:
  - `retry_requires_consent`
  - `consent_state`
  - `consent_action_url`
  - `disabled_reason`
- Add tests for:
  - consent-required retry does not dispatch.
  - consent approval dispatches the new retry operation.
  - consent denial records terminal denied state.
  - create+approve is covered locally; a focused deny regression can be added if P10 is extended.

**Frontend plan:**

- Operation card retry button:
  - low-risk: `Повторить`
  - consent-required: `Запросить согласие и повторить`
  - high-risk no permission: disabled tooltip.
- Timeline should show consent-requested retry as structured event, not raw JSON.

**Verification 2026-05-08:**

- `pytest server/tests/test_operation_retry.py -q` -> 5 passed.
- `pnpm --dir webapp test -- --run src/features/queues/support-workspace-mappers.test.ts src/pages/tickets/list-page.test.tsx` -> 37 passed.

### P10.4 Final No-Bypass Release Signoff

**Purpose:** produce a final support-workspace release with no caveats.

**Status 2026-05-08:** live/browser/agent signoff completed on the Linux stand for commit `b787b4f5e4bd2344e38f796095b0fffa5e9a0e21`, but not as a no-bypass release because P10.1 did not produce a green canonical CI summary. The stand was deployed with explicit `--skip-ci-check`, migrations were applied, remote smoke passed, server/agent status was checked, `/app/tickets` was verified in the browser, and the remote server was stopped after checks.

**Steps:**

- Run green CI artifact for HEAD.
- Deploy with `python scripts/deploy_workspace_to_remote.py` without `--skip-ci-check`.
- Release with `python scripts/release_server_to_remote.py --leave-running` without `--skip-ci-check`.
- Check:
  - `python scripts/manage_remote_stack.py smoke server`
  - `python scripts/manage_remote_stack.py status agent`
  - `python scripts/manage_remote_stack.py logs agent --lines 120`
  - browser at `http://192.168.100.17:8666/admin` and `/app/tickets`
- Browser assertions:
  - no horizontal overflow at `1366x900` and `1920x1080`.
  - no fresh console/page errors.
  - queue sidebar clean.
  - hide/archive controls visible according to role.
  - hide/archive round-trip works on a safe test ticket.
- Stop remote server after checks unless user explicitly asks to keep it running.

**Verification 2026-05-08:**

- `python scripts/release_server_to_remote.py --skip-ci-check --leave-running --smoke-attempts 8 --smoke-delay 5` -> completed successfully; remote fast-forward `439b391..b787b4f`, Alembic `upgrade head`, server smoke passed on attempt 2.
- `python scripts/manage_remote_stack.py status server` -> running before browser signoff.
- `python scripts/manage_remote_stack.py status agent` -> running; agent reconnected and received `handshake_ack`.
- Browser `http://192.168.100.17:8666/app/tickets` at `1600x900` -> three-column workspace rendered; topbar, smart views, archive toggle, selected ticket, next action, composer and right context visible.
- Browser `Ещё` menu -> visible `Скрыть у всех`, `Архивировать`, assignment/status/queue/priority/reroute controls.
- Browser archive toggle -> queue request used `include_archived=1` and returned 200.
- Browser console -> 0 errors, 0 warnings.
- Browser support APIs -> `/api/web/support/workspace/summary`, `/api/web/support/queue?limit=3`, selected `/workspace` all returned 200.
- `python scripts/manage_remote_stack.py stop server; python scripts/manage_remote_stack.py status server` -> stopped.

### P10.5 Final HEAD And Live Verification Plan

**Purpose:** turn the current support workspace branch state into a final no-bypass release candidate and run source-backed live checks on the Linux stand.

**Status 2026-05-08:** completed for final release HEAD `1c819d7046b4382d498b0b265b26665cb011b4ed`. Full CI is green, the Linux stand was released without `--skip-ci-check`, browser/live checks passed, and the remote server was stopped after signoff.

**Completion evidence 2026-05-08:**

- Full CI artifact: `artifacts/ci/1c819d7046b4382d498b0b265b26665cb011b4ed/summary.json` -> `status=green`.
- CI layers passed: `verify_workspace`, `build_webapp_bundle`, `server_pytest_no_db`, `server_pytest_db_api` (`504 passed, 177 deselected`), `server_pytest_agent_ws` (`30 passed, 651 deselected`), `pc_agent_pytest` (`190 passed, 4 deselected`).
- No-bypass release command passed: `python scripts/release_server_to_remote.py --leave-running --smoke-attempts 8 --smoke-delay 5`; remote fast-forwarded to `1c819d7`, Alembic `upgrade head` ran, webapp dist was unpacked, `/api/health` smoke returned 200.
- Remote status during live signoff: server running, agent running, agent reconnected and received `handshake_ack` after server start.
- Browser layout checks passed at `1366x900`, `1600x900`, `1920x1080`: no horizontal page overflow; three-column `/app/tickets` workspace rendered with topbar, left worklist, center ticket workspace and right context tabs.
- Browser workflow checks passed: `Ещё` menu exposed hide/archive plus assignment/status/queue/priority/reroute controls; `Показывать архив` triggered `include_archived=1`; right sidebar tabs, timeline tabs and public/internal composer mode switched without failed requests.
- Support API checks returned 200: `/api/web/support/workspace/summary`, `/api/web/support/queue?limit=5`, `/api/web/support/queue?limit=5&include_archived=1`, selected ticket `/workspace`, and selected ticket `/timeline?filter=diagnostics`.
- Observer checks passed: support Observer card visible; trace link opened `/app/admin/observer?trace_id=...`; browser console warnings/errors count was 0.
- Screenshots saved under `artifacts/diagnostics/support-workspace-p10-5-*.png`.
- Cleanup completed: `python scripts/manage_remote_stack.py stop server` -> stopped; `status server` -> inactive/stopped. Agent remains running and logs expected connection errors while the intentionally stopped server is down.

**Final HEAD steps:**

- Commit this `PLANS.md` update so the branch HEAD reflects the current verification truth and live-check plan.
- Run full CI with normal layer timeouts:
  - `python scripts/run_ci_suite.py`
  - acceptable fallback if local workspace state interferes: `python scripts/run_ci_in_temp_workspace.py`
- Confirm `artifacts/ci/<HEAD_SHA>/summary.json` has `status=green`.
- Do not use `--skip-ci-check` after this point unless a new explicit blocker is documented.

**Remote release steps:**

- `python scripts/release_server_to_remote.py --leave-running --smoke-attempts 8 --smoke-delay 5`
- Confirm release script accepts the green CI artifact without bypass.
- Confirm remote status:
  - `python scripts/manage_remote_stack.py status control`
  - `python scripts/manage_remote_stack.py status server`
  - `python scripts/manage_remote_stack.py smoke server`
  - `python scripts/manage_remote_stack.py status agent`
  - `python scripts/manage_remote_stack.py logs server --lines 120`
  - `python scripts/manage_remote_stack.py logs agent --lines 120`

**Browser live checks at `http://192.168.100.17:8666/admin`:**

- Login as admin and open `/app/tickets`.
- Desktop layout checks:
  - `1366x900`, `1600x900`, `1920x1080`.
  - topbar fixed, left/center/right columns independently scroll.
  - no horizontal page overflow.
  - no text overlap in ticket rows, next-action panel, SLA/OLA, tools, observer and passport sections.
- Data checks:
  - `/api/web/support/workspace/summary` returns 200.
  - `/api/web/support/queue` returns 200 and excludes hidden/archived by default.
  - selected `/api/web/support/tickets/{ticket_id}/workspace` returns 200.
  - timeline tab filter request returns 200 or uses aggregate fallback without UI breakage.
- Operator workflow checks:
  - select a ticket from left worklist.
  - `Ещё` menu shows assignment/status/queue/priority/reroute plus hide/archive controls.
  - `Показывать архив` toggles queue reload with `include_archived=1`.
  - right sidebar tabs/accordions switch without losing selected ticket.
  - public/internal composer mode changes labels and lock/internal state clearly.
- Hide/archive safety checks:
  - run only on a safe test/noise ticket or via existing `Скрыть test` cleanup action.
  - hide removes the ticket from active queue.
  - direct workspace detail still opens the hidden ticket and marks its state.
  - archive is admin-only and appears only through explicit control.
  - unhide/unarchive restores visibility.
- Operation/agent checks:
  - agent is running and connected while server is up.
  - low-risk retry action is visible only when the backend marks operation retryable.
  - consent-required retry creates/indicates waiting consent instead of dispatching immediately.
  - operation cards show trace/details links without raw JSON noise.
- Observer checks:
  - support Observer card shows health, root trace or quiet empty state.
  - trace links open `/app/admin/observer` with the intended trace context.
  - browser console has 0 fresh errors/warnings during support and observer navigation.
- Cleanup:
  - save screenshots under Playwright output or diagnostics artifacts.
  - stop server after checks unless the user explicitly asks to keep it running:
    `python scripts/manage_remote_stack.py stop server`
  - confirm `python scripts/manage_remote_stack.py status server` reports stopped/inactive.

**Acceptance:**

- Full green CI artifact exists for final HEAD.
- Remote release runs without `--skip-ci-check`.
- Smoke, server status and agent status are healthy.
- `/app/tickets` passes the browser checklist.
- No fresh browser console errors.
- Server is stopped after signoff unless explicitly kept running.

### P10 Open Product Questions

1. **Hide scope:** global for all support users.
2. **Archive permission:** admin only.
3. **Hard delete:** not needed; do not implement.
4. **Archived visibility:** only when `Показывать архив` is enabled.
5. **Auto-hide rules:** provide a separate cleanup button/action for obvious live/stage/test tickets.
6. **Consent retry:** create `waiting_consent` immediately.

P9 target after completion:

- Typed/backend gap: **0-1%**.
- Backend/domain gap: **1-3%**.
- UI/page polish gap: **1-2%**.

P9 scope:

- Keep ticket access and search behavior unchanged.
- Hide clearly internal navigation artifacts such as `Stage ...`, `Stage27 ...`, `Codex OLA ...`, `Live ...` and `... Test ...` from workspace queue/smart-view navigation.
- Preserve legitimate custom smart views and production queues.
- Verify summary, queue payloads, and workspace regression tests.

P9 functional benefit:

- `/app/tickets` left column becomes operator-focused instead of mixing production work queues with test/stage fixtures.
- Search can still find accessible tickets from internal queues when needed, so this is UI data hygiene rather than permission or routing logic.
- Future support-browser signoff should be easier because noisy one-off queues no longer dominate the sidebar.

P9.1 local verification:

- `python -m pytest server\tests\test_web_support_api.py -k "workspace_summary or internal_navigation_noise or published_custom_smart_view or queue_returns_typed_scope" -q --tb=short` -> `4 passed, 49 deselected`.
- `python scripts\verify_workspace.py` -> passed.
- Live deploy/signoff on `http://192.168.100.17:8666/app/tickets` -> passed after commit `eb83af1`: server smoke passed, Linux agent reconnected and received `handshake_ack`, workspace queues no longer show `Stage...` / `Live...` / `...Test...` navigation artifacts, no horizontal overflow at `1366x900`, and fresh page reload produced `0` console/page errors.

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
