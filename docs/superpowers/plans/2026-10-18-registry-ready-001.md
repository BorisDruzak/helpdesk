# REGISTRY-READY-001

Execute the supplied REGISTRY-READY-001 specification in order on
`codex/registry-ready-001`, based on main `520b6218`. Native execution; no extra
review agents or intermediate acceptance gates. Production and real-data changes
are excluded. Preserve unrelated untracked files.

| Confirmed problem | Component | Minimal change | Compatibility |
|---|---|---|---|
| Default select lacks options; local validator rejects managed types | Profile schema/runtime | Shared canonical options, recognize managed controls | Same phone/chat/email values |
| Custom values coerced to text/bool and silently truncated | Profile validation | Typed validation before writes, bounded patterns | Preserve stored values and expose correction issues |
| Used fields/options can disappear from schema | Schema preview/save/editor | Block destructive schema edits with usage count; edit labels and stable values | No rewrite of historical values |
| Requester overwrites organizational fields | Identity/Registry | Versioned per-field trust and pending proposals, audited admin decisions | No automatic confirmation of legacy data |
| Self-declared department contributes to audiences | Effective identity | Freeze legacy access baseline; exclude new untrusted values, opt-in strict policy and impact preview | No mass restriction enabled |
| Manager selection depends on support capabilities | Approval runtime/access | Confirmed and unambiguous manager resolution; explicit assigned-decision permission | Existing policy fallback and pending approvals retained |
| Readiness dispersed across quality/policy health | Registry quality | Extend read-only existing issues and UI with affected function and severity | Keep issue keys, exceptions, audit and redaction |

## Execution and verification

1. A: pure regression tests RED, strict typed writes/options/validation, legacy read
   issues, custom-select editor, default roundtrip and API persistence checks,
   frontend tests/build/browser checks.
2. B: inspect legacy access influence, provenance helpers and admin proposal
   decisions in existing Registry surface, effective identity tests and synthetic
   profile/audience API/browser checks. Strict legacy restriction stays disabled.
3. C: source-aware manager/fallback resolution, explicit assigned decision
   capability and requester pending decisions in existing approval system;
   positive/negative unit/API and ordinary-user browser coverage.
4. D: extend existing quality and Policy Health, aggregate concrete blockers,
   warnings and information; verify read-only and redacted export semantics.
5. End-to-end: synthetic profile -> v3 map -> ordinary ticket/device optional ->
   assigned approval; no real scenario publication. Record resource-picker limits.
6. Keep CODEMAP/docs current. Run workspace validation with `--workspace .`,
   focused tests and required hosted CI; inspect full diff, atomic Conventional
   Commits, push task branch and create/attach draft PR. No merge/deployment.

## Current state

Stages A–D are implemented on the task branch. Profile types/options/legacy reads,
organizational proposals and trust, explicit assigned decisions and read-only
readiness are covered by regression tests. No data migration or deployment.
GitNexus was consulted; its Helpdesk index is behind main, so dynamic boundaries
were checked in current source and tests. No manual index/group synchronization.

Verified: 840 frontend units; 1578 backend no-DB tests plus one existing skip;
12 fixture browser tests at 1366/1920 with clean JS/network checks;
PostgreSQL profile/schema/proposal5, assigned decisions2, v3 manager/fallback2,
read-only readiness1, effective-identity2. Broader Registry tests passed26 and
exposed two warning-contract assertions; both fixed and rechecked successfully.
The full synthetic profile -> v3 map -> no-agent ticket -> ordinary manager
decision -> organizational proposal/review -> audience change passed in PostgreSQL,
including preservation of historical ticket context. Exact-assignment privacy,
sequence, inactive identity and hidden profile-field preservation checks passed.
Build, workspace verification and strict test inventory/fixture audits passed.
The first assigned-approval RED run also had a disposable-DB drop timeout; the
GREEN rerun passed. Local Windows DB commands hit the configured
DNS placeholder; actual DB checks use isolated staging via the existing secret
channel. A workspace run correctly required matching docs; docs are now updated.

Remaining: finish inline diff review, stage only task files, commit/push verified
source, create and attach draft PR, verify required hosted CI. No independent
review agents or extra gates, no production or real-data changes. Owned fixture
servers exit with Playwright; no Helpdesk/Endpoint runtime services were started.
