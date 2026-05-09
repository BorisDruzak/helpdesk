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

Overall progress: 82%.

Implemented locally: DB models/migration, backend repo/service/API/signaling, RBAC permissions, audit/timeline writing, resolution-passport summary payload, Maria Agent consent dialog/banner/WebRTC thread, view-only screen track, support workspace request panel/viewer and disabled control-channel architecture. Docs/CODEMAP/Protocol/navigation catalog are synced and local verification passed. Remaining work is deploy/migration on the Linux stand and live browser/WebRTC validation on real devices.

| Level | Scope | Progress | Status |
|---|---|---:|---|
| 0 | Project analysis and plan | 100% | Completed |
| 1 | DB, API, lifecycle, consent, audit | 100% | Implemented and locally verified |
| 2 | Signaling and view-only WebRTC stream | 85% | Implemented, needs live WebRTC validation |
| 3 | Support workspace and Maria Agent UI polish | 80% | Implemented for MVP states, needs browser signoff |
| 4 | Hardening, TURN config, reconnect, timeout | 45% | Token/ICE config and expiry hooks added; reconnect/rate-limit polish remains |
| 5 | Future control-mode architecture | 65% | Disabled data-channel/stub architecture added |

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

Minimum local checks before any completion claim:

```powershell
python scripts/verify_workspace.py
python -m pytest server/tests/test_remote_assist_no_db.py -q --tb=short
python -m pytest pc_agent/tests/test_remote_assist_input_controller.py -q --tb=short
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

## Handoff

Next step: deploy through project scripts, apply migration `071`, run remote smoke/browser checks, then validate a real Maria Agent WebRTC session end to end.
