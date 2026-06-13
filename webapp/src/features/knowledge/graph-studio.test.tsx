import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { KnowledgeGraphStudioPage } from "./graph-studio-page";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const graphNodes = [
  {
    node_id: "node-vpn",
    stable_key: "concept:vpn",
    node_type: "concept",
    label: "VPN: подключение",
    visibility: "support_internal",
    status: "active",
  },
  {
    node_id: "node-article",
    stable_key: "knowledge_item:vpn-access",
    node_type: "knowledge_item",
    label: "Статья про доступ VPN",
    linked_item_id: "item-vpn",
    visibility: "requester",
    status: "active",
  },
  {
    node_id: "node-service",
    stable_key: "service:network",
    node_type: "service",
    label: "Сетевые сервисы",
    visibility: "support_internal",
    status: "active",
  },
];

const graphEdges = [
  {
    edge_id: "edge-1",
    source_node_id: "node-vpn",
    target_node_id: "node-article",
    relation_type: "mentions",
    visibility: "support_internal",
    status: "active",
    weight: 1,
    confidence_score: 0.8,
  },
];

function setupFetch() {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url === "/api/web/knowledge/graph/nodes" && !init?.method) {
      return jsonResponse({ status: "ok", nodes: graphNodes });
    }
    if (url.startsWith("/api/web/knowledge/graph/nodes/") && url.endsWith("/neighborhood?depth=2")) {
      return jsonResponse({ status: "ok", nodes: graphNodes, edges: graphEdges });
    }
    if (url === "/api/web/knowledge/graph/layouts/default" && !init?.method) {
      return jsonResponse({
        status: "ok",
        layout: {
          layout_id: "layout-1",
          scope_type: "graph",
          scope_ref: "default",
          layout_json: {
            nodes: {
              "concept:vpn": { x: 160, y: 180 },
              "knowledge_item:vpn-access": { x: 480, y: 180 },
              "service:network": { x: 320, y: 380 },
            },
            viewport: { zoom: 1 },
          },
        },
      });
    }
    if (url === "/api/web/knowledge/ai/proposals?target_kind=graph&status=pending" && !init?.method) {
      return jsonResponse({
        status: "ok",
        proposals: [
          {
            proposal_id: "prop-graph-1",
            proposal_type: "graph_edge",
            target_kind: "graph",
            target_ref: "default",
            title: "Связать понятие VPN со статьёй",
            status: "pending",
            confidence_score: 0.82,
            proposed_payload: {
              graph: {
                edges: [{ source_stable_key: "concept:vpn", target_stable_key: "knowledge_item:vpn-access", relation_type: "mentions" }],
              },
            },
          },
        ],
      });
    }
    if (url === "/api/web/knowledge/ai/proposals/prop-graph-1/review" && init?.method === "POST") {
      return jsonResponse({
        status: "ok",
        proposal: {
          proposal_id: "prop-graph-1",
          proposal_type: "graph_edge",
          target_kind: "graph",
          target_ref: "default",
          title: "Связать понятие VPN со статьёй",
          status: "approved",
        },
      });
    }
    if (url === "/api/web/knowledge/graph/nodes" && init?.method === "POST") {
      const body = JSON.parse(String(init.body));
      return jsonResponse({
        status: "ok",
        node: {
          node_id: "node-new",
          stable_key: body.stable_key,
          label: body.label,
          node_type: body.node_type,
          visibility: body.visibility,
        },
      });
    }
    if (url === "/api/web/knowledge/graph/edges" && init?.method === "POST") {
      const body = JSON.parse(String(init.body));
      return jsonResponse({
        status: "ok",
        edge: {
          edge_id: "edge-2",
          source_node_id: "node-article",
          target_node_id: "node-service",
          relation_type: body.relation_type,
          visibility: body.visibility,
          status: "active",
        },
      });
    }
    if (url === "/api/web/knowledge/graph/edges/edge-1" && init?.method === "PATCH") {
      const body = JSON.parse(String(init.body));
      return jsonResponse({
        status: "ok",
        edge: {
          ...graphEdges[0],
          relation_type: body.relation_type,
          visibility: body.visibility,
          weight: body.weight,
        },
      });
    }
    if (url === "/api/web/knowledge/graph/edges/edge-1" && init?.method === "DELETE") {
      return jsonResponse({ status: "ok", edge: { ...graphEdges[0], status: "archived" } });
    }
    if (url === "/api/web/knowledge/graph/nodes/concept%3Avpn" && init?.method === "PATCH") {
      const body = JSON.parse(String(init.body));
      return jsonResponse({ status: "ok", node: { ...graphNodes[0], label: body.label } });
    }
    if (url === "/api/web/knowledge/graph/nodes/concept%3Avpn" && init?.method === "DELETE") {
      return jsonResponse({ status: "ok", node: { ...graphNodes[0], status: "archived" } });
    }
    if (url === "/api/web/knowledge/graph/layouts/default" && init?.method === "POST") {
      return jsonResponse({
        status: "ok",
        layout: {
          layout_id: "layout-1",
          scope_type: "graph",
          scope_ref: "default",
          layout_json: JSON.parse(String(init.body)).layout_json,
        },
      });
    }
    throw new Error(`Unexpected fetch ${url}`);
  });
  vi.stubGlobal("fetch", fetchMock as typeof fetch);
  return fetchMock;
}

function renderGraphStudio() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  render(
    <QueryClientProvider client={queryClient}>
      <KnowledgeGraphStudioPage />
    </QueryClientProvider>,
  );
}

function edgePostCount(fetchMock: ReturnType<typeof setupFetch>) {
  return fetchMock.mock.calls.filter((call) => call[0] === "/api/web/knowledge/graph/edges" && call[1]?.method === "POST").length;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

beforeEach(() => {
  vi.stubGlobal(
    "ResizeObserver",
    class ResizeObserver {
      disconnect() {}
      observe() {}
      unobserve() {}
    },
  );
});

describe("KnowledgeGraphStudioPage", () => {
  it("renders a localized canvas-first graph workbench", async () => {
    setupFetch();
    renderGraphStudio();

    expect(await screen.findByRole("heading", { name: "Граф знаний" })).toBeInTheDocument();
    expect(await screen.findByTestId("knowledge-react-flow-canvas")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Проводник" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Холст" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Инспектор" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Выбрать" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Связать" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Добавить узел" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Проверить" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Авто-схема" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Сохранить схему" })).toBeInTheDocument();

    expect(
      screen.queryByText(
        /Production Graph Editor|Explorer|Canvas|Inspector|Connect Mode|Connect|Save graph|Relation palette|Connection inspector|Node palette|All nodes|Label|Type|Visibility|Status|Approve|Reject/i,
      ),
    ).not.toBeInTheDocument();
  });

  it("selects nodes and opens linked articles from the inspector", async () => {
    setupFetch();
    renderGraphStudio();

    fireEvent.click((await screen.findAllByRole("button", { name: /Статья про доступ VPN/ }))[0]);

    expect(await screen.findByRole("heading", { name: "Свойства узла" })).toBeInTheDocument();
    expect(screen.getByLabelText("Название узла")).toHaveValue("Статья про доступ VPN");
    expect(screen.getByRole("link", { name: "Открыть статью в Студии" })).toHaveAttribute(
      "href",
      "/app/admin/knowledge/studio?item=item-vpn",
    );
  });

  it("creates a node from the graph editor without manual stable key entry", async () => {
    const fetchMock = setupFetch();
    renderGraphStudio();

    await screen.findByRole("heading", { name: "Граф знаний" });
    fireEvent.click(screen.getByRole("button", { name: "Добавить узел" }));
    fireEvent.change(screen.getByLabelText("Название нового узла"), { target: { value: "Новая статья" } });
    fireEvent.change(screen.getByLabelText("Тип нового узла"), { target: { value: "knowledge_item" } });
    fireEvent.change(screen.getByLabelText("Видимость нового узла"), { target: { value: "requester" } });
    fireEvent.click(screen.getByRole("button", { name: "Создать узел" }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/knowledge/graph/nodes",
        expect.objectContaining({ method: "POST", credentials: "same-origin" }),
      ),
    );
    const createNodeCall = fetchMock.mock.calls.find((call) => call[0] === "/api/web/knowledge/graph/nodes" && call[1]?.method === "POST");
    expect(JSON.parse(String(createNodeCall?.[1]?.body))).toMatchObject({
      stable_key: "knowledge_item:novaya-statya",
      label: "Новая статья",
      node_type: "knowledge_item",
      visibility: "requester",
    });
  });

  it("validates connection drafts and creates real graph edges", async () => {
    const fetchMock = setupFetch();
    renderGraphStudio();

    await screen.findByRole("heading", { name: "Граф знаний" });
    fireEvent.click(screen.getByRole("button", { name: "Связать" }));
    const draft = screen.getByRole("group", { name: "Черновик связи" });

    fireEvent.change(within(draft).getByLabelText("Источник"), { target: { value: "concept:vpn" } });
    fireEvent.change(within(draft).getByLabelText("Цель"), { target: { value: "concept:vpn" } });
    fireEvent.click(within(draft).getByRole("button", { name: "Создать связь" }));
    expect(await screen.findByText("Нельзя связать узел с самим собой.")).toBeInTheDocument();
    expect(edgePostCount(fetchMock)).toBe(0);

    fireEvent.change(within(draft).getByLabelText("Цель"), { target: { value: "knowledge_item:vpn-access" } });
    fireEvent.change(within(draft).getByLabelText("Тип связи"), { target: { value: "mentions" } });
    fireEvent.click(within(draft).getByRole("button", { name: "Создать связь" }));
    expect(await screen.findByText("Такая связь уже есть в графе.")).toBeInTheDocument();
    expect(edgePostCount(fetchMock)).toBe(0);

    fireEvent.change(within(draft).getByLabelText("Тип связи"), { target: { value: "related_to" } });
    fireEvent.click(within(draft).getByRole("button", { name: "Создать связь" }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/knowledge/graph/edges",
        expect.objectContaining({ method: "POST", credentials: "same-origin" }),
      ),
    );
    const createEdgeCall = fetchMock.mock.calls.find((call) => call[0] === "/api/web/knowledge/graph/edges" && call[1]?.method === "POST");
    expect(JSON.parse(String(createEdgeCall?.[1]?.body))).toMatchObject({
      source_stable_key: "concept:vpn",
      target_stable_key: "knowledge_item:vpn-access",
      relation_type: "related_to",
      visibility: "support_internal",
    });
  });

  it("edits selected edges through the inspector", async () => {
    const fetchMock = setupFetch();
    renderGraphStudio();

    fireEvent.click(await screen.findByRole("button", { name: "Выбрать связь Упоминает" }));

    expect(await screen.findByRole("heading", { name: "Свойства связи" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Тип выбранной связи"), { target: { value: "supersedes" } });
    fireEvent.change(screen.getByLabelText("Вес связи"), { target: { value: "0.5" } });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить связь" }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/knowledge/graph/edges/edge-1",
        expect.objectContaining({ method: "PATCH", credentials: "same-origin" }),
      ),
    );
    const patchCall = fetchMock.mock.calls.find((call) => call[0] === "/api/web/knowledge/graph/edges/edge-1" && call[1]?.method === "PATCH");
    expect(JSON.parse(String(patchCall?.[1]?.body))).toMatchObject({ relation_type: "supersedes", weight: 0.5 });

    fireEvent.click(screen.getByRole("button", { name: "Архивировать связь" }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/knowledge/graph/edges/edge-1",
        expect.objectContaining({ method: "DELETE", credentials: "same-origin" }),
      ),
    );
  });

  it("saves dirty layout state and reviews AI proposals", async () => {
    const fetchMock = setupFetch();
    renderGraphStudio();

    await screen.findByRole("heading", { name: "Граф знаний" });
    fireEvent.click(screen.getByRole("button", { name: "Авто-схема" }));
    expect(screen.getByText("Есть несохранённые изменения схемы")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Сохранить схему" }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/knowledge/graph/layouts/default",
        expect.objectContaining({ method: "POST", credentials: "same-origin" }),
      ),
    );
    const saveLayoutCall = fetchMock.mock.calls.find((call) => call[0] === "/api/web/knowledge/graph/layouts/default" && call[1]?.method === "POST");
    expect(JSON.parse(String(saveLayoutCall?.[1]?.body))).toMatchObject({
      layout_json: {
        nodes: {
          "concept:vpn": expect.objectContaining({ x: expect.any(Number), y: expect.any(Number) }),
        },
      },
    });

    expect(await screen.findByText("Предложения AI")).toBeInTheDocument();
    expect(screen.getByText("Связать понятие VPN со статьёй")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Одобрить предложение" }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/knowledge/ai/proposals/prop-graph-1/review",
        expect.objectContaining({ method: "POST", credentials: "same-origin" }),
      ),
    );
    const reviewCall = fetchMock.mock.calls.find((call) => call[0] === "/api/web/knowledge/ai/proposals/prop-graph-1/review");
    expect(JSON.parse(String(reviewCall?.[1]?.body))).toMatchObject({ action: "approve" });
  });
});
