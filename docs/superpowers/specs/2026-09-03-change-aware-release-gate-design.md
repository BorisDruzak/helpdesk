# Change-Aware Release Gate Design

## Goal

Avoid duplicate full CI runs for a GitHub merge commit whose source tree is
identical to an already green full-gate candidate, while making normal
development checks explicitly path-aware and keeping staging release safety.

## Decision

Full CI remains a release-candidate action, not a per-commit or per-push
requirement. A full-gate deploy accepts either an exact green full-gate
artifact or an equivalent artifact only when all of the following are true:

1. The candidate is a two-parent merge commit.
2. The artifact commit is the second parent (the merged PR head).
3. Both commits resolve to the same Git tree.
4. The source artifact is green, complete, parallel-enabled, and has no
   shared-test-DB fallback.

The preflight output must identify the accepted source commit and tree. Any
different tree, non-merge candidate, incomplete artifact, or failed artifact
continues to require a new full CI run.

## Development Verification Policy

During implementation and PR iteration, use `run_ci_suite.py --changed-path`
or selected `--layer` checks for the changed surface. `verify_workspace.py`
is a release/deploy preflight, not a routine prerequisite for every change.
Full CI is run only for a frozen new release tree, when explicitly requested,
or when the risk policy calls out migrations, authentication/authorization,
Protocol V3, or cross-repository contract changes.

## Safety Boundaries

Quick/targeted checks never become a full release artifact. The existing
staging release scripts and live-release-summary checks stay in place. No
production target, credentials, or deployment configuration is changed.

## Verification

Unit tests cover acceptance of a tree-identical merge artifact and rejection
of non-parent and tree-different artifacts. Existing exact-artifact and
targeted-suite tests remain. Documentation describes the new decision rule and
the path-aware workflow.
