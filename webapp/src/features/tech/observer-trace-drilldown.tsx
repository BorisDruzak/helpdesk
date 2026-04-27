import { startTransition, useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import {
  type AdminObserverRootKindFilter,
  type AdminObserverTraceStatusFilter,
  fetchAdminObserverTraceDetail,
  fetchAdminObserverTraces
} from "./api";


const DEFAULT_LIMIT = 12;

function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "Нет данных";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(date);
}

function formatDuration(value: number | null | undefined): string {
  if (!value || value <= 0) {
    return "Нет данных";
  }
  if (value < 1000) {
    return `${value} мс`;
  }
  return `${(value / 1000).toFixed(1)} с`;
}

function formatTraceSources(attrs: Record<string, unknown> | null | undefined): string {
  const rawCounts = attrs?.source_counts;
  if (!rawCounts || typeof rawCounts !== "object") {
    return "sources: unknown";
  }
  const counts = rawCounts as Record<string, unknown>;
  const labels: Array<[string, string]> = [
    ["operations", "operation"],
    ["agent_runtime_audit", "runtime audit"],
    ["playbook_step_runs", "playbook step"],
    ["agent_observer_events", "agent telemetry"],
    ["ticket_events", "ticket event"],
    ["device_events", "device event"],
  ];
  const visible = labels
    .filter(([key]) => Number(counts[key] ?? 0) > 0)
    .map(([, label]) => label);
  return visible.length ? `sources: ${visible.join(", ")}` : "sources: root";
}

type ObserverTraceDrilldownProps = {
  deviceId: string | null;
  deviceLabel: string;
  lookbackHours: number;
  selectedTraceId: string | null;
  onSelectedTraceChange: (traceId: string | null) => void;
};

export function ObserverTraceDrilldown({
  deviceId,
  deviceLabel,
  lookbackHours,
  selectedTraceId,
  onSelectedTraceChange
}: ObserverTraceDrilldownProps) {
  const [statusFilter, setStatusFilter] = useState<AdminObserverTraceStatusFilter>("all");
  const [rootKindFilter, setRootKindFilter] = useState<AdminObserverRootKindFilter>("all");

  useEffect(() => {
    setStatusFilter("all");
    setRootKindFilter("all");
  }, [deviceId]);

  const tracesQuery = useQuery({
    queryKey: ["admin-observer-traces", deviceId, lookbackHours, statusFilter, rootKindFilter],
    queryFn: () =>
      fetchAdminObserverTraces({
        deviceId,
        lookbackHours,
        statusFilter,
        rootKindFilter,
        limit: DEFAULT_LIMIT
      }),
    retry: false
  });

  const traces = tracesQuery.data?.traces ?? [];

  useEffect(() => {
    if (!traces.length) {
      if (selectedTraceId !== null) {
        startTransition(() => {
          onSelectedTraceChange(null);
        });
      }
      return;
    }

    if (!selectedTraceId || !traces.some((trace) => trace.trace_id === selectedTraceId)) {
      startTransition(() => {
        onSelectedTraceChange(traces[0].trace_id);
      });
    }
  }, [onSelectedTraceChange, selectedTraceId, traces]);

  const detailQuery = useQuery({
    queryKey: ["admin-observer-trace-detail", selectedTraceId],
    queryFn: () => fetchAdminObserverTraceDetail(selectedTraceId!),
    enabled: Boolean(selectedTraceId),
    retry: false
  });

  return (
    <section className="admin-observer-drilldown">
      <div className="support-workspace__panel-head">
        <div>
          <h3>Детальный разбор трасс</h3>
          <p>Показываем свежие трассы для устройства {deviceLabel}, чтобы быстро переходить от summary к span-level деталям.</p>
        </div>
        <div className="admin-observer-drilldown__summary">
          <span>Трасс в выборке: {tracesQuery.data?.summary.visible_count ?? 0}</span>
          <span>Активных: {tracesQuery.data?.summary.active_count ?? 0}</span>
          <span>С ошибкой: {tracesQuery.data?.summary.error_count ?? 0}</span>
        </div>
      </div>

      <div className="admin-observer-drilldown__filters">
        <label className="support-filter-select">
          <span>Статус трассы</span>
          <select
            value={statusFilter}
            onChange={(event) => {
              const value = event.currentTarget.value as AdminObserverTraceStatusFilter;
              startTransition(() => {
                setStatusFilter(value);
              });
            }}
          >
            {(tracesQuery.data?.filters.status_options ?? []).map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="support-filter-select">
          <span>Тип потока</span>
          <select
            value={rootKindFilter}
            onChange={(event) => {
              const value = event.currentTarget.value as AdminObserverRootKindFilter;
              startTransition(() => {
                setRootKindFilter(value);
              });
            }}
          >
            {(tracesQuery.data?.filters.root_kind_options ?? []).map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      {tracesQuery.isLoading ? (
        <div className="support-detail-note">Собираем список трасс и готовим drilldown по выбранному устройству…</div>
      ) : null}

      {tracesQuery.isError ? (
        <div className="support-detail-error">
          {tracesQuery.error instanceof Error ? tracesQuery.error.message : "Не удалось загрузить список трасс."}
        </div>
      ) : null}

      {tracesQuery.data ? (
        <div className="admin-observer-drilldown__grid">
          <article className="support-operation-card">
            <div className="support-operations__head">
              <strong>Последние трассы</strong>
              <span>{tracesQuery.data.query.lookback_hours} ч</span>
            </div>
            <div className="admin-observer-trace-list">
              {traces.length ? (
                traces.map((trace) => {
                  const isActive = trace.trace_id === selectedTraceId;
                  return (
                    <button
                      key={trace.trace_id}
                      type="button"
                      className={`admin-observer-trace-card${isActive ? " active" : ""}`}
                      onClick={() => {
                        startTransition(() => {
                          onSelectedTraceChange(trace.trace_id);
                        });
                      }}
                    >
                      <div className="admin-observer-item__head">
                        <strong>{trace.root_kind_label}</strong>
                        <span>{trace.status_label}</span>
                      </div>
                      <p className="admin-observer-trace-card__code">{trace.trace_id}</p>
                      <p>
                        Ошибок: {trace.error_count} · span: {trace.span_count} · длительность: {formatDuration(trace.duration_ms)}
                      </p>
                      <p>
                        {trace.operation_id ? `Операция ${trace.operation_id}` : "Операция не привязана"}
                        {trace.ticket_id ? ` · Тикет ${trace.ticket_id}` : ""}
                      </p>
                      <p>{formatTraceSources(trace.attrs_json)}</p>
                      <p>Завершение: {formatDateTime(trace.finished_at ?? trace.started_at)}</p>
                    </button>
                  );
                })
              ) : (
                <div className="support-queue-empty">Для выбранного устройства по текущим фильтрам трасс пока нет.</div>
              )}
            </div>
          </article>

          <article className="support-operation-card">
            <div className="support-operations__head">
              <strong>Детали выбранной трассы</strong>
              <span>{selectedTraceId ?? "Нет выбора"}</span>
            </div>

            {!selectedTraceId ? (
              <div className="support-queue-empty">Выберите трассу слева, чтобы открыть span-level детали.</div>
            ) : null}

            {detailQuery.isLoading ? (
              <div className="support-detail-note">Загружаем структуру span, связи и ошибки…</div>
            ) : null}

            {detailQuery.isError ? (
              <div className="support-detail-error">
                {detailQuery.error instanceof Error ? detailQuery.error.message : "Не удалось загрузить детали трассы."}
              </div>
            ) : null}

            {detailQuery.data ? (
              <div className="admin-observer-trace-detail">
                <div className="support-snapshot-grid">
                  <article className="support-snapshot-card">
                    <span>Статус трассы</span>
                    <strong>{detailQuery.data.trace.status_label}</strong>
                    <p>{detailQuery.data.trace.root_kind_label}</p>
                  </article>
                  <article className="support-snapshot-card">
                    <span>Span в трассе</span>
                    <strong>{detailQuery.data.summary.span_count}</strong>
                    <p>Связанных трасс: {detailQuery.data.summary.linked_trace_count}</p>
                  </article>
                  <article className="support-snapshot-card">
                    <span>Ошибки</span>
                    <strong>{detailQuery.data.summary.error_count}</strong>
                    <p>Длительность: {formatDuration(detailQuery.data.trace.duration_ms)}</p>
                  </article>
                </div>

                <div className="admin-observer-panel__links">
                  <code>{tracesQuery.data.links.detail_endpoint_template}</code>
                  <code>{tracesQuery.data.links.runtime_endpoint}</code>
                </div>

                <div className="admin-observer-trace-detail__meta">
                  <div>
                    <span>Trace ID</span>
                    <code>{detailQuery.data.trace.trace_id}</code>
                  </div>
                  <div>
                    <span>Тикет</span>
                    <strong>{detailQuery.data.trace.ticket_id ?? "Не привязан"}</strong>
                  </div>
                  <div>
                    <span>Операция</span>
                    <strong>{detailQuery.data.trace.operation_id ?? "Не привязана"}</strong>
                  </div>
                  <div>
                    <span>Последнее обновление</span>
                    <strong>{formatDateTime(detailQuery.data.trace.finished_at ?? detailQuery.data.trace.started_at)}</strong>
                  </div>
                </div>

                <div className="admin-observer-trace-detail__lists">
                  <section className="admin-observer-list">
                    <div className="support-operations__head">
                      <strong>Span timeline</strong>
                      <span>{detailQuery.data.spans.length}</span>
                    </div>
                    {detailQuery.data.spans.length ? (
                      detailQuery.data.spans.map((span) => (
                        <article key={span.span_id} className="admin-observer-item">
                          <div className="admin-observer-item__head">
                            <strong>{span.name}</strong>
                            <span>{span.status_label}</span>
                          </div>
                          <p>
                            {span.component ?? "Компонент не указан"}
                            {span.tool_name ? ` · ${span.tool_name}` : ""}
                            {span.module_name ? ` · ${span.module_name}` : ""}
                          </p>
                          <p>Источник: {span.source_type ?? "unknown"}{span.source_ref ? ` · ${span.source_ref}` : ""}</p>
                          <p>Длительность: {formatDuration(span.duration_ms)}</p>
                        </article>
                      ))
                    ) : (
                      <div className="support-queue-empty">Span-последовательность для этой трассы пока пуста.</div>
                    )}
                  </section>

                  <section className="admin-observer-list">
                    <div className="support-operations__head">
                      <strong>Ошибки и связи</strong>
                      <span>{detailQuery.data.error_occurrences.length}</span>
                    </div>
                    {detailQuery.data.error_occurrences.length ? (
                      detailQuery.data.error_occurrences.map((occurrence) => (
                        <article key={occurrence.occurrence_id} className="admin-observer-item">
                          <div className="admin-observer-item__head">
                            <strong>{occurrence.error_signature}</strong>
                            <span>{occurrence.severity_label}</span>
                          </div>
                          <p>{occurrence.message_norm ?? "Сообщение ошибки недоступно"}</p>
                          <p>
                            {occurrence.exception_type ?? "Тип исключения не указан"}
                            {occurrence.failure_stage ? ` · ${occurrence.failure_stage}` : ""}
                          </p>
                          <p>Создано: {formatDateTime(occurrence.created_at)}</p>
                        </article>
                      ))
                    ) : (
                      <div className="support-queue-empty">Отдельные error occurrence для этой трассы не зафиксированы.</div>
                    )}

                    {detailQuery.data.span_links.length ? (
                      <section className="admin-observer-trace-links">
                        <div className="support-operations__head">
                          <strong>Связанные трассы</strong>
                          <span>{detailQuery.data.span_links.length}</span>
                        </div>
                        <div className="admin-observer-list">
                          {detailQuery.data.span_links.map((link) => (
                            <article key={link.id} className="admin-observer-item">
                              <div className="admin-observer-item__head">
                                <strong>{link.linked_trace_id ?? "Связанная трасса"}</strong>
                                <span>{link.reason ?? "Связь"}</span>
                              </div>
                              <p>Span: {link.span_id}</p>
                              <p>Создано: {formatDateTime(link.created_at)}</p>
                            </article>
                          ))}
                        </div>
                      </section>
                    ) : null}
                  </section>
                </div>
              </div>
            ) : null}
          </article>
        </div>
      ) : null}
    </section>
  );
}
