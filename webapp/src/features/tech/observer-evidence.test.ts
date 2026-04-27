import { describe, expect, it } from "vitest";

import { buildBundleEvidenceStats, buildTraceEvidenceSources } from "./observer-evidence";

describe("observer evidence helpers", () => {
  it("summarizes trace source counts into operator-facing labels", () => {
    const sources = buildTraceEvidenceSources({
      attrs_json: {
        source_counts: {
          operations: 1,
          agent_runtime_audit: 2,
          agent_observer_events: 3,
          playbook_step_runs: 0,
        },
      },
    });

    expect(sources).toEqual([
      { key: "agent_observer_events", label: "Agent telemetry", count: 3 },
      { key: "agent_runtime_audit", label: "Runtime audit", count: 2 },
      { key: "operations", label: "Operations", count: 1 },
    ]);
  });

  it("keeps unknown source keys visible instead of dropping evidence", () => {
    const sources = buildTraceEvidenceSources({
      attrs_json: {
        source_counts: {
          custom_source: 4,
        },
      },
    });

    expect(sources).toEqual([{ key: "custom_source", label: "custom source", count: 4 }]);
  });

  it("builds compact diagnostic bundle stats for the detail panel", () => {
    const stats = buildBundleEvidenceStats({
      summary: {
        agent_action_count: 7,
        agent_audit_count: 2,
        recent_log_count: 5,
        related_trace_count: 1,
      },
    });

    expect(stats).toEqual([
      { key: "agent_actions", label: "Agent actions", value: 7 },
      { key: "agent_audit", label: "Runtime audit", value: 2 },
      { key: "recent_logs", label: "Recent logs", value: 5 },
      { key: "related_traces", label: "Related traces", value: 1 },
    ]);
  });
});
