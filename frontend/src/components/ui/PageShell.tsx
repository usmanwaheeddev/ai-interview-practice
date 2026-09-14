import type { ReactNode } from "react";
import { AppLayout } from "../layout/AppLayout";

/** Authenticated page frame. AppLayout owns global navigation and account
 * chrome; individual pages provide only their title, actions and content. */
export function PageShell({
  title,
  actions,
  children,
}: {
  title: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <AppLayout title={title} actions={actions}>
      {children}
    </AppLayout>
  );
}

/** Chrome for unauthenticated pages — no user/logout, just a centered shell. */
export function PublicShell({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="mx-auto flex min-h-screen w-full max-w-md flex-col gap-6 px-6 py-16">
      <h1 className="text-2xl font-semibold tracking-tight text-ink-900">{title}</h1>
      {children}
    </div>
  );
}
