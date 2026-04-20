#!/usr/bin/env python3
"""Fast validation for the local pc_client workspace."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from importlib import import_module
from pathlib import Path
from typing import Iterable

DEFAULT_WORKSPACE = Path(r"C:\Users\admin-2\CodexProjects\pc_client")
TEXT_SUFFIXES = {
    ".py",
    ".js",
    ".html",
    ".css",
    ".md",
    ".mdc",
    ".json",
    ".toml",
    ".txt",
    ".yml",
    ".yaml",
    ".ps1",
}
PY_COMPILE_BATCH_SIZE = 120
SKIP_DIRS = {
    ".git",
    ".pnpm-store",
    ".run",
    ".vscode",
    ".venvs",
    ".yarn",
    ".local-agent",
    ".pytest_cache",
    "__pycache__",
    "artifacts",
    "coverage",
    "node_modules",
    "venv",
    "data",
    "build",
    "dist",
    "uploads",
    "reports",
    "temp",
}

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--smoke-url", help="Optional base URL for scripts/smoke_test.py")
    parser.add_argument("--skip-docs-drift", action="store_true", help="Skip docs/CODEMAP drift check")
    return parser.parse_args()


def iter_files(workspace: Path):
    for path in workspace.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(workspace).parts):
            continue
        yield path


def check_text_files(files: list[Path]) -> list[str]:
    failures: list[str] = []
    for path in files:
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        raw = path.read_bytes()
        if b"\x00" in raw:
            failures.append(f"NUL bytes: {path}")
            continue
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            failures.append(f"UTF-8 decode failed: {path} ({exc})")
    return failures


def run_py_compile(workspace: Path, files: list[Path]) -> list[str]:
    py_files = [str(path) for path in files if path.suffix.lower() == ".py"]
    if not py_files:
        return []
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as handle:
        helper_path = Path(handle.name)
        handle.write(
            "from __future__ import annotations\n"
            "import py_compile\n"
            "import sys\n"
            "failed = []\n"
            "for file_name in sys.argv[1:]:\n"
            "    try:\n"
            "        py_compile.compile(file_name, doraise=True)\n"
            "    except Exception as exc:\n"
            "        failed.append(f'{file_name}: {exc}')\n"
            "if failed:\n"
            "    print('\\n'.join(failed))\n"
            "    raise SystemExit(1)\n"
        )
    try:
        failures: list[str] = []
        for batch in batched(py_files, PY_COMPILE_BATCH_SIZE):
            result = subprocess.run(
                [sys.executable, str(helper_path), *batch],
                cwd=workspace,
                capture_output=True,
                text=False,
            )
            if result.returncode != 0:
                output = _combined_output(result)
                failures.extend([line for line in output.splitlines() if line.strip()])
    finally:
        helper_path.unlink(missing_ok=True)
    return failures


def batched(items: list[str], size: int) -> Iterable[list[str]]:
    for index in range(0, len(items), size):
        yield items[index:index + size]


def _decode_output(raw: bytes | None) -> str:
    if not raw:
        return ""
    for encoding in ("utf-8", "cp1251", sys.getdefaultencoding()):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _combined_output(result: subprocess.CompletedProcess[bytes]) -> str:
    return (_decode_output(result.stdout) + "\n" + _decode_output(result.stderr)).strip()


def which(name: str) -> str | None:
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        if not directory:
            continue
        candidate = Path(directory) / name
        if candidate.exists():
            return str(candidate)
        if os.name == "nt":
            candidate_exe = Path(directory) / f"{name}.exe"
            if candidate_exe.exists():
                return str(candidate_exe)
    return None


def run_node_syntax(workspace: Path, files: list[Path]) -> list[str]:
    node = which("node")
    if not node:
        return ["node not found: JS syntax check skipped"]
    failures: list[str] = []
    for path in files:
        if path.suffix.lower() != ".js":
            continue
        result = subprocess.run(
            [node, "-c", str(path)],
            cwd=workspace,
            capture_output=True,
            text=False,
        )
        if result.returncode != 0:
            output = _combined_output(result)
            failures.append(f"{path}: {output}")
    return failures


def run_smoke(workspace: Path, base_url: str) -> list[str]:
    env = os.environ.copy()
    env["BASE_URL"] = base_url
    result = subprocess.run(
        [sys.executable, str(workspace / "scripts" / "smoke_test.py")],
        cwd=workspace,
        env=env,
        capture_output=True,
        text=False,
    )
    if result.returncode == 0:
        return []
    output = _combined_output(result)
    return [line for line in output.splitlines() if line.strip()]


def run_docs_drift(workspace: Path) -> list[str]:
    result = subprocess.run(
        [sys.executable, str(workspace / "scripts" / "docs_drift_check.py")],
        cwd=workspace,
        capture_output=True,
        text=False,
    )
    if result.returncode == 0:
        return []
    output = _combined_output(result)
    return [line for line in output.splitlines() if line.strip()]


def run_module_observer_guard(workspace: Path) -> list[str]:
    server_root = workspace / "server"
    if str(server_root) not in sys.path:
        sys.path.insert(0, str(server_root))
    scan_workspace_module_observer_failures = getattr(
        import_module("utils.module_observer_contract"),
        "scan_workspace_module_observer_failures",
    )

    return scan_workspace_module_observer_failures(workspace)


def main() -> None:
    args = parse_args()
    files = list(iter_files(args.workspace))
    failures: list[str] = []

    failures.extend(check_text_files(files))
    failures.extend(run_py_compile(args.workspace, files))
    node_results = run_node_syntax(args.workspace, files)
    failures.extend([item for item in node_results if "skipped" not in item])
    failures.extend(run_module_observer_guard(args.workspace))
    if not args.skip_docs_drift:
        failures.extend(run_docs_drift(args.workspace))

    if args.smoke_url:
        failures.extend(run_smoke(args.workspace, args.smoke_url))

    if failures:
        print("Verification failed:")
        for item in failures:
            print(f" - {item}")
        raise SystemExit(1)

    print(f"Verification passed for {args.workspace}")
    if any("skipped" in item for item in node_results):
        print("Note: node not found, JS syntax check was skipped.")


if __name__ == "__main__":
    main()
