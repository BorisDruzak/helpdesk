# Quality / Observability Project Context

**Snapshot date:** 2026-10-02

This document records the current Helpdesk quality/observability direction so future work has one compact starting point.
It is context, not a deployment authority. Current `AGENTS.md`, runbooks, release gates and code remain authoritative.

## Current repository state

Repository:

`BorisDruzak/helpdesk`

Current main observed while writing this snapshot:

`03e0cb1557b714b6f21fbc20c73f473625a459ca`

Relevant recent work:

- Sentry backend observability v1 merged through PR #40.
- Sonar remediation / Endpoint cutover work is already in main.
- Browser Sentry v1 is the current observability follow-up.

## Quality / observability stack

### SonarQube

Self-hosted SonarQube Community Build 26.9 is available internally over HTTPS.

Responsibilities:

- reliability issues
- security findings
- maintainability
- duplication
- coverage after CI coverage integration
- quality gate

SonarQube MCP is configured read-only and intentionally exposes a restricted tool surface to Codex.

The first Helpdesk baseline scan is complete. Existing debt should not be treated as a reason to keep future CI permanently red; the target model is Clean as You Code.

### Sentry

Self-hosted Sentry 26.9.0 feature-complete is available internally over HTTPS.

Backend Sentry v1 status:

- merged
- production/live ingestion verified
- aiohttp error monitoring works
- tracing works
- release uses exact deployed Helpdesk Git SHA
- environment is production
- Sentry is optional observability, never an availability dependency
- privacy layer removes user identity, request bodies, cookies, auth headers, tokens, attachments and arbitrary Helpdesk free text before transmission

Relevant implementation:

- `server/observability/sentry.py`
- `server/observability/privacy.py`
- runtime config via protected `/etc/helpdesk/helpdesk.env`
- SDK pinned in `server/requirements.txt`

Browser Sentry v1 direction:

- React/browser errors
- React 19 error capture
- browser/navigation tracing
- same-origin Helpdesk API trace propagation
- runtime browser DSN injection through dynamically served `index.html`
- no environment-specific DSN baked into immutable Vite assets
- separate browser client key recommended
- no Session Replay
- no Logs/profiling/user feedback
- strict browser privacy sanitizer
- source maps deferred until the internal scanner/CI runner exists

## Current browser/runtime architecture relevant to Sentry

Frontend:

- React 19.2.5
- React Router 7.14.1
- Vite 8
- TypeScript 6

Entry point:

`webapp/src/main.tsx`

Production bundle:

- built from exact committed source
- packaged into the immutable Helpdesk release
- served under `webapp/dist`
- hashed assets are immutable
- `index.html` is served dynamically/no-cache by `server/static_pages/webapp_assets.py`

This makes runtime injection of a small public browser observability config preferable to `VITE_*` build-time environment configuration.

## Planned internal scanner / CI host

A dedicated `DEV-SCANNER` / `DEV-CI` VM is the next infrastructure stage.

Purpose:

- GitHub self-hosted Actions Runner
- Python 3.12
- Node 24.x / pnpm 10.33.x
- Docker
- pytest / coverage
- Vitest coverage
- Playwright / Chromium
- Semgrep Community Edition
- SonarScanner
- Sentry source-map upload later

Recommended initial sizing:

- Ubuntu Server 24.04 LTS
- 4 vCPU
- 12 GiB RAM
- 100 GiB disk

Do not run repository CI code on SonarQube or Sentry VMs.

**Codex Security is not part of the current plan.**

## Intended pipeline

PR:

```text
checkout
-> dependency install
-> compile/typecheck
-> pytest
-> Vitest
-> Playwright
-> Semgrep
-> artifacts
```

Initially Semgrep should be report-only while a baseline is classified.

Main:

```text
full canonical CI
-> Python coverage.xml
-> frontend lcov.info
-> SonarScanner
-> SonarQube quality gate
```

Later, on the internal runner:

```text
exact production webapp build
-> hidden source maps
-> upload to self-hosted Sentry
-> remove .map from deployable artifact
```

Public production assets must not expose source-map files.

## Semgrep role

Semgrep is intended as an independent deterministic SAST layer, not a replacement for SonarQube.

Initial coverage:

- Python
- JavaScript / TypeScript
- common security rules
- secret patterns

Likely project-specific rules after baseline:

- auth/RBAC bypass patterns
- unsafe subprocess / shell execution
- unsafe path/file handling
- token or credential logging
- SQL construction
- WebSocket authorization boundaries
- Helpdesk/Endpoint credential-boundary violations

Target policy:

- existing reviewed debt -> baseline
- new high-confidence security regressions -> fail CI

## Separation of responsibilities

```text
SonarQube
-> static quality / maintainability / reliability / coverage

Semgrep
-> independent deterministic SAST and project-specific security rules

Sentry
-> runtime production/staging errors and tracing

GitHub self-hosted runner
-> executes tests/build/scanners and publishes artifacts/results

Codex
-> consumes bounded results through tools/MCP and implements reviewed fixes
```

## Security / privacy invariants

- Never commit real Sentry DSNs/client keys merely for convenience.
- Never commit Sonar/Sentry auth tokens.
- Runtime secrets stay outside immutable releases.
- Do not send ticket text, chat/comments, attachments, user identity, cookies, authorization headers, access/refresh/consent tokens, or environment contents to Sentry.
- Sentry outage must not break Helpdesk.
- Keep Session Replay disabled until there is a separately reviewed privacy decision.
- Browser source maps must be uploaded privately to Sentry and removed before public artifact publication.
- Scanner runner should not receive production deployment/root access by default.

## Near-term sequence

1. Finish Helpdesk Browser Sentry v1.
2. Live-verify browser error event privacy and frontend->backend tracing.
3. Create and harden DEV-SCANNER / DEV-CI.
4. Register a repo-scoped GitHub self-hosted runner.
5. Add Semgrep in report-only mode and classify baseline.
6. Move SonarScanner from manual ADMIN-2 execution to the runner.
7. Add Python/JS coverage inputs to Sonar.
8. Add private Sentry source-map upload from the internal runner.
9. Tighten CI to block only new, high-confidence regressions.

