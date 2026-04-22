import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchObserverWorkbenchTraceDetail } from "./observer-workbench-api";

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
      "/api/admin/tech/traces/trace-1?include_agent_actions=1&action_limit=120",
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
