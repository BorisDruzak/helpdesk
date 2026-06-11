import { afterEach, describe, expect, it, vi } from "vitest";

import {
  applyKnowledgeContentPack,
  checkKnowledgeAiProviderHealth,
  fetchKnowledgeGaps,
  fetchKnowledgeAiAudit,
  fetchKnowledgeAiModelProfiles,
  fetchKnowledgeAiPolicies,
  fetchKnowledgeAiProviders,
  fetchKnowledgeSearchSettings,
  fetchKnowledgeSegments,
  fetchKnowledgeSegmentationProfiles,
  fetchKnowledgeQuality,
  fetchKnowledgeReviewQueue,
  fetchKnowledgeRolloutPolicies,
  previewKnowledgeSearch,
  archiveKnowledgeSegment,
  autoSegmentKnowledgeItem,
  createKnowledgeSegment,
  fetchKnowledgeTemplates,
  saveKnowledgeAiModelProfile,
  saveKnowledgeAiPolicy,
  saveKnowledgeAiProvider,
  saveKnowledgeSearchSettings,
  saveKnowledgeSegmentationProfile,
  saveKnowledgeRolloutPolicy,
  submitKnowledgeGapAction,
  submitKnowledgeReviewAction,
  submitKnowledgeReviewTaskAction,
  updateKnowledgeSegment,
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
      .mockResolvedValueOnce(jsonResponse({ status: "ok", count: 1, tasks: [{ task_id: "rt-1", item_id: "ki-1", task_type: "scheduled_review", severity: "warning", status: "open", reason: "needs_review", item: { item_id: "ki-1", space_id: "ks-1", slug: "vpn", item_type: "article", type: "article", title: "VPN", status: "needs_review", visibility: "requester" } }] }))
      .mockResolvedValueOnce(jsonResponse({ status: "ok", quality: { average_quality_score: 84, items: [{ item_id: "ki-1", quality_score: 84, issues: [] }] } }))
      .mockResolvedValueOnce(jsonResponse({ status: "ok", count: 1, findings: [{ finding_id: "kg-1", service_code: "network", offering_code: "network.vpn", gap_type: "no_requester_article", severity: "high", status: "open", evidence: { ticket_count: 2 } }] }))
      .mockResolvedValueOnce(jsonResponse({ status: "ok", policies: [{ policy_id: "kp-1", surface: "requester_portal", enabled: false, rollout_percent: 0 }] }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchKnowledgeTemplates()).resolves.toHaveLength(1);
    await expect(fetchKnowledgeReviewQueue()).resolves.toMatchObject({ count: 1 });
    await expect(fetchKnowledgeQuality()).resolves.toMatchObject({ average_quality_score: 84 });
    await expect(fetchKnowledgeGaps()).resolves.toMatchObject({ count: 1 });
    await expect(fetchKnowledgeRolloutPolicies()).resolves.toHaveLength(1);

    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/web/knowledge/templates", { credentials: "same-origin" });
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/web/knowledge/review/tasks", { credentials: "same-origin" });
    expect(fetchMock).toHaveBeenNthCalledWith(3, "/api/web/knowledge/quality", { credentials: "same-origin" });
    expect(fetchMock).toHaveBeenNthCalledWith(4, "/api/web/knowledge/gap-findings", { credentials: "same-origin" });
    expect(fetchMock).toHaveBeenNthCalledWith(5, "/api/web/knowledge/rollout-policies", { credentials: "same-origin" });
  });

  it("posts content pack, review action, and rollout policy payloads", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ status: "ok", result: { status: "installed", source_hash: "sha", items: [] } }))
      .mockResolvedValueOnce(jsonResponse({ status: "ok", result: { item: { item_id: "ki-1" }, event: { action: "approve" } } }))
      .mockResolvedValueOnce(jsonResponse({ status: "ok", task: { task_id: "rt-1", item_id: "ki-1", task_type: "scheduled_review", severity: "warning", status: "done", reason: "done" } }))
      .mockResolvedValueOnce(jsonResponse({ status: "ok", finding: { finding_id: "kg-1", status: "dismissed" } }))
      .mockResolvedValueOnce(jsonResponse({ status: "ok", policy: { policy_id: "kp-1", surface: "requester_portal", enabled: true, rollout_percent: 100 } }));
    vi.stubGlobal("fetch", fetchMock);

    await applyKnowledgeContentPack({ pack: { code: "baseline", version: 1, title: "Baseline" }, dry_run: true, force: false });
    await submitKnowledgeReviewAction("ki-1", { action: "approve", note: "checked" });
    await submitKnowledgeReviewTaskAction("rt-1", { action: "complete", note: "checked" });
    await submitKnowledgeGapAction("kg-1", "dismiss", { reason: "covered elsewhere" });
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
      "/api/web/knowledge/review/tasks/rt-1/complete",
      expect.objectContaining({ method: "POST", credentials: "same-origin" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      "/api/web/knowledge/gaps/kg-1/dismiss",
      expect.objectContaining({ method: "POST", credentials: "same-origin" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      5,
      "/api/web/knowledge/rollout-policies",
      expect.objectContaining({ method: "POST", credentials: "same-origin" }),
    );
  });
});

describe("knowledge search settings api", () => {
  it("loads and saves AI-off search settings through Phase 2 endpoints", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          status: "ok",
          display_message: "Настройки поиска загружены",
          settings: {
            settings_id: "global",
            search_mode: "keyword_only",
            effective_mode: "keyword_only",
            ai_enabled: false,
            keyword_enabled: true,
            full_text_enabled: false,
            vector_enabled: false,
            rerank_enabled: false,
            ai_query_rewrite_enabled: false,
            rag_answer_enabled: false,
            max_results: 10,
            snippet_length: 180,
          },
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          status: "ok",
          display_message: "Настройки поиска сохранены",
          settings: {
            settings_id: "global",
            search_mode: "hybrid_no_ai",
            effective_mode: "hybrid_no_ai",
            ai_enabled: false,
            keyword_enabled: true,
            full_text_enabled: true,
            vector_enabled: false,
            max_results: 8,
            snippet_length: 220,
          },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchKnowledgeSearchSettings()).resolves.toMatchObject({
      settings_id: "global",
      search_mode: "keyword_only",
      ai_enabled: false,
    });
    await expect(
      saveKnowledgeSearchSettings({
        search_mode: "hybrid_no_ai",
        keyword_enabled: true,
        full_text_enabled: true,
        vector_enabled: false,
        max_results: 8,
        snippet_length: 220,
      }),
    ).resolves.toMatchObject({ display_message: "Настройки поиска сохранены" });

    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/web/knowledge/search-settings", { credentials: "same-origin" });
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/web/knowledge/search-settings",
      expect.objectContaining({ method: "POST", credentials: "same-origin" }),
    );
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toMatchObject({
      search_mode: "hybrid_no_ai",
      vector_enabled: false,
      max_results: 8,
    });
  });

  it("runs search preview through the admin web search endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(
      jsonResponse({
        status: "ok",
        display_message: "Поиск выполнен без AI",
        search_mode: "keyword_only",
        effective_mode: "keyword_only",
        ai_used: false,
        results: [{ item_id: "ki-1", slug: "vpn", title: "VPN", summary: "Baseline", visibility: "requester" }],
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      previewKnowledgeSearch({
        query: "VPN",
        actor_role: "support",
        surface: "admin_knowledge_search",
      }),
    ).resolves.toMatchObject({
      display_message: "Поиск выполнен без AI",
      effective_mode: "keyword_only",
      ai_used: false,
      results: [{ title: "VPN" }],
    });

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/web/knowledge/search",
      expect.objectContaining({ method: "POST", credentials: "same-origin" }),
    );
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      query: "VPN",
      actor_role: "support",
      surface: "admin_knowledge_search",
    });
  });
});

describe("knowledge article segmentation api", () => {
  it("loads segments and profiles through Phase 3 endpoints", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          status: "ok",
          segments: [
            {
              segment_id: "seg-1",
              item_id: "ki-1",
              version_id: "ver-1",
              segment_index: 1,
              segment_type: "manual",
              title: "VPN checks",
              text: "Check adapter",
              keywords: ["vpn", "adapter"],
              boost: 2,
              visibility: "requester",
              status: "active",
              source: "editor_selection",
              embedding_enabled: true,
              full_text_enabled: true,
            },
          ],
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          status: "ok",
          profiles: [{ profile_id: "default-auto", code: "default-auto", title: "Авторазметка по заголовкам", mode: "auto", enabled: true }],
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchKnowledgeSegments("ki-1")).resolves.toMatchObject([{ title: "VPN checks", keywords: ["vpn", "adapter"] }]);
    await expect(fetchKnowledgeSegmentationProfiles()).resolves.toMatchObject([{ code: "default-auto", mode: "auto" }]);

    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/web/knowledge/items/ki-1/segments", { credentials: "same-origin" });
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/web/knowledge/segmentation-profiles", { credentials: "same-origin" });
  });

  it("creates, updates, archives, auto-segments and saves profiles", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ status: "ok", display_message: "Сегмент знаний сохранён", segment: { segment_id: "seg-1" } }))
      .mockResolvedValueOnce(jsonResponse({ status: "ok", display_message: "Сегмент знаний обновлён", segment: { segment_id: "seg-1", title: "Updated" } }))
      .mockResolvedValueOnce(jsonResponse({ status: "ok", display_message: "Сегмент знаний архивирован", segment: { segment_id: "seg-1", status: "archived" } }))
      .mockResolvedValueOnce(jsonResponse({ status: "ok", display_message: "Авторазметка выполнена без AI", job: { job_id: "job-1" }, segments: [{ segment_id: "seg-auto" }] }))
      .mockResolvedValueOnce(jsonResponse({ status: "ok", display_message: "Профиль разметки сохранён", profile: { profile_id: "p1", code: "paragraph-auto" } }));
    vi.stubGlobal("fetch", fetchMock);

    await createKnowledgeSegment("ki-1", {
      version_id: "ver-1",
      title: "VPN",
      text: "Check adapter",
      keywords: ["vpn"],
      start_offset: 3,
      end_offset: 16,
    });
    await updateKnowledgeSegment("seg-1", { title: "Updated", keywords: ["vpn", "dns"] });
    await archiveKnowledgeSegment("seg-1");
    await autoSegmentKnowledgeItem("ki-1", { version_id: "ver-1", profile_code: "default-auto" });
    await saveKnowledgeSegmentationProfile({ code: "paragraph-auto", title: "Paragraph auto", mode: "auto" });

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/web/knowledge/items/ki-1/segments",
      expect.objectContaining({ method: "POST", credentials: "same-origin" }),
    );
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toMatchObject({
      version_id: "ver-1",
      title: "VPN",
      keywords: ["vpn"],
      start_offset: 3,
      end_offset: 16,
    });
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/web/knowledge/segments/seg-1",
      expect.objectContaining({ method: "PATCH", credentials: "same-origin" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "/api/web/knowledge/segments/seg-1",
      expect.objectContaining({ method: "DELETE", credentials: "same-origin" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      "/api/web/knowledge/items/ki-1/segments/auto",
      expect.objectContaining({ method: "POST", credentials: "same-origin" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      5,
      "/api/web/knowledge/segmentation-profiles",
      expect.objectContaining({ method: "POST", credentials: "same-origin" }),
    );
  });
});

describe("knowledge AI settings api", () => {
  it("loads providers, profiles, policies and redacted audit from Phase 1 endpoints", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ status: "ok", providers: [{ provider_id: "p1", title: "OpenRouter", api_key_secret_ref_masked: "env:OPEN...KEY" }] }))
      .mockResolvedValueOnce(jsonResponse({ status: "ok", model_profiles: [{ profile_id: "mp1", code: "answer-default", task_type: "answer" }] }))
      .mockResolvedValueOnce(jsonResponse({ status: "ok", policies: [{ policy_id: "pol1", scope_type: "global", ai_allowed: false }] }))
      .mockResolvedValueOnce(jsonResponse({ status: "ok", display_message: "Журнал AI загружен", audit: [{ audit_id: "audit1", status: "failed", error_message_redacted: "<redacted>" }] }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchKnowledgeAiProviders()).resolves.toHaveLength(1);
    await expect(fetchKnowledgeAiModelProfiles()).resolves.toHaveLength(1);
    await expect(fetchKnowledgeAiPolicies()).resolves.toHaveLength(1);
    await expect(fetchKnowledgeAiAudit()).resolves.toHaveLength(1);

    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/web/knowledge/ai/providers", { credentials: "same-origin" });
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/web/knowledge/ai/model-profiles", { credentials: "same-origin" });
    expect(fetchMock).toHaveBeenNthCalledWith(3, "/api/web/knowledge/ai/policies", { credentials: "same-origin" });
    expect(fetchMock).toHaveBeenNthCalledWith(4, "/api/web/knowledge/ai/audit", { credentials: "same-origin" });
  });

  it("saves AI settings through provider/profile/policy and health-check endpoints", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ status: "ok", display_message: "Провайдер AI сохранён", provider: { provider_id: "p1", title: "OpenRouter" } }))
      .mockResolvedValueOnce(jsonResponse({ status: "ok", display_message: "Профиль модели сохранён", model_profile: { profile_id: "mp1", enabled: false } }))
      .mockResolvedValueOnce(jsonResponse({ status: "ok", display_message: "Политика AI сохранена", policy: { policy_id: "pol1", ai_allowed: true } }))
      .mockResolvedValueOnce(jsonResponse({ status: "ok", display_message: "Проверка OpenRouter выполнена успешно", health: { provider_id: "p1", status: "ok" } }));
    vi.stubGlobal("fetch", fetchMock);

    await saveKnowledgeAiProvider({ code: "openrouter", title: "OpenRouter", api_key_secret_ref: "env:OPENROUTER_API_KEY" });
    await saveKnowledgeAiModelProfile({ profile_id: "mp1", enabled: false });
    await saveKnowledgeAiPolicy({ policy_id: "pol1", scope_type: "global", ai_allowed: true });
    await checkKnowledgeAiProviderHealth("p1", { model_name: "openai/gpt-4o-mini" });

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/web/knowledge/ai/providers",
      expect.objectContaining({ method: "POST", credentials: "same-origin" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/web/knowledge/ai/model-profiles/mp1",
      expect.objectContaining({ method: "PATCH", credentials: "same-origin" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "/api/web/knowledge/ai/policies",
      expect.objectContaining({ method: "POST", credentials: "same-origin" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      "/api/web/knowledge/ai/providers/p1/health-check",
      expect.objectContaining({ method: "POST", credentials: "same-origin" }),
    );
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toMatchObject({ api_key_secret_ref: "env:OPENROUTER_API_KEY" });
  });
});
