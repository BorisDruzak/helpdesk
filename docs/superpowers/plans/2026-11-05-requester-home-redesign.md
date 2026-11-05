# Requester home redesign implementation plan

**Goal:** Implement the first displayed visual concept on isolated Helpdesk staging, retaining profile and device readiness and explaining Windows/Linux device linking.

**Architecture:** Reuse requester bootstrap, existing ticket/consent queries, routes and authorization. Scope the light sidebar/topbar to requester; support/admin stay on their current shell. Home has an action area, recent tickets and a compact readiness section. Preserve explicit consent decisions.

**Tech stack:** React 19.2.5, React Router 7.14.1, TanStack Query 5.99.2, existing Tailwind/Lucide, Vitest/Playwright.

**Selected target:** First image displayed in chat: `.codex/generated_images/01a1ab99-ca0a-7f22-9934-6be77cafdec1/exec-24f0abcb-c0da-48c0-9eb6-0ff722a13726.png`. White sidebar, paired create/list actions and flat ticket rows. User explicitly authorized implementation and staging deployment.

## Constraints and rulings

- Actor: requester. Primary job: create an обращение. Secondary: read own tickets; complete profile/device setup. Archetype: task-oriented dashboard, at most three normal content zones.
- Staging only `osn-admin@192.168.101.118`, immutable canonical release. Preserve unrelated local edits and existing deployed changes. No push/production/fleet action.
- Profile completion remains server-authoritative; optional/no-device ticket policies and device ownership controls remain unchanged.
- Ruling: Linux agent currently has no tray/code UI (verified in Endpoint source and architecture doc). Explain Linux/ALT support-assisted linking without inventing UI or asking users to access protected credentials. Agent implementation is outside this instruction-only request.
- Ruling: preserve explicit pending consents as an exceptional additional action zone; visual simplification must not conceal authorization requests.
- User asked for a usable staging implementation; leave the staging application available, consistent with the existing staging acceptance instructions.

## Tasks

- [x] Add regression cases for readiness, ambiguous/pending/offline device states, consent decisions, empty/loading/error home and OS-specific instructions; observe failures.
- [x] Implement scoped requester shell, home actions/list/readiness and Windows/Linux guide without new dependencies or APIs.
- [x] Run focused tests, build, workspace verification and read-only review; update canonical docs/CODEMAP.
- [x] Validate built-browser fixtures at 1366/1920/mobile: actions, states, no overflow, instructions and console/network.
- [ ] Freeze only task files in a conventional commit; back up staging, use canonical installer and verify exact source hashes/TLS/runtime/read-only browser.

## Verification / handoff

Implementation/review complete. 64 component tests, build and workspace verification pass.
Initial 11 browser cases (home/registration/usability) and 5 expanded home cases pass;
final Linux unbound fixture rerun passed at all five widths. Review found an incorrect Linux intent;
fixed through a failing regression and click-through coverage. Visual comparison
identified undersized type; corrected and recaptured, design QA passed.
Baseline branch `codex/ui-support-001`, HEAD `ff8db7ec972745fe0b0731a93380942b5eda157b`;
unrelated Studio/clipboard/doc work remains untouched. Staging snapshot matches that
SHA, schema154, all three services active. Evidence: `tmp/requester-home-20261105`.
