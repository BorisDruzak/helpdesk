import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { RouterProvider, createMemoryRouter, type RouteObject } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SessionProvider } from "../features/auth/session-provider";
import { QueryProvider } from "./providers/query-provider";
import { appRoutes } from "./router";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json"
    }
  });
}

function renderApp(initialEntries: string[], fetchMock: typeof fetch) {
  vi.stubGlobal("fetch", fetchMock);

  const router = createMemoryRouter(appRoutes, {
    initialEntries
  });

  render(
    <QueryProvider>
      <SessionProvider>
        <RouterProvider router={router} />
      </SessionProvider>
    </QueryProvider>
  );

  return { router };
}

function collectRoutePaths(routes: RouteObject[]): string[] {
  const paths: string[] = [];
  const visit = (route: RouteObject) => {
    if (route.path) {
      paths.push(route.path);
    }
    route.children?.forEach(visit);
  };
  routes.forEach(visit);
  return paths;
}

function createSupportSession() {
  return {
    user_login: "support1",
    actor_role: "support",
    auth_type: "ui_token",
    default_workspace: "support",
    available_workspaces: ["support"],
    permissions: [
      "workspace.support.view",
      "ticket.queue.view",
      "ticket.detail.view",
      "ticket.comment.public",
      "ticket.comment.internal",
      "ticket.status.change",
      "ticket.playbook.run",
      "ticket.tool.run",
      "module.tool.run.low_risk",
      "module.tool.run.high_risk",
      "ticket.passport.manage",
      "settings.view",
    ]
  };
}

function createSupportKnowledgeManagerSession() {
  return {
    ...createSupportSession(),
    default_workspace: "admin",
    available_workspaces: ["admin", "support"],
    permissions: [
      ...createSupportSession().permissions,
      "workspace.admin.view",
      "knowledge.metadata.manage",
    ]
  };
}

function createSupportAdminWorkspaceOnlySession() {
  return {
    ...createSupportSession(),
    default_workspace: "admin",
    available_workspaces: ["admin", "support"],
    permissions: [
      ...createSupportSession().permissions,
      "workspace.admin.view",
    ]
  };
}

function createAdminSession() {
  return {
    user_login: "admin1",
    actor_role: "admin",
    auth_type: "ui_token",
    default_workspace: "admin",
    available_workspaces: ["admin", "support"],
    permissions: [
      "workspace.admin.view",
      "workspace.support.view",
      "ticket.queue.view",
      "ticket.detail.view",
      "ticket.comment.public",
      "ticket.comment.internal",
      "ticket.status.change",
      "ticket.playbook.run",
      "ticket.tool.run",
      "module.tool.run.low_risk",
      "module.tool.run.high_risk",
      "ticket.passport.manage",
      "admin.inventory.view",
      "knowledge.metadata.manage",
      "admin.registry.view",
      "admin.modules.view",
      "admin.forms.view",
      "admin.playbooks.view",
      "admin.observer.view",
      "admin.access.view",
      "settings.view",
    ]
  };
}

function createRequesterSession() {
  return {
    user_login: "requester@example.test",
    actor_role: "user",
    auth_type: "web_session",
    default_workspace: "requester",
    available_workspaces: ["requester"],
    permissions: ["workspace.requester.view"],
    permissions_version: "phase-c",
  };
}

function createRequesterFetchMock() {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);

    if (url.endsWith("/api/web/session/me")) {
      return jsonResponse({ status: "success", data: createRequesterSession() });
    }

    if (url.endsWith("/api/web/notifications/unread_count")) {
      return jsonResponse({ status: "ok", unread_count: 0 });
    }

    if (url.endsWith("/api/web/requester/bootstrap")) {
      return jsonResponse({
        status: "success",
        data: {
          workspace: "requester",
          profile: {
            person_id: "person-1",
            display_name: "Иван Петров",
            full_name: "Иван Петров",
            email: "requester@example.test",
            phone: "+7 343 000-00-01",
            department_id: "dept-it",
            location_id: "loc-ekb",
            status: "active",
          },
          profile_completion: {
            complete: true,
            required: true,
            status: "complete",
            required_fields: [],
            missing_fields: [],
            setup_path: "/app/requester/profile/setup",
            blocks: {
              ticket_create: false,
              ticket_preview: false,
              knowledge_requester_actions: false,
              device_binding_confirmation: false,
            },
          },
          profile_schema: { fields: [], custom_fields: [], required_fields: [] },
          requester_context: {
            profile: { full_name: "Иван Петров", department: "ИТ", location: "Екатеринбург" },
            device: null,
            form_prefill: {},
            routing_facts: {},
            summary: [],
          },
          devices: [],
          active_bindings: [],
          pending_registration_claims: [],
          open_ticket_count: 0,
          tickets_requiring_user_action_count: 0,
          pending_consent_count: 0,
          recent_tickets: [],
          feature_flags: {
            requester_ticket_create: true,
            requester_owned_device_create: true,
            requester_no_device_create: true,
          },
          policies: { device_selection_required: false },
        },
      });
    }

    if (url.endsWith("/api/web/requester/tickets") && init?.method !== "POST") {
      return jsonResponse({ status: "success", data: { tickets: [] } });
    }

    if (url.endsWith("/api/web/requester/consents?status=pending")) {
      return jsonResponse({ status: "success", data: { consents: [] } });
    }

    if (url === "/public_api/ticket_forms/current?pack_key=request_forms") {
      return jsonResponse({
        status: "ok",
        pack: {
          key: "request_forms",
          version: "phase-c",
          forms: [
            {
              key: "workplace_issue",
              title: "Проблема с рабочим местом",
              fields: [],
              availability_policy: { available_without_agent_binding: true },
            },
          ],
        },
      });
    }

    if (url.endsWith("/api/service-catalog/current")) {
      return jsonResponse({ status: "ok", catalog_version: "phase-c", services: [], offerings: [], categories: [] });
    }

    if (url.endsWith("/api/knowledge/suggest") && init?.method === "POST") {
      return jsonResponse({ status: "ok", suggestions: [], known_errors: [], workarounds: [] });
    }

    throw new Error(`Unexpected fetch: ${url}`);
  });
}

function createKnowledgeMetadataPayload() {
  return {
    status: "ok",
    metadata: {
      spaces: [{ space_id: "space-1", code: "it", title: "IT", visibility: "requester", lifecycle_status: "active" }],
      taxonomy_terms: [],
      property_definitions: [],
      applicability_rules: [],
      quality_models: [],
      item_metadata: [],
      summary: {
        taxonomy_terms_total: 0,
        taxonomy_terms_active: 0,
        property_definitions_total: 0,
        property_definitions_active: 0,
        applicability_rules_total: 0,
        applicability_rules_active: 0,
        quality_models_total: 0,
        quality_models_active: 0,
        item_metadata_total: 0,
      },
    },
  };
}

function createKnowledgeItemsPayload() {
  return { status: "ok", items: [] };
}

function createCommandCenterPayload() {
  return {
    generated_at: "2026-05-19T10:00:00+00:00",
    scope: "team",
    filters: {
      queue: null,
      assignee: null,
      query: null,
      window_hours: 24,
      limit_per_section: 8
    },
    summary: {
      total_attention_items: 0,
      critical_count: 0,
      warning_count: 0,
      info_count: 0,
      new_unassigned_count: 0,
      operator_action_count: 0,
      unread_user_messages_count: 0,
      sla_risk_count: 0,
      ola_risk_count: 0,
      pending_approval_count: 0,
      pending_consent_count: 0,
      failed_operation_count: 0,
      agent_offline_active_count: 0,
      diagnostics_recommended_count: 0,
      closure_blocked_count: 0,
      similar_spikes_count: 0
    },
    sections: [],
    metadata: {}
  };
}

function createWorkspaceSummaryPayload() {
  return {
    views: {},
    queues: [],
    smart_view_counts: [],
    smart_view_options: []
  };
}

function createTechOverviewPayload() {
  return {
    status: "ok",
    overview: {
      postgres_health: { status: "ok", label: "PostgreSQL" },
      agent_health: { total: 3, online: 2, stale: 1, offline: 0 },
      operations_health: { stuck_count: 1, failed_recent_count: 2 },
      update_health: { pending_updates: 1, failed_updates: 0 },
      service_health: { http: "running", control_plane: "running" },
      generated_at: "2026-05-21T10:00:00+00:00",
    },
  };
}

function createTechAlertsPayload() {
  return {
    status: "ok",
    alerts: [
      {
        severity: "warning",
        title: "Операции требуют внимания",
        description: "Есть зависшая операция.",
        created_at: "2026-05-21T10:01:00+00:00",
      },
    ],
  };
}

function createTechLogsPayload() {
  return {
    status: "ok",
    logs: [
      {
        ts: "2026-05-21T10:02:00+00:00",
        level: "ERROR",
        logger: "server.housekeeping",
        message: "Inventory refresh runtime already running",
      },
    ],
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("appRoutes", () => {
  it("keeps requester routes explicit without the legacy section wildcard", () => {
    const paths = collectRoutePaths(appRoutes);

    expect(paths).toContain("requester");
    expect(paths).toContain("requester/new");
    expect(paths).toContain("requester/tickets");
    expect(paths).toContain("requester/profile");
    expect(paths).toContain("requester/devices");
    expect(paths).toContain("requester/create");
    expect(paths).not.toContain("requester/:section");
  });

  it("redirects anonymous users to the redesigned login page", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);

      if (url.endsWith("/api/web/session/me")) {
        return new Response("", { status: 401 });
      }

      throw new Error(`Unexpected fetch: ${url}`);
    });

    renderApp(["/app/tickets"], fetchMock as typeof fetch);

    expect(await screen.findByRole("heading", { name: "Добро пожаловать" })).toBeInTheDocument();
    expect(screen.getByLabelText("Логин")).toBeInTheDocument();
    expect(screen.getByLabelText("Пароль")).toBeInTheDocument();
    expect(screen.queryByText(/admin \/ admin123/)).not.toBeInTheDocument();
    expect(screen.queryByText(/op1 \/ 1\.Abcdef/)).not.toBeInTheDocument();
  });

  it("opens the operator command center for support role and keeps tickets in support menu", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);

      if (url.endsWith("/api/web/session/me")) {
        return jsonResponse({
          status: "success",
          data: createSupportSession()
        });
      }

      if (url.startsWith("/api/web/support/command-center")) {
        return jsonResponse({
          status: "success",
          data: createCommandCenterPayload()
        });
      }

      if (url.startsWith("/api/web/support/workspace/summary")) {
        return jsonResponse({
          status: "success",
          data: createWorkspaceSummaryPayload()
        });
      }

      throw new Error(`Unexpected fetch: ${url}`);
    });

    renderApp(["/app"], fetchMock as typeof fetch);

    expect(await screen.findByRole("heading", { name: "Центр действий" })).toBeInTheDocument();
    expect((await screen.findAllByRole("link", { name: /Центр действий/ })).length).toBeGreaterThan(0);
    expect((await screen.findAllByRole("link", { name: /Тикеты/ })).length).toBeGreaterThan(0);
    expect(screen.queryByRole("link", { name: /Инвентарь устройств/ })).not.toBeInTheDocument();
  });

  it("renders /app/support as the operator command center", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);

      if (url.endsWith("/api/web/session/me")) {
        return jsonResponse({
          status: "success",
          data: createSupportSession()
        });
      }

      if (url.startsWith("/api/web/support/command-center")) {
        return jsonResponse({
          status: "success",
          data: createCommandCenterPayload()
        });
      }

      if (url.startsWith("/api/web/support/workspace/summary")) {
        return jsonResponse({
          status: "success",
          data: createWorkspaceSummaryPayload()
        });
      }

      throw new Error(`Unexpected fetch: ${url}`);
    });

    const { router } = renderApp(["/app/support"], fetchMock as typeof fetch);

    expect(await screen.findByRole("heading", { name: "Центр действий" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/app/support");
  });

  it("returns support user from /app/admin to tickets after login", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);

      if (url.endsWith("/api/web/session/me")) {
        return new Response("", { status: 401 });
      }

      if (url.endsWith("/api/web/session/login")) {
        expect(init?.method).toBe("POST");
        expect(init?.body).toBe(JSON.stringify({ login: "support", password: "secret" }));

        return jsonResponse({
          status: "success",
          data: createSupportSession()
        });
      }

      if (url.startsWith("/api/web/support/command-center")) {
        return jsonResponse({
          status: "success",
          data: createCommandCenterPayload()
        });
      }

      if (url.startsWith("/api/web/support/workspace/summary")) {
        return jsonResponse({
          status: "success",
          data: createWorkspaceSummaryPayload()
        });
      }

      throw new Error(`Unexpected fetch: ${url}`);
    });

    renderApp(["/app/admin"], fetchMock as typeof fetch);

    fireEvent.change(await screen.findByLabelText("Логин"), {
      target: { value: "support" }
    });
    fireEvent.change(screen.getByLabelText("Пароль"), {
      target: { value: "secret" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Войти" }));

    expect(await screen.findByRole("heading", { name: "Центр действий" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Инвентарь устройств/ })).not.toBeInTheDocument();
  });

  it("renders /app/admin as the admin center for admin session", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);

      if (url.endsWith("/api/web/session/me")) {
        return jsonResponse({
          status: "success",
          data: createAdminSession()
        });
      }

      if (url.endsWith("/api/web/notifications/unread_count")) {
        return jsonResponse({ status: "ok", unread_count: 0 });
      }

      if (url.endsWith("/api/web/admin/connection-requests")) {
        return jsonResponse({ status: "success", data: { connection_requests: [] } });
      }

      throw new Error(`Unexpected fetch: ${url}`);
    });

    renderApp(["/app/admin"], fetchMock as typeof fetch);

    expect(await screen.findByRole("heading", { name: "Центр администрирования" })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: /Устройства и агенты/ })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Тикеты/ })).not.toBeInTheDocument();
  });

  it("opens Knowledge metadata editor for a support knowledge manager group session", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);

      if (url.endsWith("/api/web/session/me")) {
        return jsonResponse({
          status: "success",
          data: createSupportKnowledgeManagerSession()
        });
      }

      if (url.endsWith("/api/web/notifications/unread_count")) {
        return jsonResponse({ status: "ok", unread_count: 0 });
      }

      if (url === "/api/web/knowledge/metadata") {
        return jsonResponse(createKnowledgeMetadataPayload());
      }

      if (url === "/api/web/knowledge/items") {
        return jsonResponse(createKnowledgeItemsPayload());
      }

      throw new Error(`Unexpected fetch: ${url}`);
    });

    const { router } = renderApp(["/app/admin/knowledge/metadata"], fetchMock as typeof fetch);

    expect(await screen.findByRole("heading", { name: "Метаданные знаний" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/app/admin/knowledge/metadata");
    expect((await screen.findAllByText("Метаданные знаний")).length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByRole("link", { name: /Инвентарь устройств/ })).not.toBeInTheDocument();
  });

  it("does not open Knowledge metadata editor for support without knowledge manager permission", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);

      if (url.endsWith("/api/web/session/me")) {
        return jsonResponse({
          status: "success",
          data: createSupportAdminWorkspaceOnlySession()
        });
      }

      if (url.endsWith("/api/web/notifications/unread_count")) {
        return jsonResponse({ status: "ok", unread_count: 0 });
      }

      if (url.endsWith("/api/web/admin/connection-requests")) {
        return jsonResponse({ status: "success", data: { connection_requests: [] } });
      }

      throw new Error(`Unexpected fetch: ${url}`);
    });

    const { router } = renderApp(["/app/admin/knowledge/metadata"], fetchMock as typeof fetch);

    expect(await screen.findByRole("heading", { name: "Центр администрирования" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/app/admin");
    expect(fetchMock).not.toHaveBeenCalledWith("/api/web/knowledge/metadata", expect.anything());
  });

  it("opens Capability Studio for admin users", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);

      if (url.endsWith("/api/web/session/me")) {
        return jsonResponse({
          status: "success",
          data: createAdminSession()
        });
      }

      if (url.startsWith("/api/web/admin/capabilities?")) {
        return jsonResponse({
          status: "ok",
          count: 2,
          capabilities: [
            {
              id: "server.dns.resolve",
              title: "DNS resolve",
              description: "Resolve DNS from server",
              provider_id: "server_builtin",
              provider_type: "server_builtin",
              execution_target: "server_builtin",
              tool_kind: "diagnostic",
              risk_level: "low",
              readiness: "available",
              reason: null,
              actions: ["run"],
              requires_consent: false,
              requires_integration: false,
              install_required_on_agent: false,
              evidence: {
                produces_evidence: true,
                kind: "network.dns",
                domain: "network",
                perspective: "server",
                passport_eligible: true
              },
              artifacts: { may_produce_artifacts: false, artifact_kinds: [] }
            },
            {
              id: "zabbix.problems.lookup",
              title: "Zabbix problems",
              provider_id: "zabbix",
              provider_type: "server_connector",
              execution_target: "server_connector",
              tool_kind: "diagnostic",
              risk_level: "low",
              readiness: "integration_not_configured",
              reason: "Integration is not configured",
              actions: ["configure_integration"],
              requires_consent: false,
              requires_integration: true,
              integration_key: "zabbix",
              install_required_on_agent: false,
              evidence: {
                produces_evidence: true,
                kind: "monitoring.problems",
                domain: "monitoring",
                perspective: "monitoring",
                passport_eligible: true
              },
              artifacts: { may_produce_artifacts: false, artifact_kinds: [] }
            }
          ]
        });
      }

      if (url.startsWith("/api/web/admin/capabilities/provider-configs?")) {
        return jsonResponse({ status: "ok", provider_configs: [], count: 0 });
      }

      throw new Error(`Unexpected fetch: ${url}`);
    });

    renderApp(["/app/admin/capabilities"], fetchMock as typeof fetch);

    expect(await screen.findByRole("heading", { name: "Capabilities" }, { timeout: 5000 })).toBeInTheDocument();
    expect((await screen.findAllByRole("link", { name: /Возможности/ })).length).toBeGreaterThan(0);
    expect(await screen.findByText("server.dns.resolve")).toBeInTheDocument();
    expect(await screen.findByText("zabbix.problems.lookup")).toBeInTheDocument();
  });

  it("opens the migrated tech panel for admin users", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);

      if (url.endsWith("/api/web/session/me")) {
        return jsonResponse({
          status: "success",
          data: createAdminSession()
        });
      }

      if (url.endsWith("/api/web/admin/tech/snapshot")) {
        return jsonResponse({
          generated_at: "2026-05-21T08:00:00Z",
          readiness: {
            status: "blocked",
            score: 40,
            blockers: [{ key: "postgres_reachable", title: "PostgreSQL недоступен", status: "blocked", severity: "critical", description: "PostgreSQL health check failed" }],
            warnings: [],
            gates: [{ key: "postgres_reachable", title: "PostgreSQL недоступен", status: "blocked", severity: "critical", description: "PostgreSQL health check failed" }],
          },
          security: {
            auth_mode: { db_users_enabled: true, config_fallback_enabled: false, in_memory_fallback_possible: false, status: "ok", notes: [] },
            session_cookie: { secure: false, httponly: true, samesite: "lax", status: "warning", notes: [] },
            token_channels: { query_token_allowed: true, status: "warning" },
            agent_connection_policy: { mode: "manual", status: "ok", pending_requests: 0, stale_pending_requests: 0 },
            audit: { failed_logins_recent: 0, locked_users_count: 0, invalid_agent_tokens_recent: 0 },
          },
          runtime: {
            services: [{ key: "api", title: "API", status: "ok" }],
            web_sockets: { ui_connections: 0, agent_connections: 0 },
            schedulers: { operation_watchdog: "running", ticket_sla_watchdog: "running", ticket_auto_close_watchdog: "running", inventory_scheduler: "unknown", observer_refresh_runtime: "unknown" },
          },
          database: { persistence_enabled: true, reachable: false, migrations_status: "unknown", last_backup: null, last_restore_drill: null },
          agents: { total: 0, online: 0, offline: 0, stale: 0, pending_connection_requests: 0, reprovision_required: 0, invalid_token_recent: 0, below_baseline: null, update_in_progress: 0, update_failed_recent: 0, update_timed_out_recent: 0, awaiting_handshake_confirm: 0, problem_devices: [] },
          operations: { queued_stuck: 0, sent_stuck: 0, running_stuck: 0, items: [] },
          logs: { problem_logs: [{ id: "log-1", level: "error", message: "Inventory refresh runtime already running", created_at: "2026-05-21T07:55:00Z" }] },
          alerts: [{ id: "alert-1", title: "Операции требуют внимания", severity: "critical" }],
          release: { gate: "unknown" },
          smoke: { status: "unknown", last_business_smoke: null, last_health_smoke: null },
          links: { observer: "/app/admin/observer", inventory: "/app/admin/inventory", device_operations: "/app/admin/device-operations", agent_updates: "/app/admin/agent-updates", command_center: "/app/support", approval_center: "/app/support/approvals", logs: "/app/admin/tech?tab=logs" },
        });
      }

      throw new Error(`Unexpected fetch: ${url}`);
    });

    renderApp(["/app/admin/tech"], fetchMock as typeof fetch);

    expect(await screen.findByRole("heading", { name: "Техпанель стенда" })).toBeInTheDocument();
    expect(await screen.findByText("BLOCKED")).toBeInTheDocument();
    expect(await screen.findByText("PostgreSQL недоступен")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /Логи и сигналы/ })).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/web/admin/tech/snapshot", { credentials: "same-origin" });
  });

  it("opens the AI integration MCP page for admin users", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);

      if (url.endsWith("/api/web/session/me")) {
        return jsonResponse({
          status: "success",
          data: createAdminSession()
        });
      }

      if (url.endsWith("/api/web/admin/ai-integration/mcp")) {
        return jsonResponse({
          status: "ok",
          generated_at: "2026-06-06T10:00:00Z",
          mcp: {
            manifest: {
              name: "helpdesk-server-debug",
              mode: "debug_readonly",
              tools: ["helpdesk_db_health", "observer_runtime_status"],
              safety: { no_business_mutation: true, no_run_tool: true },
            },
            db_health: { status: "ok", reachable: true, latency_ms: 2.1 },
            context_freshness: { status: "ok", reason: "fresh", stale_sources_count: 0 },
            runtime_status: {
              status: "ok",
              runtime_snapshot_available: true,
              confidence: "fresh",
              snapshot: {
                git_revision: "abc1234",
                service_health: { agent_ws_connections: 0 },
                mcp: { mode: "debug_readonly" },
              },
            },
            reload: {
              required_after_deploy: true,
              codex_restart_recommended: true,
              status_text: "Перезапустите MCP/Codex после deploy",
            },
          },
        });
      }

      throw new Error(`Unexpected fetch: ${url}`);
    });

    renderApp(["/app/admin/ai-integration"], fetchMock as typeof fetch);

    expect(await screen.findByRole("heading", { name: "Интеграция ИИ" })).toBeInTheDocument();
    expect(await screen.findByText("helpdesk-server-debug")).toBeInTheDocument();
    expect(await screen.findByText("debug_readonly")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/web/admin/ai-integration/mcp", { credentials: "same-origin" });
  });

  it("renders the requester shell with Russian navigation for a single-workspace user", async () => {
    const fetchMock = createRequesterFetchMock();

    renderApp(["/app/requester"], fetchMock as typeof fetch);

    expect(await screen.findByRole("heading", { name: "Мои обращения" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Рабочая зона")).not.toBeInTheDocument();
    expect(screen.getByText("Пользователь")).toBeInTheDocument();
    expect(screen.queryByText("Requester")).not.toBeInTheDocument();
    expect(screen.queryByText("Requester workspace")).not.toBeInTheDocument();
    expect(screen.getAllByText("Кабинет пользователя").length).toBeGreaterThan(0);

    const mobileNav = screen.getByRole("navigation", { name: "Навигация заявителя" });
    expect(within(mobileNav).getByRole("link", { name: "Главная" })).toHaveAttribute("href", "/app/requester");
    expect(within(mobileNav).getByRole("link", { name: "Создать обращение" })).toHaveAttribute("href", "/app/requester/new");
    expect(within(mobileNav).getByRole("link", { name: "Мои обращения" })).toHaveAttribute("href", "/app/requester/tickets");
    expect(within(mobileNav).getByRole("link", { name: "Устройства" })).toHaveAttribute("href", "/app/requester/devices");
    expect(within(mobileNav).getByRole("link", { name: "Профиль" })).toHaveAttribute("href", "/app/requester/profile");
  });

  it("redirects known legacy requester sections to explicit routes", async () => {
    const fetchMock = createRequesterFetchMock();
    const { router } = renderApp(["/app/requester/create"], fetchMock as typeof fetch);

    await waitFor(() => expect(router.state.location.pathname).toBe("/app/requester/new"));
    expect(await screen.findByRole("heading", { name: "Опишите проблему" })).toBeInTheDocument();
  });

  it("renders a requester-safe not-found page for unknown requester routes", async () => {
    const fetchMock = createRequesterFetchMock();
    const { router } = renderApp(["/app/requester/unknown-section"], fetchMock as typeof fetch);

    expect(await screen.findByRole("heading", { name: "Раздел не найден" })).toBeInTheDocument();
    expect(screen.getAllByText("Кабинет пользователя").length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "Вернуться на главную" })).toHaveAttribute("href", "/app/requester");
    expect(router.state.location.pathname).toBe("/app/requester/unknown-section");
    expect(screen.queryByText("Requester workspace")).not.toBeInTheDocument();
  });

  it("opens the dedicated requester devices route", async () => {
    const fetchMock = createRequesterFetchMock();

    renderApp(["/app/requester/devices"], fetchMock as typeof fetch);

    expect(await screen.findByRole("heading", { name: "Устройства" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Проверить владельца" })).toHaveAttribute(
      "href",
      "/app/requester/new?intent=device_owner_change",
    );
    expect(screen.queryByText("Requester workspace")).not.toBeInTheDocument();
  });

  it("opens requester help without a web session", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);

      if (url.endsWith("/api/web/session/me")) {
        return new Response("", { status: 401 });
      }

      if (url === "/public_api/ticket_forms/current?pack_key=request_forms") {
        return jsonResponse({
          status: "ok",
          pack: {
            pack_key: "request_forms",
            version: "1.0.0",
            forms: [],
          },
        });
      }

      throw new Error(`Unexpected fetch: ${url}`);
    });

    renderApp(["/app/help"], fetchMock as typeof fetch);

    expect(await screen.findByRole("heading", { name: "Создать заявку" })).toBeInTheDocument();
  });
});
