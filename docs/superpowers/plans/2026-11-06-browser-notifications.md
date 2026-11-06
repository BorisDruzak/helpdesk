# Browser notifications implementation plan

**Goal:** Deliver chat and status events to the bell and browser, including a closed Helpdesk tab.
**Approved behavior:** The user requested both channels after the chat proposal: event list, click-through, explicit browser opt-in, and duplicate suppression.
**Architecture:** Persist notifications in the event transaction. Fan out an additive durable Web Push delivery queue to opted-in browsers. Send payload-free VAPID wakeups; a service worker retrieves actor-scoped messages using the existing authenticated session. Use existing Authlib, cryptography and httpx; no dependencies added.
**Constraints:** Preserve existing uncommitted work. User explicitly selected current staging `192.168.101.118` for launch; production is outside scope. Use reviewed release workflow. GitNexus is unavailable in this session. Keep endpoints, keys and tokens out of logs. Service worker caches no application responses.

## Launch completion

- [x] Replace unavailable example.test test tunnel with project-owned disposable SCRAM PostgreSQL16 loopback cluster; no global environment or production substitution. Database/backend tests69passed; fresh schema/idempotency/cleanup8passed. Fix three existing cleanup classifications in an independent maintenance commit.
- [x] Freeze on current accepted staging base d7971ca528b416eb77616026ee9144a713334304, preserving concurrent Users and earlier catalog/requester changes. Private release branch: codex/browser-notifications-staging; release43e81da89c021fb90de3c8770237739e71d09e23.
- [x] Verify full backup/restore at155; canonical deployment with expected-current selector guards and shared installer lock; migration156; configure outside-release0600P256 key and strictHTTPS; source hash/health/worker checks pass.
- [x] Actual FCM delivery of chat and status with Helpdesk tab closed in temporary non-incognito GoogleChrome profile: two trusted native events, provider accepts and browser ACKs. Reopened bell has both events; opt-out succeeds. Synthetic tickets closed and accounts disabled, no live test subscriptions remain.
- [x] Leave staging services active as requested. Final evidence and limitations: docs/BROWSER_NOTIFICATIONS_STAGING_ACCEPTANCE_2026-11-06.md.

The following sections retain the initial implementation checkpoint; its pending database/deployment gates are superseded by this completion record.

- [x] Backend: event projections and recipient policy tests; atomic notification creation and explicit JSON projection. PostgreSQL rollback/concurrency tests added but not yet accepted.
- [x] Web Push: VAPID, endpoint allowlist, actor/validation API tests; models/migration 156, handlers and lifecycle dispatcher. External-provider acceptance remains a deployment gate.
- [x] Frontend: bell/read/error and permission tests; shared bell, opt-in controls and closed-tab service worker with durable deduplication and safe navigation.
- [x] Local verification: 48 backend / 28 frontend / 7 full-Chromium cases, TypeScript/Vite build, workspace sanity, sole migration head 156 and inventory/cleanup-profile audits. CODEMAP/operations updated; database/provider gates remain explicitly pending.
- [x] Independent review and final task diff checked; source-only candidate and remaining gates documented in `docs/BROWSER_NOTIFICATIONS.md`.

## Review focus

- Internal messages must never enter requester notifications.
- No push may escape an uncommitted/rolled-back event transaction.
- Account switches and logout must not reveal the previous user's notifications.
- Provider failures must retry without logging access-bearing subscription endpoints.
- Denied permission, expired sessions, unsupported browsers and missing server keys must have honest user-visible states.

## Execution rulings and evidence

- Kept the authorized shared checkout because the root contract limits edits to it; preserved unrelated and concurrently edited files. No worktree, commit, push or deployment was requested.
- GitNexus was unavailable; verified dynamic event, recipient and session paths in source. No Endpoint contracts changed.
- Independent review caught and prompted fixes for logout races, revoked visibility, subscription-wide cooldown, WNS transport, unbounded badge reads and HTTPX endpoint logging.
- Added a SQL notification-scope projection matching canonical UI ticket access; count and pagination stay in SQL and actor membership aliases resolve once per request.
- Full Chromium is required for notification tests; the default headless shell denied permission. Registered-worker closed-tab synthetic CDP push acceptance passed; actual external delivery remains separate.
- PostgreSQL tests could not initialize: configured/default Windows SSH test tunnel points to `altserver@example.test`. Did not substitute a production database or modify global tunnel configuration.
- Cleanup schema audit recognizes both new tables. It reports three pre-existing unclassified tables (`web_requester_registrations`, `worktime_authorization_codes`, `worktime_session_leases`), outside this change.
