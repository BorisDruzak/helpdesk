"""Enable OLA on the isolated staging service with a guarded, reversible edit."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import tempfile


def enable_ola(environment: Path, *, expected_sha256: str) -> dict:
    if environment.is_symlink() or not environment.is_file():
        raise ValueError("Environment must be an existing regular file")
    before = environment.read_bytes()
    digest = hashlib.sha256(before).hexdigest()
    if digest != expected_sha256:
        raise ValueError("Environment changed; repeat the read-only check")
    text = before.decode("utf-8")
    lines = text.splitlines(keepends=True)
    pattern = re.compile(r"^\s*(?:export\s+)?TICKET_OLA_ENABLED\s*=")
    lines = [line for line in lines if not pattern.match(line)]
    after = ("".join(lines).rstrip("\r\n") + "\nTICKET_OLA_ENABLED=true\n").encode("utf-8")
    if after == before:
        return {"changed": False, "environment_sha256": digest}
    metadata = environment.stat()
    backup = environment.with_name(environment.name + ".ola-" + digest[:16] + ".bak")
    # Retain exact bytes, private permissions and ownership; never print values.
    try:
        with backup.open("xb") as stream:
            os.chmod(backup, 0o600)
            if hasattr(os, "chown"):
                os.chown(backup, metadata.st_uid, metadata.st_gid)
            stream.write(before)
    except FileExistsError:
        if backup.is_symlink() or backup.read_bytes() != before:
            raise ValueError("Backup path conflict")
    fd, temporary_name = tempfile.mkstemp(prefix=".ola-config-", dir=environment.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as stream:
            os.chmod(temporary, stat.S_IMODE(metadata.st_mode))
            if hasattr(os, "chown"):
                os.chown(temporary, metadata.st_uid, metadata.st_gid)
            stream.write(after)
            stream.flush()
            os.fsync(stream.fileno())
        if hashlib.sha256(environment.read_bytes()).hexdigest() != digest:
            raise ValueError("Environment changed during update")
        temporary.replace(environment)
    finally:
        temporary.unlink(missing_ok=True)
    return {"changed": True, "environment_sha256": hashlib.sha256(after).hexdigest(), "backup": str(backup)}


@contextmanager
def deployment_lock():
    import fcntl
    with Path("/run/lock/helpdesk-staging.service.deploy.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def require_staging_release(expected_release):
    current = Path("/opt/helpdesk-staging/current").resolve()
    if (socket.gethostname() != "test-helpdesk" or current.parent != Path("/opt/helpdesk-staging/releases")
            or current.name != "helpdesk-" + expected_release
            or Path(__file__).resolve().parent.parent != current):
        raise SystemExit("Staging release guard failed")


def apply_to_staging(expected_release, expected_environment_sha256):
    with deployment_lock():
        require_staging_release(expected_release)
        result = enable_ola(Path("/etc/helpdesk-staging/helpdesk.env"), expected_sha256=expected_environment_sha256)
        if result["changed"]:
            subprocess.run(["systemctl", "restart", "helpdesk-staging.service"], check=True)
        subprocess.run(["systemctl", "is-active", "--quiet", "helpdesk-staging.service"], check=True)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-release", required=True)
    parser.add_argument("--expected-environment-sha256")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    require_staging_release(args.expected_release)
    environment = Path("/etc/helpdesk-staging/helpdesk.env")
    if not args.apply:
        if environment.is_symlink():
            raise SystemExit("Environment symlink rejected")
        print(json.dumps({"release": args.expected_release, "environment_sha256": hashlib.sha256(environment.read_bytes()).hexdigest()}))
        return
    if not args.expected_environment_sha256:
        raise SystemExit("A fresh environment hash is required")
    result = apply_to_staging(args.expected_release, args.expected_environment_sha256)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
