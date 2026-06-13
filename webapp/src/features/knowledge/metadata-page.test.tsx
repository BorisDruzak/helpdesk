import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { KnowledgeMetadataPage } from "./metadata-page";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const metadataPayload = {
  status: "ok",
  metadata: {
    spaces: [{ space_id: "space-1", code: "it", title: "IT", visibility: "requester", lifecycle_status: "active" }],
    taxonomy_terms: [
      { term_id: "term-access", space_id: "space-1", term_type: "category", code: "access", title: "Доступы", visibility: "requester", status: "active", sort_order: 10 },
      {
        term_id: "term-vpn",
        space_id: "space-1",
        parent_term_id: "term-access",
        term_type: "product",
        code: "vpn",
        title: "VPN",
        visibility: "requester",
        status: "active",
        sort_order: 20,
      },
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
    applicability_rules: [{ rule_id: "rule-1", item_id: "item-1", scope_type: "service", scope_ref: "network", include_mode: "include", priority: 10 }],
    quality_models: [
      {
        model_id: "model-1",
        space_id: "space-1",
        code: "metadata-required",
        title: "Обязательные метаданные",
        weights: { properties: 12, taxonomy: 8, applicability: 5 },
        thresholds: { good: 80, review: 60 },
        status: "active",
        is_default: true,
      },
    ],
    item_metadata: [
      {
        item_id: "item-1",
        space_id: "space-1",
        slug: "vpn-access",
        title: "VPN access",
        properties: { audience: "requester" },
        taxonomy_terms: [{ term_id: "term-vpn", space_id: "space-1", term_type: "product", code: "vpn", title: "VPN", visibility: "requester", status: "active" }],
        applicability_rules: [],
      },
    ],
    summary: {
      taxonomy_terms_total: 2,
      taxonomy_terms_active: 2,
      property_definitions_total: 1,
      property_definitions_active: 1,
      applicability_rules_total: 1,
      applicability_rules_active: 1,
      quality_models_total: 1,
      quality_models_active: 1,
      item_metadata_total: 1,
    },
  },
};

const itemsPayload = {
  status: "ok",
  items: [
    {
      item_id: "item-1",
      space_id: "space-1",
      slug: "vpn-access",
      item_type: "article",
      title: "VPN access",
      summary: "VPN help",
      status: "draft",
      visibility: "requester",
      tags: [],
      current_version_id: "ver-1",
      updated_at: "2026-06-13T00:00:00Z",
    },
  ],
};

function setupFetch() {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url === "/api/web/knowledge/metadata" && !init?.method) {
      return jsonResponse(metadataPayload);
    }
    if (url === "/api/web/knowledge/items" && !init?.method) {
      return jsonResponse(itemsPayload);
    }
    if (url === "/api/service-catalog/current") {
      return jsonResponse({
        catalog_version: "test",
        services: [
          {
            service_code: "network",
            title: "Сетевые сервисы",
            offerings: [{ offering_code: "vpn", full_code: "network.vpn", title: "VPN доступ" }],
          },
        ],
      });
    }
    if (url === "/api/web/knowledge/taxonomy" && init?.method === "POST") {
      return jsonResponse({ status: "ok", term: { term_id: "term-mfa", ...JSON.parse(String(init.body)) } });
    }
    if (url === "/api/web/knowledge/properties" && init?.method === "POST") {
      return jsonResponse({ status: "ok", property: { property_id: "prop-new", ...JSON.parse(String(init.body)) } });
    }
    if (url === "/api/web/knowledge/items/item-1/applicability" && init?.method === "POST") {
      return jsonResponse({ status: "ok", rules: JSON.parse(String(init.body)).rules });
    }
    if (url === "/api/web/knowledge/quality-models" && init?.method === "POST") {
      return jsonResponse({ status: "ok", quality_model: { model_id: "model-new", ...JSON.parse(String(init.body)) } });
    }
    throw new Error(`Unexpected fetch ${url}`);
  });
  vi.stubGlobal("fetch", fetchMock as typeof fetch);
  return fetchMock;
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  render(
    <QueryClientProvider client={queryClient}>
      <KnowledgeMetadataPage />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("KnowledgeMetadataPage", () => {
  it("renders Russian-first metadata editor and saves taxonomy, property, applicability and quality model changes", async () => {
    const fetchMock = setupFetch();
    renderPage();

    expect(await screen.findByRole("heading", { name: "Метаданные знаний" })).toBeInTheDocument();
    expect(screen.getByText("Таксономия")).toBeInTheDocument();
    expect(screen.getByText("Свойства")).toBeInTheDocument();
    expect(screen.getByText("Применимость")).toBeInTheDocument();
    expect(screen.getByText("Модель качества")).toBeInTheDocument();

    const taxonomyPanel = screen.getByTestId("knowledge-metadata-taxonomy");
    expect(await within(taxonomyPanel).findByRole("button", { name: "Термин Доступы" })).toBeInTheDocument();
    expect(await within(taxonomyPanel).findByRole("button", { name: "Термин VPN" })).toBeInTheDocument();
    expect(taxonomyPanel.textContent ?? "").toContain("Связанные статьи: 1");
    expect(taxonomyPanel.textContent ?? "").toContain("Категория · access · Связанные статьи: 0");
    expect(taxonomyPanel.textContent ?? "").toContain("Продукт · vpn · Связанные статьи: 1");
    expect(taxonomyPanel.textContent ?? "").toContain("Активно");
    expect(taxonomyPanel.textContent ?? "").not.toMatch(/\bcategory\b|\bproduct\b|\bactive\b/);
    fireEvent.change(screen.getByLabelText("Код термина"), { target: { value: "mfa" } });
    fireEvent.change(screen.getByLabelText("Название термина"), { target: { value: "MFA" } });
    fireEvent.change(screen.getByLabelText("Родительский термин"), { target: { value: "term-access" } });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить термин" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/web/knowledge/taxonomy", expect.objectContaining({ method: "POST" })));
    expect(JSON.parse(String(fetchMock.mock.calls.find((call) => call[0] === "/api/web/knowledge/taxonomy")?.[1]?.body))).toMatchObject({
      code: "mfa",
      title: "MFA",
      parent_term_id: "term-access",
      visibility: "requester",
    });

    fireEvent.click(screen.getByRole("button", { name: "Свойства" }));
    expect(screen.getByText("audience · Выбор · вес 12")).toBeInTheDocument();
    expect(document.body.textContent ?? "").not.toMatch(/\bselect\b/);
    fireEvent.change(screen.getByLabelText("Код свойства"), { target: { value: "audience" } });
    fireEvent.change(screen.getByLabelText("Название свойства"), { target: { value: "Аудитория" } });
    fireEvent.change(screen.getByLabelText("Новое разрешённое значение"), { target: { value: "requester" } });
    fireEvent.click(screen.getByRole("button", { name: "Добавить значение" }));
    fireEvent.change(screen.getByLabelText("Новое разрешённое значение"), { target: { value: "support" } });
    fireEvent.click(screen.getByRole("button", { name: "Добавить значение" }));
    expect(screen.getByRole("button", { name: "Удалить значение requester" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Разрешённые значения")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("checkbox", { name: "article" }));
    fireEvent.click(screen.getByLabelText("Обязательное свойство"));
    fireEvent.click(screen.getByRole("button", { name: "Сохранить свойство" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/web/knowledge/properties", expect.objectContaining({ method: "POST" })));
    const propertyCall = fetchMock.mock.calls.find((call) => call[0] === "/api/web/knowledge/properties");
    expect(JSON.parse(String(propertyCall?.[1]?.body))).toMatchObject({
      allowed_values: ["requester", "support"],
      applies_to_item_types: ["faq", "runbook"],
    });
    expect(await screen.findByText("Свойство знаний сохранено")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Применимость" }));
    expect(await screen.findByText("Выберите сервис или услугу из каталога, когда это возможно.")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Тип области"), { target: { value: "offering" } });
    fireEvent.change(screen.getByLabelText("Сервис или услуга"), { target: { value: "network.vpn" } });
    fireEvent.click(screen.getByRole("button", { name: "Добавить правило" }));
    expect(screen.getByText("Услуга: network.vpn")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Редактировать правило Услуга: network.vpn" }));
    fireEvent.change(screen.getByLabelText("Сервис или услуга"), { target: { value: "network" } });
    fireEvent.click(screen.getByRole("button", { name: "Обновить правило" }));
    fireEvent.click(screen.getByRole("button", { name: "Удалить правило Услуга: network" }));
    expect(screen.queryByText("Услуга: network")).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Сервис или услуга"), { target: { value: "network.vpn" } });
    fireEvent.click(screen.getByRole("button", { name: "Добавить правило" }));
    fireEvent.click(screen.getByRole("button", { name: "Сохранить применимость" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/web/knowledge/items/item-1/applicability", expect.objectContaining({ method: "POST" })));
    expect(await screen.findByText("Применимость сохранена")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Модель качества" }));
    fireEvent.change(screen.getByLabelText("Код модели"), { target: { value: "metadata-required-v2" } });
    fireEvent.change(screen.getByLabelText("Название модели"), { target: { value: "Метаданные v2" } });
    fireEvent.change(screen.getByLabelText("Вес свойств"), { target: { value: "14" } });
    fireEvent.change(screen.getByLabelText("Порог хорошо"), { target: { value: "85" } });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить модель качества" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/web/knowledge/quality-models", expect.objectContaining({ method: "POST" })));

    const visibleText = document.body.textContent ?? "";
    expect(visibleText).not.toMatch(/Knowledge metadata model|Taxonomy terms|Properties|Applicability rules|Active quality model/);
    expect(visibleText).not.toMatch(/\uFFFD|\u0420\u045A|\u0420\u045E|\u0420\u040F|\u0421\u045A|\u0421\u201A|\u0421\u2039|\u0421\u0453|\u0421\u2020|\u0421\u2021|\u0421\u02DC/);
  });
});
