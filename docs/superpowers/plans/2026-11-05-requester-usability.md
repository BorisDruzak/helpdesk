# Requester usability follow-up implementation plan

**Goal:** Apply the four explicit browser comments and investigate Helpdesk-account access to WorkTime.

**Actor / composition:** requester; registration remains a three-step wizard, new
request remains a search-and-select catalog followed by its existing form or
guided scenario, device linking remains one proof-entry form with inline help.
Use the current React19.2.5/TanStack Query5 stack; no dependencies or API changes.

**Decisions from the request:** one searchable department control; separate
show/hide buttons for password and confirmation; one whole-catalog search that
opens all available categories on focus, categories expand their published
problem entrances; Windows tray/menu instructions based on supplied screenshots.
Retain the existing server search, availability filtering, explicit scenario
selection, drafts, retries and authentication. No ticket or binding is created
during visual checks. WorkTime is investigation only until its actual identity
contract is established; never infer an AD identity from a local Helpdesk login.

## Tasks

- [x] Registration: add a small accessible searchable-select and password field;
  test actual selection, free text rejection, keyboard, preserved back values,
  show/hide without submitting; preserve frozen signup retry payload.
  Files: components/ui/searchable-select.tsx, components/ui/password-input.tsx,
  features/auth/registration-wizard.tsx and guided-registration tests.
- [x] Catalog: extend CatalogSearch with the current available category model,
  one input, collapsible categories and explicit leaf selection. Remove the
  duplicate category selector and entrance search on this page; preserve legacy
  single-entrance and restored explicit scenario behavior. Tests must cover
  no automatic dispatch, restricted options, search errors/clear/retry, category
  browsing and direct-link/draft preservation. Files: features/requester/catalog-search*,
  scenario-entrances*, pages/requester/new-request-page*, new-request-panels.tsx.
- [x] Device guide: inline three-step text and two provided tray/menu images,
  collapsed illustrations so input/action remain visible. Do not publish the
  supplied one-time code screenshot. Explain expiry, renewal, missing icon and
  support fallback. Existing proof and ownership-review behavior stays intact.
- [x] WorkTime: use GitNexus group status/query plus source and live login entry
  to identify current trusted identity/session requirements and document the
  difference between local Helpdesk signup and AD SSO. No auth/role/data changes.
- [x] Run focused component tests, current TypeScript/build and real browser
  fixtures at1366/1920/mobile with console/network evidence. Review full diff,
  update registration/catalog docs/CODEMAP/own PLANS section, workspace verify.
- [ ] Commit only task files, deploy exact reviewed SHA through canonical staging
  release script, verify matching runtime and live public registration/guide
  flows where authorized. Keep staging running. No production or push.

## Review focus

Unselected typed department must not submit an old ID; keyboard Enter selects
without advancing signup; toggles retain values and never submit; old search
responses cannot choose a hidden offering; browsing does not start scenarios;
explicit entry/drafts survive reload; help images carry no live proof codes.

Implementation is native in the existing checkout, preserving unrelated changes.
Acceptance evidence: tmp/requester-usability-20261105 and a final report under docs.

## Verification before deployment

Focused41 pass; build/typecheck pass. Existing browser27 cases pass; final new
3 cases pass1366/1920/390 including assets, explicit scenario/reselection and guide.
Initial selector mismatch and non-served guide URL were caught and corrected.
Independent static review clean. Fresh verified staging backup at
`/var/backups/helpdesk-requester-usability-20261105/backup.json`; schema152.
