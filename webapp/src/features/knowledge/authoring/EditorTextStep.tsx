import { Badge } from "../../../components/ui/badge";
import type { KnowledgeItem, KnowledgeTemplate } from "../api";
import { KnowledgeTipTapEditor } from "../knowledge-tiptap-editor";
import { fieldClass, markdownPreview, type EditorDraft, type EditorSelectionSnapshot } from "./knowledge-studio-model";

type EditorTextStepProps = {
  draft: EditorDraft;
  editorSelection: EditorSelectionSnapshot;
  onDraftChange: (patch: Partial<EditorDraft>) => void;
  onInsertBlock: (block: string) => void;
  onInsertTemplate: (sections: string[]) => void;
  onSelectionChange: (selection: EditorSelectionSnapshot) => void;
  selectedItem: KnowledgeItem | null;
  templates: KnowledgeTemplate[];
};

export function EditorTextStep({
  draft,
  editorSelection,
  onDraftChange,
  onInsertBlock,
  onInsertTemplate,
  onSelectionChange,
  selectedItem,
  templates,
}: EditorTextStepProps) {
  return (
    <div className="space-y-4">
      <div className="grid gap-3 lg:grid-cols-2">
        <label className="text-sm font-medium lg:col-span-2">
          Заголовок
          <input className={fieldClass} value={draft.title} onChange={(event) => onDraftChange({ title: event.target.value })} />
        </label>
        <label className="text-sm font-medium">
          Краткое описание версии
          <input className={fieldClass} value={draft.summary} onChange={(event) => onDraftChange({ summary: event.target.value })} />
        </label>
        <label className="text-sm font-medium">
          Описание изменения
          <input className={fieldClass} value={draft.change_summary} onChange={(event) => onDraftChange({ change_summary: event.target.value })} />
        </label>
      </div>

      <div className="grid gap-4 2xl:grid-cols-[minmax(0,1.05fr)_minmax(320px,0.95fr)]">
        <div>
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-semibold text-slate-950">Текст статьи</p>
            {editorSelection.text ? (
              <Badge tone="info">Выделено {editorSelection.text.length} симв.</Badge>
            ) : (
              <Badge tone="neutral">Выделение доступно для разметки</Badge>
            )}
          </div>
          <KnowledgeTipTapEditor
            isDisabled={!selectedItem}
            onChange={(value) => onDraftChange({ body: value })}
            onInsertBlock={onInsertBlock}
            onInsertTemplate={onInsertTemplate}
            onSelectionChange={onSelectionChange}
            templates={templates}
            value={draft.body}
          />
        </div>
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <p className="text-sm font-semibold text-slate-950">Живой предпросмотр</p>
          <div className="mt-3 space-y-3">{markdownPreview(draft.body)}</div>
        </div>
      </div>
    </div>
  );
}
