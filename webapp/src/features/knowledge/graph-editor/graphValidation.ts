import type { KnowledgeGraphEdge, KnowledgeGraphNode } from "../api";

export type ConnectionValidationInput = {
  sourceStableKey: string;
  targetStableKey: string;
  relationType: string;
  edges: KnowledgeGraphEdge[];
  nodesById: Map<string, KnowledgeGraphNode>;
};

export type GraphValidationResult = {
  ok: boolean;
  messages: string[];
};

export function edgeStableKeys(edge: KnowledgeGraphEdge, nodesById: Map<string, KnowledgeGraphNode>) {
  return {
    sourceStableKey: nodesById.get(edge.source_node_id)?.stable_key ?? edge.source_node_id,
    targetStableKey: nodesById.get(edge.target_node_id)?.stable_key ?? edge.target_node_id,
  };
}

export function validateConnection(input: ConnectionValidationInput): GraphValidationResult {
  const messages: string[] = [];
  if (!input.sourceStableKey || !input.targetStableKey) {
    messages.push("Выберите источник и цель связи.");
  }
  if (input.sourceStableKey && input.sourceStableKey === input.targetStableKey) {
    messages.push("Нельзя связать узел с самим собой.");
  }
  if (!input.relationType) {
    messages.push("Выберите тип связи.");
  }
  const duplicate = input.edges.some((edge) => {
    if (edge.status === "archived") {
      return false;
    }
    const stableKeys = edgeStableKeys(edge, input.nodesById);
    return (
      stableKeys.sourceStableKey === input.sourceStableKey &&
      stableKeys.targetStableKey === input.targetStableKey &&
      edge.relation_type === input.relationType
    );
  });
  if (duplicate) {
    messages.push("Такая связь уже есть в графе.");
  }
  return { ok: messages.length === 0, messages };
}

export function validateGraph(nodes: KnowledgeGraphNode[], edges: KnowledgeGraphEdge[], nodesById: Map<string, KnowledgeGraphNode>) {
  const connectedStableKeys = new Set<string>();
  edges.forEach((edge) => {
    if (edge.status === "archived") {
      return;
    }
    const stableKeys = edgeStableKeys(edge, nodesById);
    connectedStableKeys.add(stableKeys.sourceStableKey);
    connectedStableKeys.add(stableKeys.targetStableKey);
  });
  const orphanNodes = nodes.filter((node) => !connectedStableKeys.has(node.stable_key));
  const duplicateKeys = new Set<string>();
  const seenKeys = new Set<string>();
  edges.forEach((edge) => {
    if (edge.status === "archived") {
      return;
    }
    const stableKeys = edgeStableKeys(edge, nodesById);
    const key = `${stableKeys.sourceStableKey}::${stableKeys.targetStableKey}::${edge.relation_type}`;
    if (seenKeys.has(key)) {
      duplicateKeys.add(key);
    }
    seenKeys.add(key);
  });
  const messages = [
    orphanNodes.length ? `${orphanNodes.length} узл. без активных связей` : "Нет изолированных узлов",
    duplicateKeys.size ? `${duplicateKeys.size} повторяющихся связей` : "Нет дублей связей",
  ];
  return {
    orphanCount: orphanNodes.length,
    duplicateCount: duplicateKeys.size,
    messages,
  };
}
