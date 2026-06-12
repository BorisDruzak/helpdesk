# Browser / Requester / Agent Identity Model Signoff

Status: completed and preserved as a non-regression boundary for Knowledge vNext.

Date: 2026-06-12

This document preserves the completed Browser / Requester / Agent identity and consent model that previously lived only in the rolling `PLANS.md` history. Knowledge vNext must treat these flows as already completed product behavior, not as implementation space for refactoring or replacement.

## Completed Scope

Stage 1:

- Browser-mediated device registration and login.
- Web session to `RegistryPerson` resolution.
- Admin UI user to RegistryPerson linking.
- Same-origin protection for unsafe web-session cookie requests.

Stage 2A:

- Authenticated requester workspace under `/app/requester`.
- Requester-safe APIs under `/api/web/requester/*`.
- Requester ticket bootstrap, list, detail, message, close, feedback and reopen.
- Requester-safe ticket timeline projection.

Stage 2B:

- Requester attachments through same-session upload references.
- No-device requester ticket creation with server-owned placeholder device context.
- Public ticket claim-to-account through `/api/web/requester/tickets/claim-public`.
- Strict person requirement for claim: unlinked web users receive `REQUESTER_IDENTITY_REQUIRED`.
- Shared-device privacy: requester views remain scoped by person, binding and account session.

Stage 3:

- Canonical `UserConsentRequest` model.
- Requester browser consent APIs under `/api/web/requester/consents/*`.
- Agent consent APIs under `/api/registry/agent/consents/*`.
- Consent-required operation creation and retry integration.
- Remote Assist browser consent to agent technical-start path.
- Agent account-session consent boundary.
- Redacted consent and retry payloads.

## Evidence

Evidence artifacts under `artifacts/` are local/untracked operational artifacts and are not guaranteed to exist in a fresh GitHub checkout. Preserve them outside git for audits; if they are absent, rerun the listed regression commands and live audit before relying on this signoff.

Primary full live audit:

- `artifacts/requester-agent-consent-full-live-audit-20260611-183743/`
- Pointer file: `artifacts/latest_requester_agent_full_live_audit.txt`

Primary API and DB evidence:

- `artifacts/requester-agent-consent-full-live-audit-20260611-183743/api/api-results-final.json`
- `artifacts/requester-agent-consent-full-live-audit-20260611-183743/db/db-results-final.json`

Primary browser evidence:

- `artifacts/requester-agent-consent-full-live-audit-20260611-183743/screenshots/01-requester-dashboard.png`
- `artifacts/requester-agent-consent-full-live-audit-20260611-183743/screenshots/02-requester-ticket-detail.png`
- `artifacts/requester-agent-consent-full-live-audit-20260611-183743/screenshots/03-shared-device-privacy.png`
- `artifacts/requester-agent-consent-full-live-audit-20260611-183743/screenshots/04-support-command-center.png`
- `artifacts/requester-agent-consent-full-live-audit-20260611-183743/browser/console-shared-requester.json`
- `artifacts/requester-agent-consent-full-live-audit-20260611-183743/browser/network-shared-requester.json`
- `artifacts/requester-agent-consent-full-live-audit-20260611-183743/browser/console-support.json`
- `artifacts/requester-agent-consent-full-live-audit-20260611-183743/browser/network-support.json`

Focused requester Stage 2B evidence:

- `artifacts/requester-stage2b-live/requester-chat-detail.png`
- `artifacts/requester-stage2b-attachments/`
- `artifacts/requester-stage2b-no-device/`
- `artifacts/requester-stage2b-profile/`
- `artifacts/requester-stage2b-device-detail/`

Final audit checks recorded in artifacts:

- `artifacts/requester-agent-consent-full-live-audit-20260611-183743/tests/pytest-requester-workspace-output.txt` - 16 passed.
- `artifacts/requester-agent-consent-full-live-audit-20260611-183743/tests/pytest-consent-retry-tool-output.txt` - 18 passed.
- `artifacts/requester-agent-consent-full-live-audit-20260611-183743/tests/pnpm-test-output.txt`
- `artifacts/requester-agent-consent-full-live-audit-20260611-183743/tests/pnpm-build-output.txt`
- `artifacts/requester-agent-consent-full-live-audit-20260611-183743/tests/verify-workspace-output.txt`
- `artifacts/requester-agent-consent-full-live-audit-20260611-183743/tests/git-diff-check-output.txt`

## Regression Commands

Run these before changing requester, consent, ticket workspace, Remote Assist, browser-auth, Knowledge deflection, support timeline or agent consent surfaces:

```powershell
python -m pytest server/tests/test_requester*.py -q
python -m pytest server/tests/test_user_consent*.py -q
python -m pytest server/tests/test_operation_retry.py -q
python -m pytest server/tests/test_web_session_api.py -q
python -m pytest server/tests/test_registration_api.py -q
python -m pytest server/tests/test_tools_async_response_contract.py -q
pnpm --dir webapp run test -- requester
pnpm --dir webapp run build
python scripts/verify_workspace.py
```

If exact selectors change, use the closest focused requester, consent, browser-auth and requester-knowledge tests and record the actual commands in `PLANS.md`.

Knowledge/requester regression add-on:

```powershell
PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_requester_workspace_api.py server/tests/test_knowledge_feedback.py server/tests/test_knowledge_ask.py server/tests/test_ticket_knowledge_links_compat.py -q --tb=short
pnpm --dir webapp test -- src/pages/kb/ask-page.test.tsx src/pages/requester/index.test.tsx src/features/requester/api.test.ts src/features/knowledge/api.test.ts src/app/navigation.test.ts
```

Knowledge changes that touch search, Ask, requester ticket draft, feedback, deflection or portal routing also require a live/browser checklist:

- requester knowledge suggestions render and remain requester-safe
- Ask AI-off fallback -> `/app/requester/new` prefill works
- requester ticket create is submitted with `knowledge_attempts`
- `ticket_created_after_view` analytics are recorded after submit
- public `/app/help` deflection remains backward-compatible
- `/app/kb/*` redirects unauthenticated users to login and does not expose support/admin diagnostics to requesters

## Non-Regression Boundaries

Knowledge vNext must not break:

- `/app/requester`
- `/api/web/requester/*`
- requester ticket create, preview, detail, message, attachment, close, feedback and reopen
- requester no-device ticket creation
- public ticket claim-to-account
- requester knowledge suggestions and `knowledge_attempts`
- `surface=requester_portal` analytics
- `ticket_created_after_view` feedback
- public `/app/help` requester flow
- public `/app/ticket/:ticketId` access-code flow
- `UserConsentRequest`
- `/api/web/requester/consents/*`
- `/api/registry/agent/consents/*`
- Remote Assist browser consent
- agent account-session consent boundary
- shared-device privacy

## Data Privacy Boundaries

- Requester APIs must resolve ownership from authenticated web-session identity, active binding and account session, not from caller-supplied foreign ids.
- Requester-safe projections must not expose internal queue ids, device internals, raw policy payloads, support-only knowledge items, admin-only knowledge items, operation internals or raw diagnostic metadata.
- Public claim flow must not store or echo access codes in audit or ticket events.
- Consent request payloads may preserve parameter names for scoped approval context, but sensitive values must be redacted.
- Remote Assist requester consent list/detail/decision responses must not expose ICE, SDP, signaling, agent token, viewer token, session token, cookie or authorization material.
- Unsafe cookie-auth browser writes must require same-origin `Origin` or `Referer`; bearer/agent-token flows are separate.

## Known Non-Goals

- This signoff does not make Knowledge Core depend on ticket-specific code.
- This signoff does not require AI, embeddings, RAG, OpenRouter or vector search for requester ticket creation or baseline requester workspace behavior.
- This signoff does not require automatic ticket creation after every knowledge view; only explicit requester actions may carry `knowledge_attempts` and `ticket_created_after_view` metadata.
- This signoff does not approve any path that exposes support/admin-only knowledge to requester/public surfaces.
