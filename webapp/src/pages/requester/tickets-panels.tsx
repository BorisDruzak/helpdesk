import { Paperclip, Send } from "lucide-react";
import type { ChangeEvent, MutableRefObject } from "react";
import { Link } from "react-router-dom";

import { formatRussianDateTime, formatStatusLabel } from "../../components/ui-page";
import { requesterTicketNextActionLabel } from "../../features/requester/labels";
import {
  humanRequesterTicketCode,
  requesterTicketRouteParam,
} from "../../features/requester/queries";
import type {
  AuthenticatedRequesterTicket,
  PublicTicketAttachment,
} from "../../features/requester/types";
import { Button, FieldShell, FormActions, Input, Select, Textarea } from "../../features/requester/ui/form-controls";
import {
  filters,
  reopenReasonOptions,
  requesterTicketIsActive,
  type TicketFilter,
} from "./tickets-workflow";

export function TicketsListPanel({
  filter,
  filteredTickets,
  isLoading,
  search,
  selectedTicketId,
  setFilter,
  setSearch,
}: {
  filter: TicketFilter;
  filteredTickets: AuthenticatedRequesterTicket[];
  isLoading: boolean;
  search: string;
  selectedTicketId?: string;
  setFilter: (value: TicketFilter) => void;
  setSearch: (value: string) => void;
}) {
  return (
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
        {isLoading ? <p className="px-4 py-3 text-sm text-slate-600">Загружаем обращения...</p> : null}
        {!isLoading && !filteredTickets.length ? (
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
              className={`block border-t border-slate-100 px-4 py-3 first:border-t-0 ${requesterTicketIsActive(ticket, selectedTicketId) ? "bg-brand-50" : "hover:bg-slate-50"}`}
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
  );
}

export function TicketDetailHeader({ ticket }: { ticket: AuthenticatedRequesterTicket }) {
  return (
    <article className="rounded-panel border border-slate-200 bg-white p-5">
      <p className="text-sm font-semibold text-brand-700">{humanRequesterTicketCode(ticket)}</p>
      <h2 className="mt-1 text-2xl font-semibold text-slate-950">{ticket.title || "Без темы"}</h2>
      <p className="mt-2 whitespace-pre-wrap text-sm text-slate-700">{ticket.description || "Описание не указано"}</p>
      <div className="mt-3 flex flex-wrap gap-2 text-xs font-semibold text-slate-600">
        <span>{ticket.requester_status_label || ticket.status_label || formatStatusLabel(ticket.status)}</span>
        <span>{formatRussianDateTime(ticket.updated_at || ticket.created_at, { emptyText: "Дата не указана" })}</span>
      </div>
    </article>
  );
}

export function TicketResolutionPanel({
  actionSubmitting,
  canClose,
  canRate,
  canReopen,
  closeTicket,
  feedbackComment,
  feedbackProblemResolved,
  feedbackRating,
  feedbackReason,
  reopenComment,
  reopenReason,
  reopenTicket,
  setFeedbackComment,
  setFeedbackProblemResolved,
  setFeedbackRating,
  setFeedbackReason,
  setReopenComment,
  setReopenReason,
  submitFeedback,
}: {
  actionSubmitting: boolean;
  canClose: boolean;
  canRate: boolean;
  canReopen: boolean;
  closeTicket: () => void;
  feedbackComment: string;
  feedbackProblemResolved: boolean;
  feedbackRating: number;
  feedbackReason: string;
  reopenComment: string;
  reopenReason: string;
  reopenTicket: () => void;
  setFeedbackComment: (value: string) => void;
  setFeedbackProblemResolved: (value: boolean) => void;
  setFeedbackRating: (value: number) => void;
  setFeedbackReason: (value: string) => void;
  setReopenComment: (value: string) => void;
  setReopenReason: (value: string) => void;
  submitFeedback: () => void;
}) {
  if (!canRate && !canClose) {
    return null;
  }
  return (
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
  );
}

export function TicketReplyComposer({
  attachmentInputRef,
  attachmentUploading,
  canAttachFiles,
  handleAttachmentUpload,
  handleSendMessage,
  messageSending,
  messageText,
  pendingAttachments,
  setMessageText,
}: {
  attachmentInputRef: MutableRefObject<HTMLInputElement | null>;
  attachmentUploading: boolean;
  canAttachFiles: boolean;
  handleAttachmentUpload: (event: ChangeEvent<HTMLInputElement>) => void;
  handleSendMessage: () => void;
  messageSending: boolean;
  messageText: string;
  pendingAttachments: Array<PublicTicketAttachment & { name: string }>;
  setMessageText: (value: string) => void;
}) {
  return (
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
  );
}
