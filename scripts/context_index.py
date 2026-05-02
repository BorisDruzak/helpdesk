#!/usr/bin/env python3
"""Deterministic local context index for pc_client docs and code landmarks."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

try:
    import docs_inventory
    import navigation_catalog as nav
except ModuleNotFoundError:  # pragma: no cover - package import for pytest
    from scripts import docs_inventory
    from scripts import navigation_catalog as nav


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INDEX_PATH = REPO_ROOT / "artifacts" / "context_index" / "pc_client.sqlite"
MARKDOWN_HEADING_RE = re.compile(r"^(?P<level>#{1,6})\s+(?P<title>.+?)\s*$")
ROUTE_RE = re.compile(
    r"\bweb\.(?P<method>get|post|put|patch|delete|view)\(\s*['\"](?P<path>[^'\"]+)['\"]\s*,\s*(?P<handler>[A-Za-z_][A-Za-z0-9_.]*)?",
    re.IGNORECASE,
)
TS_SYMBOL_RE = re.compile(
    r"^\s*(?:export\s+)?(?:async\s+)?(?:(?:function|class|interface|type)\s+(?P<named>[A-Za-z_][A-Za-z0-9_]*)|"
    r"(?:const|let|var)\s+(?P<const>[A-Za-z_][A-Za-z0-9_]*))"
)
TOKEN_RE = re.compile(r"[\w./:-]+", re.UNICODE)

EXCLUDED_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "artifacts",
    "build",
    "dist",
    "node_modules",
    "release_temp",
    "venv",
}
CODE_SYMBOL_ROOTS = ("server", "pc_agent", "shared", "scripts")
TS_SYMBOL_ROOT = Path("webapp/src")
PYTHON_SUFFIX = ".py"
TYPESCRIPT_SUFFIXES = {".ts", ".tsx"}
SEARCH_PROFILES = ("default", "debug", "contract", "route", "test", "web")


@dataclass(frozen=True)
class IndexItem:
    kind: str
    path: str
    title: str = ""
    name: str = ""
    parent: str = ""
    line_start: int = 1
    line_end: int = 1
    summary: str = ""
    text: str = ""
    extra: dict[str, Any] | None = None


def repo_path(path: str | Path, *, workspace: Path = REPO_ROOT) -> str:
    value = Path(path)
    if value.is_absolute():
        try:
            value = value.relative_to(workspace)
        except ValueError:
            return value.as_posix()
    return value.as_posix()


def should_skip_path(path: Path) -> bool:
    parts = {part.lower() for part in path.parts}
    return bool(parts & EXCLUDED_DIRS)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _line_count(text: str) -> int:
    return max(1, len(text.splitlines()))


def collect_markdown_docs(workspace: Path) -> list[Path]:
    docs: list[Path] = []
    for path in docs_inventory.collect_docs(workspace):
        if should_skip_path(path):
            continue
        status = docs_inventory.classify_doc(path)
        if status == "canonical" or path == Path("PLANS.md"):
            docs.append(path)
    return sorted(set(docs), key=lambda item: item.as_posix().lower())


def chunk_markdown(path: Path, text: str) -> list[IndexItem]:
    lines = text.splitlines()
    headings: list[tuple[int, str, int]] = []
    for index, line in enumerate(lines, start=1):
        match = MARKDOWN_HEADING_RE.match(line)
        if match:
            headings.append((index, match.group("title").strip(), len(match.group("level"))))

    if not headings:
        return [
            IndexItem(
                kind="doc",
                path=path.as_posix(),
                title=path.name,
                line_start=1,
                line_end=_line_count(text),
                summary=text[:240].strip(),
                text=text,
            )
        ]

    chunks: list[IndexItem] = []
    for offset, (line_start, title, level) in enumerate(headings):
        line_end = headings[offset + 1][0] - 1 if offset + 1 < len(headings) else len(lines)
        chunk_lines = lines[line_start - 1:line_end]
        chunk_text = "\n".join(chunk_lines).strip()
        chunks.append(
            IndexItem(
                kind="doc",
                path=path.as_posix(),
                title=title,
                name=title,
                parent=path.name,
                line_start=line_start,
                line_end=max(line_start, line_end),
                summary=_first_non_heading_summary(chunk_lines),
                text=chunk_text,
                extra={"heading_level": level},
            )
        )
    return chunks


def _first_non_heading_summary(lines: Sequence[str]) -> str:
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped[:260]
    return ""


def collect_doc_items(workspace: Path) -> list[IndexItem]:
    items: list[IndexItem] = []
    for relative_path in collect_markdown_docs(workspace):
        absolute_path = workspace / relative_path
        if not absolute_path.exists():
            continue
        items.extend(chunk_markdown(relative_path, _read_text(absolute_path)))
    return items


def collect_topic_items() -> list[IndexItem]:
    items: list[IndexItem] = []
    for topic in nav.TOPICS:
        text = "\n".join(
            [
                topic.title,
                topic.summary,
                "Aliases: " + ", ".join(topic.aliases),
                "First files: " + ", ".join(topic.first_files),
                "Related docs: " + ", ".join(topic.related_docs),
                "Checks: " + ", ".join(topic.checks),
            ]
        )
        items.append(
            IndexItem(
                kind="topic",
                path="scripts/navigation_catalog.py",
                title=topic.title,
                name=topic.key,
                summary=topic.summary,
                text=text,
                extra={
                    "aliases": list(topic.aliases),
                    "first_files": list(topic.first_files),
                    "related_docs": list(topic.related_docs),
                    "checks": list(topic.checks),
                    "plan_required": topic.plan_required,
                },
            )
        )
    return items


def collect_route_items(workspace: Path) -> list[IndexItem]:
    route_file = workspace / "server" / "routes.py"
    if not route_file.exists():
        return []
    relative_path = Path("server/routes.py")
    items: list[IndexItem] = []
    for line_number, line in enumerate(_read_text(route_file).splitlines(), start=1):
        for match in ROUTE_RE.finditer(line):
            method = match.group("method").upper()
            route_path = match.group("path")
            handler = match.group("handler") or ""
            name = f"{method} {route_path}"
            text = line.strip()
            if handler:
                text = f"{text}\nhandler: {handler}"
            items.append(
                IndexItem(
                    kind="route",
                    path=relative_path.as_posix(),
                    title=name,
                    name=name,
                    line_start=line_number,
                    line_end=line_number,
                    summary=line.strip(),
                    text=text,
                    extra={"method": method, "route": route_path, "handler": handler},
                )
            )
    return items


def iter_python_files(workspace: Path) -> Iterable[Path]:
    for root in CODE_SYMBOL_ROOTS:
        absolute_root = workspace / root
        if not absolute_root.exists():
            continue
        for path in absolute_root.rglob(f"*{PYTHON_SUFFIX}"):
            relative = path.relative_to(workspace)
            if should_skip_path(relative):
                continue
            if _is_test_path(relative):
                continue
            yield relative


def iter_python_test_files(workspace: Path) -> Iterable[Path]:
    roots = (*CODE_SYMBOL_ROOTS, "tests")
    seen: set[Path] = set()
    for root in roots:
        absolute_root = workspace / root
        if not absolute_root.exists():
            continue
        for path in absolute_root.rglob(f"*{PYTHON_SUFFIX}"):
            relative = path.relative_to(workspace)
            if relative in seen or should_skip_path(relative):
                continue
            if not _is_test_path(relative):
                continue
            seen.add(relative)
            yield relative


def _is_test_path(path: Path) -> bool:
    return "tests" in {part.lower() for part in path.parts} or path.name.startswith("test_")


def collect_python_symbol_items(workspace: Path) -> list[IndexItem]:
    items: list[IndexItem] = []
    for relative_path in iter_python_files(workspace):
        absolute_path = workspace / relative_path
        try:
            text = _read_text(absolute_path)
            tree = ast.parse(text)
        except (OSError, SyntaxError):
            continue
        lines = text.splitlines()
        items.extend(_symbols_from_ast(relative_path, tree, lines))
    return items


def collect_python_test_items(workspace: Path) -> list[IndexItem]:
    items: list[IndexItem] = []
    for relative_path in iter_python_test_files(workspace):
        absolute_path = workspace / relative_path
        try:
            text = _read_text(absolute_path)
            tree = ast.parse(text)
        except (OSError, SyntaxError):
            continue
        lines = text.splitlines()
        items.extend(_test_items_from_ast(relative_path, tree, lines))
    return items


def _symbols_from_ast(relative_path: Path, tree: ast.AST, lines: Sequence[str]) -> list[IndexItem]:
    items: list[IndexItem] = []
    for node in getattr(tree, "body", []):
        if isinstance(node, ast.ClassDef):
            items.append(_symbol_item(relative_path, node.name, node, lines))
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    items.append(_symbol_item(relative_path, f"{node.name}.{child.name}", child, lines, parent=node.name))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            items.append(_symbol_item(relative_path, node.name, node, lines))
    return items


def _test_items_from_ast(relative_path: Path, tree: ast.AST, lines: Sequence[str]) -> list[IndexItem]:
    items: list[IndexItem] = []
    for node in getattr(tree, "body", []):
        if isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            items.append(_symbol_item(relative_path, node.name, node, lines, kind="test"))
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name.startswith("test_"):
                    items.append(
                        _symbol_item(relative_path, f"{node.name}.{child.name}", child, lines, parent=node.name, kind="test")
                    )
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
            items.append(_symbol_item(relative_path, node.name, node, lines, kind="test"))
    return items


def _symbol_item(
    relative_path: Path,
    name: str,
    node: ast.AST,
    lines: Sequence[str],
    *,
    parent: str = "",
    kind: str = "symbol",
) -> IndexItem:
    line_start = int(getattr(node, "lineno", 1))
    line_end = int(getattr(node, "end_lineno", line_start))
    doc = ast.get_docstring(node) if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) else None
    snippet = "\n".join(lines[line_start - 1:min(line_end, line_start + 20)])
    return IndexItem(
        kind=kind,
        path=relative_path.as_posix(),
        title=name,
        name=name,
        parent=parent,
        line_start=line_start,
        line_end=line_end,
        summary=(doc or snippet.splitlines()[0] if snippet else "")[:260],
        text=snippet,
        extra={"symbol_type": type(node).__name__},
    )


def collect_typescript_symbol_items(workspace: Path) -> list[IndexItem]:
    root = workspace / TS_SYMBOL_ROOT
    if not root.exists():
        return []
    items: list[IndexItem] = []
    for absolute_path in root.rglob("*"):
        if not absolute_path.is_file() or absolute_path.suffix.lower() not in TYPESCRIPT_SUFFIXES:
            continue
        relative_path = absolute_path.relative_to(workspace)
        if should_skip_path(relative_path):
            continue
        lines = _read_text(absolute_path).splitlines()
        for line_number, line in enumerate(lines, start=1):
            match = TS_SYMBOL_RE.match(line)
            if not match:
                continue
            name = match.group("named") or match.group("const") or ""
            if not name:
                continue
            snippet = "\n".join(lines[line_number - 1:line_number + 12])
            items.append(
                IndexItem(
                    kind="symbol",
                    path=relative_path.as_posix(),
                    title=name,
                    name=name,
                    line_start=line_number,
                    line_end=line_number,
                    summary=line.strip()[:260],
                    text=snippet,
                    extra={"symbol_type": "typescript"},
                )
            )
    return items


def collect_all_items(workspace: Path) -> list[IndexItem]:
    return [
        *collect_doc_items(workspace),
        *collect_topic_items(),
        *collect_route_items(workspace),
        *collect_python_symbol_items(workspace),
        *collect_python_test_items(workspace),
        *collect_typescript_symbol_items(workspace),
    ]


def collect_index_source_paths(workspace: Path) -> list[Path]:
    paths: set[Path] = set()
    paths.update(collect_markdown_docs(workspace))
    paths.update(iter_python_files(workspace))
    paths.update(iter_python_test_files(workspace))

    route_file = Path("server/routes.py")
    if (workspace / route_file).exists():
        paths.add(route_file)

    nav_file = Path("scripts/navigation_catalog.py")
    if (workspace / nav_file).exists():
        paths.add(nav_file)

    root = workspace / TS_SYMBOL_ROOT
    if root.exists():
        for absolute_path in root.rglob("*"):
            if not absolute_path.is_file() or absolute_path.suffix.lower() not in TYPESCRIPT_SUFFIXES:
                continue
            relative_path = absolute_path.relative_to(workspace)
            if not should_skip_path(relative_path):
                paths.add(relative_path)

    return sorted(paths, key=lambda item: item.as_posix().lower())


def source_manifest(workspace: Path) -> list[dict[str, Any]]:
    manifest: list[dict[str, Any]] = []
    for relative_path in collect_index_source_paths(workspace):
        absolute_path = workspace / relative_path
        try:
            stat = absolute_path.stat()
            digest = hashlib.sha256(absolute_path.read_bytes()).hexdigest()
        except OSError:
            continue
        manifest.append(
            {
                "path": relative_path.as_posix(),
                "mtime_ns": stat.st_mtime_ns,
                "size": stat.st_size,
                "sha256": digest,
            }
        )
    return manifest


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _fts5_available(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute("CREATE VIRTUAL TABLE temp.__fts_probe USING fts5(value)")
        conn.execute("DROP TABLE temp.__fts_probe")
    except sqlite3.OperationalError:
        return False
    return True


def _create_schema(conn: sqlite3.Connection, *, fts_enabled: bool) -> None:
    conn.executescript(
        """
        DROP TABLE IF EXISTS items_fts;
        DROP TABLE IF EXISTS items;
        DROP TABLE IF EXISTS metadata;

        CREATE TABLE metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL,
            path TEXT NOT NULL,
            title TEXT NOT NULL DEFAULT '',
            name TEXT NOT NULL DEFAULT '',
            parent TEXT NOT NULL DEFAULT '',
            line_start INTEGER NOT NULL DEFAULT 1,
            line_end INTEGER NOT NULL DEFAULT 1,
            summary TEXT NOT NULL DEFAULT '',
            text TEXT NOT NULL DEFAULT '',
            extra_json TEXT NOT NULL DEFAULT '{}'
        );

        CREATE INDEX idx_items_kind ON items(kind);
        CREATE INDEX idx_items_path ON items(path);
        """
    )
    if fts_enabled:
        conn.execute(
            """
            CREATE VIRTUAL TABLE items_fts USING fts5(
                title,
                name,
                summary,
                text,
                path,
                content='items',
                content_rowid='id'
            )
            """
        )


def build_index(*, workspace: Path = REPO_ROOT, db_path: Path = DEFAULT_INDEX_PATH, force: bool = False) -> dict[str, Any]:
    workspace = workspace.resolve()
    db_path = db_path.resolve()
    if db_path.exists() and not force:
        db_path.unlink()

    items = collect_all_items(workspace)
    manifest = source_manifest(workspace)
    with connect(db_path) as conn:
        fts_enabled = _fts5_available(conn)
        _create_schema(conn, fts_enabled=fts_enabled)
        for item in items:
            cursor = conn.execute(
                """
                INSERT INTO items(kind, path, title, name, parent, line_start, line_end, summary, text, extra_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.kind,
                    item.path,
                    item.title,
                    item.name,
                    item.parent,
                    item.line_start,
                    item.line_end,
                    item.summary,
                    item.text,
                    json.dumps(item.extra or {}, ensure_ascii=False, sort_keys=True),
                ),
            )
            if fts_enabled:
                conn.execute(
                    """
                    INSERT INTO items_fts(rowid, title, name, summary, text, path)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (cursor.lastrowid, item.title, item.name, item.summary, item.text, item.path),
                )
        stats = _stats(conn, fts_enabled=fts_enabled)
        conn.execute("INSERT INTO metadata(key, value) VALUES ('stats', ?)", (json.dumps(stats, ensure_ascii=False),))
        conn.execute(
            "INSERT INTO metadata(key, value) VALUES ('source_manifest', ?)",
            (json.dumps(manifest, ensure_ascii=False, sort_keys=True),),
        )
        conn.commit()
    return stats


def _stats(conn: sqlite3.Connection, *, fts_enabled: bool) -> dict[str, Any]:
    counts = {
        row["kind"]: row["count"]
        for row in conn.execute("SELECT kind, COUNT(*) AS count FROM items GROUP BY kind").fetchall()
    }
    return {
        "items": sum(counts.values()),
        "docs": _count_distinct_paths(conn, "doc"),
        "chunks": counts.get("doc", 0),
        "topics": counts.get("topic", 0),
        "routes": counts.get("route", 0),
        "symbols": counts.get("symbol", 0),
        "tests": counts.get("test", 0),
        "fts_enabled": fts_enabled,
    }


def _count_distinct_paths(conn: sqlite3.Connection, kind: str) -> int:
    row = conn.execute("SELECT COUNT(DISTINCT path) AS count FROM items WHERE kind = ?", (kind,)).fetchone()
    return int(row["count"] or 0)


def freshness_status(*, workspace: Path = REPO_ROOT, db_path: Path = DEFAULT_INDEX_PATH) -> dict[str, Any]:
    if not db_path.exists():
        return {
            "exists": False,
            "stale": True,
            "changed_paths": [],
            "missing_paths": [],
            "new_paths": [],
            "reason": "missing",
        }

    try:
        with connect(db_path) as conn:
            row = conn.execute("SELECT value FROM metadata WHERE key = 'source_manifest'").fetchone()
    except sqlite3.Error:
        return {
            "exists": True,
            "stale": True,
            "changed_paths": [],
            "missing_paths": [],
            "new_paths": [],
            "reason": "unreadable",
        }

    if not row:
        return {
            "exists": True,
            "stale": True,
            "changed_paths": [],
            "missing_paths": [],
            "new_paths": [],
            "reason": "missing_manifest",
        }

    try:
        previous_manifest = json.loads(row["value"])
    except json.JSONDecodeError:
        previous_manifest = []
    previous = {item["path"]: item for item in previous_manifest if isinstance(item, dict) and "path" in item}
    current = {item["path"]: item for item in source_manifest(workspace)}

    changed_paths = sorted(
        path
        for path, item in current.items()
        if path in previous and item.get("sha256") != previous[path].get("sha256")
    )
    missing_paths = sorted(path for path in previous if path not in current)
    new_paths = sorted(path for path in current if path not in previous)
    stale = bool(changed_paths or missing_paths or new_paths)
    return {
        "exists": True,
        "stale": stale,
        "changed_paths": changed_paths,
        "missing_paths": missing_paths,
        "new_paths": new_paths,
        "reason": "stale" if stale else "fresh",
    }


def format_freshness_warning(status: dict[str, Any]) -> str:
    if not status.get("stale"):
        return ""
    reason = status.get("reason") or "stale"
    paths = [*status.get("changed_paths", []), *status.get("new_paths", []), *status.get("missing_paths", [])]
    suffix = ""
    if paths:
        shown = ", ".join(paths[:5])
        more = len(paths) - 5
        suffix = f": {shown}" + (f" (+{more} more)" if more > 0 else "")
    return f"Context index is stale ({reason}); rebuild with python scripts/build_context_index.py --force{suffix}."


def search_index(
    *,
    db_path: Path = DEFAULT_INDEX_PATH,
    query: str,
    limit: int = 12,
    kind: str | None = None,
    profile: str = "default",
) -> list[dict[str, Any]]:
    if not db_path.exists():
        raise FileNotFoundError(f"Context index not found: {db_path}")
    if profile not in SEARCH_PROFILES:
        raise ValueError(f"Unknown search profile: {profile}")
    with connect(db_path) as conn:
        fetch_limit = max(limit * 8, limit)
        if _has_fts_table(conn):
            rows = _search_fts(conn, query=query, limit=fetch_limit, kind=kind)
        else:
            rows = _search_like(conn, query=query, limit=fetch_limit, kind=kind)
    ranked_rows = sorted(rows, key=lambda row: _rerank_score(row, query=query, profile=profile))
    return [_row_to_result(row) for row in ranked_rows[:limit]]


def _has_fts_table(conn: sqlite3.Connection) -> bool:
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='items_fts'").fetchone()
    return row is not None


def _search_fts(conn: sqlite3.Connection, *, query: str, limit: int, kind: str | None) -> list[sqlite3.Row]:
    match_query = _fts_query(query)
    if not match_query:
        return []
    params: list[Any] = [match_query]
    kind_filter = ""
    if kind:
        kind_filter = "AND items.kind = ?"
        params.append(kind)
    params.append(limit)
    return conn.execute(
        f"""
        SELECT items.*, bm25(items_fts) AS rank
        FROM items_fts
        JOIN items ON items_fts.rowid = items.id
        WHERE items_fts MATCH ? {kind_filter}
        ORDER BY rank ASC, items.kind ASC, items.path ASC, items.line_start ASC
        LIMIT ?
        """,
        params,
    ).fetchall()


def _search_like(conn: sqlite3.Connection, *, query: str, limit: int, kind: str | None) -> list[sqlite3.Row]:
    terms = _query_terms(query)
    if not terms:
        return []
    clauses: list[str] = []
    params: list[Any] = []
    for term in terms:
        clauses.append("(title LIKE ? OR name LIKE ? OR summary LIKE ? OR text LIKE ? OR path LIKE ?)")
        like = f"%{term}%"
        params.extend([like, like, like, like, like])
    kind_filter = ""
    if kind:
        kind_filter = "AND kind = ?"
        params.append(kind)
    params.append(limit)
    return conn.execute(
        f"""
        SELECT *,
               0.0 AS rank
        FROM items
        WHERE ({' OR '.join(clauses)}) {kind_filter}
        ORDER BY kind ASC, path ASC, line_start ASC
        LIMIT ?
        """,
        params,
    ).fetchall()


def _query_terms(query: str) -> list[str]:
    return [term for term in TOKEN_RE.findall(query) if term.strip()]


def _fts_query(query: str) -> str:
    terms = _query_terms(query)
    return " OR ".join(f'"{term}"' for term in terms)


def _row_to_result(row: sqlite3.Row) -> dict[str, Any]:
    extra_raw = row["extra_json"] or "{}"
    try:
        extra = json.loads(extra_raw)
    except json.JSONDecodeError:
        extra = {}
    return {
        "kind": row["kind"],
        "path": row["path"],
        "title": row["title"],
        "name": row["name"],
        "parent": row["parent"],
        "line_start": row["line_start"],
        "line_end": row["line_end"],
        "summary": row["summary"],
        "rank": float(row["rank"]),
        "extra": extra,
    }


def _rerank_score(row: sqlite3.Row, *, query: str, profile: str = "default") -> tuple[float, str, str, int]:
    terms = [term.lower() for term in _query_terms(query)]
    haystack_parts = [
        str(row["title"] or ""),
        str(row["name"] or ""),
        str(row["summary"] or ""),
        str(row["text"] or ""),
        str(row["path"] or ""),
    ]
    haystack = "\n".join(haystack_parts).lower()
    path = str(row["path"] or "").replace("\\", "/")
    kind = str(row["kind"] or "")
    score = float(row["rank"])

    coverage = sum(1 for term in terms if term in haystack)
    score -= coverage * 0.35

    title_name = f"{row['title']} {row['name']}".lower()
    score -= sum(0.75 for term in terms if term in title_name)

    if kind == "route":
        score -= 0.35
    elif kind == "symbol":
        score -= 0.25
    elif kind == "test":
        score -= 0.20
    elif kind == "topic":
        score -= 0.15

    score += _profile_adjustment(profile=profile, kind=kind, path=path)

    if _is_context_index_path(path) and not _is_context_index_query(terms):
        score += 8.0
    elif _is_context_index_path(path):
        score -= 1.0

    if path.startswith("scripts/") and not _is_context_index_query(terms):
        score += 3.0

    if path.startswith("scripts/test_") and not _is_context_index_query(terms):
        score += 6.0

    return (score, kind, path, int(row["line_start"] or 0))


def _profile_adjustment(*, profile: str, kind: str, path: str) -> float:
    normalized = path.replace("\\", "/").lower()
    if profile == "route":
        return -6.0 if kind == "route" else 0.8
    if profile == "test":
        return -6.0 if kind == "test" else 0.6
    if profile == "contract":
        contract_markers = (
            "architecture_boundaries",
            "protocol",
            "contract",
            "security",
            "observer",
            "modules_api",
        )
        if kind == "doc" and any(marker in normalized for marker in contract_markers):
            return -4.5
        if kind == "test":
            return 6.0
        return -1.5 if any(marker in normalized for marker in contract_markers) else 0.4
    if profile == "debug":
        debug_markers = ("tests/", "codemap", "observer", "logs", "diagnostics", "runtime")
        return -1.5 if kind == "test" or any(marker in normalized for marker in debug_markers) else 0.2
    if profile == "web":
        web_markers = ("webapp/", "admin", "static", "routes.py", "templates")
        return -2.0 if any(marker in normalized for marker in web_markers) else 0.3
    return 0.0


def _is_context_index_query(terms: Sequence[str]) -> bool:
    markers = {
        "context",
        "context_index",
        "index",
        "retrieval",
        "rag",
        "fts",
        "sqlite",
        "индекс",
        "индексация",
        "раг",
        "retrieval",
    }
    return any(term.lower() in markers or "index" in term.lower() for term in terms)


def _is_context_index_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return normalized in {
        "docs/CONTEXT_INDEX.md",
        "scripts/context_index.py",
        "scripts/build_context_index.py",
        "scripts/search_context_index.py",
        "scripts/test_context_index.py",
    }


def render_search_results(results: Sequence[dict[str, Any]], *, json_output: bool = False) -> str:
    if json_output:
        return json.dumps({"results": list(results)}, ensure_ascii=False, indent=2)
    if not results:
        return "No context index results."

    lines: list[str] = []
    for index, item in enumerate(results, start=1):
        location = item["path"]
        if item["line_start"]:
            location = f"{location}:{item['line_start']}"
        label = item["name"] or item["title"] or item["path"]
        handler = (item.get("extra") or {}).get("handler")
        if handler:
            label = f"{label} -> {handler}"
        lines.append(f"{index}. [{item['kind']}] {label} — {location}")
        if item.get("summary"):
            lines.append(f"   {item['summary']}")
    return "\n".join(lines)
