#!/usr/bin/env python3
"""Enable or disable requester registration on the approved Helpdesk staging host."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import shutil
import socket
import tempfile


KEY = "WEB_SELF_REGISTRATION_ENABLED"


def set_registration(path: Path, enabled: bool) -> bool:
    if type(enabled) is not bool:
        raise ValueError("Boolean registration policy required")
    if path.is_symlink() or not path.is_file():
        raise ValueError("Regular environment file required")
    original = path.read_bytes()
    lines = original.decode("utf-8").splitlines(keepends=True)
    pattern = re.compile(r"^\s*(?:export\s+)?WEB_SELF_REGISTRATION_ENABLED\s*=")
    retained = "".join(line for line in lines if not pattern.match(line))
    if retained and not retained.endswith("\n"):
        retained += "\n"
    updated = (retained + KEY + "=" + str(enabled).lower() + "\n").encode("utf-8")
    if original == updated:
        return False
    metadata = path.stat()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    backup = path.with_name(path.name + ".registration-" + stamp + ".bak")
    fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(original)
        stream.flush()
        os.fsync(stream.fileno())
    if hasattr(os, "chown"):
        os.chown(backup, metadata.st_uid, metadata.st_gid)
    fd, temporary = tempfile.mkstemp(prefix=".registration-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(updated)
            stream.flush()
            os.fsync(stream.fileno())
        shutil.copymode(path, temporary)
        if hasattr(os, "chown"):
            os.chown(temporary, metadata.st_uid, metadata.st_gid)
        if path.is_symlink() or path.read_bytes() != original:
            raise ValueError("Environment changed during registration update")
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enabled", required=True, choices=("true", "false"))
    args = parser.parse_args()
    if os.name != "posix" or socket.gethostname() != "test-helpdesk":
        raise SystemExit("Run only on the approved Helpdesk staging host")
    changed = set_registration(Path("/etc/helpdesk-staging/helpdesk.env"), args.enabled == "true")
    print(f"Requester registration: {args.enabled}; changed: {changed}. Restart through manage_remote_stack.py.")


if __name__ == "__main__":
    main()
