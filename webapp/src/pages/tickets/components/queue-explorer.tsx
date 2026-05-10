import type { SupportWorkspaceSelectedTicket, SupportWorkspaceTicketItem } from "../../../features/queues/support-workspace-model";
import { toneClasses } from "./workspace-component-utils";

type QueueExplorerProps = {
  selectedTicket: SupportWorkspaceSelectedTicket | null;
  tickets: SupportWorkspaceTicketItem[];
  onOpenTicket: (ticketId: string) => void;
  onSelectTicket: (ticketId: string) => void;
};

export function QueueExplorer({ selectedTicket, tickets, onOpenTicket, onSelectTicket }: QueueExplorerProps) {
  return (
    <section className="flex min-h-0 flex-1 flex-col px-4 py-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-white">Очередь тикетов</h2>
          <p className="mt-1 text-sm text-slate-400">Расширенный список для triage без открытия чата как основной области.</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <button className="rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2 text-xs font-semibold text-slate-300" disabled type="button">
            Массовые действия
          </button>
          {selectedTicket ? (
            <button className="rounded-xl bg-blue-600 px-3 py-2 text-xs font-semibold text-white" onClick={() => onOpenTicket(selectedTicket.id)} type="button">
              Открыть тикет
            </button>
          ) : null}
        </div>
      </div>
      <div className="mt-4 min-h-0 flex-1 overflow-auto rounded-xl border border-white/10 bg-[#0d1828]">
        <table className="min-w-[920px] w-full border-collapse text-left text-sm">
          <thead className="sticky top-0 z-10 bg-[#101d30] text-xs uppercase tracking-[0.14em] text-slate-500">
            <tr>
              <th className="w-10 px-3 py-3">
                <input aria-label="Выбрать все тикеты" disabled type="checkbox" />
              </th>
              <th className="px-3 py-3">№ тикета</th>
              <th className="px-3 py-3">Тема</th>
              <th className="px-3 py-3">Заявитель</th>
              <th className="px-3 py-3">Приоритет</th>
              <th className="px-3 py-3">Статус</th>
              <th className="px-3 py-3">SLA</th>
              <th className="px-3 py-3">Очередь</th>
              <th className="px-3 py-3">Исполнитель</th>
              <th className="px-3 py-3">Возраст</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/10">
            {tickets.map((ticket) => (
              <tr
                className={`cursor-pointer transition ${ticket.active ? "bg-blue-600/15 text-white" : "text-slate-300 hover:bg-white/[0.04]"}`}
                key={ticket.id}
                onClick={() => onSelectTicket(ticket.id)}
              >
                <td className="px-3 py-3">
                  <input aria-label={`Выбрать ${ticket.code}`} onClick={(event) => event.stopPropagation()} type="checkbox" />
                </td>
                <td className="whitespace-nowrap px-3 py-3 font-semibold text-blue-200">{ticket.code}</td>
                <td className="max-w-[260px] truncate px-3 py-3 font-semibold text-white" title={ticket.subject}>{ticket.subject}</td>
                <td className="max-w-[180px] truncate px-3 py-3" title={ticket.requester}>{ticket.requester}</td>
                <td className="px-3 py-3">
                  <span className={`rounded-md border px-2 py-1 text-xs font-bold ${toneClasses(ticket.priorityTone)}`}>{ticket.priority}</span>
                </td>
                <td className="px-3 py-3">
                  <span className={`rounded-md border px-2 py-1 text-xs font-semibold ${toneClasses(ticket.statusTone)}`}>{ticket.statusLabel}</span>
                </td>
                <td className={`whitespace-nowrap px-3 py-3 text-xs font-semibold ${ticket.slaRisk ? "text-red-300" : "text-emerald-300"}`}>
                  {ticket.nextDueLabel}
                </td>
                <td className="px-3 py-3">{ticket.queueLabel}</td>
                <td className="px-3 py-3">{ticket.assigneeLabel}</td>
                <td className="whitespace-nowrap px-3 py-3 text-slate-400">{ticket.updatedLabel}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!tickets.length ? (
        <div className="mt-4 rounded-xl border border-white/10 bg-white/[0.03] px-4 py-8 text-center text-sm text-slate-400">
          По текущим фильтрам тикеты не найдены.
        </div>
      ) : null}
    </section>
  );
}
