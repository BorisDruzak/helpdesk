"""Create one operator credential and a separate server grant for an administrator."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _write_new_private_file(path: Path, content: str) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as output:
        output.write(content)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operator", required=True, help="Existing Helpdesk operator login")
    parser.add_argument("--token-file", type=Path, required=True, help="New private file for the MCP")
    parser.add_argument("--grant-file", type=Path, required=True, help="New file with the server-side grant")
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--scope", action="append", required=True, choices=(
        "tickets.read", "tickets.reply", "tickets.transition", "diagnostics.read", "diagnostics.run",
    ))
    args = parser.parse_args()
    if not 1 <= args.hours <= 720 or not 1 <= len(args.operator.strip()) <= 255:
        parser.error("Use an existing operator login and a lifetime of 1 to 720 hours")
    if args.token_file.resolve() == args.grant_file.resolve():
        parser.error("The token and grant must use different files")

    token = "hdo_" + secrets.token_urlsafe(32)
    record = {
        "operator": args.operator.strip(),
        "sha256": hashlib.sha256(token.encode("ascii")).hexdigest(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=args.hours)).isoformat(),
        "scopes": sorted(set(args.scope)),
    }
    _write_new_private_file(args.token_file, token + "\n")
    try:
        _write_new_private_file(args.grant_file, json.dumps([record], ensure_ascii=False, indent=2) + "\n")
    except OSError:
        args.token_file.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    main()
