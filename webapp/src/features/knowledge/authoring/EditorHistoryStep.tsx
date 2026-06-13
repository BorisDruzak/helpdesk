import { History, Sparkles } from "lucide-react";

import { Badge } from "../../../components/ui/badge";
import type { KnowledgeEditorHistory, KnowledgeVersionDiffCacheEntry } from "../api";

type EditorHistoryStepProps = {
  editorHistory?: KnowledgeEditorHistory;
  latestDiffCache: KnowledgeVersionDiffCacheEntry | null;
};

export function EditorHistoryStep({ editorHistory, latestDiffCache }: EditorHistoryStepProps) {
  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <p className="flex items-center gap-2 text-sm font-semibold text-slate-950">
          <History className="h-4 w-4" />
          История редактора
        </p>
        <div className="mt-3 space-y-2">
          {(editorHistory?.events ?? []).map((event) => (
            <div key={event.event_id} className="rounded-md border border-slate-200 px-3 py-2 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="neutral">{event.event_type}</Badge>
                {event.actor_id ? <span className="text-xs text-slate-500">{event.actor_id}</span> : null}
              </div>
              {event.summary ? <p className="mt-1 text-slate-700">{event.summary}</p> : null}
            </div>
          ))}
          {!(editorHistory?.events ?? []).length ? <p className="text-sm text-slate-500">История появится после создания версии, ревью или публикации.</p> : null}
        </div>
      </div>
      <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
        <p className="flex items-center gap-2 text-sm font-semibold text-slate-950">
          <Sparkles className="h-4 w-4" />
          AI и diff cache
        </p>
        {latestDiffCache ? (
          <p className="mt-3 text-sm text-slate-700">
            Кэш различий: +{latestDiffCache.added_lines} / -{latestDiffCache.removed_lines}
          </p>
        ) : (
          <p className="mt-3 text-sm text-slate-500">Кэш различий ещё не создан.</p>
        )}
        <p className="mt-3 text-xs leading-5 text-slate-500">AI-инструменты не вынесены в отдельную внешнюю карточку; состояние доступно внутри истории и inspector.</p>
      </div>
    </div>
  );
}
