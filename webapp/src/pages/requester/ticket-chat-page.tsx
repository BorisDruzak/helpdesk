import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Info } from "lucide-react";
import { formatStatusLabel } from "../../components/ui-page";
import { RequesterApiError } from "../../features/requester/api";
import { humanRequesterTicketCode } from "../../features/requester/queries";
import { requesterErrorMessage } from "../../features/requester/labels";
import { RequesterConsentList } from "../../features/requester/consent-card";
import { InlineAlert } from "../../features/requester/ui/form-controls";
import { TicketDetailHeader, TicketReplyComposer, TicketResolutionPanel, TicketResultSummary } from "./tickets-panels";
import { TimelinePanel } from "./tickets-workflow";
import { useRequesterTicketChat } from "./use-ticket-chat";
import { RequesterTicketContext, RequesterTicketContextBrief } from "./ticket-context-panel";
import { RequesterConversation } from "./ticket-conversation";

export function RequesterTicketChatPage() {
  const { ticketId } = useParams();
  return <RequesterTicketChat key={ticketId} ticketId={ticketId} />;
}

function RequesterTicketChat({ ticketId }: { ticketId: string | undefined }) {
  const chat = useRequesterTicketChat(ticketId);
  const [showDetails, setShowDetails] = useState(false);
  const [wide, setWide] = useState(() => window.matchMedia?.("(min-width: 1280px)").matches ?? false);
  const [contextExpanded, setContextExpanded] = useState(false);
  useEffect(() => {
    const media = window.matchMedia?.("(min-width: 1280px)");
    if (!media) return;
    const update = () => setWide(media.matches);
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const followMessages = useRef(true);
  const { detailQuery } = chat;
  const denied = detailQuery.isError && detailQuery.error instanceof RequesterApiError && [401, 403, 404].includes(detailQuery.error.status);
  const ticket = denied ? null : chat.selectedTicket;
  const handling = denied ? null : detailQuery.data?.handling;
  const messages = detailQuery.data?.messages ?? [];
  const events = detailQuery.data?.events ?? [];
  useEffect(() => {
    const scroller = scrollRef.current;
    if (scroller && followMessages.current && !showDetails && !ticket?.requester_resolution_summary && !chat.canClose && !chat.canRate && !chat.canReopen && !chat.pendingConsents.length) scroller.scrollTop = scroller.scrollHeight;
  }, [messages, events, showDetails, ticket?.requester_resolution_summary, chat.canClose, chat.canRate, chat.canReopen, chat.pendingConsents.length]);
  return (
    <section aria-label="Чат обращения" className="flex min-h-0 flex-1 flex-col bg-slate-50">
      <header className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-white px-4 py-3">
        <div className="min-w-0 w-full">
          <div className="flex flex-wrap items-center justify-between gap-2"><Link className="inline-flex items-center gap-1 text-sm font-semibold text-brand-700" to="/app/requester/tickets"><ArrowLeft className="h-4 w-4" />Все обращения</Link>
          {ticket ? <button aria-expanded={showDetails} aria-controls="requester-chat-content" className="inline-flex items-center gap-1 rounded-panel px-2 py-1 text-xs font-semibold text-slate-600 hover:bg-slate-50" onClick={() => setShowDetails(value => !value)} type="button"><Info className="h-3.5 w-3.5" />{showDetails ? "Вернуться к чату" : "Описание и история"}</button> : null}</div>
          {ticket ? <><div className="mt-2 flex flex-wrap items-center gap-2"><p className="text-xs font-semibold text-slate-500">{humanRequesterTicketCode(ticket)}</p><span className="rounded-full bg-brand-50 px-2 py-1 text-xs font-semibold text-brand-800">{handling?.status_label || ticket.public_status_label || ticket.requester_status_label || ticket.status_label || formatStatusLabel(ticket.status)}</span>{handling?.assignee?.assigned ? <span className="text-xs text-slate-600">Специалист: {handling.assignee.display_name || "поддержка"}</span> : null}</div><h1 className="mt-1 break-words text-lg font-semibold text-slate-950">{ticket.title || "Без темы"}</h1></> : <h1 className="mt-2 text-lg font-semibold">Чат обращения</h1>}
        </div>
      </header>
      {chat.notice ? <div className="shrink-0 px-4 pt-2"><InlineAlert aria-live="polite" role="status">{chat.notice}</InlineAlert></div> : null}
      {ticket && detailQuery.isError ? <div role="alert" className="shrink-0 bg-amber-50 px-4 py-2 text-sm text-amber-900">Не удалось обновить обращение. Показаны последние полученные данные. <button className="font-semibold underline" onClick={() => void detailQuery.refetch()} type="button">Повторить</button></div> : null}
      <div className={`mx-auto grid min-h-0 w-full max-w-[1600px] flex-1 grid-cols-1 gap-3 p-3 xl:gap-4 xl:p-4 ${ticket && handling ? "grid-rows-[auto_minmax(0,1fr)] xl:grid-cols-[minmax(0,1fr)_304px] xl:grid-rows-1" : "grid-rows-1"}`}>
      {ticket && handling ? <aside className="order-1 min-h-0 overflow-y-auto xl:order-2"><details open={wide || contextExpanded} onToggle={event => { if (!wide) setContextExpanded(event.currentTarget.open); }}><summary className="cursor-pointer rounded-panel border border-slate-200 bg-white p-3 text-sm font-semibold text-slate-800 xl:hidden">Обработка, SLA и устройство{!contextExpanded ? <RequesterTicketContextBrief handling={handling} /> : null}</summary><div className="mt-2 xl:mt-0"><RequesterTicketContext handling={handling} /></div></details></aside> : null}
      <div className="order-2 flex min-h-0 min-w-0 flex-col xl:order-1">
      <div id="requester-chat-content" ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-1 py-2"
        onScroll={() => { const el = scrollRef.current; if (el) followMessages.current = el.scrollHeight - el.scrollTop - el.clientHeight < 120; }}>
        {detailQuery.isLoading ? <p role="status" className="p-4 text-sm text-slate-600">Загружаем обращение...</p>
          : detailQuery.isError && !ticket ? <InlineAlert role="alert">{requesterErrorMessage(detailQuery.error, "Не удалось загрузить обращение")}</InlineAlert>
          : !ticket ? <p className="p-4 text-sm text-slate-600">Обращение не найдено.</p>
          : showDetails ? <div className="space-y-4"><TicketDetailHeader ticket={ticket} /><TimelinePanel events={events} /></div>
          : <div className="space-y-3">
            <TicketResultSummary ticket={ticket} />
            <RequesterConsentList consents={chat.pendingConsents} disabled={chat.actionSubmitting} onDecision={chat.decideConsent} />
            {chat.canClose || chat.canRate || chat.canReopen ? <TicketResolutionPanel {...chat} /> : null}
            <RequesterConversation messages={messages} events={events} />
          </div>}
      </div>
      {ticket && !showDetails && chat.canSendMessage ? <div className="mt-2 shrink-0 rounded-panel border border-slate-200 bg-white p-3"><TicketReplyComposer {...chat} /></div> : null}
      {ticket && !showDetails && !chat.canSendMessage ? <p className="mt-2 shrink-0 rounded-panel border border-slate-200 bg-white p-3 text-sm text-slate-600">Переписка доступна для просмотра. {chat.canReopen ? "Если проблема повторилась, верните обращение в работу." : "Ответ в текущем статусе недоступен."}</p> : null}
      <p className="mt-2 shrink-0 text-xs text-slate-500">Обновляется автоматически</p>
      </div>
      </div>
    </section>
  );
}
