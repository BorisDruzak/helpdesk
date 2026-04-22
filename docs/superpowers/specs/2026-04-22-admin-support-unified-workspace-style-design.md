# Admin/Support Unified Workspace Style Design

**Date:** 2026-04-22

**Status:** Approved for implementation

## Goal

Establish one visual system for the internal `webapp` so that `/app/support` and `/app/admin` feel like one product instead of two adjacent workspaces.

The old legacy pages remain reference material for:

- information architecture;
- menu and workflow coverage;
- API and feature parity expectations.

They are **not** a visual reference for this redesign wave.

## Visual Direction

### Visual Thesis

Municipal service-desk software with a calm white work canvas, a branded green navigation rail, restrained blue action accents, and dense but readable operational hierarchy.

### Content Plan

For both workspaces:

1. permanent branded rail;
2. clear page header with utility summary;
3. primary working surface in the center;
4. secondary context and inspectors on the side;
5. supporting admin/support tools below or alongside the active workspace without changing the shell language.

### Interaction Thesis

- Selected rows, tabs, and actions should feel precise and immediate, not glossy.
- Motion should be limited to light hover lift, focus rings, and small section transitions.
- The layout should privilege scanning and action over decorative card grids.

## Design Rules

### 1. Support and Admin Share One Shell

The following must be visually identical across both workspaces:

- left rail structure and brand treatment;
- typography scale;
- surface styling;
- control styling;
- status chips;
- table/list row treatment;
- inspector cards.

Support may be more conversation-centric and admin may be more inventory-centric, but both must read as the same application.

### 2. Functions Come From Current Product Sources

Visual reference comes from the attached images only.

Functional reference comes from:

- current typed `/api/web/*` contracts;
- current React `webapp` behavior;
- legacy `server/support.*` and `server/admin.*` information architecture where needed for parity.

The redesign must not invent new visual behavior by copying the old legacy look.

### 3. Workspace Layout Model

#### Support

Support should behave like an operator workspace:

- queue and filters as a dedicated navigation/worklist region;
- active ticket as the primary conversation surface;
- right-side inspector for ticket, requester, observer, and device context;
- composer and tool actions integrated into the active ticket workspace.

#### Admin

Admin should use the same shell language:

- device inventory as the primary navigation/worklist region;
- selected device as the main workspace;
- side context for summary and rollout/device facts;
- modules, forms, updates, and observer panels styled as the same product system.

### 4. Styling Constraints

- No reuse of the old beige/glassmorphism language from the first React cut.
- No reuse of the old legacy visual language.
- Avoid dashboard-card mosaics as the main impression.
- Prefer layout, spacing, dividers, rows, and inspector blocks over stacked decorative cards.
- Keep one dominant accent family: green brand + blue action.

## Implementation Consequences

This wave should start by introducing explicit design tokens and shared workspace primitives inside `webapp`, then move page-by-page:

1. shared shell and theme tokens;
2. support workspace redesign;
3. admin workspace alignment to the same system;
4. follow-up polish for modules/forms/observer/update panels.

## Acceptance Criteria

The redesign is successful when:

- `/app/support` and `/app/admin` clearly belong to one visual system;
- the workspace shell matches the attached reference mood and structure;
- legacy pages are used only as functional reference points;
- existing typed API workflows still work without regression;
- support remains a full operator workspace, not a cosmetic skin over the old layout;
- admin keeps its current React functionality while inheriting the same shell language.
