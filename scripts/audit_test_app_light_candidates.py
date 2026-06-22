#!/usr/bin/env python3
"""Report server pytest files that may be safe candidates for test_client_light."""

from __future__ import annotations

import argparse
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


DEFAULT_TESTS_DIR = Path(__file__).resolve().parent.parent / "server" / "tests"

UNSAFE_TERMS: tuple[str, ...] = (
    "test_agent",
    "agent_ws",
    "DeviceOutboxSender",
    "recover_pending_commands",
    "outbox_sender",
    "enqueue_command_async",
    "CommandResultService",
    "AgentConnectionContext",
    "ws_connect",
)

REVIEW_TERMS: tuple[str, ...] = (
    "run_tool",
    "DeviceOutbox",
    "operation_id",
)


@dataclass(frozen=True)
class LightAppCandidateRecord:
    file: Path
    uses_test_client: bool
    light_opt_in: bool
    unsafe_terms: tuple[str, ...]
    review_terms: tuple[str, ...]
    recommendation: str


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _has_word(text: str, term: str) -> bool:
    return re.search(rf"\b{re.escape(term)}\b", text) is not None


def _detect_terms(text: str, terms: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(term for term in terms if _has_word(text, term))


def _uses_test_client(text: str) -> bool:
    return _has_word(text, "test_client")


def _light_opt_in(text: str) -> bool:
    if re.search(r"def\s+test_client\s*\(\s*test_client_light\s*\)", text) is not None:
        return True
    return re.search(r"def\s+test_\w+\s*\([^)]*\btest_client_light\b", text) is not None


def _recommendation(*, uses_test_client: bool, light_opt_in: bool, unsafe_terms: tuple[str, ...]) -> str:
    if light_opt_in and uses_test_client:
        return "already_light"
    if unsafe_terms:
        return "keep_regular"
    if uses_test_client:
        return "candidate"
    return "not_http_client"


def audit_tests(tests_dir: Path = DEFAULT_TESTS_DIR) -> list[LightAppCandidateRecord]:
    records: list[LightAppCandidateRecord] = []
    for path in sorted(tests_dir.rglob("test_*.py")):
        text = _read_text(path)
        uses_test_client = _uses_test_client(text)
        light_opt_in = _light_opt_in(text)
        unsafe_terms = _detect_terms(text, UNSAFE_TERMS)
        review_terms = _detect_terms(text, REVIEW_TERMS)
        recommendation = _recommendation(
            uses_test_client=uses_test_client,
            light_opt_in=light_opt_in,
            unsafe_terms=unsafe_terms,
        )
        if uses_test_client or light_opt_in or unsafe_terms or review_terms:
            records.append(
                LightAppCandidateRecord(
                    file=path,
                    uses_test_client=uses_test_client,
                    light_opt_in=light_opt_in,
                    unsafe_terms=unsafe_terms,
                    review_terms=review_terms,
                    recommendation=recommendation,
                )
            )
    return records


def _format_terms(terms: tuple[str, ...]) -> str:
    return ",".join(terms) if terms else "-"


def print_report(records: list[LightAppCandidateRecord], tests_dir: Path) -> None:
    counts = Counter(record.recommendation for record in records)
    print(f"test_app_light candidate audit: tests_dir={tests_dir}")
    print(
        "summary: "
        f"candidate={counts['candidate']} "
        f"already_light={counts['already_light']} "
        f"keep_regular={counts['keep_regular']} "
        f"not_http_client={counts['not_http_client']}"
    )
    print("file | recommendation | uses_test_client | light_opt_in | unsafe_terms | review_terms")
    for record in records:
        rel = record.file.relative_to(tests_dir) if record.file.is_relative_to(tests_dir) else record.file
        print(
            f"{rel} | {record.recommendation} | {record.uses_test_client} | "
            f"{record.light_opt_in} | {_format_terms(record.unsafe_terms)} | {_format_terms(record.review_terms)}"
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tests-dir", type=Path, default=DEFAULT_TESTS_DIR)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    records = audit_tests(args.tests_dir)
    print_report(records, args.tests_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
