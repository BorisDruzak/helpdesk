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

P4 provides the catalog and wizard shell. The block builder (P5), requester
sessions/ticket submission (P6/P7), and publication/diff/confirmation flow (P8)
are subsequent gates. No publication, enabling of requester scenarios,
production deployment, or Endpoint execution is performed by this shell.

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
catalog/wizard at 1366×768 and 1920×1080, visible primary actions, inline settings,
no horizontal document overflow, and console/network errors. Screenshots are
normal test artifacts under `webapp/test-results`; this is fixture browser
evidence, not staging runtime acceptance (P10).
