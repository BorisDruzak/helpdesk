# Helpdesk phase-one acceptance — 2026-11-02

Status: completed for the requested staging scope. Source, isolated PostgreSQL,
browser fixtures, exact-release deployment and live requester/support acceptance
are complete. Staging remains running at the user's explicit request.

## Source candidate

Branch: `codex/ui-support-001`. Frozen runtime candidate:
`fb7d326c7e568f616d2829ec0c7a1bd318cc6f0e`.

| Commit | Message | Included surfaces and verification |
| --- | --- | --- |
| `4033b13cc5976192372c1e378114475babe2fe06` | `fix(auth): preserve profiles and clarify domain login recovery` | OIDC browser errors, login/registration components, SSO documentation and focused tests. Isolated PostgreSQL registration and real Authlib integration for user/support/admin/auditor passed; frontend and focused auth checks passed. |
| `cab4c8bf8e82d62ac9893729c2b9b9aec27b4776` | `feat(studio): add common phase-one request scenarios` | Canonical publication helper, four definitions, Other fixture, catalog procedure and tests. Catalog31 pure tests and3 isolated PostgreSQL tests passed. |
| `22d33252244fa3e9a4701b4de457d195850b175c` | `fix(requester): open created requests without extra preview actions` | Scenario session, component regressions and guided requester browser spec. Component28 and final requester16 browser cases passed. |
| `bc62a7cf45b7aa700b95179352cd0d90e92bd0a5` | `fix(helpdesk): simplify completion while preserving policy guards` | Support routes/navigation, public result, code-free completion, canonical workflow/closure and requester scope, effective metadata and authoring controls, focused tests and owning documentation. Final29 browser cases and PostgreSQL49 passed. |
| `fab497743887005c826dee5ea622d8ae7692174d` | `fix(helpdesk): remove live-flow friction in requester and support views` | Conditional projection race, terminal-session recovery, answer visibility, single queue navigation, plain facts/SLA and optional terminal actions, owning docs and regressions. Final947 unit tests,33 browser cases, TypeScript/build and workspace verification passed. Backend unchanged. |
| `fb7d326c7e568f616d2829ec0c7a1bd318cc6f0e` | `fix(requester): keep step actions clear of form fields` | Generalized normal-flow actions to every scenario step after a live old-map phone field was covered.35 focused session tests,35 actual browser cases, TypeScript/build, workspace verification and strict delta review passed. Questions, answers and navigation are unchanged. |

The phase-one section of `PLANS.md` is staged independently of unrelated
preexisting changes in that file and two older plans. No push or production
release occurred. Deployment builds from committed Git state, excluding
unrelated working-tree artifacts. Final acceptance documentation may have a
later documentation-only commit; the runtime candidate above remains deployed.

## Requested behavior

- Registration and profile/role authority remain intact. Existing-account login
  links now preserve the safe return path. Native browser SSO failures show static
  Russian recovery guidance without reflecting provider messages.
- AD login uses the domain password for all Helpdesk roles. Existing confirmed
  profiles retain the same person, login, role, binding and metadata.
- The processing preview starts automatically on the final scenario step.
  One explicit create action opens the ticket directly. Reload/resume, uncertain
  submission, blocked preview, stale terminal response and same-task double click
  have regression coverage.
- `/app/support` opens the compact queue; the previous center remains at
  `/app/support/advanced`. The problem and public result are visible in the card;
  long results expand without losing keyboard access or overflowing the page.
- Resolution code is optional stored metadata. Missing code no longer blocks
  historical closure policies or effective resolution/closure transition gates.
  The completion UI omits that field, preserving existing stored metadata.
- Ordinary completion uses one atomic resolved/closed command and a public result
  only when requester confirmation is explicitly boolean false. Approval,
  evidence, worklog, passport, role and other gates still apply. A failed second
  transition leaves no first transition or status audit behind.
- Requester confirmation, feedback and reopening use independent capabilities.
  Administrator requester actions retain the same own-ticket scope, including
  rereading ownership after a competing transaction releases the ticket lock.

## Studio content

Four additive maps collect password/login recovery, new account requests,
equipment replacement and website/business-system problems. They execute no
account, device or permission changes themselves.

The published Other map supplies the unchanged scope/urgency questions and SLA
decision. Pure runtime tests cover all six scope/continuity combinations for each
new map, conditional required fields, hidden-answer invalidation and backtracking.
Resolution durations remain authoritative120/180/300-minute source data.

The reviewed staging wrapper publishes ordinary closure version1.0.2 through
canonical services, with a public result and no required code/confirmation. It
checks exact host/release/database, uses protected runtime configuration before
server imports, checks a plan fingerprint, and compares old immutable versions,
drafts and ticket snapshots before/after publication. It also verifies idempotence.
Live application succeeded. Existing24 versions,40 drafts and65 ticket snapshots
were unchanged; repeat application was idempotent. Published version IDs are
retained in the task's `catalog-applied.json` receipt.

## Verification evidence

- `python scripts/verify_workspace.py`: passed.
- `pnpm --dir webapp test`: final full run158 files/947 tests passed in70.49s.
  The subsequent one-class all-step layout fix passed35 scenario-session tests
  and `pnpm --dir webapp exec tsc --noEmit`.
- `pnpm --dir webapp build`: passed after the final layout change.
- Final Playwright command from `webapp`: `npx playwright test
  tests/guided-requester.spec.ts tests/support-simple.spec.ts --output
  ../tmp/phase1-fixture-all-step-actions-final`:35 passed in1.3m.
  Required1366/1440/1920 desktop and820/390 fallback scenarios passed,
  including original minimum conversation-height and painted-field assertions.
  Instrumented page/console/network checks passed.
- Backend focused no-DB checks:70 passed in the implementer run; coordinator
  repeated the changed completion/metadata/form-preview targets:43 passed.
- Catalog isolated PostgreSQL:3 passed in266.74s; pure catalog:31 passed.
- Initial combined PostgreSQL run:37 passed,1 failed in791.34s. The failure was
  an invalid suggested-path setup in the new close-gate fixture. It was corrected
  while retaining the actual second-transition denial assertion.
- Final PostgreSQL run covers10 completion/API cases, closure policies, the full
  workflow-profile suite and two support detail/checklist cases:49 passed in
  1119.80s. Isolated databases/roles were removed by the harness.
- Git diff checks passed. Task and integrated reviews corrected terminal preview,
  capability/approval/evidence consistency, explicit confirmation opt-out,
  obsolete authoring controls and vertical layout. No unresolved review finding
  remains in the inspected source and staging wrappers.
- After live acceptance exposed further UI defects, the final full frontend run
  passed158 files/947 tests. Final rebuilt Playwright33 passed in1.2m
  (`tmp/phase1-fixture-polish-final2`), including painted answer/tail hit testing,
  same-category fresh requests and the reactive conditional-field race. Review
  found no remaining actionable issue. The final source/build check passed.
- The last layout correction also passed all35 browser cases in1.3m
  (`tmp/phase1-fixture-all-step-actions-final`). Required phone/contact fields and
  answer tails remain painted and editable with five back controls at1366/390;
  submitted contact values are preserved.35 focused session tests, TypeScript,
  build, workspace verification and independent source review passed afterward.

Earlier fixture failures remain in their original evidence. Category setup and
keyboard-scroll waiting were corrected in the fixtures; actual layout defects
were fixed in product CSS. Assertions were not weakened. Existing Authlib/aiohttp
deprecation warnings and Windows fixture-server disconnect teardown warnings are
recorded separately from passing browser assertions.

## Staging identity and readiness

A canonical private backup succeeded before changes:13,273,900 bytes,
SHA-256 `fc6b61154836a2c59a020af2ac11d4d4c149c9da0315d2873101df4e6b8fd64b`.
All three canonical deployments completed successfully. Final readback verifies
the exact runtime candidate, eight LF-normalized source digests against committed
blobs, strict TLS health200 and active `helpdesk-staging.service`. Only isolated
staging resources on192.168.101.118 were changed; production was not deployed.

Seven real owned synthetic tickets completed creation, direct opening, support
start, public reply and atomic code-free closure. The ordinary requester then
verified the public result and reply. Database readback confirms frozen scenario
versions, closure1.0.2, actual deadlines, first-response timestamps, both terminal
status events and no resolution code. No real account/device work was performed.

| Ticket | Live scenario and branch | Resolution / first response | Final state |
| --- | --- | --- | --- |
| T-000066 | Other, unknown subject, one person, can continue |300 /120 min | closed |
| T-000067 | Recovery, Other→known backtracking; hidden answer removed |180 /60 min | closed |
| T-000068 | New account, one person, can continue |300 /120 min | closed |
| T-000069 | Replacement, other equipment, department stopped |120 /30 min | closed |
| T-000070 | Business system, conditional field without blur; hide/reveal clears value |180 /60 min | closed |
| T-000071 | Repeated Other in same browser context; next new request starts blank |180 /60 min | closed |
| T-000072 | Existing Studio printer: jam→instruction acknowledgement→not helped→several people/degraded→network printer→description/location/phone |180 /60 min | closed |

The last printer form reproduced the old covered phone input. On the final
release it is painted, editable and included in the submitted answers at1366px;
fixture coverage additionally verifies390px and five back controls. No question
or SLA branch was removed to achieve the simpler interface.

Live support card captures at1366/1440/1920/390px show readable problem/result,
plain facts and SLA;390px facts open through an explicit drawer. No document
horizontal overflow was observed. The terminal public composer is absent.
Requester rating/reopen forms start collapsed; a voluntary rating on T-000072
was accepted with «Спасибо, оценка сохранена». This is separate from closure.

The final capture interval contains173 network responses, no failed responses
or loading failures, and no warning/error console entries. Superseded preview
cancellation is covered separately in browser fixtures. Browser SSO failure was
also checked after fully completing logout: a static Russian login recovery
message appeared at a fixed same-origin URL. An earlier automation attempt
navigated before logout settled; it is not counted as a product failure or pass.

The user explicitly selected a separate `admin-2` profile with administrator role.
Scoped reads proved no prior account/profile. The reviewed maintenance helper
verified the exact enabled federated provider identity, issuer and Helpdesk client,
then used canonical account/import/proposal/confirmation services. Existing
accounts were preserved. A repeated verification made no change.

Real browser login with the existing autofilled domain password reached
`/app/admin` as `admin-2`, without an OTP step; warning/error console logs were
empty. Screenshot: `tmp/phase1-20261102/admin2-domain-login.png`. The new profile's
personal fields remain for its owner to fill; they were not invented.

An owned ordinary synthetic requester fixture is ready with a complete profile.
Its random credential remains DPAPI-protected outside the repository. The
self-registration flag remains disabled as before. Enabled/disabled registration,
normal-user role issuance, invalid/duplicate inputs and existing-profile survival
passed in isolated PostgreSQL. Before a wider employee test, choose the intended
registration policy and provision/verify employee identity links and personal
profiles. Staging must remain running, per the explicit user request.

## Evidence, limits and next pilot preparation

Local sanitized receipts and screenshots remain under `tmp/phase1-20261102/`:

- `postdeploy.json`, `catalog-applied.json`, `live-readback.json`;
- `requester-final-checks.json`, `browser-final-network.json`;
- `printer-phone-fixed-1366.png`, `printer-closed-support-1366.png`;
- `printer-closed-requester-final.png`, `requester-final-390.png`;
- `support-final-1440.png`, `support-final-1920.png`, `support-final-390.png`,
  `support-facts-390.png`, `sso-browser-recovery.png`.

The administrator's browser tab remains open on the closed Studio printer ticket;
temporary viewport overrides were reset. Existing user tabs were preserved.

Before inviting many employees, select the self-registration/provisioning policy,
complete real employee profiles and verify exact identity links. Staging contains
historical test catalog entries and active synthetic support accounts; review the
pilot catalog and operator roster so test accounts do not receive real work.
They were not bulk deleted, archived or reassigned during this task.

The functional staging scope is accepted. Full CI, production release gates,
production deployment, fleet/device actions and load testing were not performed
because they are outside this task. Existing special approval/evidence/authority
policies remain enforced; the ordinary phase-one policy requires only the public
result for completion. No dependencies or schema migration were added.
