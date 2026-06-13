import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import type { KnowledgeGraphNode } from "../api";
import { fetchKnowledgeAiProposals, fetchKnowledgeGraphLayout, fetchKnowledgeGraphNeighborhood, fetchKnowledgeGraphNodes } from "../api";
import { autoLayoutNodes, layoutNodes, layoutPayload, mergePositionSnapshot } from "./graphLayout";
import {
  draftFromEdge,
  draftFromNode,
  emptyEdgeDraft,
  emptyNodeDraft,
  generateStableKey,
  parseOptionalNumber,
  type EdgeDraft,
  type SelectedEdgeDraft,
  type SelectedNodeDraft,
} from "./graphTypes";
import { validateConnection, validateGraph } from "./graphValidation";
import { useGraphEditorState } from "./useGraphEditorState";
import { useGraphMutations } from "./useGraphMutations";

function emptyToNull(value: string) {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function chooseInitialNode(nodes: KnowledgeGraphNode[], selectedStableKey: string) {
  return nodes.find((node) => node.stable_key === selectedStableKey) ?? nodes[0] ?? null;
}

export function useGraphEditorController() {
  const editor = useGraphEditorState();
  const mutations = useGraphMutations(editor.selectedStableKey);
  const [selectedNodeDraft, setSelectedNodeDraft] = useState<SelectedNodeDraft>(() => draftFromNode(null));
  const [selectedEdgeDraft, setSelectedEdgeDraft] = useState<SelectedEdgeDraft>(() => draftFromEdge(null));

  const nodesQuery = useQuery({ queryKey: ["knowledge-graph-nodes"], queryFn: fetchKnowledgeGraphNodes });
  const allNodes = nodesQuery.data ?? [];
  const selectedNode = chooseInitialNode(allNodes, editor.selectedStableKey);

  useEffect(() => {
    if (!editor.selectedStableKey && allNodes[0]?.stable_key) {
      editor.setSelectedStableKey(allNodes[0].stable_key);
    }
  }, [allNodes, editor.selectedStableKey, editor.setSelectedStableKey]);

  const neighborhoodQuery = useQuery({
    enabled: Boolean(selectedNode?.stable_key),
    queryKey: ["knowledge-graph-neighborhood", selectedNode?.stable_key],
    queryFn: () => fetchKnowledgeGraphNeighborhood(selectedNode?.stable_key ?? "", 2),
  });
  const layoutQuery = useQuery({ queryKey: ["knowledge-graph-layout", "default"], queryFn: () => fetchKnowledgeGraphLayout("default") });
  const proposalsQuery = useQuery({
    queryKey: ["knowledge-ai-proposals", "graph", "pending"],
    queryFn: () => fetchKnowledgeAiProposals({ target_kind: "graph", status: "pending" }),
  });

  const graphNodes = neighborhoodQuery.data?.nodes.length ? neighborhoodQuery.data.nodes : allNodes.slice(0, 12);
  const graphEdges = neighborhoodQuery.data?.edges ?? [];
  const nodesById = useMemo(() => new Map(graphNodes.map((node) => [node.node_id, node])), [graphNodes]);
  const positionedNodes = useMemo(
    () => layoutNodes(graphNodes, layoutQuery.data, editor.localPositions),
    [editor.localPositions, graphNodes, layoutQuery.data],
  );
  const selectedEdge = graphEdges.find((edge) => edge.edge_id === editor.selectedEdgeId) ?? null;
  const graphValidation = useMemo(() => validateGraph(graphNodes, graphEdges, nodesById), [graphEdges, graphNodes, nodesById]);

  useEffect(() => {
    setSelectedNodeDraft(draftFromNode(selectedNode));
  }, [selectedNode?.stable_key]);

  useEffect(() => {
    setSelectedEdgeDraft(draftFromEdge(selectedEdge));
  }, [selectedEdge?.edge_id]);

  useEffect(() => {
    if (selectedNode?.stable_key && !editor.edgeDraft.source_stable_key) {
      editor.setEdgeDraft((current) => ({ ...current, source_stable_key: selectedNode.stable_key }));
    }
  }, [editor.edgeDraft.source_stable_key, editor.setEdgeDraft, selectedNode?.stable_key]);

  function switchMode(mode: "select" | "connect" | "add_node" | "pan" | "lasso") {
    editor.setMode(mode);
    editor.setConnectionMessages([]);
    editor.setStatusMessage("");
    if (mode === "connect" && selectedNode?.stable_key) {
      editor.setEdgeDraft((current) => ({ ...current, source_stable_key: current.source_stable_key || selectedNode.stable_key }));
    }
    if (mode === "add_node") {
      editor.setSelectedEdgeId("");
    }
  }

  function selectNode(stableKey: string) {
    editor.setSelectedStableKey(stableKey);
    editor.setSelectedEdgeId("");
    editor.setConnectionMessages([]);
    if (editor.mode === "connect") {
      editor.setEdgeDraft((current) => {
        if (!current.source_stable_key || current.target_stable_key) {
          return { ...current, source_stable_key: stableKey, target_stable_key: "" };
        }
        if (current.source_stable_key === stableKey) {
          return { ...current, source_stable_key: stableKey, target_stable_key: "" };
        }
        return { ...current, target_stable_key: stableKey };
      });
    }
  }

  function selectEdge(edgeId: string) {
    editor.setSelectedEdgeId(edgeId);
    editor.setMode("select");
    editor.setConnectionMessages([]);
  }

  function openArticle(node: KnowledgeGraphNode) {
    if (node.linked_item_id) {
      window.location.assign(`/app/admin/knowledge/studio?item=${encodeURIComponent(node.linked_item_id)}`);
    }
  }

  function startConnect(stableKey?: string) {
    const sourceStableKey = stableKey ?? selectedNode?.stable_key ?? "";
    editor.setMode("connect");
    editor.setSelectedEdgeId("");
    editor.setEdgeDraft((current) => ({ ...current, source_stable_key: sourceStableKey, target_stable_key: "" }));
  }

  function duplicateNode(node?: KnowledgeGraphNode) {
    const source = node ?? selectedNode;
    if (!source) {
      return;
    }
    editor.setMode("add_node");
    editor.setSelectedEdgeId("");
    editor.setNodeDraft({
      label: `${source.label} копия`,
      node_type: source.node_type,
      visibility: source.visibility,
      linked_item_id: "",
      service_code: source.service_code ?? "",
      offering_code: source.offering_code ?? "",
    });
    const sourcePosition = positionedNodes.find((item) => item.stable_key === source.stable_key);
    editor.setQuickCreatePosition({ x: (sourcePosition?.x ?? 360) + 60, y: (sourcePosition?.y ?? 240) + 60 });
  }

  function validateEdgeDraft(draft: EdgeDraft) {
    const result = validateConnection({
      sourceStableKey: draft.source_stable_key,
      targetStableKey: draft.target_stable_key,
      relationType: draft.relation_type,
      edges: graphEdges,
      nodesById,
    });
    editor.setConnectionMessages(result.messages);
    return result;
  }

  function createEdgeFromDraft(draft: EdgeDraft) {
    const result = validateEdgeDraft(draft);
    if (!result.ok) {
      editor.setStatusMessage("Связь не создана: исправьте ошибки черновика.");
      return;
    }
    mutations.createEdge.mutate(
      {
        source_stable_key: draft.source_stable_key,
        target_stable_key: draft.target_stable_key,
        relation_type: draft.relation_type,
        visibility: draft.visibility,
        weight: parseOptionalNumber(draft.weight) ?? 1,
      },
      {
        onSuccess: (payload) => {
          editor.setSelectedEdgeId(payload.edge.edge_id);
          editor.setMode("select");
          editor.setEdgeDraft(emptyEdgeDraft(draft.source_stable_key));
          editor.setStatusMessage("Связь создана и сохранена в графе.");
          editor.setConnectionMessages([]);
        },
      },
    );
  }

  function createNode() {
    const stableKey = generateStableKey(editor.nodeDraft.node_type, editor.nodeDraft.label);
    mutations.createNode.mutate(
      {
        label: editor.nodeDraft.label.trim(),
        node_type: editor.nodeDraft.node_type,
        stable_key: stableKey,
        visibility: editor.nodeDraft.visibility,
        linked_item_id: emptyToNull(editor.nodeDraft.linked_item_id),
        service_code: emptyToNull(editor.nodeDraft.service_code),
        offering_code: emptyToNull(editor.nodeDraft.offering_code),
      },
      {
        onSuccess: (payload) => {
          const position = editor.quickCreatePosition ?? { x: 420, y: 260 };
          editor.setSelectedStableKey(payload.node.stable_key);
          editor.setLocalPositions((current) => ({ ...current, [payload.node.stable_key]: position }));
          editor.setLayoutDirty(true);
          editor.setMode("select");
          editor.setNodeDraft(emptyNodeDraft(editor.nodeDraft.node_type));
          editor.setStatusMessage("Узел создан. Сохраните схему, чтобы зафиксировать позицию.");
        },
      },
    );
  }

  function saveNode() {
    if (!selectedNode) {
      return;
    }
    mutations.updateNode.mutate(
      {
        stableKey: selectedNode.stable_key,
        payload: {
          label: selectedNodeDraft.label.trim(),
          node_type: selectedNodeDraft.node_type,
          visibility: selectedNodeDraft.visibility,
          status: selectedNodeDraft.status,
          linked_item_id: emptyToNull(selectedNodeDraft.linked_item_id),
          service_code: emptyToNull(selectedNodeDraft.service_code),
          offering_code: emptyToNull(selectedNodeDraft.offering_code),
        },
      },
      { onSuccess: () => editor.setStatusMessage("Узел сохранён.") },
    );
  }

  function archiveNode(stableKey?: string) {
    const targetStableKey = stableKey ?? selectedNode?.stable_key;
    if (!targetStableKey) {
      return;
    }
    mutations.archiveNode.mutate(targetStableKey, {
      onSuccess: () => {
        if (editor.selectedStableKey === targetStableKey) {
          editor.setSelectedStableKey("");
        }
        editor.setStatusMessage("Узел архивирован.");
      },
    });
  }

  function saveEdge() {
    if (!selectedEdge) {
      return;
    }
    mutations.updateEdge.mutate(
      {
        edgeId: selectedEdge.edge_id,
        payload: {
          relation_type: selectedEdgeDraft.relation_type,
          visibility: selectedEdgeDraft.visibility,
          status: selectedEdgeDraft.status,
          weight: parseOptionalNumber(selectedEdgeDraft.weight),
          confidence_score: parseOptionalNumber(selectedEdgeDraft.confidence_score),
        },
      },
      { onSuccess: () => editor.setStatusMessage("Связь сохранена.") },
    );
  }

  function archiveEdge() {
    if (!selectedEdge) {
      return;
    }
    mutations.archiveEdge.mutate(selectedEdge.edge_id, {
      onSuccess: () => {
        editor.setSelectedEdgeId("");
        editor.setStatusMessage("Связь архивирована.");
      },
    });
  }

  function saveLayout() {
    mutations.saveLayout.mutate(layoutPayload(positionedNodes), {
      onSuccess: () => {
        editor.setLayoutDirty(false);
        editor.setStatusMessage("Схема графа сохранена.");
      },
    });
  }

  function autoLayout() {
    editor.commitPositions(autoLayoutNodes(graphNodes));
    editor.setStatusMessage("Авто-схема применена. Сохраните схему, чтобы зафиксировать позиции.");
  }

  function commitCanvasPositions(positions: Record<string, { x: number; y: number }>) {
    editor.commitPositions({ ...mergePositionSnapshot(positionedNodes, editor.localPositions), ...positions });
  }

  function runValidation() {
    const result = editor.mode === "connect" ? validateEdgeDraft(editor.edgeDraft) : { ok: true, messages: [] };
    editor.setStatusMessage(
      result.ok ? "Проверка завершена: критичных ошибок для текущего действия нет." : "Проверка нашла ошибки связи.",
    );
  }

  return {
    actions: {
      archiveEdge,
      archiveNode,
      autoLayout,
      commitCanvasPositions,
      createEdgeFromDraft,
      createNode,
      duplicateNode,
      openArticle,
      runValidation,
      saveEdge,
      saveLayout,
      saveNode,
      selectEdge,
      selectNode,
      startConnect,
      switchMode,
    },
    allNodes,
    editor,
    graphEdges,
    graphNodes,
    graphValidation,
    mutations,
    nodesById,
    nodesQuery,
    positionedNodes,
    proposalsQuery,
    selectedEdge,
    selectedEdgeDraft,
    selectedNode,
    selectedNodeDraft,
    setSelectedEdgeDraft,
    setSelectedNodeDraft,
  };
}
