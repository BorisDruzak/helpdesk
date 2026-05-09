import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { ObserverQuickPanel } from "./observer-quick-panel";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function traceItem(traceId = "trace-deep-1") {
  return {
    trace_id: traceId,
    root_kind: "ticket",
    root_kind_label: "Ticket",
    status: "failed",
    status_label: "Ошибка",
    device_id: "device-1",
    ticket_id: "ticket-1",
    operation_id: "op-1",
    span_count: 2,
    error_count: 1,
    duration_ms: 1200,
    started_at: "2026-05-07T10:00:00+05:00",
    finished_at: "2026-05-07T10:01:00+05:00",
    attrs_json: {},
  };
}

function renderObserver(initialPath = "/app/admin/observer?trace_id=trace-deep-1") {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        refetchOnWindowFocus: false,
      },
    },
  });

  render(
    <MemoryRouter initialEntries={[initialPath]}>
      <QueryClientProvider client={queryClient}>
        <ObserverQuickPanel deviceId={null} deviceLabel="всему контуру" />
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ObserverQuickPanel deep links", () => {
  it("opens trace tab from trace_id URL parameter and requests the selected trace", async () => {
    const trace = traceItem();
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.startsWith("/api/web/admin/observer/quick")) {
        return jsonResponse({
          status: "success",
          data: {
            summary: {
              lookback_hours: 24,
              recent_trace_count: 1,
              hot_trace_count: 0,
              signature_count: 0,
              degradation_group_count: 0,
              dangerous_flow_count: 0,
            },
            runtime: {
              enabled: true,
              running: true,
              health_status: "ok",
              health_status_label: "Норма",
              pending_trace_count: 0,
              last_projected_at: "2026-05-07T10:00:00+05:00",
              issues: [],
            },
            hot_traces: [],
            top_signatures: [],
            top_degradations: [],
            dangerous_flows: [],
            links: {},
          },
        });
      }
      if (url.startsWith("/api/web/admin/observer/traces")) {
        return jsonResponse({
          status: "success",
          data: {
            query: {
              device_id: null,
              lookback_hours: 24,
              status_filter: "all",
              root_kind_filter: "all",
              limit: 40,
              trace_id: "trace-deep-1",
            },
            summary: {
              visible_count: 1,
              active_count: 0,
              error_count: 1,
              selected_trace_id: "trace-deep-1",
            },
            filters: {
              status_options: [
                { value: "all", label: "Все статусы" },
                { value: "failed", label: "Ошибки" },
              ],
              root_kind_options: [
                { value: "all", label: "Все корни" },
                { value: "ticket", label: "Ticket" },
              ],
            },
            traces: [trace],
            links: {
              detail_endpoint_template: "/api/web/admin/observer/traces/{trace_id}",
              runtime_endpoint: "/api/web/admin/observer/runtime",
            },
          },
        });
      }
      if (url === "/api/web/admin/observer/trace-detail/trace-deep-1") {
        return jsonResponse({
          status: "ok",
          trace,
          summary: {
            span_count: 2,
            error_count: 1,
            linked_trace_count: 0,
          },
          explanation: {
            launch_source: "manual",
            launch_source_label: "Ручной запуск",
            actor_id: "admin",
            actor_role: "admin",
            actor_display_name: "admin",
            actor_label: "Запустил: admin",
            tool_name: "system.collect",
            tool_label: "Сбор диагностики",
            module_name: "system",
            module_label: "system",
            preset_id: "minimal",
            preset_label: "Minimal",
            preset_description: "CPU and memory only",
            error_code: "AGENT_NOT_CONNECTED",
            error_diagnosis: "Агент на устройстве не подключен. Команда не была отправлена.",
            failure_stage: "failed",
            failure_stage_label: "Ошибка",
            agent_online: false,
            agent_status_label: "агент offline",
            launch_path: ["Тикет T-000520", "ручной запуск инструмента", "Сбор диагностики", "агент offline", "failed"],
            next_actions: ["Проверить подключение агента", "Открыть устройство в inventory"],
            human_timeline: [],
            debug_refs: { operation_id: "op-1" },
          },
          spans: [
            {
              span_id: "span-queued",
              trace_id: "trace-deep-1",
              name: "operation.stage.queued",
              status: "ok",
              status_label: "ОК",
              stage_label: "Поставлена в очередь",
              stage_state: "passed_before_failure",
              is_failure_stage: false,
              attrs_json: {},
            },
          ],
          span_links: [],
          error_occurrences: [],
          agent_actions: [],
          observer_settings: {
            action_sync_enabled: true,
            action_sync_limit: 80,
          },
        });
      }
      if (url === "/api/web/admin/observer/diagnostics/bundle?lookback_hours=24&limit=20&trace_id=trace-deep-1&include_agent_actions=1&action_limit=80") {
        return jsonResponse({
          status: "ok",
          summary: {
            primary_trace_id: "trace-deep-1",
            related_trace_count: 1,
            span_count: 2,
            error_count: 1,
            agent_action_count: 0,
            agent_audit_count: 0,
            recent_log_count: 0,
          },
          primary_trace: trace,
          related_traces: [trace],
          spans: [],
          span_links: [],
          error_occurrences: [],
          agent_actions: [],
          signatures: [],
          degradations: [],
          recent_logs: [],
          agent_audit: [],
          recommended_next_checks: [],
        });
      }
      if (url.startsWith("/api/web/admin/observer/signatures")) {
        return jsonResponse({ status: "ok", signatures: [] });
      }
      if (url.startsWith("/api/web/admin/observer/degradations")) {
        return jsonResponse({ status: "ok", items: [] });
      }
      if (url === "/api/web/admin/observer/runtime") {
        return jsonResponse({ status: "ok", runtime: { enabled: true, running: true, health: { status: "ok", issues: [] } } });
      }
      if (url === "/api/web/admin/observer/settings") {
        return jsonResponse({ status: "ok", settings: {} });
      }
      return jsonResponse({ status: "error", error: `Unhandled ${url}` }, 404);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    renderObserver();

    expect(await screen.findByText(/trace-deep-1/)).toBeInTheDocument();
    expect(await screen.findByText("Агент на устройстве не подключен. Команда не была отправлена.")).toBeInTheDocument();
    expect(screen.getByText("Запустил: admin")).toBeInTheDocument();
    expect(screen.getByText("Проверить подключение агента")).toBeInTheDocument();
    expect(screen.getByText("Поставлена в очередь")).toBeInTheDocument();
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/admin/observer/traces?lookback_hours=24&limit=40&trace_id=trace-deep-1",
        expect.objectContaining({ credentials: "same-origin" }),
      );
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/admin/observer/trace-detail/trace-deep-1",
        expect.objectContaining({ credentials: "same-origin" }),
      );
    });
  });
});
