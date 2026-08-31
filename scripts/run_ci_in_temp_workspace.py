#!/usr/bin/env python3
"""Run the canonical CI suite in a temporary checkout and venv.

This script is intended for self-hosted Linux/Windows runners or Git hooks:
it checks out a target commit into an isolated workspace, creates a dedicated
virtual environment from ``requirements-ci.txt``, runs ``scripts/run_ci_suite.py``,
and copies the resulting artifacts back into the source workspace under
``artifacts/ci/<sha>/``.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from scripts.ci_artifacts import DEFAULT_WORKSPACE, detect_commit
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.ci_artifacts import DEFAULT_WORKSPACE, detect_commit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--commit")
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python interpreter used to create the CI virtual environment.",
    )
    parser.add_argument(
        "--keep-workspace",
        action="store_true",
        help="Keep the temporary checkout for post-mortem inspection.",
    )
    return parser.parse_args()


def run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
    print(f"[ci-temp] {' '.join(str(part) for part in command)}")
    subprocess.run(command, cwd=cwd, env=env, check=True)


def venv_python(venv_root: Path) -> Path:
    if os.name == "nt":
        return venv_root / "Scripts" / "python.exe"
    return venv_root / "bin" / "python"


def main() -> None:
    args = parse_args()
    workspace = args.workspace.resolve()
    commit = detect_commit(workspace, args.commit)
    temp_root = Path(tempfile.mkdtemp(prefix=f"pc_client_ci_{commit[:8]}_"))
    checkout_dir = temp_root / "checkout"
    venv_dir = temp_root / ".venv-ci"

    try:
        run(["git", "clone", "--no-checkout", str(workspace), str(checkout_dir)], cwd=workspace)
        run(["git", "checkout", commit], cwd=checkout_dir)

        run([args.python, "-m", "venv", str(venv_dir)], cwd=checkout_dir)
        ci_python = venv_python(venv_dir)
        run([str(ci_python), "-m", "pip", "install", "--upgrade", "pip"], cwd=checkout_dir)
        run(
            [str(ci_python), "-m", "pip", "install", "-r", str(checkout_dir / "requirements-ci.txt")],
            cwd=checkout_dir,
        )
        run(
            [
                str(ci_python),
                str(checkout_dir / "scripts" / "run_ci_suite.py"),
                "--workspace",
                str(checkout_dir),
                "--commit",
                commit,
                "--parallel",
                "--max-workers",
                "2",
            ],
            cwd=checkout_dir,
        )

        source_artifact_dir = checkout_dir / "artifacts" / "ci" / commit
        target_artifact_dir = workspace / "artifacts" / "ci" / commit
        target_artifact_dir.parent.mkdir(parents=True, exist_ok=True)
        if target_artifact_dir.exists():
            shutil.rmtree(target_artifact_dir)
        shutil.copytree(source_artifact_dir, target_artifact_dir)
        print(f"[ci-temp] copied artifacts to {target_artifact_dir}")
    finally:
        if args.keep_workspace:
            print(f"[ci-temp] kept temp workspace at {temp_root}")
        else:
            shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    main()
