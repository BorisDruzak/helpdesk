# Support Context and screenshot preview — staging acceptance

Date:2026-11-05. Branch:`codex/ui-support-001`.
Installed commit:`228f59c0c279d8261883b720ab4a688b9529b4bb` —
`feat(support): add screenshot previews and a context panel`.

## Result

The ordinary support ticket at `/app/tickets/:ticketId` places description,
structured requester answers and the public result in a separate **Контекст**
block in the right inspector. The conversation starts directly below the header.
On narrow screens, **Сведения** opens that inspector; long public results keep
their existing accessible expansion. Requester pages and advanced tooling retain
their existing behavior.

Raster image attachments show lazy thumbnails. Clicking the thumbnail opens a
centered native dialog on the current page. Close, Escape and backdrop dismissal
are supported; focus returns to the thumbnail. Download remains a separate action.
The reply draft is preserved. Thumbnail/decode failures retain a download action.
Only the existing same-origin artifact route is embedded, with its supported
historical `ticket_id` ownership fallback; external URLs, unknown query parameters,
SVG/HTML and other document embeds are excluded. Existing server authorization
and attachment storage are unchanged. No dependency, route or migration added.

## Checks

- `pnpm --dir webapp exec vitest run src/pages/tickets/components/simple-support-ticket.test.tsx src/pages/tickets/components/simple-support-conversation.test.tsx src/pages/tickets/components/simple-resolution-form.test.tsx`:
  **32passed**. Includes right-panel placement, preview/download separation,
  legacy scope, rejected external/query URLs, MIME checks and failure fallbacks.
- `pnpm --dir webapp run build`: **passed**, including TypeScript.
- `PC_CLIENT_WEBAPP_E2E_PORT=14177 pnpm --dir webapp exec playwright test tests/support-simple.spec.ts`:
  **15passed**. Final centered modal/draft changes reran the4lifecycle cases
  selected with `--grep 'simple support lifecycle'`: **4passed** at1366x768,
  1440x900,1920x1080 and390x768. These4are repeated cases, not additional coverage.
- Browser assertions verify image decode, no download on preview click, Escape,
  focus restoration, centering, preserved reply draft, no horizontal body scroll,
  reachable primary actions, context access and long-result scrolling. The existing
  claim, public/internal privacy and advanced-inspector scenarios also pass.
- `python scripts/verify_workspace.py` and scoped `git diff --check`: **passed**.
- Independent source review: final verdict **no remaining findings**. A historical
  scoped-download compatibility issue was corrected and regression-tested.
- GitNexus attachment context was consulted before source exploration; current
  local composition and retained advanced entry were verified against source/tests.
  No server or cross-repository contract changed.

## Installed staging

Target:`osn-admin@192.168.101.118`, isolated `/opt/helpdesk-staging/current`.
A private verified schema154 backup was created before installation. The canonical
committed-release installer built the frozen-lockfile candidate, installed the
exact SHA above and retained schema154. All9changed source/test/doc hashes outside
PLANS matched the committed archive. Strict TLS health returned200 for Helpdesk
and Endpoint; Helpdesk, Endpoint and its worker were active. Staging remains running
as explicitly requested. Production, Endpoint code and native agent were not changed.

The initial release packaging caught an unsupported Testing Library test option
before any server installation. The unpublished commit was corrected; the final
exact-SHA build and installation passed. Earlier failed/interrupted fixture logs
are not acceptance evidence. Windows fixture teardown can emit connection-reset
noise after browser disconnect; the checked browser pages had no console/network
errors. Full CI/backend DB suites were not run for this frontend-only change.

Live browser acceptance used a new background tab, preserving the user's open
tabs/drafts. On real T-000075, all4answers appeared in the Context block. The
existing `Безымянный.png` thumbnail and full dialog image decoded successfully
(292x296); the page stayed on the same ticket URL. Closing restored thumbnail
focus. Console errors:0. No test message, upload or status command was submitted.
Local fixture ports14176/14177 were confirmed closed after checks.

Private evidence:`tmp/context-preview-20261105/`: `frontend-green.log`,
`build-final.log`, `browser-final.log`, `browser-centered.log`,
`deploy-final.log`, `installed-checks.json`, `browser-live.json`,
`staging-context.png`, `staging-image-viewer.png`, and responsive fixture screenshots.

## Files and limits

The feature commit contains the manifest below. Unrelated local PLANS/old-plan
edits and untracked artifacts remain unstaged. No push or production release.
Thumbnails use the authorized original image with lazy loading, without introducing
a server thumbnail-generation service. Non-image attachments keep download behavior.
Rollback uses the canonical previous-release procedure; no schema rollback required.


```text
PLANS.md
docs/SUPPORT_WORKSPACE.md
server/docs/CODEMAP.md
webapp/src/pages/tickets/components/chat-attachment.tsx
webapp/src/pages/tickets/components/simple-support-conversation.test.tsx
webapp/src/pages/tickets/components/simple-support-conversation.tsx
webapp/src/pages/tickets/components/simple-support-ticket.test.tsx
webapp/src/pages/tickets/components/simple-support-ticket.tsx
webapp/src/pages/tickets/components/simple-support.css
webapp/tests/support-simple.spec.ts
```
