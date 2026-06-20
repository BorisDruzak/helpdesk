import { useId, type HTMLAttributes, type ReactNode } from "react";

import { cn } from "../../shared/ui/cn";
import { Badge, type BadgeProps, type BadgeTone } from "../ui/badge";
import { Button } from "../ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/card";
import { formatStatusLabel, statusBadgeTone } from "./formatters";

type PageShellWidth = "default" | "wide" | "full";

const shellWidths: Record<PageShellWidth, string> = {
  default: "max-w-5xl",
  wide: "max-w-7xl",
  full: "max-w-none",
};

export type PageShellProps = HTMLAttributes<HTMLElement> & {
  ariaLabelledBy?: string;
  as?: "main" | "div" | "section";
  children: ReactNode;
  width?: PageShellWidth;
};

export function PageShell({
  ariaLabelledBy,
  as = "div",
  children,
  className,
  width = "wide",
  ...props
}: PageShellProps) {
  const ShellElement = as;
  return (
    <ShellElement
      aria-labelledby={ariaLabelledBy}
      className={cn("min-w-0 px-4 py-6 sm:px-6 lg:px-8", className)}
      {...props}
    >
      <div className={cn("mx-auto flex min-w-0 flex-col gap-6", shellWidths[width])}>{children}</div>
    </ShellElement>
  );
}

export type PageActionsProps = HTMLAttributes<HTMLDivElement> & {
  children: ReactNode;
  label?: string;
};

export function PageActions({ children, className, label = "Действия", ...props }: PageActionsProps) {
  return (
    <div
      aria-label={label}
      className={cn("flex min-w-0 flex-wrap items-center justify-start gap-2 sm:justify-end", className)}
      role="group"
      {...props}
    >
      {children}
    </div>
  );
}

export type PageHeaderProps = HTMLAttributes<HTMLElement> & {
  actions?: ReactNode;
  description?: ReactNode;
  eyebrow?: ReactNode;
  title: ReactNode;
};

export function PageHeader({
  actions,
  className,
  description,
  eyebrow,
  title,
  ...props
}: PageHeaderProps) {
  return (
    <header
      className={cn("flex min-w-0 flex-col gap-4 border-b border-border/70 pb-5 lg:flex-row lg:items-end lg:justify-between", className)}
      {...props}
    >
      <div className="min-w-0">
        {eyebrow ? <p className="text-sm font-semibold text-brand-700">{eyebrow}</p> : null}
        <h1 className="mt-1 text-2xl font-semibold tracking-normal text-slate-950">{title}</h1>
        {description ? <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">{description}</p> : null}
      </div>
      {actions ? <div className="min-w-0 shrink-0">{actions}</div> : null}
    </header>
  );
}

export type ContentSectionProps = HTMLAttributes<HTMLElement> & {
  actions?: ReactNode;
  children: ReactNode;
  description?: ReactNode;
  title: ReactNode;
};

export function ContentSection({
  actions,
  children,
  className,
  description,
  title,
  ...props
}: ContentSectionProps) {
  const generatedId = useId();
  const titleId = props.id ? `${props.id}-title` : generatedId;
  return (
    <section
      aria-labelledby={titleId}
      className={cn("min-w-0 space-y-4", className)}
      role="region"
      {...props}
    >
      <div className="flex min-w-0 flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h2 className="text-lg font-semibold tracking-normal text-slate-950" id={titleId}>
            {title}
          </h2>
          {description ? <p className="mt-1 text-sm leading-6 text-slate-600">{description}</p> : null}
        </div>
        {actions ? <div className="min-w-0 shrink-0">{actions}</div> : null}
      </div>
      {children}
    </section>
  );
}

export type ActionCardProps = HTMLAttributes<HTMLElement> & {
  action?: ReactNode;
  description?: ReactNode;
  meta?: ReactNode;
  title: ReactNode;
};

export function ActionCard({ action, className, description, meta, title, ...props }: ActionCardProps) {
  const titleId = useId();
  return (
    <Card aria-labelledby={titleId} className={cn("h-full", className)} role="article" {...props}>
      <CardHeader className="p-5">
        <div className="flex min-w-0 items-start justify-between gap-4">
          <div className="min-w-0">
            <CardTitle id={titleId}>{title}</CardTitle>
            {description ? <CardDescription>{description}</CardDescription> : null}
          </div>
          {meta ? <div className="shrink-0">{meta}</div> : null}
        </div>
      </CardHeader>
      {action ? <CardContent className="px-5 pb-5">{action}</CardContent> : null}
    </Card>
  );
}

export type StatCardProps = HTMLAttributes<HTMLDivElement> & {
  helper?: ReactNode;
  label: ReactNode;
  status?: ReactNode;
  value: ReactNode;
};

export function StatCard({ className, helper, label, status, value, ...props }: StatCardProps) {
  return (
    <Card className={cn("px-5 py-4", className)} {...props}>
      <div className="flex min-w-0 items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-sm text-slate-500">{label}</p>
          <p className="mt-2 text-2xl font-semibold tracking-normal text-slate-950">{value}</p>
          {helper ? <p className="mt-2 text-xs leading-5 text-slate-500">{helper}</p> : null}
        </div>
        {status ? <div className="shrink-0">{status}</div> : null}
      </div>
    </Card>
  );
}

export type StatusBadgeProps = Omit<BadgeProps, "children" | "tone"> & {
  label?: ReactNode;
  status: string | null | undefined;
  tone?: BadgeTone;
};

export function StatusBadge({ label, status, tone, withDot = true, ...props }: StatusBadgeProps) {
  return (
    <Badge tone={tone ?? statusBadgeTone(status)} withDot={withDot} {...props}>
      {label ?? formatStatusLabel(status)}
    </Badge>
  );
}

export type EmptyStateProps = HTMLAttributes<HTMLDivElement> & {
  action?: ReactNode;
  description?: ReactNode;
  title: ReactNode;
};

export function EmptyState({ action, className, description, title, ...props }: EmptyStateProps) {
  return (
    <div className={cn("surface-panel flex min-h-40 flex-col items-start justify-center p-6", className)} {...props}>
      <h3 className="text-base font-semibold text-slate-950">{title}</h3>
      {description ? <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">{description}</p> : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

export type LoadingStateProps = HTMLAttributes<HTMLDivElement> & {
  label?: string;
};

export function LoadingState({ className, label = "Загрузка", ...props }: LoadingStateProps) {
  return (
    <div
      aria-live="polite"
      className={cn("flex min-h-32 items-center gap-3 rounded-panel border border-border/80 bg-white px-5 py-4 text-sm text-slate-600", className)}
      role="status"
      {...props}
    >
      <span aria-hidden="true" className="h-3 w-3 rounded-full bg-brand-500 shadow-[0_0_0_6px_rgba(21,114,67,0.12)]" />
      {label}
    </div>
  );
}

export type PageSkeletonProps = HTMLAttributes<HTMLDivElement> & {
  sections?: number;
  title?: string;
};

export function PageSkeleton({ className, sections = 3, title = "Загрузка страницы", ...props }: PageSkeletonProps) {
  return (
    <div
      aria-busy="true"
      aria-live="polite"
      className={cn("space-y-4", className)}
      role="status"
      {...props}
    >
      <p className="sr-only">{title}</p>
      <div className="h-8 w-56 animate-pulse rounded-md bg-slate-200" />
      {Array.from({ length: Math.max(1, sections) }, (_, index) => (
        <div className="surface-panel space-y-3 p-5" key={index}>
          <div className="h-4 w-1/3 animate-pulse rounded bg-slate-200" />
          <div className="h-4 w-3/4 animate-pulse rounded bg-slate-100" />
          <div className="h-4 w-1/2 animate-pulse rounded bg-slate-100" />
        </div>
      ))}
    </div>
  );
}

export type ErrorStateProps = HTMLAttributes<HTMLDivElement> & {
  message: ReactNode;
  onRetry?: () => void;
  retryLabel?: string;
  title?: ReactNode;
};

export function ErrorState({
  className,
  message,
  onRetry,
  retryLabel = "Повторить",
  title = "Не удалось загрузить данные",
  ...props
}: ErrorStateProps) {
  return (
    <div
      className={cn("surface-panel border-rose-200 bg-rose-50/70 p-6 text-rose-950", className)}
      role="alert"
      {...props}
    >
      <h3 className="text-base font-semibold">{title}</h3>
      <p className="mt-2 text-sm leading-6">{message}</p>
      {onRetry ? (
        <Button className="mt-4" onClick={onRetry} size="sm" variant="outline">
          {retryLabel}
        </Button>
      ) : null}
    </div>
  );
}
