import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { GitBranch, Link2, MousePointer2, PlusCircle, RefreshCw, Save, Sparkles, Trash2 } from "lucide-react";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { PageHeading } from "../../components/ui/page-heading";
import { AdvancedDisclosure } from "../../components/ui-page/advanced-disclosure";
import { KnowledgeGraphCanvas, type KnowledgeGraphCanvasPosition } from "./knowledge-graph-canvas";
import {
  createKnowledgeGraphEdge,
  createKnowledgeGraphNode,
  deleteKnowledgeGraphEdge,
  deleteKnowledgeGraphNode,
  fetchKnowledgeGraphLayout,
  fetchKnowledgeGraphNeighborhood,
  fetchKnowledgeGraphNodes,
  fetchKnowledgeAiProposals,
  reviewKnowledgeAiProposal,
  saveKnowledgeGraphLayout,
  updateKnowledgeGraphNode,
  type KnowledgeAiProposal,
  type KnowledgeGraphEdge,
  type KnowledgeGraphLayout,
  type KnowledgeGraphNode,
} from "./api";

const fieldClass = "mt-1 w-full rounded-md border border-slate-200 px-3 py-2 text-sm";

type NodeDraft = {
  label: string;
  linked_item_id: string;
  node_type: string;
  offering_code: string;
  service_code: string;
  stable_key: string;
  visibility: string;
};

type EdgeDraft = {
  relation_type: string;
  source_stable_key: string;
  target_stable_key: string;
  visibility: string;
};

type PositionedNode = KnowledgeGraphNode & {
  x: number;
  y: number;
};

type LayoutPosition = {
  x: number;
  y: number;
};

function emptyToNull(value: string) {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function stableKeyFromLabel(nodeType: string, label: string) {
  const slug = label
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9а-яё]+/gi, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 64);
  return `${nodeType || "concept"}:${slug || "new-node"}`;
}

function savedPosition(layout: KnowledgeGraphLayout | undefined, stableKey: string): LayoutPosition | null {
  const nodes = layout?.layout_json?.nodes;
  if (!nodes || typeof nodes !== "object") {
    return null;
  }
  const position = (nodes as Record<string, unknown>)[stableKey];
  if (!position || typeof position !== "object") {
    return null;
  }
  const candidate = position as Record<string, unknown>;
  if (typeof candidate.x !== "number" || typeof candidate.y !== "number") {
    return null;
  }
  return { x: candidate.x, y: candidate.y };
}

function layoutNodes(nodes: KnowledgeGraphNode[], layout?: KnowledgeGraphLayout): PositionedNode[] {
  const centerX = 450;
  const centerY = 280;
  const radiusX = 310;
  const radiusY = 190;
  if (nodes.length === 1) {
    const saved = savedPosition(layout, nodes[0].stable_key);
    return [{ ...nodes[0], x: saved?.x ?? centerX, y: saved?.y ?? centerY }];
  }
  return nodes.map((node, index) => {
    const saved = savedPosition(layout, node.stable_key);
    if (saved) {
      return { ...node, x: saved.x, y: saved.y };
    }
    const angle = (Math.PI * 2 * index) / Math.max(nodes.length, 1) - Math.PI / 2;
    return {
      ...node,
      x: Math.round(centerX + Math.cos(angle) * radiusX),
      y: Math.round(centerY + Math.sin(angle) * radiusY),
    };
  });
}

function nodeTone(node: KnowledgeGraphNode) {
  if (node.node_type === "knowledge_item") {
    return "brand" as const;
  }
  if (node.node_type === "service" || node.node_type === "offering") {
    return "info" as const;
  }
  return "neutral" as const;
}

function edgeKey(edge: KnowledgeGraphEdge, nodesById: Map<string, KnowledgeGraphNode>) {
  const source = nodesById.get(edge.source_node_id)?.stable_key ?? edge.source_node_id;
  const target = nodesById.get(edge.target_node_id)?.stable_key ?? edge.target_node_id;
  return `${source} -> ${target}`;
}

export function KnowledgeGraphStudioPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [selectedStableKey, setSelectedStableKey] = useState("");
  const [selectedLabel, setSelectedLabel] = useState("");
  const [flowPositions, setFlowPositions] = useState<Record<string, KnowledgeGraphCanvasPosition>>({});
  const [nodeDraft, setNodeDraft] = useState<NodeDraft>({
    label: "",
    linked_item_id: "",
    node_type: "concept",
    offering_code: "",
    service_code: "",
    stable_key: "",
    visibility: "support_internal",
  });
  const [edgeDraft, setEdgeDraft] = useState<EdgeDraft>({
    relation_type: "mentions",
    source_stable_key: "",
    target_stable_key: "",
    visibility: "support_internal",
  });

  const nodesQuery = useQuery({ queryKey: ["knowledge-graph-nodes"], queryFn: fetchKnowledgeGraphNodes });
  const nodes = nodesQuery.data ?? [];
  const filteredNodes = useMemo(() => {
    const needle = search.trim().toLowerCase();
    if (!needle) {
      return nodes;
    }
    return nodes.filter((node) =>
      [node.label, node.stable_key, node.node_type, node.visibility].some((value) => String(value ?? "").toLowerCase().includes(needle)),
    );
  }, [nodes, search]);
  const selectedNode = nodes.find((node) => node.stable_key === selectedStableKey) ?? filteredNodes[0] ?? null;

  const neighborhoodQuery = useQuery({
    enabled: Boolean(selectedNode?.stable_key),
    queryKey: ["knowledge-graph-neighborhood", selectedNode?.stable_key],
    queryFn: () => fetchKnowledgeGraphNeighborhood(selectedNode?.stable_key ?? "", 2),
  });
  const graphNodes = neighborhoodQuery.data?.nodes.length ? neighborhoodQuery.data.nodes : filteredNodes.slice(0, 12);
  const graphEdges = neighborhoodQuery.data?.edges ?? [];
  const layoutQuery = useQuery({ queryKey: ["knowledge-graph-layout", "default"], queryFn: () => fetchKnowledgeGraphLayout("default") });
  const proposalsQuery = useQuery({
    queryKey: ["knowledge-ai-proposals", "graph", "pending"],
    queryFn: () => fetchKnowledgeAiProposals({ target_kind: "graph", status: "pending" }),
  });
  const positionedNodes = useMemo(() => layoutNodes(graphNodes, layoutQuery.data), [graphNodes, layoutQuery.data]);
  const positionedNodesForCanvas = useMemo(
    () =>
      positionedNodes.map((node) => {
        const position = flowPositions[node.stable_key];
        return position ? { ...node, x: position.x, y: position.y } : node;
      }),
    [flowPositions, positionedNodes],
  );
  const graphNodesById = useMemo(() => new Map(graphNodes.map((node) => [node.node_id, node])), [graphNodes]);

  useEffect(() => {
    if (!selectedStableKey && filteredNodes[0]?.stable_key) {
      setSelectedStableKey(filteredNodes[0].stable_key);
    }
  }, [filteredNodes, selectedStableKey]);

  useEffect(() => {
    if (selectedNode?.stable_key && !edgeDraft.source_stable_key) {
      setEdgeDraft((current) => ({ ...current, source_stable_key: selectedNode.stable_key }));
    }
  }, [edgeDraft.source_stable_key, selectedNode?.stable_key]);

  useEffect(() => {
    if (selectedNode?.stable_key) {
      setSelectedLabel(selectedNode.label);
    }
  }, [selectedNode?.stable_key, selectedNode?.label]);

  const createNodeMutation = useMutation({
    mutationFn: () =>
      createKnowledgeGraphNode({
        label: nodeDraft.label.trim(),
        linked_item_id: emptyToNull(nodeDraft.linked_item_id),
        node_type: nodeDraft.node_type,
        offering_code: emptyToNull(nodeDraft.offering_code),
        service_code: emptyToNull(nodeDraft.service_code),
        stable_key: nodeDraft.stable_key.trim() || stableKeyFromLabel(nodeDraft.node_type, nodeDraft.label),
        visibility: nodeDraft.visibility,
      }),
    onSuccess: (result) => {
      setSelectedStableKey(result.node.stable_key);
      setNodeDraft((current) => ({ ...current, label: "", linked_item_id: "", offering_code: "", service_code: "", stable_key: "" }));
      queryClient.invalidateQueries({ queryKey: ["knowledge-graph-nodes"] });
    },
  });

  const createEdgeMutation = useMutation({
    mutationFn: (draftOverride?: EdgeDraft) => createKnowledgeGraphEdge(draftOverride ?? edgeDraft),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["knowledge-graph-nodes"] });
      queryClient.invalidateQueries({ queryKey: ["knowledge-graph-neighborhood", selectedNode?.stable_key] });
    },
  });

  const updateSelectedNodeMutation = useMutation({
    mutationFn: () => updateKnowledgeGraphNode(selectedNode?.stable_key ?? "", { label: selectedLabel.trim() }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["knowledge-graph-nodes"] });
      queryClient.invalidateQueries({ queryKey: ["knowledge-graph-neighborhood", selectedNode?.stable_key] });
    },
  });

  const archiveSelectedNodeMutation = useMutation({
    mutationFn: () => deleteKnowledgeGraphNode(selectedNode?.stable_key ?? ""),
    onSuccess: () => {
      setSelectedStableKey("");
      queryClient.invalidateQueries({ queryKey: ["knowledge-graph-nodes"] });
      queryClient.invalidateQueries({ queryKey: ["knowledge-graph-neighborhood", selectedNode?.stable_key] });
    },
  });

  const archiveEdgeMutation = useMutation({
    mutationFn: (edgeId: string) => deleteKnowledgeGraphEdge(edgeId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["knowledge-graph-nodes"] });
      queryClient.invalidateQueries({ queryKey: ["knowledge-graph-neighborhood", selectedNode?.stable_key] });
    },
  });

  const saveLayoutMutation = useMutation({
    mutationFn: () =>
      saveKnowledgeGraphLayout("default", {
        nodes: Object.fromEntries(positionedNodesForCanvas.map((node) => [node.stable_key, { x: node.x, y: node.y }])),
        viewport: { zoom: 1, pan_x: 0, pan_y: 0 },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["knowledge-graph-layout", "default"] });
    },
  });

  const reviewProposalMutation = useMutation({
    mutationFn: ({ proposalId, action }: { proposalId: string; action: "approve" | "reject" | "comment" }) =>
      reviewKnowledgeAiProposal(proposalId, { action }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["knowledge-ai-proposals", "graph", "pending"] });
      queryClient.invalidateQueries({ queryKey: ["knowledge-graph-nodes"] });
      queryClient.invalidateQueries({ queryKey: ["knowledge-graph-neighborhood", selectedNode?.stable_key] });
    },
  });

  function selectGraphNode(stableKey: string) {
    setSelectedStableKey(stableKey);
    setEdgeDraft((current) => ({ ...current, source_stable_key: stableKey }));
  }

  function connectGraphNodes(connection: { source_stable_key: string; target_stable_key: string }) {
    const nextDraft = {
      ...edgeDraft,
      source_stable_key: connection.source_stable_key,
      target_stable_key: connection.target_stable_key,
    };
    setEdgeDraft(nextDraft);
    createEdgeMutation.mutate(nextDraft);
  }

  return (
    <section className="space-y-6">
      <PageHeading
        eyebrow="Knowledge Graph"
        title="Граф знаний"
        description="Визуальная карта узлов, связей и article relationships поверх существующего graph API."
      />

      <div className="grid gap-5 xl:grid-cols-[320px_minmax(0,1fr)_360px]">
        <aside className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <GitBranch className="h-5 w-5" />
                Узлы графа
              </CardTitle>
              <CardDescription>Поиск и выбор root node для neighborhood depth 2.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <label className="text-sm font-medium">
                Поиск узлов
                <input className={fieldClass} value={search} onChange={(event) => setSearch(event.target.value)} />
              </label>
              <div className="max-h-[520px] space-y-2 overflow-auto pr-1">
                {filteredNodes.map((node) => (
                  <button
                    className={`w-full rounded-md border px-3 py-2 text-left text-sm transition-colors ${
                      node.stable_key === selectedNode?.stable_key ? "border-brand-300 bg-brand-50" : "border-slate-200 bg-white hover:border-slate-300"
                    }`}
                    key={node.node_id}
                    onClick={() => selectGraphNode(node.stable_key)}
                    type="button"
                  >
                    <span className="font-semibold text-slate-950">{node.label}</span>
                    <span className="mt-1 block break-all text-xs text-slate-500">{node.stable_key}</span>
                  </button>
                ))}
                {!nodesQuery.isLoading && !filteredNodes.length ? <p className="text-sm text-slate-500">Узлы графа не найдены.</p> : null}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <PlusCircle className="h-5 w-5" />
                Новый узел
              </CardTitle>
              <CardDescription>Manual graph edits пишутся в существующий governed node API.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <label className="text-sm font-medium">
                Метка узла
                <input className={fieldClass} value={nodeDraft.label} onChange={(event) => setNodeDraft({ ...nodeDraft, label: event.target.value })} />
              </label>
              <label className="text-sm font-medium">
                Тип узла
                <select className={fieldClass} value={nodeDraft.node_type} onChange={(event) => setNodeDraft({ ...nodeDraft, node_type: event.target.value })}>
                  <option value="concept">concept</option>
                  <option value="knowledge_item">knowledge_item</option>
                  <option value="service">service</option>
                  <option value="offering">offering</option>
                  <option value="known_error">known_error</option>
                  <option value="workaround">workaround</option>
                </select>
              </label>
              <label className="text-sm font-medium">
                Видимость узла
                <select className={fieldClass} value={nodeDraft.visibility} onChange={(event) => setNodeDraft({ ...nodeDraft, visibility: event.target.value })}>
                  <option value="requester">requester</option>
                  <option value="agent_requester_safe">agent_requester_safe</option>
                  <option value="support_internal">support_internal</option>
                  <option value="admin_internal">admin_internal</option>
                </select>
              </label>
              <AdvancedDisclosure description="Stable key и технические ссылки нужны для миграций, точного связывания и debug-сценариев." title="Advanced: graph ids">
                <label className="text-sm font-medium">
                  Ключ узла
                  <input className={fieldClass} value={nodeDraft.stable_key} onChange={(event) => setNodeDraft({ ...nodeDraft, stable_key: event.target.value })} />
                </label>
                <label className="text-sm font-medium">
                  Service code
                  <input className={fieldClass} value={nodeDraft.service_code} onChange={(event) => setNodeDraft({ ...nodeDraft, service_code: event.target.value })} />
                </label>
                <label className="text-sm font-medium">
                  Offering code
                  <input className={fieldClass} value={nodeDraft.offering_code} onChange={(event) => setNodeDraft({ ...nodeDraft, offering_code: event.target.value })} />
                </label>
                <label className="text-sm font-medium">
                  Linked item id
                  <input className={fieldClass} value={nodeDraft.linked_item_id} onChange={(event) => setNodeDraft({ ...nodeDraft, linked_item_id: event.target.value })} />
                </label>
              </AdvancedDisclosure>
              <Button disabled={!nodeDraft.label.trim() || createNodeMutation.isPending} onClick={() => createNodeMutation.mutate()}>
                Создать узел
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Sparkles className="h-5 w-5" />
                AI proposals
              </CardTitle>
              <CardDescription>Pending graph proposals stay review-gated before they touch nodes or edges.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {(proposalsQuery.data ?? []).map((proposal: KnowledgeAiProposal) => (
                <div className="rounded-md border border-slate-200 bg-white p-3 text-sm" key={proposal.proposal_id}>
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="font-semibold text-slate-950">{proposal.title}</p>
                      <p className="mt-1 text-xs text-slate-500">
                        {proposal.proposal_type} · {proposal.status}
                      </p>
                    </div>
                    <Badge tone="warning">{proposal.confidence_score ?? "AI"}</Badge>
                  </div>
                  {proposal.rationale ? <p className="mt-2 text-xs text-slate-600">{proposal.rationale}</p> : null}
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button
                      aria-label={`Approve proposal ${proposal.proposal_id}`}
                      disabled={reviewProposalMutation.isPending}
                      onClick={() => reviewProposalMutation.mutate({ proposalId: proposal.proposal_id, action: "approve" })}
                      size="sm"
                    >
                      Approve
                    </Button>
                    <Button
                      aria-label={`Reject proposal ${proposal.proposal_id}`}
                      disabled={reviewProposalMutation.isPending}
                      onClick={() => reviewProposalMutation.mutate({ proposalId: proposal.proposal_id, action: "reject" })}
                      size="sm"
                      variant="outline"
                    >
                      Reject
                    </Button>
                  </div>
                </div>
              ))}
              {!proposalsQuery.isLoading && !(proposalsQuery.data ?? []).length ? <p className="text-sm text-slate-500">No pending graph AI proposals.</p> : null}
            </CardContent>
          </Card>
        </aside>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <MousePointer2 className="h-5 w-5" />
                Карта graph neighborhood
              </CardTitle>
              <CardDescription>React Flow рабочая область: выбор, drag layout и connect создают реальные изменения через graph API.</CardDescription>
            </CardHeader>
            <CardContent>
              <KnowledgeGraphCanvas
                edges={graphEdges}
                nodes={positionedNodesForCanvas}
                nodesById={graphNodesById}
                onConnectNodes={connectGraphNodes}
                onLayoutChange={setFlowPositions}
                onSelectNode={selectGraphNode}
                selectedStableKey={selectedNode?.stable_key}
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <RefreshCw className="h-5 w-5" />
                Warnings и coverage
              </CardTitle>
              <CardDescription>Ручные nodes/edges и persisted layout; AI proposals идут отдельным backend slice.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 text-sm text-slate-600 md:grid-cols-2 2xl:grid-cols-4">
              <div className="rounded-md bg-slate-50 p-3">
                <p className="font-semibold text-slate-900">Узлы</p>
                <p>{graphNodes.length} в текущем neighborhood</p>
              </div>
              <div className="rounded-md bg-slate-50 p-3">
                <p className="font-semibold text-slate-900">Связи</p>
                <p>{graphEdges.length} видимых edge</p>
              </div>
              <div className="rounded-md bg-amber-50 p-3 text-amber-800">
                <p className="font-semibold">AI suggestions</p>
                <p>Отключены до policy-gated proposals API.</p>
              </div>
              <div className="rounded-md bg-emerald-50 p-3 text-emerald-900">
                <p className="font-semibold">Layout</p>
                <p>{layoutQuery.data?.layout_id ? "Layout сохранен для scope default" : "Layout еще не сохранен"}</p>
                <Button
                  className="mt-3"
                  disabled={!positionedNodesForCanvas.length || saveLayoutMutation.isPending}
                  onClick={() => saveLayoutMutation.mutate()}
                  size="sm"
                  variant="secondary"
                >
                  <Save className="h-4 w-4" />
                  Сохранить layout
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>

        <aside className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Инспектор</CardTitle>
              <CardDescription>Выбранный node и связи neighborhood.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              {selectedNode ? (
                <>
                  <div className="space-y-1">
                    <p className="text-xs uppercase text-slate-500">Node</p>
                    <p className="font-semibold text-slate-950">{selectedNode.label}</p>
                    <p className="break-all text-slate-500">{selectedNode.stable_key}</p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Badge tone={nodeTone(selectedNode)}>{selectedNode.node_type}</Badge>
                    <Badge tone="neutral">{selectedNode.visibility}</Badge>
                    <Badge tone={selectedNode.status === "archived" ? "danger" : "success"}>{selectedNode.status ?? "active"}</Badge>
                  </div>
                  <div className="space-y-2 rounded-md border border-slate-200 p-3">
                    <label className="text-sm font-medium">
                      Метка выбранного узла
                      <input className={fieldClass} value={selectedLabel} onChange={(event) => setSelectedLabel(event.target.value)} />
                    </label>
                    <div className="flex flex-wrap gap-2">
                      <Button
                        disabled={!selectedNode || !selectedLabel.trim() || updateSelectedNodeMutation.isPending}
                        onClick={() => updateSelectedNodeMutation.mutate()}
                        size="sm"
                      >
                        Сохранить узел
                      </Button>
                      <Button
                        disabled={!selectedNode || archiveSelectedNodeMutation.isPending}
                        onClick={() => archiveSelectedNodeMutation.mutate()}
                        size="sm"
                        variant="outline"
                      >
                        <Trash2 className="h-4 w-4" />
                        Архивировать выбранный узел
                      </Button>
                    </div>
                  </div>
                </>
              ) : (
                <p className="text-slate-500">Выберите узел графа.</p>
              )}
              <div className="space-y-2">
                <p className="text-xs font-semibold uppercase text-slate-500">Связи</p>
                {graphEdges.map((edge) => (
                  <div className="rounded-md border border-slate-200 p-3" key={edge.edge_id}>
                    <p className="font-semibold text-slate-900">{edge.relation_type}</p>
                    <p className="mt-1 break-all text-xs text-slate-500">{edgeKey(edge, graphNodesById)}</p>
                    <Button
                      aria-label={`Архивировать связь ${edge.edge_id}`}
                      className="mt-3"
                      disabled={archiveEdgeMutation.isPending}
                      onClick={() => archiveEdgeMutation.mutate(edge.edge_id)}
                      size="sm"
                      variant="outline"
                    >
                      <Trash2 className="h-4 w-4" />
                      Архивировать
                    </Button>
                  </div>
                ))}
                {!graphEdges.length ? <p className="text-slate-500">Для выбранного узла связи не найдены.</p> : null}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Link2 className="h-5 w-5" />
                Новая связь
              </CardTitle>
              <CardDescription>Связь создается по stable_key source/target.</CardDescription>
            </CardHeader>
            <CardContent>
              <fieldset aria-label="Новая связь" className="space-y-3">
                <label className="text-sm font-medium">
                  Источник edge
                  <input className={fieldClass} value={edgeDraft.source_stable_key} onChange={(event) => setEdgeDraft({ ...edgeDraft, source_stable_key: event.target.value })} />
                </label>
                <label className="text-sm font-medium">
                  Цель edge
                  <input className={fieldClass} value={edgeDraft.target_stable_key} onChange={(event) => setEdgeDraft({ ...edgeDraft, target_stable_key: event.target.value })} />
                </label>
                <label className="text-sm font-medium">
                  Тип связи
                  <select className={fieldClass} value={edgeDraft.relation_type} onChange={(event) => setEdgeDraft({ ...edgeDraft, relation_type: event.target.value })}>
                    <option value="mentions">mentions</option>
                    <option value="belongs_to_service">belongs_to_service</option>
                    <option value="belongs_to_offering">belongs_to_offering</option>
                    <option value="supersedes">supersedes</option>
                    <option value="contradicts">contradicts</option>
                  </select>
                </label>
                <label className="text-sm font-medium">
                  Видимость edge
                  <select className={fieldClass} value={edgeDraft.visibility} onChange={(event) => setEdgeDraft({ ...edgeDraft, visibility: event.target.value })}>
                    <option value="requester">requester</option>
                    <option value="agent_requester_safe">agent_requester_safe</option>
                    <option value="support_internal">support_internal</option>
                    <option value="admin_internal">admin_internal</option>
                  </select>
                </label>
                <Button
                  disabled={!edgeDraft.source_stable_key.trim() || !edgeDraft.target_stable_key.trim() || createEdgeMutation.isPending}
                  onClick={() => createEdgeMutation.mutate(undefined)}
                >
                  Создать связь
                </Button>
              </fieldset>
            </CardContent>
          </Card>
        </aside>
      </div>
    </section>
  );
}
