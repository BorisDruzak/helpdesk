# Helpdesk Sentry Backend Observability v1 implementation plan

**Goal:** Implement the supplied backend-only optional Sentry specification from current HEAD8167da2f915bfb2abff3c7f17489060d10a00192.
**Architecture:** Existing environment contract in server/config.py; centralized startup/bootstrap in server/observability/sentry.py and event policy in privacy.py. Initialize after create_app constructs registered routes, before web.run_app serves requests. A bounded close runs after the aiohttp loop stops. No import-time SDK initialization and no migration/control-process bootstrap.
**Tech stack:** Existing aiohttp, Python; official sentry-sdk2.71.0 exact pin, checked through Context7, official PyPI and installed SDK source.
**Execution:** Implement incrementally in this checkout on codex/helpdesk-sentry-backend-v1, following the user's supplied execution spec. Preserve unrelated untracked files. No production/remote Sentry/Endpoint changes.

## Decisions and constraints
- SENTRY_DSN empty disables even SDK import/init. Optional invalid config fails safely without echoing values; initialization failure disables until restart.
- SENTRY_ENVIRONMENT defaults APP_ENV (prod maps production); invalid names fall back. Rate defaults0.10, finite numeric values clamp0..1; invalid/nonfinite use0.10.
- Explicit release override must be exact40-character Git SHA; invalid override falls through to fixed release-root release-identity.json beside server/, independent of cwd. Invalid/missing identity omits release. Pass empty release explicitly to prohibit SDK Git/environment autodetection.
- Only explicit AioHttpIntegration(method_and_path_pattern), no default/auto integrations/logs/metrics/profiles/sessions/breadcrumbs/trace propagation. Background HTTP transport queue32; shutdown timeout1second, close after event loop stop.
- Both event hooks project onto safe fields. Drop bodies/all headers/cookies/query/user/extras/tags/arbitrary contexts/attachments/SQL/HTTP span descriptions/frame locals/source excerpts. Route must match this application's registered canonical routes. Preserve exception type, frame file/module/function/line and safe structural exception messages; omit unstructured messages because they may embed ticket/chat/upload text. Preserve configured release/environment and timing/trace identifiers.
- Security preflight remains unchanged and Sentry optional. No new routes, database tables, migrations, frontend SDK or production deployment.

## Tasks
- [x] Add focused failing no-DB tests for disabled/idempotent bootstrap/config/release/privacy plus real SDK in-memory aiohttp error/transaction envelopes and outage behavior; run RED.
- [x] Implement centralized integration, four environment variables and canonical dependency; make tests pass.
- [x] Update env example, CODEMAP, host runbook and PLANS; add production-config/deploy fixture regressions.
- [x] Run focused auth/startup/config/deploy tests, safe-fixture CLI validator, scoped workspace verification, compileall and diff/secret scan. Full release CI/live ingestion intentionally excluded from this implementation task.
- [x] Independently review privacy/failure isolation/current SDK compatibility and docs. Resolve findings, report exact files/tests/risks; no publication without the applicable release workflow.

## Verification outcome
83 focused tests passed;28 Sentry tests include real SDK/aiohttp in-memory envelopes, incoming baggage and attachment sanitization, stalled background transport and bounded close. Production-config optionality/security, unchanged release identity packaging and auth/config regressions passed. Scoped workspace, compileall, safe-fixture production CLI, test inventory311/0issues and diff checks passed. Independent review found inherited Spotlight synchronous egress; explicit spotlight=False added and regression observed RED then GREEN. No remaining findings. Live ingestion/TLS and full release gate not run; no production/Sentry-server/Endpoint changes or push.

Official API references: https://docs.sentry.io/platforms/python/integrations/aiohttp/ ; https://github.com/getsentry/sentry-python/tree/2.71.0 ; https://pypi.org/project/sentry-sdk/2.71.0/ . Context7 queried before implementation; exact installed SDK source verified body collection, hook placement, attachment envelope construction and background queue/flush.
