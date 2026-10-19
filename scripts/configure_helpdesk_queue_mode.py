#!/usr/bin/env python3
"""Change only the reviewed staging queue-mode setting, retaining a private backup."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import shutil
import tempfile


def set_queue_mode(path: Path, mode: str) -> bool:
    if mode not in {"unified", "partitioned"}:
        raise ValueError("Unsupported queue mode")
    original = path.read_text(encoding="utf-8")
    lines = original.splitlines(keepends=True)
    pattern = re.compile(r"^\s*(?:export\s+)?TICKET_QUEUE_MODE\s*=")
    updated = "".join(line for line in lines if not pattern.match(line))
    if updated and not updated.endswith("\n"):
        updated += "\n"
    updated += f"TICKET_QUEUE_MODE={mode}\n"
    if original == updated:
        return False
    metadata = path.stat()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    backup = path.with_name(path.name + ".queue-mode-" + stamp + ".bak")
    # Create private before copying any environment data.
    with backup.open("xb") as stream:
        os.chmod(backup, 0o600)
        stream.write(path.read_bytes())
    if hasattr(os, "chown"):
        os.chown(backup, metadata.st_uid, metadata.st_gid)
    fd, temporary = tempfile.mkstemp(prefix=".queue-mode-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            stream.write(updated)
            stream.flush()
            os.fsync(stream.fileno())
        shutil.copymode(path, temporary)
        if hasattr(os, "chown"):
            os.chown(temporary, metadata.st_uid, metadata.st_gid)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=("unified", "partitioned"))
    args = parser.parse_args()
    path = Path("/etc/helpdesk-staging/helpdesk.env")
    if os.name != "posix" or not path.is_file() or path.is_symlink():
        raise SystemExit("Run on the approved staging host with its reviewed environment file")
    changed = set_queue_mode(path, args.mode)
    print(f"Queue mode: {args.mode}; changed: {changed}. Restart the staging service through manage_remote_stack.py.")


if __name__ == "__main__":
    main()
