# Browser notifications staging acceptance — 2026-11-06

Launched on the user-selected current test server `osn-admin@192.168.101.118`, at `https://helpdesk-staging.sosnadmin.local`. Chat messages and status changes appear in the shared bell and can trigger browser notifications after explicit browser opt-in, including a closed Helpdesk tab. Production `192.168.100.19` was not modified.

## Release and configuration

- Accepted base: `d7971ca528b416eb77616026ee9144a713334304`; concurrent Users administration and prior accepted requester/catalog changes retained.
- Maintenance commit: `1a0032f8f3f08f3761111743d0e80e17e1facd98` — `test(db): include registration and WorkTime rows in cleanup`. Files: `quality/db_table_classification.toml`, `scripts/reset_test_data.py`, `server/tests/conftest.py`.
- Installed feature commit: `43e81da89c021fb90de3c8770237739e71d09e23` — `feat(notifications): deliver chat and status events to browsers`. Private branch `codex/browser-notifications-staging`; shared checkout HEAD/index and unrelated dirty work preserved. No push or PR.
- Canonical `scripts/deploy_helpdesk_release.py` installation, isolated staging profile and protected access bridge. Expected-current guards reject a changed selector; a shared root `flock` covers preparation, migration and switch/restart. Competing new installers were exercised on Linux: one succeeds, the stale one rejects. Legacy installers without this lock remain a concurrency limitation; final selector guards reduce that risk.
- Immutable runtime `/opt/helpdesk-staging/releases/helpdesk-43e81da89c021fb90de3c8770237739e71d09e23`; schema **156** after real migration from155. All candidate source hashes match installed bytes.
- Verified full backup and isolated restore at revision155: `/var/backups/helpdesk-browser-push-20261106-d7971ca528b4`; SHA256 `9ffcf23bae5f93fda1f28a103e9e1d1b89c97bef1c74ac532ed2c4e768a97233`, 14,505,480 bytes. Temporary restore DB removed. Backup retained only on staging.
- `scripts/configure_helpdesk_web_push.py` configured the existing isolated environment with compare-and-swap protection. P-256 private key `/etc/helpdesk-staging/secrets/web-push-vapid.pem`, owner `helpdesk-staging`, mode0600, outside source/releases; no overwrite or secret output. VAPID subject is the staging HTTPS origin. Keep this key across releases.
- Final strict TLS `/api/health` and `/helpdesk-notifications-sw.js`: HTTP200. Worker `Cache-Control: no-store, no-cache, must-revalidate`, `Service-Worker-Allowed: /`. Helpdesk, Endpoint staging and Endpoint staging worker services active; deliberately left running.

## Database and automated checks

The previous test connection defaulted to `altserver@example.test`. The canonical `scripts/run_with_local_postgres.py` harness now supplies a fresh PostgreSQL16.15 cluster on loopback/random port with SCRAM and no shared fallback. Credentials stay in child-process memory; owned clusters were stopped/removed. Global test settings and production DB were not substituted.

- Frozen candidate focused backend, real PostgreSQL persistence/concurrency, key configuration and deployment checks: **69 passed**. Migration/schema suite in its required separate process: **8 passed**, including fresh156, idempotency, constraints and cleanup. Three pre-existing registration/WorkTime cleanup omissions fixed in the separate maintenance commit; strict cleanup schema audit passes.
- Final installer-lock tests: **17 passed, 1 skipped** on Windows (Linux-only lock scenario); real concurrent Linux lock proof passes separately.
- Frozen frontend notification/session/topbar tests: **28 passed**. TypeScript/Vite build and canonical installer fresh frozen-lockfile build pass.
- Full Chromium fixture browser suite: **7 passed**, including requester/support at desktop/mobile widths, opt-in/out, registered worker closed-tab CDP push and duplicate handling. Fixture CDP injection is separate from the actual external acceptance below.
- Workspace verification with absolute frozen workspace path, diff whitespace checks and independent review pass. Existing Authlib deprecation warnings remain; no dependency was added. Full CI was not run for this targeted staging release. GitNexus tools were unavailable; dynamic event/session paths and unchanged cross-repository boundaries were verified from source.

Detailed command output is under `tmp/browser-notifications-launch-20261106`: `frozen-v2-postgres-tests.log`, `frozen-migration-tests.log`, `frozen-v2-ui-tests.log`, `frozen-v2-build.log`, `frozen-v2-verify.log`, `frozen-browser-tests.log`, `deploy.log`, `install-lock-proof.json`. Schema suite uses `python scripts/run_with_local_postgres.py -- python -m pytest` in a separate process from regular DB tests; the selected frozen test paths are retained in the release tree and logs.

## Actual external delivery with a closed tab

`live.py` / `live-push.mjs` use installed Google Chrome, a temporary persistent profile, strict trusted HTTPS and notification permission limited to that test context. They do not bypass TLS, replace PushManager, fake provider responses or inject CDP push events. The incognito-style first attempt could not subscribe; using a non-incognito temporary profile registered with `fcm.googleapis.com`. A subsequent test-only exact-text selector failed because of the unread bullet; the final run corrected that selector and passed end to end.

Final run, 2026-11-06 UTC:

1. Disposable requester registered through the normal public endpoint and logged in through the UI; explicit browser opt-in subscribed successfully.
2. Helpdesk app tab closed; an unrelated blank tab kept the browser process running. A canonical synthetic public support message was committed to the disposable requester's own test ticket.
3. Native trusted push at09:55:10.233: **“Новое сообщение по обращению T-000079”**. Canonical status transition then produced a second native trusted push at09:55:15.583: **“Изменён статус обращения T-000079”**, body **“Нужен ваш ответ”**.
4. Both records had provider acceptance and durable browser-display acknowledgement before cleanup. Browser `registration.getNotifications()` contained both native notifications. On reopening `/app/requester/tickets`, the bell showed both events and unread count2; screenshot `live-bell-1366.png` visually checked. Original test page errors/console errors:0.
5. UI opt-out succeeded. Both synthetic test tickets T-000078/T-000079 closed through workflow; all three disposable accounts disabled and their subscriptions removed. History intentionally retained. Final totals79tickets/18537events,0subscriptions/0deliveries (baseline77tickets/18525events); acceptance operations targeted only the disposable users/tickets.

Redacted evidence: `live-push.json` (status success, trusted events and pre-cleanup ACKs), `live-browser.log`, `installed.json`, `final-verify.log`, backup/key receipts and complete changed-file manifest `commits.json` / `candidate-files.json`. Endpoints, cookies, passwords and private keys are not included. Cleanup cascades delivery rows, so the separate pre-cleanup receipt is the delivery evidence.

## User operation and limits

Open the staging site, refresh the page, open the bell and click **“Включить уведомления в браузере”**, then allow notifications. Permission and subscription belong to each browser separately. Bell events do not require browser permission.

Closed-tab native delivery is accepted for Google Chrome through FCM. A fully terminated browser, expired login, unreachable internal site/provider or OS notification suppression can delay/prevent display. The automation verified actual native push/display objects and acknowledgements; it did not visually inspect an OS notification popup. Real Firefox/Edge/Safari providers, fully terminated-browser delivery and OS click-through were not accepted in this run. No production promotion is implied.

## Changed files and ownership

Complete51-file release manifest: `tmp/browser-notifications-launch-20261106/commits.json`. Main additions are notification scope/fanout/transport, Web Push models/migration/repository/dispatcher/API, shared frontend bell/control/service worker, focused Python/UI/browser tests and guarded key setup. Integration updates include event/notification repositories, session cleanup, lifecycle/routes/assets, environment example, CODEMAP and deploy selector/lock checks. Detailed subsystem surface is in [BROWSER_NOTIFICATIONS.md](BROWSER_NOTIFICATIONS.md). Final acceptance documentation changes are this report, that subsystem document, `PLANS.md` and the task plan; CODEMAP remains accurate.
