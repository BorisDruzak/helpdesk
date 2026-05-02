#!/usr/bin/env python3
"""Shared navigation metadata for pc_client docs and helper scripts."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
QUICK_LOOKUP_PATH = Path("docs/QUICK_LOOKUP.md")
CODEX_WORKFLOW_PATH = Path("docs/CODEX_WORKFLOW.md")
ARCHITECTURE_BOUNDARIES_PATH = Path("docs/ARCHITECTURE_BOUNDARIES.md")
CONTEXT_INDEX_PATH = Path("docs/CONTEXT_INDEX.md")
SERVER_CODEMAP_PATH = Path("server/docs/CODEMAP.md")
AGENT_CODEMAP_PATH = Path("pc_agent/docs/CODEMAP.md")
PLANS_PATH = Path("PLANS.md")
CODEX_CONFIG_PATH = Path(".codex/config.toml")
TASK_INTAKE_PATH = Path("scripts/task_intake.py")
LOCAL_WORKFLOW_PATH = Path("docs/LOCAL_WORKFLOW.md")
CONTEXT_EFFICIENCY_PATH = Path("docs/CONTEXT_EFFICIENCY.md")
AGENT_CAPABILITIES_PATH = Path("docs/AGENT_CAPABILITIES_AND_REQUIREMENTS.md")

DOCS_SYNC_SKILL = "pc-client-docs-sync"
MIGRATIONS_SKILL = "pc-client-migrations"
PLANS_SKILL = "pc-client-plans"
RELEASE_SKILL = "pc-client-release"
TESTS_SKILL = "pc-client-tests"
BROWSER_CHECK_SKILL = "pc-client-browser-check"
AGENT_UPDATES_SKILL = "pc-client-agent-updates"
AGENT_RUNTIME_SKILL = "pc-client-agent-runtime"
OBSERVER_DIAGNOSTICS_SKILL = "pc-client-observer-diagnostics"


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
        summary="WS handshake, reconnect-safe runtime ownership, state-level command waiters registered before dispatch wakeup, envelope V3, terminal-only outbox dedupe for retryable NACK safety, ACK/NACK, optional outbox batching, command_result semantics and graceful sender/teardown behavior in server and agent runtimes.",
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
            "протокол",
            "рукопожатие",
            "подключение агента",
            "подтверждение доставки",
        ),
        first_files=(
            "server/websocket/agent_handshake.py",
            "server/websocket/agent_services.py",
            "server/websocket/command_result_components.py",
            "server/app/repos/device_outbox_repo.py",
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
        skills=(DOCS_SYNC_SKILL, TESTS_SKILL),
        checks=(
            "python scripts/verify_workspace.py",
            "python -m pytest server/tests/ ...",
            "python -m pytest pc_agent/tests/ ...",
            "python scripts/manage_local_agent.py verify <name>",
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
        summary="Single path for tool execution, consent approval, operation queueing, agent-side execution lanes and module execution tracing.",
        aliases=(
            "run_tool",
            "tool_call_started",
            "admin_run_tool",
            "consent",
            "approve_consent",
            "send_ws_command",
            "запуск инструмента",
            "выполнение инструмента",
            "согласие",
            "операция",
            "очередь операций",
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
        skills=(DOCS_SYNC_SKILL, TESTS_SKILL),
        checks=(
            "python scripts/verify_workspace.py",
            "python -m pytest server/tests/ ...",
            "python -m pytest pc_agent/tests/ ...",
            "python scripts/manage_local_agent.py start <name> --ws-url ws://127.0.0.1:8666/ws --api-url http://127.0.0.1:8666/api",
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
        summary="Token sources, AuthContext, connection request flow, hardware device fingerprint proof, legacy TOKEN_LIMIT_EXCEEDED diagnostics, rate-limited web_auth observer audit rows, httpOnly web session bridging for React admin/notification surfaces, and security invariants.",
        aliases=(
            "auth",
            "token",
            "token limit",
            "token_limit_exceeded",
            "device_fingerprint",
            "device_fingerprint_mismatch",
            "hardware proof",
            "active token limit",
            "authcontext",
            "connection request",
            "connection_request",
            "notification auth",
            "notifications preferences",
            "web_auth",
            "web auth",
            "web_auth_failed",
            "web_auth_forbidden",
            "route auth audit",
            "rbac",
            "security",
            "авторизация",
            "аутентификация",
            "токен",
            "права",
            "безопасность",
        ),
        first_files=(
            "server/auth/",
            "server/auth/device_fingerprint.py",
            "server/app/repos/auth_tokens_repo.py",
            "server/auth/middleware.py",
            "pc_agent/auth/token_source.py",
            "pc_agent/auth/connection_request.py",
            "pc_agent/core/identity.py",
            "pc_agent/core/device_fingerprint.py",
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
        skills=(DOCS_SYNC_SKILL, TESTS_SKILL),
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
            "pc_agent/core/device_fingerprint.py",
        ),
    ),
    Topic(
        key="tickets",
        title="Tickets / chat / queue",
        summary="Ticket lifecycle, workflow profiles with executable per-transition role/required-field/comment/approval/evidence gates plus notification/SLA action markers and `trigger`/`auto` metadata for system-triggered transitions such as `requester_replied`, configurable priority matrix/modifiers/manual override, deterministic SLA/OLA, second-precision business-calendar SLA due dates, standalone SLA JSON target calculation, policy-aware SLA start/pause/resume/stop conditions with warning-before and breach-action payloads, standalone OLA policy ack/processing targets with start/stop/pause/resume conditions, source tracking and watchdog breach events, typed request-template and active ticket-type catalogs in web settings, list/dict-compatible calendar JSON in typed settings, standalone versioned helpdesk ticket-type/form-schema/policy/request-template registry with direct publication plus diff/deactivate/rollback-as-new-version API, ticket-type defaults inherited by request templates, first-class form_schemas/form_fields/form_conditions backing request_template.form_schema_id while legacy ticket_form_packs stay compatible, field process_mapping normalized to field_roles, request-template policy refs preferred ahead of inline form JSON, effective registry policy resolution during ticket creation with policy_refs/effective_policy_sources/effective_policy_snapshots plus approval request creation from approver sources, `any_one`/`all`/`sequential` approval modes, approval timeout/reminder/escalation watchdog events and reject-comment enforcement, closure/notification/visibility/reporting lifecycle reads, support-facing closure requirement checklist and policy-driven negative feedback reopen/keep-resolved behavior, side-effect-free `/api/tickets/create/preview` for PC-agent request-template preview including priority_explanation, visual request-template constructor in the forms builder, executable request-template routing/approval/closure/visibility/notification/reporting policies, external notification channel provider/audit events, backend smart views for support queue slices plus active published custom smart-view filters and `summary.smart_view_counts`, diagnostic policy evidence materialization and normalized diagnostic consent for resolution passports, reporting-policy passport sections/evidence packages/export tags, chat, public access, queue behavior, request-template process context, request_template_key-aware ticket creation for local agent/public intake, legacy form-pack ticket_type inference, extended intake field types, form-aware routing over ticket/request-form context, template default queue fallback, editable server-driven priority question fields/roles with old pack backfill that preserves custom policy field keys, P0 process priority support in OLA targets, 64-char ticket_type/request_kind slugs, and canonical ticket-root observer trace.",
        aliases=(
            "ticket",
            "tickets",
            "chat",
            "queue",
            "public access",
            "requester",
            "sla",
            "sla calendar",
            "business calendar",
            "business hours",
            "calendar_engine",
            "ola",
            "routing",
            "routing policy",
            "routing_policy",
            "routing decision",
            "routing_decision",
            "max_auto_reroutes",
            "routing rules",
            "request kind",
            "ticket type",
            "ticket type registry",
            "ticket_types",
            "publish ticket type",
            "form schema registry",
            "form_schemas",
            "form_fields",
            "form_conditions",
            "process_mapping",
            "publish form schema",
            "policy_refs",
            "effective_policy_snapshots",
            "ticket_type inference",
            "workflow profile",
            "workflow trigger",
            "auto transition",
            "requester_replied",
            "approval request",
            "approver_source",
            "approval_mode",
            "sequential approval",
            "approval timeout",
            "approval escalation",
            "approval reminder",
            "require_comment_on_reject",
            "priority policy",
            "priority_policy",
            "priority matrix",
            "manual_override",
            "priority_explanation",
            "priority_overridden",
            "manual priority",
            "computed_priority",
            "sla policy registry",
            "standalone sla",
            "sla json targets",
            "sla warning",
            "start_conditions",
            "pause_conditions",
            "resume_conditions",
            "stop_conditions",
            "breach_actions",
            "ola policy registry",
            "standalone ola",
            "ola runtime",
            "ola_started",
            "ola_paused",
            "ola_resumed",
            "ola_breached",
            "ola_runtime",
            "effective policy",
            "helpdesk policy registry",
            "approval policy",
            "approval_policy",
            "ticket_approvals",
            "APPROVAL_POLICY_BLOCKED",
            "closure policy",
            "closure_policy",
            "before_resolved",
            "allowed_resolution_codes",
            "requester_confirmation",
            "auto_close_after_days",
            "operation_log",
            "diagnostic policy",
            "diagnostic_policy",
            "diagnostic_result",
            "ticket_evidence_items",
            "ticket passport evidence",
            "visibility policy",
            "visibility_policy",
            "public_status",
            "public_status_mapping",
            "hide_from_requester",
            "notification policy",
            "notification_policy",
            "notification channels",
            "external notification",
            "external_notification_delivery",
            "on_status_changed",
            "on_sla_breach",
            "reporting policy",
            "reporting_policy",
            "passport policy",
            "report_tags",
            "smart views",
            "smart_views",
            "smart_view",
            "custom smart view",
            "published smart view",
            "sla_risk",
            "ola_risk",
            "waiting_approval",
            "diagnostics_failed",
            "resolution_summary",
            "requester_resolution_summary",
            "evidence required",
            "effective priority",
            "p0 ola",
            "process schema",
            "support lines",
            "template default queue",
            "impact_scope",
            "work_continuity",
            "request template",
            "request_template_key",
            "request form",
            "request_form_data",
            "visible_when",
            "form-aware routing",
            "заявка",
            "заявки",
            "чат",
            "очередь",
            "маршрутизация",
            "форма заявки",
            "форма обращения",
            "исполнитель",
        ),
        first_files=(
            "server/tickets/handlers.py",
            "server/tickets/create_flow.py",
            "server/tickets/workflow_service.py",
            "server/tickets/workflow_profiles.py",
            "server/tickets/helpdesk_policy_runtime.py",
            "server/app/repos/helpdesk_policy_repo.py",
            "server/tickets/priority_policy.py",
            "server/tickets/sla_service.py",
            "server/tickets/calendar_engine.py",
            "server/tickets/approval_policy.py",
            "server/tickets/closure_policy.py",
            "server/app/services/ticket_auto_close_watchdog.py",
            "server/tickets/diagnostic_policy.py",
            "server/tickets/visibility_policy.py",
            "server/tickets/notification_service.py",
            "server/tickets/notification_channels.py",
            "server/tickets/passport_service.py",
            "server/tickets/smart_views.py",
            "server/tickets/ola_service.py",
            "server/tickets/routing_service.py",
            "server/tickets/form_catalog.py",
            "server/chat/",
            "server/api/events.py",
        ),
        related_docs=(
            "docs/QUICK_LOOKUP.md",
            "server/docs/TICKET_SYSTEM.md",
            "server/docs/CHAT_MESSAGE_CONTRACT.md",
            "server/docs/CODEMAP.md",
            "server/docs/DIAGNOSTIC_PLAYBOOKS.md",
            "server/docs/REQUEST_FORM_BUILDER.md",
        ),
        suggested_commands=(
            'python scripts/agent_find.py "ticket" --dir server',
            'python scripts/agent_find.py "chat" --dir server',
            'python scripts/agent_find.py "routing" --dir server',
            'python scripts/agent_find.py "request_form" --dir server',
            'python scripts/agent_find.py "priority_policy" --dir server',
            'python scripts/agent_find.py "calendar_engine" --dir server',
            'python scripts/agent_find.py "ola_service" --dir server',
            'python scripts/agent_find.py "approval_policy" --dir server',
            'python scripts/agent_find.py "closure_policy" --dir server',
            'python scripts/agent_find.py "diagnostic_policy" --dir server',
            'python scripts/agent_find.py "visibility_policy" --dir server',
            'python scripts/agent_find.py "notification_policy" --dir server',
            'python scripts/agent_find.py "reporting_policy" --dir server',
            'python scripts/agent_find.py "smart_view" --dir server',
        ),
        mode="Tickets / chat / queue",
        skills=(DOCS_SYNC_SKILL, TESTS_SKILL),
        checks=(
            "python scripts/verify_workspace.py",
            "python -m pytest server/tests/ ...",
        ),
        docs_to_update=(
            repo_path(QUICK_LOOKUP_PATH),
            repo_path(SERVER_CODEMAP_PATH),
            "server/docs/TICKET_SYSTEM.md",
            "server/docs/CHAT_MESSAGE_CONTRACT.md",
            "server/docs/DIAGNOSTIC_PLAYBOOKS.md",
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
        key="registry_objects",
        title="Registry objects / Реестры",
        summary="Lightweight registry for people, departments, buildings/rooms, PC/printer assets, services, vendors and support queues; agent handshake auto-creates PC assets, requester profile sync creates people/locations/departments, request forms use registry-backed picker fields and clearable file metadata, ticket detail/admin UI expose registry context, admin inventory surfaces identity source/duplicate warnings, token panel/revoke with ISO timestamps and safe env_uuid duplicate cleanup archives old test devices with their tokens.",
        aliases=(
            "registry",
            "registries",
            "assets",
            "asset registry",
            "cmdb",
            "people registry",
            "locations",
            "buildings",
            "rooms",
            "vendors",
            "services registry",
            "data quality",
            "registry profile",
            "identity source",
            "env_uuid",
            "duplicate devices",
            "cleanup env duplicates",
            "device tokens",
            "revoke token",
            "fingerprint mismatch",
            "admin-2 duplicates",
            "реестр",
            "реестры",
            "объекты",
            "здания",
            "кабинеты",
            "подразделения",
            "подрядчики",
        ),
        first_files=(
            "server/registry/service.py",
            "server/app/repos/registry_repo.py",
            "server/web_api/registry_handlers.py",
            "server/web_api/admin_handlers.py",
            "server/app/db/models.py",
            "server/websocket/agent_handshake.py",
            "server/tickets/create_flow.py",
            "server/web_api/support_handlers.py",
            "pc_agent/ui_gui/chat_panel.py",
            "pc_agent/ui_gui/server_api.py",
            "webapp/src/pages/admin/registry-page.tsx",
            "webapp/src/pages/admin/inventory-page.tsx",
            "webapp/src/features/admin/api.ts",
        ),
        related_docs=(
            "docs/QUICK_LOOKUP.md",
            "server/docs/CODEMAP.md",
            "pc_agent/docs/CODEMAP.md",
            "PLANS.md",
        ),
        suggested_commands=(
            'python scripts/agent_find.py "RegistryIngestionService" --dir server',
            'python scripts/agent_find.py "registry/profile" --dir server',
            'python scripts/agent_find.py "sync_registry_profile" --dir pc_agent',
            "python -m pytest server/tests/test_registry_service.py server/tests/test_registry_web_api.py -v --tb=short",
            "pnpm --dir webapp run build",
        ),
        mode="Registry / Assets",
        skills=(DOCS_SYNC_SKILL, MIGRATIONS_SKILL, TESTS_SKILL, BROWSER_CHECK_SKILL),
        checks=(
            "python scripts/verify_workspace.py",
            "python -m pytest server/tests/test_registry_service.py server/tests/test_registry_web_api.py -v --tb=short",
            "python -m pytest server/tests/test_web_support_api.py::test_web_support_ticket_detail_includes_observer_summary -v --tb=short",
            "pnpm --dir webapp run test",
            "pnpm --dir webapp run build",
            "GUI check via MCP at http://192.168.100.17:8666/admin",
        ),
        plan_required=True,
        docs_to_update=(
            repo_path(QUICK_LOOKUP_PATH),
            repo_path(SERVER_CODEMAP_PATH),
            repo_path(AGENT_CODEMAP_PATH),
            repo_path(PLANS_PATH),
        ),
        path_prefixes=(
            "server/registry/",
        ),
        exact_paths=(
            "server/app/repos/registry_repo.py",
            "server/web_api/registry_handlers.py",
            "server/web_api/admin_handlers.py",
            "server/app/db/models.py",
            "server/tickets/create_flow.py",
            "server/websocket/agent_handshake.py",
            "server/web_api/support_handlers.py",
            "server/web_api/dto/support.py",
            "pc_agent/ui_gui/chat_panel.py",
            "pc_agent/ui_gui/server_api.py",
            "webapp/src/pages/admin/registry-page.tsx",
            "webapp/src/pages/admin/inventory-page.tsx",
            "webapp/src/features/admin/api.ts",
        ),
    ),
    Topic(
        key="modules",
        title="Modules / reconcile",
        summary="Module install, desired state, reconcile, manifest, module registry, module_reconcile observer audit rows, and mandatory observer SDK instrumentation.",
        aliases=(
            "module",
            "modules",
            "reconcile",
            "module_reconcile",
            "module_reconcile_failed",
            "module reconcile audit",
            "desired modules",
            "manifest",
            "module install",
            "модуль",
            "модули",
            "реестр модулей",
            "установка модуля",
            "синхронизация модулей",
        ),
        first_files=(
            "server/modules/service.py",
            "server/modules/reconcile.py",
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
        skills=(DOCS_SYNC_SKILL, TESTS_SKILL),
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
            "server/websocket/outbox_ingest_components.py",
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
        summary="React/Vite `webapp`, lazy route chunks, typed `/api/web/*` contracts, role-aware `/app/*` routes, public requester `/app/help` and `/app/ticket/*`, server-driven `default_workspace`/`available_workspaces`/`permissions`, operational legacy-shell cutover guardrails, bundle serving from aiohttp, shared realtime bridge over `/api/web/realtime/bootstrap` -> `/ws_ui`, real-data support/admin/reports/settings surfaces, typed settings request-template catalog, typed notifications route/tab, typed access-control center with RBAC groups/grants/audit, typed support write guards through effective `can()` checks, support smart-view filters/counts including visible OLA risk, split settings permissions (`settings.view`, `settings.manage_queues`, `settings.manage_routing`), configurable workflow profiles at `/api/web/settings/workflow_profiles` with a visual transition guard/action constructor including `trigger` and `auto` fields, P0..P3 settings priority controls including OLA target saves, Russian labels for user-facing response/resolution deadlines, typed module workbench and tech-alert aliases, honest knowledge placeholder, and typed admin slices for inventory, registry objects, RBAC effective access, device update actions, modules registry/actions, request-template builder with process context, editable priority question roles, publish-to-standalone-policy-registry action and dedicated routing/approval/closure/diagnostic/notification/visibility/reporting policy editors, notification external-channel toggles, public/support ticket playbook autostart timeline events, ticket detail operational seven-question card with Passport X/7 completeness and closure requirement checklist before resolving, plus a full observer workbench with quick/traces/signatures/degradations/runtime tabs, global mode, trace detail with compact agent actions, and explicit detail/bundle error states.",
        aliases=(
            "webapp",
            "react app",
            "vite",
            "frontend",
            "frontend review",
            "ui review",
            "ux review",
            "accessibility",
            "accessibility audit",
            "admin ui",
            "server ui",
            "web interface",
            "visual redesign",
            "browser check",
            "typed web boundary",
            "api/web",
            "default workspace",
            "available workspaces",
            "permissions",
            "permissions_version",
            "settings.manage_queues",
            "settings.manage_routing",
            "ticket.status.change",
            "ticket.comment.public",
            "ticket.comment.internal",
            "ticket.passport.manage",
            "ticket.playbook.run",
            "ticket.tool.run",
            "module.tool.run.low_risk",
            "module.tool.run.high_risk",
            "access control",
            "access-control",
            "rbac",
            "effective access",
            "access group",
            "access groups",
            "group grants",
            "access audit",
            "api/web/admin/access",
            "cutover",
            "legacy shell",
            "legacy=1",
            "app/support",
            "app/admin",
            "app/help",
            "app/ticket",
            "requester ticket",
            "public requester",
            "support workspace",
            "admin workspace",
            "device updates",
            "admin updates",
            "admin modules",
            "admin registry",
            "admin access",
            "registry objects",
            "modules registry",
            "preferred version",
            "preferred rollout",
            "module preferred",
            "modules workbench",
            "forms builder",
            "ticket forms",
            "request forms",
            "request template builder",
            "operational ticket card",
            "playbook",
            "playbooks",
            "diagnostic playbooks",
            "playbook builder",
            "api/web/admin/playbooks",
            "api/web/support/tickets/playbooks",
            "ticket automation",
            "ticket playbook launch",
            "route preview",
            "routing builder",
            "request_form",
            "request form summary",
            "realtime",
            "realtime bridge",
            "ws_ui",
            "ui_hello",
            "observer quick",
            "observer traces",
            "trace drilldown",
            "admin tech panel",
            "reports",
            "settings",
            "notifications",
            "notification preferences",
            "tech alerts",
            "admin settings",
            "admin notifications",
            "knowledge",
            "knowledge placeholder",
            "api/web/reports",
            "api/web/settings",
            "api/web/settings/workflow_profiles",
            "api/web/notifications",
            "api/web/notifications/preferences",
            "api/web/admin/tech/alerts",
            "api/web/admin/modules/workbench",
            "api/web/admin/forms/route-preview",
            "queue settings",
            "sla policies",
            "ola targets",
            "workflow profiles",
            "workflow profile settings",
            "workflow trigger",
            "auto transition",
            "ticket type settings",
            "ticket_type settings",
            "p0 settings priority",
            "веб",
            "интерфейс",
            "веб интерфейс",
            "админка",
            "доступность",
            "формы заявок",
            "плейбук",
            "плейбуки",
            "диагностические сценарии",
            "отчеты",
            "настройки",
        ),
        first_files=(
            "webapp/src/main.tsx",
            "webapp/src/app/router.tsx",
            "webapp/src/app/routes/lazy-pages.tsx",
            "webapp/src/app/layouts/app-shell.tsx",
            "webapp/src/features/auth/session-provider.tsx",
            "webapp/src/features/auth/login-page.tsx",
            "webapp/src/features/auth/workspace-access.ts",
            "webapp/src/features/access-control/api.ts",
            "webapp/src/features/requester/api.ts",
            "webapp/src/features/requester/types.ts",
            "webapp/src/pages/help/index.tsx",
            "webapp/src/pages/requester-ticket/index.tsx",
            "webapp/scripts/remote-browser-signoff.mjs",
            "scripts/check_webapp_cutover.py",
            "webapp/package.json",
            "webapp/src/shared/realtime/client.ts",
            "webapp/src/shared/realtime/adapters/ws-ui-bridge.ts",
            "webapp/src/features/queues/api.ts",
            "webapp/src/features/reports/api.ts",
            "webapp/src/features/settings/api.ts",
            "webapp/src/features/admin/api.ts",
            "webapp/src/features/admin/admin-workspace.tsx",
            "webapp/src/pages/admin/registry-page.tsx",
            "webapp/src/pages/admin/access-page.tsx",
            "webapp/src/pages/admin/inventory-page.tsx",
            "webapp/src/pages/settings/index.tsx",
            "webapp/src/features/agent-updates/api.ts",
            "webapp/src/features/agent-updates/device-update-panel.tsx",
            "webapp/src/features/modules/api.ts",
            "webapp/src/features/modules/workbench-api.ts",
            "webapp/src/features/modules/modules-panel.tsx",
            "webapp/src/features/forms-builder/api.ts",
            "webapp/src/features/forms-builder/forms-builder-panel.tsx",
            "webapp/src/features/playbooks/api.ts",
            "webapp/src/features/playbooks/playbook-builder-panel.tsx",
            "webapp/src/pages/admin/playbooks-page.tsx",
            "server/playbooks/catalog.py",
            "server/playbooks/form_triggers.py",
            "webapp/src/features/tech/api.ts",
            "webapp/src/features/tech/observer-quick-panel.tsx",
            "webapp/src/features/tech/observer-trace-drilldown.tsx",
            "server/web_api/session_handlers.py",
            "server/access_control/catalog.py",
            "server/access_control/service.py",
            "server/app/repos/access_control_repo.py",
            "server/web_api/access_handlers.py",
            "server/web_api/support_handlers.py",
            "server/web_api/dto/support.py",
            "server/web_api/admin_handlers.py",
            "server/web_api/reports_handlers.py",
            "server/web_api/settings_handlers.py",
            "server/web_api/dto/settings.py",
            "server/tickets/workflow_profiles.py",
            "server/tickets/workflow_service.py",
            "server/tickets/admin_config_handlers.py",
            "server/web_api/realtime_handlers.py",
            "server/websocket/ui_handler.py",
            "server/static_pages/webapp_assets.py",
            "server/static_pages/cutover.py",
            "server/static_pages/handlers.py",
            "server/config.py",
            "server/routes.py",
        ),
        related_docs=(
            "docs/QUICK_LOOKUP.md",
            "server/docs/CODEMAP.md",
            "server/docs/SECURITY_AND_AUTH.md",
            "server/docs/OBSERVER_LAYER.md",
            "server/docs/OBSERVER_AUTHORING_RULES.md",
            "server/docs/REQUEST_FORM_BUILDER.md",
            "server/docs/DIAGNOSTIC_PLAYBOOKS.md",
            "docs/WEBAPP_CUTOVER_CHECKLIST.md",
            "docs/superpowers/specs/2026-04-20-admin-support-web-rearchitecture-design.md",
            "docs/superpowers/specs/2026-04-22-admin-support-unified-workspace-style-design.md",
            "docs/superpowers/plans/2026-04-22-webapp-real-data-cutover.md",
            "docs/superpowers/plans/2026-04-20-admin-support-web-rearchitecture.md",
        ),
        suggested_commands=(
            "python scripts/bootstrap_web_toolchain.py",
            "python scripts/check_webapp_cutover.py --json",
            "pnpm --dir webapp run check:remote -- --base-url http://192.168.100.17:8666",
            "pnpm --dir webapp run check:remote:webapp -- --base-url http://192.168.100.17:8666",
            'python scripts/agent_find.py "web_api" --dir server',
            'python scripts/agent_find.py "app/support" --dir server',
            'python scripts/agent_find.py "app/admin" --dir server',
            'python scripts/agent_find.py "device update" --dir server',
            'python scripts/agent_find.py "web/admin/modules" --dir server',
            'python scripts/agent_find.py "rollout_settings" --dir server',
            'python scripts/agent_find.py "observer/traces" --dir server',
            'python scripts/agent_find.py "reports/summary" --dir server',
            'python scripts/agent_find.py "api/web/settings" --dir server',
            'python scripts/agent_find.py "settings.manage_queues" --dir server',
            'python scripts/agent_find.py "ticket.tool.run" --dir server',
            'python scripts/agent_find.py "route-preview" --dir server',
            'python scripts/agent_find.py "playbook" --dir server',
            'python scripts/agent_find.py "request_form" --dir server',
            'python scripts/agent_find.py "realtime/bootstrap" --dir server',
            'python scripts/agent_find.py "ui_hello" --dir server',
        ),
        mode="Internal web platform / React",
        skills=(DOCS_SYNC_SKILL, BROWSER_CHECK_SKILL, TESTS_SKILL),
        checks=(
            "python scripts/bootstrap_web_toolchain.py",
            "python scripts/check_webapp_cutover.py --json",
            "pnpm --dir webapp run test",
            "pnpm --dir webapp run build",
            "pnpm --dir webapp run check:remote -- --base-url http://192.168.100.17:8666",
            "pnpm --dir webapp run check:remote:webapp -- --base-url http://192.168.100.17:8666",
            "python -m pytest server/tests/test_web_session_api.py server/tests/test_web_support_api.py server/tests/test_web_admin_api.py server/tests/test_web_reports_api.py server/tests/test_web_settings_api.py server/tests/test_web_realtime_api.py server/tests/test_static_pages_handlers.py -v --tb=short",
            "GUI check via MCP at http://192.168.100.17:8666/admin",
        ),
        plan_required=True,
        docs_to_update=(
            repo_path(QUICK_LOOKUP_PATH),
            repo_path(SERVER_CODEMAP_PATH),
            "server/docs/SECURITY_AND_AUTH.md",
            "server/docs/OBSERVER_LAYER.md",
            "server/docs/OBSERVER_AUTHORING_RULES.md",
            "server/docs/DIAGNOSTIC_PLAYBOOKS.md",
        ),
        path_prefixes=("webapp/", "server/web_api/", "server/static_pages/", "server/playbooks/"),
        exact_paths=(
            "server/routes.py",
            "server/config.py",
            "server/static_pages/cutover.py",
            "server/static_pages/handlers.py",
            "server/server.py",
            "webapp/package.json",
            "webapp/scripts/remote-browser-signoff.mjs",
            "scripts/check_webapp_cutover.py",
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
        summary="Admin, ticket and public pages plus control-plane backed tech panel, observer runtime/settings, drilldown, degradation search and static route handlers; legacy admin queue fallback now stays polling-only instead of subscribing `/ws_ui` to every visible ticket row.",
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
            "техпанель",
            "панель управления",
            "страница админки",
            "проверка в браузере",
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
        playbook=repo_path(LOCAL_WORKFLOW_PATH),
        skills=(
            BROWSER_CHECK_SKILL,
            RELEASE_SKILL,
            TESTS_SKILL,
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
        summary="Qt GUI, dashboard/ticket stack, request-template-aware обращение creation with `request_template_key`, searchable request-template chooser, selected-template summary cards, inline required-field errors, native date/datetime controls, replaceable/clearable file fields with attachment size labels and pre-submit checks, extended dynamic fields, server-driven priority fields, structured process preview for effective queue/priority/approval/diagnostics/deadlines with local fallback and non-blocking preview warning, post-create result panel for access code/owner/next step/deadlines/passport plus add-message action without raw SLA wording, diagnostic consent payloads, legacy fallback facts, dynamic response/resolution deadline display in Russian user-facing wording, localized validation/update microcopy, SSE bridge, initiator profiles, auth-block tray notifications and local GUI integration plus always-on diagnostics entrypoints.",
        aliases=(
            "gui",
            "ui bridge",
            "sse",
            "chat panel",
            "main window",
            "dashboard",
            "custom title bar",
            "frameless window",
            "initiator profile",
            "request template",
            "impact_scope",
            "work_continuity",
            "business_importance",
            "connection_state",
            "connection_rejected",
            "tray notification",
            "окно агента",
            "мост ui",
            "локальный интерфейс",
        ),
        first_files=(
            "pc_agent/ui_gui/main_window.py",
            "pc_agent/ui_gui/window_chrome.py",
            "pc_agent/ui_gui/chat_panel.py",
            "pc_agent/ui_gui/tray_notifications.py",
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
        playbook="pc_agent/docs/AGENT_RUNTIME_ALWAYS_ON.md",
        skills=(AGENT_RUNTIME_SKILL, TESTS_SKILL),
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
        summary="Always-on runtime lifecycle, tray behavior, Qt Widgets GUI shell/theme/assets, request-form wizard live path with searchable templates, native date/datetime controls, file replace/clear with missing/oversized attachment checks, inline form validation, structured process preview with preview-unavailable warning and post-create result panel, auth-block system notifications, runtime diagnostics/logging, mojibake-free localized lifecycle text, agent_observer_batch telemetry upload from action_trace, sticky local update request state (`requesting` / `requested` / `pending_restart`) and shutdown tracing.",
        aliases=(
            "always-on",
            "always on",
            "tray",
            "tray notification",
            "system notification",
            "device_fingerprint_mismatch",
            "runtime logs",
            "runtime logging",
            "agent shutdown",
            "close to tray",
            "trigger recommended update",
            "agent gui",
            "qt gui",
            "gui theme",
            "custom title bar",
            "frameless window",
            "ticket cards",
            "sidebar",
            "update_request_state",
            "pending_restart",
            "action trace",
            "agent_observer_batch",
            "agent observer telemetry",
            "action trace upload",
            "трей",
            "закрытие окна",
            "логи агента",
            "журнал агента",
            "рантайм агента",
            "автозапуск агента",
        ),
        first_files=(
            "pc_agent/docs/AGENT_RUNTIME_ALWAYS_ON.md",
            "pc_agent/ws_agent.py",
            "pc_agent/core/runtime_logging.py",
            "pc_agent/ui_gui/main.py",
            "pc_agent/ui_gui/main_window.py",
            "pc_agent/ui_gui/window_chrome.py",
            "pc_agent/ui_gui/chat_panel.py",
            "pc_agent/ui_gui/theme.py",
            "pc_agent/ui_gui/tickets_list_model.py",
            "pc_agent/ui_gui/assets/icons/",
            "pc_agent/ui_gui/tray_notifications.py",
        ),
        related_docs=(
            "docs/QUICK_LOOKUP.md",
            "pc_agent/docs/CODEMAP.md",
            "pc_agent/docs/AGENT_RUNTIME_ALWAYS_ON.md",
            "docs/AGENT_CAPABILITIES_AND_REQUIREMENTS.md",
        ),
        suggested_commands=(
            'python scripts/agent_find.py "tray" --dir pc_agent',
            'python scripts/agent_find.py "runtime_logging" --dir pc_agent',
            "python scripts/manage_local_agent.py status",
        ),
        mode="Agent runtime / tray / logs",
        playbook="pc_agent/docs/AGENT_RUNTIME_ALWAYS_ON.md",
        skills=(AGENT_RUNTIME_SKILL, TESTS_SKILL),
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
            repo_path(PLANS_PATH),
        ),
        exact_paths=(
            "pc_agent/ws_agent.py",
            "pc_agent/core/runtime_logging.py",
            "pc_agent/ui_gui/main.py",
            "pc_agent/ui_gui/tray_manager.py",
            "pc_agent/ui_gui/tray_notifications.py",
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
            "база",
            "база данных",
            "миграция",
            "миграции",
            "алембик",
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
        skills=(MIGRATIONS_SKILL, TESTS_SKILL),
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
        key="context_index",
        title="Context index / retrieval",
        summary="Deterministic SQLite/FTS context retrieval over canonical docs, CODEMAP, navigation topics, routes, route handlers, tests and key source symbols. Use after task_intake as a faster context finder, not as a source-of-truth replacement.",
        aliases=(
            "context index",
            "context_index",
            "search context",
            "context search",
            "retrieval",
            "rag",
            "fts",
            "sqlite index",
            "bm25",
            "symbols index",
            "routes index",
            "индекс контекста",
            "поиск контекста",
            "раг",
            "рага",
            "индексация",
            "поиск по документации",
            "поиск по символам",
            "поиск по маршрутам",
        ),
        first_files=(
            repo_path(CONTEXT_INDEX_PATH),
            "scripts/context_index.py",
            "scripts/build_context_pack.py",
            "scripts/build_context_index.py",
            "scripts/search_context_index.py",
            "scripts/test_context_index.py",
            repo_path(CODEX_WORKFLOW_PATH),
            repo_path(QUICK_LOOKUP_PATH),
        ),
        related_docs=(
            repo_path(CONTEXT_INDEX_PATH),
            repo_path(CODEX_WORKFLOW_PATH),
            repo_path(QUICK_LOOKUP_PATH),
            repo_path(ARCHITECTURE_BOUNDARIES_PATH),
            "docs/CONTEXT_EFFICIENCY.md",
        ),
        suggested_commands=(
            "python scripts/build_context_index.py --force",
            'python scripts/build_context_pack.py --topic "run_tool command_result"',
            'python scripts/search_context_index.py "run_tool command_result observer"',
            'python scripts/search_context_index.py "handshake token machine_id" --json',
            'python scripts/search_context_index.py "ToolExecutionService run_tool" --kind symbol',
            'python scripts/search_context_index.py "run_tool" --profile route --kind route',
            'python scripts/search_context_index.py "command_result retry" --profile test --kind test',
        ),
        mode="Context index / retrieval",
        skills=(DOCS_SYNC_SKILL, TESTS_SKILL),
        checks=(
            "python -m pytest scripts/test_context_index.py scripts/test_build_context_pack.py -q",
            "python scripts/build_context_index.py --force",
            'python scripts/search_context_index.py "run_tool command_result observer"',
            "python scripts/docs_inventory.py --check-links",
            "python scripts/verify_workspace.py",
        ),
        docs_to_update=(
            repo_path(CONTEXT_INDEX_PATH),
            repo_path(CODEX_WORKFLOW_PATH),
            repo_path(QUICK_LOOKUP_PATH),
            "docs/README.md",
        ),
        exact_paths=(
            "scripts/context_index.py",
            "scripts/build_context_pack.py",
            "scripts/build_context_index.py",
            "scripts/search_context_index.py",
            "scripts/test_context_index.py",
            "scripts/test_build_context_pack.py",
        ),
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
            "architecture boundary",
            "architecture boundaries",
            "codex workflow",
            "workflow",
            "dirty worktree",
            "dirty workspace",
            "debug mode",
            "root cause",
            "planning mode",
            "execute plan",
            "commit flow",
            "deploy flow",
            "ownership boundary",
            "ownership boundaries",
            "contract surface",
            "contract surfaces",
            "cross-cutting",
            "blast radius",
            "docs",
            "documentation",
            "codemap",
            "entrypoint",
            "entrypoints",
            "документация",
            "доки",
            "кодмап",
            "маршрут",
            "api маршрут",
            "контракт",
            "граница",
            "границы",
            "границы владения",
            "архитектурные границы",
            "воркфлоу",
            "рабочий цикл",
            "грязный ворктри",
            "грязный worktree",
            "режим дебага",
            "дебаг",
            "планирование",
            "коммит",
            "деплой",
            "поверхность контракта",
            "blast radius",
            "cross-cutting",
            "точка входа",
        ),
        first_files=(
            "AGENTS.md",
            "docs/README.md",
            repo_path(CODEX_WORKFLOW_PATH),
            "docs/QUICK_LOOKUP.md",
            repo_path(ARCHITECTURE_BOUNDARIES_PATH),
            repo_path(CONTEXT_INDEX_PATH),
            "scripts/build_context_pack.py",
            "scripts/build_context_index.py",
            "scripts/search_context_index.py",
            "scripts/docs_inventory.py",
            "server/docs/CODEMAP.md",
            "pc_agent/docs/CODEMAP.md",
        ),
        related_docs=(
            "AGENTS.md",
            "docs/README.md",
            repo_path(CODEX_WORKFLOW_PATH),
            "docs/QUICK_LOOKUP.md",
            repo_path(ARCHITECTURE_BOUNDARIES_PATH),
            repo_path(CONTEXT_INDEX_PATH),
            "server/docs/CODEMAP.md",
            "pc_agent/docs/CODEMAP.md",
            "docs/AGENT_CAPABILITIES_AND_REQUIREMENTS.md",
            "docs/CONTEXT_EFFICIENCY.md",
        ),
        suggested_commands=(
            "python scripts/task_intake.py --task \"add new API route\"",
            "python scripts/build_context_pack.py --topic \"<topic>\"",
            "python scripts/docs_inventory.py --check-links",
            "python scripts/diff_context.py",
        ),
        mode="Docs + CODEMAP",
        skills=(DOCS_SYNC_SKILL,),
        checks=("python scripts/verify_workspace.py",),
        docs_to_update=(
            "AGENTS.md",
            "docs/README.md",
            repo_path(CODEX_WORKFLOW_PATH),
            repo_path(QUICK_LOOKUP_PATH),
            repo_path(ARCHITECTURE_BOUNDARIES_PATH),
            repo_path(CONTEXT_INDEX_PATH),
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
        summary="Launcher builds, self-update, upload, canary rollout, recommended-version behavior, single-flight pending markers, truthful scheduled command results, launcher rollback after immediate crash, agent telemetry evidence for update flows and end-to-end update tracing.",
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
            "update_request_state",
            "pending_restart",
            "requested",
            "requesting",
            "truthful scheduled",
            "last_failed_launch",
            "update_history",
            "agent.update.apply",
            "agent.update.command",
            "agent observer update",
            "update observer telemetry",
            "обновление агента",
            "обновить агента",
            "самообновление",
            "лаунчер",
            "раскатка",
            "канарейка",
            "рекомендуемая версия",
            "доступное обновление",
        ),
        first_files=(
            "pc_agent/docs/AGENT_UPDATE_WORKFLOW.md",
            "pc_agent/docs/SELF_UPDATE.md",
            "pc_agent/core/orchestrator.py",
            "pc_agent/launcher/installer.py",
            "server/docs/AGENT_UPDATES_API.md",
            "pc_agent/version.py",
        ),
        related_docs=(
            repo_path(QUICK_LOOKUP_PATH),
            "pc_agent/docs/AGENT_UPDATE_WORKFLOW.md",
            "pc_agent/docs/SELF_UPDATE.md",
            "server/docs/AGENT_UPDATES_API.md",
            repo_path(AGENT_CODEMAP_PATH),
            "docs/AGENT_CAPABILITIES_AND_REQUIREMENTS.md",
        ),
        suggested_commands=(
            'python scripts/agent_find.py "launcher" --dir pc_agent',
            'python scripts/agent_find.py "agent_builds" --dir server',
            "python scripts/diff_context.py",
        ),
        mode="Agent updates / rollout",
        playbook="pc_agent/docs/AGENT_UPDATE_WORKFLOW.md",
        skills=(AGENT_UPDATES_SKILL, TESTS_SKILL),
        checks=(
            "python scripts/verify_workspace.py",
            "python -m pytest pc_agent/tests/ -v --tb=short",
            "python -m pytest server/tests/test_p0_workbench_update_contracts.py -v --tb=short",
            "python pc_agent/build_windows_release_v2.py",
            "python -m pytest pc_agent/tests/test_self_update_runtime.py pc_agent/tests/test_launcher_main.py pc_agent/tests/test_main_window_update_status.py -v --tb=short",
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
            "pc_agent/core/orchestrator.py",
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
        summary="Trace overlay, bounded action rows with opt-in action-span sync, pushed agent_observer_events telemetry, playbook_run/playbook_step_run roots, module_reconcile/web_auth/observer_runtime audit roots, route/playbook filters, retention/sampling settings, backfill health, degradation queries, observer correlation search, Codex-friendly diagnostics bundle, live coverage canary reports, full-ticket observer summary counts, ticket-local signature occurrence counts, single-flight UI polling, the canonical `/support` ticket-trace drawer, and the `/app/admin/observer` workbench with quick/traces/signatures/degradations/runtime tabs, global mode and evidence-source trace detail.",
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
            "diagnostics bundle",
            "observer search",
            "trace bundle",
            "agent_observer_events",
            "agent_observer_batch",
            "agent telemetry",
            "playbook_run",
            "playbook_step_run",
            "step_run_id",
            "module_reconcile",
            "web_auth",
            "observer_runtime",
            "route filter",
            "трасса",
            "трейс",
            "наблюдаемость",
            "деградация",
            "деградации",
            "сигнатура",
            "оверлей",
        ),
        first_files=(
            "server/observer/service.py",
            "server/observer/runtime.py",
            "server/app/repos/agent_observer_events_repo.py",
            "server/auth/middleware.py",
            "server/modules/reconcile.py",
            "server/tech/handlers.py",
            "pc_agent/core/action_trace.py",
            "pc_agent/ws_agent.py",
            "webapp/src/features/tech/api.ts",
            "webapp/src/features/tech/observer-evidence.ts",
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
            'python -m pytest server/tests/test_observer_agent_telemetry_projection.py server/tests/test_observer_playbook_projection.py -q',
            "GUI check via MCP at http://192.168.100.17:8666/admin",
        ),
        mode="Observer / tracing",
        skills=(
            DOCS_SYNC_SKILL,
            BROWSER_CHECK_SKILL,
            TESTS_SKILL,
            OBSERVER_DIAGNOSTICS_SKILL,
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
        ),
        path_prefixes=(
            "server/observer/",
            "shared/",
        ),
        exact_paths=(
            "server/tech/handlers.py",
            "server/auth/middleware.py",
            "server/modules/reconcile.py",
            "server/app/repos/agent_observer_events_repo.py",
            "server/app/repos/observer_settings_repo.py",
            "server/admin.html",
            "server/admin.js",
            "pc_agent/core/action_trace.py",
            "pc_agent/ws_agent.py",
            "pc_agent/core/orchestrator.py",
            "pc_agent/modules/base_module.py",
            "scripts/run_observer_canary_suite.py",
            "webapp/src/features/tech/api.ts",
            "webapp/src/features/tech/observer-evidence.ts",
            "webapp/src/features/tech/observer-workbench-api.ts",
            "webapp/src/features/tech/observer-trace-drilldown.tsx",
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
            "план",
            "планы",
            "планирование",
            "передача контекста",
            "длинная задача",
        ),
        first_files=(
            "PLANS.md",
            "AGENTS.md",
        ),
        related_docs=(
            "PLANS.md",
            "AGENTS.md",
            "docs/AGENT_CAPABILITIES_AND_REQUIREMENTS.md",
            "docs/LOCAL_WORKFLOW.md",
        ),
        suggested_commands=(
            "python scripts/verify_workspace.py",
        ),
        mode="Planning / handoff",
        skills=(PLANS_SKILL, RELEASE_SKILL),
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
        summary="Local verification, layered pytest CI, deploy to Linux, runtime control, canonical server/control wrappers, smoke and browser checks.",
        aliases=(
            "release",
            "deploy",
            "smoke",
            "browser",
            "remote stack",
            "verify workspace",
            "релиз",
            "выкладка",
            "деплой",
            "дымовой тест",
            "смоук",
            "удаленный стенд",
            "проверка рабочей копии",
        ),
        first_files=(
            "scripts/verify_workspace.py",
            "scripts/docs_inventory.py",
            "scripts/build_context_pack.py",
            "scripts/run_ci_suite.py",
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
            "docs/LOCAL_WORKFLOW.md",
            "docs/TESTING_RULES.md",
            "docs/AGENT_CAPABILITIES_AND_REQUIREMENTS.md",
        ),
        suggested_commands=(
            "python scripts/verify_workspace.py",
            "python scripts/release_server_to_remote.py",
            "python scripts/manage_remote_stack.py status control",
        ),
        mode="Release / deploy",
        playbook=repo_path(LOCAL_WORKFLOW_PATH),
        skills=(RELEASE_SKILL, TESTS_SKILL),
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
            "scripts/docs_inventory.py",
            "scripts/build_context_pack.py",
        ),
        required_docs=(
            "AGENTS.md",
            repo_path(CODEX_WORKFLOW_PATH),
            "docs/QUICK_LOOKUP.md",
            repo_path(ARCHITECTURE_BOUNDARIES_PATH),
            "docs/CONTEXT_EFFICIENCY.md",
        ),
    ),
    DriftRule(
        key="context_index_harness",
        title="Context index changed",
        reason="Context index rules and retrieval commands must stay aligned with workflow and navigation docs.",
        exact_paths=(
            "scripts/context_index.py",
            "scripts/build_context_pack.py",
            "scripts/build_context_index.py",
            "scripts/search_context_index.py",
            "scripts/test_context_index.py",
            "scripts/test_build_context_pack.py",
        ),
        required_docs=(
            repo_path(CONTEXT_INDEX_PATH),
            repo_path(CODEX_WORKFLOW_PATH),
            "docs/QUICK_LOOKUP.md",
            "docs/README.md",
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
            "docs/AGENT_CAPABILITIES_AND_REQUIREMENTS.md",
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
            "docs/LOCAL_WORKFLOW.md",
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
            "server/auth/connection_request_handlers.py",
            "server/websocket/agent_handshake.py",
            "server/agents/agent_builds_handlers.py",
            "server/tech/runtime_audit.py",
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
        key="registry_objects",
        title="Registry object flow changed",
        reason="Registry schema, auto-ingest, profile sync, request-form picker options and typed registry UI must stay discoverable in navigation docs.",
        path_prefixes=("server/registry/",),
        exact_paths=(
            "server/app/repos/registry_repo.py",
            "server/web_api/registry_handlers.py",
            "server/routes.py",
            "server/app/db/models.py",
            "server/tickets/create_flow.py",
            "server/websocket/agent_handshake.py",
            "server/web_api/support_handlers.py",
            "server/web_api/dto/support.py",
            "pc_agent/ui_gui/chat_panel.py",
            "pc_agent/ui_gui/server_api.py",
            "webapp/src/pages/admin/registry-page.tsx",
            "webapp/src/features/admin/api.ts",
        ),
        required_artifacts_all=("docs/QUICK_LOOKUP.md", "scripts/navigation_catalog.py"),
        required_docs=(
            "server/docs/CODEMAP.md",
            "pc_agent/docs/CODEMAP.md",
            "docs/QUICK_LOOKUP.md",
            "PLANS.md",
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
    for value in (*topic.first_files, *topic.related_docs, *topic.docs_to_update):
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
