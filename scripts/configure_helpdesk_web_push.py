"""Plan/apply Web Push keys and configuration on the approved Helpdesk staging host."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import tempfile

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

KEY_SETTING = "HELPDESK_WEB_PUSH_PRIVATE_KEY_FILE"
SUBJECT_SETTING = "HELPDESK_WEB_PUSH_SUBJECT"


def _private_write(path: Path, content: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as output:
        output.write(content)
        output.flush()
        os.fsync(output.fileno())


def configure_files(environment_file: Path, key_file: Path, subject: str, *, expected_sha256: str, key_owner: tuple[int, int] | None = None) -> dict:
    if environment_file.is_symlink() or key_file.is_symlink():
        raise ValueError("Refuse symlink configuration or key")
    before = environment_file.read_bytes()
    digest = hashlib.sha256(before).hexdigest()
    if digest != expected_sha256:
        raise ValueError("Environment changed since plan")
    if subject != "https://helpdesk-staging.sosnadmin.local":
        raise ValueError("Unexpected staging contact subject")
    created = not key_file.exists()
    if created:
        key = ec.generate_private_key(ec.SECP256R1())
        _private_write(key_file, key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    key = serialization.load_pem_private_key(key_file.read_bytes(), password=None)
    if not isinstance(key, ec.EllipticCurvePrivateKey) or not isinstance(key.curve, ec.SECP256R1):
        raise ValueError("Existing Web Push key must be P-256")
    key_file.chmod(0o600)
    if key_owner is not None:
        os.chown(key_file, *key_owner)
    settings = {KEY_SETTING: str(key_file), SUBJECT_SETTING: subject}
    lines = before.decode("utf-8").splitlines()
    after_lines = [line for line in lines if line.partition("=")[0].strip() not in settings]
    after_lines.extend(f"{name}={value}" for name, value in settings.items())
    after = ("\n".join(after_lines) + "\n").encode("utf-8")
    changed = after != before
    if changed:
        backup = environment_file.with_name(environment_file.name + ".web-push-" + digest[:16] + ".bak")
        if backup.exists():
            if backup.is_symlink() or backup.read_bytes() != before:
                raise ValueError("Private configuration backup differs")
        else:
            _private_write(backup, before)
        descriptor, name = tempfile.mkstemp(prefix=".web-push-config-", dir=environment_file.parent)
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, "wb") as output:
                output.write(after); output.flush(); os.fsync(output.fileno())
            temporary.chmod(0o600)
            if os.name != "nt":
                metadata = environment_file.stat()
                os.chown(temporary, metadata.st_uid, metadata.st_gid)
            if hashlib.sha256(environment_file.read_bytes()).hexdigest() != digest:
                raise ValueError("Environment changed during apply")
            temporary.replace(environment_file)
        finally:
            temporary.unlink(missing_ok=True)
    public = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return {"changed": changed, "key_created": created, "key_public_sha256": hashlib.sha256(public).hexdigest(), "environment_sha256": hashlib.sha256(after).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-env-sha256")
    parser.add_argument("--expected-release", required=True)
    args = parser.parse_args()
    if os.name == "nt" or os.geteuid() != 0 or socket.gethostname() != "test-helpdesk":
        raise SystemExit("Approved staging host and root transport required")
    current = Path("/opt/helpdesk-staging/current").resolve()
    identity = json.loads((current / "release-identity.json").read_text())
    if current.parent != Path("/opt/helpdesk-staging/releases") or identity.get("helpdesk_git_sha") != args.expected_release:
        raise SystemExit("Staging release changed")
    env = Path("/etc/helpdesk-staging/helpdesk.env")
    directory = env.parent / "secrets"
    if env.is_symlink() or directory.is_symlink() or not directory.is_dir():
        raise SystemExit("Physical staging configuration paths required")
    key = directory / "web-push-vapid.pem"
    if not args.apply:
        print(json.dumps({"release": args.expected_release, "environment_sha256": hashlib.sha256(env.read_bytes()).hexdigest(), "key_exists": key.is_file()}))
        return
    if not args.expected_env_sha256:
        parser.error("Apply requires the environment fingerprint from plan")
    import pwd
    owner = pwd.getpwnam("helpdesk-staging")
    receipt = configure_files(env, key, "https://helpdesk-staging.sosnadmin.local", expected_sha256=args.expected_env_sha256, key_owner=(owner.pw_uid, owner.pw_gid))
    print(json.dumps({"release": args.expected_release, **receipt}))


if __name__ == "__main__":
    main()
