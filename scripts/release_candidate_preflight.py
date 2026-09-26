#!/usr/bin/env python3
"""Preflight a frozen release candidate before full-gate deploy/release."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

try:
    from scripts.ci_artifacts import (
        DEFAULT_WORKSPACE,
        detect_commit,
        resolve_green_ci_artifact,
        require_webapp_bundle_artifact,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.ci_artifacts import (
        DEFAULT_WORKSPACE,
        detect_commit,
        resolve_green_ci_artifact,
        require_webapp_bundle_artifact,
    )


GENERATED_DIRTY_PREFIXES = ("artifacts/",)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--commit")
    parser.add_argument("--production", action="store_true")
    parser.add_argument("--environment-file", type=Path)
    parser.add_argument("--risk-audit", type=Path)
    parser.add_argument("--readiness-evidence", type=Path)
    parser.add_argument("--provider-root", type=Path)
    parser.add_argument("--schema-revision")
    parser.add_argument(
        "--allow-local-dirty",
        action="store_true",
        help="Allow uncommitted local files. Full release still deploys committed Git state only.",
    )
    parser.add_argument(
        "--skip-webapp-bundle",
        action="store_true",
        help="Skip checking the webapp bundle artifact for the candidate commit.",
    )
    return parser.parse_args()


def git_status_short(workspace: Path) -> list[str]:
    completed = subprocess.run(
        ["git", "status", "--short", "--untracked-files=normal"],
        cwd=workspace,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return [line.rstrip() for line in completed.stdout.splitlines() if line.strip()]


def release_relevant_dirty_entries(entries: list[str]) -> list[str]:
    relevant: list[str] = []
    for entry in entries:
        path = entry[3:].strip() if len(entry) > 3 else entry.strip()
        normalized = path.replace("\\", "/")
        if any(normalized.startswith(prefix) for prefix in GENERATED_DIRTY_PREFIXES):
            continue
        relevant.append(entry)
    return relevant


def build_dirty_message(entries: list[str]) -> str:
    preview_limit = 20
    preview_lines = entries[:preview_limit]
    preview = "\n".join(f"  {line}" for line in preview_lines)
    if len(entries) > preview_limit:
        preview = f"{preview}\n  ... and {len(entries) - preview_limit} more"
    return (
        "Release candidate preflight found uncommitted local changes.\n"
        "Full CI and full gate are keyed to the committed HEAD only, so committing after "
        "green CI invalidates the artifact and forces another full run.\n"
        f"{preview}\n"
        "Commit/stash these changes before freezing the release candidate, or rerun with "
        "`--allow-local-dirty` only when you intentionally want to release the last committed state."
    )


def main() -> None:
    args = parse_args()
    workspace = args.workspace
    commit = detect_commit(workspace, args.commit)
    production = getattr(args, "production", False)
    if production:
        if args.allow_local_dirty or args.skip_webapp_bundle:
            raise SystemExit("Production preflight forbids dirty/bundle bypasses")
        if commit != detect_commit(workspace):
            raise SystemExit("Production preflight requires the current committed HEAD")
        if not all(getattr(args, name, None) for name in (
            "environment_file", "risk_audit", "readiness_evidence", "provider_root", "schema_revision"
        )):
            raise SystemExit("Production preflight requires config, risk audit, staging evidence, provider and schema")
    all_dirty_entries = git_status_short(workspace)
    dirty_entries = release_relevant_dirty_entries(all_dirty_entries)
    if dirty_entries and not args.allow_local_dirty:
        raise SystemExit(build_dirty_message(dirty_entries))

    print(f"[release-preflight] candidate_commit={commit}")
    if dirty_entries:
        print(
            "[release-preflight] WARNING: local workspace is dirty; full gate will validate "
            "and deploy only the committed candidate."
        )
    if all_dirty_entries and not dirty_entries:
        print("[release-preflight] generated/untracked artifacts are ignored for release-candidate dirtiness.")

    summary_path, artifact_commit, reused_artifact = resolve_green_ci_artifact(workspace, commit)
    if production and (reused_artifact or artifact_commit != commit):
        raise SystemExit("Production requires exact-SHA full CI; merge artifact reuse is forbidden")
    print(f"[release-preflight] green_ci_artifact={summary_path}")
    if reused_artifact:
        print(f"[release-preflight] reused_ci_artifact_commit={artifact_commit}")

    if not args.skip_webapp_bundle:
        bundle_path = require_webapp_bundle_artifact(workspace, artifact_commit)
        print(f"[release-preflight] webapp_bundle={bundle_path}")

    if production:
        from scripts.production_release_gate import validate_production_release
        try:
            manifest = validate_production_release(
                workspace, commit, bundle_path, environment_file=args.environment_file,
                risk_audit=args.risk_audit, evidence=args.readiness_evidence,
                provider_root=args.provider_root, schema=args.schema_revision,
            )
        except (ValueError, OSError, TypeError, KeyError):
            raise SystemExit("Production acceptance failed: config/risk/contract/bundle/live evidence must all verify") from None
        print(f"[release-preflight] immutable_release_manifest={manifest}")

    print(
        "[release-preflight] OK: frozen release candidate is ready for full gate. "
        "Do not commit before `python scripts/release_server_to_remote.py --gate full`."
    )


if __name__ == "__main__":
    main()
