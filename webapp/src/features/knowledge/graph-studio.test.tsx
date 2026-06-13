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

function setupFetch() {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url === "/api/web/knowledge/graph/nodes" && !init?.method) {
      return jsonResponse({
        status: "ok",
        nodes: [
          {
            node_id: "node-vpn",
            stable_key: "concept:vpn",
            node_type: "concept",
            label: "VPN concept",
            visibility: "support_internal",
            status: "active",
          },
          {
            node_id: "node-article",
            stable_key: "knowledge_item:vpn-access",
            node_type: "knowledge_item",
            label: "VPN access article",
            visibility: "requester",
            status: "active",
          },
        ],
      });
    }
    if (url === "/api/web/knowledge/graph/nodes/concept%3Avpn/neighborhood?depth=2") {
      return jsonResponse({
        status: "ok",
        nodes: [
          {
            node_id: "node-vpn",
            stable_key: "concept:vpn",
            node_type: "concept",
            label: "VPN concept",
            visibility: "support_internal",
            status: "active",
          },
          {
            node_id: "node-article",
            stable_key: "knowledge_item:vpn-access",
            node_type: "knowledge_item",
            label: "VPN access article",
            visibility: "requester",
            status: "active",
          },
        ],
        edges: [
          {
            edge_id: "edge-1",
            source_node_id: "node-vpn",
            target_node_id: "node-article",
            relation_type: "mentions",
            visibility: "support_internal",
            status: "active",
          },
        ],
      });
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
              "concept:vpn": { x: 450, y: 90 },
              "knowledge_item:vpn-access": { x: 450, y: 470 },
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
            title: "Connect VPN concept to article",
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
          title: "Connect VPN concept to article",
          status: "approved",
        },
      });
    }
    if (url === "/api/web/knowledge/graph/nodes" && init?.method === "POST") {
      const body = JSON.parse(String(init.body));
      return jsonResponse({
        status: "ok",
        node: {
          node_id: "node-mfa",
          stable_key: body.stable_key,
          label: body.label,
          node_type: body.node_type,
          visibility: body.visibility,
        },
      });
    }
    if (url === "/api/web/knowledge/graph/edges" && init?.method === "POST") {
      return jsonResponse({
        status: "ok",
        edge: {
          edge_id: "edge-2",
          relation_type: JSON.parse(String(init.body)).relation_type,
        },
      });
    }
    if (url === "/api/web/knowledge/graph/nodes/concept%3Avpn" && init?.method === "PATCH") {
      const body = JSON.parse(String(init.body));
      return jsonResponse({
        status: "ok",
        node: {
          node_id: "node-vpn",
          stable_key: "concept:vpn",
          label: body.label,
          node_type: "concept",
          visibility: "support_internal",
          status: "confirmed",
        },
      });
    }
    if (url === "/api/web/knowledge/graph/edges/edge-1" && init?.method === "DELETE") {
      return jsonResponse({
        status: "ok",
        edge: {
          edge_id: "edge-1",
          source_node_id: "node-vpn",
          target_node_id: "node-article",
          relation_type: "mentions",
          visibility: "support_internal",
          status: "archived",
        },
      });
    }
    if (url === "/api/web/knowledge/graph/nodes/concept%3Avpn" && init?.method === "DELETE") {
      return jsonResponse({
        status: "ok",
        node: {
          node_id: "node-vpn",
          stable_key: "concept:vpn",
          label: "VPN concept",
          node_type: "concept",
          visibility: "support_internal",
          status: "archived",
        },
      });
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
  it("renders React Flow as the primary editable graph canvas instead of a read-only SVG map", async () => {
    setupFetch();
    renderGraphStudio();

    expect(await screen.findByRole("heading", { name: "Граф знаний" })).toBeInTheDocument();
    expect(await screen.findByTestId("knowledge-react-flow-canvas")).toBeInTheDocument();
    expect(screen.getByText("React Flow canvas")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Показать весь граф" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Авторазложить" })).toBeInTheDocument();
    expect(screen.queryByRole("img", { name: "Карта графа знаний" })).not.toBeInTheDocument();
  });

  it("loads a visual graph canvas and creates nodes and edges through graph APIs", async () => {
    const fetchMock = setupFetch();
    renderGraphStudio();

    expect(await screen.findByRole("heading", { name: "Граф знаний" })).toBeInTheDocument();
    expect((await screen.findAllByRole("button", { name: /VPN concept/ }))[0]).toBeInTheDocument();
    expect(await screen.findByTestId("knowledge-react-flow-canvas")).toBeInTheDocument();
    expect(screen.getByText("React Flow canvas")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Авторазложить" }));
    expect(screen.queryByRole("img", { name: "Карта графа знаний" })).not.toBeInTheDocument();
    expect(await screen.findByText("Layout сохранен для scope default")).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole("button", { name: /VPN concept/ })[0]);
    expect((await screen.findAllByText("mentions")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("VPN access article").length).toBeGreaterThan(0);

    fireEvent.change(screen.getByLabelText("Метка узла"), { target: { value: "MFA concept" } });
    fireEvent.change(screen.getByLabelText("Тип узла"), { target: { value: "concept" } });
    fireEvent.change(screen.getByLabelText("Видимость узла"), { target: { value: "support_internal" } });
    fireEvent.click(screen.getByText("Advanced: graph ids"));
    fireEvent.change(screen.getByLabelText("Ключ узла"), { target: { value: "concept:mfa" } });
    fireEvent.click(screen.getByRole("button", { name: "Создать узел" }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/knowledge/graph/nodes",
        expect.objectContaining({ method: "POST", credentials: "same-origin" }),
      ),
    );
    const createNodeCall = fetchMock.mock.calls.find((call) => call[0] === "/api/web/knowledge/graph/nodes" && call[1]?.method === "POST");
    expect(JSON.parse(String(createNodeCall?.[1]?.body))).toMatchObject({
      stable_key: "concept:mfa",
      label: "MFA concept",
      node_type: "concept",
      visibility: "support_internal",
    });

    const edgeForm = screen.getByRole("group", { name: "Новая связь" });
    fireEvent.change(within(edgeForm).getByLabelText("Источник edge"), { target: { value: "concept:mfa" } });
    fireEvent.change(within(edgeForm).getByLabelText("Цель edge"), { target: { value: "concept:vpn" } });
    fireEvent.change(within(edgeForm).getByLabelText("Тип связи"), { target: { value: "mentions" } });
    fireEvent.click(within(edgeForm).getByRole("button", { name: "Создать связь" }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/knowledge/graph/edges",
        expect.objectContaining({ method: "POST", credentials: "same-origin" }),
      ),
    );
    const createEdgeCall = fetchMock.mock.calls.find((call) => call[0] === "/api/web/knowledge/graph/edges" && call[1]?.method === "POST");
    expect(JSON.parse(String(createEdgeCall?.[1]?.body))).toMatchObject({
      source_stable_key: "concept:mfa",
      target_stable_key: "concept:vpn",
      relation_type: "mentions",
      visibility: "support_internal",
    });

    fireEvent.click(screen.getByRole("button", { name: "Сохранить layout" }));
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

    fireEvent.change(screen.getByLabelText("Метка выбранного узла"), { target: { value: "VPN concept updated" } });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить узел" }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/knowledge/graph/nodes/concept%3Avpn",
        expect.objectContaining({ method: "PATCH", credentials: "same-origin" }),
      ),
    );
    const updateNodeCall = fetchMock.mock.calls.find((call) => call[0] === "/api/web/knowledge/graph/nodes/concept%3Avpn" && call[1]?.method === "PATCH");
    expect(JSON.parse(String(updateNodeCall?.[1]?.body))).toMatchObject({ label: "VPN concept updated" });

    fireEvent.click(screen.getByRole("button", { name: "Архивировать связь edge-1" }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/knowledge/graph/edges/edge-1",
        expect.objectContaining({ method: "DELETE", credentials: "same-origin" }),
      ),
    );

    fireEvent.click(screen.getByRole("button", { name: "Архивировать выбранный узел" }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/knowledge/graph/nodes/concept%3Avpn",
        expect.objectContaining({ method: "DELETE", credentials: "same-origin" }),
      ),
    );

    expect(await screen.findByText("AI proposals")).toBeInTheDocument();
    expect(screen.getByText("Connect VPN concept to article")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Approve proposal prop-graph-1" }));
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
