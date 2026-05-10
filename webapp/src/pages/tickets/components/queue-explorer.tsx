import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import type { SupportQueueScope } from "../../../features/queues/api";
import type {
  SupportWorkspaceQueue,
  SupportWorkspaceSelectedTicket,
  SupportWorkspaceSlice,
  SupportWorkspaceTicketItem,
} from "../../../features/queues/support-workspace-model";
import { toneClasses } from "./workspace-component-utils";

type QueueExplorerTab = "mine" | "queues" | "slices";

type QueueExplorerProps = {
  activeQueueId: string | null;
  onActiveQueueChange: (queueId: string | null) => void;
  onCleanupNoise: () => void;
  onOpenTicket: (ticketId: string) => void;
  onScopeChange: (scope: SupportQueueScope) => void;
  onSearchChange: (value: string) => void;
  onSelectTicket: (ticketId: string) => void;
  onShowArchiveChange: (value: boolean) => void;
  onSmartViewChange: (viewId: string) => void;
  queues: SupportWorkspaceQueue[];
  scope: SupportQueueScope;
  search: string;
  selectedTicket: SupportWorkspaceSelectedTicket | null;
  selectedViewId: string;
  showArchive: boolean;
  cleanupNoisePending?: boolean;
  slices: SupportWorkspaceSlice[];
  tickets: SupportWorkspaceTicketItem[];
};

function ticketActionScore(ticket: SupportWorkspaceTicketItem): number {
  let score = 0;
  if (ticket.slaRisk && ticket.nextDueLabel.toLowerCase().includes("просроч")) score += 1000;
  else if (ticket.slaRisk) score += 800;
  if (ticket.priority === "P0" || ticket.priority === "P1") score += 300;
  if (ticket.unread) score += 250;
  if (ticket.assigneeLabel.toLowerCase().includes("не назнач")) score += 200;
  if (ticket.statusLabel.toLowerCase().includes("очеред")) score += 120;
  return score;
}

function getTicketSlaLabel(ticket: SupportWorkspaceTicketItem, selectedTicket: SupportWorkspaceSelectedTicket | null): string {
  if (selectedTicket?.id === ticket.id && selectedTicket.nextAction.timerType !== "none") {
    return selectedTicket.nextAction.remainingLabel;
  }
  return ticket.nextDueLabel.toLowerCase().includes("нет") ? "SLA не рассчитан" : ticket.nextDueLabel;
}

function slaClassName(label: string, ticket: SupportWorkspaceTicketItem): string {
  if (label.toLowerCase().includes("не рассчитан") || label.toLowerCase().includes("нет")) return "text-slate-400";
  if (label.toLowerCase().includes("просроч")) return "text-red-300";
  return ticket.slaRisk ? "text-amber-300" : "text-emerald-300";
}

function buildCsv(rows: SupportWorkspaceTicketItem[]): string {
  const header = ["ticket", "subject", "requester", "priority", "status", "sla", "queue", "assignee", "updated"];
  const body = rows.map((ticket) =>
    [
      ticket.code,
      ticket.subject,
      ticket.requester,
      ticket.priority,
      ticket.statusLabel,
      ticket.nextDueLabel,
      ticket.queueLabel,
      ticket.assigneeLabel,
      ticket.updatedLabel,
    ]
      .map((value) => `"${String(value).replace(/"/g, '""')}"`)
      .join(","),
  );
  return [header.join(","), ...body].join("\n");
}

export function QueueExplorer({
  activeQueueId,
  cleanupNoisePending = false,
  onActiveQueueChange,
  onCleanupNoise,
  onOpenTicket,
  onScopeChange,
  onSearchChange,
  onSelectTicket,
  onShowArchiveChange,
  onSmartViewChange,
  queues,
  scope,
  search,
  selectedTicket,
  selectedViewId,
  showArchive,
  slices,
  tickets,
}: QueueExplorerProps) {
  const [activeTab, setActiveTab] = useState<QueueExplorerTab>("mine");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set());
  const [massActionsOpen, setMassActionsOpen] = useState(false);

  const sortedTickets = useMemo(
    () =>
      [...tickets].sort((left, right) => {
        const scoreDelta = ticketActionScore(right) - ticketActionScore(left);
        if (scoreDelta !== 0) return scoreDelta;
        if (left.priority !== right.priority) return left.priority.localeCompare(right.priority);
        return right.updatedLabel.localeCompare(left.updatedLabel);
      }),
    [tickets],
  );

  const selectedRows = sortedTickets.filter((ticket) => selectedIds.has(ticket.id));
  const allVisibleSelected = sortedTickets.length > 0 && sortedTickets.every((ticket) => selectedIds.has(ticket.id));
  const selectedCount = selectedIds.size;

  function toggleTicket(ticketId: string) {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(ticketId)) next.delete(ticketId);
      else next.add(ticketId);
      return next;
    });
  }

  function toggleAll() {
    setSelectedIds((current) => {
      if (sortedTickets.length > 0 && sortedTickets.every((ticket) => current.has(ticket.id))) {
        return new Set();
      }
      return new Set(sortedTickets.map((ticket) => ticket.id));
    });
  }

  function exportSelected() {
    const rows = selectedRows.length ? selectedRows : sortedTickets;
    const blob = new Blob([buildCsv(rows)], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "support-queue.csv";
    link.click();
    URL.revokeObjectURL(url);
    setMassActionsOpen(false);
  }

  const massActions = [
    "Назначить выбранные",
    "Сменить очередь",
    "Сменить приоритет",
    "Добавить внутреннюю заметку",
    "Запустить диагностику",
    "Связать как массовую проблему",
  ];

  return (
    <section className="flex min-h-0 flex-1 flex-col px-4 py-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-white">Очередь тикетов</h2>
          <p className="mt-1 text-sm text-slate-400">Таблица triage по тикетам, доступным текущей роли и очередям.</p>
        </div>
        <div className="relative flex shrink-0 items-center gap-2">
          <button
            aria-expanded={massActionsOpen}
            className={`rounded-xl border px-3 py-2 text-xs font-semibold transition ${
              selectedCount > 0 ? "border-blue-400/60 bg-blue-500/15 text-blue-100" : "border-white/10 bg-white/[0.04] text-slate-300"
            }`}
            onClick={() => setMassActionsOpen((open) => !open)}
            type="button"
          >
            Массовые действия{selectedCount ? ` · ${selectedCount}` : ""}
          </button>
          {massActionsOpen ? (
            <div className="absolute right-0 top-11 z-20 w-72 rounded-xl border border-white/10 bg-[#101d30] p-2 shadow-2xl shadow-black/40">
              <p className="px-2 pb-2 text-xs text-slate-400">
                Выбрано: {selectedCount}. Действия без backend-handler пока показаны как недоступные.
              </p>
              {massActions.map((label) => (
                <button
                  className="block w-full rounded-lg px-3 py-2 text-left text-sm text-slate-400 disabled:cursor-not-allowed disabled:opacity-60"
                  disabled
                  key={label}
                  type="button"
                >
                  {label}
                </button>
              ))}
              <button
                className="mt-1 block w-full rounded-lg px-3 py-2 text-left text-sm font-semibold text-slate-200 hover:bg-white/10"
                onClick={exportSelected}
                type="button"
              >
                Экспорт CSV
              </button>
            </div>
          ) : null}
        </div>
      </div>

      <div className="mt-4 grid gap-3 rounded-xl border border-white/10 bg-[#0d1828] p-3">
        <div className="grid grid-cols-3 gap-2 rounded-xl bg-white/[0.04] p-1">
          {[
            ["mine", "Мои"],
            ["queues", "Очереди"],
            ["slices", "Срезы"],
          ].map(([value, label]) => (
            <button
              className={`rounded-lg px-3 py-2 text-sm font-semibold transition ${
                activeTab === value ? "bg-blue-600 text-white" : "text-slate-400 hover:text-white"
              }`}
              key={value}
              onClick={() => {
                setActiveTab(value as QueueExplorerTab);
                if (value === "mine") onScopeChange("mine");
              }}
              type="button"
            >
              {label}
            </button>
          ))}
        </div>

        <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_220px_220px]">
          <label className="flex h-10 items-center gap-2 rounded-xl border border-white/10 bg-white/[0.04] px-3 text-sm text-slate-400">
            <Search className="h-4 w-4" />
            <input
              className="min-w-0 flex-1 bg-transparent text-slate-100 outline-none placeholder:text-slate-500"
              onChange={(event) => onSearchChange(event.currentTarget.value)}
              placeholder="Поиск по номеру, теме, заявителю..."
              type="search"
              value={search}
            />
          </label>
          <select
            className="h-10 rounded-xl border border-white/10 bg-[#101d30] px-3 text-sm text-slate-200 outline-none"
            onChange={(event) => onScopeChange(event.currentTarget.value as SupportQueueScope)}
            value={scope}
          >
            <option value="mine">Мои тикеты</option>
            <option value="all">Все доступные</option>
          </select>
          <select
            className="h-10 rounded-xl border border-white/10 bg-[#101d30] px-3 text-sm text-slate-200 outline-none"
            onChange={(event) => onSmartViewChange(event.currentTarget.value)}
            value={selectedViewId}
          >
            {slices.map((slice) => (
              <option key={slice.id} value={slice.id}>
                {slice.label} · {slice.count}
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-wrap gap-2 text-xs">
          <button
            className={`rounded-lg border px-3 py-2 font-semibold ${showArchive ? "border-blue-400/60 bg-blue-500/15 text-blue-100" : "border-white/10 bg-white/[0.04] text-slate-300"}`}
            onClick={() => onShowArchiveChange(!showArchive)}
            type="button"
          >
            {showArchive ? "Архив включен" : "Показывать архив"}
          </button>
          <button
            className="rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 font-semibold text-slate-300 hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
            disabled={cleanupNoisePending}
            onClick={onCleanupNoise}
            type="button"
          >
            Скрыть test
          </button>
          <span className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-slate-400">
            SLA: сначала просроченные и ближайшие к нарушению
          </span>
          <span className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-slate-400">
            Доступ: только тикеты роли и очередей оператора
          </span>
        </div>

        {activeTab === "queues" ? (
          <div className="flex flex-wrap gap-2">
            <button
              className={`rounded-lg border px-3 py-2 text-xs font-semibold ${activeQueueId === null ? "border-blue-400/60 bg-blue-500/15 text-blue-100" : "border-white/10 bg-white/[0.04] text-slate-300"}`}
              onClick={() => onActiveQueueChange(null)}
              type="button"
            >
              Все очереди
            </button>
            {queues.map((queue) => (
              <button
                className={`rounded-lg border px-3 py-2 text-xs font-semibold ${queue.active ? "border-blue-400/60 bg-blue-500/15 text-blue-100" : "border-white/10 bg-white/[0.04] text-slate-300"}`}
                key={queue.id}
                onClick={() => onActiveQueueChange(queue.active ? null : queue.id)}
                type="button"
              >
                {queue.label} · {queue.count}
              </button>
            ))}
          </div>
        ) : null}

        {activeTab === "slices" ? (
          <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
            {slices.map((slice) => (
              <button
                className={`rounded-lg border px-3 py-2 text-left text-xs font-semibold ${slice.active ? "border-blue-400/60 bg-blue-500/15 text-blue-100" : "border-white/10 bg-white/[0.04] text-slate-300"}`}
                key={slice.id}
                onClick={() => onSmartViewChange(slice.id)}
                type="button"
              >
                <span>{slice.label}</span>
                <span className="float-right rounded-full bg-white/10 px-2 py-0.5">{slice.count}</span>
              </button>
            ))}
          </div>
        ) : null}
      </div>

      <div className="mt-4 min-h-0 flex-1 overflow-auto rounded-xl border border-white/10 bg-[#0d1828]">
        <table className="w-full min-w-[1180px] border-collapse text-left text-sm">
          <thead className="sticky top-0 z-10 bg-[#101d30] text-xs uppercase tracking-[0.12em] text-slate-500">
            <tr>
              <th className="w-10 px-3 py-3">
                <input aria-label="Выбрать все тикеты" checked={allVisibleSelected} onChange={toggleAll} type="checkbox" />
              </th>
              <th className="px-3 py-3">№</th>
              <th className="px-3 py-3">Тема</th>
              <th className="px-3 py-3">Заявитель</th>
              <th className="px-3 py-3">P</th>
              <th className="px-3 py-3">Статус</th>
              <th className="px-3 py-3">Next action</th>
              <th className="px-3 py-3">SLA</th>
              <th className="px-3 py-3">Очередь</th>
              <th className="px-3 py-3">Исполнитель</th>
              <th className="px-3 py-3">Последнее</th>
              <th className="px-3 py-3">Непроч.</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/10">
            {sortedTickets.map((ticket, index) => {
              const slaLabel = getTicketSlaLabel(ticket, selectedTicket);
              return (
              <tr
                className={`cursor-pointer transition ${ticket.active ? "bg-blue-600/15 text-white" : "text-slate-300 hover:bg-white/[0.04]"}`}
                data-ticket-row-index={index}
                key={ticket.id}
                onClick={() => onSelectTicket(ticket.id)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    onOpenTicket(ticket.id);
                    return;
                  }
                  if (event.key === " ") {
                    event.preventDefault();
                    toggleTicket(ticket.id);
                    return;
                  }
                  if (event.key === "ArrowDown" || event.key === "ArrowUp") {
                    event.preventDefault();
                    const nextIndex = event.key === "ArrowDown" ? index + 1 : index - 1;
                    const nextRow = document.querySelector<HTMLElement>(`[data-ticket-row-index="${nextIndex}"]`);
                    nextRow?.focus();
                  }
                }}
                tabIndex={0}
              >
                <td className="px-3 py-3">
                  <input
                    aria-label={`Выбрать ${ticket.code}`}
                    checked={selectedIds.has(ticket.id)}
                    onChange={() => toggleTicket(ticket.id)}
                    onClick={(event) => event.stopPropagation()}
                    type="checkbox"
                  />
                </td>
                <td className="whitespace-nowrap px-3 py-3 font-semibold text-blue-200">{ticket.code}</td>
                <td className="min-w-[260px] px-3 py-3">
                  <p className="truncate font-semibold text-white" title={ticket.subject}>{ticket.subject}</p>
                  <p className="mt-1 truncate text-xs text-slate-500">Локация и категория появятся после расширения queue API</p>
                </td>
                <td className="max-w-[180px] truncate px-3 py-3" title={ticket.requester}>{ticket.requester}</td>
                <td className="px-3 py-3">
                  <span className={`rounded-md border px-2 py-1 text-xs font-bold ${toneClasses(ticket.priorityTone)}`}>{ticket.priority}</span>
                </td>
                <td className="px-3 py-3">
                  <span className={`rounded-md border px-2 py-1 text-xs font-semibold ${toneClasses(ticket.statusTone)}`}>{ticket.statusLabel}</span>
                </td>
                <td className="whitespace-nowrap px-3 py-3 text-xs font-semibold text-blue-200">
                  {ticket.unread ? "Requester reply" : ticket.slaRisk ? "Support" : "Queue"}
                </td>
                <td className={`whitespace-nowrap px-3 py-3 text-xs font-semibold ${slaClassName(slaLabel, ticket)}`}>
                  {slaLabel}
                </td>
                <td className="px-3 py-3">{ticket.queueLabel}</td>
                <td className="px-3 py-3">{ticket.assigneeLabel}</td>
                <td className="whitespace-nowrap px-3 py-3 text-slate-400">{ticket.updatedLabel}</td>
                <td className="px-3 py-3">{ticket.unread ? <span className="rounded-full bg-blue-500 px-2 py-0.5 text-xs font-bold text-white">да</span> : <span className="text-slate-600">—</span>}</td>
              </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {!sortedTickets.length ? (
        <div className="mt-4 rounded-xl border border-white/10 bg-white/[0.03] px-4 py-8 text-center text-sm text-slate-400">
          По текущим фильтрам тикеты не найдены.
        </div>
      ) : null}
      {selectedTicket ? <p className="mt-3 text-xs text-slate-500">Preview выбранного тикета открыт справа. Enter/кнопка в preview открывает полный чат.</p> : null}
    </section>
  );
}
