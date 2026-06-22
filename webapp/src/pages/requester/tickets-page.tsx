import { useQueryClient } from "@tanstack/react-query";
import type { ChangeEvent } from "react";
import { useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";

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
import { requesterErrorMessage } from "../../features/requester/labels";
import { InlineAlert } from "../../features/requester/ui/form-controls";
import {
  TicketDetailHeader,
  TicketReplyComposer,
  TicketResolutionPanel,
  TicketsListPanel,
} from "./tickets-panels";
import {
  MessagesPanel,
  TimelinePanel,
  attachmentFromUpload,
  ticketMatchesFilter,
  ticketMatchesSearch,
  type TicketFilter,
} from "./tickets-workflow";
import {
  requesterInvalidations,
  useRequesterConsentsQuery,
  useRequesterTicketDetailQuery,
  useRequesterTicketsQuery,
} from "../../features/requester/queries";
import type {
  AuthenticatedRequesterTicket,
  PublicTicketAttachment,
  RequesterConsent,
} from "../../features/requester/types";

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
      <TicketsListPanel
        filter={filter}
        filteredTickets={filteredTickets}
        isLoading={ticketsQuery.isLoading}
        search={search}
        selectedTicketId={ticketId}
        setFilter={setFilter}
        setSearch={setSearch}
      />
      <section className="min-w-0">
        {!ticketId ? (
          <div className="rounded-panel border border-slate-200 bg-white p-5 text-sm text-slate-600">Выберите обращение из списка.</div>
        ) : detailQuery.isLoading ? (
          <div className="rounded-panel border border-slate-200 bg-white p-5 text-sm text-slate-600">Загружаем обращение...</div>
        ) : selectedTicket ? (
          <div className="space-y-4">
            <TicketDetailHeader ticket={selectedTicket} />
            {notice ? <InlineAlert aria-live="polite" role="status">{notice}</InlineAlert> : null}
            <RequesterConsentList consents={pendingConsents} disabled={actionSubmitting} onDecision={decideConsent} />
            <MessagesPanel messages={detailQuery.data?.messages ?? []} />
            <TimelinePanel events={detailQuery.data?.events ?? []} />
            <TicketResolutionPanel
              actionSubmitting={actionSubmitting}
              canClose={canClose}
              canRate={canRate}
              canReopen={canReopen}
              closeTicket={closeTicket}
              feedbackComment={feedbackComment}
              feedbackProblemResolved={feedbackProblemResolved}
              feedbackRating={feedbackRating}
              feedbackReason={feedbackReason}
              reopenComment={reopenComment}
              reopenReason={reopenReason}
              reopenTicket={reopenTicket}
              setFeedbackComment={setFeedbackComment}
              setFeedbackProblemResolved={setFeedbackProblemResolved}
              setFeedbackRating={setFeedbackRating}
              setFeedbackReason={setFeedbackReason}
              setReopenComment={setReopenComment}
              setReopenReason={setReopenReason}
              submitFeedback={submitFeedback}
            />
            {canSendMessage ? (
              <TicketReplyComposer
                attachmentInputRef={attachmentInputRef}
                attachmentUploading={attachmentUploading}
                canAttachFiles={canAttachFiles}
                handleAttachmentUpload={handleAttachmentUpload}
                handleSendMessage={handleSendMessage}
                messageSending={messageSending}
                messageText={messageText}
                pendingAttachments={pendingAttachments}
                setMessageText={setMessageText}
              />
            ) : null}
          </div>
        ) : (
          <div className="rounded-panel border border-slate-200 bg-white p-5 text-sm text-slate-600">Обращение не найдено.</div>
        )}
      </section>
    </div>
  );
}
