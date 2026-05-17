import { afterEach, describe, expect, it, vi } from "vitest";

import {
  closeImprovementAction,
  completeQualityReview,
  createImprovementAction,
  fetchImprovementActions,
  fetchQualityPolicy,
  fetchQualityReviews,
  fetchQualitySummary,
  fetchServiceQuality,
  saveQualityPolicy,
} from "./api";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("quality api", () => {
  it("loads dashboard summary and service quality without requester PII", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/web/quality/summary") {
        return jsonResponse({
          status: "ok",
          summary: {
            avg_csat: 2.5,
            feedback_count: 2,
            negative_csat_count: 1,
            reopen_count: 1,
            sla_breach_count: 1,
            qa_review_count: 1,
            improvement_action_count: 1,
          },
        });
      }
      if (url === "/api/web/quality/service-quality") {
        return jsonResponse({
          status: "ok",
          rows: [
            {
              service_code: "network",
              offering_code: "vpn",
              ticket_count: 2,
              resolved_count: 2,
              closed_count: 1,
              feedback_count: 2,
              avg_csat: 2.5,
              negative_csat_count: 1,
              reopen_count: 1,
              reopen_rate: 0.5,
              sla_breach_count: 1,
              sla_breach_rate: 0.5,
              knowledge_attempt_count: 1,
              ticket_after_failed_knowledge_count: 1,
              qa_review_count: 1,
              qa_failed_count: 0,
              improvement_action_count: 1,
            },
          ],
          last_computed_at: "2026-05-17T04:00:00+00:00",
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    const summary = await fetchQualitySummary();
    const rows = await fetchServiceQuality();

    expect(summary.avg_csat).toBe(2.5);
    expect(rows[0]?.service_code).toBe("network");
    expect(rows.lastComputedAt).toBe("2026-05-17T04:00:00+00:00");
    expect(JSON.stringify(rows)).not.toContain("requester_id");
  });

  it("filters review and action lists by ticket id", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/web/quality/reviews?ticket_id=T-1") {
        return jsonResponse({ status: "ok", reviews: [{ review_id: "qr-1", ticket_id: "T-1", review_type: "low_csat", severity: "high", status: "open" }] });
      }
      if (url === "/api/web/quality/improvement-actions?ticket_id=T-1") {
        return jsonResponse({
          status: "ok",
          actions: [{ action_id: "qa-1", source_kind: "csat", action_type: "train_support", title: "Train support", status: "open", priority: "medium", ticket_id: "T-1" }],
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    expect((await fetchQualityReviews("T-1"))[0]?.ticket_id).toBe("T-1");
    expect((await fetchImprovementActions("T-1"))[0]?.ticket_id).toBe("T-1");
  });

  it("mutates reviews and improvement actions", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/quality/improvement-actions" && init?.method === "POST") {
        return jsonResponse({ status: "ok", action: { action_id: "a1", source_kind: "manual", action_type: "process_review", title: "Review", status: "open", priority: "medium" } });
      }
      if (url === "/api/web/quality/reviews/r1/complete") {
        return jsonResponse({ status: "ok", review: { review_id: "r1", ticket_id: "T-1", review_type: "low_csat", severity: "high", status: "passed" } });
      }
      if (url === "/api/web/quality/improvement-actions/a1/close") {
        return jsonResponse({ status: "ok", action: { action_id: "a1", source_kind: "manual", action_type: "process_review", title: "Review", status: "done", priority: "medium" } });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    await createImprovementAction({ source_kind: "manual", action_type: "process_review", title: "Review", description: "Review", priority: "medium" });
    await completeQualityReview("r1", 85);
    await closeImprovementAction("a1", "done");

    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("previews and saves service/offering quality policy overrides", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/quality/policies?service_code=network&offering_code=network.vpn_issue") {
        return jsonResponse({
          status: "ok",
          policy: {
            policy_id: "qp-1",
            scope_type: "offering",
            service_code: "network",
            offering_code: "network.vpn_issue",
            low_csat_threshold: 2,
            reopen_review_enabled: true,
            sla_breach_review_enabled: true,
            high_priority_review_enabled: true,
            missing_evidence_review_enabled: true,
            random_sample_percent: 0,
            qa_due_hours: 12,
          },
        });
      }
      if (url === "/api/web/quality/policies/save" && init?.method === "POST") {
        expect(JSON.parse(String(init.body))).toMatchObject({
          scope_type: "offering",
          service_code: "network",
          offering_code: "network.vpn_issue",
          low_csat_threshold: 2,
        });
        return jsonResponse({
          status: "ok",
          policy: {
            policy_id: "qp-1",
            scope_type: "offering",
            service_code: "network",
            offering_code: "network.vpn_issue",
            low_csat_threshold: 2,
            reopen_review_enabled: true,
            sla_breach_review_enabled: true,
            high_priority_review_enabled: true,
            missing_evidence_review_enabled: true,
            random_sample_percent: 0,
            qa_due_hours: 12,
          },
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    const preview = await fetchQualityPolicy({ serviceCode: "network", offeringCode: "network.vpn_issue" });
    const saved = await saveQualityPolicy({
      scope_type: "offering",
      service_code: "network",
      offering_code: "network.vpn_issue",
      low_csat_threshold: 2,
      reopen_review_enabled: true,
      sla_breach_review_enabled: true,
      high_priority_review_enabled: true,
      missing_evidence_review_enabled: true,
      random_sample_percent: 0,
      qa_due_hours: 12,
    });

    expect(preview.scope_type).toBe("offering");
    expect(saved.policy_id).toBe("qp-1");
  });
});
