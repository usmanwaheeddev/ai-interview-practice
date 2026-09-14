import type { HTMLAttributes } from "react";

export function Card({ className = "", ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={`rounded-lg border border-ink-300/70 bg-white p-5 shadow-card ${className}`}
      {...props}
    />
  );
}
