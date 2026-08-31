# Product Webapp Staging Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** deliver the built React webapp inside the immutable Helpdesk release so staging can serve `/app/admin` rather than relying on the legacy shell.

**Architecture:** `scripts/deploy_helpdesk_release.py` creates the immutable source archive consumed by isolated staging. It will also build `webapp/dist`, validate index/assets, and append the output under the same release prefix. Existing static-page cutover policy activates `/app/admin` only when the released bundle and environment flags are present.

**Tech Stack:** Python 3.12, `tarfile`, pnpm/Vite/TypeScript, aiohttp static assets, pytest, immutable Helpdesk staging releases.

**Spec:** `docs/WEBAPP_CUTOVER_CHECKLIST.md`

## Global Constraints

- Use exact Helpdesk merge `2d35595407ffde6f476f97465f6f1ab70dfc9eec` as the implementation baseline.
- Staging only (`osn-admin@192.168.101.118`); never touch production.
- Preserve `httpOnly; Secure` sessions and the explicit `?legacy=1` rollback escape.
- Do not commit generated `webapp/dist`, credentials, or release archives.
- Deploy only through `scripts/deploy_helpdesk_release.py`; never patch `/opt/helpdesk-staging/current` manually.

---

### Task 1: Package the product webapp in an immutable release

**Files:**

- Modify: `scripts/deploy_helpdesk_release.py`
- Test: `scripts/test_deploy_helpdesk_release.py`

**Interfaces:**

- Consumes: a source tar created with `git archive`, plus the output directory created by `scripts/build_webapp_bundle.py`.
- Produces: `append_webapp_bundle_to_release_archive(release_archive: Path, bundle_dir: Path, release_prefix: str) -> None`, which adds only `webapp/dist` under the release prefix and rejects an incomplete bundle.

- [x] **Step 1: Write the failing test**

```python
def test_append_webapp_bundle_to_release_archive_places_dist_under_release_prefix(tmp_path):
    release_archive = tmp_path / "helpdesk.tar"
    bundle_dir = tmp_path / "webapp-dist"
    (bundle_dir / "assets").mkdir(parents=True)
    (bundle_dir / "index.html").write_text("<div id='root'></div>", encoding="utf-8")
    (bundle_dir / "assets" / "app.js").write_text("export {}", encoding="utf-8")

    append_webapp_bundle_to_release_archive(release_archive, bundle_dir, "helpdesk-abc123")

    with tarfile.open(release_archive) as archive:
        assert "helpdesk-abc123/webapp/dist/index.html" in archive.getnames()
        assert "helpdesk-abc123/webapp/dist/assets/app.js" in archive.getnames()
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest scripts/test_deploy_helpdesk_release.py::test_append_webapp_bundle_to_release_archive_places_dist_under_release_prefix -q`

Expected: FAIL because the archive-packaging helper does not exist.

- [x] **Step 3: Write the minimal implementation**

```python
def append_webapp_bundle_to_release_archive(release_archive: Path, bundle_dir: Path, release_prefix: str) -> None:
    index_path = bundle_dir / "index.html"
    assets_dir = bundle_dir / "assets"
    if not index_path.is_file() or not assets_dir.is_dir() or not any(assets_dir.rglob("*")):
        raise RuntimeError("webapp bundle is incomplete")
    with tarfile.open(release_archive, "a") as archive:
        archive.add(bundle_dir, arcname=f"{release_prefix}/webapp/dist")
```

Call the existing bundle builder from `main()` after `git archive` and before SCP so the archive content comes from the same local workspace and release prefix.

- [x] **Step 4: Run targeted tests to verify it passes**

Run: `python -m pytest scripts/test_deploy_helpdesk_release.py -q`

Expected: PASS, including the existing immutable-release tests.

### Task 2: Verify and document the product cutover

**Files:**

- Modify: `docs/LOCAL_WORKFLOW.md`
- Modify: `PLANS.md`
- Test: `server/tests/test_static_pages_handlers.py`

**Interfaces:**

- Consumes: the release archive from Task 1 and existing `build_webapp_cutover_state()` behavior.
- Produces: `/admin -> /app/admin` only after a released bundle and explicit cutover configuration; `?legacy=1` remains rollback.

- [x] **Step 1: Keep the Task 1 archive-layout assertion as the release regression**

No source-string route assertion is needed: the existing static-page tests exercise the real cutover contract.

- [x] **Step 2: Run static cutover tests**

Run: `python -m pytest server/tests/test_static_pages_handlers.py -q`

Expected: PASS; a present bundle plus enabled flags redirects `/admin` to `/app/admin` and preserves `legacy=1`.

- [x] **Step 3: Update the release workflow documentation**

Document that `deploy_helpdesk_release.py` builds and packages the webapp bundle into the immutable release; retain explicit cutover flags and rollback policy.

- [ ] **Step 4: Run release/browser checks**

Run `python scripts/verify_workspace.py`, `python scripts/check_webapp_cutover.py --json`, and `pnpm --dir webapp run build`. After the reviewed staging release, check `https://helpdesk-staging.sosnadmin.local/app/admin` in a real browser for a meaningful React screen, no console errors, and one navigation interaction.

## Self-Review

- Spec coverage: Task 1 delivers the missing release bundle; Task 2 verifies flag-gated product routing and preserves rollback.
- Placeholder scan: no TODO/TBD steps or implicit tests remain.
- Type consistency: Task 1 defines the archive helper and Task 2 consumes its archive layout contract.

## Execution Handoff

The user explicitly requested inline execution. Execute Tasks 1–2 in this session with TDD, then create a draft PR. Deployment remains subject to the reviewed staging procedure and available staging-operator privileges.
