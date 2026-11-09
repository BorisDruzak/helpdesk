# Studio: catalogue entrances first

Continuing the user's explicit instruction to execute the supplied UI changes. Existing React19/XYFlow12 application, no new dependency. Admin actor; primary job visually author a service route. Map remains a workbench; publication owns service settings and readiness. User chose direct implementation, without another design approval round.

## Global Constraints

- Staging only: osn-admin@192.168.101.118, /opt/helpdesk-staging. Production must not be touched.
- Preserve existing services, schema1–4, old published versions, catalogue entrances, route/SLA precedence, user drafts and unrelated dirty checkout/index. No migration or automatic rewriting on open.
- Remove the visual metadata Start node, not persisted runtime entry semantics. First visible map elements are catalogue entrances. Existing implicit primary entrances remain editable and reconnectable.
- Service title/description, section/category, catalogue availability and common rules belong to publication. New service creation opens those settings there, including before first save. Existing individual block editors remain usable.
- Entry creation is independent on the map via library/right click and connects visually to a step; no need for a hidden Start and no separate target-selection form.
- Creating a navigation/transition block must not show a redundant incoming transition card. Ordinary block transitions retain their cards, labels/conditions and existing wire semantics. Do not delete existing navigation blocks or transitions to change presentation.
- Keep essential map controls visible; group rare controls in “Ещё”. Retain features and keyboard access, remove duplicate preview/edit buttons from the main bar. Visible actions: undo/redo, whole-map view, focus entrances, library toggle; employee view/publication remain available.
- No forced browser clicks, horizontal body overflow, auth weakening, new dependencies or live ticket creation. Existing browser tabs with user edits must not be refreshed.

### Task 1: Implement the entry-first editor

Owner: one UI implementer. Own `webapp/src/features/request-template-studio/**`, and `webapp/src/pages/admin/request-template-studio-page*` only if needed for creation context; update affected existing component/native fixture tests under `webapp/tests/`. Root reserves new `webapp/tests/studio-entry-first.spec.ts` and documentation/release files.

Inspect current canvas/link model, workbench/pending entrances, Wizard, service creation and publication/Purpose components. Remove visible Start metadata node, its incoming entrance edges and obsolete toolbar/help references. Catalogue entrance cards have only their outgoing step connector; pending/new entries are usable roots. Preserve implicit and named entries, entry ids and runtime fields; existing metadata layout coordinates can remain harmlessly stored.

Move the former Start settings to an explicit “Настройки услуги” section/button on publication. New service creation opens it; returning to map does not force it open again for an existing service. Settings work before `detail` exists, autosave stays intact. Validation issue links reach the correct settings or actual block, never the removed node. Keep independent catalogue visibility and existing service rules/profile editing.

Fix navigation duplication by omitting the auxiliary incoming transition card when its destination is a real navigation/transition block, while keeping the actual source→target transition. An ordinary source→question/instruction still shows the editable transition card. Retain route/SLA calculations and outgoing branch behavior.

Simplify the toolbar per Global Constraints. Keep help and rare inspection/layout functions in “Ещё”, remove duplicate page-preview controls from main toolbar, focus entrances instead of removed Start. Update empty state to begin with a catalogue entrance.

Use RED/GREEN tests for a saved legacy definition unchanged on open, independent pending entry→existing/new step, no ghost Start nodes/edges, one navigation block without duplicate incoming card and ordinary transitions intact, new service settings before/after autosave, and issue navigation. Update only obsolete existing expectations. Run focused tests and TypeScript; write report and exact owned file list. No commit/index/remote operations and no subagents.

### Task 2: Verify, document and deploy

Root owns source baseline capture before Task1, task-only candidate over installed90fe32ecedda8a663d2d930866a4ada1d787ca56, new native browser regression at1366/1920, docs/CODEMAP/PLANS, strict read-only review and canonical guarded staging release with verified backup/restore. Validate installed source/assets, live browser, schema158 and original DB row hashes. Own disposable test service only if necessary; never mutate the user's service for acceptance. Record exact SHA, tests, residual limits, preserved data and screenshots.
