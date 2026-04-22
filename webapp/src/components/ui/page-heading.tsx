import type { ReactNode } from "react";

import { cn } from "../../shared/ui/cn";

type PageHeadingProps = {
  actions?: ReactNode;
  className?: string;
  description: string;
  eyebrow: string;
  title: string;
};

export function PageHeading({
  actions,
  className,
  description,
  eyebrow,
  title
}: PageHeadingProps) {
  return (
    <div className={cn("flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between", className)}>
      <div className="max-w-3xl">
        <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-brand-700">{eyebrow}</p>
        <h1 className="mt-3 font-display text-3xl font-semibold tracking-tight text-slate-950 md:text-4xl">
          {title}
        </h1>
        <p className="mt-3 text-sm leading-7 text-slate-500 md:text-base">{description}</p>
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-3">{actions}</div> : null}
    </div>
  );
}
