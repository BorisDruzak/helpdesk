#!/usr/bin/env python3
"""Load the canonical CI/test-suite catalog."""

from __future__ import annotations

import fnmatch
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CATALOG_PATH = REPO_ROOT / "quality" / "test_suites.toml"


@dataclass(frozen=True)
class SuiteDefinition:
    name: str
    runner: str
    command: tuple[str, ...]
    paths: tuple[str, ...]
    marker_expression: str | None
    junit: str | None
    database: str | None
    description: str
    affected_base: bool
    server_db_api_patterns: tuple[str, ...]
    server_db_api_catch_all: bool
    server_source_prefixes: tuple[str, ...]
    parallel_group: str | None
    parallel_order: int | None


@dataclass(frozen=True)
class SuiteCatalog:
    path: Path
    suites: tuple[SuiteDefinition, ...]

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(suite.name for suite in self.suites)

    @property
    def server_db_api_layer_rules(self) -> tuple[tuple[str, tuple[str, ...]], ...]:
        return tuple(
            (suite.name, suite.server_db_api_patterns)
            for suite in self.suites
            if suite.server_db_api_patterns
        )

    @property
    def server_db_api_catch_all_layer(self) -> str:
        for suite in self.suites:
            if suite.server_db_api_catch_all:
                return suite.name
        return "server_pytest_db_web_api"

    @property
    def server_db_domain_layers(self) -> tuple[str, ...]:
        names = [name for name, _patterns in self.server_db_api_layer_rules]
        catch_all = self.server_db_api_catch_all_layer
        if catch_all not in names:
            names.append(catch_all)
        return tuple(names)

    @property
    def server_source_layer_rules(self) -> tuple[tuple[str, tuple[str, ...]], ...]:
        return tuple(
            (suite.name, suite.server_source_prefixes)
            for suite in self.suites
            if suite.server_source_prefixes
        )

    @property
    def affected_base_layers(self) -> tuple[str, ...]:
        return tuple(suite.name for suite in self.suites if suite.affected_base)

    def parallel_layer_order(self, group: str) -> tuple[str, ...]:
        candidates = [
            (suite.parallel_order if suite.parallel_order is not None else index, suite.name)
            for index, suite in enumerate(self.suites)
            if suite.parallel_group == group
        ]
        return tuple(name for _order, name in sorted(candidates))

    def classify_server_db_api_test_file(self, filename: str, *, migration_schema_name: str) -> str:
        if filename == migration_schema_name:
            return "migration_schema"
        for layer_name, patterns in self.server_db_api_layer_rules:
            if any(fnmatch.fnmatch(filename, pattern) for pattern in patterns):
                return layer_name
        return self.server_db_api_catch_all_layer


def catalog_path_for_workspace(workspace: Path | None = None) -> Path:
    if workspace is not None:
        candidate = workspace / "quality" / "test_suites.toml"
        if candidate.exists():
            return candidate
    return DEFAULT_CATALOG_PATH


def _tuple_of_strings(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError("expected a list of strings")
    return tuple(value)


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("expected a string")
    return value


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int):
        raise ValueError("expected an integer")
    return value


def _suite_from_table(table: dict[str, object]) -> SuiteDefinition:
    name = table.get("name")
    runner = table.get("runner")
    if not isinstance(name, str) or not name:
        raise ValueError("suite name is required")
    if not isinstance(runner, str) or not runner:
        raise ValueError(f"{name}: runner is required")
    return SuiteDefinition(
        name=name,
        runner=runner,
        command=_tuple_of_strings(table.get("command")),
        paths=_tuple_of_strings(table.get("paths")),
        marker_expression=_optional_string(table.get("marker_expression")),
        junit=_optional_string(table.get("junit")),
        database=_optional_string(table.get("database")),
        description=_optional_string(table.get("description")) or "",
        affected_base=bool(table.get("affected_base", False)),
        server_db_api_patterns=_tuple_of_strings(table.get("server_db_api_patterns")),
        server_db_api_catch_all=bool(table.get("server_db_api_catch_all", False)),
        server_source_prefixes=_tuple_of_strings(table.get("server_source_prefixes")),
        parallel_group=_optional_string(table.get("parallel_group")),
        parallel_order=_optional_int(table.get("parallel_order")),
    )


def load_suite_catalog(workspace: Path | None = None, *, path: Path | None = None) -> SuiteCatalog:
    catalog_path = path or catalog_path_for_workspace(workspace)
    payload = tomllib.loads(catalog_path.read_text(encoding="utf-8-sig"))
    raw_suites = payload.get("suites")
    if not isinstance(raw_suites, list):
        raise ValueError(f"{catalog_path}: [[suites]] is required")
    suites = tuple(_suite_from_table(table) for table in raw_suites if isinstance(table, dict))
    names = [suite.name for suite in suites]
    duplicate_names = sorted(name for name in set(names) if names.count(name) > 1)
    if duplicate_names:
        raise ValueError(f"{catalog_path}: duplicate suite names: {', '.join(duplicate_names)}")
    return SuiteCatalog(path=catalog_path, suites=suites)


def require_catalog_layers(available_layers: Iterable[str], *, workspace: Path) -> None:
    catalog = load_suite_catalog(workspace)
    available = tuple(available_layers)
    expected = catalog.names
    extra = [name for name in available if name not in expected]
    expected_available_order = tuple(name for name in expected if name in available)
    if extra or available != expected_available_order:
        details = []
        if extra:
            details.append(f"missing from catalog: {', '.join(extra)}")
        if not extra:
            details.append("runner order differs from quality/test_suites.toml")
        raise ValueError("CI suite catalog drift: " + "; ".join(details))
