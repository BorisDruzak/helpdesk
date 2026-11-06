# Notification attention fixes

Goal: correct notification distractions and read clearing, and explain browser opt-in after login. Continue the user-authorized current staging deployment; preserve unrelated shared work.

Design: unread-only bell via the existing query flag; keep durable history. A ready chat declares its ticket in the DOM. A shared authenticated-shell hook marks only that ticket's events read when the document is visible/focused, and answers bounded service-worker visibility probes. The worker suppresses an alert only for a confirmed ready chat for the current actor, then marks that event read and acknowledges it. Background/different/closed/unready views retain alerts. A small native modal explains both channels and includes the existing explicit opt-in control plus close; dismissal persists per actor/browser, with a safe in-memory fallback if storage fails. No new dependencies, schema or Endpoint contracts.

Actor: all authenticated requester/support/admin users. Primary task: notice events needing attention. Overlay archetype: dismissible help modal; bell is an unread inbox. No operating-system permission prompt until explicit opt-in. Design choices follow the user's three concrete fixes; no separate approval round required.

- [x] Capture red regressions: read-all empties list (failed before fix), active-ready-focus suppresses only that chat, inactive views still notify, onboarding close/permission behavior.
- [x] Implement scoped read-ticket action using existing actor and SQL visibility constraints; unread list query and error handling. Required expected_actor_id prevents old-account tabs consuming new-account events.
- [x] Implement active-chat readiness markers on actual requester/support routes, shared read/presence hook, bounded worker probe with safe fallback and session rechecks. Native and ARIA modals block consumption; failed read fetch/JSON falls back to alerts.
- [x] Implement small accessible introductory modal with per-actor dismissal and reused opt-in controls.
- [ ] Run focused backend/real PostgreSQL, UI, build, workspace and Chromium browser checks at desktop/mobile sizes; review changes and docs.
- [ ] Freeze on actual current staging SHA; verify backup/restore, canonical deploy with selector guard, retained key/schema, strict HTTPS/source hashes/service status. Repeat real Chrome provider delivery for background/closed tab and active-chat suppression; clean disposable tests, leave staging running.

Risks: page/worker/session races, failed visibility probes must deliver; read only current actor/ticket; never suppress based on URL alone, background tab or loading/failed conversation. Read-all must not erase future arrivals. Modal must not recur after close or auto-request permission. Existing subscriber key must remain unchanged.
