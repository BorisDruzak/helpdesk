import { Funnel, Plus, Rows3, SlidersHorizontal } from "lucide-react";
import { startTransition, useDeferredValue, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { PageHeading } from "../../components/ui/page-heading";
import { SearchField } from "../../components/ui/search-field";
import { Select } from "../../components/ui/select";
import { StatTile } from "../../components/ui/stat-tile";
import {
  getTicketQueueCounts,
  ticketPriorityMeta,
  ticketStatusMeta,
  tickets,
  type TicketStatus
} from "../../mocks/helpdesk-data";

type QueueFilter = "all" | "mine" | TicketStatus;

const queueFilterOptions: Array<{ description: string; key: QueueFilter; label: string }> = [
  { key: "all", label: "Все тикеты", description: "Полный рабочий список" },
  { key: "mine", label: "Мои тикеты", description: "Личный рабочий поток" },
  { key: "new", label: "Новые", description: "Нужны первые ответы" },
  { key: "in_progress", label: "В работе", description: "Активные обработки" },
  { key: "waiting_on_user", label: "Ожидают ответа", description: "Ждем пользователя" },
  { key: "resolved", label: "Решенные", description: "Закрытые за текущую смену" }
];

export function TicketListPage() {
  const navigate = useNavigate();
  const [activeFilter, setActiveFilter] = useState<QueueFilter>("all");
  const [query, setQuery] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("all");
  const deferredQuery = useDeferredValue(query);
  const queueCounts = getTicketQueueCounts();

  const filteredTickets = tickets.filter((ticket) => {
    const matchesFilter =
      activeFilter === "all"
        ? true
        : activeFilter === "mine"
          ? ticket.mine
          : ticket.status === activeFilter;

    const matchesPriority =
      priorityFilter === "all" ? true : ticket.priority === priorityFilter;

    const normalizedQuery = deferredQuery.trim().toLowerCase();
    const matchesQuery =
      normalizedQuery.length === 0
        ? true
        : [ticket.code, ticket.title, ticket.requesterName, ticket.assigneeName, ticket.category]
            .join(" ")
            .toLowerCase()
            .includes(normalizedQuery);

    return matchesFilter && matchesPriority && matchesQuery;
  });

  return (
    <section className="space-y-6">
      <PageHeading
        actions={
          <>
            <Button leadingIcon={<Funnel className="h-4 w-4" />} variant="outline">
              Фильтры
            </Button>
            <Button leadingIcon={<Plus className="h-4 w-4" />}>Новый тикет</Button>
          </>
        }
        description="Собранный список заявок со статусами, поиском и быстрым переходом в карточку тикета. Пространство поддерживает плотную SaaS-композицию без лишних блоков."
        eyebrow="Support workspace"
        title="Тикеты"
      />

      <div className="grid gap-4 xl:grid-cols-4">
        <StatTile helper="За период" label="Всего тикетов" value="128" />
        <StatTile helper="Активный пул" label="В работе" value="45" />
        <StatTile helper="Ждут пользователя" label="Ожидают ответа" value="12" />
        <StatTile helper="Среднее время ответа" label="SLA" value="12м 24с" />
      </div>

      <div className="grid gap-6 xl:grid-cols-[290px_minmax(0,1fr)]">
        <Card className="h-fit">
          <CardHeader>
            <CardTitle>Рабочая панель</CardTitle>
            <CardDescription>
              Здесь вынесены мои тикеты, статусы и быстрые фильтры, как в вашем референсе.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {queueFilterOptions.map((option) => {
              const count =
                option.key === "all"
                  ? queueCounts.all
                  : option.key === "mine"
                    ? queueCounts.mine
                    : queueCounts[option.key];

              const active = option.key === activeFilter;

              return (
                <button
                  key={option.key}
                  className={`flex w-full items-center justify-between rounded-panel border px-4 py-3 text-left transition-colors ${
                    active
                      ? "border-brand-200 bg-brand-50 text-brand-900"
                      : "border-transparent bg-surface-subtle text-slate-700 hover:border-border hover:bg-white"
                  }`}
                  onClick={() =>
                    startTransition(() => {
                      setActiveFilter(option.key);
                    })
                  }
                  type="button"
                >
                  <span>
                    <span className="block text-sm font-semibold">{option.label}</span>
                    <span className="mt-1 block text-xs text-slate-500">{option.description}</span>
                  </span>
                  <span className="rounded-full bg-white/90 px-2.5 py-1 text-xs font-semibold text-slate-700 shadow-soft">
                    {count}
                  </span>
                </button>
              );
            })}

            <div className="space-y-3 border-t border-border pt-4">
              <label className="space-y-2 text-sm font-medium text-slate-800">
                <span>Поиск</span>
                <SearchField
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Код, тема, инициатор"
                  value={query}
                />
              </label>

              <label className="space-y-2 text-sm font-medium text-slate-800">
                <span>Приоритет</span>
                <Select value={priorityFilter} onChange={(event) => setPriorityFilter(event.target.value)}>
                  <option value="all">Все приоритеты</option>
                  <option value="high">Высокий</option>
                  <option value="medium">Средний</option>
                  <option value="low">Низкий</option>
                </Select>
              </label>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="gap-4">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
              <div>
                <CardTitle>Список тикетов</CardTitle>
                <CardDescription>
                  Ровная таблица без лишнего шума, с чистыми линиями и выделением активного статуса.
                </CardDescription>
              </div>

              <div className="flex items-center gap-3">
                <Button leadingIcon={<Rows3 className="h-4 w-4" />} size="sm" variant="secondary">
                  Компактный вид
                </Button>
                <Button leadingIcon={<SlidersHorizontal className="h-4 w-4" />} size="sm" variant="outline">
                  Сначала новые
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="overflow-hidden rounded-[1.1rem] border border-border">
              <table className="min-w-full divide-y divide-border text-left text-sm">
                <thead className="bg-surface-subtle text-slate-500">
                  <tr>
                    <th className="px-5 py-3.5 font-medium">ID</th>
                    <th className="px-5 py-3.5 font-medium">Тема</th>
                    <th className="px-5 py-3.5 font-medium">Клиент</th>
                    <th className="px-5 py-3.5 font-medium">Статус</th>
                    <th className="px-5 py-3.5 font-medium">Приоритет</th>
                    <th className="px-5 py-3.5 font-medium">Обновлен</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border bg-white [content-visibility:auto]">
                  {filteredTickets.map((ticket) => (
                    <tr
                      key={ticket.id}
                      className="cursor-pointer transition-colors hover:bg-brand-50/60"
                      onClick={() => navigate(`/app/tickets/${ticket.id}`)}
                    >
                      <td className="px-5 py-4 font-semibold text-slate-900">{ticket.code}</td>
                      <td className="px-5 py-4">
                        <div>
                          <p className="font-semibold text-slate-900">{ticket.title}</p>
                          <p className="mt-1 text-xs text-slate-500">{ticket.category}</p>
                        </div>
                      </td>
                      <td className="px-5 py-4 text-slate-600">{ticket.requesterName}</td>
                      <td className="px-5 py-4">
                        <Badge tone={ticketStatusMeta[ticket.status].tone}>{ticketStatusMeta[ticket.status].label}</Badge>
                      </td>
                      <td className="px-5 py-4">
                        <Badge tone={ticketPriorityMeta[ticket.priority].tone}>
                          {ticketPriorityMeta[ticket.priority].label}
                        </Badge>
                      </td>
                      <td className="px-5 py-4 text-slate-500">{ticket.updatedAt}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="flex flex-col gap-3 text-sm text-slate-500 md:flex-row md:items-center md:justify-between">
              <p>
                Показано {filteredTickets.length} из {tickets.length}
              </p>
              <div className="flex items-center gap-2">
                <span className="rounded-pill border border-border bg-surface-subtle px-3 py-1.5">1</span>
                <span className="rounded-pill border border-border px-3 py-1.5 text-slate-400">2</span>
                <span className="rounded-pill border border-border px-3 py-1.5 text-slate-400">3</span>
                <span className="rounded-pill border border-border px-3 py-1.5 text-slate-400">16</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </section>
  );
}
