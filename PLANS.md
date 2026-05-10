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

Overall progress: 98%.

Implemented locally: DB models/migration, backend repo/service/API/signaling, RBAC permissions, audit/timeline writing, resolution-passport summary payload, Maria Agent consent dialog/banner/WebRTC thread, view-only screen track, support workspace request panel/viewer and policy-gated interactive-control architecture. Docs/CODEMAP/Protocol/navigation catalog are synced. Linux migration/smoke and a live browser/WebRTC validation through a local Maria Agent completed. Manual ticket `T-000520` testing on local agent `3.1.33` found the release package was missing `aiortc`; Windows stable `3.1.34` fixed WebRTC packaging and video startup. Windows stable `3.1.35` added interactive-control testing with Windows `SendInput`, Linux `pynput`, ticket return after operator end, and timeline control events. Windows stable `3.1.36` added explicit video transceiver setup, viewer/agent WebRTC connection timeouts, failed-session audit, agent-side state logs, and lower-leak cleanup after failed negotiation. Windows stable `3.1.44` adds ICE gathering diagnostics and waits for ICE gathering before sending browser offer / agent answer. Field ticket `T-000531` failed without TURN because the deployed server returned `ice_servers=[]`; coturn is now installed on the Linux stand and backend `.env` returns STUN/TURN entries with short-lived HMAC credentials for new sessions. Windows stable `3.1.45` added selectable quality profiles, actual-size viewer mode, automatic interactive-control activation for approved `interactive_control` sessions, drag/wheel/shortcut input messages, and policy-gated text clipboard auto-sync over the WebRTC data channel. `3.1.46` fixed clipboard data-channel routing and hardened Windows foreground input injection. `3.1.47` added agent-side WSS trust for the HTTPS stand. `3.1.48` fixed field video/control reliability: capture cannot freeze indefinitely on a stuck `mss.grab()`, the viewer detects stalled video frames, and Windows mouse control uses `SetCursorPos` before clicks/wheel events for RDP/virtual-display reliability. Current `3.1.49` work fixes Remote Assist input/session lifecycle: control messages are processed sequentially, browser single/double-click/drag events are translated explicitly, user-side end is pushed to the operator viewer, and a smooth 1280x720@15fps profile is available for more responsive sessions. Follow-up RBAC hotfix grants default support operators `remote_assist.clipboard` and gates the checkbox by effective session permissions so clipboard requests no longer fail with `PERMISSION_DENIED` before a session is created. Current stand-hardening slice adds HTTPS without DNS for browser secure-context testing: a local CA signs an IP-SAN server certificate for `192.168.100.17`, an aiohttp-based TLS reverse proxy listens on `9443` and forwards HTTP/WSS to `127.0.0.1:8666`, and remote `SERVER_PUBLIC_BASE_URL` switches to `https://192.168.100.17:9443`. Final production must replace this with DNS plus a managed reverse proxy/certificate path.

| Level | Scope | Progress | Status |
|---|---|---:|---|
| 0 | Project analysis and plan | 100% | Completed |
| 1 | DB, API, lifecycle, consent, audit | 100% | Implemented and locally verified |
| 2 | Signaling and view-only WebRTC stream | 96% | Offer/answer path verified in field; ICE failure now fails cleanly instead of hanging |
| 3 | Support workspace and Maria Agent UI polish | 92% | Agent banner now distinguishes connecting from active screen visibility |
| 4 | Hardening, TURN config, reconnect, timeout | 75% | Token/ICE config, coturn on stand, short-lived TURN credentials, expiry hooks, viewer and agent timeouts, failed-state audit and cleanup added; reconnect/rate-limit polish remains |
| 5 | Full assist features | 70% | Quality profiles, production mouse/keyboard UX, text clipboard auto-sync and Windows elevated/admin helper are implemented and rolled out to the stand; file transfer and managed unattended remain policy-gated but not transport-complete |

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

Connection-hardening release checkpoint on 2026-05-10:

- Bump Windows agent to `3.1.36`.
- Add explicit browser recvonly video transceiver before WebRTC offer.
- Add viewer timeout cleanup that closes signaling/peer connection and calls `/fail`.
- Add agent WebRTC connection timeout and state logs.
- Keep Maria Agent banner in connecting state until ICE connected.
- Reuse `mss` capture context across frames to reduce capture overhead.
- Mark backend session failed when peer connection reports failed.
- Build Windows release `3.1.36`; ZIP SHA256 `05d757ed07ffa3d79a8fc836b008a6c48b5afb22320ab5248542b510c8e7ca58`.
- Upload `windows_amd64/stable/3.1.36` and assign rollout policy.
- Confirm update recommendation for device `15c8f029-bd7d-533b-a11e-dcd6c2ff48ab` returns `recommended_version=3.1.36`.

Field bug checkpoint on 2026-05-10:

- Agent `15c8f029-bd7d-533b-a11e-dcd6c2ff48ab`, session `d0ab7df5-9ba7-4072-a876-98049487ed64`: `remote_access_events` contain `signaling_connected_agent`, `signaling_connected_operator`, `offer_received`, two operator `ice_candidate_received`, and `answer_received`.
- The same session stays `status=starting`, `started_at=null`, with no `ice_connected` or `session_started`; viewer reports no video.
- Root-cause boundary: consent and signaling delivery work, but WebRTC ICE/media never reaches connected. Current deployment also has `ice_servers=[]`, so direct host-candidate connectivity is the only path and can fail through firewall/NAT.
- Secondary CPU issue: before this fix, viewer timeout did not close `RTCPeerConnection`/signaling or mark the session failed, so the agent could keep screen capture/VP8 work after the operator UI had already shown an error.
- Local fix in progress: explicit recvonly video transceiver in browser offer, viewer fail cleanup and `/fail`, agent connection timeout/failure reporting, server failed-state handling, more agent WebRTC logs, and persistent `mss` capture context to reduce per-frame overhead.

Clipboard/control hotfix checkpoint on 2026-05-10:

- Ticket `T-000531`, latest session `b3ca997c-b15c-4c76-b2cc-07727425bfb8`, reached `active` and ended cleanly, but stored `ice_config.features.clipboard_auto_sync=false` while the server global feature flag exposed `features.clipboard=true`.
- Agent code had a concrete routing bug for sessions where clipboard is enabled: browser sends `clipboard_enable`, but `RemoteAssistWebRTCClient` only routed `clipboard.*` messages to `ClipboardSyncBridge`; the enable message therefore fell through to `InputController` and was rejected as a control message.
- `3.1.46` hotfix scope:
  - route `clipboard_enable` and `clipboard_disable` to the clipboard bridge;
  - keep `InputController` rejection explicit for clipboard/file messages that reach the wrong handler;
  - add sanitized control/clipboard accept/reject logs without clipboard contents;
  - harden Windows `SendInput` by attaching the worker thread to the current foreground input queue before injection and logging `GetLastError` on partial injection;
  - make support request state use refs so the clipboard checkbox/mode values cannot be lost by a quick submit after UI interaction.

Video/control field fix checkpoint on 2026-05-10:

- Ticket `T-000531`, session `09a0c80c-fc34-4b9b-a8f7-b323f4b6829f`, reached `active` and ended cleanly, while the operator observed a frozen image with a still-working control channel. Root-cause boundary: signaling/ICE/data channel stayed alive, but the agent capture path had no timeout or frame watchdog around `mss.grab()`, so a stalled capture call could leave the viewer with the last decoded frame indefinitely.
- Fix scope for `3.1.48`:
  - move screen capture to a dedicated single-worker executor with per-frame timeout and worker replacement;
  - show visible fallback frames while capture retries instead of leaving the previous remote frame frozen;
  - add viewer-side stalled-video detection so a live data channel with no video frames becomes an explicit failure instead of an apparently active frozen session;
  - make Windows mouse injection call `SetCursorPos` before clicks, button events and wheel events, while keeping `SendInput` for the actual button/keyboard injection.

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

HTTPS stand verification slice:

```powershell
python -m py_compile scripts\run_https_reverse_proxy.py
python scripts/deploy_workspace_to_remote.py --allow-local-dirty
curl.exe --cacert artifacts\stand_https\pc_client_stand_root_ca.cer https://192.168.100.17:9443/api/health
```

Operator and Maria Agent Windows machines must trust `artifacts\stand_https\pc_client_stand_root_ca.cer` while this no-DNS self-signed stand setup is active; otherwise browsers/agents can reject WebRTC clipboard secure context or HTTPS update downloads.

## Post-MVP Expansion

Goal: move Remote Assist from view-only MVP to a controlled support tool without creating hidden access paths.

Non-negotiable safety rule: no hidden unattended access. Any unattended capability must be explicit, policy-backed, enrolled per device, visible in audit, scoped to ticket/device/operator, and revocable. User PCs keep consent by default.

Post-MVP consent model update:

- The operator chooses the requested session mode before creating the request.
- Maria Agent shows one consent dialog that describes the exact requested mode and capabilities.
- `view_only` consent text says the specialist can see the screen.
- `interactive_control` consent text says the specialist can see the screen and control mouse/keyboard.
- Clipboard auto-sync and file transfer must be declared in the initial request when enabled for the session.
- Escalating an active `view_only` session to control, clipboard, file transfer or elevated/admin is not allowed without ending the session and requesting a new mode.

Execution slices, in order:

1. Quality/settings slice: selectable quality profile (`balanced`, `sharp`, `fast`), max resolution, FPS, scale-to-fit vs actual-size viewer, and monitor metadata groundwork.
2. Control slice: production mouse/keyboard UX for `interactive_control`, focus capture, drag/select, wheel, common shortcuts, control status/audit and clear user banner text.
3. Clipboard auto-sync slice: bidirectional clipboard sync over the WebRTC data channel for text payloads first, enabled only when the initial session policy allows it, with size limits, loop prevention, privacy indicator and audit counters/events.
4. File transfer slice: explicit file channel, size limits, checksum, filename sanitization, progress UI and ticket audit.
5. Elevated/admin slice: explicit `elevated_admin` mode with visible user consent, no silent UAC bypass, and clear failure states when elevation is unavailable.
6. Managed unattended slice: enrollment-only policy for managed devices, disabled by default for ordinary user PCs.
7. Reconnect/production slice: bounded reconnect/resume, quality downgrade on packet loss, TURN health warnings and rate-limit watchdogs.

### Phase A: Policy And Contracts

- [x] Add mode permissions: `remote_assist.control`, `remote_assist.file_transfer`, `remote_assist.clipboard`, `remote_assist.elevated`, `remote_assist.unattended`.
- [x] Replace hard-coded `mode == view_only` checks with a mode policy table.
- [x] Add per-mode consent semantics:
  - `view_only`: consent required for user devices.
  - `interactive_control`: consent required before session start and dialog text must say mouse/keyboard control.
  - `file_transfer`: must be declared in the initial requested mode/capability set before any transfer is available.
  - `clipboard`: must be declared in the initial requested mode/capability set before auto-sync or manual clipboard actions are available.
  - `elevated_admin`: consent required before session start and no silent UAC bypass.
  - `unattended`: only for enrolled managed devices when server policy allows it; never for ordinary user PCs by default.
- [x] Extend Remote Assist event taxonomy for `control_enabled`, `control_disabled`, and `control_rejected`.
- [ ] Extend Remote Assist event taxonomy for `file_transfer_*`, `clipboard_*`, `elevation_*`, `unattended_policy_*`, `reconnect_*`, `turn_credentials_issued`.

### Phase B0: Quality And Viewer Ergonomics

- [x] Add session request fields for quality profile: `quality_profile`, `max_width`, `max_height`, `fps`, and `monitor_id`.
- [x] Keep defaults conservative: `balanced`, 1600x900, 8 fps.
- [x] Add support viewer controls: fit to window, actual size, fullscreen, reconnect, quality selector.
- [x] Add agent-side `ScreenCaptureTrack` options from approved session metadata instead of hard-coded 1280x720/5 fps.
- [ ] Add audit event `quality_changed` when the operator changes quality during a session.

### Phase B: Interactive Control

- [x] Enable RTCDataChannel `control` only for `interactive_control` sessions.
- [x] Browser sends normalized mouse/keyboard messages only when operator explicitly enables control.
- [x] Maria Agent validates mode/session/control state before injecting input.
- [x] Windows input injection uses a small isolated `InputController` backed by `SendInput`; Linux uses `pynput` when an interactive-control session is policy-enabled.
- [x] Add active banner text that distinguishes viewing from controlling.
- [x] Audit `control_enabled`, `control_disabled`, and rejected control messages.
- [x] Remove the extra in-session "enable control" consent concept: control is available when the approved session mode is `interactive_control`; the viewer may still have a local pause/resume toggle for operator ergonomics.
- [x] Add drag/select, right/middle click, mouse wheel and common keyboard shortcuts. Double click is now sent as an explicit `mouse_click` with `click_count=2` and processed sequentially on the agent to avoid fast down/up reordering.
- [x] Preserve native remote `Ctrl+C` / `Ctrl+V` behavior through keyboard control even when clipboard auto-sync is disabled.
- [x] Add a smoother Remote Assist request profile (`smooth`: 1280x720 at 15 fps) and make it the support-workspace default for more responsive control sessions.
- [x] Push `session.end` to the operator viewer when the user presses "Завершить доступ" in Maria Agent, including sessions ended via the HTTP endpoint rather than signaling only.
- [ ] Elevated/admin control remains a separate mode: normal `interactive_control` cannot inject into elevated Windows surfaces such as Task Manager because of UIPI/session integrity boundaries.

### Phase C: File Transfer And Clipboard

- [ ] Add dedicated `file` data channel or typed `file.*` messages with size limits, filename sanitization, destination policy and checksum.
- [ ] Add per-transfer confirmation in Maria Agent before saving any file unless session policy explicitly enables trusted transfer.
- [x] Add clipboard auto-sync for text payloads over the control/data channel when the initial session capability includes clipboard.
- [x] Add clipboard loop prevention with origin ids/content hash debounce.
- [x] Add clipboard limits from config, defaulting to text-only and `REMOTE_ASSIST_CLIPBOARD_MAX_BYTES`.
- [x] Show clipboard sync state in the support viewer and consent text in Maria Agent.
- [x] Write audit events for clipboard sync enabled/disabled and sync error; never log clipboard contents. Direction counters remain a follow-up.
- [x] Do not expose clipboard/file actions in UI until the corresponding session capability is approved.

### Phase D: Elevated/Admin Mode

- Add `elevated_admin` as a requested support mode declared in the initial consent prompt.
- On Windows, request elevation only through visible OS/User approval; do not bypass UAC.
- Surface unsupported state clearly when agent is not running elevated or the platform cannot elevate.

Current Windows helper slice:

- [x] Enable `elevated_admin` as a control-capable Remote Assist mode behind `remote_assist.elevated` and `REMOTE_ASSIST_ELEVATED_ADMIN_ENABLED`.
- [x] Add a Windows-only elevated helper path inside `pc_agent.exe` via `--remote-assist-elevated-helper`; launch it with UAC through `ShellExecuteW(..., "runas", ...)`.
- [x] Keep the helper session-scoped: one loopback connection, one high-entropy token, no server connectivity, no hidden unattended start.
- [x] Route `elevated_admin` input through the helper while leaving normal `interactive_control` unchanged.
- [x] Surface the mode in support UI only to operators with `remote_assist.elevated`; Maria Agent consent text must explicitly mention UAC/admin windows.
- [x] Verify with unit tests, webapp build, package build, then roll out as Windows stable `3.1.50`.

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

Current checkpoint: Phase B0 quality/viewer ergonomics, production interactive-control UX, Phase C text clipboard auto-sync and Phase D Windows `elevated_admin` helper are implemented, committed, deployed to the stand and rolled out as agent `3.1.50` to `AD-MAIN`. TURN is configured on the Linux stand and `T-000531` successfully starts a session after coturn setup. Next execution slice is file transfer, then managed unattended and reconnect/rate-limit hardening. Clipboard auto-sync depends on browser Clipboard API availability, so full automatic operator-side OS clipboard sync requires a secure browser context/HTTPS and browser permission.

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

Current next step: commit and deploy the `3.1.49` Remote Assist input/session lifecycle slice, build/upload the Windows agent release, roll it out to `AD-MAIN`, then run a live `T-000531` browser check for smooth profile video, explicit double-click, normal-window input, and user-side end returning the operator viewer to the ticket.

---

# Release Gate Acceleration Plan

Created: 2026-05-10.

Working mode: Release-control.

Change classification: release-control. The change formalizes a fast staging deploy gate while keeping the existing full CI artifact requirement for final release/push.

## Goal

Make deploy iterations faster without normalizing unverified releases:

- `--gate full` remains the default and requires a green CI artifact for the current commit.
- `--gate quick` is an explicit staging/iteration mode that skips only the full-CI artifact gate.
- Project rules document that GitHub push/final release still require full CI.

## Implementation Plan

1. [done] Add failing tests for quick/full gate behavior in release/deploy scripts.
2. [done] Add `--gate full|quick` to `scripts/release_server_to_remote.py`.
3. [done] Add `--gate full|quick` to `scripts/deploy_workspace_to_remote.py`.
4. [done] Keep `--skip-ci-check` as an emergency compatibility alias for quick gate.
5. [done] Update AGENTS/workflow/testing/navigation docs with quick-vs-full rules.
6. [done] Run focused script tests and workspace verification.

## Verification

Required before completion:

```powershell
python -m pytest scripts/test_release_server_to_remote.py scripts/test_deploy_workspace_to_remote.py scripts/test_task_intake.py -q
python scripts/verify_workspace.py
```

Latest local checks:

```powershell
python -m pytest scripts/test_release_server_to_remote.py scripts/test_deploy_workspace_to_remote.py scripts/test_task_intake.py scripts/test_run_ci_suite.py -q
python scripts/verify_workspace.py
```

---

# DB Fixture Optimization Plan

Created: 2026-05-10.

Working mode: Test / release-control.

Change classification: local test harness with release-control impact. The goal is to reduce `server_pytest_db_api` wall time without weakening DB test isolation.

## Goal

Reduce full CI time in layers:

- Move pure server tests out of the DB/API layer with explicit `pytest.mark.no_db`.
- Avoid repeated failed `pg_terminate_backend` attempts when shared test DB admin privileges are unavailable.
- Treat scoped DB cleanup as the next planned layer, not as an opportunistic same-change refactor.

## Current Findings

Latest green CI artifact `e47215ceb4e8b9bb386a985a3fc383a13ae3f177`:

- Full CI wall time: about 49.6 minutes.
- `server_pytest_db_api`: `2522.8s`, about 42 minutes.
- DB/API layer: 525 tests.
- 145 tests in that layer had no explicit DB fixture and totaled about `328s`.

## Implementation Plan

1. [done] Add coverage that selected pure server test modules must be module-level `no_db`.
2. [done] Mark the first safe pure modules as `pytestmark = pytest.mark.no_db`.
3. [done] Add coverage that shared DB terminate-backend failures are cached.
4. [done] Cache shared test DB terminate-backend unavailability in `server/tests/conftest.py`.
5. [pending] Next layer: design scoped cleanup markers/profiles before changing per-test `TRUNCATE`.

## Next Layer: Scoped Cleanup Design

Do not replace global cleanup blindly. First introduce explicit cleanup profiles and prove each profile covers all tables touched by its tests.

Candidate profiles:

- `tickets_db`: tickets, ticket_events, ticket queues/policies/passport/worklogs/evidence.
- `observer_db`: observer_traces/spans/signatures/occurrences, operations, device/ticket events used as trace sources.
- `modules_db`: modules, device_modules, desired modules, toolset snapshots, server_config preferred assignments.
- `auth_registry_db`: devices, agent_tokens, connection_requests, registry tables, access-control tables.

Required safety work before implementation:

- Add a marker such as `@pytest.mark.db_profile("tickets")`.
- Make unprofiled DB tests keep the current full cleanup.
- Add a guard test that every profile's table list includes foreign-key dependents needed for `TRUNCATE ... CASCADE`.
- Roll out profile by profile, measuring wall time after each batch.

## Verification

Required for this phase:

```powershell
python -m pytest server/tests/test_ci_pytest_layers_no_db.py server/tests/test_shared_test_db_harness.py -q
python -m pytest server/tests/test_tech_alert_rules_unit.py server/tests/test_ticket_notification_policy.py server/tests/test_requester_timeline_projection.py server/tests/test_runtime_control.py server/tests/test_remote_assist_no_db.py server/tests/test_support_knowledge_provider.py -q
python scripts/verify_workspace.py
```

Latest local checks:

```powershell
python -m pytest server/tests/test_ci_pytest_layers_no_db.py server/tests/test_shared_test_db_harness.py -q
python -m pytest server/tests/test_tech_alert_rules_unit.py server/tests/test_ticket_notification_policy.py server/tests/test_requester_timeline_projection.py server/tests/test_runtime_control.py server/tests/test_remote_assist_no_db.py server/tests/test_support_knowledge_provider.py -q
python -m pytest server/tests/test_tech_alert_rules_unit.py server/tests/test_ticket_notification_policy.py server/tests/test_requester_timeline_projection.py server/tests/test_runtime_control.py server/tests/test_remote_assist_no_db.py server/tests/test_support_knowledge_provider.py -m no_db --collect-only -q
python -m pytest server/tests -m "not manual and no_db" -q
python -m pytest server/tests -m "not manual and not no_db and not agent_ws" --collect-only -q
python scripts/verify_workspace.py
```

Measured effect after this phase:

- Selected pure files: 52 tests collect under `-m no_db`.
- Server `no_db` layer: 208 passed, 503 deselected in 1.46s.
- DB/API collection: 473 selected, down from 525 in the latest green CI artifact.

