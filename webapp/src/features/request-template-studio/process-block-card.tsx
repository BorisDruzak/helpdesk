import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import type { ProcessBlock } from "./studio-model";
import { statusLabel, statusTone } from "./studio-model";

export function ProcessBlockCard({
  block,
  selected,
  onSelect,
}: {
  block: ProcessBlock;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <article
      className={`rounded-md border bg-white p-4 shadow-soft transition ${
        selected ? "border-brand-300 ring-2 ring-brand-100" : "border-slate-200 hover:border-brand-200"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <h3 className="text-sm font-semibold text-slate-950">{block.title}</h3>
        <Badge tone={statusTone(block.status)}>{statusLabel(block.status)}</Badge>
      </div>
      <p className="mt-2 min-h-10 text-sm text-slate-600">{block.explanation}</p>
      <Button className="mt-3 h-9 px-3 text-xs" onClick={onSelect} type="button" variant={selected ? "primary" : "secondary"}>
        {block.actionLabel}
      </Button>
    </article>
  );
}
