#!/usr/bin/env python3
"""Dry-run inventory for historical helpdesk mojibake and placeholder data.

The script is intentionally read-only.  It inventories data quality issues and
separates safe data cleanup candidates from records that need manual review.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

WORKSPACE = Path(__file__).resolve().parent.parent
SERVER_ROOT = WORKSPACE / "server"
DEFAULT_OUTPUT_DIR = WORKSPACE / "artifacts" / "diagnostics"

INTERESTING_JSON_KEYS = {
    "description",
    "display_name",
    "full_name",
    "help_text",
    "label",
    "name",
    "placeholder",
    "title",
}

MOJIBAKE_MARKERS = (
    "Рџ",
    "Рќ",
    "Рµ",
    "СЂ",
    "Рѕ",
    "Рґ",
    "Р»",
    "С‹",
    "СЊ",
    "С‚",
    "Р°",
    "Рё",
    "РЅ",
    "СЃ",
    "Рє",
    "РІ",
    "Р±",
    "Р·",
    "Р№",
    "вЂ",
    "В«",
    "В»",
    "Ð",
    "Ñ",
    "Â",
)
PLACEHOLDER_RE = re.compile(r"(?:^|\s)\?{3,}(?:\s|$)|\?{4,}")
TOKEN_RE = re.compile(r"(?i)\b(?:bearer\s+|token\s+|public:)[a-z0-9._=-]{16,}\b")


@dataclass(frozen=True)
class ScanRow:
    table: str
    row_key: str
    fields: Mapping[str, Any]


@dataclass(frozen=True)
class DataFinding:
    table: str
    row_key: str
    field_path: str
    issue_codes: list[str]
    sample: str
    cleanup_strategy: str


def detect_text_issues(value: str | None) -> list[str]:
    if not value:
        return []

    issues: list[str] = []
    if any(marker in value for marker in MOJIBAKE_MARKERS):
        issues.append("mojibake")
    if PLACEHOLDER_RE.search(value.strip()):
        issues.append("placeholder")
    if TOKEN_RE.search(value):
        issues.append("sensitive_token_like")
    return issues


def redact_sensitive_text(value: str) -> str:
    return TOKEN_RE.sub("[REDACTED_TOKEN]", value)


def sample_text(value: Any, *, max_len: int = 180) -> str:
    text = redact_sensitive_text(str(value or "").replace("\r", " ").replace("\n", " ").strip())
    if len(text) <= max_len:
        return text
    return f"{text[: max_len - 3]}..."


def cleanup_strategy(issue_codes: Iterable[str]) -> str:
    issue_set = set(issue_codes)
    if "sensitive_token_like" in issue_set:
        return "security_review_required"
    if issue_set == {"placeholder"}:
        return "data_only_cleanup_candidate"
    return "manual_review_required"


def collect_findings(rows: Iterable[ScanRow]) -> list[DataFinding]:
    findings: list[DataFinding] = []
    for row in rows:
        for field_path, raw_value in row.fields.items():
            if raw_value is None:
                continue
            if not isinstance(raw_value, str):
                raw_value = str(raw_value)
            issues = detect_text_issues(raw_value)
            if not issues:
                continue
            findings.append(
                DataFinding(
                    table=row.table,
                    row_key=row.row_key,
                    field_path=field_path,
                    issue_codes=issues,
                    sample=sample_text(raw_value),
                    cleanup_strategy=cleanup_strategy(issues),
                )
            )
    return findings


def extract_json_text_fields(
    value: Any,
    *,
    root_path: str,
    interesting_keys: set[str] = INTERESTING_JSON_KEYS,
) -> dict[str, str]:
    fields: dict[str, str] = {}

    def walk(current: Any, path: str) -> None:
        if isinstance(current, dict):
            for key, nested in current.items():
                child_path = f"{path}.{key}" if path else str(key)
                if isinstance(nested, str) and str(key) in interesting_keys:
                    fields[child_path] = nested
                elif isinstance(nested, (dict, list)):
                    walk(nested, child_path)
        elif isinstance(current, list):
            for index, nested in enumerate(current):
                walk(nested, f"{path}[{index}]")

    walk(value, root_path)
    return fields


def compute_mode(*, apply: bool) -> str:
    return "apply_requested_but_not_implemented" if apply else "dry_run"


def build_report(
    findings: list[DataFinding],
    *,
    scanned_rows: Mapping[str, int],
    dry_run: bool,
) -> dict[str, Any]:
    strategy_counts: dict[str, int] = {}
    issue_counts: dict[str, int] = {}
    table_counts: dict[str, int] = {}
    for finding in findings:
        strategy_counts[finding.cleanup_strategy] = strategy_counts.get(finding.cleanup_strategy, 0) + 1
        table_counts[finding.table] = table_counts.get(finding.table, 0) + 1
        for code in finding.issue_codes:
            issue_counts[code] = issue_counts.get(code, 0) + 1

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "dry_run" if dry_run else "apply_requested_but_not_implemented",
        "scope": [
            "tickets.title",
            "tickets.description",
            "tickets.requester_id",
            "tickets.custom_fields.user_display_name",
            "tickets.custom_fields.requester_profile.*",
            "registry_people.display_name",
            "registry_people.full_name",
            "modules.manifest_json/manifest_summary descriptive fields",
            "device_toolset_snapshots.toolset_json descriptive fields",
        ],
        "decisions": [
            "This inventory is read-only by default and does not mutate production data.",
            "Placeholder-only fields are data-only cleanup candidates.",
            "Mojibake and mixed issues require manual review before changing historical records.",
            "Token-like values are redacted in output and require security review.",
        ],
        "scanned_rows": dict(scanned_rows),
        "summary": {
            "findings": len(findings),
            "by_strategy": strategy_counts,
            "by_issue": issue_counts,
            "by_table": table_counts,
        },
        "findings": [asdict(finding) for finding in findings],
    }


def render_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def render_markdown(report: Mapping[str, Any], *, max_findings: int = 50) -> str:
    summary = report.get("summary") or {}
    lines = [
        "# Helpdesk Data Cleanup Dry-Run",
        "",
        f"- Generated at: `{report.get('generated_at')}`",
        f"- Mode: `{report.get('mode')}`",
        f"- Findings: `{summary.get('findings', 0)}`",
        f"- Scanned rows: `{json.dumps(report.get('scanned_rows') or {}, ensure_ascii=False, sort_keys=True)}`",
        f"- By issue: `{json.dumps(summary.get('by_issue') or {}, ensure_ascii=False, sort_keys=True)}`",
        f"- By strategy: `{json.dumps(summary.get('by_strategy') or {}, ensure_ascii=False, sort_keys=True)}`",
        "",
        "## Decisions",
        "",
    ]
    lines.extend(f"- {item}" for item in report.get("decisions") or [])
    lines.extend(["", "## Findings", ""])
    findings = list(report.get("findings") or [])
    if not findings:
        lines.append("No mojibake, placeholder or token-like values found in the scanned scope.")
    for finding in findings[:max_findings]:
        codes = ", ".join(finding.get("issue_codes") or [])
        lines.append(
            f"- `{finding.get('table')}` `{finding.get('row_key')}` "
            f"`{finding.get('field_path')}` [{codes}] "
            f"strategy=`{finding.get('cleanup_strategy')}` sample={json.dumps(finding.get('sample'), ensure_ascii=False)}"
        )
    if len(findings) > max_findings:
        lines.append(f"- ... and {len(findings) - max_findings} more findings in the JSON report.")
    return "\n".join(lines) + "\n"


def load_rows_from_json(path: Path) -> tuple[list[ScanRow], dict[str, int]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_rows = payload.get("rows") if isinstance(payload, dict) else payload
    if not isinstance(raw_rows, list):
        raise ValueError("--input-json must contain a list or an object with rows")
    rows: list[ScanRow] = []
    scanned_rows: dict[str, int] = {}
    for item in raw_rows:
        if not isinstance(item, dict):
            raise ValueError("Each input row must be an object")
        table = str(item.get("table") or "").strip()
        row_key = str(item.get("row_key") or "").strip()
        fields = item.get("fields") or {}
        if not table or not row_key or not isinstance(fields, dict):
            raise ValueError("Each input row requires table, row_key and object fields")
        rows.append(ScanRow(table=table, row_key=row_key, fields=fields))
        scanned_rows[table] = scanned_rows.get(table, 0) + 1
    return rows, scanned_rows


def load_server_env() -> None:
    env_path = SERVER_ROOT / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path, override=False)
        return
    except Exception:
        pass

    for raw_line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _limit_stmt(stmt: Any, limit: int) -> Any:
    return stmt if limit <= 0 else stmt.limit(limit)


async def collect_live_rows(database_url: str | None, *, limit: int) -> tuple[list[ScanRow], dict[str, int]]:
    load_server_env()
    if database_url:
        os.environ["DATABASE_URL"] = database_url
    if str(SERVER_ROOT) not in sys.path:
        sys.path.insert(0, str(SERVER_ROOT))

    from sqlalchemy import select

    from app.db import get_session, init_db, shutdown_db
    from app.db.models import DeviceToolsetSnapshot, Module, RegistryPerson, Ticket

    await init_db(os.environ.get("DATABASE_URL"))
    rows: list[ScanRow] = []
    scanned_rows: dict[str, int] = {}
    try:
        async with get_session() as session:
            ticket_stmt = _limit_stmt(select(Ticket).order_by(Ticket.created_at.desc()), limit)
            for ticket in (await session.execute(ticket_stmt)).scalars().all():
                custom_fields = ticket.custom_fields if isinstance(ticket.custom_fields, dict) else {}
                requester_profile = custom_fields.get("requester_profile") if isinstance(custom_fields, dict) else {}
                fields: dict[str, Any] = {
                    "title": ticket.title,
                    "description": ticket.description,
                    "requester_id": ticket.requester_id,
                    "custom_fields.user_display_name": custom_fields.get("user_display_name"),
                }
                if isinstance(requester_profile, dict):
                    for key in ("full_name", "building", "room", "phone"):
                        fields[f"custom_fields.requester_profile.{key}"] = requester_profile.get(key)
                rows.append(ScanRow("tickets", f"ticket_id={ticket.ticket_id}", fields))
            scanned_rows["tickets"] = sum(1 for row in rows if row.table == "tickets")

            people_stmt = _limit_stmt(select(RegistryPerson).order_by(RegistryPerson.updated_at.desc()), limit)
            for person in (await session.execute(people_stmt)).scalars().all():
                rows.append(
                    ScanRow(
                        "registry_people",
                        f"person_id={person.person_id}",
                        {
                            "display_name": person.display_name,
                            "full_name": person.full_name,
                        },
                    )
                )
            scanned_rows["registry_people"] = sum(1 for row in rows if row.table == "registry_people")

            module_stmt = _limit_stmt(select(Module).order_by(Module.created_at.desc()), limit)
            for module in (await session.execute(module_stmt)).scalars().all():
                fields = {
                    "module_name": module.module_name,
                    **extract_json_text_fields(module.manifest_json or {}, root_path="manifest_json"),
                    **extract_json_text_fields(module.manifest_summary or {}, root_path="manifest_summary"),
                }
                rows.append(ScanRow("modules", f"module_name={module.module_name},version={module.version}", fields))
            scanned_rows["modules"] = sum(1 for row in rows if row.table == "modules")

            snapshots_stmt = _limit_stmt(
                select(DeviceToolsetSnapshot).order_by(DeviceToolsetSnapshot.captured_at.desc()),
                limit,
            )
            for snapshot in (await session.execute(snapshots_stmt)).scalars().all():
                fields = extract_json_text_fields(snapshot.toolset_json or {}, root_path="toolset_json")
                rows.append(
                    ScanRow(
                        "device_toolset_snapshots",
                        f"snapshot_id={snapshot.snapshot_id},device_id={snapshot.device_id}",
                        fields,
                    )
                )
            scanned_rows["device_toolset_snapshots"] = sum(
                1 for row in rows if row.table == "device_toolset_snapshots"
            )
    finally:
        await shutdown_db()
    return rows, scanned_rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only helpdesk data cleanup inventory.")
    parser.add_argument("--database-url", default=None, help="DATABASE_URL override. Defaults to env/server/.env.")
    parser.add_argument("--input-json", type=Path, help="Offline rows fixture instead of live DB.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output-json", type=Path, help="Exact JSON report path.")
    parser.add_argument("--output-md", type=Path, help="Exact Markdown report path.")
    parser.add_argument("--limit", type=int, default=5000, help="Rows per live table. Use 0 for no limit.")
    parser.add_argument("--apply", action="store_true", help="Reserved for future deterministic cleanup; no mutation today.")
    parser.add_argument("--fail-on-findings", action="store_true", help="Exit 1 when findings exist.")
    return parser.parse_args()


async def amain() -> int:
    args = parse_args()
    dry_run = not args.apply
    if args.input_json:
        rows, scanned_rows = load_rows_from_json(args.input_json)
    else:
        rows, scanned_rows = await collect_live_rows(args.database_url, limit=max(args.limit, 0))

    findings = collect_findings(rows)
    report = build_report(findings, scanned_rows=scanned_rows, dry_run=dry_run)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    output_json = args.output_json or output_dir / f"helpdesk_data_cleanup_{timestamp}.json"
    output_md = args.output_md or output_dir / f"helpdesk_data_cleanup_{timestamp}.md"
    output_json.write_text(render_json(report), encoding="utf-8")
    output_md.write_text(render_markdown(report), encoding="utf-8")

    print(render_json({"status": "ok", "mode": report["mode"], "findings": len(findings), "json": str(output_json), "md": str(output_md)}))
    if args.apply:
        print("Apply mode is not implemented; no data was changed.", file=sys.stderr)
        return 2
    if args.fail_on_findings and findings:
        return 1
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(amain()))


if __name__ == "__main__":
    main()
