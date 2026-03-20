#!/usr/bin/env python3
"""Shared navigation metadata for pc_client docs and helper scripts."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
QUICK_LOOKUP_PATH = Path("docs/QUICK_LOOKUP.md")
SERVER_CODEMAP_PATH = Path("server/docs/CODEMAP.md")
AGENT_CODEMAP_PATH = Path("pc_agent/docs/CODEMAP.md")


@dataclass(frozen=True)
class Topic:
    key: str
    title: str
    summary: str
    aliases: tuple[str, ...]
    first_files: tuple[str, ...]
    related_docs: tuple[str, ...]
    suggested_commands: tuple[str, ...]
    path_prefixes: tuple[str, ...] = ()
    exact_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class DriftRule:
    key: str
    title: str
    reason: str
    required_docs: tuple[str, ...]
    path_prefixes: tuple[str, ...] = ()
    exact_paths: tuple[str, ...] = ()
    statuses: tuple[str, ...] = ("A", "D", "M", "R")


@dataclass(frozen=True)
class ChangedPath:
    status: str
    path: str
    old_path: str | None = None


TOPICS: tuple[Topic, ...] = (
    Topic(
        key="protocol_v3",
        title="Protocol V3 / handshake",
        summary="WS handshake, capabilities, envelope V3, ACK/NACK and command_result.",
        aliases=(
            "protocol",
            "protocol v3",
            "ws_ticket_v3",
            "handshake",
            "capabilities",
            "outbox_ack",
            "outbox_nack",
            "command_result",
            "device_seq",
            "agent_seq",
        ),
        first_files=(
            "server/websocket/agent_handshake.py",
            "server/websocket/agent_services.py",
            "pc_agent/ws_agent.py",
            "pc_agent/core/sender.py",
        ),
        related_docs=(
            "docs/QUICK_LOOKUP.md",
            "server/docs/PROTOCOL_V3.md",
            "pc_agent/docs/PROTOCOL_V3.md",
            "server/docs/COMMAND_RESULT_LIFECYCLE.md",
            "server/docs/TOOL_CALL_STARTED_INVARIANT.md",
        ),
        suggested_commands=(
            'python scripts/agent_find.py "handshake"',
            "python scripts/diff_context.py",
        ),
        path_prefixes=("server/websocket/",),
        exact_paths=(
            "pc_agent/ws_agent.py",
            "pc_agent/core/sender.py",
            "pc_agent/core/database.py",
        ),
    ),
    Topic(
        key="run_tool",
        title="run_tool / consent",
        summary="Single path for tool execution, consent approval and operation queueing.",
        aliases=(
            "run_tool",
            "tool_call_started",
            "admin_run_tool",
            "consent",
            "approve_consent",
            "send_ws_command",
        ),
        first_files=(
            "server/tools/service.py",
            "server/tools/handlers.py",
            "server/app/services/operation_service.py",
            "pc_agent/core/orchestrator.py",
        ),
        related_docs=(
            "docs/QUICK_LOOKUP.md",
            "server/docs/TOOL_CALL_STARTED_INVARIANT.md",
            "server/docs/CODEMAP.md",
            "pc_agent/docs/CODEMAP.md",
        ),
        suggested_commands=(
            'python scripts/agent_find.py "run_tool" --dir server',
            "python scripts/diff_context.py",
        ),
        path_prefixes=(
            "server/tools/",
            "server/app/services/",
        ),
        exact_paths=(
            "server/api/admin.py",
            "server/websocket/ui_handler.py",
            "pc_agent/core/orchestrator.py",
        ),
    ),
    Topic(
        key="auth",
        title="Auth / token bootstrap",
        summary="Token sources, AuthContext, connection request flow and security invariants.",
        aliases=(
            "auth",
            "token",
            "authcontext",
            "connection request",
            "connection_request",
            "rbac",
            "security",
        ),
        first_files=(
            "server/auth/",
            "server/app/repos/auth_tokens_repo.py",
            "pc_agent/auth/token_source.py",
            "pc_agent/core/identity.py",
        ),
        related_docs=(
            "docs/QUICK_LOOKUP.md",
            "server/docs/SECURITY_AND_AUTH.md",
            "pc_agent/docs/AUTHENTICATION.md",
            "server/docs/CODEMAP.md",
            "pc_agent/docs/CODEMAP.md",
        ),
        suggested_commands=(
            'python scripts/agent_find.py "auth" --dir server',
            'python scripts/agent_find.py "token" --dir pc_agent',
        ),
        path_prefixes=(
            "server/auth/",
            "pc_agent/auth/",
        ),
        exact_paths=(
            "server/app/repos/auth_tokens_repo.py",
            "pc_agent/core/identity.py",
        ),
    ),
    Topic(
        key="tickets",
        title="Tickets / chat / queue",
        summary="Ticket lifecycle, SLA, chat, public access and queue behavior.",
        aliases=(
            "ticket",
            "tickets",
            "chat",
            "queue",
            "public access",
            "requester",
            "sla",
        ),
        first_files=(
            "server/tickets/handlers.py",
            "server/tickets/workflow_service.py",
            "server/chat/",
            "server/api/events.py",
        ),
        related_docs=(
            "docs/QUICK_LOOKUP.md",
            "server/docs/TICKET_SYSTEM.md",
            "server/docs/CHAT_MESSAGE_CONTRACT.md",
            "server/docs/CODEMAP.md",
        ),
        suggested_commands=(
            'python scripts/agent_find.py "ticket" --dir server',
            'python scripts/agent_find.py "chat" --dir server',
        ),
        path_prefixes=(
            "server/tickets/",
            "server/chat/",
        ),
        exact_paths=(
            "server/api/events.py",
            "server/api/operations.py",
        ),
    ),
    Topic(
        key="modules",
        title="Modules / reconcile",
        summary="Module install, desired state, reconcile, manifest and module registry.",
        aliases=(
            "module",
            "modules",
            "reconcile",
            "desired modules",
            "manifest",
            "module install",
        ),
        first_files=(
            "server/modules/service.py",
            "server/websocket/modules_sync.py",
            "pc_agent/core/module_manager.py",
            "pc_agent/core/registry.py",
        ),
        related_docs=(
            "docs/QUICK_LOOKUP.md",
            "server/docs/MODULES_API.md",
            "server/docs/MODULES_DRIFT_AND_SNAPSHOTS.md",
            "pc_agent/docs/MODULES.md",
            "server/docs/CODEMAP.md",
            "pc_agent/docs/CODEMAP.md",
        ),
        suggested_commands=(
            'python scripts/agent_find.py "modules" --dir server',
            'python scripts/agent_find.py "module_manager" --dir pc_agent',
        ),
        path_prefixes=(
            "server/modules/",
            "pc_agent/modules/",
        ),
        exact_paths=(
            "server/websocket/modules_sync.py",
            "server/app/services/module_reconcile_scheduler.py",
            "server/utils/module_manifest.py",
            "server/utils/module_preflight.py",
            "server/utils/module_builder.py",
            "pc_agent/core/module_manager.py",
            "pc_agent/core/loader.py",
            "pc_agent/core/registry.py",
        ),
    ),
    Topic(
        key="ui_server",
        title="Server UI / admin pages",
        summary="Admin, ticket and public pages plus static route handlers.",
        aliases=(
            "admin ui",
            "admin page",
            "ticket ui",
            "public queue",
            "help page",
            "browser check",
        ),
        first_files=(
            "server/admin.js",
            "server/ticket.js",
            "server/static_pages/",
            "server/routes.py",
        ),
        related_docs=(
            "docs/QUICK_LOOKUP.md",
            "server/docs/CODEMAP.md",
        ),
        suggested_commands=(
            "python scripts/diff_context.py",
            "GUI check via MCP at http://192.168.100.17:8666/admin",
        ),
        path_prefixes=("server/static_pages/",),
        exact_paths=(
            "server/admin.html",
            "server/admin.js",
            "server/admin.css",
            "server/ticket.html",
            "server/ticket.js",
            "server/ticket.css",
            "server/public_queue.html",
            "server/public_queue.js",
            "server/help.html",
            "server/help.js",
            "server/help.css",
        ),
    ),
    Topic(
        key="ui_agent",
        title="Agent GUI / ui_bridge",
        summary="Qt GUI, SSE bridge, initiator profiles and local GUI integration.",
        aliases=(
            "gui",
            "ui bridge",
            "sse",
            "chat panel",
            "main window",
            "initiator profile",
        ),
        first_files=(
            "pc_agent/ui_gui/main_window.py",
            "pc_agent/ui_gui/chat_panel.py",
            "pc_agent/ui_bridge/api_server.py",
            "pc_agent/ui_bridge/event_bus.py",
        ),
        related_docs=(
            "docs/QUICK_LOOKUP.md",
            "pc_agent/docs/CODEMAP.md",
        ),
        suggested_commands=(
            'python scripts/agent_find.py "ui bridge" --dir pc_agent',
            "python scripts/diff_context.py",
        ),
        path_prefixes=(
            "pc_agent/ui_gui/",
            "pc_agent/ui_bridge/",
        ),
        exact_paths=("pc_agent/ui_gui/main.py",),
    ),
    Topic(
        key="database",
        title="Database / migrations",
        summary="PostgreSQL migrations on server and SQLite schema on agent.",
        aliases=(
            "database",
            "db",
            "migration",
            "alembic",
            "sqlite",
            "storage.db",
        ),
        first_files=(
            "server/app/db/models.py",
            "server/app/db/migrations/versions/",
            "pc_agent/core/database.py",
            "server/docs/DATABASE.md",
        ),
        related_docs=(
            "docs/QUICK_LOOKUP.md",
            "server/docs/DATABASE.md",
            "pc_agent/docs/DATABASE.md",
            "server/docs/CODEMAP.md",
            "pc_agent/docs/CODEMAP.md",
        ),
        suggested_commands=(
            'python scripts/agent_find.py "alembic" --dir server',
            'python scripts/agent_find.py "DB_SCHEMA_VERSION" --dir pc_agent',
        ),
        path_prefixes=("server/app/db/",),
        exact_paths=("pc_agent/core/database.py",),
    ),
    Topic(
        key="release",
        title="Release / deploy / smoke",
        summary="Local verification, deploy to Linux, smoke and browser checks.",
        aliases=(
            "release",
            "deploy",
            "smoke",
            "browser",
            "remote stack",
            "verify workspace",
        ),
        first_files=(
            "scripts/verify_workspace.py",
            "scripts/deploy_workspace_to_remote.py",
            "scripts/release_server_to_remote.py",
            "scripts/manage_remote_stack.py",
        ),
        related_docs=(
            "docs/QUICK_LOOKUP.md",
            "server/docs/CODEMAP.md",
            "pc_agent/docs/CODEMAP.md",
        ),
        suggested_commands=(
            "python scripts/verify_workspace.py",
            "python scripts/release_server_to_remote.py",
        ),
        path_prefixes=("scripts/",),
        exact_paths=(),
    ),
)


DRIFT_RULES: tuple[DriftRule, ...] = (
    DriftRule(
        key="server_entrypoints",
        title="Server entrypoints or routes changed",
        reason="Routes, startup wiring and key server entrypoints are navigation-critical.",
        exact_paths=("server/server.py", "server/routes.py", "server/config.py"),
        required_docs=("server/docs/CODEMAP.md", "docs/QUICK_LOOKUP.md"),
    ),
    DriftRule(
        key="server_protocol",
        title="Server protocol or outbox pipeline changed",
        reason="Handshake, ACK/NACK, command_result and validator logic affect protocol docs.",
        exact_paths=(
            "server/websocket/agent_handshake.py",
            "server/websocket/agent_services.py",
            "server/websocket/protocol.py",
            "server/websocket/outbox_ingest_components.py",
            "server/websocket/command_result_components.py",
            "server/websocket/validator.py",
        ),
        required_docs=(
            "server/docs/PROTOCOL_V3.md",
            "server/docs/COMMAND_RESULT_LIFECYCLE.md",
            "server/docs/TOOL_CALL_STARTED_INVARIANT.md",
            "server/docs/CODEMAP.md",
            "docs/QUICK_LOOKUP.md",
        ),
    ),
    DriftRule(
        key="agent_protocol",
        title="Agent protocol or sender changed",
        reason="Handshake, sender and outbox behavior affect Protocol V3 and sender docs.",
        exact_paths=(
            "pc_agent/ws_agent.py",
            "pc_agent/core/sender.py",
            "pc_agent/core/database.py",
            "pc_agent/core/orchestrator.py",
        ),
        required_docs=(
            "pc_agent/docs/PROTOCOL_V3.md",
            "pc_agent/docs/SENDER.md",
            "pc_agent/docs/DATABASE.md",
            "pc_agent/docs/CODEMAP.md",
            "docs/QUICK_LOOKUP.md",
        ),
    ),
    DriftRule(
        key="server_auth",
        title="Server auth flow changed",
        reason="Auth and token flow changes should stay aligned with security docs.",
        path_prefixes=("server/auth/",),
        exact_paths=("server/app/repos/auth_tokens_repo.py",),
        required_docs=(
            "server/docs/SECURITY_AND_AUTH.md",
            "server/docs/CODEMAP.md",
            "docs/QUICK_LOOKUP.md",
        ),
    ),
    DriftRule(
        key="agent_auth",
        title="Agent auth bootstrap changed",
        reason="Token bootstrap and connection-request flow should stay aligned with agent auth docs.",
        path_prefixes=("pc_agent/auth/",),
        exact_paths=("pc_agent/core/identity.py",),
        required_docs=(
            "pc_agent/docs/AUTHENTICATION.md",
            "pc_agent/docs/CODEMAP.md",
            "docs/QUICK_LOOKUP.md",
        ),
    ),
    DriftRule(
        key="modules",
        title="Module pipeline changed",
        reason="Module install, desired state and reconcile are documented in dedicated docs.",
        path_prefixes=("server/modules/", "pc_agent/modules/"),
        exact_paths=(
            "server/websocket/modules_sync.py",
            "server/app/services/module_reconcile_scheduler.py",
            "server/utils/module_manifest.py",
            "server/utils/module_preflight.py",
            "server/utils/module_builder.py",
            "pc_agent/core/module_manager.py",
            "pc_agent/core/loader.py",
            "pc_agent/core/registry.py",
        ),
        required_docs=(
            "server/docs/MODULES_API.md",
            "server/docs/MODULES_DRIFT_AND_SNAPSHOTS.md",
            "pc_agent/docs/MODULES.md",
            "server/docs/CODEMAP.md",
            "pc_agent/docs/CODEMAP.md",
            "docs/QUICK_LOOKUP.md",
        ),
    ),
    DriftRule(
        key="tickets",
        title="Ticket or chat flow changed",
        reason="Ticket lifecycle and chat contracts should stay discoverable in docs.",
        path_prefixes=("server/tickets/", "server/chat/"),
        exact_paths=("server/api/events.py", "server/api/operations.py"),
        required_docs=(
            "server/docs/TICKET_SYSTEM.md",
            "server/docs/CHAT_MESSAGE_CONTRACT.md",
            "server/docs/CODEMAP.md",
            "docs/QUICK_LOOKUP.md",
        ),
    ),
    DriftRule(
        key="server_ui_structure",
        title="Server UI structure changed",
        reason="Added, removed or renamed page files should stay visible in navigation docs.",
        path_prefixes=("server/static_pages/",),
        exact_paths=(
            "server/admin.html",
            "server/admin.js",
            "server/admin.css",
            "server/ticket.html",
            "server/ticket.js",
            "server/ticket.css",
            "server/public_queue.html",
            "server/public_queue.js",
            "server/help.html",
            "server/help.js",
            "server/help.css",
        ),
        statuses=("A", "D", "R"),
        required_docs=("server/docs/CODEMAP.md", "docs/QUICK_LOOKUP.md"),
    ),
    DriftRule(
        key="agent_gui_structure",
        title="Agent GUI structure changed",
        reason="Added, removed or renamed GUI files should stay reflected in navigation docs.",
        path_prefixes=("pc_agent/ui_gui/", "pc_agent/ui_bridge/"),
        exact_paths=("pc_agent/ui_gui/main.py",),
        statuses=("A", "D", "R"),
        required_docs=("pc_agent/docs/CODEMAP.md", "docs/QUICK_LOOKUP.md"),
    ),
)


def repo_path(value: str | Path) -> str:
    return str(value).replace("\\", "/").strip("/")


def path_matches(path: str, *, exact_paths: Sequence[str], path_prefixes: Sequence[str]) -> bool:
    normalized = repo_path(path)
    exact_set = {repo_path(item) for item in exact_paths}
    if normalized in exact_set:
        return True
    return any(normalized.startswith(repo_path(prefix)) for prefix in path_prefixes)


def score_topic_for_query(topic: Topic, query: str) -> int:
    normalized_query = " ".join(query.lower().split())
    if not normalized_query:
        return 0
    score = 0
    for alias in topic.aliases:
        normalized_alias = " ".join(alias.lower().split())
        if normalized_query == normalized_alias:
            score = max(score, 500 + len(normalized_alias))
        elif normalized_alias in normalized_query:
            score = max(score, 250 + len(normalized_alias))
        elif normalized_query in normalized_alias:
            score = max(score, 150 + len(normalized_query))
    return score


def find_topics_for_query(query: str, *, limit: int = 5) -> list[Topic]:
    ranked: list[tuple[int, Topic]] = []
    for topic in TOPICS:
        score = score_topic_for_query(topic, query)
        if score:
            ranked.append((score, topic))
    ranked.sort(key=lambda item: (-item[0], item[1].title))
    return [topic for _, topic in ranked[:limit]]


def find_topics_for_paths(paths: Sequence[str], *, limit: int = 6) -> list[Topic]:
    scores: dict[str, int] = {}
    for topic in TOPICS:
        matched = 0
        for path in paths:
            if path_matches(path, exact_paths=topic.exact_paths, path_prefixes=topic.path_prefixes):
                matched += 1
        if matched:
            scores[topic.key] = matched
    ranked = sorted(
        ((score, topic) for topic in TOPICS if topic.key in scores for score in [scores[topic.key]]),
        key=lambda item: (-item[0], item[1].title),
    )
    return [topic for _, topic in ranked[:limit]]


def collect_related_docs(topics: Sequence[Topic]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for topic in topics:
        for path in topic.related_docs:
            normalized = repo_path(path)
            if normalized in seen:
                continue
            seen.add(normalized)
            ordered.append(normalized)
    return ordered


def collect_first_files(topics: Sequence[Topic]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for topic in topics:
        for path in topic.first_files:
            normalized = repo_path(path)
            if normalized in seen:
                continue
            seen.add(normalized)
            ordered.append(normalized)
    return ordered


def is_server_ui_path(path: str) -> bool:
    normalized = repo_path(path)
    if normalized.startswith("server/static_pages/"):
        return True
    return normalized in {
        "server/admin.html",
        "server/admin.js",
        "server/admin.css",
        "server/ticket.html",
        "server/ticket.js",
        "server/ticket.css",
        "server/public_queue.html",
        "server/public_queue.js",
        "server/help.html",
        "server/help.js",
        "server/help.css",
    }


def recommend_checks(paths: Sequence[str]) -> list[str]:
    normalized = [repo_path(path) for path in paths]
    checks: list[str] = ["python scripts/verify_workspace.py"]
    if any(path.startswith("server/") for path in normalized):
        checks.append("python -m pytest server/tests/ ...")
    if any(path.startswith("pc_agent/") for path in normalized):
        checks.append("python -m pytest pc_agent/tests/ ...")
    if any(is_server_ui_path(path) for path in normalized):
        checks.append("GUI check via MCP at http://192.168.100.17:8666/admin")
    return checks


def _run_git(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _parse_name_status(output: str) -> list[ChangedPath]:
    changes: list[ChangedPath] = []
    for raw_line in output.splitlines():
        if not raw_line.strip():
            continue
        parts = raw_line.split("\t")
        status = parts[0].strip()
        if status.startswith("R") and len(parts) >= 3:
            changes.append(ChangedPath(status="R", old_path=repo_path(parts[1]), path=repo_path(parts[2])))
        elif len(parts) >= 2:
            changes.append(ChangedPath(status=status[:1], path=repo_path(parts[1])))
    return changes


def collect_changed_paths(
    *,
    base: str | None = None,
    staged: bool = False,
    pathspecs: Sequence[str] | None = None,
) -> list[ChangedPath]:
    pathspec_list = [repo_path(item) for item in (pathspecs or ())]
    diff_cmd = ["git", "diff", "--name-status", "--find-renames", "--relative"]
    if staged:
        diff_cmd.append("--cached")
    if base:
        diff_cmd.append(f"{base}...HEAD")
    elif not staged:
        diff_cmd.append("HEAD")
    if pathspec_list:
        diff_cmd.append("--")
        diff_cmd.extend(pathspec_list)

    diff_result = _run_git(diff_cmd)
    if diff_result.returncode != 0:
        raise RuntimeError(diff_result.stderr.strip() or "git diff failed")

    changes = _parse_name_status(diff_result.stdout)

    if not base and not staged:
        untracked_cmd = ["git", "ls-files", "--others", "--exclude-standard"]
        if pathspec_list:
            untracked_cmd.append("--")
            untracked_cmd.extend(pathspec_list)
        untracked_result = _run_git(untracked_cmd)
        if untracked_result.returncode != 0:
            raise RuntimeError(untracked_result.stderr.strip() or "git ls-files failed")
        for line in untracked_result.stdout.splitlines():
            if line.strip():
                changes.append(ChangedPath(status="A", path=repo_path(line)))

    dedup: dict[tuple[str, str, str | None], ChangedPath] = {}
    for change in changes:
        dedup[(change.status, change.path, change.old_path)] = change
    return list(dedup.values())


def iter_triggered_drift_rules(changes: Iterable[ChangedPath]) -> list[tuple[DriftRule, list[ChangedPath]]]:
    grouped: list[tuple[DriftRule, list[ChangedPath]]] = []
    for rule in DRIFT_RULES:
        matched: list[ChangedPath] = []
        for change in changes:
            if change.status not in rule.statuses:
                continue
            if path_matches(change.path, exact_paths=rule.exact_paths, path_prefixes=rule.path_prefixes):
                matched.append(change)
        if matched:
            grouped.append((rule, matched))
    return grouped
