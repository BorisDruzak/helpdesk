# TASK: Helpdesk Sentry Browser Observability v1

Repository:
BorisDruzak/helpdesk

Start from current main HEAD.
Do not assume any previously inspected SHA is still current.

Existing state:
- Sentry self-hosted: https://sentry.sosnadmin.local
- Sentry project: Helpdesk / helpdesk
- Backend Sentry v1 is already merged and live-verified.
- Backend observability is production-safe and its privacy boundary must not be weakened.
- React: 19.2.5
- react-router-dom: 7.14.1
- Vite: 8.0.9
- Production React bundle is immutable and served by aiohttp.
- server/static_pages/webapp_assets.py serves index.html dynamically with no-cache.
- hashed assets are immutable.
- production runtime configuration lives in /etc/helpdesk/helpdesk.env.

IMPORTANT:
- Do not deploy unless explicitly authorized.
- Do not change the Sentry server.
- Do not touch Endpoint Platform.
- Do not hardcode a real browser DSN/client key into Git.
- Preserve unrelated user changes.
- Use GitNexus before broad exploration.
- Verify current @sentry/react APIs through Context7/current official docs.

Read:
- AGENTS.md
- webapp/AGENTS.md
- server/AGENTS.md where server runtime config changes are required
- docs/CODEX_WORKFLOW.md
- docs/LIVE_TESTING_DEBUG_RULES.md
- docs/WEBAPP_CUTOVER_CHECKLIST.md
- server/docs/CODEMAP.md
- existing backend observability implementation and runbook

======================================================================
GOAL
======================================================================

Add privacy-safe browser observability for the Helpdesk React application:

1. JavaScript/browser error monitoring.
2. React 19 error capture.
3. browser page/navigation tracing.
4. same-origin distributed tracing into the Helpdesk /api/* backend.
5. exact release/environment identity matching the deployed Helpdesk release.
6. runtime browser configuration without embedding environment-specific config
   into the immutable Vite bundle.
7. strict browser-side PII/content minimization.

Do NOT implement Session Replay.

======================================================================
ARCHITECTURE
======================================================================

Do not use VITE_SENTRY_DSN or another build-time environment secret/config.

The production bundle is immutable and should remain environment-independent.

Use the existing dynamic index.html delivery path:

server/static_pages/webapp_assets.py

Inject a small non-executable runtime configuration block into index.html,
preferably:

<script type="application/json" id="helpdesk-runtime-config">...</script>

The JSON must be serialized safely for HTML:
- no executable inline JS;
- prevent </script> breakout;
- no arbitrary environment values;
- explicit allowlist only.

Conceptual payload:

{
  "sentry": {
    "dsn": "...",
    "environment": "production",
    "release": "<exact 40-char Helpdesk SHA>",
    "tracesSampleRate": 0.05
  }
}

The browser DSN is a public client key by nature, but must still:
- come only from runtime configuration;
- never be committed;
- never be logged;
- be independently rotatable without rebuilding the webapp.

Add an environment entry equivalent to:

SENTRY_BROWSER_DSN=
SENTRY_BROWSER_TRACES_SAMPLE_RATE=0.05

to deploy/helpdesk/helpdesk.env.example.

Do not duplicate environment/release values unnecessarily:
- environment should derive from the existing application/Sentry environment
  policy;
- release must use the same immutable release identity already used by backend
  Sentry.

SENTRY_BROWSER_DSN empty/unset => browser Sentry disabled.

======================================================================
FRONTEND IMPLEMENTATION
======================================================================

Create a centralized browser observability module, e.g.:

webapp/src/observability/
  runtime-config.ts
  sentry.ts
  privacy.ts

Exact structure may vary if current architecture suggests a better location.

Initialize browser Sentry BEFORE rendering the React root.

Current entry point:
webapp/src/main.tsx

Do not scatter Sentry calls through page components.

Use the current official @sentry/react SDK and pin an exact reviewed version.

Because this application uses React 19, inspect current Sentry APIs for React 19
root error handling and use the supported mechanism rather than copying an old
React 17/18 recipe.

Do not add a visible debug/crash button or permanent crashing route.

======================================================================
ROUTING / TRACING
======================================================================

Use current official support for React Router v7 if available and compatible.

Goal:
transaction names should use known route templates, e.g.:

/app/tickets/:ticketId
/app/requester/tickets/:ticketId
/app/admin/operations/:operationId

and must NOT expose actual ticket/device/operation IDs.

Do not use raw location.pathname as a transaction name when it may contain IDs.

Browser tracing production target:

SENTRY_BROWSER_TRACES_SAMPLE_RATE=0.05

Errors are not sampled.

Configure trace propagation narrowly.

Allowed:
- same-origin Helpdesk /api/* requests.

Do not propagate sentry-trace/baggage to:
- arbitrary external origins;
- Sentry ingestion itself;
- Endpoint Platform directly;
- unrelated resources.

This should allow a browser transaction to connect to an incoming aiohttp
backend trace where supported.

======================================================================
PRIVACY POLICY
======================================================================

Browser events must be at least as restrictive as backend Sentry v1.

Mandatory:

sendDefaultPii = false

Do NOT send:
- Helpdesk user identity;
- employee names;
- email;
- ticket text;
- comments/chat;
- form values;
- search strings;
- URL query parameters;
- URL fragments;
- cookies;
- session identifiers;
- Authorization;
- CSRF token;
- access/refresh/consent tokens;
- request/response bodies;
- attachment contents;
- device credentials;
- arbitrary local/session storage;
- console log contents.

Disable/avoid breadcrumbs that can contain:
- console output;
- clicked element text;
- fetch/XHR URLs containing identifiers/query;
- navigation containing raw IDs.

Prefer maxBreadcrumbs=0 unless a reviewed safe breadcrumb allowlist is implemented.

Do not call Sentry.setUser().

Do not enable user feedback.

Implement last-mile beforeSend / beforeSendTransaction sanitization.

For browser exceptions preserve useful safe fields:
- exception type;
- sanitized stack filename;
- function;
- line/column;
- release;
- environment;
- approved route template;
- trace IDs/timing.

Arbitrary exception messages can contain user-entered Helpdesk content.
Follow the backend privacy principle:
- do not transmit arbitrary free-text error messages unless they match a small
  reviewed structural allowlist;
- otherwise replace/omit message while preserving type + stack.

Strip query/hash/userinfo from URLs.
Never transmit document.location.href verbatim.

======================================================================
SDK INTEGRATIONS
======================================================================

Minimize integrations.

Do NOT enable in this task:
- Replay
- Logs
- profiling
- user feedback
- console capture
- application metrics
- broad breadcrumbs
- browser session recording

Review default @sentry/react integrations.
If defaults collect more context than our policy allows, explicitly select a
minimal safe integration set rather than relying on defaults.

Use browser tracing explicitly.

======================================================================
RUNTIME CONFIG SAFETY
======================================================================

The injected runtime config must contain ONLY public browser-safe fields.

Never expose:
- backend SENTRY_DSN unless intentionally configured as the browser DSN;
- database URL;
- server environment map;
- credentials;
- tokens;
- private keys;
- backend internal configuration.

Prefer a separate:
SENTRY_BROWSER_DSN

for independent browser key rotation.

Invalid runtime values must fail closed:
- invalid/malformed DSN => Sentry disabled;
- invalid sample rate => safe default 0.05;
- invalid release => omit release;
- never log the supplied invalid value.

Production browser DSN must use HTTPS.

======================================================================
SOURCE MAPS
======================================================================

Do NOT implement production source-map upload in this patch.

Reason:
the current GitHub-hosted CI does not have network access to the internal
sentry.sosnadmin.local instance.

Do not publish .map files with production static assets.

Record source-map upload as a follow-up for the planned internal CI/scanner
runner.

Browser v1 must still work without source maps; stack frames may initially refer
to minified production assets.

======================================================================
TESTS
======================================================================

Add focused tests for:

1. runtime config injection:
   - absent browser DSN => disabled config;
   - valid config emitted;
   - exact release SHA emitted;
   - HTML/script breakout sequences safely encoded;
   - no unrelated environment/config values leak.

2. frontend config parser:
   - missing config => disabled;
   - malformed JSON => disabled;
   - malformed DSN => disabled;
   - malformed rate => safe 0.05.

3. SDK initialization:
   - initialized once;
   - sendDefaultPii=false;
   - Replay absent;
   - breadcrumbs/log capture absent;
   - tracing = configured rate;
   - environment/release correct.

4. privacy sanitizer:
   synthetic event containing:
   - email/name;
   - query string;
   - hash;
   - Authorization;
   - Cookie;
   - form/ticket text;
   - token;
   - localStorage-like data;
   - console breadcrumb
   must leave no private marker in the outgoing event.

5. route sanitization:
   actual values such as:
   /app/tickets/12345
   /app/admin/operations/opaque-secret-id
   must become the registered route pattern or a safe unresolved-route marker.

6. trace propagation:
   Helpdesk same-origin /api/* is allowed;
   arbitrary external origins are not.

7. existing static page/webapp behavior remains unchanged with Sentry disabled.

Tests must never contact the real Sentry server.

======================================================================
BROWSER VERIFICATION
======================================================================

Follow the repo browser skill.

Required evidence after implementation:
- webapp tests;
- production webapp build;
- Playwright affected flows;
- real browser load with Sentry disabled;
- console clean;
- network clean;
- no new horizontal/layout/UI changes.

Do not send a real Sentry event during automated CI.

======================================================================
DOCUMENTATION
======================================================================

Update appropriate current docs:

- deploy/helpdesk/helpdesk.env.example
- server/docs/RUNBOOK_HELPDESK_ENDPOINT_HOST.md
- webapp-related CODEMAP/docs if appropriate
- PLANS.md

Document:

SENTRY_BROWSER_DSN=
SENTRY_BROWSER_TRACES_SAMPLE_RATE=0.05

Explain:
- DSN is runtime-injected into HTML;
- browser DSN/client key is public by protocol but not committed;
- separate browser key is recommended;
- browser privacy policy;
- trace propagation only to same-origin Helpdesk API;
- source maps intentionally deferred to internal CI/scanner infrastructure;
- empty SENTRY_BROWSER_DSN disables browser monitoring.

======================================================================
NON-GOALS
======================================================================

Do not:
- modify backend Sentry v1 privacy guarantees;
- enable Session Replay;
- upload source maps yet;
- modify Sentry server;
- add Sentry MCP;
- add UI for observability;
- change authentication/session behavior;
- add DB migrations;
- deploy production;
- change Endpoint Platform.

======================================================================
VERIFICATION
======================================================================

Run at minimum:

python scripts/bootstrap_web_toolchain.py
pnpm --dir webapp test
pnpm --dir webapp run build

focused server static-page/runtime-config tests

python -m pytest server/tests/test_static_pages_handlers.py -q --tb=short
python scripts/verify_workspace.py
python -m compileall -q server scripts shared
git diff --check

Run additional impacted tests identified by GitNexus.

Perform a secret scan of the diff:
- no real Sentry DSN/client key;
- no SENTRY_AUTH_TOKEN;
- no credentials.

Then perform independent read-only review of:
- privacy boundary;
- runtime config injection;
- route sanitization;
- trace propagation;
- Sentry-disabled behavior.

======================================================================
ACCEPTANCE
======================================================================

Complete only when:

- browser Sentry is optional;
- real browser DSN is not committed;
- runtime config does not change immutable JS bundle per environment;
- React/browser errors are captured when configured;
- browser tracing uses 5% production sample rate;
- React Router route templates prevent ID leakage;
- trace headers propagate only to Helpdesk same-origin /api/*;
- browser event payload contains no PII/body/cookies/auth/query/hash;
- no Replay/logging/profiling is active;
- source maps are not exposed publicly;
- Sentry outage cannot break UI startup;
- all focused/full required checks are green;
- no production deployment occurs.

Final report:
- branch / HEAD;
- files changed;
- Sentry SDK exact version;
- runtime config design;
- privacy controls;
- routing/tracing design;
- tests and browser evidence;
- deferred source maps;
- residual risks;
- explicit confirmation no real DSN/token was committed.