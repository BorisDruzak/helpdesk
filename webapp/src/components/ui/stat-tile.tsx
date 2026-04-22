import type { ReactNode } from "react";

import { cn } from "../../shared/ui/cn";

type StatTileProps = {
  accent?: ReactNode;
  className?: string;
  helper?: string;
  label: string;
  value: string;
};

export function StatTile({
  accent,
  className,
  helper,
  label,
  value
}: StatTileProps) {
  return (
    <div className={cn("surface-panel px-5 py-4", className)}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm text-slate-500">{label}</p>
          <p className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">{value}</p>
          {helper ? <p className="mt-2 text-xs text-slate-400">{helper}</p> : null}
        </div>
        {accent}
      </div>
    </div>
  );
}
