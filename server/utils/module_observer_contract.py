"""
Observer contract validation for BaseCollector modules.
"""

from __future__ import annotations

import ast
import io
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, List


CANONICAL_WORKSPACE_MODULE_ROOTS = (
    Path("pc_agent/modules/impl"),
    Path("pc_agent/modules_packages"),
)
_BASE_COLLECTOR_IMPORT_SUFFIXES = {
    "modules.base_module",
    "pc_agent.modules.base_module",
}


def _decorator_base_name(decorator: ast.AST) -> str:
    target = decorator.func if isinstance(decorator, ast.Call) else decorator
    if isinstance(target, ast.Name):
        return target.id
    if isinstance(target, ast.Attribute):
        return target.attr
    return ""


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _literal_or_none(node: ast.AST) -> Any:
    try:
        return ast.literal_eval(node)
    except Exception:
        return None


def _base_collector_aliases(tree: ast.AST) -> set[str]:
    aliases = {"BaseCollector"}
    for node in getattr(tree, "body", []):
        if isinstance(node, ast.ImportFrom) and node.module in _BASE_COLLECTOR_IMPORT_SUFFIXES:
            for alias in node.names:
                if alias.name == "BaseCollector":
                    aliases.add(alias.asname or alias.name)
    return aliases


class _ToolEntryDetector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.found = False

    def visit_With(self, node: ast.With) -> None:  # noqa: N802
        self._check_items(node.items)
        if not self.found:
            self.generic_visit(node)

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:  # noqa: N802
        self._check_items(node.items)
        if not self.found:
            self.generic_visit(node)

    def _check_items(self, items: Iterable[ast.withitem]) -> None:
        for item in items:
            if self._is_tool_entry_trace_span(item.context_expr):
                self.found = True
                return

    @staticmethod
    def _is_tool_entry_trace_span(node: ast.AST) -> bool:
        if not isinstance(node, ast.Call):
            return False
        if _call_name(node.func) != "trace_span":
            return False
        if not node.args:
            return False
        return _literal_or_none(node.args[0]) == "tool.entry"


class _ExposedToolCollector(ast.NodeVisitor):
    def __init__(self, *, source_path: str, base_collector_aliases: set[str]) -> None:
        self.source_path = source_path
        self.base_collector_aliases = base_collector_aliases
        self.class_bases: dict[str, list[str]] = {}
        self.class_stack: list[str] = []
        self.errors: list[str] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
        self.class_bases[node.name] = [self._base_name(base) for base in node.bases]
        self.class_stack.append(node.name)
        self.generic_visit(node)
        self.class_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        self._check_function(node)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        self._check_function(node)
        self.generic_visit(node)

    def _check_function(self, node: ast.AsyncFunctionDef | ast.FunctionDef) -> None:
        exposed_decorator = None
        for decorator in node.decorator_list:
            if _decorator_base_name(decorator) == "exposed_tool" and isinstance(decorator, ast.Call):
                exposed_decorator = decorator
                break
        if exposed_decorator is None:
            return

        tool_name = node.name
        for keyword in exposed_decorator.keywords:
            if keyword.arg == "name":
                literal = _literal_or_none(keyword.value)
                if isinstance(literal, str) and literal.strip():
                    tool_name = literal.strip()
                break

        if not self.class_stack:
            self.errors.append(
                f"{self.source_path}:{node.lineno} tool '{tool_name}' must be declared inside a BaseCollector subclass"
            )
            return

        class_name = self.class_stack[-1]
        if not self._inherits_base_collector(class_name, set()):
            self.errors.append(
                f"{self.source_path}:{node.lineno} tool '{tool_name}' is declared on '{class_name}', "
                "which does not inherit BaseCollector"
            )
            return

        detector = _ToolEntryDetector()
        detector.visit(node)
        if detector.found:
            return
        self.errors.append(
            f"{self.source_path}:{node.lineno} tool '{tool_name}' in {class_name}.{node.name} "
            "must wrap execution with self.trace_span(\"tool.entry\", ...)"
        )

    def _inherits_base_collector(self, class_name: str, seen: set[str]) -> bool:
        if class_name in seen:
            return False
        seen.add(class_name)
        for base_name in self.class_bases.get(class_name, []):
            if base_name in self.base_collector_aliases or base_name == "BaseCollector":
                return True
            if base_name in self.class_bases and self._inherits_base_collector(base_name, seen):
                return True
        return False

    @staticmethod
    def _base_name(base: ast.expr) -> str:
        if isinstance(base, ast.Name):
            return base.id
        if isinstance(base, ast.Attribute):
            return base.attr
        return ""


def validate_observer_contract_sources(sources: Dict[str, str]) -> List[str]:
    errors: List[str] = []
    for source_path, source_text in sorted(sources.items()):
        if not source_path.endswith(".py"):
            continue
        try:
            tree = ast.parse(source_text)
        except SyntaxError as exc:
            errors.append(f"{source_path}:{exc.lineno} syntax error while validating observer contract: {exc.msg}")
            continue
        collector = _ExposedToolCollector(
            source_path=source_path,
            base_collector_aliases=_base_collector_aliases(tree),
        )
        collector.visit(tree)
        errors.extend(collector.errors)
    return errors


def validate_observer_contract_zip(zip_bytes: bytes) -> List[str]:
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            sources: Dict[str, str] = {}
            for info in zf.infolist():
                if info.is_dir() or not info.filename.endswith(".py"):
                    continue
                try:
                    sources[info.filename] = zf.read(info.filename).decode("utf-8")
                except UnicodeDecodeError as exc:
                    return [f"{info.filename}: module source must be UTF-8 ({exc})"]
    except zipfile.BadZipFile as exc:
        return [f"archive validation failed: {exc}"]
    return validate_observer_contract_sources(sources)


def scan_workspace_module_observer_failures(workspace: Path) -> List[str]:
    sources: Dict[str, str] = {}
    for root in CANONICAL_WORKSPACE_MODULE_ROOTS:
        absolute_root = workspace / root
        if not absolute_root.exists():
            continue
        for path in absolute_root.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            relative = path.relative_to(workspace)
            sources[str(relative)] = path.read_text(encoding="utf-8")
    return validate_observer_contract_sources(sources)
