import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DiagnosticCenterPanel } from "./diagnostic-center-panel";
import { DiagnosticProviderConfigPanel } from "./provider-config-panel";

vi.mock("../auth/session-provider", () => ({
  useSession: () => ({
    session: {
      permissions: [
        "ticket.tool.run",
        "module.tool.run.low_risk",
        "diagnostics.create_manual_evidence",
        "ticket.passport.manage",
      ],
    },
  }),
}));

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function renderWithQueryClient(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("DiagnosticCenterPanel", () => {
  it("renders capability readiness and routes a capability run through the diagnostics API", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/support/tickets/ticket-1/diagnostics/overview") {
        return jsonResponse({
          status: "success",
          data: {
            ticket_id: "ticket-1",
            device_id: "device-1",
            status: "ok",
            summary: "Есть базовые диагностические данные.",
            profile: {
              id: "generic",
              version: "1",
              title: "Generic diagnostics",
              recommended_capabilities: ["diag.logs.collect"],
              recommended_playbooks: [],
              required_evidence_kinds: [],
              optional_evidence_kinds: [],
            },
            evidence_counts: { ok: 1, warning: 0, error: 0 },
            perspectives: {},
            latest_evidence: [],
            latest_operations: [],
            latest_playbooks: [],
            remote_assist: { count: 0, latest: null },
            observer: { root_trace_id: null, available: false },
            artifacts: { count: 0, items: [] },
            findings: [],
            recommended_actions: [],
          },
        });
      }
      if (url === "/api/tickets/ticket-1/diagnostics/capabilities") {
        return jsonResponse({
          status: "ok",
          count: 2,
          capabilities: [
            {
              id: "diag.logs.collect",
              title: "Collect diagnostic logs",
              provider_id: "diag_logs",
              provider_type: "agent_builtin",
              source: "builtin",
              execution_target: "agent_builtin",
              risk_level: "low",
              readiness: "available",
              reason: null,
              actions: ["run"],
              requires_consent: false,
              requires_integration: false,
              integration_key: null,
              install_required_on_agent: false,
              evidence: {
                produces_evidence: true,
                kind: "logs.bundle",
                domain: "logs",
                perspective: "endpoint",
                passport_eligible: true,
              },
              artifacts: { may_produce_artifacts: true, artifact_kinds: ["logs_zip"] },
            },
            {
              id: "zabbix.problems.lookup",
              title: "Zabbix problems",
              provider_id: "zabbix_connector",
              provider_type: "server_connector",
              source: "server_connector",
              execution_target: "server_connector",
              risk_level: "low",
              readiness: "integration_not_configured",
              reason: "Required integration is not configured",
              actions: ["configure_integration"],
              requires_consent: false,
              requires_integration: true,
              integration_key: "zabbix",
              install_required_on_agent: false,
              evidence: {
                produces_evidence: true,
                kind: "monitoring.problem",
                domain: "monitoring",
                perspective: "monitoring",
              },
            },
          ],
        });
      }
      if (url === "/api/tickets/ticket-1/diagnostics/evidence") {
        return jsonResponse({
          status: "ok",
          evidence: [
            {
              id: "ev-1",
              ticket_id: "ticket-1",
              session_id: null,
              step_id: null,
              source_type: "operation",
              source_id: "op-1",
              provider_id: "diag_logs",
              capability_id: "diag.logs.collect",
              kind: "logs.bundle",
              domain: "logs",
              perspective: "endpoint",
              title: "Logs bundle",
              summary: "logs.zip",
              status: "ok",
              severity: null,
              confidence: null,
              observed_at: "2026-05-12T06:00:00Z",
              normalized_payload: {},
              artifact_refs: [],
              trace_id: null,
              passport_eligible: true,
              selected_for_passport: false,
            },
          ],
        });
      }
      if (url === "/api/tickets/ticket-1/diagnostics/sessions") {
        return jsonResponse({ status: "ok", sessions: [] });
      }
      if (url === "/api/tickets/ticket-1/diagnostics/findings") {
        return jsonResponse({ status: "ok", findings: [] });
      }
      if (url === "/api/tickets/ticket-1/diagnostics/capabilities/diag.logs.collect/run" && init?.method === "POST") {
        return jsonResponse({
          status: "success",
          capability_id: "diag.logs.collect",
          operation_id: "op-2",
          diagnostic_evidence_id: "ev-2",
          evidence_persisted: true,
        });
      }
      return jsonResponse({ status: "error", error: `unexpected ${url}` }, 500);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithQueryClient(<DiagnosticCenterPanel ticketId="ticket-1" />);

    expect(await screen.findByText("diag.logs.collect")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Запустить"));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/tickets/ticket-1/diagnostics/capabilities/diag.logs.collect/run",
        expect.objectContaining({ method: "POST" }),
      );
    });
    expect(await screen.findByText("Evidence создано: ev-2")).toBeInTheDocument();
  });

  it("creates manual evidence from the diagnostics panel", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/diagnostics/overview")) {
        return jsonResponse({
          status: "success",
          data: {
            ticket_id: "ticket-1",
            device_id: null,
            status: "unknown",
            summary: "Нет данных.",
            profile: { id: "generic", version: "1", title: "Generic", recommended_capabilities: [], recommended_playbooks: [], required_evidence_kinds: [], optional_evidence_kinds: [] },
            evidence_counts: {},
            perspectives: {},
            latest_evidence: [],
            latest_operations: [],
            latest_playbooks: [],
            remote_assist: { count: 0, latest: null },
            observer: { root_trace_id: null, available: false },
            artifacts: { count: 0, items: [] },
            findings: [],
            recommended_actions: [],
          },
        });
      }
      if (url === "/api/tickets/ticket-1/diagnostics/capabilities") {
        return jsonResponse({ status: "ok", capabilities: [], count: 0 });
      }
      if (url === "/api/tickets/ticket-1/diagnostics/evidence") {
        return jsonResponse({ status: "ok", evidence: [] });
      }
      if (url === "/api/tickets/ticket-1/diagnostics/sessions") {
        return jsonResponse({ status: "ok", sessions: [] });
      }
      if (url === "/api/tickets/ticket-1/diagnostics/findings") {
        return jsonResponse({ status: "ok", findings: [] });
      }
      if (url === "/api/tickets/ticket-1/diagnostics/evidence/manual" && init?.method === "POST") {
        return jsonResponse({
          status: "ok",
          evidence: {
            id: "manual-1",
            ticket_id: "ticket-1",
            title: "Checked with user",
            status: "info",
          },
        }, 201);
      }
      return jsonResponse({ status: "error", error: `unexpected ${url}` }, 500);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithQueryClient(<DiagnosticCenterPanel ticketId="ticket-1" />);

    fireEvent.click(await screen.findByText("Добавить manual evidence"));
    fireEvent.change(screen.getByPlaceholderText("Что проверено"), { target: { value: "Checked with user" } });
    fireEvent.change(screen.getByPlaceholderText("Краткий результат"), { target: { value: "User confirms issue" } });
    fireEvent.click(screen.getByText("Сохранить факт"));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/tickets/ticket-1/diagnostics/evidence/manual",
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining("Checked with user"),
        }),
      );
    });
  });
});

describe("DiagnosticProviderConfigPanel", () => {
  it("saves a redacted provider config through the web admin alias", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/admin/diagnostics/providers/configs") {
        return jsonResponse({ status: "ok", provider_configs: [], count: 0 });
      }
      if (url === "/api/web/admin/diagnostics/providers/configs/zabbix_connector" && init?.method === "PUT") {
        return jsonResponse({
          status: "ok",
          provider_config: {
            id: "cfg-1",
            provider_id: "zabbix_connector",
            provider_type: "server_connector",
            integration_key: "zabbix",
            enabled: true,
            status: "ready",
            config: { api_url: "https://zabbix.example/api_jsonrpc.php" },
            redaction: {},
            health: {},
            credential_refs: [{ id: "ref-1", credential_key: "api_token", secret_ref: "***redacted***", status: "ready" }],
          },
        });
      }
      return jsonResponse({ status: "error", error: `unexpected ${url}` }, 500);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithQueryClient(<DiagnosticProviderConfigPanel />);

    expect(await screen.findByText("zabbix_connector")).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText("secret://zabbix/api-token"), {
      target: { value: "secret://zabbix/api-token" },
    });
    fireEvent.click(screen.getByText("Сохранить provider config"));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/admin/diagnostics/providers/configs/zabbix_connector",
        expect.objectContaining({
          method: "PUT",
          body: expect.stringContaining("secret://zabbix/api-token"),
        }),
      );
    });
    expect(await screen.findByText("Provider config сохранён: zabbix_connector")).toBeInTheDocument();
  });
});
