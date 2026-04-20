#!/usr/bin/env python3
"""Bootstrap the canonical web toolchain for pc_client."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parent.parent


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def load_package_json() -> dict:
    return json.loads((WORKSPACE / "package.json").read_text(encoding="utf-8"))


def resolve_command(name: str) -> str:
    candidates = [name]
    if os.name == "nt":
        candidates = [f"{name}.cmd", f"{name}.exe", name]
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    raise SystemExit(f"Required command not found on PATH: {name}")


def run(command: list[str]) -> None:
    resolved = [resolve_command(command[0]), *command[1:]]
    print(f"[run] {' '.join(command)}")
    subprocess.run(resolved, cwd=WORKSPACE, check=True)


def capture(command: list[str]) -> str:
    resolved = [resolve_command(command[0]), *command[1:]]
    completed = subprocess.run(
        resolved,
        cwd=WORKSPACE,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.stdout.strip()


def normalize_node_version(raw: str) -> str:
    return raw[1:] if raw.startswith("v") else raw


def main() -> None:
    expected_node = read_text(WORKSPACE / ".node-version")
    package_json = load_package_json()
    package_manager = package_json.get("packageManager")
    if not package_manager or not package_manager.startswith("pnpm@"):
        raise SystemExit("package.json must declare an exact pnpm packageManager field before bootstrap.")

    current_node = normalize_node_version(capture(["node", "-v"]))
    if current_node != expected_node:
        raise SystemExit(
            f"Expected Node.js {expected_node} from .node-version, found {current_node}. "
            "Install or switch the canonical Node LTS before bootstrapping the web toolchain."
        )

    current_npm = capture(["npm", "-v"])
    current_corepack = capture(["corepack", "--version"])

    run(["corepack", "enable", "pnpm"])
    run(["corepack", "install"])

    current_pnpm = capture(["pnpm", "--version"])
    expected_pnpm = package_manager.split("@", 1)[1]
    if current_pnpm != expected_pnpm:
        raise SystemExit(
            f"Expected pnpm {expected_pnpm} from package.json, found {current_pnpm} after bootstrap."
        )

    print("Web toolchain is ready.")
    print(f"Node.js: {current_node}")
    print(f"npm: {current_npm}")
    print(f"corepack: {current_corepack}")
    print(f"pnpm: {current_pnpm}")
    print("Remote Linux remains a runtime host; frontend build stays local/CI-driven.")


if __name__ == "__main__":
    main()
