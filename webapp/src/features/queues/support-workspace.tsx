import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { startTransition, useDeferredValue, useEffect, useRef, useState } from "react";

import {
  fetchSupportBootstrap,
  fetchSupportQueue,
  fetchSupportTicketDetail,
  fetchSupportTicketTools,
  postSupportTicketMessage,
  postSupportTicketStatus,
  postSupportTicketToolRun,
  type SupportQueuePayload,
  type SupportQueueScope,
  type SupportTicketDetailPayload,
  type SupportTicketToolsPayload,
} from "./api";
import { getSharedWebRealtimeClient } from "../../shared/realtime/client";


const DATE_TIME_FORMATTER = new Intl.DateTimeFormat("ru-RU", {
  day: "2-digit",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
});

const SUPPORT_QUEUE_REFRESH_MS = 15_000;

function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return "—";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return DATE_TIME_FORMATTER.format(date);
}

function timelineEventLabel(entry: SupportTicketDetailPayload["timeline"][number]) {
  if (entry.event_type === "tool_call_started") {
    return "Инструмент поставлен в очередь";
  }
  if (entry.event_type === "tool_call_result") {
    return entry.tool_status === "success" ? "Инструмент завершён" : "Результат инструмента";
  }
  if (entry.visibility === "internal") {
    return "Внутренняя заметка";
  }
  if (entry.visibility === "system") {
    return "Системное событие";
  }
  return "Публичное сообщение";
}

function formatToolFieldValue(value: unknown, fieldType: string) {
  if (value == null) {
    return "";
  }
  if (fieldType === "object" || fieldType === "array") {
    try {
      return JSON.stringify(value, null, 2);
    } catch {
      return String(value);
    }
  }
  if (typeof value === "boolean") {
    return value ? "true" : "false";
  }
  return String(value);
}

function describeQueueScope(scope: SupportQueueScope) {
  return scope === "mine" ? "мои тикеты" : "все доступные";
}

function describePresence(value: boolean) {
  return value ? "онлайн" : "офлайн";
}

function describeToolRiskLevel(value: string) {
  if (value === "safe_read") {
    return "Safe read";
  }
  if (value === "confirmation_required") {
    return "Требует подтверждение";
  }
  return value;
}

function SupportQueuePanel({
  queue,
  queueStatus,
  selectedTicketId,
  onSelectTicket,
  onScopeChange,
  onStatusChange,
  onQueryChange,
  scope,
  statusFilter,
  query,
}: {
  queue?: SupportQueuePayload;
  queueStatus: "loading" | "error" | "ready";
  selectedTicketId: string | null;
  onSelectTicket: (ticketId: string) => void;
  onScopeChange: (scope: SupportQueueScope) => void;
  onStatusChange: (status: string) => void;
  onQueryChange: (query: string) => void;
  scope: SupportQueueScope;
  statusFilter: string;
  query: string;
}) {
  return (
    <section className="support-workspace__panel support-workspace__panel--queue">
      <div className="support-workspace__panel-head">
        <div>
          <p className="workspace-boot__eyebrow">Очередь</p>
          <h2>Очередь и фильтры</h2>
          <p>Рабочий список тикетов, фильтры и быстрый поиск по текущему typed boundary.</p>
        </div>
      </div>

      <div className="support-queue-toolbar">
        <div className="support-filter-group" role="group" aria-label="Область видимости очереди">
          {(queue?.filters.scope_options ?? []).map((option) => (
            <button
              className={`support-chip${scope === option.value ? " active" : ""}`}
              key={option.value}
              onClick={() => onScopeChange(option.value as SupportQueueScope)}
              type="button"
            >
              {option.label}
            </button>
          ))}
        </div>

        <label className="support-filter-search">
          <span>Поиск</span>
          <input
            onChange={(event) => onQueryChange(event.target.value)}
            placeholder="Код, тема, инициатор, устройство"
            type="search"
            value={query}
          />
        </label>

        <label className="support-filter-select">
          <span>Статус</span>
          <select onChange={(event) => onStatusChange(event.target.value)} value={statusFilter}>
            {(queue?.filters.status_options ?? []).map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="support-queue-summary">
        <span>Видимых тикетов: {queue?.summary.visible_count ?? 0}</span>
        <span>Режим: {describeQueueScope(scope)}</span>
        <span>Автообновление: 15 сек</span>
      </div>

      {queueStatus === "loading" ? (
        <div className="support-queue-empty">Загружаем очередь поддержки…</div>
      ) : null}

      {queueStatus === "error" ? (
        <div className="support-queue-empty">Не удалось загрузить новую очередь поддержки.</div>
      ) : null}

      {queueStatus === "ready" && queue && queue.tickets.length === 0 ? (
        <div className="support-queue-empty">По текущим фильтрам тикеты не найдены.</div>
      ) : null}

      {queueStatus === "ready" && queue && queue.tickets.length > 0 ? (
        <div className="support-ticket-list">
          {queue.tickets.map((ticket) => (
            <button
              aria-pressed={selectedTicketId === ticket.ticket_id}
              className={`support-ticket-card${selectedTicketId === ticket.ticket_id ? " active" : ""}`}
              key={ticket.ticket_id}
              onClick={() => onSelectTicket(ticket.ticket_id)}
              type="button"
            >
              <div className="support-ticket-card__head">
                <span className="support-ticket-card__code">{ticket.ticket_code ?? ticket.ticket_id}</span>
                <span className="support-ticket-card__status">{ticket.status_label}</span>
              </div>
              <strong>{ticket.title}</strong>
              <p>{ticket.requester_display_name ?? "Инициатор не указан"}</p>
              <div className="support-ticket-card__meta">
                <span>{ticket.queue_code ?? "Без очереди"}</span>
                <span>Ход: {ticket.next_action_owner ?? "support"}</span>
                <span>{ticket.requester_status_label}</span>
                <span>{formatDateTime(ticket.updated_at ?? ticket.created_at)}</span>
                <span>{ticket.unread_user_messages > 0 ? `${ticket.unread_user_messages} непрочит.` : "без новых"}</span>
              </div>
            </button>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function SupportDetailPanel({
  ticketDetail,
  tools,
  isLoading,
  errorMessage,
  observerDrawerTab,
  onSendMessage,
  onApplyStatus,
  onRunTool,
  sendPending,
  statusPending,
  toolsLoading,
  toolsErrorMessage,
  toolPending,
  toolActionMessage,
}: {
  ticketDetail?: SupportTicketDetailPayload;
  tools?: SupportTicketToolsPayload;
  isLoading: boolean;
  errorMessage?: string;
  observerDrawerTab: string;
  onSendMessage: (text: string) => Promise<void>;
  onApplyStatus: (toStatus: string) => Promise<void>;
  onRunTool: (payload: {
    toolName: string;
    presetId: string | null;
    params: Record<string, unknown>;
  }) => Promise<void>;
  sendPending: boolean;
  statusPending: boolean;
  toolsLoading: boolean;
  toolsErrorMessage?: string;
  toolPending: boolean;
  toolActionMessage?: string | null;
}) {
  const [replyText, setReplyText] = useState("");
  const [composerError, setComposerError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [toolError, setToolError] = useState<string | null>(null);
  const [selectedToolName, setSelectedToolName] = useState<string | null>(null);
  const [selectedPresetId, setSelectedPresetId] = useState("");
  const [toolParams, setToolParams] = useState<Record<string, string>>({});

  useEffect(() => {
    setComposerError(null);
    setActionError(null);
    setToolError(null);
  }, [ticketDetail?.ticket.ticket_id]);

  useEffect(() => {
    const toolList = tools?.tools ?? [];
    const currentToolStillVisible = selectedToolName && toolList.some((tool) => tool.tool_name === selectedToolName);
    if (currentToolStillVisible) {
      return;
    }
    setSelectedToolName(toolList[0]?.tool_name ?? null);
    setSelectedPresetId("");
    setToolParams({});
  }, [selectedToolName, tools?.tools]);

  const timeline = ticketDetail?.timeline ?? [];
  const statusOptions = ticketDetail?.actions?.status_options ?? [];
  const snapshot = ticketDetail?.snapshot;
  const selectedTool = tools?.tools.find((tool) => tool.tool_name === selectedToolName) ?? null;

  async function handleSubmitMessage() {
    const trimmed = replyText.trim();
    if (!trimmed) {
      setComposerError("Введите ответ, прежде чем отправлять сообщение.");
      return;
    }

    setComposerError(null);
    try {
      await onSendMessage(trimmed);
      setReplyText("");
    } catch (error) {
      setComposerError(error instanceof Error ? error.message : "Не удалось отправить сообщение.");
    }
  }

  async function handleApplyStatus(value: string) {
    setActionError(null);
    try {
      await onApplyStatus(value);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Не удалось обновить статус.");
    }
  }

  function parseToolParams() {
    if (!selectedTool) {
      throw new Error("Выберите инструмент из списка.");
    }
    if (selectedPresetId.trim()) {
      const preset = selectedTool.presets.find((item) => item.preset_id === selectedPresetId.trim());
      return {
        presetId: selectedPresetId.trim(),
        params: preset?.params ?? {},
      };
    }

    const params: Record<string, unknown> = {};
    for (const field of selectedTool.params_schema) {
      const rawValue = toolParams[field.name] ?? formatToolFieldValue(field.default, field.type);
      const trimmedValue = rawValue.trim();
      if (!trimmedValue) {
        if (field.required) {
          throw new Error(`Заполните поле «${field.label ?? field.name}».`);
        }
        continue;
      }

      if (field.type === "boolean") {
        params[field.name] = trimmedValue === "true";
        continue;
      }
      if (field.type === "integer") {
        params[field.name] = Number.parseInt(trimmedValue, 10);
        continue;
      }
      if (field.type === "number") {
        params[field.name] = Number.parseFloat(trimmedValue);
        continue;
      }
      if (field.type === "object" || field.type === "array") {
        try {
          params[field.name] = JSON.parse(trimmedValue);
        } catch {
          throw new Error(`Поле «${field.label ?? field.name}» должно содержать валидный JSON.`);
        }
        continue;
      }
      params[field.name] = trimmedValue;
    }

    return {
      presetId: null,
      params,
    };
  }

  async function handleRunTool() {
    if (!selectedTool) {
      setToolError("Выберите инструмент из списка.");
      return;
    }

    setToolError(null);
    try {
      const payload = parseToolParams();
      await onRunTool({
        toolName: selectedTool.tool_name,
        presetId: payload.presetId,
        params: payload.params,
      });
    } catch (error) {
      setToolError(error instanceof Error ? error.message : "Не удалось запустить инструмент.");
    }
  }

  if (!ticketDetail && !isLoading && !errorMessage) {
    return (
      <aside className="support-workspace__panel support-workspace__panel--detail">
        <div className="support-workspace__panel-head">
          <div>
            <p className="workspace-boot__eyebrow">Тикет</p>
            <h2>Карточка и рабочая лента</h2>
          </div>
        </div>
        <div className="support-ticket-empty">Выберите тикет в очереди, чтобы открыть карточку.</div>
      </aside>
    );
  }

  if (!ticketDetail && isLoading) {
    return (
      <aside className="support-workspace__panel support-workspace__panel--detail">
        <div className="support-workspace__panel-head">
          <div>
            <p className="workspace-boot__eyebrow">Тикет</p>
            <h2>Карточка и рабочая лента</h2>
          </div>
        </div>
        <div className="support-ticket-empty">Загружаем карточку тикета…</div>
      </aside>
    );
  }

  if (!ticketDetail && errorMessage) {
    return (
      <aside className="support-workspace__panel support-workspace__panel--detail">
        <div className="support-workspace__panel-head">
          <div>
            <p className="workspace-boot__eyebrow">Тикет</p>
            <h2>Карточка и рабочая лента</h2>
          </div>
        </div>
        <div className="support-ticket-empty">{errorMessage}</div>
      </aside>
    );
  }

  if (!ticketDetail) {
    return null;
  }

  return (
    <aside className="support-workspace__panel support-workspace__panel--detail">
      <div className="support-ticket-layout">
        <header className="support-ticket-layout__header">
          <div className="support-ticket-layout__title">
            <p className="support-ticket-detail__code">{ticketDetail.ticket.ticket_code ?? ticketDetail.ticket.ticket_id}</p>
            <h2>{ticketDetail.ticket.title}</h2>
            <div className="support-ticket-layout__meta">
              <span>Создан: {formatDateTime(ticketDetail.ticket.created_at)}</span>
              <span>Клиент: {ticketDetail.ticket.requester_display_name ?? "не указан"}</span>
              <span>Обновлён: {formatDateTime(ticketDetail.ticket.updated_at)}</span>
            </div>
          </div>

          <div className="support-ticket-layout__actions">
            <div className="support-ticket-layout__status-pill">{ticketDetail.ticket.status_label}</div>
            <div className="support-ticket-layout__status-pill">{ticketDetail.ticket.requester_status_label}</div>
            {statusOptions.length ? (
              <div className="support-status-actions">
                {statusOptions.map((option) => (
                  <button
                    className="support-status-action"
                    disabled={statusPending}
                    key={option.value}
                    onClick={() => void handleApplyStatus(option.value)}
                    type="button"
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            ) : null}
          </div>
        </header>

        <nav className="support-ticket-layout__tabs" aria-label="Разделы тикета">
          <a className="support-ticket-layout__tab support-ticket-layout__tab--active" href="#support-dialog">
            Диалог
          </a>
          <a className="support-ticket-layout__tab" href="#support-context">
            Информация
          </a>
          <a className="support-ticket-layout__tab" href="#support-tools">
            Инструменты
          </a>
          <a className="support-ticket-layout__tab" href="#support-observer">
            {observerDrawerTab}
          </a>
        </nav>

        {actionError ? <p className="support-detail-error">{actionError}</p> : null}

        <div className="support-ticket-layout__workspace">
          <div className="support-ticket-layout__main">
            <section className="support-ticket-detail__block" id="support-dialog">
              <div className="support-ticket-detail__section-head">
                <h4>Диалог</h4>
                <span>Последние сообщения и системные события по тикету</span>
              </div>

              {timeline.length === 0 ? (
                <div className="support-ticket-empty support-ticket-empty--inline">В ленте пока нет сообщений.</div>
              ) : (
                <div className="support-timeline">
                  {timeline.map((message) => (
                    <article
                      className={`support-timeline__message${message.event_type !== "chat_message" ? " support-timeline__message--system" : ""}`}
                      key={message.message_id ?? String(message.event_id)}
                    >
                      <div className="support-timeline__meta">
                        <strong>{message.sender_display_name ?? message.from_role}</strong>
                        <span>{timelineEventLabel(message)}</span>
                        <span>{formatDateTime(message.ts)}</span>
                      </div>
                      <p>{message.text}</p>
                      {message.result_summary ? <p className="support-timeline__result">{message.result_summary}</p> : null}
                      {message.result_preview ? <code className="support-timeline__preview">{message.result_preview}</code> : null}
                    </article>
                  ))}
                </div>
              )}

              <div className="support-composer">
                <div className="support-composer__tabs">
                  <button className="support-composer__tab support-composer__tab--active" type="button">
                    Ответить
                  </button>
                  <button className="support-composer__tab" disabled type="button">
                    Внутренний комментарий
                  </button>
                </div>
                <label className="support-composer__field">
                  <span>Ответ оператору</span>
                  <textarea
                    aria-label="Ответ оператору"
                    onChange={(event) => setReplyText(event.target.value)}
                    placeholder="Напишите обновление по тикету, чтобы оно сразу попало в ленту."
                    value={replyText}
                  />
                </label>
                <div className="support-composer__actions">
                  <button
                    className="support-composer__submit"
                    disabled={sendPending}
                    onClick={() => void handleSubmitMessage()}
                    type="button"
                  >
                    {sendPending ? "Отправляем…" : "Отправить ответ"}
                  </button>
                </div>
                {composerError ? <p className="support-detail-error">{composerError}</p> : null}
              </div>
            </section>

            <section className="support-ticket-detail__block" id="support-tools">
              <div className="support-ticket-detail__section-head">
                <h4>Инструменты и запуск</h4>
                <span>Typed запуск инструментов без перехода в legacy</span>
              </div>

              {toolsLoading ? (
                <div className="support-detail-note">Загружаем доступные инструменты…</div>
              ) : null}
              {toolsErrorMessage ? <div className="support-detail-error">{toolsErrorMessage}</div> : null}

              {!toolsLoading && !toolsErrorMessage && (tools?.tools.length ?? 0) === 0 ? (
                <div className="support-ticket-empty support-ticket-empty--inline">
                  Для текущего тикета пока нет доступных инструментов.
                </div>
              ) : null}

              {(tools?.tools.length ?? 0) > 0 ? (
                <div className="support-tools-grid">
                  <div className="support-tools-list">
                    {tools?.tools.map((tool) => (
                      <button
                        className={`support-tool-card${selectedTool?.tool_name === tool.tool_name ? " active" : ""}`}
                        key={tool.tool_name}
                        onClick={() => {
                          setToolError(null);
                          setSelectedToolName(tool.tool_name);
                          setSelectedPresetId("");
                          setToolParams({});
                        }}
                        type="button"
                      >
                        <strong>{tool.tool_name}</strong>
                        <p>{tool.description ?? "Описание инструмента не передано"}</p>
                        <div className="support-tool-card__meta">
                          <span>{describeToolRiskLevel(tool.risk_level)}</span>
                          <span>{tool.source}</span>
                          {tool.requires_consent ? <span>consent</span> : null}
                        </div>
                      </button>
                    ))}
                  </div>

                  <div className="support-tool-inspector">
                    {selectedTool ? (
                      <>
                        <div className="support-tool-inspector__head">
                          <h5>{selectedTool.tool_name}</h5>
                          <p>{selectedTool.description ?? "Описание инструмента не передано."}</p>
                        </div>

                        <div className="support-tool-inspector__badges">
                          <span>{selectedTool.module_name ?? "builtin"}</span>
                          <span>{describeToolRiskLevel(selectedTool.risk_level)}</span>
                          <span>{selectedTool.source}</span>
                          {selectedTool.install_required ? <span>install required</span> : null}
                        </div>

                        {selectedTool.presets.length ? (
                          <label className="support-tool-field">
                            <span>Preset</span>
                            <select
                              aria-label="Preset"
                              onChange={(event) => {
                                const value = event.target.value;
                                setSelectedPresetId(value);
                                const preset = selectedTool.presets.find((item) => item.preset_id === value);
                                setToolParams(
                                  preset?.params
                                    ? Object.fromEntries(
                                        Object.entries(preset.params).map(([key, paramValue]) => [
                                          key,
                                          typeof paramValue === "object"
                                            ? JSON.stringify(paramValue, null, 2)
                                            : String(paramValue),
                                        ])
                                      )
                                    : {}
                                );
                              }}
                              value={selectedPresetId}
                            >
                              <option value="">Без preset, задать параметры вручную</option>
                              {selectedTool.presets.map((preset) => (
                                <option key={preset.preset_id} value={preset.preset_id}>
                                  {preset.label}
                                </option>
                              ))}
                            </select>
                          </label>
                        ) : null}

                        {!selectedPresetId ? (
                          <div className="support-tool-fields">
                            {selectedTool.params_schema.map((field) => {
                              const fieldValue = toolParams[field.name] ?? formatToolFieldValue(field.default, field.type);
                              if (field.type === "boolean") {
                                return (
                                  <label className="support-tool-field" key={field.name}>
                                    <span>{field.label ?? field.name}</span>
                                    <select
                                      aria-label={field.label ?? field.name}
                                      onChange={(event) =>
                                        setToolParams((current) => ({ ...current, [field.name]: event.target.value }))
                                      }
                                      value={fieldValue || "false"}
                                    >
                                      <option value="false">false</option>
                                      <option value="true">true</option>
                                    </select>
                                    {field.description ? <small>{field.description}</small> : null}
                                  </label>
                                );
                              }

                              const multiline = field.type === "object" || field.type === "array";
                              return (
                                <label className="support-tool-field" key={field.name}>
                                  <span>{field.label ?? field.name}</span>
                                  {multiline ? (
                                    <textarea
                                      aria-label={field.label ?? field.name}
                                      onChange={(event) =>
                                        setToolParams((current) => ({ ...current, [field.name]: event.target.value }))
                                      }
                                      value={fieldValue}
                                    />
                                  ) : (
                                    <input
                                      aria-label={field.label ?? field.name}
                                      onChange={(event) =>
                                        setToolParams((current) => ({ ...current, [field.name]: event.target.value }))
                                      }
                                      type={field.type === "integer" || field.type === "number" ? "number" : "text"}
                                      value={fieldValue}
                                    />
                                  )}
                                  {field.description ? <small>{field.description}</small> : null}
                                </label>
                              );
                            })}
                          </div>
                        ) : null}

                        <div className="support-tool-inspector__actions">
                          <button
                            className="support-composer__submit"
                            disabled={toolPending}
                            onClick={() => void handleRunTool()}
                            type="button"
                          >
                            {toolPending ? "Запускаем…" : "Запустить инструмент"}
                          </button>
                        </div>
                      </>
                    ) : (
                      <p className="support-tool-inspector__empty">Выберите инструмент слева, чтобы открыть параметры запуска.</p>
                    )}
                  </div>
                </div>
              ) : null}

              {toolActionMessage ? <p className="support-detail-note">{toolActionMessage}</p> : null}
              {toolError ? <p className="support-detail-error">{toolError}</p> : null}
            </section>
          </div>

          <div className="support-ticket-layout__aside">
            <section className="support-ticket-detail__block" id="support-context">
              <div className="support-ticket-detail__section-head">
                <h4>Информация о тикете</h4>
                <span>{ticketDetail.ticket.queue.name ?? ticketDetail.ticket.queue.code ?? "Без очереди"}</span>
              </div>
              <div className="support-ticket-detail__facts support-ticket-detail__facts--stacked">
                <div>
                  <dt>ID</dt>
                  <dd>{ticketDetail.ticket.ticket_code ?? ticketDetail.ticket.ticket_id}</dd>
                </div>
                <div>
                  <dt>Статус</dt>
                  <dd>{ticketDetail.ticket.status_label}</dd>
                </div>
                <div>
                  <dt>Статус для пользователя</dt>
                  <dd>{ticketDetail.ticket.requester_status_label}</dd>
                </div>
                <div>
                  <dt>Чей ход</dt>
                  <dd>{ticketDetail.ticket.next_action_owner ?? "support"}</dd>
                </div>
                <div>
                  <dt>Причина ожидания</dt>
                  <dd>{ticketDetail.ticket.status_reason ?? "не указана"}</dd>
                </div>
                <div>
                  <dt>Следующий срок</dt>
                  <dd>{formatDateTime(ticketDetail.ticket.next_action_due_at)}</dd>
                </div>
                <div>
                  <dt>Инициатор</dt>
                  <dd>{ticketDetail.ticket.requester_display_name ?? "не указан"}</dd>
                </div>
                <div>
                  <dt>Ответственный</dt>
                  <dd>{ticketDetail.ticket.assignee_id ?? "не назначен"}</dd>
                </div>
                <div>
                  <dt>Устройство</dt>
                  <dd>{ticketDetail.ticket.device_id ?? "не привязано"}</dd>
                </div>
                <div>
                  <dt>Состав очереди</dt>
                  <dd>
                    {ticketDetail.ticket.queue_members.length > 0
                      ? ticketDetail.ticket.queue_members
                          .map((member) => (member.role_in_queue ? `${member.actor_id} (${member.role_in_queue})` : member.actor_id))
                          .join(", ")
                      : "состав очереди не передан"}
                  </dd>
                </div>
              </div>
              <div className="support-ticket-layout__description">
                <strong>Описание</strong>
                <p>{ticketDetail.ticket.description ?? "Описание пока не заполнено."}</p>
              </div>
            </section>

            {ticketDetail.request_form ? (
              <section className="support-ticket-detail__block" id="support-request-form">
                <div className="support-ticket-detail__section-head">
                  <h4>Данные формы</h4>
                  <span>{ticketDetail.request_form.form_title ?? ticketDetail.request_form.form_key ?? "структурированный ввод"}</span>
                </div>
                <div className="support-ticket-detail__facts support-ticket-detail__facts--stacked">
                  <div>
                    <dt>request_kind</dt>
                    <dd>{ticketDetail.request_form.request_kind ?? "не указан"}</dd>
                  </div>
                  <div>
                    <dt>Ключ формы</dt>
                    <dd>{ticketDetail.request_form.form_key ?? "не указан"}</dd>
                  </div>
                </div>
                {ticketDetail.request_form.rows.length > 0 ? (
                  <div className="support-ticket-layout__description">
                    <strong>Нормализованные ответы</strong>
                    <dl className="support-ticket-detail__facts support-ticket-detail__facts--stacked">
                      {ticketDetail.request_form.rows.map((row) => (
                        <div key={row.key}>
                          <dt>{row.label}</dt>
                          <dd>{row.value}</dd>
                        </div>
                      ))}
                    </dl>
                  </div>
                ) : null}
              </section>
            ) : null}

            <section className="support-ticket-detail__block" id="support-observer">
              <div className="support-ticket-detail__section-head">
                <h4>Observer</h4>
                <span>tab: {observerDrawerTab}</span>
              </div>
              <div className="support-ticket-detail__observer-grid">
                <article>
                  <span>Трасс всего</span>
                  <strong>{ticketDetail.observer.summary.trace_count}</strong>
                </article>
                <article>
                  <span>Активных</span>
                  <strong>{ticketDetail.observer.summary.active_trace_count}</strong>
                </article>
                <article>
                  <span>С ошибками</span>
                  <strong>{ticketDetail.observer.summary.error_trace_count}</strong>
                </article>
                <article>
                  <span>Сигнатур</span>
                  <strong>{ticketDetail.observer.summary.signature_count}</strong>
                </article>
              </div>
              <div className="support-ticket-detail__observer-meta">
                <div>
                  <span>Root trace</span>
                  <code>{ticketDetail.observer.summary.root_trace_id ?? "ещё не назначен"}</code>
                </div>
                <div>
                  <span>Последняя trace</span>
                  <strong>{formatDateTime(ticketDetail.observer.summary.latest_trace_at)}</strong>
                </div>
              </div>
              <div className="support-ticket-detail__observer-endpoint">
                <span>Endpoint сводки по тикету</span>
                <code>{ticketDetail.observer.ticket_summary_endpoint}</code>
              </div>
            </section>

            <section className="support-ticket-detail__block">
              <div className="support-ticket-detail__section-head">
                <h4>Информация об устройстве</h4>
                <span>presence и последние операции</span>
              </div>
              <div className="support-snapshot-grid support-snapshot-grid--compact">
                <article className="support-snapshot-card">
                  <span>Presence</span>
                  <strong>{snapshot?.presence.agent_online ? "Агент онлайн" : "Агент офлайн"}</strong>
                  <p>
                    Клиент: {describePresence(Boolean(snapshot?.presence.requester_online))}, поддержка:{" "}
                    {describePresence(Boolean(snapshot?.presence.support_online))}
                  </p>
                </article>
                <article className="support-snapshot-card">
                  <span>Устройство</span>
                  <strong>{snapshot?.device.hostname ?? snapshot?.device.device_id ?? "не привязано"}</strong>
                  <p>
                    {snapshot?.device.os ?? "ОС не указана"} · агент {snapshot?.device.agent_version ?? "—"}
                  </p>
                </article>
                <article className="support-snapshot-card">
                  <span>Последний сигнал</span>
                  <strong>{formatDateTime(snapshot?.device.last_seen_at ?? null)}</strong>
                  <p>Непрочитанных уведомлений: {snapshot?.notification_unread ?? 0}</p>
                </article>
              </div>

              <div className="support-operations">
                <div className="support-operations__head">
                  <span>Последние операции</span>
                  <span>{snapshot?.latest_operations.length ?? 0}</span>
                </div>
                {(snapshot?.latest_operations.length ?? 0) === 0 ? (
                  <div className="support-ticket-empty support-ticket-empty--inline">
                    Операции по устройству пока не найдены.
                  </div>
                ) : (
                  <div className="support-operations__list">
                    {snapshot?.latest_operations.map((operation) => (
                      <article className="support-operation-card" key={operation.operation_id}>
                        <strong>{operation.tool_name ?? operation.command_name ?? operation.kind}</strong>
                        <span>{operation.status}</span>
                        <p>{operation.result_summary ?? operation.error_message ?? "Без краткого результата"}</p>
                      </article>
                    ))}
                  </div>
                )}
              </div>
            </section>
          </div>
        </div>
      </div>
    </aside>
  );
}

export function SupportWorkspace() {
  const queryClient = useQueryClient();
  const [scope, setScope] = useState<SupportQueueScope>("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [query, setQuery] = useState("");
  const [selectedTicketId, setSelectedTicketId] = useState<string | null>(null);
  const [toolActionMessage, setToolActionMessage] = useState<string | null>(null);
  const deferredQuery = useDeferredValue(query);
  const selectedTicketIdRef = useRef<string | null>(null);
  const realtimeTicketSubscriptionsRef = useRef(new Map<string, () => void>());

  const supportBootstrapQuery = useQuery({
    queryKey: ["support", "bootstrap"],
    queryFn: fetchSupportBootstrap,
  });
  const supportQueueQuery = useQuery({
    queryKey: ["support", "queue", scope, statusFilter, deferredQuery],
    queryFn: () => fetchSupportQueue({ scope, statusFilter, query: deferredQuery }),
    enabled: supportBootstrapQuery.isSuccess,
    refetchInterval: SUPPORT_QUEUE_REFRESH_MS,
  });
  const supportTicketQuery = useQuery({
    queryKey: ["support", "ticket", selectedTicketId],
    queryFn: () => fetchSupportTicketDetail(selectedTicketId ?? ""),
    enabled: Boolean(selectedTicketId) && supportBootstrapQuery.isSuccess,
  });
  const supportToolsQuery = useQuery({
    queryKey: ["support", "tools", selectedTicketId],
    queryFn: () => fetchSupportTicketTools(selectedTicketId ?? ""),
    enabled: Boolean(selectedTicketId) && supportBootstrapQuery.isSuccess,
  });

  useEffect(() => {
    const queue = supportQueueQuery.data;
    if (!queue) {
      return;
    }

    const stillVisible = selectedTicketId && queue.tickets.some((ticket) => ticket.ticket_id === selectedTicketId);
    if (stillVisible) {
      return;
    }

    startTransition(() => {
      setSelectedTicketId(queue.summary.selected_ticket_id);
    });
  }, [selectedTicketId, supportQueueQuery.data]);

  useEffect(() => {
    setToolActionMessage(null);
  }, [selectedTicketId]);

  useEffect(() => {
    selectedTicketIdRef.current = selectedTicketId;
  }, [selectedTicketId]);

  useEffect(() => {
    const realtimeClient = getSharedWebRealtimeClient();
    const activeSubscriptions = realtimeTicketSubscriptionsRef.current;
    const targetTicketIds = new Set(selectedTicketId ? [selectedTicketId] : []);

    for (const [ticketId, unsubscribe] of activeSubscriptions.entries()) {
      if (targetTicketIds.has(ticketId)) {
        continue;
      }
      unsubscribe();
      activeSubscriptions.delete(ticketId);
    }

    for (const ticketId of targetTicketIds) {
      if (activeSubscriptions.has(ticketId)) {
        continue;
      }

      const unsubscribe = realtimeClient.subscribeTicket(ticketId, (message) => {
        void queryClient.invalidateQueries({ queryKey: ["support", "queue"] });

        const currentSelectedTicketId = selectedTicketIdRef.current;
        if (!currentSelectedTicketId || message.ticketId !== currentSelectedTicketId) {
          return;
        }

        void queryClient.invalidateQueries({ queryKey: ["support", "ticket", currentSelectedTicketId] });
        void queryClient.invalidateQueries({ queryKey: ["support", "tools", currentSelectedTicketId] });
      });

      activeSubscriptions.set(ticketId, unsubscribe);
    }
  }, [queryClient, selectedTicketId]);

  useEffect(() => {
    return () => {
      for (const unsubscribe of realtimeTicketSubscriptionsRef.current.values()) {
        unsubscribe();
      }
      realtimeTicketSubscriptionsRef.current.clear();
    };
  }, []);

  const sendMessageMutation = useMutation({
    mutationFn: ({ ticketId, text }: { ticketId: string; text: string }) => postSupportTicketMessage(ticketId, text),
    onSuccess: async (_result, variables) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["support", "ticket", variables.ticketId] }),
        queryClient.invalidateQueries({ queryKey: ["support", "queue"] }),
      ]);
    },
  });

  const statusMutation = useMutation({
    mutationFn: ({ ticketId, toStatus }: { ticketId: string; toStatus: string }) => postSupportTicketStatus(ticketId, toStatus),
    onSuccess: async (_result, variables) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["support", "ticket", variables.ticketId] }),
        queryClient.invalidateQueries({ queryKey: ["support", "queue"] }),
      ]);
    },
  });

  const toolRunMutation = useMutation({
    mutationFn: ({
      ticketId,
      toolName,
      presetId,
      params,
    }: {
      ticketId: string;
      toolName: string;
      presetId: string | null;
      params: Record<string, unknown>;
    }) => postSupportTicketToolRun(ticketId, { toolName, presetId, params }),
    onSuccess: async (result, variables) => {
      setToolActionMessage(
        result.dispatch_status === "waiting_consent"
          ? `Операция ${result.operation_id} ожидает согласование.`
          : `Операция ${result.operation_id} поставлена в очередь выполнения.`,
      );
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["support", "ticket", variables.ticketId] }),
        queryClient.invalidateQueries({ queryKey: ["support", "tools", variables.ticketId] }),
        queryClient.invalidateQueries({ queryKey: ["support", "queue"] }),
      ]);
    },
  });

  const queueStatus: "loading" | "error" | "ready" = supportQueueQuery.isPending
    ? "loading"
    : supportQueueQuery.isError
      ? "error"
      : "ready";

  if (supportBootstrapQuery.isPending) {
    return (
      <section className="workspace-boot workspace-boot--loading" aria-live="polite">
        <div className="workspace-boot__hero">
          <div className="workspace-boot__hero-copy">
            <p className="workspace-boot__eyebrow">Операторский контур</p>
            <h1>Поднимаем рабочее место поддержки</h1>
            <p>Загружаем базовую конфигурацию, queue boundary и observer-контекст.</p>
          </div>
        </div>
      </section>
    );
  }

  if (supportBootstrapQuery.isError) {
    return (
      <section className="workspace-boot workspace-boot--error" aria-live="polite">
        <div className="workspace-boot__hero">
          <div className="workspace-boot__hero-copy">
            <p className="workspace-boot__eyebrow">Операторский контур</p>
            <h1>Не удалось открыть поддержку</h1>
            <p>{supportBootstrapQuery.error.message}</p>
            <button className="workspace-boot__retry" onClick={() => void supportBootstrapQuery.refetch()} type="button">
              Повторить загрузку
            </button>
          </div>
        </div>
      </section>
    );
  }

  const bootstrap = supportBootstrapQuery.data;

  return (
    <section className="support-workspace workspace-page">
      <header className="workspace-page__header">
        <div className="workspace-page__copy">
          <p className="workspace-boot__eyebrow">Операторский контур</p>
          <h1>Рабочее место поддержки</h1>
          <p>
            Единый рабочий слой для очереди, активного тикета, observer-сводки и запуска типизированных
            инструментов без возврата в legacy `/ticket`.
          </p>
        </div>

        <dl className="workspace-page__stats">
          <div>
            <dt>Рабочая зона</dt>
            <dd>{bootstrap.workspace}</dd>
          </div>
          <div>
            <dt>Видимых тикетов</dt>
            <dd>{supportQueueQuery.data?.summary.visible_count ?? 0}</dd>
          </div>
          <div>
            <dt>Вкладка observer</dt>
            <dd>{bootstrap.observer.drawer_tab}</dd>
          </div>
        </dl>
      </header>

      <div className="support-workspace__grid">
        <SupportQueuePanel
          onQueryChange={setQuery}
          onScopeChange={setScope}
          onSelectTicket={setSelectedTicketId}
          onStatusChange={setStatusFilter}
          query={query}
          queue={supportQueueQuery.data}
          queueStatus={queueStatus}
          scope={scope}
          selectedTicketId={selectedTicketId}
          statusFilter={statusFilter}
        />
        <SupportDetailPanel
          errorMessage={supportTicketQuery.isError ? supportTicketQuery.error.message : undefined}
          isLoading={Boolean(selectedTicketId) && supportTicketQuery.isPending}
          observerDrawerTab={bootstrap.observer.drawer_tab}
          onApplyStatus={async (toStatus) => {
            if (!selectedTicketId) {
              return;
            }
            await statusMutation.mutateAsync({ ticketId: selectedTicketId, toStatus });
          }}
          onRunTool={async ({ toolName, presetId, params }) => {
            if (!selectedTicketId) {
              return;
            }
            await toolRunMutation.mutateAsync({
              ticketId: selectedTicketId,
              toolName,
              presetId,
              params,
            });
          }}
          onSendMessage={async (text) => {
            if (!selectedTicketId) {
              return;
            }
            await sendMessageMutation.mutateAsync({ ticketId: selectedTicketId, text });
          }}
          sendPending={sendMessageMutation.isPending}
          statusPending={statusMutation.isPending}
          ticketDetail={supportTicketQuery.data}
          toolActionMessage={toolActionMessage}
          toolPending={toolRunMutation.isPending}
          tools={supportToolsQuery.data}
          toolsErrorMessage={supportToolsQuery.isError ? supportToolsQuery.error.message : undefined}
          toolsLoading={Boolean(selectedTicketId) && supportToolsQuery.isPending}
        />
      </div>
    </section>
  );
}
