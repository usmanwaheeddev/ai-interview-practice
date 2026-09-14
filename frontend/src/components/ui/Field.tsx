import {
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
  forwardRef,
} from "react";

const fieldClasses =
  "w-full rounded border border-ink-300 bg-white px-3 py-2 text-sm text-ink-900 placeholder:text-ink-500 focus:border-brand-500 focus:outline focus:outline-2 focus:outline-brand-200 disabled:bg-ink-100 disabled:text-ink-500";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className = "", ...props }, ref) {
    return <input ref={ref} className={`${fieldClasses} ${className}`} {...props} />;
  },
);

export const Select = forwardRef<
  HTMLSelectElement,
  SelectHTMLAttributes<HTMLSelectElement>
>(function Select({ className = "", ...props }, ref) {
  return <select ref={ref} className={`${fieldClasses} ${className}`} {...props} />;
});

export const Textarea = forwardRef<
  HTMLTextAreaElement,
  TextareaHTMLAttributes<HTMLTextAreaElement>
>(function Textarea({ className = "", ...props }, ref) {
  return <textarea ref={ref} className={`${fieldClasses} ${className}`} {...props} />;
});

/** Wraps a field in a <label> so the association is implicit nesting, same
 * as the plain-HTML markup this replaces — no id/htmlFor wiring needed. */
export function Field({ label, hint, children }: { label: ReactNode; hint?: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5 text-sm">
      <span className="font-medium text-ink-700">{label}</span>
      {children}
      {hint && <span className="text-xs font-normal text-ink-500">{hint}</span>}
    </label>
  );
}
