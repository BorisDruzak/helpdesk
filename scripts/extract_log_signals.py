#!/usr/bin/env python3
"""
Выделяет из лога сервера/агента pc_client строки с повышенным сигналом.

Ввод: stdin (по умолчанию) или файл (--file). Кодировка UTF-8.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


# Подстроки/шаблоны без лишних ложных срабатываний на "Exception" внутри слов
_LINE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"Traceback \(most recent call last\):", re.I),
    re.compile(r"^\s*File \".+\", line \d+", re.M),
    re.compile(r"\|\s*(ERROR|CRITICAL)\s+\|"),
    re.compile(r"\bException\b"),
    re.compile(r"\bBaseException\b"),
    re.compile(r"invalid UI token", re.I),
    re.compile(r"Невалидный токен UI", re.I),
    re.compile(r"Authentication failed", re.I),
    re.compile(r"Module download failed", re.I),
    re.compile(r"MODULE_FILE_MISSING", re.I),
    re.compile(r"module archive missing", re.I),
    re.compile(r"install_module_package", re.I),
    re.compile(r"Builtin module install skipped", re.I),
    re.compile(r"address already in use", re.I),
    re.compile(r"Errno 98\b"),
    re.compile(r"Another agent instance is already running", re.I),
    re.compile(r"greenlet_spawn has not been called", re.I),
    re.compile(r"await_only\(\)", re.I),
    re.compile(r"Версия БД \d+ > версия кода", re.I),
]


def line_is_signal(line: str) -> bool:
    return any(p.search(line) for p in _LINE_PATTERNS)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Filter log lines to high-signal errors and known failure modes."
    )
    parser.add_argument(
        "path",
        nargs="?",
        metavar="PATH",
        help="Log file (default: stdin)",
    )
    parser.add_argument(
        "-f",
        "--file",
        dest="path_flag",
        metavar="PATH",
        help="Log file (alternative to positional PATH)",
    )
    args = parser.parse_args()
    path = args.path_flag or args.path

    if path:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines(keepends=True)
    else:
        lines = sys.stdin.readlines()

    for line in lines:
        if line_is_signal(line):
            sys.stdout.write(line)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
