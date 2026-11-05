# Requester home staging acceptance — 2026-11-05

Implemented the first displayed white-sidebar concept: two clear create/list
actions, grouped recent-ticket rows, compact profile and computer readiness.
The requester shell is separate from existing support/admin appearance; staff
workspace switching, profile, logout and ticket notifications remain available.

## Code and scope

- Branch: `codex/ui-support-001`.
- Runtime SHA: `881cf704f3b28cd41c9a42c71fd452e4a051c058`.
- Message: `feat(requester): simplify home and explain device connection`.
- The 20 committed files cover requester home/readiness/CSS, scoped sidebar/topbar
  and shell, Windows/Linux guide, component/browser tests, contract/CODEMAP and plan.
  Exact paths: `git show --name-only 881cf704f3b28cd41c9a42c71fd452e4a051c058`.
- Unrelated Studio/clipboard/worktime changes, including other CODEMAP/PLANS hunks,
  remain unstaged. No push, production deployment, Endpoint change or agent rollout.
- Profile and device ownership policies remain authoritative. Offline, missing,
  ambiguous and pending-review computers are distinct. Appropriate no-device
  requests remain available. Existing pending consents retain explicit decisions.

## Linux instruction boundary

Windows keeps the existing tray, copy/renew text and optional screenshots.
Linux / ALT Linux has a separate keyboard-accessible tab explaining hostname,
OS and department, with a link to the existing `device_owner_change` assistance
intent. Current Linux agents have no tray code UI; no native Linux self-service
issuance is claimed. A valid existing code can still be entered manually after
the server-authoritative profile check.

## Checks

- `pnpm --dir webapp test src/pages/requester/home-page.test.tsx src/pages/requester/device-link-page.test.tsx src/pages/requester/new-request-page.test.tsx src/components/shell/app-sidebar.test.tsx src/components/shell/app-topbar.test.tsx src/app/layouts/app-shell.test.tsx src/features/requester/queries.test.ts`: **64 passed**.
- `pnpm --dir webapp build`: passed. Canonical installer separately rebuilt the
  exact frozen Git source with its committed lockfile; no dirty bundle was deployed.
- `python scripts/verify_workspace.py`: passed.
- `git diff --cached --check`: passed before both commits.
- `PC_CLIENT_WEBAPP_E2E_PORT=4186 pnpm --dir webapp test:e2e tests/requester-home-redesign.spec.ts tests/requester-registration.spec.ts tests/requester-usability.spec.ts --output=../tmp/requester-home-20261105/browser`: initial **11 passed**.
- Final expanded `requester-home-redesign.spec.ts` at **1366x768, 1440x900,
  1488x1058, 1920x1080 and 390x844**: **5 passed** after typography refinement
  and explicit unbound Linux click-through. Covers primary visibility, no horizontal
  overflow, ready/incomplete/empty/error/retry states, profile gate, OS keyboard
  tabs, real image decode and the owner-check form/prefill without a device picker.
  Expected synthetic 503 reads are distinguished from unexpected browser errors.
- Independent read-only review found the wrong Linux intent; fixed through a
  failing regression and click-through coverage. Final review found no blockers.
- GitNexus requester architecture consulted; source/tests verified dynamic UI and
  policy relationships. AppShell impact lookup did not resolve, so no graph-only
  no-dependency claim is made. React guidance checked against pinned React19.
- Visual QA and combined comparison: [design QA](REQUESTER_HOME_DESIGN_QA_2026-11-05.md).

Full CI, backend DB suites, production gates and native agent installation/binding
were outside this frontend/instruction change. Existing bundle-size/npm environment
warnings remain nonfatal.

## Deployment and live browser

Approved isolated target only: `osn-admin@192.168.101.118`.
Canonical `scripts/deploy_helpdesk_release.py` ran through the existing protected
staging transport. Source baseline `ff8db7ec972745fe0b0731a93380942b5eda157b`
was an ancestor of the installed candidate.

Verified private pre-release backup: schema154, 13525338 bytes,
SHA256 `7b068f0bf9ab54950a334c6c827a176ae5c9f0abc79254d383636a8608d9bdef`.
Selector `/opt/helpdesk-staging/releases/helpdesk-881cf704f3b28cd41c9a42c71fd452e4a051c058`
and release identity match. All15 committed frontend runtime/test files match
normalized-LF Git SHA256. Schema stays154; strict CA/hostname HTTPS returns200
for Helpdesk and Endpoint. Helpdesk/Endpoint/worker staging units remain active.

Real authorized `admin` requester session opened the installed home, its own
ticket list, Windows/Linux guide, assistance intent and profile setup. Incomplete
profile and missing computer are visible; code entry is blocked until profile
completion. The real current catalog shows general help intake for this incomplete
account; automatic owner-form selection is fixture evidence with an available form,
not a claim that the current incomplete account has that form available.
No profile, consent, ticket or binding submission was made. Console errors0;
observed assets/API/catalog/profile/options responses200, loading failures0.
Create is visible without scrolling; live document width1265 <= viewport1280.
Final browser tab remains on the updated home.

Pre/post counts match: tickets75, events18108, artifacts5, users160, people44.
Staging remains available for the requested review; production is unchanged.

Private redacted evidence: `tmp/requester-home-20261105` (snapshot, verified backup
receipt, canonical deploy log, source/health receipt, browser screenshots and network
status summaries). Final screen: `live-home-final.jpg`; Linux: `live-linux-guide.jpg`.
