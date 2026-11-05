import { Clock3 } from "lucide-react";
import { ChatAttachment } from "../../components/chat-attachment";
import { formatRussianDateTime } from "../../components/ui-page";
import { requesterSafeAttachmentName } from "../../features/requester/labels";
import type { PublicTicketEvent, PublicTicketMessage } from "../../features/requester/types";

const supportRoles = new Set(["support", "admin", "staff", "operator"]);

export function RequesterConversation({ messages, events }: { messages: PublicTicketMessage[]; events: PublicTicketEvent[] }) {
  const rows = [
    ...messages.map((message, index) => ({ key: `message:${message.event_id || message.message_id || index}`, at: message.created_at || message.ts, message, event: null as PublicTicketEvent | null })),
    ...events.filter(event => (event.type || event.event_type) !== "chat_message" && event.requester_timeline_text
      && !["user_message", "support_message"].includes(event.requester_timeline_kind || ""))
      .map((event, index) => ({ key: `event:${event.event_id || event.id || index}`, at: event.created_at || event.ts, message: null as PublicTicketMessage | null, event })),
  ].sort((a, b) => (Date.parse(a.at || "") || 0) - (Date.parse(b.at || "") || 0));
  return <section aria-label="Переписка" className="min-w-0">
    <h2 className="mb-3 text-sm font-semibold text-slate-700">Переписка</h2>
    {!rows.length ? <p className="rounded-panel border border-dashed border-slate-200 bg-white p-5 text-sm text-slate-600">Здесь появятся ответы поддержки и изменения по обращению.</p> : null}
    <ol className="space-y-3" role="log" aria-label="Сообщения и события обращения" aria-live="polite" aria-relevant="additions">
      {rows.map(row => {
        const message = row.message;
        const system = !message || message.metadata?.message_kind === "ticket_access_notice" || ["system", "service"].includes(message.from_role || message.sender_role || "");
        const support = message && supportRoles.has(message.from_role || message.sender_role || "");
        if (system) return <li key={row.key} className="flex items-start justify-center gap-2 px-2 py-1 text-xs text-slate-500"><Clock3 className="mt-0.5 h-3.5 w-3.5 shrink-0" /><span className="break-words">{message?.text || row.event?.requester_timeline_text}{row.at ? <time className="ml-2 whitespace-nowrap text-slate-400" dateTime={row.at}>{formatRussianDateTime(row.at, { emptyText: "" })}</time> : null}</span></li>;
        if (!message) return null;
        return <li key={row.key} className={`flex ${support ? "justify-start" : "justify-end"}`}><article className={`min-w-0 max-w-[92%] rounded-panel border p-3 sm:max-w-[85%] ${support ? "border-slate-200 bg-white" : "border-brand-200 bg-brand-50"}`}>
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs"><span className="font-semibold text-slate-700">{support ? "Поддержка" : "Вы"}</span>{row.at ? <time className="text-slate-500" dateTime={row.at}>{formatRussianDateTime(row.at, { emptyText: "" })}</time> : null}</div>
          {message.text ? <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-relaxed text-slate-800 [overflow-wrap:anywhere]">{message.text}</p> : null}
          {message.attachments?.length ? <ul className="mt-2 flex max-w-full flex-wrap gap-2">{message.attachments.map(attachment => <li className="min-w-0 max-w-full" key={attachment.artifact_id}><ChatAttachment attachment={{...attachment, name: requesterSafeAttachmentName(attachment.name), url: attachment.url || `/api/artifacts/${encodeURIComponent(attachment.artifact_id)}/download`}} /></li>)}</ul> : null}
        </article></li>;
      })}
    </ol>
  </section>;
}
