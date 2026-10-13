# Guided Request Studio administration

The admin/auditor entry is `/app/admin/request-template-studio`. It opens the
visual map workbench immediately, with **Каталог / Блоки** in the left explorer.
The initial empty map is local and untouched; opening Studio does not create or
save a server draft. The canvas mounts after the workbench measures its actual
viewport so the initial start element fits inside the available height. Select an
offering to open its existing map or prepare a new map in the same workspace. Multiple maps require an explicit choice. A fresh
offering-scoped catalog lookup prevents creation based on incomplete search results.
Switching maps with unsaved edits requires explicit discard; autosave is paused
during that confirmation and while the next offering loads. Confirmed discard
clears the old local draft before loading, including the multiple-map chooser.
An auditor without an admin/support workspace opens Studio
directly; other workspace routes still require their own grants. Auditor testing
uses pure server simulation while editing and publication stay disabled.
Search and status filters run on the server. Searching for a request
type by its machine code or Russian name also finds scenarios and form-only
offerings; software installation is searchable through its saved Studio profile.
Selecting a category includes all its descendants before pagination. The catalog shows
the full human category path, description, active published version number and
last scenario/draft modification time. The compact explorer has a section/category
picker; server category filtering still includes descendants. Offering lookup
context is separate from visible filtered/paginated catalog entries.
The catalog has one card per offering, including offerings with only a canonical
form. Requester mode (**Для сотрудника: обычная форма** or **Для сотрудника:
пошаговый сценарий**) is separate from draft validation/publication status.
Archived/disabled scenarios never imply that requesters use them. Mode uses the
same published-version and public category-ancestor guard as requester runtime.
Separate requester availability also checks the offering and service publication,
public visibility and form binding; unavailable offerings are labeled explicitly.

Service headings are selectable root categories containing all their offerings,
including plain forms without a subcategory. Subcategory filters include all
descendants and retain disabled-scenario offerings; archive history supplies
location only when no current scenario exists. Unassigned offerings remain in
their main section. Search/status/category/pagination operate on offering cards.

`/app/admin/request-template-studio/services/:offeringCode` opens one offering,
with form/scenario actions and collapsed archive history.
`/app/admin/service-catalog/offerings/:offeringCode` opens settings for one
offering; configuration groups start collapsed. The old `/app/admin/service-catalog`
list redirects to the unified catalog, preserving link context. Navigation has
one catalog entry. Settings guard unsaved changes on navigation/unload; mutation
requests disable editing until their response updates the saved baseline. Existing
plain-form consumers keep their canonical forms.

**Новая карта** prepares another local map. The primary sections are
**Каталог**, **Карта сценария** and **Согласования**. Testing, publication and
version history open in the contextual inspector from header actions; the map
remains visible. The single system **Начало** holds title, description, category,
Service/Offering/RequestTemplate binding and inherited policies. It is metadata,
not a runtime step. Existing bindings cannot be replaced on a saved scenario.
Inline category creation preserves unsaved map values.

Drag the boundaries beside the explorer/inspector to change their widths and the
bottom boundary to change editor height. Focused separators also support arrow
keys, Home and End. Sizes are bounded to keep the canvas usable and stored as
browser preferences; they do not modify scenario geometry, draft revision or
published versions. **Сбросить размеры панелей** restores defaults. Tablet/mobile
layouts stack the inspector and do not expose desktop resize handles.

**Что ещё настроить** lists actionable authoring hints for service/start/result,
unfinished routes and disconnected steps. A hint selects its block or the needed
explorer tab and closes testing/publication panels so the relevant inspector is
visible. These hints do not certify publication readiness; **Проверить готовность**
opens the canonical full publication check. Legacy single entrances remain valid.

**Конструктор форм** and **Проверка политик** are temporarily hidden from sidebar
and domain navigation. Their permission-checked routes remain available for
ordinary forms/template creation and expert policy diagnostics. Existing offering
settings remain reachable through secondary **Настройки услуги** links in the
catalog explorer, with the normal unsaved-navigation guard.

**Создать услугу** opens `/app/admin/request-template-studio/services/new`, an
independent creation page. Choose a published/public section and an active,
published processing template. Saving creates only an offering draft and opens
its dedicated page; no scenario is created. Unsaved edits are protected, and save
remains visible when scrolling. The offering page requires explicit confirmation
before canonical standalone publication. Employees then use its ordinary form;
a scenario can be added later. Canonical publication validates forms, sections
and policies and retains the existing role/audit guards.

**Создать шаблон** next to the offering's template picker opens
`/app/admin/forms/new` in a separate tab. It explains ordinary questions and
processing rules, allows text/long-text/checkbox questions, and selects existing
published policy references. Explicit confirmation publishes one new template and
form schema through the canonical publish-from-form endpoint, with
`publish_policies=false`; it does not rewrite the shared form pack or existing
policies. Stable keys are generated automatically. Admin and forms-publication
permission checks, unsaved-navigation protection, loading/retry/error states and
mutation locking remain in effect. After publication, return to the offering tab
and choose **Обновить список шаблонов**; local service values remain intact.

The Начало inspector links to separate service creation instead of embedding
a second form. Existing offering drafts can still opt into source-bound atomic
publication with their scenario; selection sets the explicit publication intent.
Software installation retains its profile metadata and existing service_request
type. A published service exposes a requester deep link on its dedicated page.

Select a block to configure its questions/content, answer roles or catalog
entrances; select an arrow to edit its target, typed condition, priority and
fallback. Stable keys and technical limits stay in the selected element's local
advanced disclosure. Testing uses structured server issue paths with actions
that select the affected block/arrow/policy. Simulation never creates tickets,
approvals, notifications or Endpoint operations.

Saving creates or updates a disabled draft and displays its server revision.
A conflict preserves local edits. **Загрузить серверную версию** explicitly
replaces them. Unsaved scenario/category changes are protected on router
navigation and browser unload. Opening the embedded catalog retains the current
map; replacing it requires an explicit discard decision. Category cancellation
retains its existing discard guard. Copy/archive require a saved, unchanged
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

## Map workbench

The explorer contains seven palette types: Вопрос, Инструкция, Условие,
Проверка результата, Диагностика, Сводка and Результат. Result modes reuse
`finish`/`submit_ticket`; the other visual types reuse existing runtime kinds.
React Flow supplies draggable blocks, ports, selectable/reconnectable arrows,
zoom, pan and fit. `editor_layout.positions` persists geometry separately from
runtime transitions. Keyboard alternatives use block search, position inputs and
source/target pickers. Reconnecting updates one canonical transition. Inserting a
continuing block on an arrow retains its original condition on the first link.
Terminal/branching insertions require explicit route configuration. Automatic
cycles are rejected with an explanation.

Copy generates new block/field/fact keys and remaps local field dependencies.
Deletion displays incoming/outgoing links, entrance bindings and field uses;
entrances require an explicit draft reassignment/removal. Operations are atomic
and reversible through bounded 100-snapshot Undo/Redo (Ctrl+Z/Ctrl+Shift+Z/Ctrl+Y).
Autosave persists valid bound drafts with visible status/errors and optimistic
revision checks. Newer local edits survive an in-flight save; conflict pauses
saving and retains local state until explicit server reload. Save is separate
from publication.

Question blocks reuse single/group/section layout and one selected field editor,
including supported field types, required/unknown/options/help/validation,
visibility DSL and multiple compatible `process_mapping.roles`. Deleting used
fields shows dependencies. Conditions reuse the server typed DSL; there is no
client execution or SLA evaluator. Instructions render safe text.

Each ordinary block can own multiple stable catalog entrances with title,
description, category, search phrases, availability, target and reported symptom.
Markers and explorer entries select their block for editing. One version stores
all entrances and shared graph; specialized routes do not duplicate diagnostics.
Reported symptoms remain separate from answers and verified facts. Publication
checks every configured entrance and canonical required processing inputs.

**Согласования** manages existing published approval policies and explicit new
policy versions. Modes and trusted approver sources use the existing backend;
policy publication requires explicit confirmation. Actual approval happens only
after ticket creation. Result/Начало inspectors choose published policies or
inherit Service/Offering/template settings. Arbitrary requester manager IDs are
never accepted as authority.

## Components and verification

The page orchestrates `scenario-catalog`, `scenario-category-form`,
`scenario-purpose`, `scenario-wizard`, `use-scenario-editor`,
`use-scenario-context` and `use-scenario-dirty-guard`. Typed API calls are in
`features/request-template-studio/scenario-api.ts`; legacy API helpers remain
available for the subsequent publication integration.

Component checks cover catalog/loading/empty/error/retry/search/category,
creation, contextual map panels, CAS save/reload/conflict, auditor, legacy forms,
deep links and unsaved navigation/unload. `webapp/tests/guided-studio.spec.ts`
uses the project fixture server and mocked API contracts to verify the rendered
catalog/map at 1366×768 and 1920×1080, and the block builder at those widths,
1440×900 and tablet 820×1180. It checks preview column geometry, keyboard focus,
separator typing, typed membership, save/reload, fully visible primary actions, inline settings,
no horizontal document overflow, and console/network errors. Screenshots are
normal test artifacts under `webapp/test-results`; this is fixture browser
evidence, not staging runtime acceptance (P10).

P10 candidate quality analysis uses the existing `dev-scanner-quality.yml`
manual workflow on `codex/guided-request-studio-v2`. Its separate candidate job
admits only same-repository, open draft PR #41 targeting main, with the dispatched
SHA matching its head. Admission runs before checkout and again before analysis.
It shares the canonical Semgrep and frontend/backend coverage steps and pinned
scanner with the unchanged main job, but sets all three Sonar pull-request
parameters explicitly. Unsupported PR analysis or a failed Quality Gate is a
blocker; it must never fall back to analyzing the candidate as main. This workflow
does not install or publish the Studio. Exact-SHA CI and installed staging A–J
remain separate requirements.

## Requester sessions

Published, enabled scenarios add `guided_scenario_enabled` to their public
offering. Public category ancestors must also be published/public. Other
offerings retain the existing form UI at `/app/requester/new`.

Publication shows the target offering, scenario title/description and a
collapsible overview of every step using the existing requester preview controls.
The result prefers the immutable definition returned by publication and links to
`/app/requester/new?offering=<full_code>` in a separate browser tab; version
history remains available from the map header. The link chooses only an
offering present in the authenticated requester catalog. It grants no additional
access and still starts/resumes through the owner-scoped server runtime.
Normal requester drafts and drafts entered through individual offering links
have separate storage keys. Changing intent/offering in the same router remounts
the restoration lifecycle so answers cannot be written into another draft.

Requester-only endpoints under `/api/web/requester/request-scenarios/sessions`
start/resume a session (POST), read its current step (GET `/{identifier}`),
and accept `answer`, `advance`, `back`, `finish` and `step-preview` POST commands.
The owner comes exclusively from verified `AuthContext`; another owner receives
404. Commands carry revision/current block and strict typed answers, never
actor/policy authority. Sessions expire after 24 hours, pin an immutable version,
and allow retired versions to continue unless revoked/disabled. Back clears
downstream answers/results. Repeating the latest identical command returns its
saved result; a changed stale command returns 409. Start resumes an active session
for the same owner/version/entrance. Ticket submit uses the existing requester create
ledger and a server-derived key scoped to the owner/session.

`step-preview` uses the canonical runtime to reevaluate current-page conditions
without advancing or saving. The safe projection contains only the current step,
evaluated fields, visited Back targets and retained review answers. Picker options
come from existing Registry/catalog/identity sources. Device choices are restricted
to the owner's active bindings; user choices currently contain the verified self
profile. Selected identifiers are checked again server-side. No Endpoint dispatch
occurs. Session audit entries contain version/block/revision/state, never answers.

The requester component stores only an opaque session ID per login/offering/entrance in
sessionStorage. Late responses are canceled/ignored on owner/offering/entrance change;
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

The publication panel separates Policy Health from Scenario Readiness. Prepare
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
The simulation panel accepts typed test answers and shows actual server priority,
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

In «Обработка обращения», select published policies for priority, routing,
SLA/OLA, approval, notifications, closure and visibility. Each choice has its
own inline advanced disclosure for the reference. «Наследовать» preserves the
current service/template behavior. Only the scenario draft changes; the wizard
does not republish policies or modify the live offering. Unavailable selections
require a replacement before publication. Selected policies remain governed by
the existing Helpdesk lifecycle resolver.

Testing shows the traversed branch and normalized facts with human option labels,
the calculated priority, first response/resolution, internal support deadlines,
approval and closure requirements. The priority calculation reason is available
in a local disclosure. Notification groups describe policy rules; no messages
were sent and no provider delivery was checked by the simulator.

Create a category directly in «Категория и назначение» with «Создать категорию
здесь». The existing category form starts under the selected category and fixes
the service to the scenario service. Saving selects the new category while
preserving the scenario's unsaved title, description and graph. Close or save
this form before navigating between wizard stages, saving, copying or archiving
the scenario. Category settings keep their own local advanced disclosure.

For a long page choose «Разделы», select a question, then choose or create its
section by human title. Renaming a section updates all questions using that
section without changing their stable group keys. The requester and test run
render the same named sections; hidden fields are removed by the server first.
«Один вопрос» and «Группа вопросов» keep their existing layouts. Older groups
without a title use a readable fallback instead of exposing the machine key.

Selected-step preview renders the existing requester controls in a disabled
view; it does not evaluate conditions or execute the branch. «Предпросмотр всей
ветки» opens the server testing stage. Its «Не знаю» control sends explicit null
for fields allowing an unknown answer, matching the requester contract.

To let a requester reach support without completing a long instruction, open
that instruction's local advanced transitions and choose the result «Нужна
помощь поддержки» with a review block as its destination. Use an explicit
equality condition. The server shows the matching button only when this is the
selected transition; an earlier matching branch can make it unavailable. The
requester and simulator can take this branch without checking «Инструкция
выполнена». Answers already collected remain available for review; mandatory
ticket facts and processing checks still apply. Ordinary «Продолжить» retains
the configured acknowledgment requirement.

Publication blockers include an «Исправить» action. It opens the source block
of a graph error without changing the draft. For a broken transition, its local
advanced settings open and the first missing target receives keyboard focus.
Missing routing, SLA or closure opens the corresponding processing policy;
focus waits for the registry to load. A general issue opens its relevant wizard
stage rather than pretending to identify a more specific control. Save the
correction and prepare publication again; the server remains authoritative.

The routing check requires an existing active queue for every branch. A rule
pointing at a missing or disabled queue blocks publication. If the queue becomes
unavailable later, the employee's processing preview blocks ticket creation;
an earlier successful preview does not grant permission to submit.

Requester step actions stay visible at the bottom of the viewport on long
question pages. The new-request shell clips horizontal overflow without creating
an intermediate scroll container, so the action bar follows the document scroll.
Questions remain in normal document flow and keyboard order; busy steps disable
both their fields and actions.

Dynamic group approvers remain unavailable in the current backend: group sources
produce a literal group marker, while decisions require exact authenticated actor
identity and do not expand group membership. Existing configurations are preserved.
Explicit approvers are selected by human names from active support/admin accounts
in the existing Registry; requester-supplied IDs do not define managerial authority.
