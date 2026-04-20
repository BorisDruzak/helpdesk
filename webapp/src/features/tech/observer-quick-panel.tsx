import { startTransition, useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { fetchAdminObserverQuick } from "./api";
import { ObserverTraceDrilldown } from "./observer-trace-drilldown";


const LOOKBACK_OPTIONS = [
  { hours: 6, label: "6 часов" },
  { hours: 24, label: "24 часа" },
  { hours: 72, label: "72 часа" }
] as const;

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

type ObserverQuickPanelProps = {
  deviceId: string | null;
  deviceLabel: string;
};

export function ObserverQuickPanel({ deviceId, deviceLabel }: ObserverQuickPanelProps) {
  const [lookbackHours, setLookbackHours] = useState<number>(24);
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);

  useEffect(() => {
    setSelectedTraceId(null);
  }, [deviceId]);

  const observerQuickQuery = useQuery({
    queryKey: ["admin-observer-quick", deviceId, lookbackHours],
    queryFn: () =>
      fetchAdminObserverQuick({
        lookbackHours,
        deviceId
      }),
    enabled: Boolean(deviceId),
    retry: false
  });

  return (
    <section className="admin-observer-panel">
      <div className="support-workspace__panel-head">
        <div className="admin-observer-panel__header">
          <div>
            <h3>Быстрый срез трассировки</h3>
            <p>Собираем горячие трассы, сигнатуры, деградации и опасные потоки для устройства {deviceLabel} через новый typed boundary.</p>
          </div>
          <span className={`admin-observer-panel__runtime admin-observer-panel__runtime--${observerQuickQuery.data?.runtime.health_status ?? "unknown"}`}>
            {observerQuickQuery.data?.runtime.health_status_label ?? "Собираем статус"}
          </span>
        </div>

        <div className="support-filter-group">
          {LOOKBACK_OPTIONS.map((option) => (
            <button
              key={option.hours}
              type="button"
              className={`support-chip${lookbackHours === option.hours ? " active" : ""}`}
              onClick={() => {
                startTransition(() => {
                  setLookbackHours(option.hours);
                });
              }}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {observerQuickQuery.isLoading ? (
        <div className="support-detail-note">Собираем быстрый срез по последним трассам и runtime-статусу…</div>
      ) : null}

      {observerQuickQuery.isError ? (
        <div className="support-detail-error">
          {observerQuickQuery.error instanceof Error
            ? observerQuickQuery.error.message
            : "Не удалось загрузить быстрый срез трассировки."}
        </div>
      ) : null}

      {observerQuickQuery.data ? (
        <>
          <div className="support-snapshot-grid">
            <article className="support-snapshot-card">
              <span>Горячие трассы</span>
              <strong>{observerQuickQuery.data.summary.hot_trace_count}</strong>
              <p>Всего недавних трасс: {observerQuickQuery.data.summary.recent_trace_count}</p>
            </article>
            <article className="support-snapshot-card">
              <span>Сигнатуры ошибок</span>
              <strong>{observerQuickQuery.data.summary.signature_count}</strong>
              <p>Группы деградаций: {observerQuickQuery.data.summary.degradation_group_count}</p>
            </article>
            <article className="support-snapshot-card">
              <span>Опасные потоки</span>
              <strong>{observerQuickQuery.data.summary.dangerous_flow_count}</strong>
              <p>
                Runtime: {observerQuickQuery.data.runtime.health_status_label}
                {observerQuickQuery.data.runtime.pending_trace_count !== null
                  ? `, в очереди ${observerQuickQuery.data.runtime.pending_trace_count}`
                  : ""}
              </p>
            </article>
          </div>

          <div className="admin-observer-panel__links">
            <code>{observerQuickQuery.data.links.quick_endpoint}</code>
            <code>{observerQuickQuery.data.links.traces_endpoint}</code>
            <code>{observerQuickQuery.data.links.runtime_endpoint}</code>
          </div>

          <div className="admin-observer-grid">
            <article className="support-operation-card">
              <div className="support-operations__head">
                <strong>Горячие трассы</strong>
                <span>{observerQuickQuery.data.summary.lookback_hours} ч</span>
              </div>
              {observerQuickQuery.data.hot_traces.length ? (
                <div className="admin-observer-list">
                  {observerQuickQuery.data.hot_traces.map((trace) => (
                    <button
                      key={trace.trace_id}
                      type="button"
                      className={`admin-observer-item admin-observer-item--button${selectedTraceId === trace.trace_id ? " active" : ""}`}
                      onClick={() => {
                        startTransition(() => {
                          setSelectedTraceId(trace.trace_id);
                        });
                      }}
                    >
                      <div className="admin-observer-item__head">
                        <strong>{trace.root_kind_label}</strong>
                        <span>{trace.status_label}</span>
                      </div>
                      <p>{trace.trace_id}</p>
                      <p>
                        Ошибок: {trace.error_count} · span: {trace.span_count} · длительность: {formatDuration(trace.duration_ms)}
                      </p>
                      <p>Завершена: {formatDateTime(trace.finished_at ?? trace.started_at)}</p>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="support-queue-empty">За выбранное окно горячих трасс пока нет.</div>
              )}
            </article>

            <article className="support-operation-card">
              <div className="support-operations__head">
                <strong>Сигнатуры ошибок</strong>
                <span>{observerQuickQuery.data.top_signatures.length}</span>
              </div>
              {observerQuickQuery.data.top_signatures.length ? (
                <div className="admin-observer-list">
                  {observerQuickQuery.data.top_signatures.map((signature) => (
                    <article key={signature.error_signature} className="admin-observer-item">
                      <div className="admin-observer-item__head">
                        <strong>{signature.title}</strong>
                        <span>{signature.occurrences_count}</span>
                      </div>
                      <p>{signature.tool_name ?? signature.component ?? "Без источника"}</p>
                      <p>Устройств затронуто: {signature.affected_devices_count}</p>
                      <p>Последний случай: {formatDateTime(signature.last_seen_at)}</p>
                    </article>
                  ))}
                </div>
              ) : (
                <div className="support-queue-empty">Новых сигнатур ошибок за окно нет.</div>
              )}
            </article>

            <article className="support-operation-card">
              <div className="support-operations__head">
                <strong>Деградации</strong>
                <span>{observerQuickQuery.data.top_degradations.length}</span>
              </div>
              {observerQuickQuery.data.top_degradations.length ? (
                <div className="admin-observer-list">
                  {observerQuickQuery.data.top_degradations.map((item) => (
                    <article key={`${item.operation_kind ?? "unknown"}:${item.tool_name ?? "tool"}`} className="admin-observer-item">
                      <div className="admin-observer-item__head">
                        <strong>{item.tool_name ?? item.operation_kind_label}</strong>
                        <span>{item.operation_kind_label}</span>
                      </div>
                      <p>
                        Таймаутов: {item.timeout_count} · retry: {item.retried_operations_count} · slow: {item.slow_operations_count}
                      </p>
                      <p>Пик: {formatDuration(item.max_duration_ms)}</p>
                      <p>Последняя активность: {formatDateTime(item.latest_operation_at)}</p>
                    </article>
                  ))}
                </div>
              ) : (
                <div className="support-queue-empty">Деградации по текущему окну не обнаружены.</div>
              )}
            </article>

            <article className="support-operation-card">
              <div className="support-operations__head">
                <strong>Опасные потоки</strong>
                <span>{observerQuickQuery.data.dangerous_flows.length}</span>
              </div>
              {observerQuickQuery.data.dangerous_flows.length ? (
                <div className="admin-observer-list">
                  {observerQuickQuery.data.dangerous_flows.map((item) => (
                    <article key={item.root_kind} className="admin-observer-item">
                      <div className="admin-observer-item__head">
                        <strong>{item.root_kind_label}</strong>
                        <span>{item.operations_count}</span>
                      </div>
                      <p>
                        Ошибок: {item.error_count} · таймаутов: {item.timeout_count} · retry: {item.retried_count}
                      </p>
                      <p>Активных сейчас: {item.active_count}</p>
                      <p>Последняя операция: {formatDateTime(item.latest_operation_at)}</p>
                    </article>
                  ))}
                </div>
              ) : (
                <div className="support-queue-empty">Опасные потоки за окно не попали в выборку.</div>
              )}
            </article>
          </div>

          <ObserverTraceDrilldown
            deviceId={deviceId}
            deviceLabel={deviceLabel}
            lookbackHours={lookbackHours}
            selectedTraceId={selectedTraceId}
            onSelectedTraceChange={setSelectedTraceId}
          />
        </>
      ) : null}
    </section>
  );
}
