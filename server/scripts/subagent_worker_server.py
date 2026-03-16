#!/usr/bin/env python3
"""
Server-focused worker.

Checks:
- key server files/docs presence
- admin URL availability
- PostgreSQL read-only connectivity (if asyncpg is available)
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path


DEFAULT_ADMIN_URL = "http://192.168.100.17:8666/admin"
DEFAULT_DB_URL = "postgresql://pc_client_ro:1.Abcdef@192.168.100.17:5432/pc_client"


def check_files(repo_root: Path) -> dict:
    must_exist = [
        "server/server.py",
        "server/routes.py",
        "server/config.py",
        "server/docs/PROTOCOL_V3.md",
        "server/docs/CODEMAP.md",
        "server/AGENTS.md",
    ]
    results = []
    for rel in must_exist:
        p = repo_root / rel
        results.append({"path": rel, "exists": p.exists()})
    ok = all(x["exists"] for x in results)
    return {"ok": ok, "items": results}


def check_admin_url(url: str) -> dict:
    start = time.perf_counter()
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=6) as resp:
            body = resp.read(2000).decode("utf-8", errors="replace")
            dt = round((time.perf_counter() - start) * 1000, 2)
            return {
                "ok": True,
                "url": url,
                "status": getattr(resp, "status", 200),
                "latency_ms": dt,
                "title_hint": "Панель администратора" if "Панель администратора" in body else None,
            }
    except urllib.error.HTTPError as e:
        dt = round((time.perf_counter() - start) * 1000, 2)
        return {"ok": False, "url": url, "error": f"HTTPError {e.code}", "latency_ms": dt}
    except Exception as e:  # noqa: BLE001
        dt = round((time.perf_counter() - start) * 1000, 2)
        return {"ok": False, "url": url, "error": str(e), "latency_ms": dt}


async def check_db_async(url: str) -> dict:
    try:
        import asyncpg  # type: ignore
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "available": False, "error": f"asyncpg unavailable: {e}"}

    conn = None
    try:
        conn = await asyncpg.connect(url, timeout=7)
        one = await conn.fetchval("select 1")
        tbl_count = await conn.fetchval(
            "select count(*) from information_schema.tables where table_schema='public'"
        )
        return {"ok": True, "available": True, "select_1": one, "public_tables": int(tbl_count)}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "available": True, "error": str(e)}
    finally:
        if conn is not None:
            await conn.close()


def render_markdown(report: dict) -> str:
    lines = []
    lines.append("# Subagent Report: Server")
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
    lines.append("## Admin URL")
    admin = report["checks"]["admin_url"]
    lines.append(f"- url: `{admin.get('url')}`")
    lines.append(f"- ok: `{admin.get('ok')}`")
    if "status" in admin:
        lines.append(f"- status: `{admin['status']}`")
    if "latency_ms" in admin:
        lines.append(f"- latency_ms: `{admin['latency_ms']}`")
    if admin.get("error"):
        lines.append(f"- error: `{admin['error']}`")
    lines.append("")
    lines.append("## PostgreSQL (read-only)")
    db = report["checks"]["postgres_readonly"]
    lines.append(f"- ok: `{db.get('ok')}`")
    lines.append(f"- available: `{db.get('available')}`")
    if "select_1" in db:
        lines.append(f"- select_1: `{db['select_1']}`")
    if "public_tables" in db:
        lines.append(f"- public_tables: `{db['public_tables']}`")
    if db.get("error"):
        lines.append(f"- error: `{db['error']}`")
    lines.append("")
    return "\n".join(lines)


async def run(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    output_json = Path(args.output_json)
    output_md = Path(args.output_md)

    started = time.strftime("%Y-%m-%dT%H:%M:%S")
    checks = {
        "files": check_files(repo_root),
        "admin_url": check_admin_url(args.admin_url),
        "postgres_readonly": await check_db_async(args.readonly_db_url),
    }

    ok = checks["files"]["ok"] and checks["admin_url"]["ok"] and checks["postgres_readonly"]["ok"]
    report = {
        "worker": "server",
        "started_at": started,
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "ok": ok,
        "checks": checks,
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    output_md.write_text(render_markdown(report), encoding="utf-8")

    print(f"[server-worker] report_json={output_json}")
    print(f"[server-worker] report_md={output_md}")
    print(f"[server-worker] ok={ok}")
    return 0 if ok else 1


def parse_args() -> argparse.Namespace:
    script = Path(__file__).resolve()
    default_repo = script.parents[2]
    p = argparse.ArgumentParser(description="Server subagent worker")
    p.add_argument("--repo-root", default=str(default_repo))
    p.add_argument("--admin-url", default=DEFAULT_ADMIN_URL)
    p.add_argument("--readonly-db-url", default=os.getenv("READONLY_DATABASE_URL", DEFAULT_DB_URL))
    p.add_argument("--output-json", required=True)
    p.add_argument("--output-md", required=True)
    return p.parse_args()


if __name__ == "__main__":
    import asyncio

    raise SystemExit(asyncio.run(run(parse_args())))
