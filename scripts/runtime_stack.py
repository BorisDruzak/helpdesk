#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
SERVER_DIR = WORKSPACE / "server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from runtime_control import (
    ALL_TARGETS,
    SYSTEMD_TARGETS,
    filter_log_entries,
    format_log_entries_as_text,
    get_unit_status,
    list_journal_entries,
    run_action_and_wait,
    smoke_server,
    stream_journal_logs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage pc_client runtime services on the current host.")
    parser.add_argument("action", choices=["start", "stop", "restart", "status", "smoke", "logs"])
    parser.add_argument("target", choices=ALL_TARGETS)
    parser.add_argument("--lines", type=int, default=80)
    parser.add_argument("--follow", action="store_true")
    parser.add_argument("--levels", default="")
    parser.add_argument("--contains", default="")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def _targets_for(value: str) -> list[str]:
    target = str(value or "").strip().lower()
    if target == "all":
        return ["control", "server", "agent"]
    if target in SYSTEMD_TARGETS:
        return [target]
    raise ValueError(f"Unsupported target: {value}")


def main() -> None:
    args = parse_args()
    targets = _targets_for(args.target)

    if args.action == "logs" and len(targets) == 1 and args.follow:
        raise SystemExit(stream_journal_logs(targets[0], lines=args.lines, follow=True))

    if args.action == "logs":
        level_filter = [item.strip().lower() for item in args.levels.split(",") if item.strip()]
        payload = {}
        for target in targets:
            entries = filter_log_entries(
                list_journal_entries(target, lines=args.lines),
                levels=level_filter,
                contains=args.contains,
            )
            payload[target] = entries
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            for target in targets:
                if len(targets) > 1:
                    print(f"== {target} ==")
                print(format_log_entries_as_text(payload[target]))
        return

    if args.action == "status":
        payload = {target: get_unit_status(target) for target in targets}
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            for target, status in payload.items():
                print(
                    f"{target}: {status['display_state']} "
                    f"(active={status['active_state']}, sub={status['sub_state']}, pid={status['main_pid'] or '-'})"
                )
                if status.get("uptime_sec") is not None:
                    print(f"  uptime_sec={status['uptime_sec']}")
                if status.get("status_excerpt"):
                    print(status["status_excerpt"])
        return

    if args.action == "smoke":
        if args.target not in {"server", "all"}:
            raise SystemExit("Smoke is supported only for the server target.")
        completed = smoke_server()
        if completed.stdout.strip():
            print(completed.stdout.strip())
        return

    results = {}
    for target in targets:
        results[target] = run_action_and_wait(target, args.action)
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for target, status in results.items():
            print(
                f"{target}: {args.action} -> {status['display_state']} "
                f"(active={status['active_state']}, sub={status['sub_state']}, pid={status['main_pid'] or '-'})"
            )


if __name__ == "__main__":
    main()
