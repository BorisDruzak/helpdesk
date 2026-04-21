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
PLANS_PATH = Path("PLANS.md")
CODEX_CONFIG_PATH = Path(".codex/config.toml")
TASK_INTAKE_PATH = Path("scripts/task_intake.py")

SUBAGENTS_PLAYBOOK_PATH = Path(".cursor/rules/subagents-pc-client.mdc")
NAVIGATION_PLAYBOOK_PATH = Path(".cursor/rules/navigation-tools.mdc")
RELEASE_PLAYBOOK_PATH = Path(".cursor/rules/release-pc-client.mdc")
AGENT_UPDATES_PLAYBOOK_PATH = Path(".cursor/rules/agent-updates-pc-client.mdc")
AGENT_RUNTIME_PLAYBOOK_PATH = Path(".cursor/rules/agent-runtime-pc-client.mdc")

DOCS_SYNC_SKILL_PATH = Path(".cursor/skills/pc-client-docs-sync/SKILL.md")
MIGRATIONS_SKILL_PATH = Path(".cursor/skills/pc-client-migrations/SKILL.md")
PLANS_SKILL_PATH = Path(".cursor/skills/pc-client-plans/SKILL.md")
RELEASE_SKILL_PATH = Path(".cursor/skills/pc-client-release/SKILL.md")
TESTS_SKILL_PATH = Path(".cursor/skills/pc-client-tests/SKILL.md")
BROWSER_CHECK_SKILL_PATH = Path(".cursor/skills/pc-client-browser-check/SKILL.md")
AGENT_UPDATES_SKILL_PATH = Path(".cursor/skills/pc-client-agent-updates/SKILL.md")
AGENT_RUNTIME_SKILL_PATH = Path(".cursor/skills/pc-client-agent-runtime/SKILL.md")
OBSERVER_DIAGNOSTICS_SKILL_PATH = Path(".cursor/skills/pc-client-observer-diagnostics/SKILL.md")


def repo_path(value: str | Path) -> str:
    return str(value).replace("\\", "/").strip("/")


@dataclass(frozen=True)
class Topic:
    key: str
    title: str
    summary: str
    aliases: tuple[str, ...]
    first_files: tuple[str, ...]
    related_docs: tuple[str, ...]
    suggested_commands: tuple[str, ...]
    mode: str | None = None
    playbook: str | None = None
    skills: tuple[str, ...] = ()
    checks: tuple[str, ...] = ()
    plan_required: bool = False
    docs_to_update: tuple[str, ...] = ()
    path_prefixes: tuple[str, ...] = ()
    exact_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class DriftRule:
    key: str
    title: str
    reason: str
    required_docs: tuple[str, ...]
    required_artifacts_all: tuple[str, ...] = ()
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
        mode="Protocol V3 / WS",
        playbook=repo_path(SUBAGENTS_PLAYBOOK_PATH),
        skills=(repo_path(DOCS_SYNC_SKILL_PATH), repo_path(TESTS_SKILL_PATH)),
        checks=(
            "python scripts/verify_workspace.py",
            "python -m pytest server/tests/ ...",
            "python -m pytest pc_agent/tests/ ...",
        ),
        plan_required=True,
        docs_to_update=(
            repo_path(QUICK_LOOKUP_PATH),
            repo_path(SERVER_CODEMAP_PATH),
            repo_path(AGENT_CODEMAP_PATH),
            "server/docs/PROTOCOL_V3.md",
            "pc_agent/docs/PROTOCOL_V3.md",
            "server/docs/COMMAND_RESULT_LIFECYCLE.md",
            "server/docs/TOOL_CALL_STARTED_INVARIANT.md",
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
        summary="Single path for tool execution, consent approval, operation queueing and agent-side module execution tracing.",
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
        mode="Tool execution / operations",
        skills=(repo_path(DOCS_SYNC_SKILL_PATH), repo_path(TESTS_SKILL_PATH)),
        checks=(
            "python scripts/verify_workspace.py",
            "python -m pytest server/tests/ ...",
            "python -m pytest pc_agent/tests/ ...",
        ),
        docs_to_update=(
            repo_path(QUICK_LOOKUP_PATH),
            repo_path(SERVER_CODEMAP_PATH),
            repo_path(AGENT_CODEMAP_PATH),
            "server/docs/TOOL_CALL_STARTED_INVARIANT.md",
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
        mode="Auth / token bootstrap",
        skills=(repo_path(DOCS_SYNC_SKILL_PATH), repo_path(TESTS_SKILL_PATH)),
        checks=(
            "python scripts/verify_workspace.py",
            "python -m pytest server/tests/ ...",
            "python -m pytest pc_agent/tests/ ...",
        ),
        docs_to_update=(
            repo_path(QUICK_LOOKUP_PATH),
            repo_path(SERVER_CODEMAP_PATH),
            repo_path(AGENT_CODEMAP_PATH),
            "server/docs/SECURITY_AND_AUTH.md",
            "pc_agent/docs/AUTHENTICATION.md",
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
        summary="Ticket lifecycle, SLA, chat, public access, queue behavior and canonical ticket-root observer trace.",
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
        mode="Tickets / chat / queue",
        skills=(repo_path(DOCS_SYNC_SKILL_PATH), repo_path(TESTS_SKILL_PATH)),
        checks=(
            "python scripts/verify_workspace.py",
            "python -m pytest server/tests/ ...",
        ),
        docs_to_update=(
            repo_path(QUICK_LOOKUP_PATH),
            repo_path(SERVER_CODEMAP_PATH),
            "server/docs/TICKET_SYSTEM.md",
            "server/docs/CHAT_MESSAGE_CONTRACT.md",
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
        summary="Module install, desired state, reconcile, manifest, module registry and mandatory observer SDK instrumentation.",
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
        mode="Modules / reconcile",
        skills=(repo_path(DOCS_SYNC_SKILL_PATH), repo_path(TESTS_SKILL_PATH)),
        checks=(
            "python scripts/verify_workspace.py",
            "python -m pytest server/tests/ ...",
            "python -m pytest pc_agent/tests/ ...",
        ),
        plan_required=True,
        docs_to_update=(
            repo_path(QUICK_LOOKUP_PATH),
            repo_path(SERVER_CODEMAP_PATH),
            repo_path(AGENT_CODEMAP_PATH),
            "server/docs/MODULES_API.md",
            "server/docs/MODULES_DRIFT_AND_SNAPSHOTS.md",
            "pc_agent/docs/MODULES.md",
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
            "server/utils/module_observer_contract.py",
            "server/utils/module_builder.py",
            "server/docs/MODULE_AUTHORING_RULES.md",
            "pc_agent/core/module_manager.py",
            "pc_agent/core/loader.py",
            "pc_agent/core/registry.py",
            "pc_agent/modules/base_module.py",
        ),
    ),
    Topic(
        key="web_platform",
        title="New web workspaces / typed web boundary",
        summary="React/Vite `webapp`, typed `/api/web/*` contracts, session-gated `/app/*` routes, bundle serving from aiohttp, support Playwright signoff and typed admin slices for inventory, device update actions, modules registry/actions, request-form builder, observer quick summary and trace drilldown surfaces.",
        aliases=(
            "webapp",
            "react app",
            "vite",
            "typed web boundary",
            "api/web",
            "app/support",
            "app/admin",
            "support workspace",
            "admin workspace",
            "device updates",
            "admin updates",
            "admin modules",
            "modules registry",
            "preferred version",
            "preferred rollout",
            "module preferred",
            "modules workbench",
            "forms builder",
            "ticket forms",
            "request forms",
            "observer quick",
            "observer traces",
            "trace drilldown",
            "admin tech panel",
        ),
        first_files=(
            "webapp/src/main.tsx",
            "webapp/src/app/router.tsx",
            "webapp/src/app/layouts/app-shell.tsx",
            "webapp/src/features/auth/session-provider.tsx",
            "webapp/src/features/auth/login-page.tsx",
            "webapp/src/features/admin/api.ts",
            "webapp/src/features/admin/admin-workspace.tsx",
            "webapp/src/features/agent-updates/api.ts",
            "webapp/src/features/agent-updates/device-update-panel.tsx",
            "webapp/src/features/modules/api.ts",
            "webapp/src/features/modules/modules-panel.tsx",
            "webapp/src/features/forms-builder/api.ts",
            "webapp/src/features/forms-builder/forms-builder-panel.tsx",
            "webapp/src/features/tech/api.ts",
            "webapp/src/features/tech/observer-quick-panel.tsx",
            "webapp/src/features/tech/observer-trace-drilldown.tsx",
            "server/web_api/session_handlers.py",
            "server/web_api/support_handlers.py",
            "server/web_api/admin_handlers.py",
            "server/static_pages/webapp_assets.py",
            "server/routes.py",
        ),
        related_docs=(
            "docs/QUICK_LOOKUP.md",
            "server/docs/CODEMAP.md",
            "server/docs/SECURITY_AND_AUTH.md",
            "server/docs/OBSERVER_LAYER.md",
            "server/docs/OBSERVER_AUTHORING_RULES.md",
            "server/docs/REQUEST_FORM_BUILDER.md",
            "docs/superpowers/specs/2026-04-20-admin-support-web-rearchitecture-design.md",
            "docs/superpowers/plans/2026-04-20-admin-support-web-rearchitecture.md",
        ),
        suggested_commands=(
            "python scripts/bootstrap_web_toolchain.py",
            'python scripts/agent_find.py "web_api" --dir server',
            'python scripts/agent_find.py "app/support" --dir server',
            'python scripts/agent_find.py "app/admin" --dir server',
            'python scripts/agent_find.py "device update" --dir server',
            'python scripts/agent_find.py "web/admin/modules" --dir server',
            'python scripts/agent_find.py "rollout_settings" --dir server',
            'python scripts/agent_find.py "observer/traces" --dir server',
        ),
        mode="Internal web platform / React",
        skills=(repo_path(DOCS_SYNC_SKILL_PATH), repo_path(TESTS_SKILL_PATH)),
        checks=(
            "python scripts/bootstrap_web_toolchain.py",
            "pnpm --dir webapp run test",
            "pnpm --dir webapp run build",
            "python -m pytest server/tests/test_web_session_api.py server/tests/test_web_support_api.py server/tests/test_web_admin_api.py server/tests/test_static_pages_handlers.py -v --tb=short",
        ),
        plan_required=True,
        docs_to_update=(
            repo_path(QUICK_LOOKUP_PATH),
            repo_path(SERVER_CODEMAP_PATH),
            "server/docs/SECURITY_AND_AUTH.md",
            "server/docs/OBSERVER_LAYER.md",
            "server/docs/OBSERVER_AUTHORING_RULES.md",
        ),
        path_prefixes=("webapp/", "server/web_api/", "server/static_pages/"),
        exact_paths=(
            "server/routes.py",
            "package.json",
            ".node-version",
            ".nvmrc",
            ".npmrc",
            "scripts/bootstrap_web_toolchain.py",
            "server/auth/middleware.py",
        ),
    ),
    Topic(
        key="ui_server",
        title="Server UI / admin pages",
        summary="Admin, ticket and public pages plus control-plane backed tech panel, observer runtime/settings, drilldown, degradation search and static route handlers.",
        aliases=(
            "admin ui",
            "admin page",
            "ticket ui",
            "public queue",
            "help page",
            "browser check",
            "tech panel",
            "control plane",
            "degradation",
            "timeout rate",
            "retry rate",
            "slow rate",
            "root_kind",
            "observer settings",
            "sampling",
            "retention",
        ),
        first_files=(
            "server/admin.js",
            "server/control_plane.py",
            "server/runtime_control.py",
            "server/ticket.js",
            "server/static_pages/",
            "server/routes.py",
        ),
        related_docs=(
            "docs/QUICK_LOOKUP.md",
            "server/docs/CODEMAP.md",
            "server/docs/SECURITY_AND_AUTH.md",
        ),
        suggested_commands=(
            "python scripts/diff_context.py",
            "python scripts/manage_remote_stack.py status control",
            "GUI check via MCP at http://192.168.100.17:8666/admin",
        ),
        mode="Release / deploy / web admin",
        playbook=repo_path(RELEASE_PLAYBOOK_PATH),
        skills=(
            repo_path(BROWSER_CHECK_SKILL_PATH),
            repo_path(RELEASE_SKILL_PATH),
            repo_path(TESTS_SKILL_PATH),
        ),
        checks=(
            "python scripts/verify_workspace.py",
            "python -m pytest server/tests/ ...",
            "GUI check via MCP at http://192.168.100.17:8666/admin",
        ),
        plan_required=True,
        docs_to_update=(
            repo_path(QUICK_LOOKUP_PATH),
            repo_path(SERVER_CODEMAP_PATH),
        ),
        path_prefixes=("server/static_pages/",),
        exact_paths=(
            "server/admin.html",
            "server/admin.js",
            "server/admin.css",
            "server/control_plane.py",
            "server/runtime_control.py",
            "server/tech/handlers.py",
            "server/observer/runtime.py",
            "server/observer/service.py",
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
        summary="Qt GUI, SSE bridge, initiator profiles and local GUI integration plus always-on diagnostics entrypoints.",
        aliases=(
            "gui",
            "ui bridge",
            "sse",
            "chat panel",
            "main window",
            "initiator profile",
            "connection_state",
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
            "pc_agent/docs/AGENT_RUNTIME_ALWAYS_ON.md",
        ),
        suggested_commands=(
            'python scripts/agent_find.py "ui bridge" --dir pc_agent',
            'python scripts/agent_find.py "connection_state" --dir pc_agent',
            "python scripts/diff_context.py",
        ),
        mode="Agent runtime / tray / logs",
        playbook=repo_path(AGENT_RUNTIME_PLAYBOOK_PATH),
        skills=(repo_path(AGENT_RUNTIME_SKILL_PATH), repo_path(TESTS_SKILL_PATH)),
        checks=(
            "python scripts/verify_workspace.py",
            "python -m pytest pc_agent/tests/test_ui_api_server_shutdown.py -v --tb=short",
            "python -m pytest pc_agent/tests/test_runtime_logging.py -v --tb=short",
        ),
        plan_required=True,
        docs_to_update=(
            repo_path(QUICK_LOOKUP_PATH),
            repo_path(AGENT_CODEMAP_PATH),
            "pc_agent/docs/AGENT_RUNTIME_ALWAYS_ON.md",
        ),
        path_prefixes=(
            "pc_agent/ui_gui/",
            "pc_agent/ui_bridge/",
        ),
        exact_paths=("pc_agent/ui_gui/main.py",),
    ),
    Topic(
        key="agent_runtime",
        title="Agent runtime / tray / logs",
        summary="Always-on runtime lifecycle, tray behavior, runtime diagnostics/logging and local update request/shutdown tracing.",
        aliases=(
            "always-on",
            "always on",
            "tray",
            "runtime logs",
            "runtime logging",
            "agent shutdown",
            "close to tray",
            "trigger recommended update",
            "action trace",
        ),
        first_files=(
            "pc_agent/docs/AGENT_RUNTIME_ALWAYS_ON.md",
            "pc_agent/ws_agent.py",
            "pc_agent/core/runtime_logging.py",
            "pc_agent/ui_gui/main.py",
        ),
        related_docs=(
            "docs/QUICK_LOOKUP.md",
            "pc_agent/docs/CODEMAP.md",
            "pc_agent/docs/AGENT_RUNTIME_ALWAYS_ON.md",
            ".cursor/skills/pc-client-agent-runtime/SKILL.md",
        ),
        suggested_commands=(
            'python scripts/agent_find.py "tray" --dir pc_agent',
            'python scripts/agent_find.py "runtime_logging" --dir pc_agent',
            "python scripts/manage_local_agent.py status",
        ),
        mode="Agent runtime / tray / logs",
        playbook=repo_path(AGENT_RUNTIME_PLAYBOOK_PATH),
        skills=(repo_path(AGENT_RUNTIME_SKILL_PATH), repo_path(TESTS_SKILL_PATH)),
        checks=(
            "python scripts/verify_workspace.py",
            "python -m pytest pc_agent/tests/test_ui_api_server_shutdown.py -v --tb=short",
            "python -m pytest pc_agent/tests/test_runtime_logging.py -v --tb=short",
            "python scripts/manage_local_agent.py start <name> --gui --ui-port <port>",
        ),
        plan_required=True,
        docs_to_update=(
            repo_path(QUICK_LOOKUP_PATH),
            repo_path(AGENT_CODEMAP_PATH),
            "pc_agent/docs/AGENT_RUNTIME_ALWAYS_ON.md",
        ),
        exact_paths=(
            "pc_agent/ws_agent.py",
            "pc_agent/core/runtime_logging.py",
            "pc_agent/ui_gui/main.py",
            "pc_agent/ui_gui/tray_manager.py",
        ),
        path_prefixes=(
            "pc_agent/ui_gui/",
            "pc_agent/ui_bridge/",
        ),
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
        mode="Database / migrations",
        playbook=repo_path(SUBAGENTS_PLAYBOOK_PATH),
        skills=(repo_path(MIGRATIONS_SKILL_PATH), repo_path(TESTS_SKILL_PATH)),
        checks=(
            "python scripts/verify_workspace.py",
            "python -m pytest server/tests/ ...",
        ),
        plan_required=True,
        docs_to_update=(
            repo_path(QUICK_LOOKUP_PATH),
            repo_path(SERVER_CODEMAP_PATH),
            repo_path(AGENT_CODEMAP_PATH),
            "server/docs/DATABASE.md",
            "pc_agent/docs/DATABASE.md",
        ),
        path_prefixes=("server/app/db/",),
        exact_paths=("pc_agent/core/database.py",),
    ),
    Topic(
        key="docs_sync",
        title="Docs + CODEMAP",
        summary="Routes, API contracts, entrypoints and navigation docs that must stay in sync with code.",
        aliases=(
            "route",
            "routes",
            "api route",
            "endpoint",
            "contract",
            "contracts",
            "docs",
            "documentation",
            "codemap",
            "entrypoint",
            "entrypoints",
        ),
        first_files=(
            "AGENTS.md",
            "docs/QUICK_LOOKUP.md",
            "server/docs/CODEMAP.md",
            "pc_agent/docs/CODEMAP.md",
        ),
        related_docs=(
            "AGENTS.md",
            "docs/QUICK_LOOKUP.md",
            "server/docs/CODEMAP.md",
            "pc_agent/docs/CODEMAP.md",
            repo_path(DOCS_SYNC_SKILL_PATH),
        ),
        suggested_commands=(
            "python scripts/task_intake.py --task \"add new API route\"",
            "python scripts/diff_context.py",
        ),
        mode="Docs + CODEMAP",
        playbook=repo_path(SUBAGENTS_PLAYBOOK_PATH),
        skills=(repo_path(DOCS_SYNC_SKILL_PATH),),
        checks=("python scripts/verify_workspace.py",),
        docs_to_update=(
            "AGENTS.md",
            repo_path(QUICK_LOOKUP_PATH),
            repo_path(SERVER_CODEMAP_PATH),
            repo_path(AGENT_CODEMAP_PATH),
        ),
        path_prefixes=("docs/", "server/api/", "server/routes/", "server/app/api/"),
        exact_paths=(
            "server/routes.py",
            "server/server.py",
            "server/config.py",
            "AGENTS.md",
        ),
    ),
    Topic(
        key="agent_updates",
        title="Agent updates / rollout",
        summary="Launcher builds, self-update, upload, canary rollout, recommended-version behavior, typed admin device-update boundary and end-to-end update tracing.",
        aliases=(
            "agent update",
            "agent updates",
            "self update",
            "self-update",
            "launcher",
            "rollout",
            "canary",
            "recommended build",
            "recommended version",
            "update availability",
            "pending_update",
            "update_history",
            "agent.update.apply",
            "agent.update.command",
        ),
        first_files=(
            "pc_agent/docs/AGENT_UPDATE_WORKFLOW.md",
            "pc_agent/docs/SELF_UPDATE.md",
            "server/docs/AGENT_UPDATES_API.md",
            "pc_agent/version.py",
        ),
        related_docs=(
            repo_path(QUICK_LOOKUP_PATH),
            "pc_agent/docs/AGENT_UPDATE_WORKFLOW.md",
            "pc_agent/docs/SELF_UPDATE.md",
            "server/docs/AGENT_UPDATES_API.md",
            repo_path(AGENT_CODEMAP_PATH),
            repo_path(AGENT_UPDATES_SKILL_PATH),
        ),
        suggested_commands=(
            'python scripts/agent_find.py "launcher" --dir pc_agent',
            'python scripts/agent_find.py "agent_builds" --dir server',
            "python scripts/diff_context.py",
        ),
        mode="Agent updates / rollout",
        playbook=repo_path(AGENT_UPDATES_PLAYBOOK_PATH),
        skills=(repo_path(AGENT_UPDATES_SKILL_PATH), repo_path(TESTS_SKILL_PATH)),
        checks=(
            "python scripts/verify_workspace.py",
            "python -m pytest pc_agent/tests/ -v --tb=short",
            "python -m pytest server/tests/test_p0_workbench_update_contracts.py -v --tb=short",
            "python pc_agent/build_windows_release_v2.py",
        ),
        plan_required=True,
        docs_to_update=(
            repo_path(QUICK_LOOKUP_PATH),
            repo_path(AGENT_CODEMAP_PATH),
            repo_path(SERVER_CODEMAP_PATH),
            "pc_agent/docs/AGENT_UPDATE_WORKFLOW.md",
            "pc_agent/docs/SELF_UPDATE.md",
            "server/docs/AGENT_UPDATES_API.md",
        ),
        path_prefixes=("pc_agent/launcher/",),
        exact_paths=(
            "pc_agent/ws_agent.py",
            "pc_agent/ui_bridge/api_server.py",
            "pc_agent/ui_gui/main_window.py",
            "pc_agent/version.py",
            "scripts/manage_local_agent.py",
            "server/agents/agent_builds_handlers.py",
            "server/app/repos/agent_rollout_repo.py",
        ),
    ),
    Topic(
        key="observer",
        title="Observer / traces / degradations",
        summary="Trace overlay, action-span sync, retention/sampling settings, backfill health, degradation queries, full-ticket observer summary counts, ticket-local signature occurrence counts, single-flight UI polling, and the canonical `/support` ticket-trace drawer.",
        aliases=(
            "observer",
            "trace overlay",
            "spans",
            "signatures",
            "degradation",
            "degradations",
            "timeout rate",
            "retry rate",
            "retention",
            "sampling",
            "backfill",
        ),
        first_files=(
            "server/observer/service.py",
            "server/observer/runtime.py",
            "server/tech/handlers.py",
            "server/admin.js",
            "server/support.js",
        ),
        related_docs=(
            repo_path(QUICK_LOOKUP_PATH),
            repo_path(SERVER_CODEMAP_PATH),
            repo_path(AGENT_CODEMAP_PATH),
            "server/docs/OBSERVER_LAYER.md",
            "server/docs/OBSERVER_AUTHORING_RULES.md",
        ),
        suggested_commands=(
            'python scripts/agent_find.py "ObserverOverlayService" --dir server',
            'python scripts/agent_find.py "trace_span" --dir pc_agent',
            "GUI check via MCP at http://192.168.100.17:8666/admin",
        ),
        mode="Observer / tracing",
        skills=(
            repo_path(DOCS_SYNC_SKILL_PATH),
            repo_path(BROWSER_CHECK_SKILL_PATH),
            repo_path(TESTS_SKILL_PATH),
            repo_path(OBSERVER_DIAGNOSTICS_SKILL_PATH),
        ),
        checks=(
            "python scripts/verify_workspace.py",
            "python -m pytest server/tests/ ...",
            "python -m pytest pc_agent/tests/ ...",
            "GUI check via MCP at http://192.168.100.17:8666/admin",
        ),
        plan_required=True,
        docs_to_update=(
            repo_path(QUICK_LOOKUP_PATH),
            repo_path(SERVER_CODEMAP_PATH),
            repo_path(AGENT_CODEMAP_PATH),
            "server/docs/OBSERVER_LAYER.md",
            "server/docs/OBSERVER_AUTHORING_RULES.md",
            repo_path(OBSERVER_DIAGNOSTICS_SKILL_PATH),
        ),
        path_prefixes=(
            "server/observer/",
            "shared/",
        ),
        exact_paths=(
            "server/tech/handlers.py",
            "server/app/repos/observer_settings_repo.py",
            "server/admin.html",
            "server/admin.js",
            "pc_agent/core/action_trace.py",
            "pc_agent/core/orchestrator.py",
            "pc_agent/modules/base_module.py",
        ),
    ),
    Topic(
        key="planning",
        title="Planning / handoff",
        summary="Long-horizon plan, verification state and handoff between sessions.",
        aliases=(
            "plan",
            "plans.md",
            "handoff",
            "verification",
            "residual risk",
            "long task",
        ),
        first_files=(
            "PLANS.md",
            "AGENTS.md",
        ),
        related_docs=(
            "PLANS.md",
            "AGENTS.md",
            ".cursor/skills/pc-client-plans/SKILL.md",
            ".cursor/skills/pc-client-release/SKILL.md",
        ),
        suggested_commands=(
            "python scripts/verify_workspace.py",
        ),
        mode="Planning / handoff",
        skills=(repo_path(PLANS_SKILL_PATH), repo_path(RELEASE_SKILL_PATH)),
        plan_required=True,
        docs_to_update=(repo_path(PLANS_PATH),),
        exact_paths=(
            "PLANS.md",
            ".codex/config.toml",
        ),
    ),
    Topic(
        key="release",
        title="Release / deploy / smoke",
        summary="Local verification, deploy to Linux, runtime control, canonical server/control wrappers, smoke and browser checks.",
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
            "scripts/run_observer_canary_suite.py",
            "scripts/deploy_workspace_to_remote.py",
            "scripts/release_server_to_remote.py",
            "scripts/manage_remote_stack.py",
            "scripts/runtime_stack.py",
        ),
        related_docs=(
            "docs/QUICK_LOOKUP.md",
            "server/docs/CODEMAP.md",
            "pc_agent/docs/CODEMAP.md",
            "PLANS.md",
            ".cursor/skills/pc-client-release/SKILL.md",
            ".cursor/skills/pc-client-tests/SKILL.md",
        ),
        suggested_commands=(
            "python scripts/verify_workspace.py",
            "python scripts/release_server_to_remote.py",
            "python scripts/manage_remote_stack.py status control",
        ),
        mode="Release / deploy",
        playbook=repo_path(RELEASE_PLAYBOOK_PATH),
        skills=(repo_path(RELEASE_SKILL_PATH), repo_path(TESTS_SKILL_PATH)),
        checks=(
            "python scripts/verify_workspace.py",
            "python scripts/run_ci_suite.py",
            "python scripts/manage_remote_stack.py status control",
        ),
        plan_required=True,
        docs_to_update=(
            "AGENTS.md",
            repo_path(QUICK_LOOKUP_PATH),
            repo_path(PLANS_PATH),
            "docs/LOCAL_WORKFLOW.md",
        ),
        path_prefixes=("scripts/",),
        exact_paths=("scripts/run_observer_canary_suite.py",),
    ),
)


DRIFT_RULES: tuple[DriftRule, ...] = (
    DriftRule(
        key="navigation_harness",
        title="Navigation harness changed",
        reason="Navigation scripts and rules should stay aligned with AGENTS and QUICK_LOOKUP.",
        exact_paths=(
            "scripts/navigation_catalog.py",
            "scripts/diff_context.py",
            "scripts/agent_find.py",
            "scripts/docs_drift_check.py",
            "scripts/task_intake.py",
        ),
        required_docs=(
            "AGENTS.md",
            "docs/QUICK_LOOKUP.md",
            ".cursor/rules/navigation-tools.mdc",
        ),
    ),
    DriftRule(
        key="workflow_harness",
        title="Workflow or verification harness changed",
        reason="Deploy, verification and shell bootstrap flows should stay aligned across docs and skills.",
        exact_paths=(
            "scripts/verify_workspace.py",
            "scripts/deploy_workspace_to_remote.py",
            "scripts/release_server_to_remote.py",
            "scripts/manage_remote_stack.py",
            "scripts/runtime_stack.py",
            "scripts/run_control_plane.py",
            "scripts/bootstrap_shell_utf8.ps1",
        ),
        required_docs=(
            "AGENTS.md",
            "docs/LOCAL_WORKFLOW.md",
            ".cursor/skills/pc-client-release/SKILL.md",
            ".cursor/skills/pc-client-tests/SKILL.md",
        ),
    ),
    DriftRule(
        key="server_runtime_control",
        title="Server runtime control changed",
        reason="Control-plane, runtime lifecycle scripts and tech panel contracts must stay aligned with docs and browser verification rules.",
        exact_paths=(
            "server/control_plane.py",
            "server/runtime_control.py",
            "server/admin.html",
            "server/admin.js",
            "server/admin.css",
            "server/tech/handlers.py",
        ),
        required_docs=(
            "AGENTS.md",
            "docs/QUICK_LOOKUP.md",
            "server/docs/CODEMAP.md",
            "server/docs/SECURITY_AND_AUTH.md",
            ".cursor/rules/automation.mdc",
            ".cursor/skills/pc-client-browser-check/SKILL.md",
        ),
    ),
    DriftRule(
        key="server_entrypoints",
        title="Server entrypoints or routes changed",
        reason="Routes, startup wiring and key server entrypoints are navigation-critical.",
        exact_paths=("server/server.py", "server/routes.py", "server/config.py"),
        required_artifacts_all=("docs/QUICK_LOOKUP.md", "scripts/navigation_catalog.py"),
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
        required_artifacts_all=("docs/QUICK_LOOKUP.md", "scripts/navigation_catalog.py"),
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
        required_artifacts_all=("docs/QUICK_LOOKUP.md", "scripts/navigation_catalog.py"),
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
        required_artifacts_all=("docs/QUICK_LOOKUP.md", "scripts/navigation_catalog.py"),
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
        required_artifacts_all=("docs/QUICK_LOOKUP.md", "scripts/navigation_catalog.py"),
        required_docs=(
            "pc_agent/docs/AUTHENTICATION.md",
            "pc_agent/docs/CODEMAP.md",
            "docs/QUICK_LOOKUP.md",
        ),
    ),
    DriftRule(
        key="observer",
        title="Observer layer changed",
        reason="Observer runtime, quick diagnosis, trace APIs, projection-session behavior and dangerous-flow instrumentation must stay aligned with canonical observer docs.",
        path_prefixes=("server/observer/",),
        exact_paths=(
            "server/tech/handlers.py",
            "server/tickets/handlers.py",
            "server/admin.html",
            "server/admin.js",
            "server/support.html",
            "server/support.js",
            "server/web_api/admin_handlers.py",
            "webapp/src/features/tech/api.ts",
            "webapp/src/features/tech/observer-quick-panel.tsx",
            "webapp/src/features/tech/observer-trace-drilldown.tsx",
            "pc_agent/core/action_trace.py",
            "pc_agent/modules/base_module.py",
            "server/app/repos/observer_settings_repo.py",
        ),
        required_artifacts_all=("docs/QUICK_LOOKUP.md", "scripts/navigation_catalog.py"),
        required_docs=(
            "server/docs/OBSERVER_LAYER.md",
            "server/docs/OBSERVER_AUTHORING_RULES.md",
            "server/docs/CODEMAP.md",
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
            "server/utils/module_observer_contract.py",
            "server/utils/module_builder.py",
            "pc_agent/core/module_manager.py",
            "pc_agent/core/loader.py",
            "pc_agent/core/registry.py",
        ),
        required_artifacts_all=("docs/QUICK_LOOKUP.md", "scripts/navigation_catalog.py"),
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
        required_artifacts_all=("docs/QUICK_LOOKUP.md", "scripts/navigation_catalog.py"),
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
        required_artifacts_all=("docs/QUICK_LOOKUP.md", "scripts/navigation_catalog.py"),
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
        required_artifacts_all=("docs/QUICK_LOOKUP.md", "scripts/navigation_catalog.py"),
        required_docs=("pc_agent/docs/CODEMAP.md", "docs/QUICK_LOOKUP.md"),
    ),
    DriftRule(
        key="agent_updates_flow",
        title="Agent update or rollout flow changed",
        reason="Launcher, recommended update and rollout logic must stay aligned with update docs and routing metadata.",
        path_prefixes=("pc_agent/launcher/",),
        exact_paths=(
            "pc_agent/ws_agent.py",
            "pc_agent/ui_bridge/api_server.py",
            "pc_agent/ui_gui/main_window.py",
            "pc_agent/version.py",
            "server/agents/agent_builds_handlers.py",
            "server/app/repos/agent_rollout_repo.py",
        ),
        required_artifacts_all=("docs/QUICK_LOOKUP.md", "scripts/navigation_catalog.py"),
        required_docs=(
            "pc_agent/docs/AGENT_UPDATE_WORKFLOW.md",
            "pc_agent/docs/SELF_UPDATE.md",
            "server/docs/AGENT_UPDATES_API.md",
            "pc_agent/docs/CODEMAP.md",
            "docs/QUICK_LOOKUP.md",
        ),
    ),
    DriftRule(
        key="agent_runtime",
        title="Agent runtime or tray flow changed",
        reason="Always-on runtime, tray and ui_bridge behavior must stay aligned with runtime docs and routing metadata.",
        exact_paths=(
            "pc_agent/core/runtime_logging.py",
            "pc_agent/ws_agent.py",
        ),
        path_prefixes=("pc_agent/ui_gui/", "pc_agent/ui_bridge/"),
        required_artifacts_all=("docs/QUICK_LOOKUP.md", "scripts/navigation_catalog.py"),
        required_docs=(
            "pc_agent/docs/AGENT_RUNTIME_ALWAYS_ON.md",
            "pc_agent/docs/CODEMAP.md",
            "docs/QUICK_LOOKUP.md",
        ),
    ),
)


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


def collect_skills(topics: Sequence[Topic]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for topic in topics:
        for path in topic.skills:
            normalized = repo_path(path)
            if normalized in seen:
                continue
            seen.add(normalized)
            ordered.append(normalized)
    return ordered


def collect_checks(topics: Sequence[Topic], *, paths: Sequence[str] = ()) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for check in recommend_checks(paths):
        if check in seen:
            continue
        seen.add(check)
        ordered.append(check)
    for topic in topics:
        for check in topic.checks:
            if check in seen:
                continue
            seen.add(check)
            ordered.append(check)
    return ordered


def collect_docs_to_update(topics: Sequence[Topic], *, paths: Sequence[str] = ()) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()

    def add_path(value: str) -> None:
        normalized = repo_path(value)
        if normalized in seen:
            return
        seen.add(normalized)
        ordered.append(normalized)

    for topic in topics:
        for path in topic.docs_to_update:
            add_path(path)

    if paths:
        synthetic_changes = [ChangedPath(status="M", path=repo_path(path)) for path in paths]
        for rule, _ in iter_triggered_drift_rules(synthetic_changes):
            for path in rule.required_docs:
                add_path(path)

    return ordered


def select_mode(topics: Sequence[Topic]) -> str:
    if not topics:
        return "General / explore first"
    return topics[0].mode or topics[0].title


def select_playbook(topics: Sequence[Topic]) -> str | None:
    for topic in topics:
        if topic.playbook:
            return repo_path(topic.playbook)
    return None


def is_plan_required(topics: Sequence[Topic], *, paths: Sequence[str] = ()) -> bool:
    if any(topic.plan_required for topic in topics):
        return True

    normalized = [repo_path(path) for path in paths]
    subsystems: set[str] = set()
    for path in normalized:
        if path.startswith("server/"):
            subsystems.add("server")
        elif path.startswith("pc_agent/"):
            subsystems.add("pc_agent")
        elif path.startswith("scripts/"):
            subsystems.add("scripts")
        elif path.startswith("docs/") or path == "AGENTS.md":
            subsystems.add("docs")

    code_subsystems = {"server", "pc_agent"} & subsystems
    return len(code_subsystems) > 1 or ("scripts" in subsystems and bool(code_subsystems))


def iter_topic_artifacts(topic: Topic) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in (*topic.first_files, *topic.related_docs, *topic.skills, *topic.docs_to_update):
        normalized = repo_path(value)
        if normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    if topic.playbook:
        normalized = repo_path(topic.playbook)
        if normalized not in seen:
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
    if any(
        path.startswith("webapp/")
        or path.startswith("server/web_api/")
        or path in {
            "package.json",
            ".node-version",
            ".nvmrc",
            ".npmrc",
            "scripts/bootstrap_web_toolchain.py",
        }
        for path in normalized
    ):
        checks.extend(
            (
                "python scripts/bootstrap_web_toolchain.py",
                "pnpm --dir webapp run test",
                "pnpm --dir webapp run build",
            )
        )
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
