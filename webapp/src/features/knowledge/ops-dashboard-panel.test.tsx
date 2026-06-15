import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
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

  return render(
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
              action_queues: {
                no_audience_users: {
                  total: 1,
                  items: [{ item_id: "item-zero", title: "VPN для заявителей", reason: "Аудитория не содержит пользователей", action_url: "/app/admin/knowledge/studio?item=item-zero" }],
                },
                missing_helpdesk_binding: {
                  total: 2,
                  items: [{ item_id: "item-binding", title: "Принтеры", reason: "Нет связи с услугой или формой обращения", action_url: "/app/admin/knowledge/studio?item=item-binding" }],
                },
                stale_article: {
                  total: 1,
                  items: [{ item_id: "item-stale", title: "VPN устарела", reason: "Просрочена проверка", action_url: "/app/admin/knowledge/studio?item=item-stale" }],
                },
                indexing_failed: {
                  total: 2,
                  items: [{ job_id: "job-1", title: "Индексация item", reason: "embedding provider unavailable", action_url: "/app/admin/knowledge/indexing" }],
                },
                low_quality: {
                  total: 2,
                  items: [{ item_id: "item-quality", title: "Слабая статья", reason: "Оценка качества ниже порога", action_url: "/app/admin/knowledge/studio?item=item-quality" }],
                },
                zero_result_searches: {
                  total: 5,
                  items: [{ query: "vpn", reason: "5 поисков без результата", action_url: "/app/admin/knowledge/search-settings" }],
                },
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
              taxonomy_terms: [
                { term_id: "term-1", space_id: "ks-1", term_type: "product", code: "vpn", title: "VPN", visibility: "requester", status: "active" },
                { term_id: "term-2", space_id: "ks-1", term_type: "tag", code: "draft", title: "Draft", visibility: "requester", status: "draft" },
                { term_id: "term-3", space_id: "ks-1", term_type: "tag", code: "archived", title: "Archived", visibility: "requester", status: "archived" },
              ],
              property_definitions: [
                { property_id: "prop-1", space_id: "ks-1", code: "audience", title: "Audience", value_type: "select", required: true, status: "active" },
                { property_id: "prop-2", space_id: "ks-1", code: "draft_property", title: "Draft property", value_type: "text", required: false, status: "draft" },
                { property_id: "prop-3", space_id: "ks-1", code: "archived_property", title: "Archived property", value_type: "text", required: false, status: "archived" },
              ],
              applicability_rules: [{ rule_id: "rule-1", item_id: "item-1", scope_type: "service", scope_ref: "network", include_mode: "include", priority: 10 }],
              quality_models: [{ model_id: "qm-1", space_id: "ks-1", code: "metadata-required", title: "Metadata required", weights: { properties: 12, applicability: 8 }, status: "active", is_default: true }],
              item_metadata: [{ item_id: "item-1", space_id: "ks-1", slug: "vpn", title: "VPN", properties: { audience: "requester" }, taxonomy_terms: [], applicability_rules: [] }],
              summary: {
                taxonomy_terms_total: 3,
                taxonomy_terms_active: 1,
                property_definitions_total: 3,
                property_definitions_active: 1,
                applicability_rules_total: 1,
                applicability_rules_active: 1,
                quality_models_total: 1,
                quality_models_active: 1,
                item_metadata_total: 1,
              },
            },
          }),
        );
      }
      return Promise.resolve(jsonResponse({ status: "error" }, 404));
    });
    vi.stubGlobal("fetch", fetchMock);

    const { container } = renderPanel();

    expect(await screen.findByText("Деградация")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Центр операций базы знаний" })).toBeInTheDocument();
    expect(screen.getByText("Безопасное покрытие")).toBeInTheDocument();
    expect(screen.getByText("Поиски без результатов")).toBeInTheDocument();
    expect(screen.getByText("RAG без ответа")).toBeInTheDocument();
    expect(screen.getByText("Ошибки индексации")).toBeInTheDocument();
    expect(screen.getByText("Поиск и RAG")).toBeInTheDocument();
    expect(screen.getByText("Покрытие и проверка")).toBeInTheDocument();
    expect(screen.getByText("AI, индексация и граф")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Очереди действий" })).toBeInTheDocument();
    expect(screen.getByText("Нет пользователей в аудитории")).toBeInTheDocument();
    expect(screen.getByText("Нет связи с обращениями")).toBeInTheDocument();
    expect(screen.getByText("Устаревшие статьи")).toBeInTheDocument();
    expect(screen.getByText("Слабое качество")).toBeInTheDocument();
    expect(screen.getByText("Нулевые поиски")).toBeInTheDocument();
    expect(screen.getByText("VPN для заявителей")).toBeInTheDocument();
    expect(screen.getByText("embedding provider unavailable")).toBeInTheDocument();
    expect(screen.getByText("Деградации из Observer")).toBeInTheDocument();
    expect(screen.getByText("knowledge.indexing.failed")).toBeInTheDocument();
    expect(screen.getByText("Embedding provider unavailable")).toBeInTheDocument();
    const metadataHeading = await screen.findByRole("heading", { name: "Модель метаданных знаний" });
    const metadataCard = metadataHeading.closest(".surface-panel") as HTMLElement;
    expect(metadataCard).toBeTruthy();
    expect(within(metadataCard).getByText("Термины таксономии")).toBeInTheDocument();
    expect(within(metadataCard).getByText("Свойства")).toBeInTheDocument();
    expect(within(metadataCard).getByText("Правила применимости")).toBeInTheDocument();
    expect(within(metadataCard).getByText("Метаданные статей")).toBeInTheDocument();
    expect(within(metadataCard).getByText("Активная модель качества:")).toBeInTheDocument();
    expect(within(metadataCard).getAllByText("1")).toHaveLength(4);
    expect(within(metadataCard).queryByText("3")).not.toBeInTheDocument();
    expect(screen.getByText("metadata-required")).toBeInTheDocument();
    expect(screen.getByText("properties: 12")).toBeInTheDocument();
    expect(metadataCard.textContent ?? "").not.toMatch(/Knowledge metadata model|Taxonomy terms|Properties|Applicability rules|Item metadata|Active quality model/);
    expect(container.textContent ?? "").not.toMatch(/Knowledge Operations Center|Search and RAG|Coverage and Review|AI, Indexing and Graph|Observer-backed degradation/);
    expect(container.textContent ?? "").not.toMatch(/\uFFFD|\u0420\u045A|\u0420\u045E|\u0420\u040F|\u0421\u045A|\u0421\u201A|\u0421\u2039|\u0421\u0453|\u0421\u2020|\u0421\u2021|\u0421\u02DC/);
    expect(fetchMock).toHaveBeenCalledWith("/api/web/knowledge/ops/summary", { credentials: "same-origin" });
    expect(fetchMock).toHaveBeenCalledWith("/api/web/knowledge/metadata", { credentials: "same-origin" });
  });
});
