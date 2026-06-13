import { useState } from "react";

import { emptyEdgeDraft, emptyNodeDraft, type EdgeDraft, type GraphEditorMode, type GraphNodePosition, type NodeDraft } from "./graphTypes";

export function useGraphEditorState() {
  const [mode, setMode] = useState<GraphEditorMode>("select");
  const [search, setSearch] = useState("");
  const [selectedStableKey, setSelectedStableKey] = useState("");
  const [selectedEdgeId, setSelectedEdgeId] = useState("");
  const [nodeDraft, setNodeDraft] = useState<NodeDraft>(() => emptyNodeDraft());
  const [edgeDraft, setEdgeDraft] = useState<EdgeDraft>(() => emptyEdgeDraft());
  const [quickCreatePosition, setQuickCreatePosition] = useState<GraphNodePosition | null>(null);
  const [localPositions, setLocalPositions] = useState<Record<string, GraphNodePosition>>({});
  const [layoutDirty, setLayoutDirty] = useState(false);
  const [layoutHistory, setLayoutHistory] = useState<Array<Record<string, GraphNodePosition>>>([]);
  const [layoutFuture, setLayoutFuture] = useState<Array<Record<string, GraphNodePosition>>>([]);
  const [statusMessage, setStatusMessage] = useState("");
  const [connectionMessages, setConnectionMessages] = useState<string[]>([]);

  function commitPositions(nextPositions: Record<string, GraphNodePosition>) {
    setLayoutHistory((current) => [...current.slice(-19), localPositions]);
    setLayoutFuture([]);
    setLocalPositions(nextPositions);
    setLayoutDirty(true);
  }

  function undoLayout() {
    setLayoutHistory((current) => {
      const previous = current[current.length - 1];
      if (!previous) {
        return current;
      }
      setLayoutFuture((future) => [localPositions, ...future]);
      setLocalPositions(previous);
      setLayoutDirty(true);
      return current.slice(0, -1);
    });
  }

  function redoLayout() {
    setLayoutFuture((current) => {
      const next = current[0];
      if (!next) {
        return current;
      }
      setLayoutHistory((history) => [...history, localPositions]);
      setLocalPositions(next);
      setLayoutDirty(true);
      return current.slice(1);
    });
  }

  return {
    commitPositions,
    connectionMessages,
    edgeDraft,
    layoutDirty,
    layoutFuture,
    layoutHistory,
    localPositions,
    mode,
    nodeDraft,
    quickCreatePosition,
    redoLayout,
    search,
    selectedEdgeId,
    selectedStableKey,
    setConnectionMessages,
    setEdgeDraft,
    setLayoutDirty,
    setLocalPositions,
    setMode,
    setNodeDraft,
    setQuickCreatePosition,
    setSearch,
    setSelectedEdgeId,
    setSelectedStableKey,
    setStatusMessage,
    statusMessage,
    undoLayout,
  };
}
