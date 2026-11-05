# Helpdesk session → WorkTime employee login

## Approved intent and boundaries

The user explicitly approved Helpdesk-account login to WorkTime after employee
registration, without entering credentials again, plus an AD login option in
Helpdesk. All registered employees, including local accounts without AD, can
enter their own WorkTime cabinet. The prior proposal was a server-validated
one-time handoff, not shared passwords/cookies. Existing AD identity linkage is
explicit; no name/email/login matching or automatic privileged grants.

Staging only, leave both services running. Production/agent/telemetry/ownership
flows are outside scope. Do not replay historical WorkTime activation receipts.
Preserve existing personnel records and active authorities. No new dependencies.

## Approach

Security references: [PKCE S256](https://www.rfc-editor.org/rfc/rfc7636#section-4.6)
and browser-bound state with exact redirect validation.

Reuse the existing fixed environment pair and confidential Helpdesk identity
service credential. Extend that narrow server-to-server contract for WorkTime.
Endpoint starts a browser-bound state/PKCE flow; Helpdesk authorizes its current
web-cookie account and returns a one-time code; Endpoint exchanges it and issues
an independent **WorkTime-only** cookie. Helpdesk cookie/password never leave
Helpdesk. No synthetic AD GUID or assumed AD identity is created.

Rejected: copying browser cookies/passwords; granting roles from username;
pretending a local Helpdesk user has an AD GUID; sharing the new authority with
DLP/admin; disabling the existing AD identity/assurance checks.

## Browser flow

1. Helpdesk «Рабочее время» opens the fixed Endpoint
   `/auth/worktime/helpdesk/login` when handoff is enabled; otherwise retains its
   old `/employee` target. Existing trusted origin-pair validation remains.
2. Endpoint stores a 5-minute flow: state digest, browser-cookie digest,
   encrypted PKCE verifier; uses a dedicated secure HttpOnly SameSite=Lax flow
   cookie. Redirects to fixed Helpdesk
   `/api/web/session/worktime/authorize` with state, S256 challenge and exact
   fixed callback URI. No arbitrary client/callback/origin accepted.
3. Helpdesk requires the actual browser web-cookie session, active account,
   unexpired/unrevoked UiToken and complete active own profile. Existing OIDC
   sessions also revalidate through `validate_oidc_session`. Header/service auth
   cannot authorize browser handoff. Missing login goes through a small
   `/app/worktime/connect` continuation route and existing `/app/login?next=...`;
   incomplete profile shows an explicit setup link, without guessing a person.
4. Helpdesk stores a random code digest, source token hash, own person ID,
   challenge, fixed audience/callback, 60-second expiry and consumed marker.
   It returns a no-store HTML form that auto-POSTs code/state to the exact
   Endpoint callback. Nonce CSP/form-action and origin-only referrer; include a manual
   Continue button. Codes never enter query strings, referrers or access logs.
   A real browser probe confirmed that no-referrer turns POST Origin into null;
   origin-only preserves strict expected-Origin validation without a path/query.
   Other redirects/responses retain no-referrer.
5. Endpoint verifies expected Origin, flow state/browser binding/expiry, then
   atomically consumes the flow before confidential exchange. The code is
   separately single-use under a Helpdesk DB lock and requires its verifier.
6. Endpoint sets `endpoint_worktime_session`, redirects to clean `/employee`.
   This is a WorkTime-only authority, even when the Helpdesk account is admin.
   Its lifetime is bounded by source session and at most8 hours; every API call
   introspects the opaque encrypted server-held lease with Helpdesk. Source
   logout, revocation, account disable, profile deletion/relink or expiry ends it.
   Provider failure is503, not a successful/empty or silently expired session.
   Validation by stored source token hash must reuse canonical token rotation
   grace, password-login-enabled and Registry-block checks. Add an opt-in typed
   OIDC-provider-unavailable outcome; existing OIDC callers keep their behavior.

Both handoff feature flags default false. Enabling requires reviewed exact-SHA
deployments and current fixed staging origins; no new service secret is exposed.

## Minimal version1 Helpdesk provider contract

All integration calls require the existing dedicated identity service Bearer
credential, bounded JSON, no redirects/proxy trust, verified TLS and rate limits.
Extra fields, malformed/noncanonical UUIDs and credentials fail closed. Responses
are no-store; errors never echo credentials, codes or request bodies.

- POST `/api/integration/v1/worktime/sessions/exchange`:
  `{code, code_verifier, redirect_uri}` →
  `{version:1, handle, person_id, department_id, expires_at}`.
- POST `/api/integration/v1/worktime/sessions/introspect`:
  `{handle}` → `{version:1, state:"active", person_id, department_id, expires_at}`.
- POST `/api/integration/v1/worktime/people/resolve`:
  `{person_id}` → `{version:1, state:"active", person_id, department_id}`.
  This reads an active profile with a verified account alias or confirmed AD
  binding and active UI account, not arbitrary directory contents. Existing
  personnel managers may use this to revalidate local Helpdesk targets; no names
  or HR contents are exposed.

Lease handles are random43-character urlsafe secrets stored only as hashes in
Helpdesk and encrypted with Endpoint's existing Fernet key at the consumer.
They expose only this source session/person; they are never browser credentials.
Issuer for a new local person is the configured Helpdesk origin; subject is the
canonical person UUID. No roles/grants/AD claims are returned by these APIs.

## Endpoint identity and authority model

Reuse the existing clean staging baseline checkout under
`C:/Users/admin-2/Documents/endpoint/.worktrees/worktime-recorded-release-20261030`,
at1b6ce5a83dd17852ecca724c1b45378ac8536041, on a new codex branch. The primary
Endpoint checkout has unrelated dirty state and remains unchanged.

- Add explicit `authority_kind` (`oidc` default / `helpdesk`) to
  ConfirmedIdentity; AD GUID nullable only for Helpdesk identities, enforced by
  check constraints. Preserve person uniqueness and all existing OIDC values.
- Add dedicated WorkTimeLoginFlow and HelpdeskWorktimeSession models.
  Do not change EmployeeSession/UpstreamSession tables or DLP/admin cookies.
- New `/api/employee/worktime/session` GET/DELETE and `require_worktime_employee` accept
  the new cookie; absence retains old AD employee authentication. An invalid
  present WorkTime cookie must not silently switch to another person's AD session.
- The new principal is marked `auth_source=helpdesk`, has no grants or privileged
  assurance. WorkTime endpoints use this dependency; other employee/DLP/admin
  endpoints keep the original dependency. Explicitly reject all cross-person,
  manager/HR/configuration and privileged actions from the Helpdesk principal.
  `visible_people` returns only self before considering any existing grants.
- Unsafe WorkTime requests and logout validate CSRF against the selected
  WorkTime cookie; its session endpoint returns that exact matching CSRF token.
  Missing tokens and tokens for the old AD/DLP cookie are rejected.
- Local confirmed person rows permit existing WorkTime locking/business logic,
  but create no WorkState, schedule, correction, activity/device binding or
  privileged grant during login. Own WorkTime read/write uses freshly verified
  Helpdesk authority. Existing OIDC principals revalidate local targets through
  the new people/resolve contract before existing personnel authorization.
- If later a verified AD callback resolves exactly the same person as an existing
  Helpdesk identity, promote that same locked identity row to the exact verified
  AD issuer/sub/GUID. Never create duplicates, infer a link, replace a different
  AD binding, move history or change any grants. Existing OIDC callbacks otherwise
  retain their checks and behavior.

## UI

Helpdesk login already has working OIDC capability. Label its existing button
«Войти через AD», explain «Доменная учётная запись»; retain local password login,
safe next routing and existing errors for unlinked/inactive identities.

WorkTime login offers «Войти через Helpdesk» for normal portal navigation and
retains its AD option. DLP and agent companion bootstrap retain their AD entry
and proof requirements; handoff does not claim native device possession.
WorkTime EmployeePortal uses its new session API; DLP keeps the old employee API.
Sign-out revokes the selected authority, not the other realm or Helpdesk login.
Explicit WorkTime AD login starts the existing employee OIDC flow with an
encrypted flow marker; only its successful verified callback clears the
WorkTime-only cookie. Normal invalid-cookie failures never silently fall back.
This prevents a stale handoff cookie from shadowing an intentional AD login.

## Migration, contracts, rollout, verification

Helpdesk migration153 after current152: code and lease hash records only.
Endpoint migration0044 after current0043: identity discriminator/nullable AD GUID
with explicit constraint and the two dedicated tables. Existing AD rows retain
their identity, grants and sessions. Back up both isolated staging databases;
verify revisions immediately before migration through canonical release scripts.
Update owning CODEMAP/SSO docs, provider contract and Endpoint published OpenAPI
for new API routes. Do not edit GitNexus managed manifests; document discovery
gaps and source-verify both ends if reverse-direction contracts are not indexed.

Tests: state/browser mismatch, invalid callback/origin/audience, S256 proof,
replayed/expired code and lease, concurrent exchange, logout/revocation/account
disable/profile relink, OIDC source revalidation, fail-closed503, self-only access
including when the same identity has HR/admin grants, DLP/admin rejection,
old AD session fallback, local→confirmed AD promotion, unchanged personnel rows.
Use isolated DBs and frontend mocks, then a real staging Helpdesk-session→WorkTime
navigation. No live start/end day, correction, role grant or device action is
necessary. Browser checks include mobile/desktop, clear errors, no credential
in URLs/logs, and persistence across reload. Leave staging running.

Implementation details left to builder: module factoring, DTO class names,
appropriate existing audit/rate-limit helpers and test fixture reuse. Security
invariants and scope above are fixed by the approved request and current contracts.
