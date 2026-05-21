"""Write a safe restore-drill evidence marker for Tech Panel readiness."""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SECRET_RE = re.compile(r"(?i)(password|passwd|token|secret|api[_-]?key|authorization|cookie)")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_optional(value: str | None) -> str | None:
    if not value:
        return None
    if SECRET_RE.search(value):
        return "***REDACTED***"
    return value


def write_restore_drill_marker(
    output: str | Path,
    *,
    status: str,
    target: str,
    duration_seconds: int | float | None = None,
    artifact: str | None = None,
    finished_at: str | None = None,
) -> dict[str, Any]:
    normalized_status = str(status).strip().lower()
    if normalized_status not in {"success", "failed"}:
        raise ValueError("status must be success or failed")

    payload: dict[str, Any] = {
        "status": normalized_status,
        "finished_at": finished_at or _now_iso(),
        "target": _safe_optional(target) or "unknown",
        "duration_seconds": duration_seconds,
    }
    safe_artifact = _safe_optional(artifact)
    if safe_artifact:
        payload["artifact"] = safe_artifact

    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write Tech Panel restore drill marker")
    parser.add_argument("--status", required=True, choices=["success", "failed"])
    parser.add_argument("--target", required=True)
    parser.add_argument("--duration-seconds", type=float, default=None)
    parser.add_argument("--artifact", default=None)
    parser.add_argument("--output", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    write_restore_drill_marker(
        args.output,
        status=args.status,
        target=args.target,
        duration_seconds=args.duration_seconds,
        artifact=args.artifact,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
