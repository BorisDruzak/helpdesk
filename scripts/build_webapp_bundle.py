#!/usr/bin/env python3
"""Build the React webapp and export a deployable bundle artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

DEFAULT_WORKSPACE = Path(r"C:\Users\admin-2\CodexProjects\pc_client")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--source-commit", help="Exact commit for a git-archive source export")
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Assume webapp dependencies are already installed.",
    )
    return parser.parse_args()


def resolve_command(name: str) -> str:
    candidates = [name]
    if os.name == "nt":
        candidates = [f"{name}.cmd", f"{name}.exe", name]
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    raise SystemExit(f"Required command not found on PATH: {name}")


def run(command: list[str], *, cwd: Path) -> None:
    print(f"[webapp-bundle] {' '.join(str(part) for part in command)}")
    subprocess.run([resolve_command(command[0]), *command[1:]], cwd=cwd, check=True)


def copy_dist_tree(dist_dir: Path, output_dir: Path) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    shutil.copytree(dist_dir, output_dir)


def create_archive(output_dir: Path, archive_path: Path) -> None:
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(output_dir, arcname="dist")


def bundle_digest(output_dir: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(output_dir.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(output_dir).as_posix().encode("utf-8") + b"\0")
            with path.open("rb") as handle:
                digest.update(hashlib.file_digest(handle, "sha256").digest())
    return digest.hexdigest()


def main() -> None:
    args = parse_args()
    workspace = args.workspace.resolve()
    if (workspace / ".git").exists():
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=workspace, text=True).strip()
        if args.source_commit and args.source_commit != commit:
            raise SystemExit("Web bundle source commit differs from checkout")
        dirty = subprocess.check_output(["git", "status", "--porcelain", "--", "webapp", "package.json", "pnpm-lock.yaml", ".node-version"], cwd=workspace, text=True)
        if dirty.strip():
            raise SystemExit("Web bundle source must be committed and clean")
    else:
        commit = args.source_commit
    if not commit or len(commit) != 40 or any(char not in "0123456789abcdef" for char in commit):
        raise SystemExit("Web bundle requires an exact source commit")
    webapp_dir = workspace / "webapp"
    dist_dir = webapp_dir / "dist"

    run([sys.executable, str(workspace / "scripts" / "bootstrap_web_toolchain.py")], cwd=workspace)
    if not args.skip_install:
        run(["pnpm", "--dir", str(webapp_dir), "install", "--frozen-lockfile"], cwd=workspace)
    run(["pnpm", "--dir", str(webapp_dir), "run", "build"], cwd=workspace)

    if not dist_dir.exists():
        raise SystemExit(f"webapp build did not produce dist directory: {dist_dir}")

    output_dir = args.output_dir.resolve()
    copy_dist_tree(dist_dir, output_dir)
    create_archive(output_dir, args.archive.resolve())
    archive_path = args.archive.resolve()
    with archive_path.open("rb") as handle:
        archive_digest = hashlib.file_digest(handle, "sha256").hexdigest()
    metadata = dict(helpdesk_git_sha=commit, webapp_build_digest=bundle_digest(output_dir), archive_sha256=archive_digest)
    archive_path.with_name(archive_path.name + ".manifest.json").write_text(json.dumps(metadata, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[webapp-bundle] bundle directory: {output_dir}")
    print(f"[webapp-bundle] bundle archive: {args.archive.resolve()}")


if __name__ == "__main__":
    main()
