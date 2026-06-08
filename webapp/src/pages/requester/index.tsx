import { CheckCircle2, RefreshCw, RotateCcw, Send, Star } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";

import {
  closeRequesterTicket,
  createRequesterTicket,
  fetchRequesterBootstrap,
  fetchRequesterTicket,
  fetchRequesterTickets,
  reopenRequesterTicket,
  RequesterApiError,
  sendRequesterTicketMessage,
  submitRequesterTicketFeedback,
} from "../../features/requester/api";
import type {
  AuthenticatedRequesterTicket,
  RequesterBootstrap,
  RequesterDevice,
  RequesterTicketDetail,
} from "../../features/requester/types";

function deviceLabel(device: RequesterDevice): string {
  return device.hostname || device.asset_name || device.device_id;
}

function ticketStatus(ticket: AuthenticatedRequesterTicket): string {
  return ticket.requester_status_label || ticket.status_label || ticket.requester_status || ticket.status || "open";
}

export function RequesterWorkspacePage() {
  const [bootstrap, setBootstrap] = useState<RequesterBootstrap | null>(null);
  const [tickets, setTickets] = useState<AuthenticatedRequesterTicket[]>([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState("");
  const [title, setTitle] = useState("Проверка рабочего места");
  const [description, setDescription] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createdTicketId, setCreatedTicketId] = useState<string | null>(null);
  const [selectedTicketId, setSelectedTicketId] = useState<string | null>(null);
  const [selectedTicketDetail, setSelectedTicketDetail] = useState<RequesterTicketDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [messageText, setMessageText] = useState("");
  const [messageSending, setMessageSending] = useState(false);
  const [messageNotice, setMessageNotice] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [actionSubmitting, setActionSubmitting] = useState(false);
  const [feedbackRating, setFeedbackRating] = useState(5);
  const [feedbackProblemResolved, setFeedbackProblemResolved] = useState(true);
  const [feedbackReason, setFeedbackReason] = useState("not_resolved");
  const [feedbackComment, setFeedbackComment] = useState("");
  const [feedbackId, setFeedbackId] = useState<string | null>(null);
  const [reopenReason, setReopenReason] = useState("not_resolved");
  const [reopenComment, setReopenComment] = useState("");
  const [reopenAvailable, setReopenAvailable] = useState(false);

  const devices = bootstrap?.devices ?? [];
  const visibleTickets = tickets.length ? tickets : bootstrap?.recent_tickets ?? [];
  const profileName = bootstrap?.profile?.display_name || bootstrap?.profile?.full_name || bootstrap?.profile?.email || "Пользователь";

  const selectedDevice = useMemo(
    () => devices.find((device) => device.device_id === selectedDeviceId) ?? devices[0] ?? null,
    [devices, selectedDeviceId],
  );
  const selectedTicket = selectedTicketDetail?.ticket ?? null;
  const selectedTicketStatus = selectedTicket?.status ?? "";
  const canCloseSelectedTicket = selectedTicketStatus === "resolved";
  const canRateSelectedTicket = selectedTicketStatus === "resolved" || selectedTicketStatus === "closed";
  const canReopenSelectedTicket = canRateSelectedTicket && (reopenAvailable || feedbackRating <= 3 || !feedbackProblemResolved);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const nextBootstrap = await fetchRequesterBootstrap();
      const nextTickets = await fetchRequesterTickets();
      setBootstrap(nextBootstrap);
      setTickets(nextTickets);
      setSelectedDeviceId((current) => current || nextBootstrap.devices[0]?.device_id || "");
    } catch (exc) {
      setError(exc instanceof RequesterApiError ? exc.message : "Не удалось загрузить кабинет");
    } finally {
      setLoading(false);
    }
  }

  async function refreshSelectedTicket(ticketId: string) {
    const [nextDetail, nextTickets] = await Promise.all([
      fetchRequesterTicket(ticketId),
      fetchRequesterTickets(),
    ]);
    setSelectedTicketDetail(nextDetail);
    setTickets(nextTickets);
  }

  useEffect(() => {
    void load();
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedDevice || !description.trim()) {
      setError("Выберите устройство и заполните описание");
      return;
    }
    setSubmitting(true);
    setError(null);
    setCreatedTicketId(null);
    try {
      const result = await createRequesterTicket({
        device_id: selectedDevice.device_id,
        title,
        description,
        user_display_name: profileName,
        urgency: false,
        importance: false,
        urgency_reason: "Создано из кабинета заявителя",
        importance_reason: "Создано из кабинета заявителя",
      });
      setCreatedTicketId(result.ticket_id);
      setDescription("");
      setTickets(await fetchRequesterTickets());
    } catch (exc) {
      setError(exc instanceof RequesterApiError ? exc.message : "Не удалось создать обращение");
    } finally {
      setSubmitting(false);
    }
  }

  async function openTicket(ticketId: string) {
    setSelectedTicketId(ticketId);
    setSelectedTicketDetail(null);
    setDetailLoading(true);
    setMessageNotice(null);
    setActionNotice(null);
    setFeedbackId(null);
    setReopenAvailable(false);
    setError(null);
    try {
      setSelectedTicketDetail(await fetchRequesterTicket(ticketId));
    } catch (exc) {
      setError(exc instanceof RequesterApiError ? exc.message : "Не удалось загрузить обращение");
    } finally {
      setDetailLoading(false);
    }
  }

  async function handleMessageSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const ticketId = selectedTicketId;
    const text = messageText.trim();
    if (!ticketId || !text) {
      return;
    }
    setMessageSending(true);
    setMessageNotice(null);
    setError(null);
    try {
      await sendRequesterTicketMessage(ticketId, text);
      setMessageText("");
      setSelectedTicketDetail(await fetchRequesterTicket(ticketId));
      setMessageNotice("Сообщение отправлено");
    } catch (exc) {
      setError(exc instanceof RequesterApiError ? exc.message : "Не удалось отправить сообщение");
    } finally {
      setMessageSending(false);
    }
  }

  async function handleCloseSelectedTicket() {
    const ticketId = selectedTicketId;
    if (!ticketId) {
      return;
    }
    setActionSubmitting(true);
    setActionNotice(null);
    setError(null);
    try {
      await closeRequesterTicket(ticketId);
      await refreshSelectedTicket(ticketId);
      setActionNotice("Решение подтверждено, обращение закрыто");
    } catch (exc) {
      setError(exc instanceof RequesterApiError ? exc.message : "Не удалось закрыть обращение");
    } finally {
      setActionSubmitting(false);
    }
  }

  async function handleFeedbackSubmit() {
    const ticketId = selectedTicketId;
    if (!ticketId) {
      return;
    }
    setActionSubmitting(true);
    setActionNotice(null);
    setError(null);
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
      await refreshSelectedTicket(ticketId);
      setActionNotice(result.message || "Оценка сохранена");
    } catch (exc) {
      setError(exc instanceof RequesterApiError ? exc.message : "Не удалось сохранить оценку");
    } finally {
      setActionSubmitting(false);
    }
  }

  async function handleReopenSelectedTicket() {
    const ticketId = selectedTicketId;
    if (!ticketId) {
      return;
    }
    setActionSubmitting(true);
    setActionNotice(null);
    setError(null);
    try {
      await reopenRequesterTicket(ticketId, {
        reason_code: reopenReason,
        reason_comment: reopenComment.trim() || feedbackComment.trim() || null,
        linked_feedback_id: feedbackId,
      });
      await refreshSelectedTicket(ticketId);
      setActionNotice("Обращение вернулось в работу");
    } catch (exc) {
      setError(exc instanceof RequesterApiError ? exc.message : "Не удалось вернуть обращение в работу");
    } finally {
      setActionSubmitting(false);
    }
  }

  if (loading) {
    return <section className="workspace-page p-6 text-sm text-slate-500">Загружаем кабинет заявителя...</section>;
  }

  return (
    <section className="workspace-page space-y-5 p-6">
      <header className="workspace-page__header">
        <div className="workspace-page__copy">
          <p className="workspace-boot__eyebrow">Кабинет заявителя</p>
          <h1>Мои обращения</h1>
          <p>Профиль {profileName}. Доступны только устройства и обращения, связанные с вашей учетной записью.</p>
        </div>
        <dl className="workspace-page__stats">
          <div>
            <dt>Устройства</dt>
            <dd>{devices.length}</dd>
          </div>
          <div>
            <dt>Открытые</dt>
            <dd>{bootstrap?.open_ticket_count ?? visibleTickets.length}</dd>
          </div>
          <div>
            <dt>Действия</dt>
            <dd>{bootstrap?.tickets_requiring_user_action_count ?? 0}</dd>
          </div>
        </dl>
      </header>

      {error ? <div className="rounded-panel border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div> : null}
      {createdTicketId ? (
        <div className="rounded-panel border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          Создано обращение {createdTicketId}
        </div>
      ) : null}

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-5">
        <section className="support-workspace__panel">
          <div className="support-workspace__panel-head">
            <div>
              <p className="workspace-boot__eyebrow">Обращения</p>
              <h2 className="text-lg font-semibold text-slate-950">Последние заявки</h2>
            </div>
            <button className="inline-flex items-center gap-2 rounded-panel border px-3 py-2 text-sm font-semibold" onClick={() => void load()} type="button">
              <RefreshCw className="h-4 w-4" />
              Обновить
            </button>
          </div>
          <div className="mt-4 divide-y divide-slate-100">
            {visibleTickets.length ? (
              visibleTickets.map((ticket) => (
                <button
                  aria-label={`Open requester ticket ${ticket.ticket_id}`}
                  className={`block w-full py-3 text-left ${selectedTicketId === ticket.ticket_id ? "bg-slate-50" : ""}`}
                  key={ticket.ticket_id}
                  onClick={() => void openTicket(ticket.ticket_id)}
                  type="button"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold text-slate-950">{ticket.ticket_id}</span>
                    <span className="rounded-panel bg-slate-100 px-2 py-1 text-xs text-slate-600">{ticketStatus(ticket)}</span>
                  </div>
                  <h3 className="mt-1 text-sm font-semibold text-slate-800">{ticket.title || "Без темы"}</h3>
                  <p className="mt-1 line-clamp-2 text-sm text-slate-500">{ticket.description || "Описание не указано"}</p>
                </button>
              ))
            ) : (
              <p className="py-6 text-sm text-slate-500">Обращений пока нет.</p>
            )}
          </div>
        </section>

          {selectedTicketId ? (
            <section className="support-workspace__panel">
              <div className="support-workspace__panel-head">
                <div>
                  <p className="workspace-boot__eyebrow">Диалог</p>
                  <h2 className="text-lg font-semibold text-slate-950">
                    {selectedTicketDetail?.ticket.title || selectedTicketId}
                  </h2>
                  <p className="mt-1 text-sm text-slate-500">
                    {selectedTicketDetail?.ticket.description || (detailLoading ? "Загружаем обращение..." : "Описание не указано")}
                  </p>
                </div>
              </div>

              <div className="mt-4 space-y-3">
                {detailLoading ? (
                  <p className="text-sm text-slate-500">Загружаем историю...</p>
                ) : selectedTicketDetail?.messages?.length ? (
                  selectedTicketDetail.messages.map((message) => (
                    <div className="rounded-panel border border-slate-200 p-3" key={message.message_id || message.event_id || message.ts}>
                      <div className="flex items-center justify-between gap-3 text-xs text-slate-500">
                        <span>{message.from_role === "support" ? "Поддержка" : "Заявитель"}</span>
                        <span>{message.ts || message.created_at || ""}</span>
                      </div>
                      <p className="mt-1 whitespace-pre-wrap text-sm text-slate-800">{message.text || ""}</p>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-slate-500">Сообщений пока нет.</p>
                )}
              </div>

              {selectedTicket ? (
                <div className="mt-4 grid gap-3 rounded-panel border border-slate-200 bg-slate-50 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-slate-900">Действия по обращению</p>
                      <p className="text-xs text-slate-500">
                        Статус: {selectedTicket.requester_status_label || selectedTicket.status_label || selectedTicket.status}
                      </p>
                    </div>
                    {canCloseSelectedTicket ? (
                      <button
                        aria-label="Close requester ticket"
                        className="inline-flex items-center justify-center gap-2 rounded-panel bg-emerald-700 px-3 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300"
                        disabled={actionSubmitting}
                        onClick={() => void handleCloseSelectedTicket()}
                        type="button"
                      >
                        <CheckCircle2 className="h-4 w-4" />
                        Подтвердить и закрыть
                      </button>
                    ) : null}
                  </div>

                  {canRateSelectedTicket ? (
                    <div className="grid gap-3 border-t border-slate-200 pt-3">
                      <div className="grid gap-3 sm:grid-cols-2">
                        <label className="block text-sm font-semibold text-slate-700">
                          Оценка
                          <select
                            aria-label="Requester feedback rating"
                            className="mt-1 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
                            onChange={(event) => setFeedbackRating(Number(event.target.value))}
                            value={feedbackRating}
                          >
                            {[5, 4, 3, 2, 1].map((value) => (
                              <option key={value} value={value}>
                                {value}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label className="flex items-center gap-2 self-end text-sm font-semibold text-slate-700">
                          <input
                            aria-label="Requester problem resolved"
                            checked={feedbackProblemResolved}
                            onChange={(event) => {
                              setFeedbackProblemResolved(event.target.checked);
                              if (!event.target.checked) {
                                setReopenAvailable(true);
                              }
                            }}
                            type="checkbox"
                          />
                          Проблема решена
                        </label>
                      </div>
                      {feedbackRating <= 3 || !feedbackProblemResolved ? (
                        <label className="block text-sm font-semibold text-slate-700">
                          Причина
                          <select
                            className="mt-1 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
                            onChange={(event) => {
                              setFeedbackReason(event.target.value);
                              setReopenReason(event.target.value);
                            }}
                            value={feedbackReason}
                          >
                            <option value="not_resolved">Не решено</option>
                            <option value="problem_returned">Проблема вернулась</option>
                            <option value="slow_resolution">Долгое решение</option>
                            <option value="poor_communication">Недостаточно коммуникации</option>
                            <option value="other">Другое</option>
                          </select>
                        </label>
                      ) : null}
                      <label className="block text-sm font-semibold text-slate-700">
                        Комментарий
                        <textarea
                          className="mt-1 min-h-20 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
                          onChange={(event) => setFeedbackComment(event.target.value)}
                          value={feedbackComment}
                        />
                      </label>
                      <div className="flex flex-wrap gap-2">
                        <button
                          aria-label="Submit requester feedback"
                          className="inline-flex items-center justify-center gap-2 rounded-panel border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-800 disabled:cursor-not-allowed disabled:bg-slate-100"
                          disabled={actionSubmitting || (feedbackReason === "other" && !feedbackComment.trim())}
                          onClick={() => void handleFeedbackSubmit()}
                          type="button"
                        >
                          <Star className="h-4 w-4" />
                          Отправить оценку
                        </button>
                        {canReopenSelectedTicket ? (
                          <button
                            aria-label="Reopen requester ticket"
                            className="inline-flex items-center justify-center gap-2 rounded-panel border border-amber-300 bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-900 disabled:cursor-not-allowed disabled:bg-slate-100"
                            disabled={actionSubmitting || (reopenReason === "other" && !reopenComment.trim() && !feedbackComment.trim())}
                            onClick={() => void handleReopenSelectedTicket()}
                            type="button"
                          >
                            <RotateCcw className="h-4 w-4" />
                            Вернуть в работу
                          </button>
                        ) : null}
                      </div>
                      {canReopenSelectedTicket ? (
                        <label className="block text-sm font-semibold text-slate-700">
                          Комментарий для повторного открытия
                          <textarea
                            className="mt-1 min-h-16 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
                            onChange={(event) => setReopenComment(event.target.value)}
                            value={reopenComment}
                          />
                        </label>
                      ) : null}
                    </div>
                  ) : null}
                  {actionNotice ? <p className="text-sm text-emerald-700">{actionNotice}</p> : null}
                </div>
              ) : null}

              <form className="mt-4 space-y-3" onSubmit={(event) => void handleMessageSubmit(event)}>
                <label className="block text-sm font-semibold text-slate-700">
                  Ответ
                  <textarea
                    aria-label="Requester message"
                    className="mt-1 min-h-24 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
                    onChange={(event) => setMessageText(event.target.value)}
                    value={messageText}
                  />
                </label>
                {messageNotice ? <p className="text-sm text-emerald-700">{messageNotice}</p> : null}
                <button
                  aria-label="Send requester message"
                  className="inline-flex items-center justify-center gap-2 rounded-panel bg-brand-700 px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300"
                  disabled={messageSending || !selectedTicketId || !messageText.trim()}
                  type="submit"
                >
                  <Send className="h-4 w-4" />
                  {messageSending ? "Отправляем..." : "Отправить"}
                </button>
              </form>
            </section>
          ) : null}
        </div>

        <aside className="space-y-5">
          <section className="support-workspace__panel">
            <div className="support-workspace__panel-head">
              <div>
                <p className="workspace-boot__eyebrow">Устройства</p>
                <h2 className="text-lg font-semibold text-slate-950">Мои устройства</h2>
              </div>
            </div>
            <div className="mt-4 space-y-2">
              {devices.length ? (
                devices.map((device) => (
                  <label className="flex cursor-pointer items-start gap-3 rounded-panel border border-slate-200 p-3 text-sm" key={device.device_id}>
                    <input
                      checked={(selectedDevice?.device_id ?? "") === device.device_id}
                      className="mt-1"
                      name="requester-device"
                      onChange={() => setSelectedDeviceId(device.device_id)}
                      type="radio"
                    />
                    <span>
                      <span className="block font-semibold text-slate-900">{deviceLabel(device)}</span>
                      <span className="block text-xs text-slate-500">{device.os || "OS не указан"} · agent {device.agent_version || "unknown"}</span>
                    </span>
                  </label>
                ))
              ) : (
                <p className="text-sm text-slate-500">Зарегистрированных устройств пока нет.</p>
              )}
            </div>
          </section>

          <form className="support-workspace__panel space-y-3" onSubmit={(event) => void handleSubmit(event)}>
            <div className="support-workspace__panel-head">
              <div>
                <p className="workspace-boot__eyebrow">Новая заявка</p>
                <h2 className="text-lg font-semibold text-slate-950">Создать обращение</h2>
              </div>
            </div>
            <label className="block text-sm font-semibold text-slate-700">
              Тема
              <input className="mt-1 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal" onChange={(event) => setTitle(event.target.value)} value={title} />
            </label>
            <label className="block text-sm font-semibold text-slate-700">
              Описание
              <textarea
                className="mt-1 min-h-32 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
                onChange={(event) => setDescription(event.target.value)}
                value={description}
              />
            </label>
            <button
              className="inline-flex w-full items-center justify-center gap-2 rounded-panel bg-brand-700 px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300"
              disabled={submitting || !selectedDevice || !description.trim()}
              type="submit"
            >
              <Send className="h-4 w-4" />
              {submitting ? "Создаем..." : "Создать обращение"}
            </button>
          </form>
        </aside>
      </div>
    </section>
  );
}
