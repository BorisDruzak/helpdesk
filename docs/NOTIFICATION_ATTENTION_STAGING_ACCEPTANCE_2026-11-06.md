# Notification attention fixes — staging acceptance 2026-11-06

All three requested corrections are installed on the current test server `osn-admin@192.168.101.118`, `https://helpdesk-staging.sosnadmin.local`. Production was not changed. Refresh the application with Ctrl+F5 to load the new shell and worker.

## Result

- A loaded, focused, visible chat consumes its own events without a popup. Another ticket, a hidden/unfocused view, loading/error state or a native/ARIA modal cannot claim that the chat is being read. Worker visibility probes have a750ms bound; failed probes/reads fall back to an alert. A stale-account tab cannot mark the newly logged-in account's events read.
- The bell now requests unread-only events. “Прочитать все” removes the displayed events, including after reopening the menu; database history is retained. New events remain eligible for the inbox.
- A small native modal explains chat/status and closed-tab notifications after entry. It has explicit opt-in, close and Escape controls, never requests permission automatically, remembers dismissal per account/browser and skips an already subscribed browser.

## Release

Installed commit **`2573425f1b85f0e5dd83450e357f0e4d36b5e061`**, **`fix(notifications): respect active chats and clear read events`**, branch `codex/notification-attention-fixes`, parent `48f32ef49941213c197244e95466b3bebee7f9c1`. Actual prior runtime `43e81da89c021fb90de3c8770237739e71d09e23` was guarded by `--expected-current-sha` and the canonical shared installer lock. Local private index preserved the shared HEAD/index and unrelated dirty work. No push or PR.

Canonical `scripts/deploy_helpdesk_release.py` installed an immutable release and built the exact candidate frontend using the frozen lockfile. Before installation, verified full dump/isolated restore at schema156: `/var/backups/helpdesk-notification-attention-20261106-43e81da89c02`, SHA256 `06c927fc4ff88ddb996ea28c62d0485d4c1b88fde2b6ef622abd519e4ba1db5f`, 14,525,091 bytes. Restore database removed; backup retained on staging.

No new schema or dependencies. Final schema **156**, health and notification worker HTTP200 under trusted TLS, worker no-store/root scope headers correct; all candidate source hashes match installed bytes. Existing private key remains outside releases, owner `helpdesk-staging`, mode0600; protected environment fingerprint unchanged. The prior user's subscription remains present: final1subscription/0pending delivery rows after test cleanup. Helpdesk/Endpoint staging/Endpoint staging worker services remain active as requested.

## Verification

- Red regression: read-all left rows in the menu before the unread query fix.
- `python scripts/run_with_local_postgres.py -- python -m pytest server/tests/test_web_push_persistence.py server/tests/test_notification_scope_no_db.py server/tests/test_browser_notifications_no_db.py server/tests/test_web_push_api_no_db.py -q`: **27 passed**, including actual PostgreSQL actor/ticket/revoked-scope isolation. An initial test fixture omitted public visibility and was correctly rejected; it was corrected without weakening the scope rule. Owned test cluster stopped/removed.
- `python -m pytest server/tests/test_notification_attention_api_no_db.py -q`: **2 passed**, including unauthenticated401, malformed-body400 and stale-actor409 with no mutation.
- `pnpm --dir webapp exec vitest run src/features/notifications src/components/shell/app-topbar.test.tsx src/features/auth/session-provider.test.tsx src/pages/requester/ticket-chat-page.test.tsx src/pages/tickets/components/simple-support-conversation.test.tsx`: **58 passed**.
- `pnpm --dir webapp run build`: **passed**, TypeScript/Vite; canonical frozen candidate build also passed. Existing large-chunk warning retained.
- `PC_CLIENT_WEBAPP_E2E_PORT=4295 pnpm --dir webapp exec playwright test browser-notifications.spec.ts --output=../tmp/notification-attention-browser-accepted`: **12 passed**. Instruction screenshots at1366/1920/390 inspected, no horizontal overflow; default permission unchanged on entry, dismissal survives reload. Read-all/reopen, requester/support bell, native registered-worker foreground suppression, failed-read JSON fallback and closed-tab delivery pass. Negative unfocused-page state is explicitly emulated because headless tabs stay artificially focused; closed-tab coverage is separate. Existing fixture Windows connection-reset cleanup warnings did not fail assertions.
- Workspace verification, strict test-inventory audit and diff whitespace checks pass. Independent review has no remaining concrete blockers after stale-account, read-failure and ARIA modal findings were corrected. GitNexus tools unavailable; owning source/dynamic routes verified, no Endpoint contract changes.

## Actual Chrome / FCM acceptance

Installed Google Chrome with a temporary persistent profile, trusted HTTPS, no provider mocks or CDP push injection. Test-only permission grant is limited to that browser context. A disposable requester uses normal registration/login and explicit opt-in. Final successful run on T-000085, **15:48 local time (UTC+5)**:

1. Login instruction shown, screenshot captured and closed. Actual focused/visible requester chat loaded.
2. Committed synthetic public support message: native trusted push received, provider accepted, browser acknowledged, event marked read; **zero browser notification objects** while the chat is active.
3. Closed the Helpdesk tab, leaving the browser running with a blank tab. New chat notification received at15:48:37, status notification at15:48:42. Both provider acceptance and browser acknowledgements confirmed. Three native push events in total, all trusted; no application errors on the monitored page.
4. Reopened requester list: exactly the two unread events visible in bell. “Прочитать все” produces empty state, which stays empty after reopening. Explicit opt-out succeeds.
5. Test tickets T-000084/T-000085 closed through canonical workflow; both disposable accounts disabled and their subscriptions removed. Synthetic history retained. Existing user subscription preserved. Final observed totals85tickets/18621events; users were also active on staging during the work, so count differences are not a claim that all intervening events belong to this test.

The first external run accepted active-chat silence and closed-tab chat delivery, then timed out waiting for two simultaneous notification objects during the status step. No server push warnings/tracebacks were found. The successful rerun waits for each event type separately and records all provider/browser acknowledgements; the first failure is retained in `live-first-attempt.json` rather than discarded. No product code changed between these external runs.

Real Firefox/Edge/Safari provider delivery, a fully terminated browser and OS popup/click visual inspection were not tested. Native notification objects/events and durable acknowledgements are the external delivery evidence. Full CI was not requested/run for this targeted staging correction. No production promotion is implied.

## Changed files and evidence

Complete24-file commit manifest: `tmp/notification-attention-20261106/commit.json`; exact diff `candidate.diff`. Server: notification repository/scoped read handler+route and regression tests. Frontend: unread query, shared bell/active-chat hook, opt-in callback, introductory modal, requester/support readiness markers, worker and UI/browser fixtures/tests. Docs: subsystem behavior, CODEMAP, PLANS and task plan. Acceptance documentation is recorded separately after the installed source commit.

Evidence: `tmp/notification-attention-20261106/{backup-and-restore.json,deploy.log,installed.json,key-check.log,live-push.json,live-browser.log,final-verify.log,live-introduction-1366.png,live-bell-1366.png}` plus focused logs under `tmp/notification-attention-*.log` and browser artifacts under `tmp/notification-attention-browser-accepted/`. Endpoints, passwords, cookies and private keys are not included.
