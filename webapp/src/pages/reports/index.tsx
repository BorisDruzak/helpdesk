import { BarChart3, RefreshCcw } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { PageHeading } from "../../components/ui/page-heading";
import { Select } from "../../components/ui/select";
import { StatTile } from "../../components/ui/stat-tile";
import { fetchWebReportsSummary } from "../../features/reports/api";


const DAY_OPTIONS = [
  { value: 7, label: "7 дней" },
  { value: 14, label: "14 дней" },
  { value: 30, label: "30 дней" },
] as const;


function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "Нет данных";
  }
  return `${value.toFixed(1)}%`;
}


function formatMinutes(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "Нет данных";
  }
  if (value < 60) {
    return `${Math.round(value)} мин`;
  }
  const hours = Math.floor(value / 60);
  const minutes = Math.round(value % 60);
  return `${hours} ч ${minutes} мин`;
}


function formatDateRange(startAt: string, endAt: string): string {
  const startDate = new Date(startAt);
  const endDate = new Date(endAt);
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "long",
  }).format(startDate) + " - " +
    new Intl.DateTimeFormat("ru-RU", {
      day: "2-digit",
      month: "long",
    }).format(endDate);
}


function formatAge(seconds: number): string {
  if (!seconds) {
    return "0 мин";
  }
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.max(1, Math.round((seconds % 3600) / 60));
  if (hours <= 0) {
    return `${minutes} мин`;
  }
  return `${hours} ч ${minutes} мин`;
}


export function ReportsPage() {
  const [days, setDays] = useState<number>(14);
  const [queueId, setQueueId] = useState<number | null>(null);

  const reportsQuery = useQuery({
    queryKey: ["web-reports-summary", days, queueId],
    queryFn: () =>
      fetchWebReportsSummary({
        days,
        queueId,
      }),
    retry: false,
    refetchInterval: 60_000,
  });

  const payload = reportsQuery.data;
  const maxTrendValue = Math.max(
    1,
    ...((payload?.daily_trend ?? []).flatMap((item) => [item.created_count, item.closed_count]))
  );
  const maxBacklogValue = Math.max(1, ...((payload?.backlog_by_priority ?? []).map((item) => item.count)));

  return (
    <section className="space-y-6">
      <PageHeading
        actions={
          <>
            <Select
              onChange={(event) => setDays(Number(event.target.value))}
              value={String(days)}
            >
              {DAY_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
            <Select
              onChange={(event) => setQueueId(event.target.value ? Number(event.target.value) : null)}
              value={queueId === null ? "" : String(queueId)}
            >
              <option value="">Все очереди</option>
              {(payload?.filters.queue_options ?? []).map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
            <Button
              leadingIcon={<RefreshCcw className="h-4 w-4" />}
              onClick={() => void reportsQuery.refetch()}
              size="sm"
              variant="outline"
            >
              Обновить
            </Button>
          </>
        }
        description="Операционный отчёт на реальных метриках тикетов: backlog, сроки ответа, reopen rate, среднее время решения и живые срезы по очередям и типам обращений."
        eyebrow="Analytics"
        title="Отчёты"
      />

      {reportsQuery.isLoading ? <p className="text-sm text-slate-500">Собираем реальные ticket metrics…</p> : null}
      {reportsQuery.isError ? (
        <p className="text-sm text-rose-600">
          {reportsQuery.error instanceof Error ? reportsQuery.error.message : "Не удалось загрузить отчёты."}
        </p>
      ) : null}

      {payload ? (
        <>
          <div className="grid gap-4 xl:grid-cols-4">
            <StatTile
              helper={formatDateRange(payload.period.start_at, payload.period.end_at)}
              label="Открытый backlog"
              value={String(payload.summary.open_backlog_count)}
            />
            <StatTile
              helper="Тикеты с closed_at в выбранном периоде"
              label="Закрыто за период"
              value={String(payload.summary.closed_in_period_count)}
            />
            <StatTile
              helper="Среднее по закрытым тикетам"
              label="Среднее время решения"
              value={formatMinutes(payload.summary.avg_resolution_minutes)}
            />
            <StatTile
              helper={`FRT ${formatPercent(payload.summary.first_response_compliance_percent)}`}
              label="Выполнение сроков"
              value={formatPercent(payload.summary.resolution_compliance_percent)}
            />
          </div>

          <div className="grid gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(320px,0.75fr)]">
            <Card>
              <CardHeader>
                <CardTitle>Дневная динамика тикетов</CardTitle>
                <CardDescription>Created и closed по реальным данным tickets за выбранный интервал.</CardDescription>
              </CardHeader>
              <CardContent>
                {payload.daily_trend.length ? (
                  <div className="grid min-h-[320px] grid-cols-7 items-end gap-3">
                    {payload.daily_trend.map((point) => (
                      <div key={point.day} className="flex h-full flex-col items-center justify-end gap-3">
                        <div className="flex h-full w-full items-end justify-center gap-2 rounded-[1.1rem] bg-surface-subtle px-3 py-4">
                          <div
                            className="w-3 rounded-full bg-blue-500"
                            style={{ height: `${Math.max(12, (point.created_count / maxTrendValue) * 220)}px` }}
                            title={`Создано: ${point.created_count}`}
                          />
                          <div
                            className="w-3 rounded-full bg-emerald-500"
                            style={{ height: `${Math.max(12, (point.closed_count / maxTrendValue) * 220)}px` }}
                            title={`Закрыто: ${point.closed_count}`}
                          />
                        </div>
                        <p className="text-xs font-medium text-slate-500">{point.day}</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-4 py-8 text-sm text-slate-500">
                    Для выбранного интервала пока нет накопленной динамики.
                  </div>
                )}
              </CardContent>
            </Card>

            <div className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>Типы обращений</CardTitle>
                  <CardDescription>Распределение по request_kind и ticket_type из реальных тикетов.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {payload.request_kinds.length ? (
                    payload.request_kinds.map((item) => (
                      <div key={item.key}>
                        <div className="mb-2 flex items-center justify-between text-sm">
                          <span className="text-slate-600">{item.label}</span>
                          <span className="font-semibold text-slate-950">{item.count}</span>
                        </div>
                        <div className="h-2 rounded-full bg-surface-subtle">
                          <div
                            className="h-2 rounded-full bg-brand-500"
                            style={{
                              width: `${Math.max(
                                8,
                                (item.count / Math.max(1, payload.request_kinds[0]?.count ?? 1)) * 100
                              )}%`,
                            }}
                          />
                        </div>
                      </div>
                    ))
                  ) : (
                    <p className="text-sm text-slate-500">Типы обращений пока не накопились.</p>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Риски периода</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
                    <p className="text-sm text-slate-500">Reopen rate</p>
                    <p className="mt-2 text-2xl font-semibold text-slate-950">
                      {formatPercent(payload.summary.reopen_rate_percent)}
                    </p>
                  </div>
                  <div className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
                    <p className="text-sm text-slate-500">First response compliance</p>
                    <p className="mt-2 text-2xl font-semibold text-slate-950">
                      {formatPercent(payload.summary.first_response_compliance_percent)}
                    </p>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>

          <div className="grid gap-6 xl:grid-cols-3">
            <Card>
              <CardHeader>
                <CardTitle>Backlog по приоритету</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {payload.backlog_by_priority.length ? (
                  payload.backlog_by_priority.map((item) => (
                    <div key={item.priority}>
                      <div className="mb-2 flex items-center justify-between text-sm">
                        <span className="text-slate-600">{item.priority_label}</span>
                        <Badge tone="brand">{item.count}</Badge>
                      </div>
                      <div className="h-2 rounded-full bg-surface-subtle">
                        <div
                          className="h-2 rounded-full bg-blue-500"
                          style={{ width: `${Math.max(10, (item.count / maxBacklogValue) * 100)}%` }}
                        />
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-slate-500">Открытого backlog по текущему фильтру нет.</p>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Aging buckets</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {payload.aging_buckets.length ? (
                  payload.aging_buckets.map((item) => (
                    <div key={item.bucket} className="flex items-center justify-between rounded-[1.1rem] bg-surface-subtle px-4 py-4">
                      <span className="text-sm text-slate-600">{item.bucket}</span>
                      <span className="text-lg font-semibold text-slate-950">{item.count}</span>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-slate-500">Старение очереди пока не зафиксировано.</p>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Top очереди</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {payload.top_queues.length ? (
                  payload.top_queues.map((item) => (
                    <div key={`${item.queue_id ?? "none"}:${item.queue_label}`} className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
                      <p className="font-semibold text-slate-950">{item.queue_label}</p>
                      <p className="mt-2 text-sm text-slate-500">Открыто тикетов: {item.open_count}</p>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-slate-500">Топ очередей пока пуст.</p>
                )}
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-6 xl:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">
            <Card>
              <CardHeader>
                <CardTitle>Последние тикеты в отчёте</CardTitle>
                <CardDescription>Живой список последних обновлённых тикетов по текущему фильтру.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {payload.recent_tickets.length ? (
                  payload.recent_tickets.map((ticket) => (
                    <div key={ticket.ticket_id} className="rounded-[1.1rem] border border-border bg-white px-4 py-4">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <p className="font-semibold text-slate-950">{ticket.ticket_code}</p>
                          <p className="mt-1 text-sm text-slate-500">{ticket.title}</p>
                        </div>
                        <Badge tone="brand">{ticket.status_label}</Badge>
                      </div>
                      <div className="mt-3 flex flex-wrap items-center gap-4 text-xs text-slate-400">
                        <span>{ticket.queue_label}</span>
                        <span>{ticket.requester_id ?? "requester не указан"}</span>
                        <span>{ticket.updated_at ? new Date(ticket.updated_at).toLocaleString("ru-RU") : "нет updated_at"}</span>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-slate-500">Подходящих тикетов для текущего фильтра пока нет.</p>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Статусы и средний возраст</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {payload.status_age.length ? (
                  payload.status_age.map((item) => (
                    <div key={item.status} className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
                      <div className="flex items-center justify-between gap-3">
                        <p className="font-semibold text-slate-950">{item.status_label}</p>
                        <Badge tone="info">{item.count}</Badge>
                      </div>
                      <p className="mt-2 text-sm text-slate-500">Средний возраст: {formatAge(item.avg_age_seconds)}</p>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-slate-500">По открытым статусам пока нет данных.</p>
                )}
              </CardContent>
            </Card>
          </div>
        </>
      ) : (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
            <BarChart3 className="h-8 w-8 text-brand-700" />
            <div>
              <p className="font-semibold text-slate-950">Отчёт пока недоступен</p>
              <p className="mt-1 text-sm text-slate-500">Когда backend вернёт данные, здесь появятся реальные KPI и срезы по тикетам.</p>
            </div>
          </CardContent>
        </Card>
      )}
    </section>
  );
}
