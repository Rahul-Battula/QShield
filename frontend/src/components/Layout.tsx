import type { ReactNode } from "react";

function Shield() {
  return (
    <svg viewBox="0 0 24 24" className="h-7 w-7" aria-hidden>
      <defs>
        <linearGradient id="sg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#8fd0ff" />
          <stop offset="1" stopColor="#3d7fd6" />
        </linearGradient>
      </defs>
      <path d="M12 2.4l7.4 2.8v5.7c0 4.8-3.1 8.1-7.4 9.6-4.3-1.5-7.4-4.8-7.4-9.6V5.2z"
        fill="none" stroke="url(#sg)" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M12 9a2 2 0 00-1 3.8V15h2v-2.2A2 2 0 0012 9z" fill="url(#sg)" />
    </svg>
  );
}

export interface Tab { id: string; label: string }

export function Layout({
  tabs, active, onTab, children,
}: { tabs: Tab[]; active: string; onTab: (id: string) => void; children: ReactNode }) {
  return (
    <div className="grid min-h-screen grid-cols-1 md:grid-cols-[236px_1fr]">
      <aside className="sticky top-0 z-10 flex h-screen flex-col gap-7 border-r border-white/[0.06]
        bg-gradient-to-b from-ink-900 to-ink-950/80 px-4 py-6 md:h-screen
        max-md:h-auto max-md:flex-row max-md:items-center max-md:overflow-x-auto">
        <div className="flex items-center gap-3 px-1.5">
          <Shield />
          <div>
            <div className="text-[15px] font-semibold tracking-tight">QShield</div>
            <div className="text-[10px] uppercase tracking-[0.13em] text-fg-faint">Command Centre</div>
          </div>
        </div>
        <nav className="flex flex-col gap-1 max-md:flex-row">
          {tabs.map((t) => (
            <button key={t.id} onClick={() => onTab(t.id)}
              className={`relative flex items-center gap-2.5 rounded-lg px-3 py-2 text-[13px]
                font-medium transition ${
                  active === t.id
                    ? "bg-brand/10 text-fg"
                    : "text-fg-muted hover:bg-white/[0.03] hover:text-fg"
                }`}>
              {active === t.id && (
                <span className="absolute -left-4 top-2 bottom-2 w-[3px] rounded-r bg-brand max-md:hidden" />
              )}
              <span className={`h-1.5 w-1.5 rounded-full ${active === t.id ? "bg-brand" : "bg-current opacity-40"}`} />
              {t.label}
            </button>
          ))}
        </nav>
        <div className="mt-auto px-1.5 text-[11px] leading-relaxed text-fg-faint max-md:hidden">
          Post-quantum cryptography<br />migration, six phases.
        </div>
      </aside>

      <main className="mx-auto w-full max-w-[1180px] px-6 py-8 md:px-10">{children}</main>
    </div>
  );
}
