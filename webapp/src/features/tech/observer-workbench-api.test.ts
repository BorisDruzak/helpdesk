import { afterEach, describe, expect, it, vi } from "vitest";

import {
  fetchObserverDiagnosticsBundle,
  fetchObserverWorkbenchTraceDetail,
  fetchObserverWorkbenchTraces,
} from "./observer-workbench-api";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json",
    },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("fetchObserverWorkbenchTraceDetail", () => {
  it("derives summary from direct tech payloads that do not include summary", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse({
        status: "ok",
        trace: {
          trace_id: "trace-1",
          root_kind: "ticket",
          root_kind_label: "Тикет",
          status: "error",
          status_label: "Ошибка",
          duration_ms: 2400,
          span_count: 3,
          error_count: 1,
          started_at: "2026-04-22T10:00:00Z",
          finished_at: "2026-04-22T10:00:02Z",
          ticket_id: "ticket-1",
          operation_id: null,
          device_id: "device-1",
          job_id: null,
        },
        spans: [
          {
            span_id: "span-1",
            trace_id: "trace-1",
            name: "ticket.lifecycle",
            status: "running",
            status_label: "В работе",
          },
          {
            span_id: "span-2",
            trace_id: "trace-1",
            name: "operation.stage.failed",
            status: "error",
            status_label: "Ошибка",
          },
          {
            span_id: "span-3",
            trace_id: "trace-1",
            name: "ticket.tool_call_result",
            status: "ok",
            status_label: "Успешно",
          },
        ],
        span_links: [
          {
            id: 1,
            span_id: "span-2",
            linked_trace_id: "trace-linked-1",
            linked_span_id: "linked-span-1",
            reason: "operation_id_bridge",
            created_at: "2026-04-22T10:00:02Z",
          },
          {
            id: 2,
            span_id: "span-3",
            linked_trace_id: "trace-linked-1",
            linked_span_id: "linked-span-2",
            reason: "same_trace",
            created_at: "2026-04-22T10:00:02Z",
          },
        ],
        error_occurrences: [
          {
            occurrence_id: "occ-1",
            trace_id: "trace-1",
            span_id: "span-2",
            error_signature: "sig-1",
            severity: "error",
            severity_label: "Ошибка",
            created_at: "2026-04-22T10:00:02Z",
          },
        ],
        agent_actions: [],
      })
    );

    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    const detail = await fetchObserverWorkbenchTraceDetail("trace-1", {
      includeAgentActions: true,
      actionLimit: 120,
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/web/admin/observer/trace-detail/trace-1?include_agent_actions=1&action_limit=120",
      expect.objectContaining({
        credentials: "same-origin",
      })
    );
    expect(detail.summary).toEqual({
      span_count: 3,
      error_count: 1,
      linked_trace_count: 1,
    });
    expect(detail.spans).toHaveLength(3);
    expect(detail.error_occurrences).toHaveLength(1);
    expect(detail.span_links).toHaveLength(2);
  });
});

describe("observer workbench search helpers", () => {
  it("passes server-side trace query to typed observer traces", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse({
        status: "success",
        data: {
          query: {
            device_id: null,
            lookback_hours: 24,
            status_filter: "all",
            root_kind_filter: "all",
            limit: 40,
            query: "op-1",
          },
          summary: {
            visible_count: 0,
            active_count: 0,
            error_count: 0,
            selected_trace_id: null,
          },
          filters: {
            status_options: [],
            root_kind_options: [],
          },
          traces: [],
          links: {
            detail_endpoint_template: "/api/web/admin/observer/traces/{trace_id}",
            runtime_endpoint: "/api/web/admin/observer/runtime",
          },
        },
      })
    );
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    await fetchObserverWorkbenchTraces({
      lookbackHours: 24,
      statusFilter: "all",
      rootKindFilter: "all",
      limit: 40,
      query: "op-1",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/web/admin/observer/traces?lookback_hours=24&limit=40&q=op-1",
      expect.objectContaining({ credentials: "same-origin" })
    );
  });

  it("serializes support deep-link trace filters", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse({
        status: "success",
        data: {
          query: {
            device_id: null,
            lookback_hours: 24,
            status_filter: "all",
            root_kind_filter: "all",
            limit: 40,
            trace_id: "trace-deep-1",
            ticket_id: "ticket-1",
            operation_id: "op-1",
          },
          summary: {
            visible_count: 1,
            active_count: 0,
            error_count: 1,
            selected_trace_id: "trace-deep-1",
          },
          filters: {
            status_options: [],
            root_kind_options: [],
          },
          traces: [],
          links: {
            detail_endpoint_template: "/api/web/admin/observer/traces/{trace_id}",
            runtime_endpoint: "/api/web/admin/observer/runtime",
          },
        },
      })
    );
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    await fetchObserverWorkbenchTraces({
      lookbackHours: 24,
      statusFilter: "all",
      rootKindFilter: "all",
      limit: 40,
      traceId: "trace-deep-1",
      ticketId: "ticket-1",
      operationId: "op-1",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/web/admin/observer/traces?lookback_hours=24&limit=40&trace_id=trace-deep-1&ticket_id=ticket-1&operation_id=op-1",
      expect.objectContaining({ credentials: "same-origin" })
    );
  });

  it("serializes observer closure filters for playbook and web auth traces", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse({
        status: "success",
        data: {
          query: {
            device_id: null,
            lookback_hours: 24,
            status_filter: "all",
            root_kind_filter: "playbook_run",
            limit: 40,
            query: "AUTH_REQUIRED",
            playbook_run_id: 42,
            step_run_id: 7,
            route: "/api/tickets",
          },
          summary: {
            visible_count: 0,
            active_count: 0,
            error_count: 0,
            selected_trace_id: null,
          },
          filters: {
            status_options: [],
            root_kind_options: [
              { value: "playbook_run", label: "Playbook run" },
              { value: "web_auth", label: "Web auth" },
              { value: "observer_runtime", label: "Observer runtime" },
            ],
          },
          traces: [],
          links: {
            detail_endpoint_template: "/api/web/admin/observer/traces/{trace_id}",
            runtime_endpoint: "/api/web/admin/observer/runtime",
          },
        },
      })
    );
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    await fetchObserverWorkbenchTraces({
      lookbackHours: 24,
      statusFilter: "all",
      rootKindFilter: "playbook_run",
      limit: 40,
      query: "AUTH_REQUIRED",
      playbookRunId: 42,
      stepRunId: 7,
      route: "/api/tickets",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/web/admin/observer/traces?lookback_hours=24&root_kind=playbook_run&limit=40&q=AUTH_REQUIRED&playbook_run_id=42&step_run_id=7&route=%2Fapi%2Ftickets",
      expect.objectContaining({ credentials: "same-origin" })
    );
  });

  it("loads diagnostic bundle with agent actions", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse({
        status: "ok",
        summary: {
          primary_trace_id: "trace-1",
          related_trace_count: 1,
        },
        recommended_next_checks: ["Open trace detail"],
      })
    );
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    const bundle = await fetchObserverDiagnosticsBundle({
      traceId: "trace-1",
      includeAgentActions: true,
      actionLimit: 80,
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/web/admin/observer/diagnostics/bundle?limit=20&trace_id=trace-1&include_agent_actions=1&action_limit=80",
      expect.objectContaining({ credentials: "same-origin" })
    );
    expect(bundle.summary.primary_trace_id).toBe("trace-1");
  });
});
