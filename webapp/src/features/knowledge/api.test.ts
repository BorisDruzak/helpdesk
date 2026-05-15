import { afterEach, describe, expect, it, vi } from "vitest";

import {
  applyKnowledgeContentPack,
  fetchKnowledgeGaps,
  fetchKnowledgeQuality,
  fetchKnowledgeReviewQueue,
  fetchKnowledgeRolloutPolicies,
  fetchKnowledgeTemplates,
  saveKnowledgeRolloutPolicy,
  submitKnowledgeReviewAction,
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

describe("knowledge operations api", () => {
  it("loads P2.2 operations summaries from real endpoints", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ status: "ok", templates: [{ type: "article", title: "Article", sections: ["Steps"] }] }))
      .mockResolvedValueOnce(jsonResponse({ status: "ok", review_queue: { count: 1, items: [{ item_id: "ki-1", title: "VPN", reason: "needs_review" }] } }))
      .mockResolvedValueOnce(jsonResponse({ status: "ok", quality: { average_quality_score: 84, items: [{ item_id: "ki-1", quality_score: 84, issues: [] }] } }))
      .mockResolvedValueOnce(jsonResponse({ status: "ok", gaps: { count: 1, gaps: [{ service_code: "network", offering_code: "network.vpn", ticket_count: 2 }] } }))
      .mockResolvedValueOnce(jsonResponse({ status: "ok", policies: [{ policy_id: "kp-1", surface: "requester_portal", enabled: false, rollout_percent: 0 }] }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchKnowledgeTemplates()).resolves.toHaveLength(1);
    await expect(fetchKnowledgeReviewQueue()).resolves.toMatchObject({ count: 1 });
    await expect(fetchKnowledgeQuality()).resolves.toMatchObject({ average_quality_score: 84 });
    await expect(fetchKnowledgeGaps()).resolves.toMatchObject({ count: 1 });
    await expect(fetchKnowledgeRolloutPolicies()).resolves.toHaveLength(1);

    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/web/knowledge/templates", { credentials: "same-origin" });
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/web/knowledge/review-queue", { credentials: "same-origin" });
    expect(fetchMock).toHaveBeenNthCalledWith(3, "/api/web/knowledge/quality", { credentials: "same-origin" });
    expect(fetchMock).toHaveBeenNthCalledWith(4, "/api/web/knowledge/gaps", { credentials: "same-origin" });
    expect(fetchMock).toHaveBeenNthCalledWith(5, "/api/web/knowledge/rollout-policies", { credentials: "same-origin" });
  });

  it("posts content pack, review action, and rollout policy payloads", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ status: "ok", result: { status: "installed", source_hash: "sha", items: [] } }))
      .mockResolvedValueOnce(jsonResponse({ status: "ok", result: { item: { item_id: "ki-1" }, event: { action: "approve" } } }))
      .mockResolvedValueOnce(jsonResponse({ status: "ok", policy: { policy_id: "kp-1", surface: "requester_portal", enabled: true, rollout_percent: 100 } }));
    vi.stubGlobal("fetch", fetchMock);

    await applyKnowledgeContentPack({ pack: { code: "baseline", version: 1, title: "Baseline" }, dry_run: true, force: false });
    await submitKnowledgeReviewAction("ki-1", { action: "approve", note: "checked" });
    await saveKnowledgeRolloutPolicy({ surface: "requester_portal", enabled: true, rollout_percent: 100 });

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/web/knowledge/content-packs/apply",
      expect.objectContaining({ method: "POST", credentials: "same-origin" }),
    );
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toMatchObject({ dry_run: true, force: false, pack: { code: "baseline" } });
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/web/knowledge/items/ki-1/review-action",
      expect.objectContaining({ method: "POST", credentials: "same-origin" }),
    );
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({ action: "approve", note: "checked" });
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "/api/web/knowledge/rollout-policies",
      expect.objectContaining({ method: "POST", credentials: "same-origin" }),
    );
  });
});
