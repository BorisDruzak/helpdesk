import { Search } from "lucide-react";
import type { InputHTMLAttributes } from "react";

import { cn } from "../../shared/ui/cn";
import { Input } from "./input";

export function SearchField({
  className,
  ...props
}: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div className={cn("relative", className)}>
      <Search
        aria-hidden="true"
        className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
      />
      <Input className="pl-10 pr-16" type="search" {...props} />
      <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 rounded-full border border-border bg-white px-2 py-0.5 text-[11px] font-semibold text-slate-400">
        Ctrl K
      </span>
    </div>
  );
}
