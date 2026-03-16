#!/usr/bin/env python3
"""
Agent-focused worker.

Checks:
- key agent files/docs presence
- agent SQLite availability and base stats
- protocol marker in ws_agent.py
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import time
from pathlib import Path


def check_files(repo_root: Path) -> dict:
    must_exist = [
        "pc_agent/ws_agent.py",
        "pc_agent/core/orchestrator.py",
        "pc_agent/core/database.py",
        "pc_agent/docs/PROTOCOL_V3.md",
        "pc_agent/docs/CODEMAP.md",
        "pc_agent/AGENTS.md",
        "pc_agent/data/storage.db",
    ]
    items = []
    for rel in must_exist:
        p = repo_root / rel
        items.append({"path": rel, "exists": p.exists()})
    return {"ok": all(i["exists"] for i in items), "items": items}


def check_protocol_marker(repo_root: Path) -> dict:
    ws_agent = repo_root / "pc_agent/ws_agent.py"
    if not ws_agent.exists():
        return {"ok": False, "error": "ws_agent.py missing"}
    text = ws_agent.read_text(encoding="utf-8", errors="replace")
    has_marker = "ws_ticket_v3" in text
    return {"ok": has_marker, "marker": "ws_ticket_v3", "present": has_marker}


def query_sqlite(repo_root: Path) -> dict:
    db_path = repo_root / "pc_agent/data/storage.db"
    if not db_path.exists():
        return {"ok": False, "error": "storage.db missing"}

    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("select name from sqlite_master where type='table' order by name")
        tables = [r[0] for r in cur.fetchall()]

        stats = {}
        for t in ("outbox", "jobs", "seen_commands", "pending_consents", "auth_tokens"):
            if t in tables:
                cur.execute(f"select count(*) from {t}")
                stats[t] = int(cur.fetchone()[0])

        return {
            "ok": True,
            "db_path": str(db_path),
            "db_size_bytes": db_path.stat().st_size,
            "tables_count": len(tables),
            "tables_preview": tables[:25],
            "stats": stats,
        }
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}
    finally:
        if conn is not None:
            conn.close()


def render_markdown(report: dict) -> str:
    lines = []
    lines.append("# Subagent Report: Agent")
    lines.append("")
    lines.append(f"- worker: `{report['worker']}`")
    lines.append(f"- started_at: `{report['started_at']}`")
    lines.append(f"- finished_at: `{report['finished_at']}`")
    lines.append(f"- ok: `{report['ok']}`")
    lines.append("")
    lines.append("## Files")
    lines.append(f"- ok: `{report['checks']['files']['ok']}`")
    for item in report["checks"]["files"]["items"]:
        lines.append(f"- `{item['path']}` -> `{item['exists']}`")
    lines.append("")
    lines.append("## Protocol Marker")
    marker = report["checks"]["protocol_marker"]
    lines.append(f"- marker: `{marker.get('marker')}`")
    lines.append(f"- present: `{marker.get('present')}`")
    lines.append(f"- ok: `{marker.get('ok')}`")
    if marker.get("error"):
        lines.append(f"- error: `{marker['error']}`")
    lines.append("")
    lines.append("## SQLite")
    sq = report["checks"]["sqlite"]
    lines.append(f"- ok: `{sq.get('ok')}`")
    if sq.get("db_path"):
        lines.append(f"- db_path: `{sq['db_path']}`")
    if sq.get("db_size_bytes") is not None:
        lines.append(f"- db_size_bytes: `{sq['db_size_bytes']}`")
    if sq.get("tables_count") is not None:
        lines.append(f"- tables_count: `{sq['tables_count']}`")
    if sq.get("tables_preview"):
        lines.append(f"- tables_preview: `{', '.join(sq['tables_preview'])}`")
    if sq.get("stats"):
        for key, value in sq["stats"].items():
            lines.append(f"- {key}_count: `{value}`")
    if sq.get("error"):
        lines.append(f"- error: `{sq['error']}`")
    lines.append("")
    return "\n".join(lines)


def run(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    output_json = Path(args.output_json)
    output_md = Path(args.output_md)

    started = time.strftime("%Y-%m-%dT%H:%M:%S")
    checks = {
        "files": check_files(repo_root),
        "protocol_marker": check_protocol_marker(repo_root),
        "sqlite": query_sqlite(repo_root),
    }
    ok = checks["files"]["ok"] and checks["protocol_marker"]["ok"] and checks["sqlite"]["ok"]
    report = {
        "worker": "agent",
        "started_at": started,
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "ok": ok,
        "checks": checks,
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    output_md.write_text(render_markdown(report), encoding="utf-8")

    print(f"[agent-worker] report_json={output_json}")
    print(f"[agent-worker] report_md={output_md}")
    print(f"[agent-worker] ok={ok}")
    return 0 if ok else 1


def parse_args() -> argparse.Namespace:
    script = Path(__file__).resolve()
    default_repo = script.parents[2]
    p = argparse.ArgumentParser(description="Agent subagent worker")
    p.add_argument("--repo-root", default=str(default_repo))
    p.add_argument("--output-json", required=True)
    p.add_argument("--output-md", required=True)
    return p.parse_args()


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
