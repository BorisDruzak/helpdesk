#!/usr/bin/env python3
"""Deploy a committed Helpdesk revision to its dedicated Linux host."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from scripts.helpdesk_remote_profile import RemoteProfile


def release_path(profile: RemoteProfile, commit: str) -> str:
    deployment_root = Path(profile.root).parent.as_posix()
    return f"{deployment_root}/releases/helpdesk-{commit}"


def remote_install_command(profile: RemoteProfile, commit: str, remote_archive: str) -> str:
    release = release_path(profile, commit)
    deployment_root = Path(profile.root).parent.as_posix()
    release_venv = f"{release}/{profile.release_venv_path}"
    runtime_services = " ".join(
        service for service in (profile.server_service, profile.control_service) if service
    )
    return " ; ".join(
        [
            "set -eu",
            f"test -f {profile.environment_file}",
            f"test ! -e {release}",
            f"sudo install -d -o root -g root -m 0755 {deployment_root}/releases",
            f"sudo mkdir {release}",
            f"sudo tar -xf {remote_archive} -C {release} --strip-components=1",
            f"sudo rm -f {remote_archive}",
            f"sudo python3 -m venv {release_venv}",
            f"sudo {release_venv}/bin/pip install --disable-pip-version-check --no-input -r {release}/server/requirements.txt",
            f"sudo chown -R root:root {release}",
            f"sudo chmod -R a-w {release}",
            f"sudo ln -sfn {release} {profile.root}",
            "sudo systemctl daemon-reload",
            f"sudo systemctl start {profile.migrate_service}",
            f"sudo systemctl restart {runtime_services}",
            f"sudo systemctl is-active {runtime_services}",
        ]
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", help="Committed Git revision to deploy (defaults to HEAD).")
    parser.add_argument("--remote", help="SSH destination override.")
    return parser.parse_args()


def _git_commit(commit: str | None) -> str:
    requested = commit or "HEAD"
    completed = subprocess.run(
        ["git", "rev-parse", "--verify", f"{requested}^{{commit}}"],
        cwd=WORKSPACE,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def _ssh_base(profile: RemoteProfile) -> list[str]:
    command = ["ssh"]
    if profile.ssh_key.exists():
        command.extend(["-i", str(profile.ssh_key)])
    return command


def _scp_base(profile: RemoteProfile) -> list[str]:
    command = ["scp"]
    if profile.ssh_key.exists():
        command.extend(["-i", str(profile.ssh_key)])
    return command


def main() -> None:
    args = parse_args()
    profile = RemoteProfile.from_environment()
    remote = args.remote or profile.remote
    commit = _git_commit(args.commit)
    archive_name = f"helpdesk-{commit}.tar"
    remote_archive = f"/tmp/{archive_name}"

    with tempfile.TemporaryDirectory(prefix="helpdesk_release_") as temp_dir:
        local_archive = Path(temp_dir) / archive_name
        subprocess.run(
            ["git", "archive", "--format=tar", f"--prefix=helpdesk-{commit}/", "-o", str(local_archive), commit],
            cwd=WORKSPACE,
            check=True,
        )
        subprocess.run([*_scp_base(profile), str(local_archive), f"{remote}:{remote_archive}"], cwd=WORKSPACE, check=True)

    subprocess.run(
        [*_ssh_base(profile), remote, remote_install_command(profile, commit, remote_archive)],
        cwd=WORKSPACE,
        check=True,
    )
    print(f"Deployed Helpdesk commit {commit} to {remote}.")


if __name__ == "__main__":
    main()
