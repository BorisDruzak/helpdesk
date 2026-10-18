import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Info } from "lucide-react";
import { humanRequesterTicketCode } from "../../features/requester/queries";
import { requesterErrorMessage } from "../../features/requester/labels";
import { RequesterConsentList } from "../../features/requester/consent-card";
import { InlineAlert } from "../../features/requester/ui/form-controls";
import { TicketDetailHeader, TicketReplyComposer, TicketResolutionPanel } from "./tickets-panels";
import { MessagesPanel, TimelinePanel, partitionRequesterTimeline } from "./tickets-workflow";
import { useRequesterTicketChat } from "./use-ticket-chat";

export function RequesterTicketChatPage() {
  const { ticketId } = useParams();
  return <RequesterTicketChat key={ticketId} ticketId={ticketId} />;
}

function RequesterTicketChat({ ticketId }: { ticketId: string | undefined }) {
  const chat = useRequesterTicketChat(ticketId);
  const [showDetails, setShowDetails] = useState(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const followMessages = useRef(true);
  const { selectedTicket: ticket, detailQuery } = chat;
  const { messages, events } = useMemo(() => partitionRequesterTimeline(detailQuery.data?.messages ?? [], detailQuery.data?.events ?? []), [detailQuery.data?.messages, detailQuery.data?.events]);
  useEffect(() => {
    const scroller = scrollRef.current;
    if (scroller && followMessages.current && !showDetails && !chat.canClose && !chat.pendingConsents.length) scroller.scrollTop = scroller.scrollHeight;
  }, [messages, showDetails, chat.canClose, chat.pendingConsents.length]);
  return (
    <section aria-label="Чат обращения" className="flex min-h-0 flex-1 flex-col bg-slate-50">
      <header className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-white px-4 py-3">
        <div className="min-w-0 flex-1">
          <Link className="inline-flex items-center gap-1 text-sm font-semibold text-brand-700" to="/app/requester/tickets"><ArrowLeft className="h-4 w-4" />Все обращения</Link>
          {ticket ? <><p className="mt-2 text-xs font-semibold text-slate-500">{humanRequesterTicketCode(ticket)} · <span>{ticket.requester_status_label || ticket.status_label}</span></p><h1 className="truncate text-lg font-semibold text-slate-950">{ticket.title || "Без темы"}</h1></> : <h1 className="mt-2 text-lg font-semibold">Чат обращения</h1>}
        </div>
        {ticket ? <button aria-expanded={showDetails} aria-controls="requester-chat-content" className="inline-flex items-center gap-2 rounded-panel border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50" onClick={() => setShowDetails(value => !value)} type="button"><Info className="h-4 w-4" />{showDetails ? "Вернуться к чату" : "Описание и история"}</button> : null}
      </header>
      {chat.notice ? <div className="shrink-0 px-4 pt-2"><InlineAlert aria-live="polite" role="status">{chat.notice}</InlineAlert></div> : null}
      <div id="requester-chat-content" ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-3"
        onScroll={() => { const el = scrollRef.current; if (el) followMessages.current = el.scrollHeight - el.scrollTop - el.clientHeight < 120; }}>
        {detailQuery.isLoading ? <p role="status" className="p-4 text-sm text-slate-600">Загружаем обращение...</p>
          : detailQuery.isError ? <InlineAlert role="alert">{requesterErrorMessage(detailQuery.error, "Не удалось загрузить обращение")}</InlineAlert>
          : !ticket ? <p className="p-4 text-sm text-slate-600">Обращение не найдено.</p>
          : showDetails ? <div className="mx-auto max-w-4xl space-y-4"><TicketDetailHeader ticket={ticket} /><TimelinePanel events={events} /></div>
          : <div className="mx-auto max-w-4xl space-y-3">
            <RequesterConsentList consents={chat.pendingConsents} disabled={chat.actionSubmitting} onDecision={chat.decideConsent} />
            {chat.canClose || chat.canRate || chat.canReopen ? <TicketResolutionPanel {...chat} /> : null}
            <MessagesPanel messages={messages} />
          </div>}
      </div>
      {ticket && !showDetails && chat.canSendMessage ? <div className="shrink-0 border-t border-slate-200 bg-white px-4 py-3"><div className="mx-auto max-w-4xl"><TicketReplyComposer {...chat} /></div></div> : null}
    </section>
  );
}
