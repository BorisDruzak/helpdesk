import type { ButtonHTMLAttributes, ReactNode } from "react";

import { cn } from "../../shared/ui/cn";

type ButtonVariant = "primary" | "secondary" | "ghost" | "outline";
type ButtonSize = "sm" | "md" | "lg" | "icon";

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    "bg-brand-600 text-white shadow-soft hover:bg-brand-700 active:bg-brand-800",
  secondary:
    "bg-surface-subtle text-slate-900 shadow-soft hover:bg-brand-50 hover:text-brand-800",
  ghost:
    "bg-transparent text-slate-600 hover:bg-slate-100 hover:text-slate-900",
  outline:
    "border border-border bg-white text-slate-700 hover:border-brand-200 hover:bg-brand-50 hover:text-brand-800"
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: "h-9 rounded-pill px-3 text-sm font-medium",
  md: "h-11 rounded-pill px-4 text-sm font-semibold",
  lg: "h-12 rounded-pill px-5 text-base font-semibold",
  icon: "h-11 w-11 rounded-pill"
};

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  leadingIcon?: ReactNode;
  trailingIcon?: ReactNode;
};

export function Button({
  className,
  disabled,
  leadingIcon,
  size = "md",
  trailingIcon,
  type = "button",
  variant = "primary",
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 whitespace-nowrap transition-colors duration-200 disabled:cursor-not-allowed disabled:opacity-60",
        variantClasses[variant],
        sizeClasses[size],
        className
      )}
      disabled={disabled}
      type={type}
      {...props}
    >
      {leadingIcon}
      {children}
      {trailingIcon}
    </button>
  );
}
