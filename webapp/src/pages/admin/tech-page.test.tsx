import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchTechPanelV2Snapshot, locateTechQuery } from "../../features/tech/tech-panel-api";
import type { TechLocatorPayload, TechPanelV2Snapshot } from "../../features/tech/tech-panel-api";
import { AdminTechPage } from "./tech-page";

vi.mock("../../features/tech/tech-panel-api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../features/tech/tech-panel-api")>();
  return {
    ...actual,
    fetchTechPanelV2Snapshot: vi.fn(),
    locateTechQuery: vi.fn(),
  };
});

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <MemoryRouter>
      <QueryClientProvider client={client}>
        <AdminTechPage />
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

function snapshot(overrides: Partial<TechPanelV2Snapshot> = {}): TechPanelV2Snapshot {
  return {
    generated_at: "2026-05-21T08:00:00Z",
    readiness: {
      status: "blocked",
      score: 42,
      blockers: [
        {
          key: "db_persistence_enabled",
          title: "DB persistence отключён",
          status: "blocked",
          severity: "critical",
          description: "ENABLE_DB_PERSISTENCE=false блокирует пилот.",
          evidence: "ENABLE_DB_PERSISTENCE=false",
        },
      ],
      warnings: [],
      gates: [
        {
          key: "db_persistence_enabled",
          title: "DB persistence отключён",
          status: "blocked",
          severity: "critical",
          description: "ENABLE_DB_PERSISTENCE=false блокирует пилот.",
          evidence: "ENABLE_DB_PERSISTENCE=false",
        },
        {
          key: "business_smoke",
          title: "Business smoke отсутствует",
          status: "warning",
          severity: "warning",
          description: "Нет свежего marker-файла business smoke.",
        },
      ],
    },
    security: {
      auth_mode: {
        db_users_enabled: true,
        config_fallback_enabled: true,
        in_memory_fallback_possible: true,
        status: "warning",
        notes: ["config fallback включён"],
      },
      session_cookie: {
        secure: false,
        httponly: true,
        samesite: "lax",
        status: "warning",
        notes: ["Secure не включён"],
      },
      token_channels: { query_token_allowed: true, query_token_attempts_recent: 2, status: "warning" },
      agent_connection_policy: {
        mode: "accept_all",
        status: "warning",
        pending_requests: 2,
        stale_pending_requests: 1,
      },
      audit: { failed_logins_recent: 3, locked_users_count: 1, invalid_agent_tokens_recent: 4 },
    },
    runtime: {
      services: [
        { key: "api", title: "API", status: "ok" },
        { key: "inventory_scheduler", title: "Inventory scheduler", status: "degraded", details: "enabled but not running" },
      ],
      web_sockets: { ui_connections: 1, agent_connections: 2 },
      schedulers: {
        operation_watchdog: "running",
        ticket_sla_watchdog: "running",
        ticket_auto_close_watchdog: "running",
        inventory_scheduler: "enabled_not_running",
        observer_refresh_runtime: "unknown",
      },
      scheduler_details: {
        inventory_scheduler: {
          enabled: true,
          running: false,
          active_task_count: 2,
          duplicate_task_detected: true,
          last_tick_at: null,
          last_error: "duplicate runtime task detected",
        },
      },
    },
    database: {
      persistence_enabled: false,
      reachable: false,
      latency_ms: null,
      database: "pc_client",
      pool_status: null,
      alembic_current: null,
      alembic_head: null,
      migrations_status: "unknown",
      last_backup: null,
      last_restore_drill: null,
    },
    agents: {
      total: 3,
      online: 1,
      offline: 1,
      stale: 1,
      pending_connection_requests: 2,
      reprovision_required: 1,
      invalid_token_recent: 4,
      below_baseline: 1,
      update_in_progress: 1,
      update_failed_recent: 1,
      update_timed_out_recent: 0,
      awaiting_handshake_confirm: 1,
      baseline: {
        min_version: "3.1.50",
        below_baseline_count: 1,
        devices: [
          {
            device_id: "device-1",
            hostname: "pc-support-01",
            agent_version: "3.1.40",
            last_seen_at: "2026-05-21T07:00:00Z",
            reasons: ["below baseline"],
            href: "/app/admin/device-operations/device-1",
          },
        ],
      },
      problem_devices: [
        {
          device_id: "device-1",
          hostname: "pc-support-01",
          status: "stale",
          reasons: ["offline", "below baseline"],
          href: "/app/admin/device-operations/device-1",
        },
      ],
    },
    operations: {
      queued_stuck: 1,
      sent_stuck: 1,
      running_stuck: 0,
      waiting_consent: 2,
      recent_failed: 3,
      outbox_backlog: 4,
      recent_nack_count: 1,
      items: [
        {
          operation_id: "op-1",
          device_id: "device-1",
          ticket_id: "ticket-1",
          kind: "collect",
          status: "queued",
          queued_at: "2026-05-21T07:00:00Z",
        },
      ],
    },
    logs: {
      problem_logs: [{ id: "log-1", level: "error", logger: "server", message: "failed", created_at: "2026-05-21T07:30:00Z" }],
      error_count: 1,
      warning_count: 0,
      critical_count: 0,
    },
    alerts: [{ id: "alert-1", title: "PostgreSQL down", severity: "critical", description: "DB unreachable" }],
    release: {
      branch: "codex/helpdesk-process-model",
      commit: "abcdef1",
      deployed_at: "2026-05-21T07:50:00Z",
      webapp_bundle_commit: "abcdef1",
      gate: "quick",
      dirty: false,
      remote_profile: "stage",
    },
    smoke: {
      last_health_smoke: { status: "success", finished_at: "2026-05-21T07:55:00Z", steps: [] },
      last_business_smoke: {
        status: "failed",
        finished_at: "2026-05-21T07:56:00Z",
        steps: [{ key: "login", status: "success" }, { key: "support_bootstrap", status: "failed" }],
      },
      status: "blocked",
    },
    links: {
      observer: "/app/admin/observer",
      inventory: "/app/admin/inventory",
      device_operations: "/app/admin/device-operations",
      agent_updates: "/app/admin/agent-updates",
      command_center: "/app/support",
      approval_center: "/app/support/approvals",
      logs: "/app/admin/tech?tab=logs",
    },
    ...overrides,
  };
}

function locatorPayload(overrides: Partial<TechLocatorPayload> = {}): TechLocatorPayload {
  return {
    status: "ok",
    query: "T-910571",
    normalized_query: "T-910571",
    generated_at: "2026-05-21T08:01:00Z",
    summary: { match_count: 1, highest_severity: "warning", primary_diagnosis: "Найден тикет с рисками." },
    matches: [
      {
        kind: "ticket",
        id: "ticket-1",
        title: "T-910571 · Pilot workstation cannot print",
        status: "in_progress",
        severity: "warning",
        reason: "Тикет открыт, есть SLA risk.",
        context: { ticket_id: "ticket-1", ticket_code: "T-910571", device_id: "device-1", hostname: "pc-support-01" },
        signals: { ticket_open: true, ticket_sla_risk: true, pending_approval: true },
        links: [
          { label: "Открыть тикет", href: "/app/tickets/ticket-1", kind: "ticket" },
          { label: "Операция", href: "/app/admin/operations/op-1", kind: "operation" },
          { label: "Device Operations", href: "/app/admin/device-operations/device-1", kind: "device_operations" },
        ],
      },
    ],
    ...overrides,
  };
}

describe("AdminTechPage v2", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the title, BLOCKED banner and all tabs", async () => {
    vi.mocked(fetchTechPanelV2Snapshot).mockResolvedValue(snapshot());

    renderPage();

    expect(await screen.findByRole("heading", { name: "Техпанель стенда" })).toBeInTheDocument();
    expect(await screen.findByText("BLOCKED")).toBeInTheDocument();
    for (const tab of ["Обзор", "Безопасность", "Runtime", "База данных", "Агенты", "Операции", "Логи и сигналы", "Релиз и smoke"]) {
      expect(screen.getByRole("button", { name: new RegExp(tab) })).toBeInTheDocument();
    }
  });

  it("shows security, database, agents, operations, logs and release details in tabs", async () => {
    vi.mocked(fetchTechPanelV2Snapshot).mockResolvedValue(snapshot());

    renderPage();
    await screen.findByText("BLOCKED");

    fireEvent.click(screen.getByRole("button", { name: /Безопасность/ }));
    expect(screen.getAllByText(/config fallback/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/query token/i).length).toBeGreaterThan(0);
    expect(screen.getByText("2 attempts")).toBeInTheDocument();
    expect(screen.getAllByText(/cookie/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/connection policy/i).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: /База данных/ }));
    expect(screen.getAllByText(/PostgreSQL/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/migrations/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/backup/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/restore drill/i).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: /Runtime/ }));
    expect(screen.getByText(/duplicate runtime task detected/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Агенты/ }));
    expect(screen.getAllByText(/online/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/offline/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/stale/i).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: /device-1/i })[0]).toHaveAttribute("href", "/app/admin/device-operations/device-1");
    expect(screen.getByText("3.1.40")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Операции/ }));
    expect(screen.getByText("op-1")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /ticket-1/i })).toHaveAttribute("href", "/app/tickets/ticket-1");

    fireEvent.click(screen.getByRole("button", { name: /Логи и сигналы/ }));
    expect(screen.getByText("PostgreSQL down")).toBeInTheDocument();
    expect(screen.getByText("failed")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Релиз и smoke/ }));
    expect(screen.getByText("codex/helpdesk-process-model")).toBeInTheDocument();
    expect(screen.getAllByText(/business smoke/i).length).toBeGreaterThan(0);
    expect(screen.getByText("support_bootstrap")).toBeInTheDocument();
  });

  it("renders empty logs state and alert list", async () => {
    vi.mocked(fetchTechPanelV2Snapshot).mockResolvedValue(
      snapshot({ logs: { problem_logs: [] }, alerts: [{ id: "a", title: "No restore drill", severity: "warning" }] }),
    );

    renderPage();
    await screen.findByText("BLOCKED");
    fireEvent.click(screen.getByRole("button", { name: /Логи и сигналы/ }));

    expect(screen.getByText("No restore drill")).toBeInTheDocument();
    expect(screen.getByText(/Проблемных логов нет/)).toBeInTheDocument();
  });

  it("renders a clear Russian API error", async () => {
    vi.mocked(fetchTechPanelV2Snapshot).mockRejectedValue(new Error("Снимок техпанели недоступен"));

    renderPage();

    await waitFor(() => expect(screen.getByText(/Снимок техпанели недоступен/)).toBeInTheDocument());
  });

  it("renders quick locator and ticket/device links", async () => {
    vi.mocked(fetchTechPanelV2Snapshot).mockResolvedValue(snapshot());
    vi.mocked(locateTechQuery).mockResolvedValue(locatorPayload());

    renderPage();
    await screen.findByText("BLOCKED");

    fireEvent.change(screen.getByPlaceholderText(/ticket, device_id, hostname/i), { target: { value: "T-910571" } });
    fireEvent.click(screen.getByRole("button", { name: "Найти" }));

    await waitFor(() => expect(locateTechQuery).toHaveBeenCalledWith("T-910571"));
    expect(await screen.findByText(/Pilot workstation cannot print/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Открыть тикет" })).toHaveAttribute("href", "/app/tickets/ticket-1");
    expect(screen.getByRole("link", { name: "Операция" })).toHaveAttribute("href", "/app/admin/operations/op-1");
    expect(screen.getByRole("link", { name: "Device Operations" })).toHaveAttribute("href", "/app/admin/device-operations/device-1");
  });

  it("renders quick locator empty and error states", async () => {
    vi.mocked(fetchTechPanelV2Snapshot).mockResolvedValue(snapshot());
    vi.mocked(locateTechQuery)
      .mockResolvedValueOnce(
        locatorPayload({
          matches: [],
          summary: { match_count: 0, highest_severity: "unknown", primary_diagnosis: "По запросу ничего не найдено." },
        }),
      )
      .mockRejectedValueOnce(new Error("Locator unavailable"));

    renderPage();
    await screen.findByText("BLOCKED");

    fireEvent.change(screen.getByPlaceholderText(/ticket, device_id, hostname/i), { target: { value: "missing-ticket" } });
    fireEvent.click(screen.getByRole("button", { name: "Найти" }));
    expect(await screen.findByText(/По запросу ничего не найдено/)).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText(/ticket, device_id, hostname/i), { target: { value: "device-1" } });
    fireEvent.click(screen.getByRole("button", { name: "Найти" }));
    expect(await screen.findByText(/Locator unavailable/)).toBeInTheDocument();
  });
});
