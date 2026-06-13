import { Archive, CheckCircle2, GitCompare, History, MessageSquare, RotateCcw, Send, Sparkles, Undo2 } from "lucide-react";

import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../../components/ui/card";
import type { KnowledgeEditorHistory, KnowledgeItem, KnowledgeItemVersion, KnowledgeVersionDiffCacheEntry } from "../api";
import { fieldClass, statusLabel, type ValidationCheck, visibilityLabel } from "./knowledge-studio-model";

type ArticleInspectorProps = {
  checklistComplete: boolean;
  currentDiff: { added: string[]; removed: string[] };
  draftVisibility: string;
  editorHistory?: KnowledgeEditorHistory;
  isPublishing: boolean;
  isReviewing: boolean;
  latestDiffCache: KnowledgeVersionDiffCacheEntry | null;
  onPublish: () => void;
  onPublishNoteChange: (value: string) => void;
  onReviewAction: (action: string) => void;
  onReviewNoteChange: (value: string) => void;
  onRollback: () => void;
  onSelectVersion: (versionId: string) => void;
  publishNote: string;
  reviewNote: string;
  selectedItem: KnowledgeItem | null;
  selectedVersion: KnowledgeItemVersion | null;
  selectedVersionId: string;
  validationChecks: ValidationCheck[];
  versions: KnowledgeItemVersion[];
};

export function ArticleInspector({
  checklistComplete,
  currentDiff,
  draftVisibility,
  editorHistory,
  isPublishing,
  isReviewing,
  latestDiffCache,
  onPublish,
  onPublishNoteChange,
  onReviewAction,
  onReviewNoteChange,
  onRollback,
  onSelectVersion,
  publishNote,
  reviewNote,
  selectedItem,
  selectedVersion,
  selectedVersionId,
  validationChecks,
  versions,
}: ArticleInspectorProps) {
  return (
    <Card className="sticky top-4 min-h-[calc(100vh-14rem)]">
      <CardHeader className="pb-3">
        <CardTitle>Инспектор и публикация</CardTitle>
        <CardDescription>Статус, проверки, версии и действия всегда рядом.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap gap-2">
          <Badge tone={selectedItem?.status === "published" ? "success" : selectedItem?.status === "archived" ? "danger" : "warning"}>
            {statusLabel(selectedItem?.status)}
          </Badge>
          <Badge tone="neutral">{visibilityLabel(draftVisibility || selectedItem?.visibility)}</Badge>
        </div>

        <label className="text-sm font-medium">
          Версия для сравнения
          <select className={fieldClass} value={selectedVersionId} onChange={(event) => onSelectVersion(event.target.value)}>
            {versions.map((version) => (
              <option key={version.version_id} value={version.version_id}>
                v{version.version_number}: {version.title}
              </option>
            ))}
            {!versions.length ? <option value="">Нет версий</option> : null}
          </select>
        </label>

        <fieldset aria-label="Проверка публикации" className="space-y-2">
          <legend className="text-sm font-semibold text-slate-950">Проверка публикации</legend>
          {validationChecks.map((check) => (
            <label className="flex items-start gap-2 text-sm text-slate-700" key={check.key}>
              <input checked={check.ok} className="mt-1" readOnly type="checkbox" />
              <span>
                <span className={check.ok ? "text-slate-800" : "text-slate-500"}>{check.label}</span>
                {check.detail ? <span className="block text-xs text-slate-500">{check.detail}</span> : null}
              </span>
            </label>
          ))}
        </fieldset>

        <label className="text-sm font-medium">
          Комментарий к публикации
          <input className={fieldClass} value={publishNote} onChange={(event) => onPublishNoteChange(event.target.value)} />
        </label>
        <label className="text-sm font-medium">
          Комментарий ревью
          <input className={fieldClass} value={reviewNote} onChange={(event) => onReviewNoteChange(event.target.value)} />
        </label>

        <div className="space-y-2 rounded-lg border border-slate-200 p-3">
          <div>
            <p className="text-sm font-semibold text-slate-950">Жизненный цикл версии</p>
            <p className="mt-1 text-xs leading-5 text-slate-500">
              Эти действия меняют статус, публикацию или выбранную версию. Текст редактора фиксируется кнопкой «Создать версию».
            </p>
          </div>
          <Button
            className="w-full"
            disabled={!selectedItem || isReviewing}
            onClick={() => onReviewAction("submit_review")}
            variant="outline"
            leadingIcon={<Send className="h-4 w-4" />}
          >
            Отправить на ревью
          </Button>
          <Button className="w-full" disabled={!selectedItem || !checklistComplete || isPublishing} onClick={onPublish}>
            Опубликовать версию
          </Button>
          <Button
            className="w-full"
            disabled={!selectedItem || !selectedVersionId || isPublishing}
            onClick={onRollback}
            variant="outline"
            leadingIcon={<RotateCcw className="h-4 w-4" />}
          >
            Откатить к выбранной версии
          </Button>
          <Button
            className="w-full border-rose-200 bg-rose-50 text-rose-700 hover:border-rose-300 hover:bg-rose-100"
            disabled={!selectedItem || isReviewing}
            onClick={() => onReviewAction("archive")}
            variant="outline"
            leadingIcon={<Archive className="h-4 w-4" />}
          >
            Архивировать / заменить
          </Button>
        </div>

        <div className="space-y-2 rounded-lg border border-slate-200 p-3">
          <div>
            <p className="text-sm font-semibold text-slate-950">Ревью</p>
            <p className="mt-1 text-xs leading-5 text-slate-500">
              Комментарий, одобрение и запрос правок отправляются в review-action и не сохраняют текст статьи.
            </p>
          </div>
          <Button className="w-full" disabled={!selectedItem || isReviewing} onClick={() => onReviewAction("comment")} size="sm" variant="outline" leadingIcon={<MessageSquare className="h-4 w-4" />}>
            Добавить комментарий
          </Button>
          <Button className="w-full" disabled={!selectedItem || isReviewing} onClick={() => onReviewAction("approve")} size="sm" variant="outline" leadingIcon={<CheckCircle2 className="h-4 w-4" />}>
            Одобрить
          </Button>
          <Button
            className="w-full"
            disabled={!selectedItem || isReviewing}
            onClick={() => onReviewAction("request_changes")}
            size="sm"
            variant="outline"
            leadingIcon={<Undo2 className="h-4 w-4" />}
          >
            Запросить правки
          </Button>
        </div>

        <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
          <p className="flex items-center gap-2 font-semibold text-slate-900">
            <GitCompare className="h-4 w-4" />
            Diff
          </p>
          <p className="mt-2 text-xs text-slate-600">
            Добавлено: {currentDiff.added.length} · Удалено: {currentDiff.removed.length}
          </p>
          {latestDiffCache ? (
            <p className="mt-1 text-xs text-slate-500">
              Кэш: +{latestDiffCache.added_lines} / -{latestDiffCache.removed_lines}
            </p>
          ) : null}
        </div>

        <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
          <p className="flex items-center gap-2 font-semibold text-slate-900">
            <History className="h-4 w-4" />
            История
          </p>
          <div className="mt-2 space-y-1 text-xs text-slate-600">
            {(editorHistory?.events ?? []).slice(0, 3).map((event) => (
              <p key={event.event_id}>
                {event.event_type}
                {event.summary ? ` · ${event.summary}` : ""}
              </p>
            ))}
            {!(editorHistory?.events ?? []).length ? <p>История появится после сохранения версии.</p> : null}
          </div>
        </div>

        <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
          <p className="flex items-center gap-2 font-semibold text-slate-900">
            <Sparkles className="h-4 w-4" />
            AI
          </p>
          <p className="mt-2 text-xs text-slate-600">Разметка видима в редакторе; AI-предложения включаются политикой.</p>
          {selectedVersion ? <p className="mt-1 text-xs text-slate-500">Текущая версия: v{selectedVersion.version_number}</p> : null}
        </div>
      </CardContent>
    </Card>
  );
}
