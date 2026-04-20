#!/usr/bin/env python3
"""Build the React webapp and export a deployable bundle artifact."""

from __future__ import annotations

import argparse
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


def main() -> None:
    args = parse_args()
    workspace = args.workspace.resolve()
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
    print(f"[webapp-bundle] bundle directory: {output_dir}")
    print(f"[webapp-bundle] bundle archive: {args.archive.resolve()}")


if __name__ == "__main__":
    main()
