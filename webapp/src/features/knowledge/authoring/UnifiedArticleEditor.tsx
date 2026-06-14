import { useState } from "react";

import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../../components/ui/card";
import type { KnowledgeEditorHistory, KnowledgeItem, KnowledgeItemVersion, KnowledgeSpace, KnowledgeTemplate, KnowledgeVersionDiffCacheEntry } from "../api";
import { EditorHistoryStep } from "./EditorHistoryStep";
import { EditorMetadataStep } from "./EditorMetadataStep";
import { EditorSegmentsStep } from "./EditorSegmentsStep";
import { EditorTextStep } from "./EditorTextStep";
import { EditorValidationStep } from "./EditorValidationStep";
import {
  editorQuickViews,
  editorSteps,
  itemTypeLabel,
  markdownPreview,
  statusLabel,
  type EditorDraft,
  type EditorSelectionSnapshot,
  type ValidationCheck,
  visibilityLabel,
} from "./knowledge-studio-model";

type UnifiedArticleEditorProps = {
  activeSegmentsCount: number;
  currentDiff: { added: string[]; removed: string[] };
  draft: EditorDraft;
  editorHistory?: KnowledgeEditorHistory;
  editorSelection: EditorSelectionSnapshot;
  latestDiffCache: KnowledgeVersionDiffCacheEntry | null;
  onDraftChange: (patch: Partial<EditorDraft>) => void;
  onInsertBlock: (block: string) => void;
  onInsertTemplate: (sections: string[]) => void;
  onSelectionChange: (selection: EditorSelectionSnapshot) => void;
  selectedItem: KnowledgeItem | null;
  selectedVersion: KnowledgeItemVersion | null;
  spaces: KnowledgeSpace[];
  templates: KnowledgeTemplate[];
  validationChecks: ValidationCheck[];
};

export function UnifiedArticleEditor({
  activeSegmentsCount,
  currentDiff,
  draft,
  editorHistory,
  editorSelection,
  latestDiffCache,
  onDraftChange,
  onInsertBlock,
  onInsertTemplate,
  onSelectionChange,
  selectedItem,
  selectedVersion,
  spaces,
  templates,
  validationChecks,
}: UnifiedArticleEditorProps) {
  const [activeView, setActiveView] = useEditorView();
  const [advancedToolsOpen, setAdvancedToolsOpen] = useState(false);

  const selectedStatus = statusLabel(selectedItem?.status);
  const currentSpace = spaces.find((space) => space.code === draft.space_code || space.space_id === selectedItem?.space_id);

  return (
    <Card className="min-h-[calc(100vh-14rem)] overflow-hidden">
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <CardTitle>Редактор статьи</CardTitle>
            <CardDescription>Одна рабочая область для текста, основных настроек, предпросмотра и проверки перед сохранением.</CardDescription>
            <div className="mt-3 flex flex-wrap gap-2">
              <Badge tone="warning">{selectedStatus}</Badge>
              <Badge tone="neutral">{visibilityLabel(draft.visibility)}</Badge>
              <Badge tone="brand">{itemTypeLabel(draft.item_type)}</Badge>
              {currentSpace ? <Badge tone="info">{currentSpace.title}</Badge> : null}
            </div>
          </div>
          <div className="max-w-xs text-right text-xs leading-5 text-slate-500">
            Версии, фрагменты поиска и публикация создаются автоматически при сохранении статьи.
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        <div className="grid gap-2 lg:grid-cols-3" aria-label="Шаги редактора статьи">
          {editorSteps.map((step, index) => {
            const active = activeView === step.value || (activeView === "preview" && step.value === "text");
            return (
              <button
                className={`rounded-pill border px-4 py-2 text-left text-sm font-semibold transition-colors ${
                  active ? "border-brand-600 bg-brand-600 text-white" : "border-slate-200 bg-slate-50 text-slate-600 hover:border-brand-200"
                }`}
                key={step.value}
                onClick={() => setActiveView(step.value)}
                type="button"
              >
                {index + 1}. {step.label}
              </button>
            );
          })}
        </div>

        <p className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
          Поисковые фрагменты создаются автоматически по заголовкам и тексту статьи.
        </p>

        <div className="flex flex-wrap gap-2" aria-label="Быстрые вкладки редактора">
          {editorQuickViews.map((view) => (
            <button
              className={`rounded-pill border px-3 py-1.5 text-sm font-semibold transition-colors ${
                activeView === view.value ? "border-brand-200 bg-brand-50 text-brand-800" : "border-slate-200 bg-white text-slate-600 hover:border-slate-300"
              }`}
              key={view.value}
              onClick={() => setActiveView(view.value)}
              type="button"
            >
              {view.label}
            </button>
          ))}
        </div>

        <section className="rounded-lg border border-slate-200 bg-slate-50 p-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-slate-950">Расширенные инструменты</p>
              <p className="mt-1 text-xs leading-5 text-slate-500">Для длинных документов и точной настройки поиска.</p>
            </div>
            <button
              className="rounded-pill border border-slate-200 bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 hover:border-brand-200 hover:bg-brand-50 hover:text-brand-800"
              onClick={() => setAdvancedToolsOpen((current) => !current)}
              type="button"
            >
              {advancedToolsOpen ? "Скрыть advanced" : "Показать advanced"}
            </button>
          </div>
          {advancedToolsOpen ? (
            <div className="mt-3 flex flex-wrap gap-2">
              <Button onClick={() => setActiveView("segments")} size="sm" variant={activeView === "segments" ? "primary" : "outline"}>
                Поисковые фрагменты
              </Button>
              <span className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600">Авторазметка</span>
              <span className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600">Ручная разметка</span>
              <span className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600">Сегменты версии</span>
            </div>
          ) : null}
        </section>

        {activeView === "text" ? (
          <EditorTextStep
            draft={draft}
            editorSelection={editorSelection}
            onDraftChange={onDraftChange}
            onInsertBlock={onInsertBlock}
            onInsertTemplate={onInsertTemplate}
            onSelectionChange={onSelectionChange}
            selectedItem={selectedItem}
            templates={templates}
          />
        ) : null}

        {activeView === "preview" ? (
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <p className="text-xs font-semibold uppercase text-slate-500">Живой предпросмотр</p>
            <div className="mt-3 space-y-3">{markdownPreview(draft.body)}</div>
          </div>
        ) : null}

        {activeView === "metadata" ? (
          <EditorMetadataStep draft={draft} onDraftChange={onDraftChange} selectedItem={selectedItem} spaces={spaces} />
        ) : null}

        {activeView === "segments" ? (
          <EditorSegmentsStep
            draftBody={draft.body}
            editorSelection={editorSelection}
            selectedItem={selectedItem}
            selectedVersion={selectedVersion}
          />
        ) : null}

        {activeView === "validation" ? (
          <EditorValidationStep activeSegmentsCount={activeSegmentsCount} currentDiff={currentDiff} validationChecks={validationChecks} />
        ) : null}

        {activeView === "history" ? (
          <EditorHistoryStep editorHistory={editorHistory} latestDiffCache={latestDiffCache} />
        ) : null}
      </CardContent>
    </Card>
  );
}

function useEditorView(): [string, (value: string) => void] {
  return useState("text");
}
