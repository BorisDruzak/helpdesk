import { fireEvent, render, screen } from "@testing-library/react";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
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

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("appRoutes", () => {
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
    expect(screen.getByText(/admin \/ admin123/)).toBeInTheDocument();
    expect(screen.getByText(/op1 \/ 1\.Abcdef/)).toBeInTheDocument();
  });

  it("opens the new tickets page for support role and hides admin menu", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);

      if (url.endsWith("/api/web/session/me")) {
        return jsonResponse({
          status: "success",
          data: createSupportSession()
        });
      }

      throw new Error(`Unexpected fetch: ${url}`);
    });

    renderApp(["/app"], fetchMock as typeof fetch);

    expect(await screen.findByRole("heading", { name: "Тикеты" })).toBeInTheDocument();
    expect((await screen.findAllByRole("link", { name: /Тикеты/ })).length).toBeGreaterThan(0);
    expect(screen.queryByRole("link", { name: /Инвентарь устройств/ })).not.toBeInTheDocument();
  });

  it("redirects /app/support to the new support ticket workspace", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);

      if (url.endsWith("/api/web/session/me")) {
        return jsonResponse({
          status: "success",
          data: createSupportSession()
        });
      }

      if (url.startsWith("/api/web/support/queue")) {
        return jsonResponse({
          status: "success",
          data: {
            scope: "all",
            query: "",
            status_filter: "all",
            smart_view: "all",
            summary: {
              visible_count: 0,
              selected_ticket_id: null,
              scope_counts: [],
              status_counts: [],
              queue_counts: [],
              smart_view_counts: [],
              smart_view_options: []
            },
            filters: {
              scope_options: [],
              status_options: [],
              smart_view_options: []
            },
            tickets: []
          }
        });
      }

      throw new Error(`Unexpected fetch: ${url}`);
    });

    const { router } = renderApp(["/app/support"], fetchMock as typeof fetch);

    expect(await screen.findByRole("heading", { name: "Тикеты" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/app/tickets");
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

    expect(await screen.findByRole("heading", { name: "Тикеты" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Инвентарь устройств/ })).not.toBeInTheDocument();
  });

  it("redirects /app/admin to inventory for admin session", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);

      if (url.endsWith("/api/web/session/me")) {
        return jsonResponse({
          status: "success",
          data: createAdminSession()
        });
      }

      throw new Error(`Unexpected fetch: ${url}`);
    });

    renderApp(["/app/admin"], fetchMock as typeof fetch);

    expect(await screen.findByRole("heading", { name: "Агенты" })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: /Инвентарь устройств/ })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: /Тикеты/ })).toBeInTheDocument();
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

    expect(await screen.findByRole("heading", { name: "Capabilities" })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: /Возможности/ })).toBeInTheDocument();
    expect(await screen.findByText("server.dns.resolve")).toBeInTheDocument();
    expect(await screen.findByText("zabbix.problems.lookup")).toBeInTheDocument();
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
