#!/usr/bin/env python3
"""
Run subagent workers in parallel and produce a combined summary report.

Workers:
- subagent_worker_server.py
- subagent_worker_agent.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path


def ts_folder() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


async def run_one(name: str, cmd: list[str], cwd: Path) -> dict:
    started = time.perf_counter()
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_b, stderr_b = await proc.communicate()
    dt = round(time.perf_counter() - started, 3)
    return {
        "name": name,
        "cmd": cmd,
        "returncode": proc.returncode,
        "duration_sec": dt,
        "stdout": stdout_b.decode("utf-8", errors="replace"),
        "stderr": stderr_b.decode("utf-8", errors="replace"),
    }


def render_summary_md(summary: dict) -> str:
    lines = []
    lines.append("# Subagents Summary")
    lines.append("")
    lines.append(f"- started_at: `{summary['started_at']}`")
    lines.append(f"- finished_at: `{summary['finished_at']}`")
    lines.append(f"- repo_root: `{summary['repo_root']}`")
    lines.append(f"- ok: `{summary['ok']}`")
    lines.append("")
    lines.append("## Workers")
    for w in summary["workers"]:
        lines.append(f"- `{w['name']}`: returncode=`{w['returncode']}` duration_sec=`{w['duration_sec']}`")
    lines.append("")
    lines.append("## Reports")
    lines.append(f"- server: `{summary['report_paths']['server_md']}`")
    lines.append(f"- agent: `{summary['report_paths']['agent_md']}`")
    lines.append(f"- summary_json: `{summary['report_paths']['summary_json']}`")
    lines.append("")
    lines.append("## Stdout/Stderr")
    for w in summary["workers"]:
        stdout_clean = (w["stdout"] or "").replace("\r", "").rstrip()
        stderr_clean = (w["stderr"] or "").replace("\r", "").rstrip()
        lines.append(f"### {w['name']}")
        lines.append("```text")
        lines.append(stdout_clean or "<empty stdout>")
        if stderr_clean:
            lines.append("--- stderr ---")
            lines.append(stderr_clean)
        lines.append("```")
        lines.append("")
    return "\n".join(lines)


async def run(args: argparse.Namespace) -> int:
    script_dir = Path(__file__).resolve().parent
    repo_root = Path(args.repo_root).resolve()

    if args.output_dir:
        out_dir = Path(args.output_dir).resolve()
    else:
        out_dir = (repo_root / "server" / "reports" / "subagents" / ts_folder()).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    server_json = out_dir / "server_worker.json"
    server_md = out_dir / "server_worker.md"
    agent_json = out_dir / "agent_worker.json"
    agent_md = out_dir / "agent_worker.md"

    py = sys.executable
    env_readonly = os.getenv(
        "READONLY_DATABASE_URL",
        "postgresql://pc_client_ro:1.Abcdef@example.test:5432/pc_client",
    )

    cmd_server = [
        py,
        str(script_dir / "subagent_worker_server.py"),
        "--repo-root",
        str(repo_root),
        "--admin-url",
        args.admin_url,
        "--readonly-db-url",
        env_readonly,
        "--output-json",
        str(server_json),
        "--output-md",
        str(server_md),
    ]
    cmd_agent = [
        py,
        str(script_dir / "subagent_worker_agent.py"),
        "--repo-root",
        str(repo_root),
        "--output-json",
        str(agent_json),
        "--output-md",
        str(agent_md),
    ]

    started_at = time.strftime("%Y-%m-%dT%H:%M:%S")
    workers = await asyncio.gather(
        run_one("server-worker", cmd_server, repo_root),
        run_one("agent-worker", cmd_agent, repo_root),
    )
    finished_at = time.strftime("%Y-%m-%dT%H:%M:%S")

    ok = all(w["returncode"] == 0 for w in workers)
    summary = {
        "started_at": started_at,
        "finished_at": finished_at,
        "repo_root": str(repo_root),
        "ok": ok,
        "workers": workers,
        "report_paths": {
            "server_md": str(server_md),
            "agent_md": str(agent_md),
            "summary_md": str(out_dir / "summary.md"),
            "summary_json": str(out_dir / "summary.json"),
        },
    }

    summary_json = out_dir / "summary.json"
    summary_md = out_dir / "summary.md"
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    summary_md.write_text(render_summary_md(summary), encoding="utf-8")

    print(f"[subagents] output_dir={out_dir}")
    print(f"[subagents] summary_md={summary_md}")
    print(f"[subagents] ok={ok}")
    return 0 if ok else 1


def parse_args() -> argparse.Namespace:
    script = Path(__file__).resolve()
    default_repo = script.parents[2]
    p = argparse.ArgumentParser(description="Run project subagent workers in parallel")
    p.add_argument("--repo-root", default=str(default_repo))
    p.add_argument("--admin-url", default="http://example.test:8666/admin")
    p.add_argument("--output-dir", default="")
    return p.parse_args()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run(parse_args())))
