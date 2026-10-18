import { Lock, MessageSquare, Paperclip } from "lucide-react";
import { partitionSupportTimeline } from "../../../features/queues/support-conversation";
import type { SupportWorkspaceTimelineItem } from "../../../features/queues/support-workspace-model";

export function SupportConversationTimeline({ items, onOpenContext }: {
  items: readonly SupportWorkspaceTimelineItem[];
  onOpenContext?: () => void;
}) {
  const { conversation, context } = partitionSupportTimeline(items);
  return <section aria-label="Переписка" className="min-w-0 space-y-4">
    {context.length ? <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3 text-xs text-slate-400">
      <span>Системные события и диагностика: {context.length}</span>
      {onOpenContext ? <button type="button" className="font-semibold text-blue-200 underline" onClick={onOpenContext}>Открыть контекст</button> : null}
    </div> : null}
    {!conversation.length ? <p className="rounded-xl border border-dashed border-white/10 px-5 py-8 text-center text-sm text-slate-400">Сообщений пользователя и поддержки пока нет.</p> : null}
    {conversation.map(item => <article aria-label={item.kind === "internal" ? "Внутренний комментарий" : "Сообщение"} className="grid min-w-0 grid-cols-[36px_minmax(0,1fr)] gap-3" key={item.id}>
      <div className={`flex h-9 w-9 items-center justify-center rounded-full border ${item.kind === "internal" ? "border-amber-400/50 bg-amber-500/10 text-amber-100" : "border-blue-400/40 bg-blue-500/10 text-blue-100"}`}>
        {item.kind === "internal" ? <Lock className="h-4 w-4" /> : <MessageSquare className="h-4 w-4" />}
      </div>
      <div className="min-w-0 rounded-xl border border-white/10 bg-[#0d1828] px-4 py-3">
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span className="font-semibold text-white">{item.actor}</span>
          <span className="text-slate-400">{item.kind === "internal" ? "Внутренняя заметка" : item.title}</span>
          <time className="ml-auto text-xs text-slate-500">{item.timestampLabel}</time>
        </div>
        <p className="mt-2 break-words whitespace-pre-line text-sm leading-6 text-slate-200">{item.body}</p>
        {item.attachments.length ? <div className="mt-3 flex items-center gap-2 text-xs text-slate-400"><Paperclip className="h-4 w-4" />{item.attachments.length} влож.</div> : null}
      </div>
    </article>)}
  </section>;
}
