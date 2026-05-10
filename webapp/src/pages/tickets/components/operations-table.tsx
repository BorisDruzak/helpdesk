import type { SupportWorkspaceOperationSummary } from "../../../features/queues/support-workspace-model";
import { toneClasses } from "./workspace-component-utils";

type OperationsTableProps = {
  operations: SupportWorkspaceOperationSummary[];
  onCancel: (operationId: string) => void;
  onRetry: (operationId: string) => void;
};

export function OperationsTable({ operations, onCancel, onRetry }: OperationsTableProps) {
  if (!operations.length) {
    return (
      <p className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-8 text-center text-sm text-slate-400">
        Операций по тикету пока нет.
      </p>
    );
  }
  return (
    <div className="overflow-auto rounded-xl border border-white/10 bg-[#0d1828]">
      <table className="min-w-[880px] w-full text-left text-sm">
        <thead className="bg-[#101d30] text-xs uppercase tracking-[0.14em] text-slate-500">
          <tr>
            <th className="px-3 py-3">Операция</th>
            <th className="px-3 py-3">Статус</th>
            <th className="px-3 py-3">Начало</th>
            <th className="px-3 py-3">Завершение</th>
            <th className="px-3 py-3">Повторы</th>
            <th className="px-3 py-3">Trace</th>
            <th className="px-3 py-3">Действия</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/10">
          {operations.map((operation) => (
            <tr className="text-slate-300" key={operation.id}>
              <td className="max-w-[220px] px-3 py-3">
                <p className="truncate font-semibold text-white">{operation.title}</p>
                {operation.summary ? <p className="mt-1 line-clamp-2 text-xs text-slate-500">{operation.summary}</p> : null}
              </td>
              <td className="px-3 py-3">
                <span className={`rounded-md border px-2 py-1 text-xs font-semibold ${toneClasses(operation.statusTone)}`}>
                  Статус: {operation.statusLabel}
                </span>
              </td>
              <td className="px-3 py-3 text-xs">{operation.queuedOrStartedLabel}</td>
              <td className="px-3 py-3 text-xs">{operation.finishedLabel ?? "В процессе"}</td>
              <td className="px-3 py-3 text-xs">{operation.metaLabels.find((label) => label.startsWith("Повторы"))?.replace(/^Повторы:\s*/, "") ?? "Нет"}</td>
              <td className="px-3 py-3 text-xs">
                {operation.traceUrl ? <a className="text-blue-200 hover:text-blue-100" href={operation.traceUrl}>{operation.traceRelationLabel}</a> : "Нет trace"}
              </td>
              <td className="px-3 py-3">
                <div className="flex gap-2">
                  <button className="rounded-lg border border-white/10 px-2 py-1 text-xs font-semibold text-slate-200 disabled:opacity-50" disabled={!operation.canRetry} onClick={() => onRetry(operation.id)} type="button">
                    Повторить
                  </button>
                  <button className="rounded-lg border border-white/10 px-2 py-1 text-xs font-semibold text-slate-200 disabled:opacity-50" disabled={!operation.canCancel} onClick={() => onCancel(operation.id)} type="button">
                    Отменить
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
