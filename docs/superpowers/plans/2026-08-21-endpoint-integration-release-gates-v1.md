# Helpdesk Endpoint Integration Release Gates v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lock Helpdesk acceptance to the published Endpoint provider, audit rejected mapping attempts safely, prove the no-legacy vertical slice, rehearse migrations, and document an unexecuted canary.

**Architecture:** Helpdesk retains local ownership and accesses Endpoint only through `ExternalEndpointHttpAdapter`. The lock validator proves a clean immutable provider checkout before test-only import; tests and CI record exact SHAs. Mapping denials produce a best-effort safe `TicketAdminAudit`, while accepted work remains transactionally coupled to its success audit.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy/Alembic, PostgreSQL 16, pytest, GitHub Actions.

**Spec:** `C:/Users/admin-2/.codex/attachments/7f3ca8d4-acc5-4719-9dba-2a92bbf48505/pasted-text.txt`

**Implementation record:** Endpoint PR #7 was merged first at
`54fe6b975b7e8c4dff067d01c847be1da4eb7a81`; Helpdesk now locks that merge,
uses the mainline acceptance workflow, and has dedicated tests/runbook for the
remaining release gates. No production action is part of this plan.

## Global Constraints

- Base is immutable Helpdesk mainline merge `bf770a38523272ced04028b8bc7bde0a8987e0ef`; Endpoint lock must use the published Endpoint mainline merge `54fe6b975b7e8c4dff067d01c847be1da4eb7a81` and repository `BorisDruzak/endpoint_platform`.
- No production deployment, migration, DB/config/TLS/credential change, restart, test-agent modification, agent rollout, or endpoint-mode production enablement.
- No production Python import across repositories. Endpoint stays reachable only through `ExternalEndpointHttpAdapter`; no ToolService, Helpdesk WebSocket, DeviceOutbox, legacy fallback, or dual dispatch for this capability.
- Migration rehearsal uses disposable PostgreSQL only; no downgrade and no changes to migrations 135–137.

---

### Task 1: Immutable clean provider lock

**Files:**
- Modify: `integration/endpoint_contract.lock.json`, `scripts/validate_endpoint_contract_lock.py`
- Test: `server/tests/test_endpoint_contract_lock.py`, `server/tests/acceptance/test_endpoint_operations_v1_acceptance.py`

**Interfaces:**
- Produces: `EXPECTED_PROVIDER_REPOSITORY = "BorisDruzak/endpoint_platform"` and `validate(lock_path: Path, provider_root: Path) -> None` rejecting non-clean checkouts before imports.

- [ ] **Step 1: Write failing lock tests**

```python
with pytest.raises(ValueError, match="provider repository"):
    validate(lock_path=wrong_repository_lock, provider_root=provider_root)
dirty_file.write_text("dirty", encoding="utf-8")
with pytest.raises(ValueError, match="clean"):
    validate(lock_path=lock, provider_root=provider_root)
```

Cover valid lock, wrong repository/HEAD/digest, modified tracked file, staged file, untracked file, traversal, and CRLF checkout with matching Git blob.

- [ ] **Step 2: Run RED**

Run: `python -m pytest server/tests/test_endpoint_contract_lock.py -q --tb=short`

Expected: tests fail because repository identity and porcelain cleanliness are not enforced.

- [ ] **Step 3: Implement validation and lock update**

Require strict repository identity in `_load_lock`; after exact Git-root detection run `git status --porcelain --untracked-files=all`, fail on non-empty output, then compare HEAD and Git-blob SHA-256. Update only `provider_commit` to `b50bee41b1c19174cba1f3ee0d28610d4b1d11e2`; retain the digest if blob bytes match.

- [ ] **Step 4: Run GREEN with locked Endpoint worktree**

Run: `python -m pytest server/tests/test_endpoint_contract_lock.py -q --tb=short`

Run: `python scripts/validate_endpoint_contract_lock.py --lock integration/endpoint_contract.lock.json --provider-root "C:/Users/admin-2/Documents/endpoint/.worktrees/codex/operations-release-gates-v1"`

- [ ] **Step 5: Commit**

```powershell
git add integration/endpoint_contract.lock.json scripts/validate_endpoint_contract_lock.py server/tests/test_endpoint_contract_lock.py server/tests/acceptance/test_endpoint_operations_v1_acceptance.py
git commit -m "test(endpoint): require clean locked provider checkout"
```

### Task 2: Mainline acceptance CI

**Files:**
- Modify: `.github/workflows/endpoint-contract-acceptance.yml`

**Interfaces:**
- Produces: PR/push triggers for `codex/helpdesk-process-model`, `workflow_dispatch`, ref-scoped cancellation, a JUnit artifact, and `acceptance-summary.json` containing both SHAs and declared non-production test-client semantics.

- [ ] **Step 1: Write static workflow tests or assertions**

```python
assert "codex/helpdesk-process-model" in workflow
assert "workflow_dispatch:" in workflow
assert "endpoint-contract-${{ github.ref }}" in workflow
assert "--junitxml=artifacts/endpoint-contract-acceptance.xml" in workflow
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest server/tests/test_endpoint_contract_lock.py -q --tb=short`

Expected: workflow assertions fail until the mainline trigger/artifact contract exists.

- [ ] **Step 3: Implement workflow**

Retain a locked SHA checkout, run contract-lock, adapter, reconciler, device reference and no-legacy guards before the marked acceptance test; write the requested summary JSON with `provider_app="real"`, `gateway_wss="real"`, `agent_client="protocol_test_client"`, and `production_changed=false`; upload the XML and summary as `endpoint-contract-acceptance`.

- [ ] **Step 4: Validate source and focused tests**

Run the exact non-acceptance test list specified by the task, then inspect YAML parseability.

- [ ] **Step 5: Commit**

```powershell
git add .github/workflows/endpoint-contract-acceptance.yml
git commit -m "ci: run endpoint acceptance on helpdesk mainline"
```

### Task 3: Rejected mapping audit

**Files:**
- Modify: `server/app/services/endpoint_device_reference_service.py`, `server/diagnostics/handlers.py`
- Test: `server/tests/test_endpoint_device_reference_service.py`

**Interfaces:**
- Produces: best-effort `TicketAdminAudit(action="rejected", entity_type="endpoint_device_mapping")` with only current opaque ref and requested ref/replace/reason_code; no request body, credential, raw response, host/IP/MAC, context, WSS, exception, or environment value.

- [ ] **Step 1: Write failing denial-audit tests**

```python
assert response.status_code == 409
assert audit.action == "rejected"
assert audit.before_json == {"endpoint_device_ref": current_ref}
assert audit.after_json == {"requested_endpoint_device_ref": requested_ref, "replace": True, "reason_code": "ENDPOINT_DEVICE_RETIRED"}
assert "raw_body" not in json.dumps(audit.after_json)
```

Cover retired/mismatched previous/unavailable/invalid body denials, authorization, successful created/replaced audits, and immutable ticket/ref snapshot on denial.

- [ ] **Step 2: Run RED**

Run: `python -m pytest server/tests/test_endpoint_device_reference_service.py -q --tb=short`

Expected: absent rejected audit assertions fail.

- [ ] **Step 3: Implement minimal safe audit helper**

Derive only explicit reason codes and opaque references after safe validation. Preserve success audit transaction behavior. Catch/log rejected-audit persistence failure without changing the rejection response or ticket state.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest server/tests/test_endpoint_device_reference_service.py -q --tb=short`

- [ ] **Step 5: Commit**

```powershell
git add server/app/services/endpoint_device_reference_service.py server/diagnostics/handlers.py server/tests/test_endpoint_device_reference_service.py
git commit -m "fix(endpoint): audit rejected device mapping attempts"
```

### Task 4: Cross-repository vertical acceptance

**Files:**
- Modify: `server/tests/acceptance/test_endpoint_operations_v1_acceptance.py`

**Interfaces:**
- Consumes: real disposable Endpoint and Helpdesk PostgreSQL apps, Gateway WSS, service bearer, and protocol-compatible Gateway WSS test client.
- Produces: proof that the ticket status is unchanged, one remote operation and one evidence, terminal local lifecycle, safe payload, no persisted correlation, and no legacy dispatch.

- [ ] **Step 1: Write failing post-reconciliation assertions**

```python
assert ticket.status == original_ticket_status
assert evidence_count == 1
assert remote_operation_count == 1
assert gateway_payload_has_no_helpdesk_fields(command)
```

Install raising spies for `ToolService.run_tool`, `send_ws_command`, `enqueue_command_async`, and `DeviceOutboxRepo.enqueue_command`; assert matching DeviceOutbox rows are zero.

- [ ] **Step 2: Run RED with locked provider**

Run: `$env:ENDPOINT_PLATFORM_REPO = "C:/Users/admin-2/Documents/endpoint/.worktrees/codex/operations-release-gates-v1"; python -m pytest server/tests/acceptance/test_endpoint_operations_v1_acceptance.py -m cross_repo_acceptance -q --tb=short`

Expected: new assertions fail until the acceptance harness verifies them.

- [ ] **Step 3: Extend the real harness only**

Use no provider mock or installed-agent claim. Assert exactly one `DiagnosticEvidence(source_type="endpoint_platform", source_id=remote_operation_id)`, repeated reconciliation no-ops, one provider DB operation keyed by service client/idempotency key, lifecycle completion conditions, and correlation absence from model/Gateway payload.

- [ ] **Step 4: Run GREEN and no-provider skip**

Run: `python -m pytest server/tests/acceptance/test_endpoint_operations_v1_acceptance.py -q --tb=short`

Run the locked-provider command from Step 2 with `--junitxml=artifacts/endpoint-contract-acceptance.xml`.

- [ ] **Step 5: Commit**

```powershell
git add server/tests/acceptance/test_endpoint_operations_v1_acceptance.py
git commit -m "test(endpoint): strengthen no-legacy vertical acceptance"
```

### Task 5: Disposable migration rehearsal

**Files:**
- Create: `server/tests/migration/test_endpoint_integration_upgrade_rehearsal.py`

**Interfaces:**
- Produces: `artifacts/migration/endpoint-integration-rehearsal.json` after isolated PostgreSQL upgrade `134 -> 137` and fresh `head` verification.

- [ ] **Step 1: Write a failing migration-clone test**

```python
report = json.loads(Path("artifacts/migration/endpoint-integration-rehearsal.json").read_text())
assert report["starting_revision"] == "134"
assert report["ending_revision"] == "137"
assert report["destructive_changes_detected"] is False
assert report["success"] is True
```

- [ ] **Step 2: Run RED against disposable PostgreSQL**

Run: `python -m pytest server/tests/migration/test_endpoint_integration_upgrade_rehearsal.py -q --tb=short`

Expected: collection failure because the rehearsal test does not exist.

- [ ] **Step 3: Implement forward-only rehearsal**

Clone the project’s approved migration test pattern; seed representative revision-134 Ticket/Operation/DiagnosticSession/DiagnosticStep/(if present) DeviceOutbox data; compare primary keys/counts/safe business-column checksums after `upgrade 137`; introspect required nullable columns, tables, indexes, checks, FKs, and no Endpoint DB FK; run a separate clean `upgrade head`; never invoke downgrade.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest server/tests/migration/test_endpoint_integration_upgrade_rehearsal.py -q --tb=short`

- [ ] **Step 5: Commit**

```powershell
git add server/tests/migration/test_endpoint_integration_upgrade_rehearsal.py
git commit -m "test(db): rehearse endpoint integration migrations"
```

### Task 6: Canary runbook and gate record

**Files:**
- Create: `docs/runbooks/ENDPOINT_DIAGNOSTIC_CANARY.md`
- Modify: `docs/segmentation/HELPDESK_ENDPOINT_OPERATION_BOUNDARY.md`, `docs/superpowers/plans/2026-08-21-endpoint-integration-release-gates-v1.md`

**Interfaces:**
- Produces: a non-executable canary sequence with prerequisites, staged flags, exact observation criteria, rollback without DB downgrade, stop conditions, and explicit no-production-execution statement.

- [ ] **Step 1: Write a documentation-content assertion**

```python
text = Path("docs/runbooks/ENDPOINT_DIAGNOSTIC_CANARY.md").read_text(encoding="utf-8")
assert "ENDPOINT_DIAGNOSTIC_EXECUTION_MODE=endpoint" in text
assert "Do not perform database downgrade" in text
assert "duplicate evidence" in text.lower()
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest server/tests/test_endpoint_diagnostic_cutover_guards.py -q --tb=short`

Expected: documentation assertion fails until the runbook exists.

- [ ] **Step 3: Write the runbook**

Document exact prerequisites, stages 1–4, required safe verification and all stated rollback/stop conditions. Use “protocol-compatible Gateway WSS test client” only for CI terminology and state the document does not deploy or execute a canary.

- [ ] **Step 4: Run requested Helpdesk verification**

Run: `python scripts/verify_workspace.py`

Run: the exact focused endpoint test list from the task.

Run: `python -m compileall -q server scripts`

Run: `git diff --check`

- [ ] **Step 5: Commit docs**

```powershell
git add docs/runbooks/ENDPOINT_DIAGNOSTIC_CANARY.md docs/segmentation/HELPDESK_ENDPOINT_OPERATION_BOUNDARY.md docs/superpowers/plans/2026-08-21-endpoint-integration-release-gates-v1.md
git commit -m "docs: add endpoint diagnostic canary runbook"
git commit -m "docs: record endpoint integration release gates"
```
