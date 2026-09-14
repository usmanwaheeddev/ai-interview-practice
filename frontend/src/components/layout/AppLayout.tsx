import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { useAuth } from "../../lib/auth";

type IconName = "add" | "history" | "menu" | "panel" | "logout" | "language" | "code";

function Icon({ name, className = "h-5 w-5" }: { name: IconName; className?: string }) {
  const paths: Record<IconName, ReactNode> = {
    add: <path d="M12 5v14M5 12h14" />,
    history: <path d="M3 12a9 9 0 1 0 3-6.7L3 8m0-5v5h5M12 7v5l3 2" />,
    menu: <path d="M4 7h16M4 12h16M4 17h16" />,
    panel: <path d="M4 5h16v14H4zM9 5v14" />,
    logout: <path d="M10 17l5-5-5-5m5 5H3m11-7h5a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2h-5" />,
    language: <path d="M4 5h9M8.5 3v2m0 0c0 4-1.5 8-5.5 10M6 8c1 3 3 5 6 6.5M14 21l4-9 4 9m-6.5-3h5" />,
    code: <path d="M8 5l-6 7 6 7M16 5l6 7-6 7" />,
  };

  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {paths[name]}
    </svg>
  );
}

const navigation = [
  { label: "New interview", to: "/practice/new", icon: "add" as const },
  { label: "Language interview", to: "/practice/language/new", icon: "language" as const },
  { label: "Interview history", to: "/mock-interviews", icon: "history" as const },
  { label: "Coding challenges", to: "/coding", icon: "code" as const },
];

export function AppLayout({
  title,
  actions,
  children,
}: {
  title: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  const { user, logout } = useAuth();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => setMobileOpen(false), [location.pathname]);

  const initials = useMemo(
    () =>
      (user?.full_name ?? "User")
        .split(/\s+/)
        .slice(0, 2)
        .map((part) => part[0])
        .join("")
        .toUpperCase(),
    [user?.full_name],
  );

  const renderSidebar = (isCollapsed: boolean) => (
    <>
      <div className="flex h-20 items-center border-b border-white/10 px-4">
        <Link to="/practice/new" className="flex min-w-0 items-center gap-3 rounded-lg focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-indigo-400">
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-indigo-500 text-sm font-bold text-white shadow-lg shadow-indigo-950/30">
            AI
          </span>
          {!isCollapsed && (
            <span className="truncate text-[0.95rem] font-semibold tracking-tight text-white">
              Interview Studio
            </span>
          )}
        </Link>
      </div>

      <nav className="flex-1 space-y-1.5 px-3 py-5" aria-label="Primary navigation">
        {!isCollapsed && (
          <p className="mb-3 px-3 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
            Workspace
          </p>
        )}
        {navigation.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            title={isCollapsed ? item.label : undefined}
            className={({ isActive }) =>
              `group flex min-h-11 items-center gap-3 rounded-xl px-3 text-sm font-medium transition-all duration-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400 ${
                isActive
                  ? "bg-white/10 text-white shadow-sm ring-1 ring-inset ring-white/10"
                  : "text-slate-400 hover:bg-white/[0.06] hover:text-slate-100"
              }`
            }
          >
            <Icon name={item.icon} className="h-5 w-5 shrink-0" />
            {!isCollapsed && <span>{item.label}</span>}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-white/10 p-3">
        <div className={`flex items-center ${isCollapsed ? "justify-center" : "gap-3"}`}>
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-gradient-to-br from-indigo-400 to-violet-600 text-xs font-semibold text-white ring-2 ring-slate-800">
            {initials}
          </span>
          {!isCollapsed && (
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-slate-100">{user?.full_name}</p>
              <p className="truncate text-xs text-slate-500">{user?.email}</p>
            </div>
          )}
          {!isCollapsed && (
            <button
              type="button"
              onClick={() => void logout()}
              className="rounded-lg p-2 text-slate-500 transition-colors hover:bg-white/10 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-400"
              aria-label="Log out"
              title="Log out"
            >
              <Icon name="logout" className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>
    </>
  );

  return (
    <div className="min-h-screen bg-slate-50 text-slate-950">
      <aside
        className={`fixed inset-y-0 left-0 z-30 hidden flex-col bg-slate-950 transition-[width] duration-300 ease-out lg:flex ${collapsed ? "w-[4.5rem]" : "w-64"}`}
      >
        {renderSidebar(collapsed)}
        <button
          type="button"
          onClick={() => setCollapsed((value) => !value)}
          className="absolute -right-3 top-[5.25rem] grid h-7 w-7 place-items-center rounded-full border border-slate-200 bg-white text-slate-500 shadow-md transition-colors hover:text-indigo-600 focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-500"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          <Icon name="panel" className="h-3.5 w-3.5" />
        </button>
      </aside>

      {mobileOpen && (
        <button
          className="fixed inset-0 z-40 bg-slate-950/50 backdrop-blur-sm lg:hidden"
          onClick={() => setMobileOpen(false)}
          aria-label="Close navigation"
        />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-50 flex w-72 flex-col bg-slate-950 shadow-2xl transition-transform duration-300 ease-out lg:hidden ${mobileOpen ? "translate-x-0" : "-translate-x-full"}`}
        aria-hidden={!mobileOpen}
      >
        {renderSidebar(false)}
      </aside>

      <div className={`transition-[padding] duration-300 ease-out ${collapsed ? "lg:pl-[4.5rem]" : "lg:pl-64"}`}>
        <header className="sticky top-0 z-20 border-b border-slate-200/80 bg-white/85 backdrop-blur-xl">
          <div className="flex h-20 items-center gap-4 px-5 sm:px-8 lg:px-10">
            <button
              type="button"
              onClick={() => setMobileOpen(true)}
              className="rounded-xl border border-slate-200 bg-white p-2.5 text-slate-600 shadow-sm transition-colors hover:bg-slate-50 hover:text-slate-950 focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-500 lg:hidden"
              aria-label="Open navigation"
            >
              <Icon name="menu" />
            </button>
            <div className="min-w-0 flex-1">
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-indigo-600">Practice workspace</p>
              <h1 className="truncate text-xl font-semibold tracking-tight text-slate-950 sm:text-2xl">{title}</h1>
            </div>
            {actions && <div className="flex shrink-0 items-center gap-3">{actions}</div>}
          </div>
        </header>

        <main className="relative min-h-[calc(100vh-5rem)] overflow-hidden px-5 py-8 sm:px-8 lg:px-10 lg:py-10">
          <div className="pointer-events-none absolute right-0 top-0 h-80 w-80 -translate-y-1/2 translate-x-1/3 rounded-full bg-indigo-100/60 blur-3xl" />
          <div className="relative mx-auto w-full max-w-6xl">{children}</div>
        </main>
      </div>
    </div>
  );
}
