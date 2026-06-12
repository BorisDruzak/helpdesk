import { afterEach, describe, expect, it, vi } from "vitest";

import {
  applyKnowledgeContentPack,
  askKnowledgePortal,
  checkKnowledgeAiProviderHealth,
  fetchKnowledgeGaps,
  createKnowledgeGraphEdge,
  createKnowledgeGraphNode,
  fetchKnowledgeAiAudit,
  fetchKnowledgeAiModelProfiles,
  fetchKnowledgeAiPolicies,
  fetchKnowledgeAiProviders,
  fetchKnowledgeGraphNeighborhood,
  fetchKnowledgeGraphNodes,
  fetchKnowledgeSearchSettings,
  fetchKnowledgeSegments,
  fetchKnowledgeSegmentationProfiles,
  fetchKnowledgeQuality,
  fetchKnowledgeReviewQueue,
  fetchKnowledgeRolloutPolicies,
  fetchKnowledgeIndexingStatus,
  fetchKnowledgeIndexJobs,
  fetchKnowledgePortalArticle,
  fetchKnowledgePortalCollection,
  fetchKnowledgePortalHome,
  removeKnowledgePortalBookmark,
  previewKnowledgeSearch,
  previewKnowledgeRetrieval,
  archiveKnowledgeSegment,
  approveKnowledgeAiSegment,
  autoSegmentKnowledgeItem,
  createKnowledgeIndexJob,
  createKnowledgeSegment,
  fetchKnowledgeTemplates,
  proposeKnowledgeAiSegments,
  previewKnowledgeAsk,
  revalidateKnowledgeSegments,
  reindexKnowledgeAll,
  reindexKnowledgeItem,
  reindexKnowledgeSegment,
  reindexKnowledgeSpace,
  retrieveKnowledge,
  saveKnowledgeAiModelProfile,
  saveKnowledgeAiPolicy,
  saveKnowledgeAiProvider,
  saveKnowledgeSearchSettings,
  saveKnowledgeSegmentationProfile,
  saveKnowledgeRolloutPolicy,
  searchKnowledgePortal,
  sendKnowledgeArticleCorrectionRequest,
  sendKnowledgeArticleFeedback,
  setKnowledgePortalBookmark,
  submitKnowledgeGapAction,
  submitKnowledgeReviewAction,
  submitKnowledgeReviewTaskAction,
  syncKnowledgeSegmentIndex,
  rejectKnowledgeAiSegment,
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

describe("knowledge graph api", () => {
  it("loads graph nodes and neighborhood and posts node/edge mutations", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ status: "ok", nodes: [{ node_id: "n1", stable_key: "concept:vpn", label: "VPN", node_type: "concept", visibility: "support_internal" }] }))
      .mockResolvedValueOnce(jsonResponse({ status: "ok", nodes: [{ node_id: "n1", stable_key: "concept:vpn", label: "VPN", node_type: "concept", visibility: "support_internal" }], edges: [] }))
      .mockResolvedValueOnce(jsonResponse({ status: "ok", node: { node_id: "n2", stable_key: "concept:mfa", label: "MFA", node_type: "concept", visibility: "support_internal" } }))
      .mockResolvedValueOnce(jsonResponse({ status: "ok", edge: { edge_id: "e1", relation_type: "mentions" } }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchKnowledgeGraphNodes()).resolves.toHaveLength(1);
    await expect(fetchKnowledgeGraphNeighborhood("concept:vpn", 2)).resolves.toMatchObject({ nodes: [{ stable_key: "concept:vpn" }], edges: [] });
    await createKnowledgeGraphNode({ stable_key: "concept:mfa", label: "MFA", node_type: "concept", visibility: "support_internal" });
    await createKnowledgeGraphEdge({ source_stable_key: "concept:mfa", target_stable_key: "concept:vpn", relation_type: "mentions", visibility: "support_internal" });

    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/web/knowledge/graph/nodes", { credentials: "same-origin" });
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/web/knowledge/graph/nodes/concept%3Avpn/neighborhood?depth=2", { credentials: "same-origin" });
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "/api/web/knowledge/graph/nodes",
      expect.objectContaining({ method: "POST", credentials: "same-origin" }),
    );
    expect(JSON.parse(fetchMock.mock.calls[2][1].body)).toMatchObject({ stable_key: "concept:mfa", label: "MFA" });
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      "/api/web/knowledge/graph/edges",
      expect.objectContaining({ method: "POST", credentials: "same-origin" }),
    );
    expect(JSON.parse(fetchMock.mock.calls[3][1].body)).toMatchObject({
      source_stable_key: "concept:mfa",
      target_stable_key: "concept:vpn",
      relation_type: "mentions",
    });
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

  it("runs requester portal search through the public-compatible endpoint", async () => {
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
      searchKnowledgePortal({
        query: "VPN",
        actor_role: "requester",
        surface: "requester_portal",
      }),
    ).resolves.toMatchObject({
      effective_mode: "keyword_only",
      ai_used: false,
      results: [{ title: "VPN" }],
    });

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/knowledge/search",
      expect.objectContaining({ method: "POST", credentials: "same-origin" }),
    );
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      query: "VPN",
      actor_role: "requester",
      surface: "requester_portal",
    });
  });

  it("loads requester portal home and article reader through public-compatible endpoints", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          status: "ok",
          spaces: [{ space_id: "ks-1", code: "it", title: "IT", visibility: "requester", lifecycle_status: "active" }],
          featured_articles: [{ item_id: "ki-1", slug: "vpn-access", title: "Доступ к VPN", visibility: "requester" }],
          recent_articles: [],
          popular_articles: [],
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          status: "ok",
          article: { item_id: "ki-1", slug: "vpn-access", title: "Доступ к VPN", visibility: "requester" },
          version: { version_id: "ver-1", item_id: "ki-1", version_number: 1, title: "Доступ к VPN", body_format: "markdown", body: "Body" },
          segments: [],
          related_articles: [],
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchKnowledgePortalHome()).resolves.toMatchObject({
      spaces: [{ code: "it" }],
      featured_articles: [{ slug: "vpn-access" }],
    });
    await expect(fetchKnowledgePortalArticle("vpn-access")).resolves.toMatchObject({
      article: { slug: "vpn-access" },
      version: { body: "Body" },
    });

    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/knowledge/portal/home", { credentials: "same-origin" });
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/knowledge/articles/vpn-access", { credentials: "same-origin" });
  });

  it("loads requester portal space and tag collections", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          status: "ok",
          collection_type: "space",
          collection_code: "it",
          title: "IT",
          articles: [{ item_id: "ki-1", slug: "vpn-access", title: "Доступ к VPN", visibility: "requester" }],
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          status: "ok",
          collection_type: "tag",
          collection_code: "vpn",
          title: "vpn",
          articles: [{ item_id: "ki-1", slug: "vpn-access", title: "Доступ к VPN", visibility: "requester" }],
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchKnowledgePortalCollection("space", "it")).resolves.toMatchObject({
      collection_type: "space",
      articles: [{ slug: "vpn-access" }],
    });
    await expect(fetchKnowledgePortalCollection("tag", "vpn")).resolves.toMatchObject({
      collection_type: "tag",
      articles: [{ slug: "vpn-access" }],
    });

    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/knowledge/portal/spaces/it", { credentials: "same-origin" });
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/knowledge/portal/tags/vpn", { credentials: "same-origin" });
  });

  it("sends article feedback, correction and bookmark requests", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ status: "ok", event: { event_type: "helpful" } }))
      .mockResolvedValueOnce(jsonResponse({ status: "ok", event: { event_type: "not_helpful", result: "correction_requested" } }))
      .mockResolvedValueOnce(jsonResponse({ status: "ok", bookmark: { bookmarked: true } }))
      .mockResolvedValueOnce(jsonResponse({ status: "ok", bookmark: { bookmarked: false } }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(sendKnowledgeArticleFeedback("vpn-access", { helpful: true, session_id: "safe-session" })).resolves.toMatchObject({
      event: { event_type: "helpful" },
    });
    await expect(sendKnowledgeArticleCorrectionRequest("vpn-access", { comment: "Outdated" })).resolves.toMatchObject({
      event: { result: "correction_requested" },
    });
    await expect(setKnowledgePortalBookmark("vpn-access", { session_id: "safe-session" })).resolves.toMatchObject({
      bookmark: { bookmarked: true },
    });
    await expect(removeKnowledgePortalBookmark("vpn-access")).resolves.toMatchObject({
      bookmark: { bookmarked: false },
    });

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/knowledge/articles/vpn-access/feedback",
      expect.objectContaining({ method: "POST", credentials: "same-origin" }),
    );
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ helpful: true, session_id: "safe-session" });
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/knowledge/articles/vpn-access/correction-request",
      expect.objectContaining({ method: "POST", credentials: "same-origin" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "/api/knowledge/articles/vpn-access/bookmark",
      expect.objectContaining({ method: "POST", credentials: "same-origin" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      "/api/knowledge/articles/vpn-access/bookmark",
      expect.objectContaining({ method: "DELETE", credentials: "same-origin" }),
    );
  });

  it("runs explainable retrieval through Phase 5 endpoints", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          status: "ok",
          display_message: "Retrieval выполнен",
          effective_mode: "hybrid_vector",
          ai_used: true,
          results: [
            {
              item: { item_id: "ki-1", space_id: "ks-1", slug: "vpn", item_type: "article", type: "article", title: "VPN", status: "published", visibility: "requester" },
              version: { version_id: "ver-1", title: "VPN" },
              snippet: "VPN segment",
              score: 125,
              score_parts: { keyword_title: 50, vector: 75 },
              source_mode: ["keyword", "vector"],
              citations: [{ chunk_id: "chunk-1" }],
            },
          ],
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          status: "ok",
          display_message: "Retrieval выполнен",
          effective_mode: "hybrid_no_ai",
          ai_used: false,
          results: [],
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    await expect(retrieveKnowledge({ query: "VPN", query_vector: [0.1, 0.2], actor_role: "support" })).resolves.toMatchObject({
      effective_mode: "hybrid_vector",
      results: [{ item: { slug: "vpn" }, score_parts: { vector: 75 } }],
    });
    await expect(previewKnowledgeRetrieval({ query: "none", actor_role: "support" })).resolves.toMatchObject({
      effective_mode: "hybrid_no_ai",
      results: [],
    });

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/web/knowledge/retrieve",
      expect.objectContaining({ method: "POST", credentials: "same-origin" }),
    );
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toMatchObject({ query: "VPN", query_vector: [0.1, 0.2] });
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/web/knowledge/search/preview",
      expect.objectContaining({ method: "POST", credentials: "same-origin" }),
    );
  });

  it("runs Knowledge Ask through requester and preview endpoints", async () => {
    const askPayload = {
      status: "ok",
      answer: null,
      answer_status: "ai_disabled",
      display_message: "AI-ответы отключены. Ниже показаны результаты поиска по базе знаний.",
      ai_used: false,
      retrieval_results: [],
      citations: [],
    };
    const fetchMock = vi.fn().mockResolvedValueOnce(jsonResponse(askPayload)).mockResolvedValueOnce(jsonResponse({ ...askPayload, answer_status: "provider_unavailable" }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(askKnowledgePortal({ query: "VPN", surface: "requester_portal" })).resolves.toMatchObject({
      answer_status: "ai_disabled",
      ai_used: false,
    });
    await expect(previewKnowledgeAsk({ query: "VPN", surface: "admin_ask_preview" })).resolves.toMatchObject({
      answer_status: "provider_unavailable",
    });

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/knowledge/ask",
      expect.objectContaining({ method: "POST", credentials: "same-origin" }),
    );
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ query: "VPN", surface: "requester_portal" });
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/web/knowledge/ask/preview",
      expect.objectContaining({ method: "POST", credentials: "same-origin" }),
    );
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

  it("calls revalidation, AI proposal review and index sync endpoints", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ status: "ok", display_message: "Сегменты перепроверены", job: { job_id: "job-rev" }, segments: [] }))
      .mockResolvedValueOnce(jsonResponse({ status: "ok", display_message: "AI-предложения сегментов созданы", job: { job_id: "job-ai" }, segments: [{ segment_id: "seg-ai" }] }))
      .mockResolvedValueOnce(jsonResponse({ status: "ok", display_message: "Индекс сегментов синхронизирован", job: { job_id: "job-sync" }, chunks: [{ chunk_id: "chunk-1" }], stats: { chunks_synced: 1 } }))
      .mockResolvedValueOnce(jsonResponse({ status: "ok", display_message: "AI-предложение сегмента одобрено", segment: { segment_id: "seg-ai", status: "active" } }))
      .mockResolvedValueOnce(jsonResponse({ status: "ok", display_message: "AI-предложение сегмента отклонено", segment: { segment_id: "seg-ai-2", status: "rejected" } }));
    vi.stubGlobal("fetch", fetchMock);

    await revalidateKnowledgeSegments("ki-1", { source_version_id: "ver-1", target_version_id: "ver-2" });
    await proposeKnowledgeAiSegments("ki-1", { version_id: "ver-2", profile_code: "markup-safe" });
    await syncKnowledgeSegmentIndex("ki-1", { version_id: "ver-2" });
    await approveKnowledgeAiSegment("seg-ai");
    await rejectKnowledgeAiSegment("seg-ai-2", { reason: "Дубль существующего сегмента" });

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/web/knowledge/items/ki-1/segments/revalidate",
      expect.objectContaining({ method: "POST", credentials: "same-origin" }),
    );
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toMatchObject({ source_version_id: "ver-1", target_version_id: "ver-2" });
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/web/knowledge/items/ki-1/segments/ai-proposals",
      expect.objectContaining({ method: "POST", credentials: "same-origin" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "/api/web/knowledge/items/ki-1/segments/index-sync",
      expect.objectContaining({ method: "POST", credentials: "same-origin" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      "/api/web/knowledge/segments/seg-ai/approve",
      expect.objectContaining({ method: "POST", credentials: "same-origin" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      5,
      "/api/web/knowledge/segments/seg-ai-2/reject",
      expect.objectContaining({ method: "POST", credentials: "same-origin" }),
    );
    expect(JSON.parse(fetchMock.mock.calls[4][1].body)).toMatchObject({ reason: "Дубль существующего сегмента" });
  });

  it("loads indexing status, jobs and runs scoped reindex without exposing raw vectors", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ status: "ok", indexing: { embeddings: { indexed: 2 }, jobs: { completed: 1 }, vector_enabled: false, embedding_model: null } }))
      .mockResolvedValueOnce(jsonResponse({ status: "ok", jobs: [{ job_id: "job-1", scope_type: "item", status: "completed" }] }))
      .mockResolvedValueOnce(
        jsonResponse({
          status: "ok",
          display_message: "Индексация embeddings выполнена",
          job: { job_id: "job-2", scope_type: "item", status: "completed" },
          embeddings: [{ embedding_id: "emb-1", chunk_id: "chunk-1", item_id: "ki-1", version_id: "ver-1", status: "indexed", content_hash: "hash", visibility: "requester" }],
          stats: { indexed_embeddings: 1 },
        }),
      )
      .mockResolvedValueOnce(jsonResponse({ status: "ok", job: { job_id: "job-3", scope_type: "segment", status: "completed" }, embeddings: [], stats: { disabled_embeddings: 1 } }))
      .mockResolvedValueOnce(jsonResponse({ status: "ok", job: { job_id: "job-4", scope_type: "space", status: "completed" }, embeddings: [], stats: { indexed_embeddings: 2 } }))
      .mockResolvedValueOnce(jsonResponse({ status: "ok", job: { job_id: "job-5", scope_type: "all", status: "completed" }, embeddings: [], stats: { indexed_embeddings: 3 } }))
      .mockResolvedValueOnce(
        jsonResponse({
          status: "ok",
          job: { job_id: "job-6", scope_type: "segment", status: "completed" },
          embeddings: [],
          stats: { indexed_embeddings: 1 },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchKnowledgeIndexingStatus()).resolves.toMatchObject({ vector_enabled: false, embeddings: { indexed: 2 } });
    await expect(fetchKnowledgeIndexJobs()).resolves.toMatchObject([{ job_id: "job-1" }]);
    const result = await reindexKnowledgeItem({ item_id: "ki-1", version_id: "ver-1" });
    await expect(reindexKnowledgeSegment({ segment_id: "seg-1" })).resolves.toMatchObject({ job: { scope_type: "segment" } });
    await expect(reindexKnowledgeSpace({ space_id: "ks-1" })).resolves.toMatchObject({ job: { scope_type: "space" } });
    await expect(reindexKnowledgeAll({ limit: 25 })).resolves.toMatchObject({ job: { scope_type: "all" } });
    await expect(createKnowledgeIndexJob({ scope_type: "segment", scope_ref: "seg-1" })).resolves.toMatchObject({
      job: { scope_type: "segment" },
    });

    expect(result.embeddings[0]).not.toHaveProperty("embedding_vector");
    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/web/knowledge/indexing/status", { credentials: "same-origin" });
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/web/knowledge/indexing/jobs", { credentials: "same-origin" });
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "/api/web/knowledge/indexing/reindex-item",
      expect.objectContaining({ method: "POST", credentials: "same-origin" }),
    );
    expect(JSON.parse(fetchMock.mock.calls[2][1].body)).toMatchObject({ item_id: "ki-1", version_id: "ver-1" });
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      "/api/web/knowledge/indexing/reindex-segment",
      expect.objectContaining({ method: "POST", credentials: "same-origin" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      5,
      "/api/web/knowledge/indexing/reindex-space",
      expect.objectContaining({ method: "POST", credentials: "same-origin" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      6,
      "/api/web/knowledge/indexing/reindex-all",
      expect.objectContaining({ method: "POST", credentials: "same-origin" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      7,
      "/api/web/knowledge/indexing/jobs",
      expect.objectContaining({ method: "POST", credentials: "same-origin" }),
    );
    expect(JSON.parse(fetchMock.mock.calls[6][1].body)).toMatchObject({ scope_type: "segment", scope_ref: "seg-1" });
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
