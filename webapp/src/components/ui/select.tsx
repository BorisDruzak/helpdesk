import { forwardRef, type SelectHTMLAttributes } from "react";

import { cn } from "../../shared/ui/cn";

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  function Select({ className, children, ...props }, ref) {
    return (
      <select
        ref={ref}
        className={cn(
          "field-base h-11 appearance-none px-4 pr-10 text-sm text-slate-900",
          className
        )}
        {...props}
      >
        {children}
      </select>
    );
  }
);
