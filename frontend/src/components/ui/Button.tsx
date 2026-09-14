import { type ButtonHTMLAttributes, forwardRef } from "react";

type Variant = "primary" | "secondary" | "danger" | "ghost";

const variantClasses: Record<Variant, string> = {
  primary:
    "bg-brand-600 text-white hover:bg-brand-700 focus-visible:outline-brand-600 disabled:bg-brand-600",
  secondary:
    "bg-white text-ink-900 border border-ink-300 hover:bg-ink-100 focus-visible:outline-brand-600",
  danger:
    "bg-danger-600 text-white hover:bg-danger-700 focus-visible:outline-danger-600",
  ghost:
    "bg-transparent text-ink-700 hover:bg-ink-100 focus-visible:outline-brand-600",
};

export const Button = forwardRef<
  HTMLButtonElement,
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }
>(function Button({ variant = "primary", className = "", ...props }, ref) {
  return (
    <button
      ref={ref}
      className={`inline-flex w-fit cursor-pointer items-center justify-center gap-2 rounded px-4 py-2 text-sm font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-50 ${variantClasses[variant]} ${className}`}
      {...props}
    />
  );
});
