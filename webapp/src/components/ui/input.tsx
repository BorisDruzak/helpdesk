import { forwardRef, type InputHTMLAttributes } from "react";

import { cn } from "../../shared/ui/cn";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className, ...props }, ref) {
    return (
      <input
        ref={ref}
        className={cn(
          "field-base h-11 px-4 text-sm text-slate-900 placeholder:text-slate-400",
          className
        )}
        {...props}
      />
    );
  }
);
