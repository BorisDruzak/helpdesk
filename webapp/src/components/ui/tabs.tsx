import type { HTMLAttributes } from "react";

import { cn } from "../../shared/ui/cn";

type TabItem = {
  value: string;
  label: string;
  count?: string | number;
};

type TabsProps = HTMLAttributes<HTMLDivElement> & {
  items: TabItem[];
  onValueChange: (value: string) => void;
  value: string;
};

export function Tabs({ className, items, onValueChange, value, ...props }: TabsProps) {
  return (
    <div
      className={cn("flex flex-wrap items-center gap-2 rounded-pill bg-surface-subtle p-1", className)}
      {...props}
    >
      {items.map((item) => {
        const active = item.value === value;

        return (
          <button
            key={item.value}
            className={cn(
              "inline-flex min-w-[7.5rem] items-center justify-center gap-2 rounded-pill px-4 py-2 text-sm font-medium transition-colors",
              active ? "bg-white text-brand-800 shadow-soft" : "text-slate-500 hover:text-slate-900"
            )}
            onClick={() => onValueChange(item.value)}
            type="button"
          >
            <span>{item.label}</span>
            {item.count ? (
              <span className={cn("text-xs", active ? "text-brand-700" : "text-slate-400")}>
                {item.count}
              </span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
