#!/usr/bin/env python3
"""Write a safe Tech Panel backup status marker."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def write_backup_status_marker(
    *,
    output: Path,
    status: str,
    target: str,
    duration_seconds: int | None = None,
    artifact: str | None = None,
) -> dict[str, Any]:
    normalized_status = str(status or "").strip().lower()
    if normalized_status not in {"success", "failed", "unknown"}:
        raise ValueError("status must be success, failed or unknown")
    payload: dict[str, Any] = {
        "status": normalized_status,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "target": str(target or "").strip(),
    }
    if duration_seconds is not None:
        payload["duration_seconds"] = int(duration_seconds)
    if artifact:
        payload["artifact"] = str(artifact)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", choices=("success", "failed", "unknown"), required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--duration-seconds", type=int)
    parser.add_argument("--artifact")
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = write_backup_status_marker(
        output=args.output,
        status=args.status,
        target=args.target,
        duration_seconds=args.duration_seconds,
        artifact=args.artifact,
    )
    print(json.dumps({"status": payload["status"], "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
