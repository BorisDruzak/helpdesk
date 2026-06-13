import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  createKnowledgeGraphEdge,
  createKnowledgeGraphNode,
  deleteKnowledgeGraphEdge,
  deleteKnowledgeGraphNode,
  reviewKnowledgeAiProposal,
  saveKnowledgeGraphLayout,
  updateKnowledgeGraphEdge,
  updateKnowledgeGraphNode,
} from "../api";

export function useGraphMutations(selectedStableKey: string) {
  const queryClient = useQueryClient();

  function invalidateGraph() {
    queryClient.invalidateQueries({ queryKey: ["knowledge-graph-nodes"] });
    queryClient.invalidateQueries({ queryKey: ["knowledge-graph-neighborhood"] });
    queryClient.invalidateQueries({ queryKey: ["knowledge-graph-layout", "default"] });
  }

  return {
    archiveEdge: useMutation({
      mutationFn: (edgeId: string) => deleteKnowledgeGraphEdge(edgeId),
      onSuccess: invalidateGraph,
    }),
    archiveNode: useMutation({
      mutationFn: (stableKey: string) => deleteKnowledgeGraphNode(stableKey),
      onSuccess: invalidateGraph,
    }),
    createEdge: useMutation({
      mutationFn: (payload: Record<string, unknown>) => createKnowledgeGraphEdge(payload),
      onSuccess: invalidateGraph,
    }),
    createNode: useMutation({
      mutationFn: (payload: Record<string, unknown>) => createKnowledgeGraphNode(payload),
      onSuccess: invalidateGraph,
    }),
    reviewProposal: useMutation({
      mutationFn: ({ proposalId, action }: { proposalId: string; action: "approve" | "reject" }) => reviewKnowledgeAiProposal(proposalId, { action }),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["knowledge-ai-proposals", "graph", "pending"] });
        invalidateGraph();
      },
    }),
    saveLayout: useMutation({
      mutationFn: (layoutJson: Record<string, unknown>) => saveKnowledgeGraphLayout("default", layoutJson),
      onSuccess: () => queryClient.invalidateQueries({ queryKey: ["knowledge-graph-layout", "default"] }),
    }),
    updateEdge: useMutation({
      mutationFn: ({ edgeId, payload }: { edgeId: string; payload: Record<string, unknown> }) => updateKnowledgeGraphEdge(edgeId, payload),
      onSuccess: invalidateGraph,
    }),
    updateNode: useMutation({
      mutationFn: ({ stableKey, payload }: { stableKey: string; payload: Record<string, unknown> }) => updateKnowledgeGraphNode(stableKey, payload),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["knowledge-graph-nodes"] });
        queryClient.invalidateQueries({ queryKey: ["knowledge-graph-neighborhood", selectedStableKey] });
      },
    }),
  };
}
