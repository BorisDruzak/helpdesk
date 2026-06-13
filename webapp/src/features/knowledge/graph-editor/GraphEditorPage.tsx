import { AiProposalPanel } from "./AiProposalPanel";
import { EdgeInspector } from "./EdgeInspector";
import { GraphCanvas } from "./GraphCanvas";
import { GraphExplorer } from "./GraphExplorer";
import { GraphPalette } from "./GraphPalette";
import { GraphValidationPanel } from "./GraphValidationPanel";
import { GraphWorkbenchLayout } from "./GraphWorkbenchLayout";
import { NodeInspector } from "./NodeInspector";
import { RelationPalette } from "./RelationPalette";
import { useGraphEditorController } from "./useGraphEditorController";

export function GraphEditorPage() {
  const {
    actions,
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
  } = useGraphEditorController();

  const leftColumn = (
    <>
      <GraphExplorer
        isError={nodesQuery.isError}
        isLoading={nodesQuery.isLoading}
        nodes={allNodes}
        onSearchChange={editor.setSearch}
        onSelectNode={actions.selectNode}
        search={editor.search}
        selectedStableKey={editor.selectedStableKey}
      />
      <section className="surface-panel space-y-5 p-5">
        <GraphPalette
          activeNodeType={editor.nodeDraft.node_type}
          onChooseNodeType={(nodeType) => {
            editor.setNodeDraft({ ...editor.nodeDraft, node_type: nodeType });
            actions.switchMode("add_node");
          }}
        />
        <RelationPalette
          activeRelationType={editor.edgeDraft.relation_type}
          onChooseRelation={(relationType) => {
            editor.setEdgeDraft({ ...editor.edgeDraft, relation_type: relationType });
            actions.switchMode("connect");
          }}
        />
      </section>
      <GraphValidationPanel
        connectionMessages={editor.connectionMessages}
        duplicateCount={graphValidation.duplicateCount}
        orphanCount={graphValidation.orphanCount}
        validationMessages={graphValidation.messages}
      />
      <AiProposalPanel
        isLoading={proposalsQuery.isLoading}
        onReview={(proposalId, action) => mutations.reviewProposal.mutate({ proposalId, action })}
        proposals={proposalsQuery.data ?? []}
        reviewing={mutations.reviewProposal.isPending}
      />
    </>
  );

  const canvas = (
    <GraphCanvas
      activeRelationType={editor.edgeDraft.relation_type}
      canRedo={editor.layoutFuture.length > 0}
      canUndo={editor.layoutHistory.length > 0}
      edges={graphEdges}
      layoutDirty={editor.layoutDirty}
      mode={editor.mode}
      nodes={positionedNodes}
      nodesById={nodesById}
      onArchiveNode={actions.archiveNode}
      onAutoLayout={actions.autoLayout}
      onConnectNodes={(connection) => actions.createEdgeFromDraft({ ...editor.edgeDraft, ...connection })}
      onDuplicateNode={actions.duplicateNode}
      onFitView={() => editor.setStatusMessage("Холст подогнан под видимые узлы.")}
      onLayoutCommit={actions.commitCanvasPositions}
      onModeChange={actions.switchMode}
      onOpenArticle={actions.openArticle}
      onRedo={editor.redoLayout}
      onRequestAddNode={(position) => {
        editor.setQuickCreatePosition(position);
        editor.setMode("add_node");
      }}
      onSaveLayout={actions.saveLayout}
      onSelectEdge={actions.selectEdge}
      onSelectNode={actions.selectNode}
      onStartConnect={actions.startConnect}
      onUndo={editor.undoLayout}
      onValidate={actions.runValidation}
      savingLayout={mutations.saveLayout.isPending}
      selectedEdgeId={editor.selectedEdgeId}
      selectedStableKey={editor.selectedStableKey}
    />
  );

  const inspector =
    editor.mode === "connect" || selectedEdge ? (
      <EdgeInspector
        archiving={mutations.archiveEdge.isPending}
        connectionMessages={editor.connectionMessages}
        creating={mutations.createEdge.isPending}
        edgeDraft={editor.edgeDraft}
        edges={graphEdges}
        mode={editor.mode}
        nodes={graphNodes}
        nodesById={nodesById}
        onArchiveEdge={actions.archiveEdge}
        onCreateEdge={() => actions.createEdgeFromDraft(editor.edgeDraft)}
        onEdgeDraftChange={(draft) => {
          editor.setEdgeDraft(draft);
          editor.setConnectionMessages([]);
        }}
        onSaveEdge={actions.saveEdge}
        onSelectedEdgeDraftChange={setSelectedEdgeDraft}
        selectedEdge={selectedEdge}
        selectedEdgeDraft={selectedEdgeDraft}
        updating={mutations.updateEdge.isPending}
      />
    ) : (
      <NodeInspector
        archiving={mutations.archiveNode.isPending}
        creating={mutations.createNode.isPending}
        mode={editor.mode}
        nodeDraft={editor.nodeDraft}
        onArchiveNode={() => actions.archiveNode()}
        onCreateNode={actions.createNode}
        onDuplicateNode={() => actions.duplicateNode()}
        onNodeDraftChange={editor.setNodeDraft}
        onSaveNode={actions.saveNode}
        onSelectedDraftChange={setSelectedNodeDraft}
        onStartConnect={() => actions.startConnect()}
        quickCreatePosition={editor.quickCreatePosition}
        selectedDraft={selectedNodeDraft}
        selectedNode={selectedNode}
        updating={mutations.updateNode.isPending}
      />
    );

  return (
    <div className="space-y-3">
      <GraphWorkbenchLayout canvas={canvas} explorer={leftColumn} inspector={inspector} />
      {editor.statusMessage ? (
        <div className="rounded-lg border border-brand-100 bg-brand-50 px-4 py-3 text-sm font-semibold text-brand-800" role="status">
          {editor.statusMessage}
        </div>
      ) : null}
    </div>
  );
}
