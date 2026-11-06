# Bell and browser notifications

Chat messages and status changes create notification rows in the same transaction as the deduplicated ticket event. Rollback cannot send a browser notification. Existing recipient policy, internal-message visibility, muted events and suppress-self preferences apply. Generated system messages have no human initiator.

For an unambiguous existing UI account, notifications recognize the stored login
and its normalized password-session spelling as the same recipient. Inbox reads,
acknowledgements, browser subscriptions and preferences use those validated
aliases; queue/assignee overlap creates one event and self suppression applies
across login methods. Arbitrary principals and unsupported spellings remain
exact-only, and ambiguous UI identities receive no alias access.

The shared requester/support/admin bell shows the latest 30 **unread** events, individual click-through and “Прочитать все”. It requests `unread_only=true`; successful reads disappear on refetch instead of accumulating in the menu. Durable history is retained in the database. It polls the existing inbox/count endpoints every 15 seconds. Failed reads have an explicit error state. The API emits a JSON projection with a Russian title, safe summary and internal ticket URL; it does not expose raw chat payloads. Current role, requester ownership, queue membership aliases, direct assignee and unified-queue rules are checked in SQL **before** pagination and counting; badge polls do not load the full unread history into Python.

## Attention and first-login help

Installed staging correction and current evidence: [attention acceptance](NOTIFICATION_ATTENTION_STAGING_ACCEPTANCE_2026-11-06.md).

A loaded requester/support conversation declares a readiness marker only in its chat view, not its loading/error/history view. The shared shell reads events for that ticket while the document is focused and visible and no native or ARIA modal covers it. The worker probes a matching foreground window over MessageChannel (750ms bound), checks the current actor/session, and suppresses the alert only after a positive readiness reply and a successful event read. Failed/unanswered probes or failed reads retain an alert. Another ticket, a background/closed tab, an account mismatch or a covered/unready conversation cannot suppress it.

`POST /api/web/notifications/read_ticket` accepts `ticket_id` and required `expected_actor_id`. It rejects stale-account tabs with409 before database access. Reads apply current actor and SQL visibility scope; other tickets/users are preserved. The shell retries on focus/visibility changes and a five-second timer without requiring Web Push opt-in. The original global read-all action remains unchanged.

An introductory native modal appears for supported browsers with configured but inactive notifications. It explains chat/status alerts, closed-tab behavior and the unread bell, with an explicit opt-in button and close/Escape controls. Permission is never requested on login automatically. Dismissal is remembered per actor/browser in localStorage with an in-memory fallback when storage is blocked; an already subscribed browser is not prompted. The existing bell opt-in remains available after closing the help.

## Opt-in and delivery

“Включить уведомления в браузере” asks permission only on user interaction. Opt-in belongs to this browser and the authenticated actor; another browser requires its own opt-in. A root-scoped `/helpdesk-notifications-sw.js` worker handles notifications only: it does not intercept fetches or cache application responses. The worker asset is served with `no-store` and `Service-Worker-Allowed: /`.

`web_push_subscriptions` stores the access-bearing provider endpoint, its SHA-256 lookup key and the VAPID public key. `web_push_deliveries` records fanout per subscription/notification in the event transaction. The lifecycle-managed dispatcher uses PostgreSQL row locks with `SKIP LOCKED`, sends bounded batches, retries failures with backoff, removes HTTP 404/410 subscriptions and retries accepted but unacknowledged messages after five minutes. Fresh events can wake a browser immediately after a successful prior send. Wakeups expire after 24 hours; the bell retains its normal history.

External providers receive an **empty** Web Push body plus VAPID authentication, never ticket IDs or chat text. The worker fetches actor-scoped details over the current same-origin authenticated session, checks the current session again before display, saves displayed IDs in IndexedDB for seven days and acknowledges delivery. A stable notification tag also suppresses replacement alerts. Click-through verifies the current actor and marks that notification read before opening the appropriate ticket. Logout/login drains and suspends worker processing, revokes the browser subscription and closes outstanding notifications; server revocation has a three-second timeout. Expired sessions cannot retrieve messages and the worker unsubscribes.

Only HTTPS endpoints at FCM, Mozilla Autopush, Apple Web Push and a single-label `*.notify.windows.com` WNS host are allowed. Redirects are disabled. WNS receives its required `wns/raw` and octet-stream headers only on Microsoft endpoints. HTTPX request logging redacts these URLs; provider failures log only HTTP status. Treat subscription endpoints as secrets; never include them, cookies or VAPID proofs in evidence.

## Server activation

Deployed and enabled on the approved staging server `192.168.101.118` on 2026-11-06. Migration 156 and real FCM delivery for both event types with the Helpdesk tab closed passed. See [staging acceptance](BROWSER_NOTIFICATIONS_STAGING_ACCEPTANCE_2026-11-06.md) for release identity, evidence and limits. Production was not changed. Use the reviewed Helpdesk release workflow; do not patch a runtime directory.

1. Run the isolated PostgreSQL tests and release checks, then apply migration **156** after verifying revision 155 and the required backup evidence. It adds only the two Web Push tables and an actor index. Its downgrade deletes browser subscriptions/delivery metadata; ordinary bell history stays intact. Downgrade is not a routine rollback action.
2. Create a P-256 PEM outside the checkout and release directory, for example with the new `scripts/generate_web_push_key.py --output <private-path>` provisioning tool. It refuses overwrite and never prints the private key. Ensure only the Helpdesk Unix user can read it (mode 0600); keep it across releases. Do not commit it or rotate it casually.
3. Configure `HELPDESK_WEB_PUSH_PRIVATE_KEY_FILE` and `HELPDESK_WEB_PUSH_SUBJECT` (an operator contact such as `mailto:<contact>`), then restart through the reviewed lifecycle procedure. Both unset means browser delivery is disabled and the menu says it is not configured. The bell remains available. Invalid partial configuration fails validation.
4. Serve the site using a trusted HTTPS certificate, forward the worker URL to Helpdesk, and allow server HTTPS egress to the browser push provider. Browser and OS policies must allow notifications. A private Helpdesk site must remain reachable by the worker when it wakes.
5. On staging, opt in with each supported real browser, send a synthetic public support reply and status change, close the Helpdesk tab, and verify the OS notification plus ticket navigation, duplicate suppression, mute/internal scope, logout and session expiry. Check exact deployed SHA, migration revision and redacted status evidence before production promotion.

Closing a tab is supported. A fully terminated browser, an offline workstation, expired authentication, OS “Do not disturb”, blocked provider connectivity or browser policy can prevent/delay delivery. Service-worker registration and push subscription keys stay local to the browser; the server needs only the endpoint because no payload encryption is necessary for an empty wakeup.

## API and ownership

- Existing `GET /api/web/notifications` and `/unread_count`, `POST /read_all` and `/{id}/read` remain the bell surface; list projection gains `title`, `body`, `url` and removes unsafe/raw payload serialization.
- `GET /api/web/notifications/push/config` returns availability and the public key.
- `POST /api/web/notifications/push/{subscribe,status,unsubscribe,messages,acknowledge}` uses the authenticated UI actor and existing same-origin CSRF middleware. Public ticket credentials cannot enumerate a notification inbox. Ownership is checked for pending reads and acknowledgements.
- This is Helpdesk-owned browser delivery. No Endpoint Platform API, agent transport or cross-repository contract changes are needed.

## Verification

Run focused backend tests (`test_browser_notifications_no_db.py`, `test_notification_scope_no_db.py`, `test_web_push_no_db.py`, `test_web_push_api_no_db.py`, `test_ticket_notification_policy.py`, `test_ticket_events_repo_no_db.py`, `test_server_runtime_lifecycle.py`) and PostgreSQL `test_web_push_persistence.py` / `test_ticket_event_idempotency_concurrency.py`.

Frontend: `pnpm --dir webapp exec vitest run src/features/notifications src/components/shell/app-topbar.test.tsx src/features/auth/session-provider.test.tsx`, then `pnpm --dir webapp run build` and `pnpm --dir webapp exec playwright test browser-notifications.spec.ts`. The browser test uses full Chromium (`channel: chromium`): the smaller headless shell denies OS notifications. It serves synthetic notification data, checks 1366/1920/390 layouts, registers the actual worker, closes the Helpdesk tab and injects a CDP push. This verifies worker/browser behavior, **not** an external provider or production delivery.

Relevant specifications: [RFC 8030](https://www.rfc-editor.org/rfc/rfc8030), [VAPID RFC 8292](https://www.rfc-editor.org/rfc/rfc8292), [Windows push headers](https://learn.microsoft.com/en-us/windows/apps/develop/notifications/push-notifications/push-request-response-headers).

## Initial local verification record — 2026-11-06

Historical source-only checkpoint. The database and deployment blockers below were subsequently resolved; the linked staging acceptance record describes the final state.

- Focused backend command listed above: **48 passed**; Authlib emits existing/deprecation notices for its JOSE/httpx integration. Tests cover VAPID signature, endpoint allowlist/WNS headers, HTTPX log redaction, protected routes/verified actor, strict acknowledgement validation, SQL scope/count, projections and existing recipient preferences.
- Focused frontend command listed above: **28 passed**, including denied permission, server failure, stalled-revocation timeout, logout cleanup and existing session-boundary tests.
- `pnpm --dir webapp run build`: **passed** (TypeScript and Vite). An initial concurrent, unrelated Users-page edit temporarily broke the build; the completed current source subsequently built successfully without changes to that work.
- `pnpm --dir webapp exec playwright test browser-notifications.spec.ts` with a dedicated `PC_CLIENT_WEBAPP_E2E_PORT`: **7 passed**. Requester menu checked at 1366/390, support menu at 1366/1920/390, explicit opt-in/out and actual registered-worker closed-tab CDP push/duplicate handling. UI page/console error and unexpected HTTP checks passed; screenshots were visually inspected. The local Python fixture emitted an intermittent Windows connection-reset cleanup warning after navigation; it did not fail browser assertions.
- `python scripts/verify_workspace.py`: **passed**; `git diff --check`: **passed**; Alembic script directory has one head, **156**.
- `python scripts/audit_test_inventory.py --strict`: **passed**; `python scripts/audit_db_cleanup_profiles.py --strict`: **passed**.
- `python scripts/audit_db_cleanup_schema.py --schema-from-models --strict`: both new tables classified/cleaned correctly; the broader audit reports three unrelated existing unclassified tables (`web_requester_registrations`, `worktime_authorization_codes`, `worktime_session_leases`).
- PostgreSQL acceptance was attempted using the canonical test harness and stopped during initialization because the configured/default SSH target is `altserver@example.test`. No production database was substituted and no global test connection setting was changed. Fresh migration, transactional rollback and competing-producer tests remain **unaccepted** until the isolated test database is available.
- Independent review found no remaining concrete blockers after the targeted fixes. GitNexus was unavailable; committed/runtime dynamic paths were checked against source. No external provider was contacted, no private VAPID key generated, and no remote service deployed or restarted. Local fixture servers for this task stop with their test runs.

## Changed surface

Task-owned additions are `server/tickets/{browser_notifications,notification_scope,web_push}.py`, `server/web_api/push_handlers.py`, `server/app/db/web_push_models.py`, migration `20261106_156_web_push.py`, `server/app/repos/web_push_repo.py`, `server/app/services/web_push_dispatcher.py`, `scripts/generate_web_push_key.py`, four backend no-DB test modules plus `test_web_push_persistence.py`, `webapp/src/features/notifications/` (API, menu, bell, browser control/helpers and tests), `webapp/public/helpdesk-notifications-sw.js`, `webapp/tests/browser-notifications.spec.ts` and its synthetic `notification_fixture.py`.

Integration edits touch `server/app/db/models.py`, `server/app/repos/{notification_repo,ticket_events_repo}.py`, `server/tickets/{notification_service,handlers}.py`, requester/support message handler payloads, `server/{routes,server}.py`, `server/static_pages/webapp_assets.py`, `server/.env.example`, `server/tests/conftest.py`, `quality/db_table_classification.toml`, `scripts/reset_test_data.py`, the shared topbar/test, auth session provider, notification API type, local browser fixture server, CODEMAP, PLANS and the task plan. Launch work also adds guarded key configuration and release-selector/installer-lock checks. Unrelated work in these or other dirty files is preserved. Local release commits and their complete file manifest are recorded in staging acceptance; no Git push was made.
