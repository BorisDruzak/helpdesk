import type { KnowledgeGraphLayout, KnowledgeGraphNode } from "../api";
import type { GraphNodePosition, PositionedGraphNode } from "./graphTypes";

function savedPosition(layout: KnowledgeGraphLayout | undefined, stableKey: string): GraphNodePosition | null {
  const rawNodes = layout?.layout_json?.nodes;
  if (!rawNodes || typeof rawNodes !== "object") {
    return null;
  }
  const position = (rawNodes as Record<string, unknown>)[stableKey];
  if (!position || typeof position !== "object") {
    return null;
  }
  const candidate = position as Record<string, unknown>;
  if (typeof candidate.x !== "number" || typeof candidate.y !== "number") {
    return null;
  }
  return { x: candidate.x, y: candidate.y };
}

export function layoutNodes(
  nodes: KnowledgeGraphNode[],
  layout?: KnowledgeGraphLayout,
  localPositions: Record<string, GraphNodePosition> = {},
): PositionedGraphNode[] {
  if (!nodes.length) {
    return [];
  }
  if (nodes.length === 1) {
    const node = nodes[0];
    const saved = localPositions[node.stable_key] ?? savedPosition(layout, node.stable_key);
    return [{ ...node, x: saved?.x ?? 360, y: saved?.y ?? 260 }];
  }
  const radiusX = 360;
  const radiusY = 220;
  const centerX = 460;
  const centerY = 310;
  return nodes.map((node, index) => {
    const saved = localPositions[node.stable_key] ?? savedPosition(layout, node.stable_key);
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

export function autoLayoutNodes(nodes: KnowledgeGraphNode[]) {
  const typeOrder = ["service", "offering", "concept", "knowledge_item", "known_error", "workaround", "glossary_term"];
  const byType = new Map<string, KnowledgeGraphNode[]>();
  nodes.forEach((node) => {
    const group = byType.get(node.node_type) ?? [];
    group.push(node);
    byType.set(node.node_type, group);
  });
  const positions: Record<string, GraphNodePosition> = {};
  typeOrder.forEach((nodeType, columnIndex) => {
    const group = byType.get(nodeType) ?? [];
    group.forEach((node, rowIndex) => {
      positions[node.stable_key] = {
        x: 120 + columnIndex * 260,
        y: 120 + rowIndex * 150,
      };
    });
  });
  nodes
    .filter((node) => !positions[node.stable_key])
    .forEach((node, index) => {
      positions[node.stable_key] = { x: 120 + (index % 4) * 260, y: 120 + Math.floor(index / 4) * 150 };
    });
  return positions;
}

export function layoutPositions(nodes: PositionedGraphNode[]) {
  return Object.fromEntries(nodes.map((node) => [node.stable_key, { x: Math.round(node.x), y: Math.round(node.y) }]));
}

export function mergePositionSnapshot(
  visibleNodes: PositionedGraphNode[],
  localPositions: Record<string, GraphNodePosition>,
): Record<string, GraphNodePosition> {
  return {
    ...layoutPositions(visibleNodes),
    ...localPositions,
  };
}

export function layoutPayload(nodes: PositionedGraphNode[]) {
  return {
    nodes: layoutPositions(nodes),
    viewport: { zoom: 1, pan_x: 0, pan_y: 0 },
  };
}
