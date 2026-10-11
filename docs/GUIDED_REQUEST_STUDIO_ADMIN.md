# Guided Request Studio administration

The admin/auditor entry is `/app/admin/request-template-studio`. It opens the
catalog by default. Search and status filters run on the server. Selecting a
category includes all its descendants before pagination. The catalog also shows
existing offerings without a scenario as **Обычная форма / нет сценария**, with a
link to the existing Forms editor and an admin action to create a scenario for
that offering. Existing form-only consumers continue using their canonical forms.

**Создать сценарий** opens a five-step wizard: category/purpose, user scenario,
ticket processing, testing, publication. Only the selected step is rendered.
Choose an existing offering by its human title; the corresponding service and
request template binding are set together. Technical keys live in the local
**Расширенные настройки** disclosure, rather than a global mode or another tab.
The service/offering/template binding cannot be replaced on a saved scenario.
Later steps become available after saving a valid purpose/offering binding;
navigation between them preserves local changes. The category tree is grouped
into collapsible service branches.

Saving creates or updates a disabled draft and displays its server revision.
A conflict preserves local edits. **Загрузить серверную версию** explicitly
replaces them. Unsaved scenario/category changes are protected on router
navigation and browser unload. Return-to-catalog and category cancellation also
require an explicit discard decision. Copy/archive require a saved, unchanged
draft; archive has a separate confirmation.

**Создать категорию** edits title, service and parent. Each category has its own
inline advanced settings for slug, visibility, lifecycle and order. The parent
picker excludes that category and its descendants. The server still validates
cycles, scope, revisions and effective visibility. A non-empty category cannot
be archived. Auditor can inspect scenarios and run pure simulation; mutation
controls and editable inputs are unavailable, with server RBAC authoritative.

Existing links from Forms, Service Catalog and Policy Health preserve the
`template`, `service` and `offering` context. An unambiguous existing scenario
opens directly; an admin can prepare a new draft for an unambiguous offering.
Ambiguous/missing context stays in the catalog with an explicit notice. A
paginated/incomplete catalog also requires an explicit search/open choice;
absence from its first page never causes automatic creation of another draft.

P4 provides the catalog and wizard shell. P5 adds the block builder. Requester
sessions/ticket submission (P6/P7) and publication/diff/confirmation flow (P8)
are subsequent gates. No publication, enabling of requester scenarios,
production deployment, or Endpoint execution is performed by this shell.

## Block workbench

The second wizard step contains the block explorer and exactly one selected
block editor. Add from the palette inserts after selection and focuses its title.
Drag/drop and keyboard-accessible up/down buttons change list order without
rewriting explicit graph transitions. Copy assigns fresh block/field/fact keys
and remaps copied local dependencies. Removal shows incoming transitions and
requires an existing replacement for references/entry. An answer still referenced
elsewhere cannot be removed until its dependencies are edited. Local undo/redo
is bounded to 100 snapshots and resets on an externally replaced definition.

Question pages have single/group/section layout, a question list and exactly one
field editor. Labels, types, required/help/placeholder and option labels are
primary controls. Each field/option/block/instruction has its own inline advanced
settings: stable identifiers, typed conditions, length/numeric bounds, aliases,
fact key, dependency uses and compatible multiple process roles. Changing a
field type removes incompatible roles/bounds/options. File fields are explicitly
unavailable. Conditions use human-readable source/target pickers, never a JSON
editor. The server remains authoritative for graph and answer semantics.

Selected-step preview is collapsible and renders content as safe text; it does
not execute transitions. At 1440px and above it is the third workbench column;
at smaller widths it is a keyboard-contained drawer with Escape/close and focus
restoration. Tablet uses the explorer list above the full-width selected editor.
Canonical branch execution is the separate server testing/session flow.

## Components and verification

The page orchestrates `scenario-catalog`, `scenario-category-form`,
`scenario-purpose`, `scenario-wizard`, `use-scenario-editor`,
`use-scenario-context` and `use-scenario-dirty-guard`. Typed API calls are in
`features/request-template-studio/scenario-api.ts`; legacy API helpers remain
available for the subsequent publication integration.

Component checks cover catalog/loading/empty/error/retry/search/category,
creation, one visible step, CAS save/reload/conflict, auditor, legacy forms,
deep links and unsaved navigation/unload. `webapp/tests/guided-studio.spec.ts`
uses the project fixture server and mocked API contracts to verify the rendered
catalog/wizard at 1366×768 and 1920×1080, and the block builder at those widths,
1440×900 and tablet 820×1180. It checks preview column geometry, keyboard focus,
separator typing, typed membership, save/reload, fully visible primary actions, inline settings,
no horizontal document overflow, and console/network errors. Screenshots are
normal test artifacts under `webapp/test-results`; this is fixture browser
evidence, not staging runtime acceptance (P10).

## Requester sessions

Published, enabled scenarios add `guided_scenario_enabled` to their public
offering. Public category ancestors must also be published/public. Other
offerings retain the existing form UI at `/app/requester/new`.

Requester-only endpoints under `/api/web/requester/request-scenarios/sessions`
start/resume a session (POST), read its current step (GET `/{identifier}`),
and accept `answer`, `advance`, `back`, `finish` and `step-preview` POST commands.
The owner comes exclusively from verified `AuthContext`; another owner receives
404. Commands carry revision/current block and strict typed answers, never
actor/policy authority. Sessions expire after 24 hours, pin an immutable version,
and allow retired versions to continue unless revoked/disabled. Back clears
downstream answers/results. Repeating the latest identical command returns its
saved result; a changed stale command returns 409. Start resumes an active session
for the same owner/version. Ticket submit idempotency belongs to the existing
create ledger integration in P7.

`step-preview` uses the canonical runtime to reevaluate current-page conditions
without advancing or saving. The safe projection contains only the current step,
evaluated fields, visited Back targets and retained review answers. Picker options
come from existing Registry/catalog/identity sources. Device choices are restricted
to the owner's active bindings; user choices currently contain the verified self
profile. Selected identifiers are checked again server-side. No Endpoint dispatch
occurs. Session audit entries contain version/block/revision/state, never answers.

The requester component stores only an opaque session ID per login/offering in
sessionStorage. Late responses are canceled/ignored on owner/offering change;
resume preserves explicit unknown answers. Instructions are rendered as text;
resolution checks require explicit yes/no/unknown. Actual ticket creation and
policy preview are the following P7 gate, not a P6 success claim.
