#!/usr/bin/env python3
"""Create a live validation evidence folder with checklist markdown templates."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_ARTIFACTS_ROOT = Path(__file__).resolve().parent.parent / "artifacts"
SURFACES = (
    "admin",
    "requester",
    "support",
    "reports",
    "native_agent",
    "protocol_v3",
    "operation_lifecycle",
    "generic",
)


@dataclass(frozen=True)
class EvidencePack:
    run_id: str
    surface: str
    scenario_key: str | None
    release_run_id: str | None
    commit: str | None
    deployed_commit: str | None
    environment: str | None
    branch: str | None
    expected_schema_head: str | None
    actual_schema_head: str | None
    ticket: str | None
    device: str | None
    output_dir: Path


def _base_context(pack: EvidencePack) -> str:
    return (
        f"Run ID: {pack.run_id}\n"
        f"Surface: {pack.surface}\n"
        f"Ticket: {pack.ticket or 'n/a'}\n"
        f"Device: {pack.device or 'n/a'}\n"
        f"Created at: {datetime.now(timezone.utc).isoformat()}\n"
    )


def _browser_template(pack: EvidencePack) -> str:
    surface_notes = {
        "admin": "- Canonical route: `/admin` or the matching `/app/admin/*` page.\n- Capture URL, DOM-visible result, screenshot, and relevant network/console errors.\n",
        "requester": "- Canonical route: `/app/requester`, `/app/requester/devices`, or compatible `/app/device/*` route.\n- Capture authenticated web account, requester profile/device-link state, and server-resolved target device.\n",
        "support": "- Canonical route: `/app/support` or `/app/tickets`.\n- Capture support account, queue/detail URL, visible result, screenshot, and relevant network/console errors.\n",
        "reports": "- Canonical route: `/app/reports`.\n- Capture report URL, visible totals, screenshot or DOM output, and relevant network/console errors.\n",
        "native_agent": "- Browser is supporting evidence only when the native GUI flow opens a web cabinet.\n",
        "protocol_v3": "- Browser evidence may be not applicable; write the reason if skipped.\n",
        "operation_lifecycle": "- If the operation is visible to support/requester/admin, capture the relevant browser page.\n",
        "generic": "- Capture URL, visible result, screenshot or DOM output, and relevant network/console errors.\n",
    }
    return (
        "# Browser Evidence\n\n"
        f"{_base_context(pack)}\n"
        f"{surface_notes[pack.surface]}\n"
        "Checklist:\n"
        "- [ ] URL recorded\n"
        "- [ ] visible status/text/result recorded\n"
        "- [ ] screenshot or DOM-visible output attached\n"
        "- [ ] console errors checked\n"
        "- [ ] network errors checked\n\n"
        "Evidence:\n\n"
    )


def _api_template(pack: EvidencePack) -> str:
    return (
        "# API / Transport Evidence\n\n"
        f"{_base_context(pack)}\n"
        "Checklist:\n"
        "- [ ] endpoint or WS path recorded\n"
        "- [ ] method/status/close code recorded\n"
        "- [ ] request marker included\n"
        "- [ ] response payload redacted\n"
        "- [ ] auth/session evidence redacted\n\n"
        "Evidence:\n\n"
    )


def _server_db_template(pack: EvidencePack) -> str:
    surface_notes = {
        "requester": "- Verify account_session_id, account mode, requester person, and registry binding fields.\n",
        "support": "- Verify support actor, ticket queue/detail rows, related ticket events, and Observer trace ids.\n",
        "reports": "- Verify report totals against the seeded pack or scenario-specific DB rows.\n",
        "protocol_v3": "- Verify persisted event/outbox row or duplicate/no-op proof.\n",
        "operation_lifecycle": "- Verify operations, device_outbox, ticket_events, and target operation state.\n",
    }
    return (
        "# Server DB Evidence\n\n"
        f"{_base_context(pack)}\n"
        f"{surface_notes.get(pack.surface, '')}"
        "Checklist:\n"
        "- [ ] query target and database recorded\n"
        "- [ ] rows filtered by run marker\n"
        "- [ ] no raw secrets included\n"
        "- [ ] pre-fix contamination separated\n\n"
        "Evidence:\n\n"
    )


def _agent_sqlite_template(pack: EvidencePack) -> str:
    surface_notes = {
        "native_agent": "- Verify local GUI/account/session/update state in agent SQLite when relevant.\n",
        "protocol_v3": "- Verify agent outbox/seen command state.\n",
        "operation_lifecycle": "- Verify local operation/outbox state when an agent is involved.\n",
    }
    return (
        "# Agent SQLite Evidence\n\n"
        f"{_base_context(pack)}\n"
        f"{surface_notes.get(pack.surface, '')}"
        "Checklist:\n"
        "- [ ] local DB path recorded\n"
        "- [ ] rows filtered by run marker/device/ticket\n"
        "- [ ] token/session values redacted\n"
        "- [ ] not applicable reason written if no local agent is involved\n\n"
        "Evidence:\n\n"
    )


def _logs_template(pack: EvidencePack) -> str:
    return (
        "# Logs Evidence\n\n"
        f"{_base_context(pack)}\n"
        "Checklist:\n"
        "- [ ] server log checked\n"
        "- [ ] agent log checked if agent is involved\n"
        "- [ ] control/runtime log checked if deployment/runtime is involved\n"
        "- [ ] errors correlated by run marker/ticket/device\n"
        "- [ ] secrets redacted\n\n"
        "Evidence:\n\n"
    )


def _contamination_template(pack: EvidencePack) -> str:
    return (
        "# Contamination / Stop Conditions\n\n"
        f"{_base_context(pack)}\n"
        "Pre-fix contamination:\n"
        "- [ ] old ticket/operation/outbox rows identified or confirmed absent\n"
        "- [ ] old rows are not used as post-fix evidence\n\n"
        "Stop live run if:\n"
        "- [ ] new data-integrity bug appears\n"
        "- [ ] auth/account boundary is unclear\n"
        "- [ ] DB contamination invalidates evidence\n"
        "- [ ] tunnel/deploy/runtime environment is unstable\n"
        "- [ ] two consecutive probes disagree across API/DB/UI\n\n"
        "Notes:\n\n"
    )


def _observer_delta_template(pack: EvidencePack) -> str:
    return (
        "# Observer Integrity Delta\n\n"
        f"{_base_context(pack)}\n"
        "Before scenario:\n"
        "- [ ] baseline integrity scan run id recorded\n"
        "- [ ] existing active integrity events recorded\n"
        "- [ ] existing suppressed integrity events recorded\n\n"
        "After scenario:\n"
        "- [ ] scenario integrity scan run id recorded\n"
        "- [ ] related traces requested and attached\n"
        "- [ ] required trace/span coverage compared with DB outcome\n"
        "- [ ] no new active critical/high/error event linked to the run\n"
        "- [ ] no unexpected suppression\n"
        "- [ ] Observer writer/correlation health confirmed\n\n"
        "Evidence:\n\n"
    )


def _observer_canary_template(pack: EvidencePack) -> str:
    return (
        "# Observer Canary Report\n\n"
        f"{_base_context(pack)}\n"
        "Run:\n"
        "- [ ] `python scripts/run_observer_canary_suite.py --report-path <json> --markdown-report-path <md>` executed on the target stand\n"
        "- [ ] JSON report path recorded in `manifest.json` as `observer_canary.json_report_path`\n"
        "- [ ] Markdown report path recorded in `manifest.json` as `observer_canary.markdown_report_path`\n\n"
        "Coverage:\n"
        "- [ ] required root kinds recorded\n"
        "- [ ] observed root kinds recorded\n"
        "- [ ] missing root kinds is empty\n"
        "- [ ] failed scenarios is empty\n"
        "- [ ] coverage/status fields are `pass`\n\n"
        "Evidence:\n\n"
    )


TEMPLATES = {
    "browser.md": _browser_template,
    "api.md": _api_template,
    "server-db.md": _server_db_template,
    "agent-sqlite.md": _agent_sqlite_template,
    "logs.md": _logs_template,
    "contamination.md": _contamination_template,
    "observer-delta.md": _observer_delta_template,
    "observer-canary.md": _observer_canary_template,
}


def create_pack(
    *,
    run_id: str,
    surface: str,
    artifacts_root: Path = DEFAULT_ARTIFACTS_ROOT,
    scenario_key: str | None = None,
    release_run_id: str | None = None,
    commit: str | None = None,
    deployed_commit: str | None = None,
    environment: str | None = None,
    branch: str | None = None,
    expected_schema_head: str | None = None,
    actual_schema_head: str | None = None,
    ticket: str | None = None,
    device: str | None = None,
) -> EvidencePack:
    output_dir = artifacts_root / "live" / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    pack = EvidencePack(
        run_id=run_id,
        surface=surface,
        scenario_key=scenario_key,
        release_run_id=release_run_id,
        commit=commit,
        deployed_commit=deployed_commit,
        environment=environment,
        branch=branch,
        expected_schema_head=expected_schema_head,
        actual_schema_head=actual_schema_head,
        ticket=ticket,
        device=device,
        output_dir=output_dir,
    )
    for filename, template in TEMPLATES.items():
        (output_dir / filename).write_text(template(pack), encoding="utf-8")
    created_at = datetime.now(timezone.utc).isoformat()
    manifest = {
        "schema": "pc_client.live_evidence.v2",
        "run_id": run_id,
        "release_run_id": release_run_id,
        "scenario": scenario_key or surface,
        "scenario_key": scenario_key,
        "surface": surface,
        "status": "blocked",
        "commit": commit,
        "deployed_commit": deployed_commit,
        "environment": environment,
        "started_at": created_at,
        "finished_at": None,
        "entities": {
            "ticket_id": ticket,
            "device_id": device,
            "operation_id": None,
            "scenario_key": scenario_key,
            "trace_ids": [],
        },
        "preflight": {
            "branch": branch,
            "local_commit": commit,
            "deployed_commit": deployed_commit,
            "expected_schema_head": expected_schema_head,
            "actual_schema_head": actual_schema_head,
            "schema_status": "blocked",
            "service_health": "blocked",
            "checked_at": None,
        },
        "observer_delta": {
            "baseline_run_id": None,
            "scenario_run_id": run_id,
            "before": {
                "active_refs": [],
                "suppressed_refs": [],
                "scan_status": "blocked",
                "checked_at": None,
            },
            "after": {
                "active_refs": [],
                "suppressed_refs": [],
                "scan_status": "blocked",
                "checked_at": None,
            },
            "delta": {
                "new_active_critical_high_error_refs": [],
                "unexpected_suppression_refs": [],
            },
            "traces": {
                "required_trace_ids": [],
                "linked_trace_ids": [],
                "missing_required_trace_ids": [],
                "db_outcome": None,
                "trace_outcome": None,
                "consistency_status": "blocked",
            },
            "checker_status": "blocked",
            "writer_status": "blocked",
            "correlation_status": "blocked",
            "status": "blocked",
            "checked_at": None,
        },
        "observer_canary": {
            "json_report_path": None,
            "markdown_report_path": None,
            "required_root_kinds": [],
            "observed_root_kinds": [],
            "missing_root_kinds": [],
            "failed_scenarios": [],
            "coverage_status": "blocked",
            "status": "blocked",
            "checked_at": None,
        },
        "checks": [],
        "artifacts": [],
        "contamination": {"status": "not_reviewed"},
        "cleanup": {"status": "not_started"},
        "template_files": sorted(TEMPLATES),
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return pack


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--surface", choices=SURFACES, default="generic")
    parser.add_argument("--scenario-key")
    parser.add_argument("--release-run-id")
    parser.add_argument("--commit")
    parser.add_argument("--deployed-commit")
    parser.add_argument("--environment")
    parser.add_argument("--branch")
    parser.add_argument("--expected-schema-head")
    parser.add_argument("--actual-schema-head")
    parser.add_argument("--ticket")
    parser.add_argument("--device")
    parser.add_argument("--artifacts-root", type=Path, default=DEFAULT_ARTIFACTS_ROOT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    pack = create_pack(
        run_id=args.run_id,
        surface=args.surface,
        artifacts_root=args.artifacts_root,
        scenario_key=args.scenario_key,
        release_run_id=args.release_run_id,
        commit=args.commit,
        deployed_commit=args.deployed_commit,
        environment=args.environment,
        branch=args.branch,
        expected_schema_head=args.expected_schema_head,
        actual_schema_head=args.actual_schema_head,
        ticket=args.ticket,
        device=args.device,
    )
    print(f"live evidence pack: {pack.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
