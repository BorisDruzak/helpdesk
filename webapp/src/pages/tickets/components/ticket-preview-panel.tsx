import { Inbox } from "lucide-react";
import type { SupportWorkspaceSelectedTicket } from "../../../features/queues/support-workspace-model";
import { toneClasses } from "./workspace-component-utils";

type TicketPreviewPanelProps = {
  selectedTicket: SupportWorkspaceSelectedTicket | null;
  onOpenTicket: (ticketId: string) => void;
};

export function TicketPreviewPanel({ selectedTicket, onOpenTicket }: TicketPreviewPanelProps) {
  if (!selectedTicket) {
    return (
      <div className="flex flex-1 items-center justify-center px-6 text-center text-sm text-slate-400">
        <div>
          <Inbox className="mx-auto h-10 w-10 text-slate-500" />
          <p className="mt-4 font-semibold text-white">Выберите строку очереди</p>
          <p className="mt-1">Preview тикета появится здесь.</p>
        </div>
      </div>
    );
  }
  return (
    <section className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-5">
      <div className="rounded-xl border border-white/10 bg-[#111f33] p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-blue-200">{selectedTicket.code}</p>
            <h2 className="mt-1 text-xl font-semibold text-white">{selectedTicket.subject}</h2>
          </div>
          <button className="shrink-0 rounded-xl bg-blue-600 px-3 py-2 text-sm font-semibold text-white" onClick={() => onOpenTicket(selectedTicket.id)} type="button">
            Открыть тикет
          </button>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <span className={`rounded-md border px-2 py-1 text-xs font-bold ${toneClasses(selectedTicket.priorityTone)}`}>{selectedTicket.priority}</span>
          <span className={`rounded-md border px-2 py-1 text-xs font-semibold ${toneClasses(selectedTicket.statusTone)}`}>{selectedTicket.statusLabel}</span>
          <span className="rounded-md border border-white/10 bg-white/[0.04] px-2 py-1 text-xs text-slate-300">{selectedTicket.queueLabel}</span>
        </div>
        <p className="mt-4 text-sm leading-6 text-slate-300">{selectedTicket.description}</p>
      </div>
      <section className={`rounded-xl border p-4 ${toneClasses(selectedTicket.nextAction.tone)}`}>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-300">Следующее действие</p>
        <p className="mt-1 text-base font-semibold text-white">{selectedTicket.nextAction.label}</p>
        <p className="mt-1 text-sm text-slate-300">{selectedTicket.nextAction.hint}</p>
        <p className="mt-3 text-lg font-semibold text-white">{selectedTicket.nextAction.remainingLabel}</p>
      </section>
      <section className="rounded-xl border border-white/10 bg-[#111f33] p-4">
        <p className="font-semibold text-white">Последние события</p>
        <div className="mt-3 space-y-3">
          {selectedTicket.timeline.slice(0, 4).map((item) => (
            <div className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2" key={item.id}>
              <div className="flex justify-between gap-3 text-xs text-slate-500">
                <span>{item.actor}</span>
                <span>{item.timestampLabel}</span>
              </div>
              <p className="mt-1 text-sm font-semibold text-white">{item.title}</p>
              {item.body ? <p className="mt-1 text-xs leading-5 text-slate-400">{item.body}</p> : null}
            </div>
          ))}
          {!selectedTicket.timeline.length ? <p className="text-sm text-slate-400">Событий пока нет.</p> : null}
        </div>
      </section>
    </section>
  );
}
