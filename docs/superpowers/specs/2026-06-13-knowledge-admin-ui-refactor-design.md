# Knowledge Admin UI Refactor Design Spec

Date: 2026-06-13
Status: design decision recorded, implementation pending

## What A Design Spec Is

A design spec is the project contract for a product change before implementation starts. It records what experience we are building, who it is for, which workflows matter, what is intentionally out of scope, which dependencies are required, and how completion will be verified.

For this refactor the spec prevents the Knowledge admin pages from drifting back into endpoint-driven CRUD screens. It gives implementation and review a stable target: each page must be judged against the intended admin workflow, not against whether every existing backend field is still visible on the first screen.

## Goal

Refactor the Knowledge admin suite into a scenario-first operations and authoring workspace while preserving existing backend contracts where practical.

Target routes:

- `/app/admin/knowledge`
- `/app/admin/knowledge/studio`
- `/app/admin/knowledge/graph`
- `/app/admin/knowledge/import`
- `/app/admin/knowledge/search-settings`
- `/app/admin/knowledge/ai`
- `/app/admin/knowledge/indexing`

The redesign must preserve the current `pc_client` visual language and Russian-first UI text, but move the pages away from long card stacks, raw identifiers, and mixed mental models.

## Required Frontend Dependencies

These dependency decisions are mandatory for the implementation plan:

- `TipTap` / `ProseMirror` for `/app/admin/knowledge/studio`.
- `React Flow` (`@xyflow/react`) for `/app/admin/knowledge/graph`.

Rationale:

- The Studio requirement is a real editor with inline selections, manual markup, AI markup, auto segmentation highlights, diff visualization, validation marks, and inspector-driven editing. Rebuilding this on a plain textarea would duplicate editor-engine behavior and make selection/highlight state fragile.
- The Graph requirement is a real graph editor with selectable nodes/edges, canvas-first layout, connection creation, movement, saved layout, and visible mutation effects. Rebuilding this as ad hoc SVG/list UI would repeat the current problem: the page displays graph data but is not a practical editor.

Implementation must isolate both libraries behind feature components so they do not leak across the whole webapp bundle more than necessary.

## Page Archetypes

### `/app/admin/knowledge` - Knowledge Operations Center

Actor: admin.
Primary job: identify knowledge platform health issues and jump to the correct workbench.

Structure:

- health/status summary;
- key degradations from Observer, quality, search and indexing;
- prioritized queues: review queue, gaps, low quality, indexing errors;
- quick transitions to Studio, Import, Search Settings, Indexing and Graph.

Not allowed on this page:

- raw Content Pack JSON editor;
- spaces/items/versions CRUD;
- rollout mega-forms;
- long publication forms;
- graph/import explanations as independent bottom cards.

Content packs must move to a guided installer or an advanced import/admin section with dry-run preview.

### `/app/admin/knowledge/studio` - Authoring Workbench

Actor: admin / knowledge manager.
Primary job: edit one article end to end in one editor.

Hard requirement: Studio has one primary editor for all authoring work. Metadata, segmentation, AI markup and publication controls support the editor; they do not replace it with separate large forms.

Required layout:

- left Article Explorer with search, status filters, visibility filters and "Новый черновик" drawer/modal;
- center TipTap/ProseMirror editor workspace with title/status row, toolbar, split preview/diff modes and inline highlights;
- right Inspector / Publication panel with selected version, owner/reviewer, checklist, validation errors, review actions and publish action.

Required inline visual states:

- manual selected text / manual segment;
- AI proposed markup;
- auto segmentation;
- changed text compared with selected/published version;
- validation warning;
- stale segment or remap warning.

Primary actions:

- create version;
- send to review;
- publish;
- request changes;
- archive/supersede.

Metadata belongs in an inspector tab or drawer. It must not dominate the editor.

### `/app/admin/knowledge/graph` - Graph Workbench

Actor: admin / knowledge manager.
Primary job: build and maintain graph relationships using a real graph canvas.

Hard requirement: Graph is an editor, not a read-only visualization.

Required layout:

- left node explorer with search and filters;
- center React Flow canvas as the dominant surface;
- right inspector for selected node/edge and AI proposals.

Required editor behavior:

- select node/edge;
- create node through drawer/modal;
- create edge through searchable source/target pickers or canvas connection;
- edit label/type/visibility in inspector;
- archive/delete with confirmation;
- drag/reposition and save layout;
- after create/update/delete/save, refetch or update state so the visible graph proves the change took effect.

Raw `stable_key` input is Advanced only; default flow must generate or suggest keys.

### `/app/admin/knowledge/import` - Import Wizard

Actor: admin / knowledge manager.
Primary job: create reviewable drafts from text, file, URL or git source.

Steps:

1. Source: paste text, upload file, URL or git; choose space, visibility and source name.
2. Preview: detected title, sections, warnings, policy and AI status.
3. Create draft: final title/slug check, auto-segmentation toggle, create, result link to Studio.

Remote import warnings and AI enrichment must be contextual inside the relevant step.

### `/app/admin/knowledge/search-settings` - Retrieval Settings

Actor: admin.
Primary job: configure retrieval behavior and test the effect.

Structure:

- top status for current mode, effective mode and AI status;
- sections/tabs: Basic search, Hybrid/vector, RAG/AI rewrite, Weights & limits, Test query;
- AI-dependent controls disabled or clearly gated when provider/policy is off;
- test panel on the right or bottom with preview result and safe diagnostics.

### `/app/admin/knowledge/ai` - AI Governance Settings

Actor: admin.
Primary job: configure AI providers, model profiles, policies and audit visibility safely.

Structure:

- Providers list + edit drawer;
- Model profiles list + edit drawer;
- Policies grouped by consequence;
- Audit table with filters.

Secret references must appear as secret/config references with helper text, not as ordinary user-facing raw text fields.

### `/app/admin/knowledge/indexing` - Indexing Operations

Actor: admin.
Primary job: inspect indexing health and run controlled reindex operations.

Structure:

- status cards;
- queue table with failed jobs first;
- reindex drawer with searchable item picker, optional version and dry-run/confirm when applicable;
- raw item id only in Advanced.

## Shared UI Primitives

Create or reuse:

- `PageFrame`
- `PageSection`
- `WorkbenchLayout`
- `EntityExplorer`
- `InspectorPanel`
- `SettingsSection`
- `WizardSteps`
- `AdvancedDisclosure`
- `DangerZone`
- `EmptyState`
- `StatusBanner`

These primitives must adapt to existing `Card`, `Button`, `Badge`, `PageHeading` and shell styles. Do not introduce a parallel design system.

## Component Boundaries

- Page components orchestrate only.
- Large feature blocks must be split into layout, explorer, toolbar, editor/canvas, inspector, form/preview and hooks files.
- Avoid 700-1000 line feature components.
- Query/mutation logic moves into hooks when JSX becomes hard to read.

## Acceptance Criteria

For every changed route:

- primary action is visible at 1366x768 without scrolling;
- no body horizontal scroll;
- no raw JSON textarea in normal workflow;
- no required manual raw id or `stable_key` outside Advanced mode;
- empty/loading/error states exist for the main blocks;
- each page has one clear primary workflow;
- destructive actions are separated and confirmed;
- AppShell and domain tabs still work;
- targeted tests pass.

Browser evidence must cover 1366x768 and 1920x1080 for all seven admin Knowledge routes.

## Verification Plan

Minimum local checks after implementation:

- `pnpm --dir webapp test -- src/features/knowledge/authoring-studio-page.test.tsx src/features/knowledge/graph-studio.test.tsx`
- targeted tests for import, search settings, AI settings and indexing pages touched by the refactor;
- `pnpm --dir webapp build`;
- `python scripts/verify_workspace.py`;
- browser validation through the project browser workflow for all target routes.

The Studio test set must prove selected item changes the editor/inspector and that markup/highlight states render. The Graph test set must prove create/update/delete/layout actions call the correct APIs and update/refetch visible graph state.
