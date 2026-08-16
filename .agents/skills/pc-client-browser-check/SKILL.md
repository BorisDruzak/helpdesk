---
name: pc-client-browser-check
description: Use for pc_client browser-visible changes: webapp UI, admin UI, frontend behavior, forms, navigation, visual regressions, accessibility, console/network errors, screenshots, or real browser validation.
---

# pc-client-browser-check

## When to use

Use when a change affects browser-visible behavior.

Typical triggers: UI, browser, frontend, webapp, admin page, form, button, modal, route, screenshot, visual, CSS, React, Next.js, console error, network error, or accessibility.

## Inputs

- Target route or page.
- User flow.
- Expected visual or behavioral result.
- Affected browser surface.
- Screenshot or console/network error if available.

## Workflow

1. Identify browser-visible surface: route/page, component, form/action, expected user role, and expected state/data.
2. Check workspace state:
   - `git status --short`
3. Read relevant docs when available:
   - `docs/CODEX_WORKFLOW.md`
   - `docs/LIVE_TESTING_DEBUG_RULES.md`
4. Bootstrap frontend toolchain when the project requires it:
   - `python scripts/bootstrap_web_toolchain.py`
5. Start or connect to the project-approved local/dev server using documented scripts only.
6. Validate with a real browser or project browser MCP workflow:
   - open target route
   - perform the relevant user flow
   - verify visible result
   - check console errors
   - check network failures when relevant
   - capture screenshots/observations when useful
7. Run targeted frontend checks when available: lint, typecheck, unit/component tests, or e2e/smoke tests.
8. If a bug was fixed, verify that the old failure no longer reproduces.

## Rules

- Do not claim browser-visible behavior is fixed based only on code inspection or unit tests.
- Do not use browser validation as a substitute for relevant tests.
- Do not use tests as a substitute for browser validation when behavior is visible to the user.
- Do not leave dev servers running unless the user asked for it or project workflow requires it.
- Do not manually patch built assets unless the project explicitly documents that workflow.
- Check console/network errors when validating UI behavior.
- Verify Russian rendered text is not mojibake.

## Verification

Collect real browser evidence when the project supports it. Record the route/page, user flow, visible result, console/network status, and targeted frontend checks.

## Final response requirements

Include route/page tested, user flow tested, browser evidence collected, console/network status, frontend checks run, files changed, checks not run with reason, and residual UI risks.
