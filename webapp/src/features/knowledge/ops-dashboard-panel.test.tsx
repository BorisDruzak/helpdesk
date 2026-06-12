import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { KnowledgeOpsDashboardPanel } from "./ops-dashboard-panel";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderPanel() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  render(
    <QueryClientProvider client={queryClient}>
      <KnowledgeOpsDashboardPanel />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("KnowledgeOpsDashboardPanel", () => {
  it("renders ops summary cards and observer-backed degraded state", async () => {
    const fetchMock = vi.fn((url: string) => {
      if (url === "/api/web/knowledge/ops/summary") {
        return Promise.resolve(
          jsonResponse({
            status: "ok",
            summary: {
              status: "degraded",
              generated_at: "2026-06-12T08:00:00Z",
              coverage: {
                spaces: { total: 3 },
                published_articles: { total: 9 },
                requester_safe: { total: 4 },
                support_runbooks: { total: 2 },
                services_without_kb: { total: 1 },
              },
              quality: {
                average_score: 67,
                low_quality_count: { total: 2 },
                stale_review_count: { total: 1 },
                missing_owner_reviewer_count: { total: 3 },
                unsafe_requester_safe_blockers: { total: 1 },
              },
              search: {
                zero_result_searches: { total: 5 },
                fallback_count: { total: 4 },
                ai_disabled_count: { total: 1 },
                vector_usage_count: { total: 2 },
                rerank_usage_count: { total: 1 },
                top_queries: [{ query: "vpn", count: 3 }],
              },
              rag: {
                answer_count: { total: 8 },
                no_answer_count: { total: 2 },
                provider_failures: { total: 1 },
                citation_validation_failures: { total: 1 },
              },
              indexing: {
                queued: { total: 1 },
                failed: { total: 2 },
                stale_embeddings: { total: 3 },
                disabled: { total: 4 },
              },
              ai: {
                provider_health: { status: "degraded", failed_count: 1 },
                model_profile_status: { active_count: 2, disabled_count: 1 },
                policy_blocks: { total: 6 },
              },
              graph: {
                orphan_nodes: { total: 2 },
                pending_proposals: { total: 1 },
                contradiction_duplicate_findings: { total: 1 },
              },
              review: {
                assigned_open: { total: 3 },
                overdue: { total: 2 },
              },
              observer: {
                degradations: [
                  {
                    code: "knowledge.indexing.failed",
                    severity: "critical",
                    source: "knowledge.indexing",
                    count: 2,
                    status: "active",
                    message: "Embedding provider unavailable",
                  },
                ],
              },
            },
          }),
        );
      }
      if (url === "/api/web/knowledge/metadata") {
        return Promise.resolve(
          jsonResponse({
            status: "ok",
            metadata: {
              spaces: [{ space_id: "ks-1", code: "it", title: "IT", visibility: "requester", lifecycle_status: "active" }],
              taxonomy_terms: [{ term_id: "term-1", space_id: "ks-1", term_type: "product", code: "vpn", title: "VPN", visibility: "requester", status: "active" }],
              property_definitions: [{ property_id: "prop-1", space_id: "ks-1", code: "audience", title: "Audience", value_type: "select", required: true, status: "active" }],
              applicability_rules: [{ rule_id: "rule-1", item_id: "item-1", scope_type: "service", scope_ref: "network", include_mode: "include", priority: 10 }],
              quality_models: [{ model_id: "qm-1", space_id: "ks-1", code: "metadata-required", title: "Metadata required", weights: { properties: 12, applicability: 8 }, status: "active", is_default: true }],
              item_metadata: [{ item_id: "item-1", space_id: "ks-1", slug: "vpn", title: "VPN", properties: { audience: "requester" }, taxonomy_terms: [], applicability_rules: [] }],
            },
          }),
        );
      }
      return Promise.resolve(jsonResponse({ status: "error" }, 404));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPanel();

    expect(await screen.findByText("Degraded")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Knowledge Operations Center" })).toBeInTheDocument();
    expect(screen.getByText("Requester-safe coverage")).toBeInTheDocument();
    expect(screen.getByText("Zero-result searches")).toBeInTheDocument();
    expect(screen.getByText("RAG no-answer")).toBeInTheDocument();
    expect(screen.getByText("Failed indexing jobs")).toBeInTheDocument();
    expect(screen.getByText("Observer-backed degradation")).toBeInTheDocument();
    expect(screen.getByText("knowledge.indexing.failed")).toBeInTheDocument();
    expect(screen.getByText("Embedding provider unavailable")).toBeInTheDocument();
    expect(await screen.findByText("Knowledge metadata model")).toBeInTheDocument();
    expect(screen.getByText("metadata-required")).toBeInTheDocument();
    expect(screen.getByText("properties: 12")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/web/knowledge/ops/summary", { credentials: "same-origin" });
    expect(fetchMock).toHaveBeenCalledWith("/api/web/knowledge/metadata", { credentials: "same-origin" });
  });
});
