---
name: pc-client-browser-check
description: Use for pc_client browser-visible changes, webapp UI, admin UI, frontend behavior, visual regressions, forms, navigation, accessibility, Playwright/browser MCP validation, or screenshot-based verification.
---

# pc-client-browser-check

## When to use

Use for browser-visible server UI, `webapp/`, forms, navigation, visual state, frontend behavior, accessibility, screenshot checks, Playwright, or browser MCP validation.

## Inputs

- Changed route or user flow.
- Expected visible behavior.
- Local, remote, or project-approved browser target.
- Console/network symptoms when relevant.

## Workflow

1. Identify the changed browser-visible surface.
2. Use the project browser target unless explicitly told otherwise:
   - `https://192.168.100.17:9443/admin`
3. Read frontend/browser docs when available.
4. Bootstrap frontend toolchain when required:
   - `python scripts/bootstrap_web_toolchain.py`
5. Start or connect to the project-approved server.
6. Validate with real browser actions:
   - open target route
   - reproduce old behavior if applicable
   - verify new behavior
   - check console/network errors when relevant
7. Capture evidence:
   - route tested
   - user flow tested
   - screenshot or DOM-visible observation
   - console/network errors if any
8. Run targeted frontend checks when available.

## Verification

Browser-visible behavior is not verified by code inspection, direct HTTP, DB rows, or smoke tests alone. The final evidence must include the real browser route and visible result.

## Final response requirements

Include:

- browser route(s)
- scenario tested
- evidence collected
- frontend checks run
- limitations
