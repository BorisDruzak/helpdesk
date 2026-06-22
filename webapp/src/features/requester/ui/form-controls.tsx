import { forwardRef, type HTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";
import { AlertCircle, CheckCircle2, Info } from "lucide-react";

import { Button, type ButtonProps } from "../../../components/ui/button";
import { Input } from "../../../components/ui/input";
import { Select } from "../../../components/ui/select";
import { cn } from "../../../shared/ui/cn";

type FieldShellProps = {
  children: ReactNode;
  className?: string;
  error?: ReactNode;
  errorId?: string;
  helpText?: ReactNode;
  helpId?: string;
  label: ReactNode;
  required?: boolean;
};

export function FieldShell({ children, className, error, errorId, helpText, helpId, label, required }: FieldShellProps) {
  return (
    <label className={cn("block text-sm font-semibold text-slate-700", className)}>
      <span>
        {label}
        {required ? " *" : ""}
      </span>
      {children}
      {helpText ? <span className="mt-1 block text-xs font-normal text-slate-500" id={helpId}>{helpText}</span> : null}
      {error ? <span className="mt-1 block text-xs font-semibold text-rose-700" id={errorId}>{error}</span> : null}
    </label>
  );
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  function Textarea({ className, ...props }, ref) {
    return (
      <textarea
        ref={ref}
        className={cn("field-base min-h-24 w-full px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400", className)}
        {...props}
      />
    );
  }
);

export const SelectField = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement> & Omit<FieldShellProps, "children">>(
  function SelectField({ children, className, error, helpText, label, required, ...props }, ref) {
    return (
      <FieldShell className={className} error={error} helpText={helpText} label={label} required={required}>
        <Select className="mt-1 w-full font-normal" ref={ref} {...props}>
          {children}
        </Select>
      </FieldShell>
    );
  }
);

type InlineAlertTone = "info" | "success" | "warning" | "danger";

const inlineAlertTone: Record<InlineAlertTone, { icon: ReactNode; className: string; titleClassName: string }> = {
  info: {
    icon: <Info className="mt-0.5 h-4 w-4" />,
    className: "border-brand-100 bg-brand-50 text-brand-900",
    titleClassName: "text-brand-950",
  },
  success: {
    icon: <CheckCircle2 className="mt-0.5 h-4 w-4" />,
    className: "border-emerald-100 bg-emerald-50 text-emerald-900",
    titleClassName: "text-emerald-950",
  },
  warning: {
    icon: <AlertCircle className="mt-0.5 h-4 w-4" />,
    className: "border-amber-100 bg-amber-50 text-amber-900",
    titleClassName: "text-amber-950",
  },
  danger: {
    icon: <AlertCircle className="mt-0.5 h-4 w-4" />,
    className: "border-rose-100 bg-rose-50 text-rose-900",
    titleClassName: "text-rose-950",
  },
};

export function InlineAlert({
  children,
  className,
  title,
  tone = "info",
  ...props
}: HTMLAttributes<HTMLDivElement> & {
  children?: ReactNode;
  className?: string;
  title?: ReactNode;
  tone?: InlineAlertTone;
}) {
  const toneConfig = inlineAlertTone[tone];
  return (
    <div className={cn("flex gap-2 rounded-panel border px-3 py-2 text-sm", toneConfig.className, className)} {...props}>
      {toneConfig.icon}
      <div className="min-w-0">
        {title ? <p className={cn("font-semibold", toneConfig.titleClassName)}>{title}</p> : null}
        {children ? <div className={title ? "mt-1" : undefined}>{children}</div> : null}
      </div>
    </div>
  );
}

export function FormActions({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("flex flex-wrap items-center gap-2", className)}>{children}</div>;
}

export function StickyActionBar({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn("sticky bottom-0 z-10 -mx-4 flex flex-wrap items-center gap-3 border-t border-slate-200 bg-white/95 px-4 py-3 backdrop-blur", className)}>
      {children}
    </div>
  );
}

export function Stepper({
  current,
  onStepSelect,
  steps,
}: {
  current: string;
  onStepSelect?: (stepId: string) => void;
  steps: Array<{ disabled?: boolean; id: string; label: string }>;
}) {
  return (
    <ol className="grid gap-2 sm:grid-cols-[repeat(auto-fit,minmax(0,1fr))]">
      {steps.map((step, index) => {
        const active = step.id === current;
        const className = cn(
          "flex w-full items-center gap-2 rounded-panel border px-3 py-2 text-left text-sm font-semibold transition-colors",
          active ? "border-brand-200 bg-brand-50 text-brand-900" : "border-slate-200 bg-white text-slate-600",
          onStepSelect && !step.disabled ? "hover:border-brand-200 hover:text-brand-800" : "",
          step.disabled ? "cursor-not-allowed opacity-60" : "",
        );
        const content = (
          <>
            <span className={cn("grid h-6 w-6 shrink-0 place-items-center rounded-full text-xs", active ? "bg-brand-700 text-white" : "bg-slate-100 text-slate-600")}>
              {index + 1}
            </span>
            <span className="min-w-0 truncate">{step.label}</span>
          </>
        );
        return (
          <li key={step.id}>
            {onStepSelect ? (
              <button
                aria-current={active ? "step" : undefined}
                className={className}
                disabled={step.disabled}
                onClick={() => onStepSelect(step.id)}
                type="button"
              >
                {content}
              </button>
            ) : (
              <div aria-current={active ? "step" : undefined} className={className}>
                {content}
              </div>
            )}
          </li>
        );
      })}
    </ol>
  );
}

export { Button, Input, Select, type ButtonProps };
