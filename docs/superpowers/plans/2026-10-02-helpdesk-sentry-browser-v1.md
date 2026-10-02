# Helpdesk Sentry Browser Observability v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Capture browser/React failures and sampled route/API traces without transmitting Helpdesk content or identity.

**Architecture:** aiohttp injects an allowlisted public JSON configuration into the dynamic HTML response. A centralized frontend module validates it, initializes a minimal Sentry client before React rendering, and projects every outgoing event/transaction onto a safe schema. Route templates come from the existing router, while propagation targets are limited to same-origin Helpdesk API requests.

**Tech Stack:** Python/aiohttp; React 19.2.5; react-router-dom 7.14.1; Vite 8.0.9; exact @sentry/react 11.2.0; pytest, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-02-helpdesk-sentry-browser-v1.md` (the supplied specification, preserved verbatim).

## Global Constraints

- Start from freshly fetched current `main`; discovery baseline is `03e0cb1557b714b6f21fbc20c73f473625a459ca`, recheck before execution.
- Preserve unrelated changes; work in the canonical workspace on `codex/sentry-browser-v1`.
- No production deployment, Sentry-server changes, Endpoint Platform changes, authentication changes, DB migrations, source-map upload, or public debug UI.
- `SENTRY_BROWSER_DSN` is runtime-only and independently rotatable; empty or invalid means disabled. Never commit or log a real key.
- `SENTRY_BROWSER_TRACES_SAMPLE_RATE=0.05`; malformed/nonfinite/out-of-range values use 0.05. Errors remain unsampled.
- Reuse backend environment policy and immutable 40-character release resolution; omit an invalid release.
- `sendDefaultPii=false`, `maxBreadcrumbs=0`; no replay, logs, metrics, profiling, feedback, sessions, console capture, or user assignment.
- Select integrations explicitly with SDK defaults disabled; test the actual SDK and complete outgoing envelope, not only mocked options.
- Pin `traceLifecycle: 'static'`: SDK 11 defaults to streaming, which bypasses `beforeSendTransaction`. Reassess this API when upgrading to SDK 12.
- Automated checks use fake DSNs and intercepted/in-memory transport; never contact the real Sentry service.

## Review Focus

- Config with script-breaking characters or malformed URL syntax must neither escape the JSON element nor disclose backend settings (task 1).
- A DSN on the application origin must not cause ingestion requests to receive API tracing headers (task 3).
- Wildcards, unmatched routes, and nested/encoded identifiers must produce a registered template or fixed unresolved marker (task 2).
- SDK enrichment, transaction spans, hint attachments, and envelope metadata must not reintroduce private fields after event projection (tasks 2–3).
- SDK initialization failure, unavailable transport, and malformed/missing config must preserve UI startup and disabled behavior (tasks 3–4).

---

### Task 1: Public runtime configuration and dynamic HTML

**Files:**
- Create `server/observability/browser_runtime.py`.
- Modify `server/config.py`, `server/static_pages/webapp_assets.py`, `deploy/helpdesk/helpdesk.env.example`.
- Extend `server/tests/test_static_pages_handlers.py`; create `server/tests/test_browser_runtime_config.py`.

**Interfaces:**
- Consume existing `SentrySettings.from_config(config)` environment policy and `resolve_release(override, identity_path)`; do not alter backend capture/sanitization.
- Produce `browser_runtime_config(config, *, identity_path=None) -> dict`: exactly `{'sentry': None}` when disabled; otherwise only `dsn`, `environment`, optional `release`, `tracesSampleRate` inside `sentry`.
- Produce `serialize_browser_runtime_config(payload: dict) -> str`: JSON with `<`, `>`, `&`, U+2028/U+2029 escaped.

- [x] Add failing unit tests for empty/valid/invalid DSN, HTTPS production requirement, nonfinite and out-of-range rates, shared environment policy, valid/invalid release identity, and exclusion of backend DSN/DB credentials.
- [x] Run `python -m pytest server/tests/test_browser_runtime_config.py -q --tb=short`; confirm new behavior fails before implementation.
- [x] Implement independent browser DSN/rate configuration and validators. Reject passwords, query/fragment, invalid project paths and control characters without logging supplied values.
- [x] Add failing handler tests asserting one non-executable `helpdesk-runtime-config` element before the frontend module, no-cache HTML, unchanged immutable assets, and safe serialization of literal script-breakout input.
- [x] Implement injection in `handle_webapp_page`; avoid mutating the dist index or emitting arbitrary config. Missing bundle behavior remains 503.
- [x] Run focused runtime and existing static-page tests; expect all green.

### Task 2: Browser parsing, route templates, and privacy projection

**Files:**
- Create `webapp/src/observability/runtime-config.ts`, `privacy.ts`, `routes.ts` and corresponding `.test.ts` files.
- Read existing route definitions from `webapp/src/app/router.tsx` through parameters, without copying a route catalog or importing page components into privacy code.

**Interfaces:**
- `BrowserSentryConfig`: `{dsn: string; environment: string; release?: string; tracesSampleRate: number}`.
- `readBrowserSentryConfig(document: Document): BrowserSentryConfig | null`.
- `resolveRouteTemplate(routes: RouteObject[], pathname: string): string`: registered full pattern or `[unresolved route]`, never substituted parameters or splat values.
- `createBrowserEventSanitizer(config, routes, origin)` returns typed `beforeSend` and `beforeSendTransaction` SDK callbacks.

- [x] Add parser tests: missing element, wrong JSON types, malformed JSON/DSN/environment/release, production HTTP DSN, invalid rate, and ignored extra fields.
- [x] Run focused Vitest tests and confirm failures; implement the bounded parser with the same server validation policy.
- [x] Add route tests using the application route tree: ticket/operation identifiers, encoded paths, wildcard/unknown paths, query/hash handling, index routes and nested patterns. Assert that actual IDs never appear in the result.
- [x] Implement route matching using React Router's registered definitions; route paths containing wildcard matches resolve to the fixed marker.
- [x] Add privacy tests with private markers in every input field, nested exceptions, spans, contexts, tags, breadcrumbs, URLs, attachments and storage-like data. Assert serialized outgoing results contain none of these markers.
- [x] Implement positive projection: validated release/environment/event ID, finite timestamps, approved route template, trace IDs/status/op, exception type, bounded safe asset filenames/functions/line/column. Replace arbitrary exception messages with a fixed message. Drop request/user/body/extra/breadcrumb/attachment data and unknown fields. Sanitize spans through the same positive schema.
- [x] Run focused parser/route/privacy tests; expect all green.

### Task 3: Minimal SDK initialization and React Router integration

**Files:**
- Modify `webapp/package.json`, `webapp/pnpm-lock.yaml`, `webapp/src/main.tsx`.
- Create `webapp/src/observability/sentry.ts`, `sentry.test.ts`, `sentry.integration.test.ts`.

**Interfaces:**
- `initializeBrowserSentry(config: BrowserSentryConfig | null, routes: RouteObject[], origin: string): BrowserObservability | null` initializes at most once.
- `BrowserObservability` provides the supported router wrapper and React root error callbacks. Disabled/failing initialization returns null and leaves existing router/root construction available.
- `buildTracePropagationTargets(origin: string, dsn: string): RegExp[]` allows same-origin `/api/*` only, excluding ingestion endpoints. Verify matching against SDK URL normalization rather than assuming relative/absolute semantics.

- [x] Bootstrap the repository web toolchain; install exact `@sentry/react@11.2.0` and inspect its published types/source for current router wrappers, React error handling, integration defaults, static lifecycle and propagation behavior.
- [x] Add failing option/idempotence tests: defaults disabled, minimal global-error handlers plus Router tracing, no prohibited integration, no sampled error setting, static lifecycle, configured trace rate and release/environment.
- [x] Implement initialization before rendering, current nondeprecated React Router integration/wrapper when compatible, and supported `reactErrorHandler` root callbacks. SDK failures must not throw into application startup.
- [x] Add propagation tests for relative/absolute API URLs, query-bearing API URLs, lookalike origins, different ports/schemes, external Endpoint URLs, static assets, Sentry transport URLs and same-origin ingestion paths.
- [x] Implement anchored same-origin target matching and request instrumentation exclusions; never use unrestricted origin/path regexes.
- [x] Add actual-SDK tests using intercepted transport: browser error, React root error, route navigation, fetch/XHR API tracing, network outage. Inspect complete emitted envelopes and headers for marker leakage, sessions/client reports/logs and ingestion propagation.
- [x] Verify startup continues after SDK initialization exceptions and unavailable transport; run all observability tests and production TypeScript build.

### Task 4: Static asset boundary, documentation, browser acceptance and independent review

**Files:**
- Modify `webapp/vite.config.ts`, `server/static_pages/webapp_assets.py` and static-page tests.
- Add focused Playwright test in `webapp/tests/`; use the existing isolated fixture without a public debug route or real Sentry endpoint.
- Update `server/docs/RUNBOOK_HELPDESK_ENDPOINT_HOST.md`, `server/docs/CODEMAP.md`, appropriate existing webapp map/documentation and `PLANS.md`.

- [x] Add failing direct-handler tests for `.map` requests through both asset and public-asset handlers, including a map physically present in fixture dist.
- [x] Explicitly disable build source maps and reject public map serving. Verify production dist contains no `.map` files.
- [x] Document runtime rotation/disable, separate public browser client key, shared identity, safe payload limitations, 5% tracing, same-origin API propagation, SDK static lifecycle and deferred internal-runner source maps.
- [x] Execute required checks:
  - `python scripts/bootstrap_web_toolchain.py`
  - `pnpm --dir webapp test`
  - `pnpm --dir webapp run build`
  - `python -m pytest server/tests/test_static_pages_handlers.py server/tests/test_browser_runtime_config.py -q --tb=short`
  - Existing backend observability tests to verify policy remains unchanged.
  - `python scripts/verify_workspace.py --workspace .`
  - `python -m compileall -q server scripts shared`
  - `git diff --check`
- [x] Run affected Playwright flows with disabled Sentry and fake enabled configuration; intercept any ingestion. Verify routes, headers, outage resilience and no content leakage.
- [x] Follow the repository browser skill for a real disabled browser load: record screenshots, console/network results and horizontal overflow at the required viewport sizes. Stop isolated services after acceptance.
- [x] Inspect complete diff and perform secret scan; synthetic keys must be unmistakably fake. Confirm no real DSN, auth token, credential or unrelated change is staged.
- [x] Dispatch the user-requested independent read-only reviewer covering privacy, HTML injection, route templates, propagation and disabled behavior; resolve findings and rerun affected checks.
- [x] Report branch/HEAD, changed files, exact SDK version, verification evidence, deferred source maps and residual limitations. Do not deploy or push this task without explicit authorization for this feature.

## Execution and acceptance

Recommended execution: Native implementation in this session, followed by the requested independent read-only whole-diff review. The four tasks share runtime, routing and privacy interfaces; keeping implementation together avoids duplicate context while preserving independent final verification.

Self-review: every supplied architecture, privacy, runtime, tracing, source-map, test and documentation requirement has an owning task. Task 3 must validate SDK behavior after sanitizers, not infer envelope safety from mocks. Source-map limitations and future SDK lifecycle migration remain documented follow-ups, not claims of full symbolication.
