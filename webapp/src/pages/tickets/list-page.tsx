import { useQuery } from "@tanstack/react-query";
import { RefreshCcw } from "lucide-react";
import { startTransition, useDeferredValue, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { PageHeading } from "../../components/ui/page-heading";
import { SearchField } from "../../components/ui/search-field";
import { StatTile } from "../../components/ui/stat-tile";
import { fetchSupportQueue, type SupportCountItem, type SupportQueueScope } from "../../features/queues/api";
import { getTicketStatusPresentation } from "../../features/tickets/status-presentation";

const SUPPORT_QUEUE_REFRESH_MS = 15_000;

function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return "Нет данных";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit"
  }).format(date);
}

function getCount(items: SupportCountItem[] | undefined, value: string) {
  return items?.find((item) => item.value === value)?.count ?? 0;
}

export function TicketListPage() {
  const navigate = useNavigate();
  const [scope, setScope] = useState<SupportQueueScope>("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [smartView, setSmartView] = useState("all");
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query);

  const queueQuery = useQuery({
    queryKey: ["tickets-page-queue", scope, statusFilter, smartView, deferredQuery],
    queryFn: () =>
      fetchSupportQueue({
        scope,
        statusFilter,
        smartView,
        query: deferredQuery
      }),
    retry: false,
    refetchInterval: SUPPORT_QUEUE_REFRESH_MS
  });

  const queue = queueQuery.data;
  const scopeCounts = queue?.summary.scope_counts ?? [];
  const statusCounts = queue?.summary.status_counts ?? [];
  const smartViewCounts = queue?.summary.smart_view_counts ?? [];

  return (
    <section className="space-y-6">
      <PageHeading
        actions={
          <Button
            disabled={queueQuery.isFetching}
            leadingIcon={<RefreshCcw className="h-4 w-4" />}
            onClick={() => {
              void queueQuery.refetch();
            }}
            variant="outline"
          >
            {queueQuery.isFetching ? "Обновляем..." : "Обновить"}
          </Button>
        }
        description="Рабочий список тикетов идёт из реального typed support boundary: живая очередь, поиск, статусы и быстрый переход в карточку без вымышленных данных."
        eyebrow="Support workspace"
        title="Тикеты"
      />

      <div className="grid gap-4 xl:grid-cols-5">
        <StatTile helper="Текущий срез" label="Всего доступно" value={String(getCount(scopeCounts, "all"))} />
        <StatTile helper="Назначено на меня" label="Мои тикеты" value={String(getCount(scopeCounts, "mine"))} />
        <StatTile helper="Активная обработка" label="В работе" value={String(getCount(statusCounts, "in_progress"))} />
        <StatTile
          helper="Нужен ответ пользователя"
          label="Ожидают ответа"
          value={String(getCount(statusCounts, "waiting_on_user"))}
        />
        <StatTile helper="Контроль внутренних сроков" label="OLA риск" value={String(getCount(smartViewCounts, "ola_risk"))} />
      </div>

      <div className="grid gap-6 xl:grid-cols-[300px_minmax(0,1fr)]">
        <Card className="h-fit">
          <CardHeader>
            <CardTitle>Рабочая панель</CardTitle>
            <CardDescription>
              Здесь собраны реальные области видимости, статусы и поиск по очереди, как вы просили по структуре рабочего пространства.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-3">
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">Область</p>
              {scopeCounts.map((item) => {
                const active = item.value === scope;

                return (
                  <button
                    key={item.value}
                    className={`flex w-full items-center justify-between rounded-panel border px-4 py-3 text-left transition-colors ${
                      active
                        ? "border-brand-200 bg-brand-50 text-brand-900"
                        : "border-transparent bg-surface-subtle text-slate-700 hover:border-border hover:bg-white"
                    }`}
                    onClick={() => {
                      startTransition(() => {
                        setScope(item.value as SupportQueueScope);
                      });
                    }}
                    type="button"
                  >
                    <span className="font-semibold">{item.label}</span>
                    <span className="rounded-full bg-white/90 px-2.5 py-1 text-xs font-semibold text-slate-700 shadow-soft">
                      {item.count}
                    </span>
                  </button>
                );
              })}
            </div>

            <div className="space-y-3 border-t border-border pt-6">
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">Статусы</p>
              {statusCounts.map((item) => {
                const active = item.value === statusFilter;

                return (
                  <button
                    key={item.value}
                    className={`flex w-full items-center justify-between rounded-panel border px-4 py-3 text-left transition-colors ${
                      active
                        ? "border-brand-200 bg-brand-50 text-brand-900"
                        : "border-transparent bg-surface-subtle text-slate-700 hover:border-border hover:bg-white"
                    }`}
                    onClick={() => {
                      startTransition(() => {
                        setStatusFilter(item.value);
                      });
                    }}
                    type="button"
                  >
                    <span className="font-medium">{item.label}</span>
                    <span className="rounded-full bg-white/90 px-2.5 py-1 text-xs font-semibold text-slate-700 shadow-soft">
                      {item.count}
                    </span>
                  </button>
                );
              })}
            </div>

            <div className="space-y-3 border-t border-border pt-6">
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">Рабочие срезы</p>
              {(queue?.filters.smart_view_options ?? []).map((option) => {
                const count = getCount(smartViewCounts, option.value);
                const active = option.value === smartView;

                return (
                  <button
                    key={option.value}
                    className={`flex w-full items-center justify-between rounded-panel border px-4 py-3 text-left transition-colors ${
                      active
                        ? "border-brand-200 bg-brand-50 text-brand-900"
                        : "border-transparent bg-surface-subtle text-slate-700 hover:border-border hover:bg-white"
                    }`}
                    onClick={() => {
                      startTransition(() => {
                        setSmartView(option.value);
                      });
                    }}
                    type="button"
                  >
                    <span className="font-medium">{option.label}</span>
                    <span className="rounded-full bg-white/90 px-2.5 py-1 text-xs font-semibold text-slate-700 shadow-soft">
                      {count}
                    </span>
                  </button>
                );
              })}
            </div>

            <label className="space-y-2 text-sm font-medium text-slate-800">
              <span>Поиск</span>
              <SearchField
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Код, тема, инициатор, устройство"
                value={query}
              />
            </label>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="gap-4">
            <div className="flex flex-col gap-2 xl:flex-row xl:items-end xl:justify-between">
              <div>
                <CardTitle>Список тикетов</CardTitle>
                <CardDescription>
                  Ровная таблица очереди с реальными статусами, живым обновлением и плотной SaaS-подачей.
                </CardDescription>
              </div>
              <p className="text-sm text-slate-500">
                Видимых тикетов: <span className="font-semibold text-slate-950">{queue?.summary.visible_count ?? 0}</span>
              </p>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {queueQuery.isLoading ? (
              <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-5 py-10 text-center text-sm text-slate-500">
                Загружаем реальную очередь поддержки...
              </div>
            ) : null}

            {queueQuery.isError ? (
              <div className="rounded-[1.1rem] border border-rose-200 bg-rose-50 px-5 py-4 text-sm text-rose-700">
                {queueQuery.error instanceof Error
                  ? queueQuery.error.message
                  : "Не удалось загрузить очередь поддержки."}
              </div>
            ) : null}

            {queue && queue.tickets.length === 0 ? (
              <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-5 py-10 text-center text-sm text-slate-500">
                По текущим фильтрам тикеты не найдены.
              </div>
            ) : null}

            {queue && queue.tickets.length > 0 ? (
              <div className="overflow-hidden rounded-[1.1rem] border border-border">
                <table className="min-w-full divide-y divide-border text-left text-sm">
                  <thead className="bg-surface-subtle text-slate-500">
                    <tr>
                      <th className="px-5 py-3.5 font-medium">ID</th>
                      <th className="px-5 py-3.5 font-medium">Тема</th>
                      <th className="px-5 py-3.5 font-medium">Инициатор</th>
                      <th className="px-5 py-3.5 font-medium">Статус</th>
                      <th className="px-5 py-3.5 font-medium">Очередь</th>
                      <th className="px-5 py-3.5 font-medium">Обновлён</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border bg-white [content-visibility:auto]">
                    {queue.tickets.map((ticket) => {
                      const presentation = getTicketStatusPresentation({
                        status: ticket.status,
                        statusLabel: ticket.status_label,
                        requesterStatusLabel: ticket.requester_status_label,
                        nextActionOwner: ticket.next_action_owner,
                        statusReason: ticket.status_reason,
                      });

                      return (
                        <tr
                          key={ticket.ticket_id}
                          className="cursor-pointer transition-colors hover:bg-brand-50/60"
                          onClick={() => navigate(`/app/tickets/${ticket.ticket_id}`)}
                        >
                          <td className="px-5 py-4 font-semibold text-slate-900">
                            {ticket.ticket_code ?? ticket.ticket_id}
                          </td>
                          <td className="px-5 py-4">
                            <div>
                              <p className="font-semibold text-slate-900">{ticket.title}</p>
                              <p className="mt-1 text-xs text-slate-500">
                                {ticket.device_id ?? "Без привязки к устройству"}
                                {ticket.unread_user_messages > 0 ? ` • ${ticket.unread_user_messages} непрочит.` : ""}
                              </p>
                            </div>
                          </td>
                          <td className="px-5 py-4 text-slate-600">
                            {ticket.requester_display_name ?? "Инициатор не указан"}
                          </td>
                          <td className="px-5 py-4">
                            <div className="space-y-2">
                              <Badge tone={presentation.tone}>{presentation.statusLabel}</Badge>
                              <div className="text-xs leading-5 text-slate-500">
                                <span>{presentation.stageLabel}</span>
                                <span> • {presentation.ownerLabel}</span>
                                {presentation.requesterStatusLabel !== "Не указан" ? (
                                  <span> • {presentation.requesterStatusLabel}</span>
                                ) : null}
                              </div>
                            </div>
                          </td>
                          <td className="px-5 py-4 text-slate-500">{ticket.queue_code ?? "Без очереди"}</td>
                          <td className="px-5 py-4 text-slate-500">{formatDateTime(ticket.updated_at ?? ticket.created_at)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : null}
          </CardContent>
        </Card>
      </div>
    </section>
  );
}
