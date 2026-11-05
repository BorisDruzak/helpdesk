# Requester screenshot preview — staging acceptance

Date:2026-11-05. Branch:`codex/ui-support-001`.
Installed:`cf51046d5f864f11fa4ea1dea40164acf2ce0a0b` —
`feat(requester): reuse in-page screenshot previews in chat`.

The authenticated requester chat at `/app/requester/tickets/:ticketId` reuses
the same screenshot thumbnail/modal as support, for both message senders.
Opening stays on the current ticket; download is separate. Escape, backdrop and
close restore the chat; the reply draft is preserved. Non-image downloads and
failure fallbacks remain available. Shared component and standalone CSS now live
under `webapp/src/components`, so direct requester entry loads the styles without
visiting support. Existing artifact ownership, cookie authentication, URL/MIME and
historical `ticket_id` scope guards are unchanged. No production backend route,
dependency, database migration or permission change.

Checks performed:

- `pnpm --dir webapp exec vitest run src/pages/requester/ticket-conversation.test.tsx src/pages/tickets/components/simple-support-conversation.test.tsx`: **20passed**.
- `pnpm --dir webapp exec playwright test tests/requester-workspace.spec.ts tests/support-simple.spec.ts --grep 'requester screenshot preview|simple support lifecycle'`
  with fixture port14178: **7passed** — requester1366/1920/390 and support1366/1440/1920/390.
  Verifies both senders' images, decode, centered preview without download or URL
  navigation, Escape/backdrop, focus restoration, draft preservation, explicit
  completed download, no overflow and no browser console/network errors.
- `pnpm --dir webapp run build`, `python scripts/verify_workspace.py`, scoped
  `git diff --check`: **passed**. Independent final review: no blockers.
- Binary fixture transport uses2fixed-image HTTP routes confined to the test
  server. Earlier `route.fulfill` downloads were canceled on Windows; those failed
  logs are not acceptance evidence. Real HTTP fixture downloads pass.

Deployment used the canonical frozen committed-release installer on isolated
staging `192.168.101.118`, after a verified private schema154 backup. All10changed
non-PLANS source/test/doc hashes matched; retired support-local viewer path was
absent. Schema remains154. Strict TLS health returned200 for Helpdesk and Endpoint;
Helpdesk, Endpoint and its worker were active. Staging remains running as requested.
Production, Endpoint/native code and business ticket state were not changed.

Live direct-requester browser check used retained `admin`'s own synthetic T-000058
in requester workspace. Its existing nonpersonal PNG decoded as thumbnail and full
420x100image, opened at the same URL, and closing restored thumbnail focus.
Console errors:0. Ordinary user role and responsive behavior were separately
verified by the fixtures. No new message/upload/status command was submitted.
The local fixture port was closed after tests. User tabs/drafts were preserved.

Private evidence:`tmp/requester-preview-20261105/`: `unit.log`, `build-final.log`,
`browser-green.log`, `deploy.log`, `installed-checks.json`, `browser-live.json`,
`staging-thumbnails.png`, `staging-preview.png` and responsive screenshots.
Full CI/backend DB suites were not run for this frontend-only change. Unrelated
local changes remain unstaged; no push or production deployment performed.
Rollback uses the previous committed release without a schema rollback.

Feature file manifest follows.

```text
M	PLANS.md
M	docs/SUPPORT_WORKSPACE.md
M	server/docs/CODEMAP.md
A	webapp/src/components/chat-attachment.css
R056	webapp/src/pages/tickets/components/chat-attachment.tsx	webapp/src/components/chat-attachment.tsx
M	webapp/src/pages/requester/ticket-conversation.test.tsx
M	webapp/src/pages/requester/ticket-conversation.tsx
M	webapp/src/pages/tickets/components/simple-support-conversation.tsx
M	webapp/src/pages/tickets/components/simple-support.css
M	webapp/tests/fixtures/support_fixture_server.py
M	webapp/tests/requester-workspace.spec.ts
```
