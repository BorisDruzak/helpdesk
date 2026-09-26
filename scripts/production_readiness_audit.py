"""Fail-closed validation of current-revision release risk evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def refresh_risk_audit(historical: dict, commit: str) -> dict:
    """Carry IDs forward without promoting historical fixes to current proof."""
    bugs = historical.get("bugs")
    if not isinstance(bugs, list) or not all(isinstance(item, dict) for item in bugs):
        raise ValueError("historical registry bugs must be records")
    return {
        "schema_version": "helpdesk_readiness_risks_v1",
        "source_revision": commit,
        "historical_revision": historical.get("head"),
        "bugs": [dict(
            id=item["id"], priority=item["priority"], status="unverified",
            release_blocker=bool(item.get("release_blocker")),
            source_revision=commit, verification=[],
        ) for item in bugs],
    }


def validate_risk_audit(payload: dict, commit: str) -> None:
    if payload.get("source_revision") != commit:
        raise ValueError("risk audit does not identify the candidate revision")
    bugs = payload.get("bugs")
    if not isinstance(bugs, list):
        raise ValueError("risk audit bugs must be a list")
    seen = set()
    for item in bugs:
        if not isinstance(item, dict) or not all(key in item for key in (
            "id", "priority", "status", "release_blocker", "source_revision", "verification"
        )):
            raise ValueError("risk record is incomplete")
        identifier = item["id"]
        if not isinstance(identifier, str) or not identifier or identifier in seen:
            raise ValueError("risk IDs must be nonempty and unique")
        seen.add(identifier)
        priority = item["priority"]
        if priority not in {"P0", "P1", "P2", "P3"} or not isinstance(item["release_blocker"], bool):
            raise ValueError("risk priority or blocker flag is invalid")
        if priority in {"P0", "P1"}:
            proof = item["verification"]
            if item["source_revision"] != commit or not isinstance(proof, list) or not proof or not all(
                isinstance(entry, str) and entry.strip() for entry in proof
            ):
                raise ValueError(f"{identifier}: current-revision verification missing")
            status = item["status"]
            if status not in {"verified", "open"}:
                raise ValueError(f"{identifier}: high-priority disposition is unverified")
            if status == "open" and (priority == "P0" or item["release_blocker"]):
                raise ValueError(f"{identifier}: open release blocker")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--refresh-source", type=Path,
                        help="Create an unverified audit from the historical registry; never passes the gate")
    args = parser.parse_args()
    try:
        if args.refresh_source:
            payload = refresh_risk_audit(json.loads(args.refresh_source.read_text(encoding="utf-8")), args.commit)
            args.audit.parent.mkdir(parents=True, exist_ok=True)
            args.audit.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            print("Unverified current-revision audit created; acceptance remains blocked")
            return
        validate_risk_audit(json.loads(args.audit.read_text(encoding="utf-8")), args.commit)
    except (ValueError, OSError, TypeError) as error:
        raise SystemExit(f"Readiness risk gate failed: {error}") from None
    print("Current-revision risk gate passed")


if __name__ == "__main__":
    main()
