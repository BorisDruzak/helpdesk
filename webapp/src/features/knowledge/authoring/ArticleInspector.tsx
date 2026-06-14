import { useState } from "react";
import { GitCompare, History, RotateCcw, Save, X } from "lucide-react";

import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../../components/ui/card";
import type { KnowledgeEditorHistory, KnowledgeItem, KnowledgeItemVersion, KnowledgeVersionDiffCacheEntry } from "../api";
import { statusLabel, type ValidationCheck, visibilityLabel } from "./knowledge-studio-model";

type ArticleInspectorProps = {
  checklistComplete: boolean;
  currentDiff: { added: string[]; removed: string[] };
  draftVisibility: string;
  editorHistory?: KnowledgeEditorHistory;
  isPublishing: boolean;
  latestDiffCache: KnowledgeVersionDiffCacheEntry | null;
  onPublish: () => void;
  onRollback: () => void;
  onSelectVersion: (versionId: string) => void;
  saveMessage: string;
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
  latestDiffCache,
  onPublish,
  onRollback,
  onSelectVersion,
  saveMessage,
  selectedItem,
  selectedVersion,
  selectedVersionId,
  validationChecks,
  versions,
}: ArticleInspectorProps) {
  const [historyOpen, setHistoryOpen] = useState(false);
  const [rollbackConfirmed, setRollbackConfirmed] = useState(false);
  const currentVersion = versions.find((version) => version.version_id === selectedItem?.current_version_id) ?? selectedVersion;
  const selectedHistoryVersion = versions.find((version) => version.version_id === selectedVersionId) ?? selectedVersion;

  function selectHistoryVersion(versionId: string) {
    setRollbackConfirmed(false);
    onSelectVersion(versionId);
  }

  return (
    <>
      <Card className="sticky top-4 min-h-[calc(100vh-14rem)]">
        <CardHeader className="pb-3">
          <CardTitle>Сохранение статьи</CardTitle>
          <CardDescription>Проверки и основное действие всегда рядом. Версии создаются и публикуются автоматически.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <Badge tone={selectedItem?.status === "published" ? "success" : selectedItem?.status === "archived" ? "danger" : "warning"}>
              {statusLabel(selectedItem?.status)}
            </Badge>
            <Badge tone="neutral">{visibilityLabel(draftVisibility || selectedItem?.visibility)}</Badge>
            {currentVersion ? <Badge tone="brand">Текущая версия: v{currentVersion.version_number}</Badge> : null}
          </div>

          <Button
            className="w-full"
            disabled={!selectedItem || !checklistComplete || isPublishing}
            leadingIcon={<Save className="h-4 w-4" />}
            onClick={onPublish}
            size="lg"
          >
            Сохранить статью
          </Button>
          <p className="text-xs leading-5 text-slate-500">
            При сохранении Studio создаёт новую версию, публикует её как текущую и обновляет список статей.
          </p>
          {saveMessage ? <p className="rounded-md bg-emerald-50 px-3 py-2 text-sm font-medium text-emerald-800">{saveMessage}</p> : null}

          <fieldset aria-label="Готовность к сохранению" className="space-y-2">
            <legend className="text-sm font-semibold text-slate-950">Готовность к сохранению</legend>
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

          <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
            <p className="flex items-center gap-2 font-semibold text-slate-900">
              <GitCompare className="h-4 w-4" />
              Изменения
            </p>
            <p className="mt-2 text-xs text-slate-600">
              Добавлено: {currentDiff.added.length} · Удалено: {currentDiff.removed.length}
            </p>
            {latestDiffCache ? (
              <p className="mt-1 text-xs text-slate-500">
                Кэш различий: +{latestDiffCache.added_lines} / -{latestDiffCache.removed_lines}
              </p>
            ) : null}
          </div>

          <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
            <p className="flex items-center gap-2 font-semibold text-slate-900">
              <History className="h-4 w-4" />
              Последние события
            </p>
            <div className="mt-2 space-y-1 text-xs text-slate-600">
              {(editorHistory?.events ?? []).slice(0, 3).map((event) => (
                <p key={event.event_id}>
                  {event.event_type}
                  {event.summary ? ` · ${event.summary}` : ""}
                </p>
              ))}
              {!(editorHistory?.events ?? []).length ? <p>История появится после сохранения статьи.</p> : null}
            </div>
          </div>

          <Button className="w-full" onClick={() => setHistoryOpen(true)} variant="outline" leadingIcon={<History className="h-4 w-4" />}>
            История версий
          </Button>
        </CardContent>
      </Card>

      {historyOpen ? (
        <div className="fixed inset-0 z-50 flex justify-end bg-slate-950/30" role="presentation">
          <div aria-label="История версий" aria-modal="true" className="h-full w-full max-w-xl overflow-y-auto border-l border-slate-200 bg-white p-6 shadow-xl" role="dialog">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-xl font-semibold text-slate-950">История версий</h2>
                <p className="mt-1 text-sm text-slate-500">Старые версии можно просмотреть и восстановить только после подтверждения.</p>
              </div>
              <Button aria-label="Закрыть историю версий" onClick={() => setHistoryOpen(false)} size="icon" variant="ghost">
                <X className="h-5 w-5" />
              </Button>
            </div>

            <div className="mt-6 space-y-3">
              {versions.map((version) => {
                const active = version.version_id === selectedHistoryVersion?.version_id;
                const current = version.version_id === selectedItem?.current_version_id;
                return (
                  <button
                    className={`w-full rounded-lg border px-3 py-3 text-left text-sm transition-colors ${
                      active ? "border-brand-300 bg-brand-50" : "border-slate-200 bg-white hover:border-slate-300"
                    }`}
                    key={version.version_id}
                    onClick={() => selectHistoryVersion(version.version_id)}
                    type="button"
                  >
                    <span className="block font-semibold text-slate-950">
                      v{version.version_number}: {version.title}
                    </span>
                    <span className="mt-1 block text-xs text-slate-500">
                      {current ? "Текущая версия" : "Предыдущая версия"}
                      {version.published_at ? ` · опубликована ${version.published_at}` : ""}
                    </span>
                    {active ? <span className="mt-2 block line-clamp-3 text-xs leading-5 text-slate-600">{version.body}</span> : null}
                  </button>
                );
              })}
              {!versions.length ? <p className="rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-500">Версий пока нет.</p> : null}
            </div>

            <div className="mt-6 rounded-lg border border-amber-200 bg-amber-50 p-3">
              <label className="flex items-start gap-2 text-sm font-medium text-amber-900">
                <input checked={rollbackConfirmed} className="mt-1" onChange={(event) => setRollbackConfirmed(event.target.checked)} type="checkbox" />
                Подтвердить восстановление выбранной версии
              </label>
              <Button
                className="mt-3 w-full"
                disabled={!selectedItem || !selectedVersionId || !rollbackConfirmed || isPublishing}
                onClick={onRollback}
                variant="outline"
                leadingIcon={<RotateCcw className="h-4 w-4" />}
              >
                Восстановить выбранную версию
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
