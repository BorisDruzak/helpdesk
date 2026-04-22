import {
  ArrowLeft,
  ChevronDown,
  CircleHelp,
  Copy,
  FileText,
  History,
  Paperclip,
  Smile,
  Tags,
  TextCursorInput
} from "lucide-react";
import { startTransition, useDeferredValue, useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";

import { Avatar } from "../../components/ui/avatar";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { SearchField } from "../../components/ui/search-field";
import { Select } from "../../components/ui/select";
import { Tabs } from "../../components/ui/tabs";
import {
  getTicketById,
  getTicketQueueCounts,
  ticketPriorityMeta,
  ticketStatusMeta,
  tickets,
  type TicketStatus
} from "../../mocks/helpdesk-data";

type QueueFilter = "all" | "mine" | TicketStatus;

const queueTabs = [
  { value: "dialog", label: "Диалог" },
  { value: "info", label: "Информация" },
  { value: "files", label: "Файлы" },
  { value: "history", label: "История" }
];

export function TicketDetailPage() {
  const navigate = useNavigate();
  const { ticketId = "" } = useParams();
  const ticket = getTicketById(ticketId);
  const queueCounts = getTicketQueueCounts();
  const [activeQueueFilter, setActiveQueueFilter] = useState<QueueFilter>("all");
  const [queueQuery, setQueueQuery] = useState("");
  const [activeTab, setActiveTab] = useState("dialog");
  const [composerTab, setComposerTab] = useState("reply");
  const deferredQueueQuery = useDeferredValue(queueQuery);

  if (!ticketId || !ticket) {
    return <Navigate replace to="/app/tickets" />;
  }

  const visibleTickets = tickets.filter((item) => {
    const matchesFilter =
      activeQueueFilter === "all"
        ? true
        : activeQueueFilter === "mine"
          ? item.mine
          : item.status === activeQueueFilter;
    const normalizedQuery = deferredQueueQuery.trim().toLowerCase();
    const matchesQuery =
      normalizedQuery.length === 0
        ? true
        : [item.code, item.title, item.requesterName].join(" ").toLowerCase().includes(normalizedQuery);
    return matchesFilter && matchesQuery;
  });

  return (
    <section className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <Button
              leadingIcon={<ArrowLeft className="h-4 w-4" />}
              onClick={() => navigate("/app/tickets")}
              size="sm"
              variant="outline"
            >
              Назад
            </Button>
            <div className="flex items-center gap-3">
              <h1 className="font-display text-2xl font-semibold tracking-tight text-slate-950 md:text-3xl">
                Тикет #{ticket.code}
              </h1>
              <button
                className="rounded-full border border-border p-2 text-slate-400 transition-colors hover:text-brand-700"
                type="button"
              >
                <Copy className="h-4 w-4" />
              </button>
            </div>
          </div>

          <div>
            <p className="text-2xl font-semibold tracking-tight text-slate-950">{ticket.title}</p>
            <p className="mt-2 text-sm text-slate-500">
              Создан: {ticket.createdAt} • Клиент: {ticket.requesterName} • {ticket.requesterEmail}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <Badge tone={ticketStatusMeta[ticket.status].tone} withDot>
            {ticketStatusMeta[ticket.status].label}
          </Badge>
          <Button trailingIcon={<ChevronDown className="h-4 w-4" />} variant="outline">
            Еще
          </Button>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[300px_minmax(0,1fr)_320px]">
        <Card className="h-fit">
          <CardHeader>
            <CardTitle>Очередь</CardTitle>
            <CardDescription>
              Вынесена в отдельное окно рабочей области, чтобы чат оставался главным.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-2">
              {[
                { key: "all" as const, label: "Все", count: queueCounts.all },
                { key: "mine" as const, label: "Мои", count: queueCounts.mine },
                { key: "in_progress" as const, label: "В работе", count: queueCounts.in_progress },
                { key: "waiting_on_user" as const, label: "Ожидают", count: queueCounts.waiting_on_user }
              ].map((item) => (
                <button
                  key={item.key}
                  className={`rounded-pill px-3 py-2 text-sm font-medium transition-colors ${
                    activeQueueFilter === item.key
                      ? "bg-brand-600 text-white"
                      : "bg-surface-subtle text-slate-600 hover:bg-brand-50 hover:text-brand-800"
                  }`}
                  onClick={() =>
                    startTransition(() => {
                      setActiveQueueFilter(item.key);
                    })
                  }
                  type="button"
                >
                  {item.label} ({item.count})
                </button>
              ))}
            </div>

            <SearchField
              onChange={(event) => setQueueQuery(event.target.value)}
              placeholder="Код, тема, инициатор"
              value={queueQuery}
            />

            <div className="space-y-3">
              {visibleTickets.map((queueTicket) => {
                const active = queueTicket.id === ticket.id;

                return (
                  <button
                    key={queueTicket.id}
                    className={`w-full rounded-[1.1rem] border px-4 py-4 text-left transition-colors ${
                      active
                        ? "border-brand-200 bg-brand-50"
                        : "border-border bg-white hover:border-brand-100 hover:bg-surface-subtle"
                    }`}
                    onClick={() => navigate(`/app/tickets/${queueTicket.id}`)}
                    type="button"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-brand-700">
                          {queueTicket.code}
                        </p>
                        <p className="mt-2 text-base font-semibold text-slate-950">{queueTicket.title}</p>
                      </div>
                      <Badge tone={ticketStatusMeta[queueTicket.status].tone}>
                        {ticketStatusMeta[queueTicket.status].label}
                      </Badge>
                    </div>
                    <p className="mt-3 text-sm text-slate-500">{queueTicket.requesterName}</p>
                    <p className="mt-2 text-xs text-slate-400">{queueTicket.updatedAt}</p>
                  </button>
                );
              })}
            </div>
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card className="overflow-hidden">
            <CardContent className="relative px-0 pb-0 pt-0">
              <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(16,185,129,0.08),transparent_28%),radial-gradient(circle_at_center,rgba(37,99,235,0.06),transparent_40%)]" />
              <div className="relative border-b border-border px-6 py-5">
                <Tabs items={queueTabs} onValueChange={setActiveTab} value={activeTab} />
              </div>

              <div className="relative space-y-4 px-6 py-6">
                {activeTab === "dialog" ? (
                  ticket.messages.map((message) => {
                    const roleTone = message.role === "client" ? "client" : message.role === "agent" ? "agent" : "neutral";
                    const badgeTone = message.role === "client" ? "neutral" : message.role === "agent" ? "info" : "warning";
                    const roleLabel = message.role === "client" ? "Клиент" : message.role === "agent" ? "Агент" : "Система";

                    return (
                      <div
                        key={message.id}
                        className={`rounded-[1.3rem] border px-5 py-5 shadow-soft ${
                          message.role === "agent"
                            ? "border-blue-100 bg-blue-50/60"
                            : "border-border bg-white"
                        }`}
                      >
                        <div className="flex items-start gap-4">
                          <Avatar name={message.author} tone={roleTone} />
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <p className="font-semibold text-slate-950">{message.author}</p>
                              <span className="text-sm text-slate-400">{message.timestamp}</span>
                              <Badge className="ml-auto" tone={badgeTone}>
                                {roleLabel}
                              </Badge>
                            </div>
                            <p className="mt-3 max-w-3xl whitespace-pre-line text-[15px] leading-7 text-slate-700">
                              {message.body}
                            </p>
                          </div>
                        </div>
                      </div>
                    );
                  })
                ) : null}

                {activeTab === "info" ? (
                  <Card className="border-dashed bg-surface-subtle shadow-none">
                    <CardHeader>
                      <CardTitle>Информация по запросу</CardTitle>
                      <CardDescription>{ticket.summary}</CardDescription>
                    </CardHeader>
                    <CardContent className="grid gap-3 text-sm text-slate-600 md:grid-cols-2">
                      <div className="rounded-panel bg-white px-4 py-4">
                        <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Канал</p>
                        <p className="mt-2 font-semibold text-slate-950">{ticket.channel}</p>
                      </div>
                      <div className="rounded-panel bg-white px-4 py-4">
                        <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Категория</p>
                        <p className="mt-2 font-semibold text-slate-950">{ticket.category}</p>
                      </div>
                    </CardContent>
                  </Card>
                ) : null}

                {activeTab === "files" ? (
                  <div className="space-y-3">
                    {ticket.attachments.map((attachment) => (
                      <div
                        key={attachment.id}
                        className="flex items-center justify-between rounded-[1.1rem] border border-border bg-white px-4 py-4"
                      >
                        <div className="flex items-center gap-3">
                          <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-brand-50 text-brand-700">
                            <Paperclip className="h-4 w-4" />
                          </div>
                          <div>
                            <p className="font-semibold text-slate-900">{attachment.name}</p>
                            <p className="text-sm text-slate-500">{attachment.size}</p>
                          </div>
                        </div>
                        <Button size="sm" variant="outline">
                          Скачать
                        </Button>
                      </div>
                    ))}
                  </div>
                ) : null}

                {activeTab === "history" ? (
                  <div className="space-y-3">
                    {ticket.history.map((item) => (
                      <div key={item.id} className="rounded-[1.1rem] border border-border bg-white px-4 py-4">
                        <div className="flex items-center justify-between gap-3">
                          <p className="font-semibold text-slate-950">{item.label}</p>
                          <span className="text-sm text-slate-400">{item.timestamp}</span>
                        </div>
                        <p className="mt-2 text-sm text-slate-500">{item.detail}</p>
                      </div>
                    ))}
                  </div>
                ) : null}
              </div>
            </CardContent>
          </Card>

          {activeTab === "dialog" ? (
            <Card>
              <CardContent className="space-y-4 pt-6">
                <div className="flex gap-6 border-b border-border pb-3">
                  <button
                    className={`text-sm font-semibold ${composerTab === "reply" ? "text-brand-700" : "text-slate-500"}`}
                    onClick={() => setComposerTab("reply")}
                    type="button"
                  >
                    Ответить
                  </button>
                  <button
                    className={`text-sm font-semibold ${composerTab === "comment" ? "text-brand-700" : "text-slate-500"}`}
                    onClick={() => setComposerTab("comment")}
                    type="button"
                  >
                    Внутренний комментарий
                  </button>
                </div>

                <textarea
                  aria-label="Ответ оператору"
                  className="field-base min-h-[140px] w-full resize-none px-4 py-4 text-sm text-slate-800"
                  defaultValue=""
                  placeholder={
                    composerTab === "reply"
                      ? "Напишите сообщение..."
                      : "Добавьте внутренний комментарий для команды..."
                  }
                />

                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <button className="icon-button" type="button">
                      <Paperclip className="h-4 w-4" />
                    </button>
                    <button className="icon-button" type="button">
                      <Smile className="h-4 w-4" />
                    </button>
                    <button className="icon-button" type="button">
                      <TextCursorInput className="h-4 w-4" />
                    </button>
                    <button className="icon-button" type="button">
                      <FileText className="h-4 w-4" />
                    </button>
                  </div>

                  <div className="flex items-center gap-2">
                    <Button>Отправить</Button>
                    <Button size="icon" variant="outline">
                      <ChevronDown className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ) : null}
        </div>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Информация о тикете</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-slate-500">ID</span>
                <div className="flex items-center gap-2 font-semibold text-slate-900">
                  <span>{ticket.code}</span>
                  <Copy className="h-4 w-4 text-slate-400" />
                </div>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500">Статус</span>
                <Badge tone={ticketStatusMeta[ticket.status].tone} withDot>
                  {ticketStatusMeta[ticket.status].label}
                </Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500">Приоритет</span>
                <Badge tone={ticketPriorityMeta[ticket.priority].tone} withDot>
                  {ticketPriorityMeta[ticket.priority].label}
                </Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500">Категория</span>
                <span className="font-medium text-slate-900">{ticket.category}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500">Создан</span>
                <span className="font-medium text-slate-900">{ticket.createdAt}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500">Обновлен</span>
                <span className="font-medium text-slate-900">{ticket.updatedAt}</span>
              </div>
              <label className="space-y-2">
                <span className="text-slate-500">Ответственный</span>
                <Select defaultValue={ticket.assigneeName}>
                  <option value={ticket.assigneeName}>{ticket.assigneeName}</option>
                  <option value="Екатерина Л.">Екатерина Л.</option>
                  <option value="Олег К.">Олег К.</option>
                </Select>
              </label>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Информация о клиенте</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-start gap-3">
                <Avatar name={ticket.requesterName} tone="client" />
                <div>
                  <p className="font-semibold text-slate-950">{ticket.requesterName}</p>
                  <p className="text-sm text-slate-500">{ticket.requesterEmail}</p>
                  <p className="mt-1 text-sm text-slate-500">{ticket.requesterPhone}</p>
                </div>
              </div>
              <Link className="inline-flex items-center gap-2 text-sm font-semibold text-brand-700" to="/app/tickets">
                Все тикеты клиента (5)
              </Link>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Теги</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              {ticket.tags.map((tag) => (
                <Badge key={tag} tone="info">
                  {tag}
                </Badge>
              ))}
              <button className="icon-button" type="button">
                <Tags className="h-4 w-4" />
              </button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Дополнительно</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-slate-500">Браузер</span>
                <span className="font-medium text-slate-900">{ticket.browser}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500">ОС</span>
                <span className="font-medium text-slate-900">{ticket.os}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500">IP адрес</span>
                <span className="font-medium text-slate-900">{ticket.ipAddress}</span>
              </div>
              <div className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
                <div className="flex items-center gap-2 text-slate-700">
                  <CircleHelp className="h-4 w-4" />
                  <span className="font-semibold">SLA</span>
                </div>
                <div className="mt-4 space-y-3">
                  <div>
                    <div className="mb-1 flex items-center justify-between text-xs text-slate-500">
                      <span>Ответ</span>
                      <span>{ticket.responseSla}</span>
                    </div>
                    <div className="h-2 rounded-full bg-white">
                      <div className="h-2 w-[72%] rounded-full bg-brand-500" />
                    </div>
                  </div>
                  <div>
                    <div className="mb-1 flex items-center justify-between text-xs text-slate-500">
                      <span>Решение</span>
                      <span>{ticket.resolutionSla}</span>
                    </div>
                    <div className="h-2 rounded-full bg-white">
                      <div className="h-2 w-[54%] rounded-full bg-blue-500" />
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </section>
  );
}
