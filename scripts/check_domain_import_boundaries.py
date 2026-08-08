#!/usr/bin/env python3
"""Reject runtime Helpdesk imports of the local Knowledge implementation."""

from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WORKSPACE = REPO_ROOT
SERVER_ROOT = Path("server")
MIGRATION_VERSIONS = Path("server/app/db/migrations/versions")
KNOWLEDGE_MODULE = "knowledge"
KNOWLEDGE_REPOSITORY = "app.repos.knowledge_repo"
KNOWLEDGE_MODELS_MODULE = "app.db.models"


@dataclass(frozen=True)
class ImportViolation:
    path: Path
    line: int
    imported: str


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    return parser.parse_args(argv)


def _is_historical_migration(path: Path, workspace: Path) -> bool:
    try:
        relative = path.relative_to(workspace)
    except ValueError:
        return False
    return relative.is_relative_to(MIGRATION_VERSIONS)


def _is_knowledge_module(module: str) -> bool:
    return module == KNOWLEDGE_MODULE or module.startswith(f"{KNOWLEDGE_MODULE}.")


def _is_knowledge_repository(module: str) -> bool:
    return module == KNOWLEDGE_REPOSITORY or module.startswith(f"{KNOWLEDGE_REPOSITORY}.")


def _format_import_from(module: str, names: list[ast.alias]) -> str:
    imported = ", ".join(
        alias.name if alias.asname is None else f"{alias.name} as {alias.asname}" for alias in names
    )
    return f"from {module} import {imported}"


def _find_file_violations(path: Path, workspace: Path) -> list[ImportViolation]:
    if _is_historical_migration(path, workspace):
        return []

    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    violations: list[ImportViolation] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_knowledge_module(alias.name) or _is_knowledge_repository(alias.name):
                    imported = alias.name if alias.asname is None else f"{alias.name} as {alias.asname}"
                    violations.append(ImportViolation(path, node.lineno, f"import {imported}"))
            continue

        if not isinstance(node, ast.ImportFrom) or node.level != 0 or node.module is None:
            continue
        if _is_knowledge_module(node.module) or _is_knowledge_repository(node.module):
            violations.append(ImportViolation(path, node.lineno, _format_import_from(node.module, node.names)))
            continue
        if node.module != KNOWLEDGE_MODELS_MODULE:
            continue

        knowledge_models = [alias for alias in node.names if alias.name == "*" or alias.name.startswith("Knowledge")]
        if knowledge_models:
            violations.append(
                ImportViolation(path, node.lineno, _format_import_from(node.module, knowledge_models))
            )
    return violations


def find_forbidden_imports(workspace: Path) -> list[ImportViolation]:
    workspace = workspace.resolve()
    server_root = workspace / SERVER_ROOT
    if not server_root.exists():
        return []

    violations: list[ImportViolation] = []
    for path in sorted(server_root.rglob("*.py")):
        if path.is_relative_to(server_root / "tests"):
            continue
        violations.extend(_find_file_violations(path, workspace))
    return violations


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    workspace = args.workspace.resolve()
    violations = find_forbidden_imports(workspace)
    if not violations:
        print(f"Domain import boundary check passed for {workspace}")
        return 0

    print("Domain import boundary check failed:")
    for violation in violations:
        relative = violation.path.relative_to(workspace).as_posix()
        print(f" - {relative}:{violation.line}: {violation.imported}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
