# Remote Assist MVP Plan

Created: 2026-05-09.

Working mode: Execute / Cross-cutting / Remote Assist.

Change classification: cross-cutting. The feature touches DB schema, server HTTP and WebSocket contracts, Protocol V3 command delivery, Maria Agent Qt UI and WebRTC runtime, support workspace React UI, ticket timeline, resolution passport payload, tests and docs.

## Goal

Implement WebRTC-based Remote Assist through Maria Agent:

ticket -> request remote assist -> user consent -> WebRTC view-only session -> audit -> ticket timeline -> resolution passport.

## Scope

- MVP mode: `view_only` only.
- One user device and one operator per session.
- One primary monitor, no audio, no file transfer, no recording.
- Mouse and keyboard control are represented only by disabled architecture stubs.
- All sessions are bound to `ticket_id`, `device_id`, and operator identity.
- User consent is mandatory for user PCs.
- All significant actions are written to `remote_access_events` and human-readable ticket timeline events.

## Constraints

- Work only in `C:\Users\admin-2\CodexProjects\pc_client`.
- Use existing ticket, device, DeviceOutbox and WS V3 mechanisms where they exist.
- Do not block Maria Agent GUI thread.
- Do not log raw tokens, full SDP or TURN static secrets.
- Do not store or record screen frames.
- Do not implement hidden unattended access.
- Do not implement input control in MVP.
- PostgreSQL migrations are code-only locally; apply migrations on the remote host only through project scripts after deploy.

## Decisions

- `session_id`, `ticket_id`, and `device_id` use the project's current string UUID style.
- Operator/requester identity stays compatible with the current auth model, where actor ids can be non-UUID strings.
- Remote Assist has its own DB lifecycle tables; outbox operations are transport delivery records, not the source of truth for the session.
- Support workspace gets `/api/web/support/...` endpoints for cookie-auth integration, with compatibility endpoints matching the requested `/api/tickets/...` and `/api/remote-assist/...` shapes.
- Signaling uses a dedicated WebSocket endpoint and only relays validated envelopes.
- Maria Agent uses `aiortc` and `mss`; WebRTC and capture run outside GUI work in a dedicated `QThread` with its own asyncio loop.

## Current State

Overall progress: 95%.

Implemented locally: DB models/migration, backend repo/service/API/signaling, RBAC permissions, audit/timeline writing, resolution-passport summary payload, Maria Agent consent dialog/banner/WebRTC thread, view-only screen track, support workspace request panel/viewer and policy-gated interactive-control architecture. Docs/CODEMAP/Protocol/navigation catalog are synced. Linux migration/smoke and a live browser/WebRTC validation through a local Maria Agent completed. Manual ticket `T-000520` testing on local agent `3.1.33` found the release package was missing `aiortc`; Windows stable `3.1.34` fixed WebRTC packaging and video startup. Current stage is Windows stable `3.1.35`: interactive control uses Windows `SendInput`, Linux has a `pynput` backend, support viewer returns to the ticket after operator end, and control state changes are written as human-readable timeline events.

| Level | Scope | Progress | Status |
|---|---|---:|---|
| 0 | Project analysis and plan | 100% | Completed |
| 1 | DB, API, lifecycle, consent, audit | 100% | Implemented and locally verified |
| 2 | Signaling and view-only WebRTC stream | 95% | Implemented and live source smoke validated; 3.1.34 release packaging hotfix in progress |
| 3 | Support workspace and Maria Agent UI polish | 90% | Implemented and live consent/viewer flow validated; release packaging in progress |
| 4 | Hardening, TURN config, reconnect, timeout | 50% | Token/ICE config, expiry hooks, viewer timeout and agent failure reporting added; reconnect/rate-limit polish remains |
| 5 | Future control-mode architecture | 85% | Policy-gated interactive control added for testing; file/clipboard/elevated/unattended remain gated |

## Implementation Plan

### Level 1: Remote Assist Core

- Add ORM models and Alembic migration for `remote_access_sessions` and `remote_access_events`.
- Add `RemoteAccessRepo`.
- Add `RemoteAssistService` for request, approve, deny, end, expire, audit and ticket timeline events.
- Add RBAC permissions `remote_assist.request` and `remote_assist.view`.
- Add HTTP handlers and routes for request, approve, deny, viewer info, status, list and end.
- Send `remote_assist.request` through existing DeviceOutbox / WS V3 command delivery.
- Add Maria Agent command handling for `remote_assist.request`.
- Show a non-blocking consent dialog in Maria Agent and call backend approve/deny.
- Add support workspace request button/modal and waiting/denied/expired states.

### Level 2: WebRTC MVP

- Add signaling WebSocket `/ws/remote-assist/{session_id}?role=operator|agent&token=...`.
- Add short-lived role tokens hashed in DB.
- Add browser viewer with `RTCPeerConnection`, remote video, ICE candidate exchange and reserved disabled `control` data channel.
- Add agent `RemoteAssistWebRTCClient` with `aiortc`.
- Add `ScreenCaptureTrack` using `mss`, capped to 1280x720 and 5 fps.
- Support status transitions `approved -> starting -> active -> ended/failed`.
- Add end-session from operator and user.

### Level 3: UI And Ticket Integration

- Add human-readable remote assist timeline cards.
- Add support viewer states: waiting, connecting, active, ended, failed.
- Add Maria Agent active banner with "Завершить доступ".
- Add resolution passport summary fields in passport payload.

### Level 4: Production Hardening

- Add ICE/TURN config and coturn REST-style short-lived credential support.
- Add consent timeout and max active duration expiration.
- Add reconnect and connection health states.
- Add signaling message size limits and ICE flood guard.
- Add complete error taxonomy in service and UI.

### Level 5: Future Control Architecture

- Create disabled `InputController` stubs.
- Define control channel message schema.
- Keep UI mode locked to `view_only`.
- Do not inject keyboard or mouse input in MVP.

## Verification

Executed locally on 2026-05-09:

```powershell
python -m py_compile scripts\navigation_catalog.py server\remote_assist\service.py server\remote_assist\handlers.py server\remote_assist\signaling.py server\app\repos\remote_access_repo.py server\app\db\models.py server\routes.py server\tickets\passport_service.py pc_agent\remote_assist\webrtc_client.py pc_agent\remote_assist\thread.py pc_agent\remote_assist\screen_track.py pc_agent\remote_assist\input_controller.py pc_agent\ui_gui\remote_assist_dialog.py pc_agent\ui_gui\main_window.py pc_agent\ws_agent.py
python -m pytest server\tests\test_remote_assist_no_db.py -q --tb=short
python -m pytest pc_agent\tests\test_remote_assist_input_controller.py -q --tb=short
python scripts\bootstrap_web_toolchain.py
pnpm --dir webapp run build
python scripts\verify_workspace.py
python scripts\build_context_index.py --force
```

Executed on 2026-05-10:

```powershell
python scripts/run_ci_suite.py --commit 5fbc0a6eee71f8fe36bf2b55ad5bde09d4c48fe1
python -m py_compile pc_agent/ws_agent.py pc_agent/ui_gui/main_window.py
python -m pytest pc_agent/tests/test_remote_assist_input_controller.py pc_agent/tests/test_main_window_runtime_windows.py
python scripts/verify_workspace.py
```

Live validation on 2026-05-10:

- Deployed the Remote Assist MVP to the Linux stand and applied migration `071`.
- Started a local Maria Agent source instance, created a test ticket, delivered `remote_assist.request`, approved consent, completed WebRTC offer/answer/ICE exchange, received a browser video track, and ended the session cleanly.
- Fixed and committed the two agent-side runtime issues found during smoke: `ws_agent.py` local `datetime` shadowing and retained/topmost Qt consent dialogs.

Manual failure checkpoint on 2026-05-10:

- Ticket `T-000520` reached the viewer but stayed at "Ожидаем видео с устройства...".
- Local agent `3.1.33` log showed `Remote Assist WebRTC failed: No module named 'aiortc'`.
- Fix: package `aiortc`, `aioice`, `av` and `pylibsrtp` in both Windows PyInstaller specs, add `/remote-assist/{session_id}/fail`, have Maria Agent report WebRTC startup failure, and add a viewer timeout instead of indefinite waiting.

Current release checkpoint:

- Bump Windows agent to `3.1.34`.
- Run `python scripts/verify_workspace.py`.
- Run `python -m pytest pc_agent/tests/ -v --tb=short`.
- Build with `python pc_agent/build_windows_release_v2.py` (done after installing missing build-env WebRTC dependencies; ZIP SHA256 `cacdc328ab654c8bdf5b35b2a7a0cc07b574df2e60b09da2238944f5caf8ca1e`).
- Confirm `pc_agent/dist/release/windows_amd64/stable/3.1.34/install/versions/3.1.34/pc_agent.exe` has bundled WebRTC/ICE/media dependencies (done: `av.libs`, `pylibsrtp`, `google_crc32c`, `python314.dll` present in ZIP; PyInstaller no longer reports missing `aiortc`, `av` or `pylibsrtp`).
- Upload `pc_agent/dist/release/windows_amd64/stable/3.1.34/pc_agent-windows_amd64-3.1.34.zip`.
- Canary one launcher-based local agent and verify handshake/update status before any bulk rollout.

Interactive-control release checkpoint on 2026-05-10:

- Bump Windows agent to `3.1.35`.
- Replace Windows Remote Assist control injection with `SendInput`; remove `mouse_event`/`keybd_event` usage from the Remote Assist path.
- Add Linux `pynput` input backend behind the same `interactive_control` policy gate.
- Add support viewer behavior: operator "Завершить" ends the session, refreshes ticket data and closes the viewer back to the ticket.
- Add timeline/system messages for `control_enabled`, `control_disabled`, `control_rejected`.
- Build Windows release `3.1.35`; ZIP SHA256 `770283c156dc6247fa4c3e1941991dd4831560a67846c579e1df9e823fadf508`.
- Upload `windows_amd64/stable/3.1.35` and assign rollout policy.
- Local launcher agent `remote-assist-fulltest-3135b` started on device `7a3429ec-1c0b-5495-9aad-b284f08ae965` and received `handshake_ack` as `3.1.35`.

Minimum local checks before any completion claim:

```powershell
python scripts/verify_workspace.py
python -m pytest server/tests/test_remote_assist_no_db.py -q --tb=short
python -m pytest pc_agent/tests/test_remote_assist_input_controller.py -q --tb=short
pnpm -C webapp test -- remote-assist-viewer
python scripts/bootstrap_web_toolchain.py
pnpm --dir webapp run build
```

Browser and live checks after local verification:

```powershell
python scripts/deploy_workspace_to_remote.py
python scripts/run_remote_migrations.py upgrade head
python scripts/manage_remote_stack.py start server
python scripts/manage_remote_stack.py smoke server
```

Then verify through `http://192.168.100.17:8666/admin` and stop the server unless explicitly asked to leave it running:

```powershell
python scripts/manage_remote_stack.py stop server
```

## Post-MVP Expansion

Goal: move Remote Assist from view-only MVP to a controlled support tool without creating hidden access paths.

Non-negotiable safety rule: no hidden unattended access. Any unattended capability must be explicit, policy-backed, enrolled per device, visible in audit, scoped to ticket/device/operator, and revocable. User PCs keep consent by default.

### Phase A: Policy And Contracts

- [x] Add mode permissions: `remote_assist.control`, `remote_assist.file_transfer`, `remote_assist.clipboard`, `remote_assist.elevated`, `remote_assist.unattended`.
- [x] Replace hard-coded `mode == view_only` checks with a mode policy table.
- [x] Add per-mode consent semantics:
  - `view_only`: consent required for user devices.
  - `interactive_control`: consent required and dialog text must say mouse/keyboard control.
  - `file_transfer`: separate explicit consent before any transfer.
  - `clipboard`: separate explicit consent before read/write.
  - `elevated_admin`: separate explicit consent and no silent UAC bypass.
  - `unattended`: only for enrolled managed devices when server policy allows it; never for ordinary user PCs by default.
- [x] Extend Remote Assist event taxonomy for `control_enabled`, `control_disabled`, and `control_rejected`.
- [ ] Extend Remote Assist event taxonomy for `file_transfer_*`, `clipboard_*`, `elevation_*`, `unattended_policy_*`, `reconnect_*`, `turn_credentials_issued`.

### Phase B: Interactive Control

- [x] Enable RTCDataChannel `control` only for `interactive_control` sessions.
- [x] Browser sends normalized mouse/keyboard messages only when operator explicitly enables control.
- [x] Maria Agent validates mode/session/control state before injecting input.
- [x] Windows input injection uses a small isolated `InputController` backed by `SendInput`; Linux uses `pynput` when an interactive-control session is policy-enabled.
- [x] Add active banner text that distinguishes viewing from controlling.
- [x] Audit `control_enabled`, `control_disabled`, and rejected control messages.

### Phase C: File Transfer And Clipboard

- Add dedicated `file` data channel or typed `file.*` messages with size limits, filename sanitization, destination policy and checksum.
- Add per-transfer consent in Maria Agent before saving any file.
- Add clipboard request/write messages with separate consent and payload limits.
- Do not expose clipboard/file actions in UI until the corresponding session mode is approved.

### Phase D: Elevated/Admin Mode

- Add `elevated_admin` as a requested support mode with separate consent.
- On Windows, request elevation only through visible OS/User approval; do not bypass UAC.
- Surface unsupported state clearly when agent is not running elevated or the platform cannot elevate.

### Phase E: Managed Unattended

- Add server-side enrollment/policy gate for managed devices.
- Only allow unattended when `REMOTE_ASSIST_ALLOW_UNATTENDED=true`, device enrollment allows it, operator has `remote_assist.unattended`, and ticket/device/operator audit exists.
- Show persistent agent-side visibility indicator when an unattended session is active if GUI/tray is available.
- Keep unattended disabled by default in config and tests.

### Phase F: Production TURN/Reconnection

- [x] Implement coturn REST-style short-lived credentials from server-only shared secret.
- [ ] Add signaling reconnect tokens with bounded resume windows.
- [ ] Add connection health state and operator/agent reconnect UI.
- [ ] Add rate limits for ICE/control/file messages and max active duration watchdog.

## Handoff

Current checkpoint: Phase A server policy/contracts and Phase B interactive mouse/keyboard control are implemented locally behind explicit config/RBAC gates. `view_only` remains the only enabled mode by default. File transfer, clipboard, elevated/admin and managed unattended remain policy-gated but not transport-complete. Reconnection hardening still needs bounded resume tokens, UI reconnect state, and rate-limit watchdog work.

---

# Agent Updates React UI Plan

Created: 2026-05-10.

Working mode: Execute / Boundary + Release-control.

Change classification: boundary/release-control. The change exposes the existing agent build registry and rollout policy in the React `/app/admin` workspace, then uses the existing server-side rollout policy to make Windows stable `3.1.34` the preferred agent version on the live stand.

## Goal

Add a production-ready React admin page for agent builds and rollout policy:

- `/app/admin/agent-updates` shows the agent build registry.
- Admin can upload, download and delete builds.
- Admin can assign or clear rollout policy per target.
- Inventory and device pages have explicit navigation into Agent Updates.
- Device/update context clearly shows current version, target rollout, recommended build and last update status.
- The live stand should have `windows_amd64/stable/3.1.34` assigned as the preferred rollout version.

## Scope

- Reuse existing endpoint implementations through web-session aliases:
  - `GET /api/web/admin/agent-builds`
  - `POST /api/web/admin/agent-builds/upload`
  - `DELETE /api/web/admin/agent-builds/{target}/{channel}/{version}`
  - `GET /api/web/admin/agent-builds/{target}/{channel}/{version}/download`
  - `GET /api/web/admin/agent-updates/rollout-policy`
  - `PATCH /api/web/admin/agent-updates/rollout-policy`
- Keep legacy token endpoints available for agents/scripts/legacy admin:
  - `GET /api/agent_builds`
  - `POST /api/agent_builds/upload`
  - `DELETE /api/agent_builds/{target}/{channel}/{version}`
  - `GET /api/agent_builds/{target}/{channel}/{version}/download`
  - `GET /api/agent_updates/rollout_policy`
  - `PATCH /api/agent_updates/rollout_policy`
  - existing typed device update endpoints under `/api/web/admin/devices/{device_id}/updates`
- Add frontend API adapter/types under `webapp/src/features/agent-updates`.
- Add React page and route under `/app/admin/agent-updates`.
- Add sidebar item and quick links from inventory/device pages.
- No new DB schema unless an existing endpoint cannot satisfy the page.
- No per-device persistent preferred version in this slice; current contract stays target-level rollout policy.

## Constraints

- Work only in `C:\Users\admin-2\CodexProjects\pc_client`.
- Keep rollout source of truth in existing server policy by target.
- Do not duplicate legacy `/admin` business logic in backend; React uses typed web aliases that delegate to the existing build/rollout handlers and accept the web cookie session.
- Do not delete builds assigned to rollout; backend already blocks this and UI must explain it.
- Deploy through project release/deploy scripts only.

## Current State

Progress: 85%.

The React page, route, navigation and inventory/device deep links are implemented and committed once. First live check after deploy found that direct legacy `/api/agent_builds*` and `/api/agent_updates/rollout_policy` reject the React web cookie session with 401. The fix is in progress: `/api/web/admin/agent-builds*` and `/api/web/admin/agent-updates/rollout-policy` aliases now delegate to the existing handlers under `@require_auth("admin")`, and the frontend has been moved to those aliases.

## Implementation Plan

1. [done] Add typed agent update API client for builds, rollout policy, upload, delete and assign/clear policy.
2. [done] Add `AgentUpdatesPanel` with:
   - build list grouped by target/channel;
   - summary tiles for targets, assigned rollout and latest versions;
   - upload form;
   - assign rollout / clear rollout controls;
   - download and guarded delete actions;
   - loading, error and empty states.
3. [done] Add `/app/admin/agent-updates` route, lazy page and navigation item.
4. [done] Add quick links:
   - inventory panel/button to Agent Updates;
   - device page quick action to Agent Updates with selected target context when possible.
5. [done] Add focused tests for API aliases and route/sidebar visibility where practical.
6. [in progress] Run local checks:
   - `python scripts/verify_workspace.py`
   - `pnpm --dir webapp run build`
   - focused webapp tests if touched.
7. [pending] Commit the web-session alias fix locally.
8. [pending] Deploy the fix to Linux stand, run smoke and browser check at `http://192.168.100.17:8666/admin`.
9. [pending] Upload or confirm `windows_amd64/stable/3.1.34`, then set rollout policy to `3.1.34`.
10. [pending] Verify via API and React page that `3.1.34` is assigned.

## Verification

Latest local checks:

```powershell
python -m pytest server/tests/test_web_admin_api.py -k "agent_builds_alias or agent_rollout_policy_alias" -q
pnpm --dir webapp run build
```

Pending after alias fix:

```powershell
python scripts/verify_workspace.py
pnpm --dir webapp run build
python scripts/release_server_to_remote.py --leave-running
python scripts/manage_remote_stack.py smoke server
```

Live browser verification:

- Open `http://192.168.100.17:8666/admin`.
- Navigate to `/app/admin/agent-updates`.
- Confirm build registry loads.
- Confirm `windows_amd64/stable/3.1.34` is visible.
- Confirm rollout policy shows `3.1.34` assigned.
- Open inventory and device page and confirm Agent Updates links.

## Handoff

Current next step: run full workspace verification, commit the web-session alias fix and Remote Assist WebRTC hotfix, deploy the new commit to Linux, verify `/app/admin/agent-updates` loads builds/policy without 401, then set `windows_amd64/stable/3.1.34` as live preferred rollout.
