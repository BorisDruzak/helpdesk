export type SupportQueueDisplayMode = "collapsed" | "compact" | "full";

export function SupportQueueModes({ mode, hasTicket, onChange }: {
  mode: SupportQueueDisplayMode; hasTicket: boolean; onChange: (mode: SupportQueueDisplayMode) => void;
}) {
  return <div className="support-queue-modes" role="group" aria-label="Режим очереди">
    {([
      ["collapsed", "Свернуть очередь", "Свёрнута"],
      ["compact", "Очередь рядом", "Рядом с тикетом"],
      ["full", "Полная очередь", "Вся очередь"],
    ] as const).map(([value, label, text]) => <button key={value} type="button" aria-label={label}
      aria-pressed={mode === value} disabled={!hasTicket && value !== "full"}
      title={!hasTicket && value !== "full" ? "Сначала откройте обращение из списка" : label}
      onClick={() => onChange(value)}>{text}</button>)}
  </div>;
}
