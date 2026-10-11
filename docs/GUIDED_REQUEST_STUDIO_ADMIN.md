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
for the same owner/version. Ticket submit uses the existing requester create
ledger and a server-derived key scoped to the owner/session.

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
resolution checks require explicit yes/no/unknown.

At the submit step, «Проверить обработку» calls `ticket-preview` with the revision.
Only a successful safe preview exposes «Создать обращение». `submit` accepts just
revision, `confirm: true` and optional selected computer (`device_id`) or
explicit no-computer context (`device_scope: none`); the server repeats the preview and canonical
profile/device/form checks. Priority, queue, SLA/OLA, approval and closure remain
owned by the existing policy services. No actor, queue, priority or raw answers
are accepted in this command. Retained visible answers, mapped facts, roles and
human summary are stored in the ticket's `request_scenario` snapshot alongside
the existing `request_form_data`, resolved form/template refs and catalog snapshot.
One transaction owns ticket initialization, create ledger completion, session
link/state and audit; failure rolls everything back. Concurrent/repeated submits
return the same linked ticket. The result links to the existing requester ticket
page. Canonical form constraints still apply: bind a compatible published form;
new scenario publication/readiness is the separate P8 gate.
The selected computer uses the existing ownership gate. Changing that selection
invalidates the UI preview and pending responses; disagreement with a retained
scenario device picker is rejected rather than silently replacing its target.

The publication step separates Policy Health from Scenario Readiness. Prepare
publication only after saving; examine the diff and blockers, then explicitly
confirm. A confirmation belongs to the authenticated administrator, saved
revision and complete canonical source snapshot. Changes to policy, form,
catalog, taxonomy, queue or SLA calendar require another preview. Tokens expire
and can be consumed only once. The publisher repeats readiness in the same
transaction that creates the immutable version and switches its active pointer.

Readiness enumerates finite answers through the canonical scenario evaluator,
including optional instruction acknowledgments and all resolution outcomes.
Processing is checked through the existing form and policy runtime. Above 512
variants, or when an unbounded fact can affect branching/processing, publication
is blocked with a specific explanation. Policy Health alone cannot clear this.

«История версий» loads published history on demand. Select a version and return
it to the saved draft; unsaved changes must be handled first. This replaces the
draft through the normal revision gate, while the active publication remains
effective. Review and publish the restored draft to create a new version.
The simulation step accepts typed test answers and shows actual server priority,
queue, deadline and approval requirement without creating a ticket or running
device operations. P8 acceptance and full staging signoff are tracked in the
implementation progress ledger.

For diagnostic blocks, the inspector shows consent as a configuration setting,
the fallback step and the unavailable pre-ticket execution boundary. In testing,
choose one of four failure outcomes: unavailable, consent not received, timeout,
or capability absent. Changing the outcome restarts the simulation. Results are
explicitly marked «Симуляция — реальная операция не выполнялась»; configured
consent is not a real authorization. Branch conditions use the same readable
outcome labels. Actual requester diagnostics continue to use the safe fallback.

The attachment field stays disabled until a reviewed secure pre-ticket storage
contract exists. Imported unsupported attachment fields block publication with
an explanation; the Studio does not stage or upload files.
