import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { GitBranch, Link2, MousePointer2, PlusCircle, RefreshCw } from "lucide-react";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { PageHeading } from "../../components/ui/page-heading";
import {
  createKnowledgeGraphEdge,
  createKnowledgeGraphNode,
  fetchKnowledgeGraphNeighborhood,
  fetchKnowledgeGraphNodes,
  type KnowledgeGraphEdge,
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

function emptyToNull(value: string) {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function layoutNodes(nodes: KnowledgeGraphNode[]): PositionedNode[] {
  const centerX = 450;
  const centerY = 280;
  const radiusX = 310;
  const radiusY = 190;
  if (nodes.length === 1) {
    return [{ ...nodes[0], x: centerX, y: centerY }];
  }
  return nodes.map((node, index) => {
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
  const positionedNodes = useMemo(() => layoutNodes(graphNodes), [graphNodes]);
  const positionedById = useMemo(() => new Map(positionedNodes.map((node) => [node.node_id, node])), [positionedNodes]);
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

  const createNodeMutation = useMutation({
    mutationFn: () =>
      createKnowledgeGraphNode({
        label: nodeDraft.label.trim(),
        linked_item_id: emptyToNull(nodeDraft.linked_item_id),
        node_type: nodeDraft.node_type,
        offering_code: emptyToNull(nodeDraft.offering_code),
        service_code: emptyToNull(nodeDraft.service_code),
        stable_key: nodeDraft.stable_key.trim(),
        visibility: nodeDraft.visibility,
      }),
    onSuccess: (result) => {
      setSelectedStableKey(result.node.stable_key);
      setNodeDraft((current) => ({ ...current, label: "", linked_item_id: "", offering_code: "", service_code: "", stable_key: "" }));
      queryClient.invalidateQueries({ queryKey: ["knowledge-graph-nodes"] });
    },
  });

  const createEdgeMutation = useMutation({
    mutationFn: () => createKnowledgeGraphEdge(edgeDraft),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["knowledge-graph-nodes"] });
      queryClient.invalidateQueries({ queryKey: ["knowledge-graph-neighborhood", selectedNode?.stable_key] });
    },
  });

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
                    onClick={() => {
                      setSelectedStableKey(node.stable_key);
                      setEdgeDraft((current) => ({ ...current, source_stable_key: node.stable_key }));
                    }}
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
                Ключ узла
                <input className={fieldClass} value={nodeDraft.stable_key} onChange={(event) => setNodeDraft({ ...nodeDraft, stable_key: event.target.value })} />
              </label>
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
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
                <label className="text-sm font-medium">
                  Service code
                  <input className={fieldClass} value={nodeDraft.service_code} onChange={(event) => setNodeDraft({ ...nodeDraft, service_code: event.target.value })} />
                </label>
                <label className="text-sm font-medium">
                  Linked item id
                  <input className={fieldClass} value={nodeDraft.linked_item_id} onChange={(event) => setNodeDraft({ ...nodeDraft, linked_item_id: event.target.value })} />
                </label>
              </div>
              <Button disabled={!nodeDraft.stable_key.trim() || !nodeDraft.label.trim() || createNodeMutation.isPending} onClick={() => createNodeMutation.mutate()}>
                Создать узел
              </Button>
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
              <CardDescription>SVG canvas без новой зависимости: nodes/edges кликабельны, layout пересчитывается из текущего neighborhood.</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="rounded-md border border-slate-200 bg-slate-950 p-3">
                <svg aria-label="Карта графа знаний" className="h-[560px] w-full" role="img" viewBox="0 0 900 560">
                  <title>Карта графа знаний</title>
                  <rect fill="#0f172a" height="560" rx="8" width="900" />
                  {graphEdges.map((edge) => {
                    const source = positionedById.get(edge.source_node_id);
                    const target = positionedById.get(edge.target_node_id);
                    if (!source || !target) {
                      return null;
                    }
                    const midX = (source.x + target.x) / 2;
                    const midY = (source.y + target.y) / 2;
                    return (
                      <g key={edge.edge_id}>
                        <line stroke="#38bdf8" strokeOpacity="0.55" strokeWidth="2" x1={source.x} x2={target.x} y1={source.y} y2={target.y} />
                        <text fill="#bae6fd" fontSize="12" textAnchor="middle" x={midX} y={midY - 8}>
                          {edge.relation_type}
                        </text>
                      </g>
                    );
                  })}
                  {positionedNodes.map((node) => {
                    const selected = node.stable_key === selectedNode?.stable_key;
                    return (
                      <g
                        aria-label={node.label}
                        key={node.node_id}
                        onClick={() => setSelectedStableKey(node.stable_key)}
                        role="button"
                        tabIndex={0}
                      >
                        <circle fill={selected ? "#f8fafc" : "#1e293b"} r={selected ? 42 : 36} stroke={selected ? "#22c55e" : "#94a3b8"} strokeWidth="3" cx={node.x} cy={node.y} />
                        <text fill={selected ? "#0f172a" : "#e2e8f0"} fontSize="12" fontWeight="700" textAnchor="middle" x={node.x} y={node.y - 4}>
                          {node.label.slice(0, 24)}
                        </text>
                        <text fill={selected ? "#334155" : "#cbd5e1"} fontSize="10" textAnchor="middle" x={node.x} y={node.y + 14}>
                          {node.node_type}
                        </text>
                      </g>
                    );
                  })}
                  {!positionedNodes.length ? (
                    <text fill="#cbd5e1" fontSize="18" textAnchor="middle" x="450" y="280">
                      Нет узлов для отображения
                    </text>
                  ) : null}
                </svg>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <RefreshCw className="h-5 w-5" />
                Warnings и coverage
              </CardTitle>
              <CardDescription>Первый Phase 9 slice покрывает ручные nodes/edges; persisted layout и AI proposals идут отдельным backend slice.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 text-sm text-slate-600 md:grid-cols-3">
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
                  onClick={() => createEdgeMutation.mutate()}
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
