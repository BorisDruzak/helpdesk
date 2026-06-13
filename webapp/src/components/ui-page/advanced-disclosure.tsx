import type { ReactNode } from "react";

type AdvancedDisclosureProps = {
  children: ReactNode;
  description?: string;
  title?: string;
};

export function AdvancedDisclosure({ children, description, title = "Advanced" }: AdvancedDisclosureProps) {
  return (
    <details className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
      <summary className="cursor-pointer text-sm font-semibold text-slate-800">{title}</summary>
      {description ? <p className="mt-2 text-xs leading-5 text-slate-500">{description}</p> : null}
      <div className="mt-3 space-y-3">{children}</div>
    </details>
  );
}
