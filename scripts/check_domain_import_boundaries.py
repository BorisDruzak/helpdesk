#!/usr/bin/env python3
"""Reject selected Helpdesk imports of local external-domain implementations."""

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
FORBIDDEN_KNOWLEDGE_MODELS = frozenset(
    {
        "KnowledgeSpace",
        "KnowledgeItem",
        "KnowledgeItemVersion",
        "KnowledgeChunk",
        "KnowledgeBinding",
        "KnowledgeAudienceRule",
        "KnowledgeTaxonomyTerm",
        "KnowledgePropertyDefinition",
        "KnowledgeItemPropertyValue",
        "KnowledgeItemTaxonomyTerm",
        "KnowledgeApplicabilityRule",
        "KnowledgeQualityModel",
        "KnowledgeNode",
        "KnowledgeEdge",
        "KnowledgeGraphLayout",
        "KnowledgeAiProposal",
        "KnowledgeEntityMention",
        "KnowledgeFeedbackEvent",
        "KnowledgeArticleView",
        "KnowledgeUserBookmark",
        "KnowledgeCorrectionRequest",
        "KnowledgeArticleSubscription",
        "KnowledgeArticleEditorEvent",
        "KnowledgeVersionDiffCache",
        "KnowledgeIngestionJob",
        "TicketKnowledgeLink",
        "KnowledgeContentPack",
        "KnowledgeContentPackItem",
        "KnowledgeRolloutPolicy",
        "KnowledgeReviewTask",
        "KnowledgeReviewComment",
        "KnowledgeQualitySnapshot",
        "KnowledgeGapFinding",
        "KnowledgeSearchEvent",
        "KnowledgeSearchSettings",
        "KnowledgeChunkEmbedding",
        "KnowledgeIndexJob",
    }
)
REGISTRY_MODULE = "registry"
REGISTRY_REPOSITORIES = frozenset(
    {
        "app.repos.registration_repo",
        "app.repos.registry_repo",
    }
)
REGISTRY_REPOSITORY_EXPORTS = frozenset({"RegistrationRepo", "RegistryRepo"})
# A parent package is as capable of reaching local Registry persistence as
# its child modules, so protect it at import time instead of attempting
# alias-use dataflow analysis.
REGISTRY_BROAD_MODULES = frozenset({"app.db", "app.db.models", "app.repos"})
FORBIDDEN_REGISTRY_MODELS = frozenset(
    {
        "RegistryDepartment",
        "RegistryLocation",
        "RegistryAdminPolicy",
        "RegistryAdminEvent",
        "RegistryQualityIssueOverride",
        "RegistryVendor",
        "RegistryService",
        "RegistryPerson",
        "RegistryAsset",
        "RegistryPersonIdentity",
        "RegistryAudienceGroup",
        "RegistryAudienceGroupMember",
        "RegistryPersonDepartmentMembership",
        "DeviceRegistrationClaim",
        "DeviceUserBinding",
        "DeviceRegistrationEvent",
        "DeviceAccountSession",
        "DeviceAccountLoginRequest",
        "DeviceAccountEvent",
        "DeviceBrowserPairing",
    }
)
REGISTRY_SCOPE_TARGETS = {
    "requester": frozenset({"server/requester/identity_service.py"}),
    "tickets": frozenset(
        {
            "server/tickets/create_flow.py",
            "server/tickets/ticket_context.py",
        }
    ),
    "customer_history": frozenset({"server/customer_history/sources.py"}),
    "inventory": frozenset({"server/inventory/service.py"}),
    "web_api": frozenset(
        {
            "server/web_api/requester_handlers.py",
            "server/web_api/support_handlers.py",
        }
    ),
}
REGISTRY_SCOPE_PREFIXES = {
    # New ticket modules are guarded immediately. Existing unmigrated ticket
    # consumers must be named in the allowance ledger below.
    "tickets": ("server/tickets/",),
}

# These exact imports are known, reviewable debt for operations not represented
# by the current RegistryPort. The scoped guard rejects every other local
# Registry import in the migrated modules, including additions to these files.
REGISTRY_IMPORT_ALLOWANCES = {
    "server/requester/identity_service.py": frozenset(
        {
            ("app.db.models", "DeviceAccountSession"),
            ("app.db.models", "DeviceRegistrationClaim"),
            ("app.db.models", "DeviceUserBinding"),
            ("app.db.models", "RegistryAsset"),
            ("app.db.models", "RegistryPerson"),
            ("app.db.models", "RegistryPersonIdentity"),
            ("app.repos.registration_repo", "RegistrationRepo"),
            ("app.repos.registration_repo", "is_person_active"),
            ("app.repos.registration_repo", "normalize_identifier"),
            ("app.repos.registry_repo", "RegistryRepo"),
            ("registry.primary_agent_resolver", "PrimaryAgentResolver"),
            ("registry.profile_schema_service", "RequesterProfileSchemaService"),
        }
    ),
    "server/tickets/create_flow.py": frozenset(
        {
            # Exact binding revalidation preserves Task 2 shared-user/session
            # scope until RegistryPort exposes a binding-specific operation.
            ("app.repos.registration_repo", "RegistrationRepo"),
            ("registry.account_session_service", "AccountSessionService"),
            ("registry.service", "RegistryIngestionService"),
        }
    ),
    "server/tickets/account_access_service.py": frozenset(
        {
            ("registry.account_session_service", "AccountSessionService"),
        }
    ),
    "server/tickets/ticket_context.py": frozenset(
        {
            ("app.db.models", "RegistryPerson"),
            ("registry.primary_agent_resolver", "PrimaryAgentResolver"),
        }
    ),
    "server/web_api/requester_handlers.py": frozenset(
        {
            ("app.db.models", "RegistryDepartment"),
            ("app.db.models", "RegistryLocation"),
            ("app.db.models", "RegistryPerson"),
            ("registry.primary_agent_resolver", "PrimaryAgentResolver"),
            ("registry.profile_schema_service", "RequesterProfileSchemaService"),
        }
    ),
}


@dataclass(frozen=True)
class ImportViolation:
    path: Path
    line: int
    imported: str


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument(
        "--registry-scope",
        default="",
        help=(
            "comma-separated incremental Registry guard scopes: "
            + ",".join(REGISTRY_SCOPE_TARGETS)
        ),
    )
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


def _is_registry_module(module: str) -> bool:
    return module == REGISTRY_MODULE or module.startswith(f"{REGISTRY_MODULE}.")


def _is_registry_repository(module: str) -> bool:
    return any(module == root or module.startswith(f"{root}.") for root in REGISTRY_REPOSITORIES)


def _registry_scopes(raw: str) -> frozenset[str]:
    scopes = frozenset(item.strip() for item in str(raw or "").split(",") if item.strip())
    unknown = sorted(scopes.difference(REGISTRY_SCOPE_TARGETS))
    if unknown:
        raise ValueError(f"unknown Registry scope(s): {', '.join(unknown)}")
    return scopes


def _registry_guard_applies(path: Path, workspace: Path, scopes: frozenset[str]) -> bool:
    if not scopes:
        return False
    relative = path.relative_to(workspace).as_posix()
    return any(
        relative in REGISTRY_SCOPE_TARGETS[scope]
        or any(relative.startswith(prefix) for prefix in REGISTRY_SCOPE_PREFIXES.get(scope, ()))
        for scope in scopes
    )


def _registry_import_allowed(
    path: Path,
    workspace: Path,
    *,
    module: str,
    name: str,
) -> bool:
    relative = path.relative_to(workspace).as_posix()
    return (module, name) in REGISTRY_IMPORT_ALLOWANCES.get(relative, frozenset())


def _format_import_from(module: str, names: list[ast.alias]) -> str:
    imported = ", ".join(
        alias.name if alias.asname is None else f"{alias.name} as {alias.asname}" for alias in names
    )
    return f"from {module} import {imported}"


def _importing_package(path: Path, workspace: Path) -> tuple[str, ...]:
    relative = path.relative_to(workspace / SERVER_ROOT).with_suffix("")
    return tuple(relative.parts[:-1])


def _resolved_import_module(node: ast.ImportFrom, path: Path, workspace: Path) -> str | None:
    if node.level == 0:
        return node.module

    package = _importing_package(path, workspace)
    parent_levels = node.level - 1
    if parent_levels > len(package):
        return None
    base = package[: len(package) - parent_levels]
    suffix = tuple(node.module.split(".")) if node.module else ()
    return ".".join((*base, *suffix))


def _forbidden_from_import_names(module: str, names: list[ast.alias]) -> list[ast.alias]:
    if _is_knowledge_module(module) or _is_knowledge_repository(module):
        return names
    return [
        alias
        for alias in names
        if _is_knowledge_module(f"{module}.{alias.name}")
        or _is_knowledge_repository(f"{module}.{alias.name}")
    ]


def _find_file_violations(
    path: Path,
    workspace: Path,
    *,
    registry_scopes: frozenset[str] = frozenset(),
) -> list[ImportViolation]:
    if _is_historical_migration(path, workspace):
        return []

    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    violations: list[ImportViolation] = []
    registry_guard = _registry_guard_applies(path, workspace, registry_scopes)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_knowledge_module(alias.name) or _is_knowledge_repository(alias.name):
                    imported = alias.name if alias.asname is None else f"{alias.name} as {alias.asname}"
                    violations.append(ImportViolation(path, node.lineno, f"import {imported}"))
                if (
                    registry_guard
                    and (
                        _is_registry_module(alias.name)
                        or _is_registry_repository(alias.name)
                        or alias.name in REGISTRY_BROAD_MODULES
                    )
                    and not _registry_import_allowed(
                        path,
                        workspace,
                        module=alias.name,
                        name="*",
                    )
                ):
                    imported = alias.name if alias.asname is None else f"{alias.name} as {alias.asname}"
                    violations.append(ImportViolation(path, node.lineno, f"import {imported}"))
            continue

        if not isinstance(node, ast.ImportFrom):
            continue
        module = _resolved_import_module(node, path, workspace)
        if module is None:
            continue
        forbidden_names = _forbidden_from_import_names(module, node.names)
        if forbidden_names:
            violations.append(ImportViolation(path, node.lineno, _format_import_from(module, forbidden_names)))
        if module == KNOWLEDGE_MODELS_MODULE:
            knowledge_models = [
                alias
                for alias in node.names
                if alias.name == "*" or alias.name in FORBIDDEN_KNOWLEDGE_MODELS
            ]
            if knowledge_models:
                violations.append(
                    ImportViolation(path, node.lineno, _format_import_from(module, knowledge_models))
                )
        if not registry_guard:
            continue

        registry_names: list[ast.alias] = []
        if _is_registry_module(module) or _is_registry_repository(module):
            registry_names = [
                alias
                for alias in node.names
                if not _registry_import_allowed(
                    path,
                    workspace,
                    module=module,
                    name=alias.name,
                )
            ]
        elif module == "app.repos":
            registry_names = [
                alias
                for alias in node.names
                if alias.name in REGISTRY_REPOSITORY_EXPORTS
                and not _registry_import_allowed(
                    path,
                    workspace,
                    module=module,
                    name=alias.name,
                )
            ]
        elif module == KNOWLEDGE_MODELS_MODULE:
            registry_names = [
                alias
                for alias in node.names
                if (alias.name == "*" or alias.name in FORBIDDEN_REGISTRY_MODELS)
                and not _registry_import_allowed(
                    path,
                    workspace,
                    module=module,
                    name=alias.name,
                )
            ]
        else:
            registry_names = [
                alias
                for alias in node.names
                if (
                    _is_registry_module(f"{module}.{alias.name}")
                    or _is_registry_repository(f"{module}.{alias.name}")
                    or f"{module}.{alias.name}" in REGISTRY_BROAD_MODULES
                )
                and not _registry_import_allowed(
                    path,
                    workspace,
                    module=f"{module}.{alias.name}",
                    name="*",
                )
            ]
        if registry_names:
            violations.append(
                ImportViolation(path, node.lineno, _format_import_from(module, registry_names))
            )
    return violations


def find_forbidden_imports(
    workspace: Path,
    *,
    registry_scopes: frozenset[str] = frozenset(),
) -> list[ImportViolation]:
    workspace = workspace.resolve()
    server_root = workspace / SERVER_ROOT
    if not server_root.exists():
        return []

    violations: list[ImportViolation] = []
    for path in sorted(server_root.rglob("*.py")):
        if path.is_relative_to(server_root / "tests"):
            continue
        violations.extend(
            _find_file_violations(path, workspace, registry_scopes=registry_scopes)
        )
    return violations


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    workspace = args.workspace.resolve()
    try:
        registry_scopes = _registry_scopes(args.registry_scope)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    violations = find_forbidden_imports(workspace, registry_scopes=registry_scopes)
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
