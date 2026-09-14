export function Alert({ children }: { children: React.ReactNode }) {
  return (
    <p
      role="alert"
      className="rounded border border-danger-600/20 bg-danger-50 px-3 py-2 text-sm text-danger-700"
    >
      {children}
    </p>
  );
}
