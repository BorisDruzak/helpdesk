#!/usr/bin/env python3
"""
Быстрый поиск по коду для агента и разработчика.

Примеры:
  python scripts/agent_find.py "run_tool"
  python scripts/agent_find.py "outbox_ack" --dir server
  python scripts/agent_find.py "handshake" --dir pc_agent -n 3
  python scripts/agent_find.py "device_seq" --ext py,md --fixed-strings
"""

from __future__ import annotations

import argparse
import locale
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from navigation_catalog import QUICK_LOOKUP_PATH, find_topics_for_query, repo_path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


REPO_ROOT = Path(__file__).resolve().parent.parent
CODEMAP_SERVER = REPO_ROOT / "server" / "docs" / "CODEMAP.md"
CODEMAP_AGENT = REPO_ROOT / "pc_agent" / "docs" / "CODEMAP.md"
EXCLUDED_DIR_NAMES = {
    ".git",
    "venv",
    ".venv",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
}
DEFAULT_EXTENSIONS = ("py", "js", "ts", "tsx", "md", "mdc", "toml", "yaml", "yml", "json", "ps1")


def decode_subprocess_output(data: bytes) -> str:
    for encoding in ("utf-8", locale.getpreferredencoding(False) or "utf-8", "cp1251"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def get_working_rg_path() -> str | None:
    candidates: list[str] = []
    env_path = os.environ.get("RG_PATH")
    if env_path:
        candidates.append(env_path)
    candidates.append(r"C:\Users\admin-2\AppData\Local\Microsoft\WinGet\Links\rg.exe")
    rg_path = shutil.which("rg")
    if rg_path:
        candidates.append(rg_path)

    seen: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        if not Path(candidate).exists():
            continue
        try:
            completed = subprocess.run(
                [candidate, "--version"],
                capture_output=True,
                text=False,
                timeout=10,
                cwd=REPO_ROOT,
            )
        except OSError:
            continue
        if completed.returncode == 0:
            return candidate
    return None


def normalize_extensions(raw_ext: str) -> list[str]:
    exts = [item.strip().lstrip(".") for item in raw_ext.split(",") if item.strip()]
    return exts or list(DEFAULT_EXTENSIONS)


def compile_pattern(pattern: str, *, fixed_strings: bool, case_sensitive: bool) -> re.Pattern[str]:
    source = re.escape(pattern) if fixed_strings else pattern
    flags = 0 if case_sensitive else re.IGNORECASE
    return re.compile(source, flags)


def should_skip_dir(path: Path) -> bool:
    return any(part in EXCLUDED_DIR_NAMES for part in path.parts)


def iter_candidate_files(search_root: Path, extensions: set[str]) -> list[Path]:
    files: list[Path] = []
    for path in search_root.rglob("*"):
        if not path.is_file():
            continue
        if should_skip_dir(path.relative_to(search_root)):
            continue
        if extensions and path.suffix.lstrip(".").lower() not in extensions:
            continue
        files.append(path)
    return files


def parse_rg_output(stdout: str, max_count: int) -> list[tuple[str, int, int, str]]:
    matches: list[tuple[str, int, int, str]] = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split(":", 3)
        if len(parts) < 4:
            continue
        filepath, line_num, column_num, content = parts
        try:
            matches.append((filepath, int(line_num), int(column_num), content.strip()))
        except ValueError:
            continue
        if max_count and len(matches) >= max_count:
            break
    return matches


def run_rg(
    rg_path: str,
    pattern: str,
    search_root: Path,
    extensions: list[str],
    max_count: int,
    *,
    fixed_strings: bool,
    case_sensitive: bool,
) -> list[tuple[str, int, int, str]]:
    cmd = [
        rg_path,
        "--line-number",
        "--column",
        "--no-heading",
        "--color",
        "never",
        "--hidden",
        "--glob",
        "!**/.git/**",
        "--glob",
        "!**/venv/**",
        "--glob",
        "!**/.venv/**",
        "--glob",
        "!**/node_modules/**",
        "--glob",
        "!**/__pycache__/**",
        "--glob",
        "!**/dist/**",
        "--glob",
        "!**/build/**",
    ]
    if fixed_strings:
        cmd.append("--fixed-strings")
    if case_sensitive:
        cmd.append("--case-sensitive")
    else:
        cmd.append("--smart-case")
    if max_count:
        cmd.extend(["--max-count", str(max_count)])
    for ext in extensions:
        cmd.extend(["--glob", f"*.{ext}"])
    cmd.extend([pattern, str(search_root)])

    completed = subprocess.run(
        cmd,
        capture_output=True,
        text=False,
        timeout=30,
        cwd=REPO_ROOT,
    )
    stdout = decode_subprocess_output(completed.stdout)
    stderr = decode_subprocess_output(completed.stderr)

    if completed.returncode == 1 and not stdout.strip():
        return []
    if completed.returncode not in (0, 1) and stderr.strip():
        raise RuntimeError(stderr.strip())
    return parse_rg_output(stdout, max_count)


def run_python_search(
    compiled_pattern: re.Pattern[str],
    search_root: Path,
    extensions: list[str],
    max_count: int,
) -> list[tuple[str, int, int, str]]:
    matches: list[tuple[str, int, int, str]] = []
    extension_set = {ext.lower() for ext in extensions}

    for file_path in iter_candidate_files(search_root, extension_set):
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            match = compiled_pattern.search(line)
            if not match:
                continue
            column_number = match.start() + 1
            matches.append((str(file_path), line_number, column_number, line.strip()))
            if max_count and len(matches) >= max_count:
                return matches
    return matches


def codemap_mentions(pattern: str) -> list[str]:
    hints: list[str] = []
    escaped = re.escape(pattern)
    for label, path in (("server", CODEMAP_SERVER), ("pc_agent", CODEMAP_AGENT)):
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if re.search(escaped, content, re.IGNORECASE):
            rel_path = path.relative_to(REPO_ROOT)
            hints.append(f"see {label} codemap: {rel_path}")
    return hints


def topic_hints(pattern: str, *, max_topics: int) -> list[str]:
    hints: list[str] = []
    topics = find_topics_for_query(pattern, limit=max_topics)
    for topic in topics:
        first_files = ", ".join(topic.first_files[:3])
        docs = ", ".join(topic.related_docs[:3])
        hints.append(f"topic: {topic.title} -> open {first_files}")
        hints.append(f"topic-docs: {docs}")
    if topics:
        hints.append(f"see quick lookup: {repo_path(QUICK_LOOKUP_PATH)}")
    return hints


def format_match(
    filepath: str,
    line_number: int,
    column_number: int,
    content: str,
    *,
    absolute_paths: bool,
) -> str:
    path_obj = Path(filepath)
    try:
        display_path = path_obj if absolute_paths else path_obj.relative_to(REPO_ROOT)
    except ValueError:
        display_path = path_obj
    snippet = content if len(content) <= 140 else content[:137] + "..."
    return f"{display_path}:{line_number}:{column_number}: {snippet}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Быстрый поиск по коду для агента и разработчика.")
    parser.add_argument("pattern", help="Строка или regex для поиска")
    parser.add_argument("--dir", choices=["server", "pc_agent"], help="Ограничить поиск каталогом")
    parser.add_argument(
        "--ext",
        default=",".join(DEFAULT_EXTENSIONS),
        help="Расширения через запятую (по умолчанию py,js,ts,tsx,md,mdc,toml,yaml,yml,json,ps1)",
    )
    parser.add_argument("-n", "--max", type=int, default=0, help="Максимум строк вывода (0 = без лимита)")
    parser.add_argument("--fixed-strings", action="store_true", help="Искать как обычную строку, а не regex")
    parser.add_argument("--case-sensitive", action="store_true", help="Включить чувствительность к регистру")
    parser.add_argument("--absolute-paths", action="store_true", help="Печатать абсолютные пути")
    parser.add_argument("--no-codemap", action="store_true", help="Не показывать подсказки по CODEMAP")
    parser.add_argument("--topics-only", action="store_true", help="Показать только подсказки по темам и документам")
    parser.add_argument("--max-topics", type=int, default=3, help="Сколько тематических подсказок печатать")
    args = parser.parse_args()

    search_root = REPO_ROOT / args.dir if args.dir else REPO_ROOT
    if not search_root.is_dir():
        print(f"Каталог не найден: {search_root}", file=sys.stderr)
        return 1

    hints = topic_hints(args.pattern, max_topics=max(0, args.max_topics))
    if args.topics_only:
        if not hints:
            return 1
        for hint in hints:
            print(f"hint: {hint}")
        return 0

    extensions = normalize_extensions(args.ext)
    rg_path = get_working_rg_path()

    try:
        if rg_path:
            matches = run_rg(
                rg_path,
                args.pattern,
                search_root,
                extensions,
                args.max,
                fixed_strings=args.fixed_strings,
                case_sensitive=args.case_sensitive,
            )
        else:
            compiled_pattern = compile_pattern(
                args.pattern,
                fixed_strings=args.fixed_strings,
                case_sensitive=args.case_sensitive,
            )
            matches = run_python_search(compiled_pattern, search_root, extensions, args.max)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except re.error as exc:
        print(f"Некорректный regex: {exc}", file=sys.stderr)
        return 2

    for filepath, line_number, column_number, content in matches:
        print(
            format_match(
                filepath,
                line_number,
                column_number,
                content,
                absolute_paths=args.absolute_paths,
            )
        )

    if matches and not args.no_codemap:
        for hint in codemap_mentions(args.pattern):
            print(f"hint: {hint}")
    for hint in hints:
        print(f"hint: {hint}")

    return 0 if matches else 1


if __name__ == "__main__":
    raise SystemExit(main())
