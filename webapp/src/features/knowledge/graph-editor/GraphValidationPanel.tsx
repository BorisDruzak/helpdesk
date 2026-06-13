type GraphValidationPanelProps = {
  connectionMessages: string[];
  duplicateCount: number;
  orphanCount: number;
  validationMessages: string[];
};

export function GraphValidationPanel({ connectionMessages, duplicateCount, orphanCount, validationMessages }: GraphValidationPanelProps) {
  const hasErrors = connectionMessages.length > 0 || duplicateCount > 0;
  return (
    <section className={`rounded-lg border p-4 ${hasErrors ? "border-amber-200 bg-amber-50" : "border-emerald-100 bg-emerald-50"}`}>
      <h3 className="text-sm font-semibold text-slate-950">Проверки графа</h3>
      <div className="mt-3 space-y-2 text-xs leading-5">
        {validationMessages.map((message) => (
          <p className={message.includes("Нет") ? "text-emerald-800" : "text-amber-800"} key={message}>
            {message.includes("Нет") ? "✓" : "!"} {message}
          </p>
        ))}
        {connectionMessages.map((message) => (
          <p className="font-semibold text-rose-700" key={message}>
            ! {message}
          </p>
        ))}
      </div>
      <p className="mt-3 text-[11px] leading-5 text-slate-500">Self-loop и дубли блокируются до вызова API. Ошибки показываются рядом с черновиком связи.</p>
    </section>
  );
}
