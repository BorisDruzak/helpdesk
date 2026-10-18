import { formatRussianDateTime, formatStatusLabel } from "../../components/ui-page";
import { requesterSafeAttachmentName } from "../../features/requester/labels";
import { humanRequesterTicketCode } from "../../features/requester/queries";
import type {
  AuthenticatedRequesterTicket,
  PublicTicketAttachment,
  PublicTicketEvent,
  PublicTicketMessage,
  RequesterAttachmentUploadResult,
} from "../../features/requester/types";

export type TicketFilter = "open" | "action" | "closed" | "all";

export const filters: Array<{ key: TicketFilter; label: string }> = [
  { key: "open", label: "Открытые" },
  { key: "action", label: "Требуют действий" },
  { key: "closed", label: "Закрытые" },
  { key: "all", label: "Все" },
];

const actionStatuses = new Set(["waiting_on_user", "resolved"]);
const closedStatuses = new Set(["closed", "canceled", "archived"]);

export const reopenReasonOptions = [
  { value: "problem_returned", label: "Проблема повторилась" },
  { value: "not_resolved", label: "Проблема не решена" },
  { value: "incomplete_work", label: "Работа выполнена не полностью" },
  { value: "wrong_resolution", label: "Решение не подходит" },
  { value: "unclear_instruction", label: "Непонятная инструкция" },
  { value: "requester_disagreed", label: "Не согласен с решением" },
  { value: "closed_too_early", label: "Закрыто слишком рано" },
  { value: "new_information", label: "Появилась новая информация" },
  { value: "wrong_category_or_queue", label: "Нужна другая команда" },
  { value: "dependency_failed", label: "Смежная проблема не устранена" },
  { value: "knowledge_article_failed", label: "Статья не помогла" },
  { value: "other", label: "Другая причина" },
];

export function ticketMatchesFilter(ticket: AuthenticatedRequesterTicket, filter: TicketFilter): boolean {
  const status = String(ticket.status ?? "").toLowerCase();
  if (filter === "all") {
    return true;
  }
  if (filter === "action") {
    return actionStatuses.has(status);
  }
  if (filter === "closed") {
    return closedStatuses.has(status);
  }
  return !closedStatuses.has(status);
}

export function ticketMatchesSearch(ticket: AuthenticatedRequesterTicket, search: string): boolean {
  const query = search.trim().toLowerCase();
  if (!query) {
    return true;
  }
  return [
    ticket.title,
    ticket.ticket_code,
    humanRequesterTicketCode(ticket),
    ticket.requester_status_label,
    ticket.status_label,
    formatStatusLabel(ticket.status),
  ]
    .filter(Boolean)
    .some((value) => String(value).toLowerCase().includes(query));
}

export function requesterTicketIsActive(ticket: AuthenticatedRequesterTicket, routeParam: string | undefined): boolean {
  if (!routeParam) {
    return false;
  }
  return routeParam === ticket.ticket_id || routeParam === ticket.ticket_code;
}

export function attachmentFromUpload(upload: RequesterAttachmentUploadResult): PublicTicketAttachment & { name: string } {
  return {
    artifact_id: upload.artifact_id,
    kind: upload.kind,
    name: requesterSafeAttachmentName(upload.filename),
    url: upload.url,
  };
}

const humanMessageRoles = new Set(["user", "requester", "agent", "device", "client", "support", "admin", "staff", "operator"]);
const supportMessageRoles = new Set(["support", "admin", "staff", "operator"]);
type RequesterHistoryEvent = PublicTicketEvent & { attachments?: PublicTicketAttachment[] };
function messageRole(message: PublicTicketMessage): string {
  return (message.from_role || message.sender_role || "user").trim().toLowerCase();
}

export function partitionRequesterTimeline(messages: PublicTicketMessage[], events: PublicTicketEvent[]) {
  const conversation: PublicTicketMessage[] = [];
  const history: RequesterHistoryEvent[] = [...events];
  const eventIndices = new Map(history.flatMap((event, index) => {
    const id = event.event_id ?? event.id;
    return id == null ? [] : [[String(id), index] as const];
  }));
  for (const [index, message] of messages.entries()) {
    const eventIndex = message.event_id == null ? undefined : eventIndices.get(String(message.event_id));
    const existing = eventIndex === undefined ? undefined : history[eventIndex];
    if (humanMessageRoles.has(messageRole(message)) && existing?.requester_timeline_kind !== "system_event" && existing?.requester_timeline_kind !== "diagnostic_result") {
      conversation.push(message);
      continue;
    }
    if (existing) {
      // Retain the server's canonical safe event projection and public file references.
      if (message.attachments?.length) history[eventIndex!] = { ...existing, attachments: message.attachments };
    } else {
      const event: RequesterHistoryEvent = {
        event_id: message.event_id ?? `message:${message.message_id ?? index}`, type: "chat_message",
        requester_timeline_kind: "system_event", requester_timeline_text: message.text || "Системное уведомление",
        ts: message.ts, created_at: message.created_at, attachments: message.attachments,
      };
      eventIndices.set(String(event.event_id), history.length); history.push(event);
    }
  }
  return { messages: conversation, events: history };
}

export function MessagesPanel({ messages }: { messages: PublicTicketMessage[] }) {
  return (
    <section className="rounded-panel border border-slate-200 bg-white p-4">
      <h3 className="text-lg font-semibold text-slate-950">Переписка</h3>
      {!messages.length ? <p className="mt-2 text-sm text-slate-600">Сообщений пока нет.</p> : null}
      <div className="mt-3 grid gap-3">
        {messages.map((message) => (
          <article className="rounded-panel border border-slate-200 px-3 py-2" key={message.message_id || message.event_id || message.created_at}>
            <div className="flex flex-wrap justify-between gap-2 text-xs font-semibold text-slate-500">
              <span>{supportMessageRoles.has(messageRole(message)) ? "Поддержка" : "Заявитель"}</span>
              <span>{formatRussianDateTime(message.created_at || message.ts, { emptyText: "" })}</span>
            </div>
            {message.text ? <p className="mt-2 whitespace-pre-wrap text-sm text-slate-800">{message.text}</p> : null}
            {message.attachments?.length ? (
              <div className="mt-2 flex flex-wrap gap-2">
                {message.attachments.map((attachment) => (
                  <a className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700" href={attachment.url || `/api/artifacts/${encodeURIComponent(attachment.artifact_id)}/download`} key={attachment.artifact_id}>
                    {requesterSafeAttachmentName(attachment.name)}
                  </a>
                ))}
              </div>
            ) : null}
          </article>
        ))}
      </div>
    </section>
  );
}

export function TimelinePanel({ events }: { events: RequesterHistoryEvent[] }) {
  return (
    <section className="rounded-panel border border-slate-200 bg-white p-4">
      <h3 className="text-lg font-semibold text-slate-950">История</h3>
      <ul aria-label="История обращения" className="mt-3 grid gap-2">
        {events.length ? (
          events.map((event) => (
            <li className="rounded-panel bg-slate-50 px-3 py-2 text-sm text-slate-700" key={String(event.event_id ?? event.id ?? event.created_at ?? event.ts)}>
              <span className="font-semibold">{event.requester_timeline_text || "Обновление обращения"}</span>
              <span className="ml-2 text-xs text-slate-500">{formatRussianDateTime(event.created_at || event.ts, { emptyText: "" })}</span>
              {event.attachments?.length ? <div className="mt-2 flex flex-wrap gap-2">{event.attachments.map(attachment => <a className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700" href={attachment.url || `/api/artifacts/${encodeURIComponent(attachment.artifact_id)}/download`} key={attachment.artifact_id}>{requesterSafeAttachmentName(attachment.name)}</a>)}</div> : null}
            </li>
          ))
        ) : (
          <li className="text-sm text-slate-600">История пока пуста.</li>
        )}
      </ul>
    </section>
  );
}
