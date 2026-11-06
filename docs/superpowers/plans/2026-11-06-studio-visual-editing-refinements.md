# Studio visual editing refinements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. This refines the previously approved inline-map design in response to the user's five concrete browser comments.

**Goal:** Make block size, question pages/order and named navigation buttons directly editable visually.
**Architecture:** Keep the existing React/ReactFlow Studio and unchanged scenario API/runtime. Question authoring is the employee page with inline editable content and subordinate technical controls. Persist editor sizes as local UI preferences, never as business-definition fields.
**Tech Stack:** React19.2.5, @xyflow/react12.11, existing Tiptap3.26, TypeScript6; no added dependencies.
**Spec:** `docs/superpowers/specs/2026-11-06-studio-inline-map-editor-design.md` and the current user's browser comments.

## Global Constraints

- Preserve schema1/2/3/4 behavior, IDs, conditions, references, stable action keys and existing published services; no automatic legacy upgrade or route-mode conversion.
- Preserve unrelated dirty checkout/index and both user browser tabs/unsaved drafts. Production is out of scope.
- No additional edit/preview activation button is required to edit a question visually.
- No horizontal body or editor scrolling; controls wrap. Resizing must work at canvas zoom and remain bounded to the available viewport.
- Use only current dependencies. Read library docs through Context7 before relying on new APIs.

## Review Focus

- Reordering and copying preserve field keys, dependencies and effective grouping; deleting referenced fields is blocked.
- Resizing must not move a node or create connections and must accommodate content on1366×768 and1920×1080.
- Automatic routes retain conditions/priority and are not silently transformed into employee buttons.
- Multiple named buttons retain their action keys and do not become recorded question answers.
- Opening legacy content must not serialize new fields or dirty it.

### Task 1: Visual question pages, adjustable editors and map buttons

- [ ] Snapshot current task files and read nearest instructions/current source.
- [ ] RED regressions for the three user-facing behaviors; then implement.
- [ ] Replace question chips/order configuration with all question cards rendered together as an employee-style page. Labels, help and choice labels editable directly. Reuse requester styles/rendering where possible. Technical settings remain collapsible. Provide1–100 question count/addition and drag-handle reorder with keyboard equivalent. Keep grouping and field-use guards.
- [ ] Make inline block editor, edge popover and full editor user-resizable in both dimensions with sensible compact defaults, minimums, viewport maximums and local per-scenario sizing preferences. Remove fixed height caps and clipping conflicts. Supply accessible resize handle/keyboard controls and prevent canvas gestures while resizing.
- [ ] Replace navigation mode dropdown as the primary UI with visual automatic-vs-button controls and editable employee-style button cards. Show named outgoing buttons on nodes/edges. Rename each v4 button directly from its connection; retain stable keys/conditions. Provide an explicit mode change for eligible v4 sources and preserve legacy automatic routes. Avoid ambiguous duplicate defaults when constructing multiple buttons; enforce existing limit10.
- [ ] Update focused tests/docs and run related component suites and build. Write implementation report and exact changed file list under `tmp/studio-visual-refinements-20261106/`.
- [ ] Independent task review, bounded fixes,1366/1920 real browser checks, frozen staging candidate and installed acceptance through existing project release workflow if checks pass.

## Current State

Analysis confirmed fixed560px/height caps, selected-question settings form and generic automatic-route labels. GitNexus tool unavailable. Implementation pending. Parent owns browser draft backups, release packaging and staging operations.
