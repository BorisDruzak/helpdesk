import { useQueryClient } from "@tanstack/react-query";
import type { ChangeEvent } from "react";
import { useRef, useState } from "react";
import { useChatUploads } from "../../components/use-chat-uploads";

import {
  approveRequesterConsent,
  closeRequesterTicket,
  denyRequesterConsent,
  reopenRequesterTicket,
  sendRequesterTicketMessage,
  submitRequesterTicketFeedback,
  uploadRequesterTicketAttachment,
} from "../../features/requester/api";
import { requesterErrorMessage } from "../../features/requester/labels";
import { attachmentFromUpload } from "./tickets-workflow";
import {
  requesterInvalidations,
  useRequesterConsentsQuery,
  useRequesterTicketDetailQuery,
} from "../../features/requester/queries";
import type {
  PublicTicketAttachment,
  RequesterConsent,
} from "../../features/requester/types";

export function useRequesterTicketChat(ticketId: string | undefined) {
  const queryClient = useQueryClient();
  const consentsQuery = useRequesterConsentsQuery();
  const detailQuery = useRequesterTicketDetailQuery(ticketId, { enabled: Boolean(ticketId) });
  const [messageText, setMessageText] = useState("");
  const [pendingAttachments, setPendingAttachments] = useState<Array<PublicTicketAttachment & { name: string }>>([]);
  const [messageSending, setMessageSending] = useState(false);
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

  const { uploading: attachmentUploading, addFiles: attachFiles } = useChatUploads({
    scope: selectedInternalTicketId ?? ticketId ?? null,
    enabled: canSendMessage && canAttachFiles && !messageSending,
    upload: (file) => uploadRequesterTicketAttachment(selectedInternalTicketId ?? ticketId!, file),
    onStart: () => setNotice(null), onError: setNotice,
    errorMessage: (error) => requesterErrorMessage(error, "Не удалось загрузить вложение"),
    onUploaded: (item, file) => setPendingAttachments(current => [...current, {...attachmentFromUpload(item), name: file.name || item.filename || "Вложение", mime_type: file.type || item.mime_type}]),
  });
  function handleAttachmentUpload(event: ChangeEvent<HTMLInputElement>) {
    attachFiles(Array.from(event.currentTarget.files ?? []));
    event.currentTarget.value = "";
  }
  function removePendingAttachment(id: string) {
    if (!messageSending) setPendingAttachments(current => current.filter(item => item.artifact_id !== id));
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
      setNotice(requesterErrorMessage(exc, "Не удалось сохранить решение", { domain: "consent" }));
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

  return {
    detailQuery,
    selectedTicket,
    notice,
    pendingConsents,
    actionSubmitting,
    decideConsent,
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
    reopenAvailable,
    feedbackId,
    setFeedbackComment,
    setFeedbackProblemResolved,
    setFeedbackRating,
    setFeedbackReason,
    setReopenComment,
    setReopenReason,
    submitFeedback,
    reopenTicket,
    canSendMessage,
    canAttachFiles,
    attachmentInputRef,
    attachmentUploading,
    handleAttachmentUpload,
    attachFiles,
    removePendingAttachment,
    handleSendMessage,
    messageSending,
    messageText,
    pendingAttachments,
    setMessageText
  };
}
