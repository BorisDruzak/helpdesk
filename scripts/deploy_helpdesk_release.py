#!/usr/bin/env python3
"""Deploy a committed Helpdesk revision to its dedicated Linux host."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
import tarfile
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from scripts.helpdesk_remote_profile import RemoteProfile


def release_path(profile: RemoteProfile, commit: str, *, release_id: str | None = None) -> str:
    deployment_root = Path(profile.root).parent.as_posix()
    identifier = release_id or commit
    if not re.fullmatch(r"[0-9A-Za-z][0-9A-Za-z._-]*", identifier):
        raise ValueError("release id must contain only letters, digits, dots, underscores, and hyphens")
    return f"{deployment_root}/releases/helpdesk-{identifier}"


def remote_install_command(
    profile: RemoteProfile,
    commit: str,
    remote_archive: str,
    *,
    release_id: str | None = None,
) -> str:
    release = release_path(profile, commit, release_id=release_id)
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
            f"previous_release=$(sudo readlink -f {profile.root} 2>/dev/null || true)",
            f"if [ -n \"$previous_release\" ]; then printf '%s\\n' \"$previous_release\" | sudo install -o root -g root -m 0644 /dev/stdin /etc/helpdesk/previous-release; fi",
            f"sudo ln -sfn {release} {profile.root}",
            "sudo systemctl daemon-reload",
            f"sudo systemctl start {profile.migrate_service}",
            f"sudo systemctl restart {runtime_services}",
            f"sudo systemctl is-active {runtime_services}",
        ]
    )


def append_webapp_bundle_to_release_archive(
    release_archive: Path,
    bundle_dir: Path,
    release_prefix: str,
) -> None:
    index_path = bundle_dir / "index.html"
    assets_dir = bundle_dir / "assets"
    if not index_path.is_file() or not assets_dir.is_dir() or not any(path.is_file() for path in assets_dir.rglob("*")):
        raise RuntimeError("webapp bundle is incomplete: expected index.html and at least one asset")
    with tarfile.open(release_archive, "a") as archive:
        archive.add(bundle_dir, arcname=f"{release_prefix}/webapp/dist")


def build_webapp_bundle_into_release_archive(
    workspace: Path,
    commit: str,
    release_archive: Path,
    release_prefix: str,
) -> None:
    with tempfile.TemporaryDirectory(prefix="helpdesk_webapp_bundle_") as temp_dir:
        temp_root = Path(temp_dir)
        source_archive = temp_root / "release-source.tar"
        source_workspace = temp_root / "workspace"
        bundle_dir = temp_root / "webapp-dist"
        bundle_archive = temp_root / "webapp-dist.tar.gz"
        subprocess.run(
            ["git", "archive", "--format=tar", "-o", str(source_archive), commit],
            cwd=workspace,
            check=True,
        )
        with tarfile.open(source_archive) as archive:
            archive.extractall(source_workspace, filter="data")
        subprocess.run(
            [
                sys.executable,
                str(source_workspace / "scripts" / "build_webapp_bundle.py"),
                "--workspace",
                str(source_workspace),
                "--output-dir",
                str(bundle_dir),
                "--archive",
                str(bundle_archive),
            ],
            cwd=source_workspace,
            check=True,
        )
        append_webapp_bundle_to_release_archive(release_archive, bundle_dir, release_prefix)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", help="Committed Git revision to deploy (defaults to HEAD).")
    parser.add_argument("--remote", help="SSH destination override.")
    parser.add_argument(
        "--release-id",
        help="Optional immutable release identifier; use for a retry of an existing commit.",
    )
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
    if profile.ssh_tty:
        command.append("-tt")
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
    release_id = args.release_id or commit
    release_path(profile, commit, release_id=release_id)
    archive_name = f"helpdesk-{release_id}.tar"
    remote_archive = f"/tmp/{archive_name}"

    with tempfile.TemporaryDirectory(prefix="helpdesk_release_") as temp_dir:
        local_archive = Path(temp_dir) / archive_name
        release_prefix = f"helpdesk-{commit}"
        subprocess.run(
            ["git", "archive", "--format=tar", f"--prefix={release_prefix}/", "-o", str(local_archive), commit],
            cwd=WORKSPACE,
            check=True,
        )
        build_webapp_bundle_into_release_archive(WORKSPACE, commit, local_archive, release_prefix)
        subprocess.run([*_scp_base(profile), str(local_archive), f"{remote}:{remote_archive}"], cwd=WORKSPACE, check=True)

    subprocess.run(
        [
            *_ssh_base(profile),
            remote,
            remote_install_command(profile, commit, remote_archive, release_id=release_id),
        ],
        cwd=WORKSPACE,
        check=True,
    )
    print(f"Deployed Helpdesk commit {commit} to {remote}.")


if __name__ == "__main__":
    main()
