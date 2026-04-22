import type { HTMLAttributes } from "react";

import { cn } from "../../shared/ui/cn";

function deriveInitials(value: string) {
  return value
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

type AvatarProps = HTMLAttributes<HTMLDivElement> & {
  name: string;
  tone?: "brand" | "agent" | "client" | "neutral";
};

const toneClasses: Record<NonNullable<AvatarProps["tone"]>, string> = {
  brand: "bg-brand-600/12 text-brand-800",
  agent: "bg-blue-100 text-blue-700",
  client: "bg-emerald-100 text-emerald-700",
  neutral: "bg-slate-100 text-slate-600"
};

export function Avatar({
  className,
  name,
  tone = "neutral",
  ...props
}: AvatarProps) {
  return (
    <div
      aria-hidden="true"
      className={cn(
        "flex h-11 w-11 items-center justify-center rounded-full text-sm font-semibold",
        toneClasses[tone],
        className
      )}
      {...props}
    >
      {deriveInitials(name)}
    </div>
  );
}
