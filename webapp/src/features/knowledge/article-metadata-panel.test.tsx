import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ArticleMetadataPanel } from "./article-metadata-panel";
import type { KnowledgeItem } from "./api";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const item = {
  item_id: "item-1",
  space_id: "space-1",
  slug: "vpn-access",
  item_type: "article",
  type: "article",
  title: "VPN access",
  summary: "VPN help",
  status: "draft",
  visibility: "requester",
  tags: [],
  current_version_id: "ver-1",
  updated_at: "2026-06-13T00:00:00Z",
} as KnowledgeItem;

const metadataBundle = {
  spaces: [{ space_id: "space-1", code: "it", title: "IT", visibility: "requester", lifecycle_status: "active" }],
  taxonomy_terms: [
    { term_id: "term-vpn", space_id: "space-1", term_type: "product", code: "vpn", title: "VPN", visibility: "requester", status: "active" },
    { term_id: "term-admin", space_id: "space-1", term_type: "tag", code: "admin", title: "Admin", visibility: "admin_internal", status: "active" },
  ],
  property_definitions: [
    {
      property_id: "prop-audience",
      space_id: "space-1",
      code: "audience",
      title: "Аудитория",
      value_type: "select",
      required: true,
      allowed_values: ["requester", "support"],
      applies_to_item_types: ["article"],
      quality_weight: 12,
      status: "active",
    },
  ],
  applicability_rules: [],
  quality_models: [
    {
      model_id: "model-1",
      space_id: "space-1",
      code: "metadata-required",
      title: "Обязательные метаданные",
      weights: { properties: 12, taxonomy: 8, applicability: 5 },
      thresholds: { good: 80 },
      status: "active",
      is_default: true,
    },
  ],
  item_metadata: [],
  summary: {
    taxonomy_terms_total: 2,
    taxonomy_terms_active: 2,
    property_definitions_total: 1,
    property_definitions_active: 1,
    applicability_rules_total: 0,
    applicability_rules_active: 0,
    quality_models_total: 1,
    quality_models_active: 1,
    item_metadata_total: 0,
  },
};

function setupFetch() {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url === "/api/web/knowledge/metadata" && !init?.method) {
      return jsonResponse({ status: "ok", metadata: metadataBundle });
    }
    if (url === "/api/web/knowledge/items/item-1/metadata" && !init?.method) {
      return jsonResponse({
        status: "ok",
        item_metadata: {
          item_id: "item-1",
          space_id: "space-1",
          slug: "vpn-access",
          title: "VPN access",
          properties: {},
          taxonomy_terms: [],
          applicability_rules: [],
        },
      });
    }
    if (url === "/api/web/knowledge/items/item-1/metadata" && init?.method === "PUT") {
      return jsonResponse({ status: "ok", item_metadata: { item_id: "item-1", ...JSON.parse(String(init.body)) } });
    }
    if (url === "/api/web/knowledge/items/item-1/applicability" && !init?.method) {
      return jsonResponse({ status: "ok", rules: [] });
    }
    if (url === "/api/web/knowledge/items/item-1/applicability" && init?.method === "POST") {
      return jsonResponse({ status: "ok", rules: JSON.parse(String(init.body)).rules });
    }
    throw new Error(`Unexpected fetch ${url}`);
  });
  vi.stubGlobal("fetch", fetchMock as typeof fetch);
  return fetchMock;
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
      <ArticleMetadataPanel item={item} canManage />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ArticleMetadataPanel", () => {
  it("renders item metadata tabs and saves taxonomy, properties and applicability without mojibake", async () => {
    const fetchMock = setupFetch();
    renderPanel();

    expect(await screen.findByRole("heading", { name: "Метаданные статьи" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Таксономия" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Свойства" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Применимость" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Качество" })).toBeInTheDocument();

    const taxonomyPanel = screen.getByTestId("article-metadata-taxonomy");
    expect(await within(taxonomyPanel).findByLabelText("Термин VPN")).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Термин VPN"));

    fireEvent.click(screen.getByRole("button", { name: "Свойства" }));
    expect(screen.getByText("Не заполнено обязательное свойство: Аудитория")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Свойство Аудитория"), { target: { value: "requester" } });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить метаданные статьи" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/web/knowledge/items/item-1/metadata", expect.objectContaining({ method: "PUT" })));
    const metadataCall = fetchMock.mock.calls.find((call) => call[0] === "/api/web/knowledge/items/item-1/metadata" && call[1]?.method === "PUT");
    expect(JSON.parse(String(metadataCall?.[1]?.body))).toMatchObject({
      properties: { audience: "requester" },
      taxonomy_term_ids: ["term-vpn"],
    });

    fireEvent.click(screen.getByRole("button", { name: "Применимость" }));
    fireEvent.change(screen.getByLabelText("Тип области статьи"), { target: { value: "service" } });
    fireEvent.change(screen.getByLabelText("Значение области статьи"), { target: { value: "network/vpn" } });
    fireEvent.click(screen.getByRole("button", { name: "Добавить правило статьи" }));
    fireEvent.click(screen.getByRole("button", { name: "Сохранить правила статьи" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/web/knowledge/items/item-1/applicability", expect.objectContaining({ method: "POST" })));

    fireEvent.click(screen.getByRole("button", { name: "Качество" }));
    expect(screen.getByText("Модель: metadata-required")).toBeInTheDocument();
    expect(screen.getByText("Предварительная оценка: 100")).toBeInTheDocument();

    const visibleText = document.body.textContent ?? "";
    expect(visibleText).not.toMatch(/Item metadata|Applicability rules|Active quality model/);
    expect(visibleText).not.toMatch(/\uFFFD|\u0420\u045A|\u0420\u045E|\u0420\u040F|\u0421\u045A|\u0421\u201A|\u0421\u2039|\u0421\u0453|\u0421\u2020|\u0421\u2021|\u0421\u02DC/);
  });
});
