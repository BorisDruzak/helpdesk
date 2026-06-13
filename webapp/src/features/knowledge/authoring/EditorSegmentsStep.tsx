import { ArticleSegmentationPanel } from "../article-segmentation-panel";
import type { KnowledgeItem, KnowledgeItemVersion } from "../api";
import type { EditorSelectionSnapshot } from "./knowledge-studio-model";

type EditorSegmentsStepProps = {
  draftBody: string;
  editorSelection: EditorSelectionSnapshot;
  selectedItem: KnowledgeItem | null;
  selectedVersion: KnowledgeItemVersion | null;
};

export function EditorSegmentsStep({ draftBody, editorSelection, selectedItem, selectedVersion }: EditorSegmentsStepProps) {
  return (
    <ArticleSegmentationPanel
      canManage={Boolean(selectedItem)}
      editorSelection={editorSelection}
      embedded
      item={selectedItem}
      sourceBody={draftBody}
      version={selectedVersion}
    />
  );
}
