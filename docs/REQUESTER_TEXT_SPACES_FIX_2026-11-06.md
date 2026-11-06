# Preserve spaces while entering a requester form — 2026-11-06

User report: description words join together while typing a new request. The
shared `RequestFormFieldControl` rendered a normalized value on every keystroke;
`normalizeEditableFieldValue` called the submission codec, whose string `.trim()`
removed each trailing space before the next character could be entered.

## Fix and scope

`webapp/src/features/requester/dynamic-form/index.tsx` renders the raw string for
text/textarea/phone/email/url controls. Normalization, required checks, schema
validation, default/prefill merging, review and payload helpers remain unchanged.
Numeric/select/checkbox handling and invalid-checkbox fallback remain unchanged.
No new state/dependency, server/API/auth/profile change, schema or data repair.

Regression coverage:

- `dynamic-form/dynamic-form.test.tsx`: sequential character entry preserves
  leading, trailing and repeated spaces in text, textarea and phone; textarea
  newlines survive. Required whitespace-only remains empty, payload edges trim.
- `scenario-session.test.tsx`: editing and explicit answer retain internal spaces,
  line breaks and the current trailing space in the guided-session request body.
- `webapp/tests/requester-text-spaces.spec.ts`: browser key events including Space
  and Enter at 1366x768, 1920x1080 and 390x844. A normalized server step-preview
  cannot overwrite live editor values. Description/room/phone values survive to
  answer, no ticket is created, no console errors/unexpected API calls or overflow.

## Checks

- Initial component regressions failed 3/3 on the old renderer, then passed.
- `pnpm --dir webapp test src/features/requester/dynamic-form/dynamic-form.test.tsx src/features/requester/scenario-session.test.tsx src/features/requester/scenario-session-attachments.test.tsx src/pages/requester/new-request-page.test.tsx`: 141 passed.
- `pnpm --dir webapp build`: passed.
- `python scripts/verify_workspace.py`: passed.
- `PC_CLIENT_WEBAPP_E2E_PORT=4189 pnpm --dir webapp test:e2e tests/requester-text-spaces.spec.ts --output=../tmp/requester-spaces-fix-20261106/browser`: 3 passed.
- Independent scoped review: no actionable findings. Email/URL use the same raw
  renderer branch; native sanitization remains the browser's responsibility and
  has no dedicated new keystroke test. Existing validation tests pass.

GitNexus MCP was unavailable in this session. The affected shared control and its
scenario caller were verified directly against the current source and accepted
Git baseline. React 19.2.5 controlled-input behavior was checked against official
React documentation through Context7. CODEMAP records raw editing vs normalization.

Exact immutable staging install, backup, source hashes, health and business-count
acceptance are appended after deployment. Full CI and production are outside this
targeted staging task. Existing unrelated shared checkout/index work is preserved
using a private index based on `2ed60576070064c5d468778e0c26aa9a8486676b`, retaining
the accepted SLA repair and prior requester/catalog improvements.

Private evidence: `tmp/requester-spaces-fix-20261106` and matching test/build logs.
