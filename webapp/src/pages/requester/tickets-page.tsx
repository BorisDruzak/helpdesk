import { useQueryClient } from "@tanstack/react-query";
import { Paperclip, Send } from "lucide-react";
import type { ChangeEvent } from "react";
import { useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { formatRussianDateTime, formatStatusLabel } from "../../components/ui-page";
import {
  approveRequesterConsent,
  closeRequesterTicket,
  denyRequesterConsent,
  reopenRequesterTicket,
  sendRequesterTicketMessage,
  submitRequesterTicketFeedback,
  uploadRequesterTicketAttachment,
} from "../../features/requester/api";
import { RequesterConsentList } from "../../features/requester/consent-card";
import { requesterErrorMessage, requesterSafeAttachmentName, requesterTicketNextActionLabel } from "../../features/requester/labels";
import { Button, FieldShell, FormActions, InlineAlert, Input, Select, Textarea } from "../../features/requester/ui/form-controls";
import {
  humanRequesterTicketCode,
  requesterInvalidations,
  requesterTicketRouteParam,
  useRequesterConsentsQuery,
  useRequesterTicketDetailQuery,
  useRequesterTicketsQuery,
} from "../../features/requester/queries";
import type {
  AuthenticatedRequesterTicket,
  PublicTicketAttachment,
  PublicTicketEvent,
  PublicTicketMessage,
  RequesterConsent,
  RequesterAttachmentUploadResult,
} from "../../features/requester/types";

type TicketFilter = "open" | "action" | "closed" | "all";

const filters: Array<{ key: TicketFilter; label: string }> = [
  { key: "open", label: "Открытые" },
  { key: "action", label: "Требуют действий" },
  { key: "closed", label: "Закрытые" },
  { key: "all", label: "Все" },
];

const actionStatuses = new Set(["waiting_on_user", "resolved"]);
const closedStatuses = new Set(["closed", "canceled", "archived"]);

const reopenReasonOptions = [
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

export function RequesterTicketsPage() {
  const { ticketId } = useParams();
  const queryClient = useQueryClient();
  const ticketsQuery = useRequesterTicketsQuery();
  const consentsQuery = useRequesterConsentsQuery();
  const detailQuery = useRequesterTicketDetailQuery(ticketId, { enabled: Boolean(ticketId) });
  const [filter, setFilter] = useState<TicketFilter>("open");
  const [search, setSearch] = useState("");
  const [messageText, setMessageText] = useState("");
  const [pendingAttachments, setPendingAttachments] = useState<Array<PublicTicketAttachment & { name: string }>>([]);
  const [messageSending, setMessageSending] = useState(false);
  const [attachmentUploading, setAttachmentUploading] = useState(false);
  const [actionSubmitting, setActionSubmitting] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [feedbackRating, setFeedbackRating] = useState(5);
  const [feedbackProblemResolved, setFeedbackProblemResolved] = useState(true);
  const [feedbackReason, setFeedbackReason] = useState("not_resolved");
  const [feedbackComment, setFeedbackComment] = useState("");
  const [feedbackId, setFeedbackId] = useState<string | null>(null);
  const [reopenAvailable, setReopenAvailable] = useState(false);
  const [reopenReason, setReopenReason] = useState("problem_returned");
  const [reopenComment, setReopenComment] = useState("");
  const attachmentInputRef = useRef<HTMLInputElement | null>(null);

  const tickets = ticketsQuery.data ?? [];
  const selectedTicket = detailQuery.data?.ticket ?? null;
  const selectedInternalTicketId = selectedTicket?.ticket_id ?? null;
  const selectedActions = selectedTicket?.actions;
  const canSendMessage = selectedActions?.can_send_message === true;
  const canAttachFiles = selectedActions?.can_attach_files === true;
  const pendingConsents = (consentsQuery.data ?? []).filter(
    (consent) =>
      consent.status === "pending" &&
      (!ticketId || consent.ticket_id === ticketId || (selectedInternalTicketId ? consent.ticket_id === selectedInternalTicketId : false)),
  );
  const filteredTickets = useMemo(
    () => tickets.filter((ticket) => ticketMatchesFilter(ticket, filter)).filter((ticket) => ticketMatchesSearch(ticket, search)),
    [filter, search, tickets],
  );
  const canClose = selectedActions?.can_confirm_solution === true;
  const canRate = selectedActions?.can_rate_solution === true;
  const canReopen = selectedActions?.can_reopen === true;

  async function refreshTicket() {
    if (!ticketId) {
      await requesterInvalidations.afterTicketMutation(queryClient);
      return;
    }
    await requesterInvalidations.afterTicketMutation(queryClient, ticketId);
    await detailQuery.refetch();
  }

  async function handleAttachmentUpload(event: ChangeEvent<HTMLInputElement>) {
    if (!ticketId) {
      return;
    }
    const files = Array.from(event.currentTarget.files ?? []);
    if (!files.length) {
      return;
    }
    setAttachmentUploading(true);
    setNotice(null);
    try {
      const uploaded = await Promise.all(files.map((file) => uploadRequesterTicketAttachment(selectedInternalTicketId ?? ticketId, file)));
      setPendingAttachments((current) => [...current, ...uploaded.map((item) => attachmentFromUpload(item))]);
    } catch (exc) {
      setNotice(requesterErrorMessage(exc, "Не удалось загрузить вложение"));
    } finally {
      setAttachmentUploading(false);
    }
  }

  async function handleSendMessage() {
    if (!ticketId || !canSendMessage || messageSending || attachmentUploading) {
      return;
    }
    const text = messageText.trim();
    const attachmentRefs = pendingAttachments.map((attachment) => attachment.artifact_id);
    if (!text && !attachmentRefs.length) {
      return;
    }
    setMessageSending(true);
    setNotice(null);
    try {
      await sendRequesterTicketMessage(ticketId, text, attachmentRefs);
      setMessageText("");
      setPendingAttachments([]);
      if (attachmentInputRef.current) {
        attachmentInputRef.current.value = "";
      }
      await refreshTicket();
      setNotice("Ответ отправлен");
    } catch (exc) {
      setNotice(requesterErrorMessage(exc, "Не удалось отправить сообщение", { operation: "message" }));
    } finally {
      setMessageSending(false);
    }
  }

  async function decideConsent(consent: RequesterConsent, decision: "approved" | "denied") {
    setActionSubmitting(true);
    setNotice(null);
    try {
      if (decision === "approved") {
        await approveRequesterConsent(consent.consent_id);
      } else {
        await denyRequesterConsent(consent.consent_id, "requester_denied");
      }
      await requesterInvalidations.afterConsentDecision(queryClient, ticketId ?? consent.ticket_id);
      await detailQuery.refetch();
      setNotice(decision === "approved" ? "Согласие подтверждено" : "Согласие отклонено");
    } catch (exc) {
      setNotice(requesterErrorMessage(exc, "Не удалось сохранить решение", { operation: "close" }));
    } finally {
      setActionSubmitting(false);
    }
  }

  async function closeTicket() {
    if (!ticketId) {
      return;
    }
    setActionSubmitting(true);
    setNotice(null);
    try {
      await closeRequesterTicket(ticketId);
      await refreshTicket();
      setNotice("Решение подтверждено");
    } catch (exc) {
      setNotice(requesterErrorMessage(exc, "Не удалось закрыть обращение", { operation: "close" }));
    } finally {
      setActionSubmitting(false);
    }
  }

  async function submitFeedback() {
    if (!ticketId) {
      return;
    }
    setActionSubmitting(true);
    setNotice(null);
    try {
      const result = await submitRequesterTicketFeedback(ticketId, {
        rating: feedbackRating,
        problem_resolved: feedbackProblemResolved,
        resolution_confirmed: feedbackProblemResolved,
        reason_codes: feedbackRating <= 3 || !feedbackProblemResolved ? [feedbackReason] : [],
        comment: feedbackComment.trim() || null,
        source_surface: "requester_portal",
      });
      setFeedbackId(result.feedback_id);
      setReopenAvailable(result.reopen_available);
      await refreshTicket();
      setNotice(result.message || "Оценка сохранена");
    } catch (exc) {
      setNotice(requesterErrorMessage(exc, "Не удалось сохранить оценку", { operation: "feedback" }));
    } finally {
      setActionSubmitting(false);
    }
  }

  async function reopenTicket() {
    if (!ticketId) {
      return;
    }
    setActionSubmitting(true);
    setNotice(null);
    try {
      await reopenRequesterTicket(ticketId, {
        reason_code: reopenReason,
        reason_comment: reopenComment.trim() || feedbackComment.trim() || null,
        linked_feedback_id: feedbackId,
      });
      setReopenAvailable(false);
      await refreshTicket();
      setNotice("Обращение возвращено в работу");
    } catch (exc) {
      setNotice(requesterErrorMessage(exc, "Не удалось вернуть обращение в работу", { operation: "reopen" }));
    } finally {
      setActionSubmitting(false);
    }
  }

  return (
    <div className="mx-auto grid max-w-6xl gap-5 px-4 py-6 lg:grid-cols-[360px_minmax(0,1fr)]">
      <section className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-brand-700">Кабинет пользователя</p>
            <h1 className="mt-1 text-2xl font-semibold text-slate-950">Мои обращения</h1>
          </div>
          <Link className="rounded-panel bg-brand-700 px-3 py-2 text-sm font-semibold text-white" to="/app/requester/new">
            Создать
          </Link>
        </div>
        <FieldShell label="Поиск по обращениям">
          <Input
            aria-label="Поиск по обращениям"
            className="mt-1 w-full font-normal"
            onChange={(event) => setSearch(event.currentTarget.value)}
            value={search}
          />
        </FieldShell>
        <div className="flex flex-wrap gap-2" role="group" aria-label="Фильтр обращений">
          {filters.map((item) => (
            <Button
              className={filter === item.key ? "border-brand-300 bg-brand-50 text-brand-800" : undefined}
              key={item.key}
              onClick={() => setFilter(item.key)}
              size="sm"
              type="button"
              variant={filter === item.key ? "outline" : "ghost"}
            >
              {item.label}
            </Button>
          ))}
        </div>
        <div className="overflow-hidden rounded-panel border border-slate-200 bg-white">
          {ticketsQuery.isLoading ? <p className="px-4 py-3 text-sm text-slate-600">Загружаем обращения...</p> : null}
          {!ticketsQuery.isLoading && !filteredTickets.length ? (
            <p className="px-4 py-3 text-sm text-slate-600">Нет обращений по выбранным условиям</p>
          ) : null}
          {filteredTickets.map((ticket) => {
            const routeParam = requesterTicketRouteParam(ticket);
            const cardBody = (
              <>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-xs font-semibold text-brand-700">{humanRequesterTicketCode(ticket)}</p>
                    <p className="mt-1 truncate text-sm font-semibold text-slate-950">{ticket.title || "Без темы"}</p>
                  </div>
                  <span className="shrink-0 rounded-full bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-700">
                    {ticket.requester_status_label || ticket.public_status_label || ticket.status_label || formatStatusLabel(ticket.status)}
                  </span>
                </div>
                <p className="mt-2 text-xs text-slate-500">{formatRussianDateTime(ticket.updated_at || ticket.created_at, { emptyText: "Дата не указана" })}</p>
                {requesterTicketNextActionLabel(ticket) ? <p className="mt-1 text-xs font-semibold text-amber-700">{requesterTicketNextActionLabel(ticket)}</p> : null}
              </>
            );
            return routeParam ? (
              <Link
                className={`block border-t border-slate-100 px-4 py-3 first:border-t-0 ${requesterTicketIsActive(ticket, ticketId) ? "bg-brand-50" : "hover:bg-slate-50"}`}
                key={ticket.ticket_id}
                to={`/app/requester/tickets/${encodeURIComponent(routeParam)}`}
              >
                {cardBody}
              </Link>
            ) : (
              <div className="block border-t border-slate-100 px-4 py-3 first:border-t-0" key={ticket.ticket_id}>
                {cardBody}
              </div>
            );
          })}
        </div>
      </section>
      <section className="min-w-0">
        {!ticketId ? (
          <div className="rounded-panel border border-slate-200 bg-white p-5 text-sm text-slate-600">Выберите обращение из списка.</div>
        ) : detailQuery.isLoading ? (
          <div className="rounded-panel border border-slate-200 bg-white p-5 text-sm text-slate-600">Загружаем обращение...</div>
        ) : selectedTicket ? (
          <div className="space-y-4">
            <article className="rounded-panel border border-slate-200 bg-white p-5">
              <p className="text-sm font-semibold text-brand-700">{humanRequesterTicketCode(selectedTicket)}</p>
              <h2 className="mt-1 text-2xl font-semibold text-slate-950">{selectedTicket.title || "Без темы"}</h2>
              <p className="mt-2 whitespace-pre-wrap text-sm text-slate-700">{selectedTicket.description || "Описание не указано"}</p>
              <div className="mt-3 flex flex-wrap gap-2 text-xs font-semibold text-slate-600">
                <span>{selectedTicket.requester_status_label || selectedTicket.status_label || formatStatusLabel(selectedTicket.status)}</span>
                <span>{formatRussianDateTime(selectedTicket.updated_at || selectedTicket.created_at, { emptyText: "Дата не указана" })}</span>
              </div>
            </article>
            {notice ? <InlineAlert aria-live="polite" role="status">{notice}</InlineAlert> : null}
            <RequesterConsentList consents={pendingConsents} disabled={actionSubmitting} onDecision={decideConsent} />
            <MessagesPanel messages={detailQuery.data?.messages ?? []} />
            <TimelinePanel events={detailQuery.data?.events ?? []} />
            {canRate || canClose ? (
              <section className="rounded-panel border border-slate-200 bg-white p-4">
                <h3 className="text-lg font-semibold text-slate-950">Решение обращения</h3>
                {canClose ? (
                  <Button className="mt-3" disabled={actionSubmitting} onClick={closeTicket} type="button">
                    Подтвердить решение
                  </Button>
                ) : null}
                {canRate ? (
                  <div className="mt-4 grid gap-3">
                    <FieldShell label="Оценка обращения">
                      <Input
                        aria-label="Оценка обращения"
                        className="mt-1 w-24 font-normal"
                        max={5}
                        min={1}
                        onChange={(event) => setFeedbackRating(Number(event.currentTarget.value))}
                        type="number"
                        value={feedbackRating}
                      />
                    </FieldShell>
                    <label className="flex items-center gap-2 text-sm font-semibold text-slate-700">
                      <input checked={feedbackProblemResolved} onChange={(event) => setFeedbackProblemResolved(event.currentTarget.checked)} type="checkbox" />
                      Проблема решена
                    </label>
                    {(feedbackRating <= 3 || !feedbackProblemResolved) ? (
                      <FieldShell label="Причина">
                        <Select className="mt-1 w-full font-normal" onChange={(event) => setFeedbackReason(event.currentTarget.value)} value={feedbackReason}>
                          <option value="not_resolved">Проблема не решена</option>
                          <option value="poor_quality">Низкое качество решения</option>
                          <option value="other">Другая причина</option>
                        </Select>
                      </FieldShell>
                    ) : null}
                    <FieldShell label="Комментарий">
                      <Textarea className="mt-1 min-h-20 font-normal" onChange={(event) => setFeedbackComment(event.currentTarget.value)} value={feedbackComment} />
                    </FieldShell>
                    <FormActions>
                      <Button disabled={actionSubmitting} onClick={submitFeedback} type="button" variant="outline">
                        Отправить оценку
                      </Button>
                      {canReopen ? (
                        <Button className="border-amber-300 bg-amber-50 text-amber-800 hover:bg-amber-100" disabled={actionSubmitting} onClick={reopenTicket} type="button" variant="outline">
                          Вернуть в работу
                        </Button>
                      ) : null}
                    </FormActions>
                    {canReopen ? (
                      <div className="grid gap-3">
                        <FieldShell label="Причина возврата">
                          <Select className="mt-1 w-full font-normal" onChange={(event) => setReopenReason(event.currentTarget.value)} value={reopenReason}>
                            {reopenReasonOptions.map((option) => (
                              <option key={option.value} value={option.value}>
                                {option.label}
                              </option>
                            ))}
                          </Select>
                        </FieldShell>
                        <Textarea
                        aria-label="Комментарий для возврата в работу"
                        className="min-h-20 text-sm"
                        onChange={(event) => setReopenComment(event.currentTarget.value)}
                        placeholder="Что осталось не решено"
                          value={reopenComment}
                        />
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </section>
            ) : null}
            {canSendMessage ? (
              <section aria-labelledby="requester-reply-title" className="sticky bottom-4 rounded-panel border border-slate-200 bg-white p-4 shadow-lg">
                <h3 className="text-lg font-semibold text-slate-950" id="requester-reply-title">Ответить</h3>
                <Textarea
                  aria-label="Ответ заявителя"
                  className="mt-3 min-h-28 text-sm"
                  onChange={(event) => setMessageText(event.currentTarget.value)}
                  value={messageText}
                />
                <input aria-label="Прикрепить файл к ответу" className="sr-only" onChange={handleAttachmentUpload} ref={attachmentInputRef} type="file" />
                {pendingAttachments.length ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {pendingAttachments.map((attachment) => (
                      <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700" key={attachment.artifact_id}>
                        {attachment.name}
                      </span>
                    ))}
                  </div>
                ) : null}
                <FormActions className="mt-3">
                  <Button disabled={!canAttachFiles || attachmentUploading || messageSending} leadingIcon={<Paperclip className="h-4 w-4" />} onClick={() => attachmentInputRef.current?.click()} type="button" variant="outline">
                    {attachmentUploading ? "Загружаем..." : "Вложить файл"}
                  </Button>
                  <Button
                    disabled={messageSending || attachmentUploading || (!messageText.trim() && !pendingAttachments.length)}
                    leadingIcon={<Send className="h-4 w-4" />}
                    onClick={handleSendMessage}
                    type="button"
                  >
                    {messageSending ? "Отправляем..." : "Отправить"}
                  </Button>
                </FormActions>
              </section>
            ) : null}
          </div>
        ) : (
          <div className="rounded-panel border border-slate-200 bg-white p-5 text-sm text-slate-600">Обращение не найдено.</div>
        )}
      </section>
    </div>
  );
}

function ticketMatchesFilter(ticket: AuthenticatedRequesterTicket, filter: TicketFilter): boolean {
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

function ticketMatchesSearch(ticket: AuthenticatedRequesterTicket, search: string): boolean {
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

function requesterTicketIsActive(ticket: AuthenticatedRequesterTicket, routeParam: string | undefined): boolean {
  if (!routeParam) {
    return false;
  }
  return routeParam === ticket.ticket_id || routeParam === ticket.ticket_code;
}

function attachmentFromUpload(upload: RequesterAttachmentUploadResult): PublicTicketAttachment & { name: string } {
  return {
    artifact_id: upload.artifact_id,
    kind: upload.kind,
    name: requesterSafeAttachmentName(upload.filename),
    url: upload.url,
  };
}

function MessagesPanel({ messages }: { messages: PublicTicketMessage[] }) {
  return (
    <section className="rounded-panel border border-slate-200 bg-white p-4">
      <h3 className="text-lg font-semibold text-slate-950">Переписка</h3>
      {!messages.length ? <p className="mt-2 text-sm text-slate-600">Сообщений пока нет.</p> : null}
      <div className="mt-3 grid gap-3">
        {messages.map((message) => (
          <article className="rounded-panel border border-slate-200 px-3 py-2" key={message.message_id || message.event_id || message.created_at}>
            <div className="flex flex-wrap justify-between gap-2 text-xs font-semibold text-slate-500">
              <span>{message.from_role === "support" || message.sender_role === "support" ? "Поддержка" : "Заявитель"}</span>
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

function TimelinePanel({ events }: { events: PublicTicketEvent[] }) {
  return (
    <section className="rounded-panel border border-slate-200 bg-white p-4">
      <h3 className="text-lg font-semibold text-slate-950">История</h3>
      <ul aria-label="История обращения" className="mt-3 grid gap-2">
        {events.length ? (
          events.map((event) => (
            <li className="rounded-panel bg-slate-50 px-3 py-2 text-sm text-slate-700" key={String(event.event_id ?? event.id ?? event.created_at ?? event.ts)}>
              <span className="font-semibold">{event.requester_timeline_text || "Обновление обращения"}</span>
              <span className="ml-2 text-xs text-slate-500">{formatRussianDateTime(event.created_at || event.ts, { emptyText: "" })}</span>
            </li>
          ))
        ) : (
          <li className="text-sm text-slate-600">История пока пуста.</li>
        )}
      </ul>
    </section>
  );
}
