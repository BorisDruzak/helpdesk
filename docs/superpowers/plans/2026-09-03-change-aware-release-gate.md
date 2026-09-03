# Change-Aware Release Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reuse a full CI artifact for a tree-identical GitHub merge candidate and document path-aware development validation.

**Architecture:** `scripts.ci_artifacts` remains the single artifact validator. It gains a narrowly scoped merge-parent/tree equivalence resolver; `release_candidate_preflight` reports provenance. Existing release scripts retain their validator calls.

**Tech Stack:** Python 3 standard library, Git CLI, pytest, Markdown.

**Spec:** `docs/superpowers/specs/2026-09-03-change-aware-release-gate-design.md`

## Global Constraints

- Never accept affected or selected CI as a full release artifact.
- Accept reuse only for a two-parent merge whose PR-head parent has an identical Git tree.
- Keep staging release scripts and live release summary requirements intact.
- Do not change production configuration or store credentials.

---

### Task 1: Resolve equivalent full CI artifacts

**Files:**
- Modify: `scripts/ci_artifacts.py`
- Modify: `scripts/test_ci_artifacts.py`

**Interfaces:**
- Add `resolve_green_ci_artifact(workspace: Path, commit: str) -> tuple[Path, str, bool]`.
- Keep `require_green_ci_artifact(workspace, commit) -> Path` compatible.

- [ ] **Step 1: Write failing tests**

Add a passing source summary and mock Git output. Assert a two-parent merge uses
its second parent only when both `^{tree}` values match; assert a tree mismatch
raises `SystemExit` with the existing exact-commit guidance.

- [ ] **Step 2: Prove red state**

Run: `python -m pytest scripts/test_ci_artifacts.py -k tree_identical -q`

Expected: the new resolver is absent or rejects the tree-identical merge.

- [ ] **Step 3: Implement the resolver**

Make the exact summary path the first choice. Only if absent, resolve the two
parents with `git show -s --format=%P`, require exactly two, compare
`git rev-parse <sha>^{tree}`, then validate the second parent's full green
summary with the existing status and shared-DB guards.

- [ ] **Step 4: Verify the validator**

Run: `python -m pytest scripts/test_ci_artifacts.py -q`

Expected: PASS.

### Task 2: Report provenance in preflight

**Files:**
- Modify: `scripts/release_candidate_preflight.py`
- Modify: `scripts/test_release_candidate_preflight.py`

**Interfaces:**
- Preflight consumes the new resolver and emits
  `[release-preflight] reused_ci_artifact_commit=<sha>` only for a reused artifact.

- [ ] **Step 1: Write the failing preflight test**

Mock the resolver to return `(workspace / "summary.json", "source123", True)`
and assert captured stdout includes `reused_ci_artifact_commit=source123`.

- [ ] **Step 2: Prove red state**

Run: `python -m pytest scripts/test_release_candidate_preflight.py -k reused -q`

Expected: FAIL because preflight still calls the exact-only validator.

- [ ] **Step 3: Implement reporting**

Replace the direct validator call with the resolver, keep the existing green
artifact line, and print the source commit only when `reused` is true.

- [ ] **Step 4: Verify preflight tests**

Run: `python -m pytest scripts/test_release_candidate_preflight.py -q`

Expected: PASS.

### Task 3: Document path-aware verification

**Files:**
- Modify: `docs/LOCAL_WORKFLOW.md`
- Modify: `docs/TESTING_RULES.md`
- Modify: `docs/CODEX_WORKFLOW.md`

- [ ] **Step 1: Update policy text**

Document `--changed-path` and selected layers as the normal iteration route;
state that full CI is explicit/frozen-new-tree evidence and that only a
tree-identical GitHub merge may reuse its PR-head full artifact.

- [ ] **Step 2: Check docs**

Run: `python scripts/docs_inventory.py --check-links`

Expected: PASS.

### Task 4: Review and commit

**Files:**
- Modify: all Task 1–3 files only

- [ ] **Step 1: Run focused checks**

Run: `python -m pytest scripts/test_ci_artifacts.py scripts/test_release_candidate_preflight.py scripts/test_run_ci_suite.py -q`

Expected: PASS.

- [ ] **Step 2: Run workspace and diff checks**

Run: `python scripts/verify_workspace.py; git diff --check`

Expected: both commands exit 0.

- [ ] **Step 3: Commit the atomic change**

Run: `git add <Task 1-3 files>; git commit -m "feat(release): reuse tree-identical CI artifacts"`

Expected: clean worktree with a single conventional commit.
