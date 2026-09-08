import type { ReactNode } from "react";
import type { AsyncState } from "../lib/hooks";

export const EXPO: Record<string, [string, string]> = {
  CLASSICALLY_BROKEN: ["text-crit bg-crit/10", "BROKEN NOW"],
  QUANTUM_BROKEN: ["text-high bg-high/10", "QUANTUM-BROKEN"],
  QUANTUM_WEAKENED: ["text-med bg-med/10", "WEAKENED"],
  QUANTUM_SAFE: ["text-ok bg-ok/10", "SAFE"],
  UNKNOWN: ["text-fg-muted bg-white/5", "UNKNOWN"],
};
export const BAND: Record<string, string> = {
  P1: "text-crit bg-crit/10", P2: "text-high bg-high/10",
  P3: "text-med bg-med/10", P4: "text-ok bg-ok/10",
  High: "text-crit bg-crit/10", Medium: "text-high bg-high/10", Low: "text-ok bg-ok/10",
};

export function Pill({ tone, plain, children }: { tone: string; plain?: boolean; children: ReactNode }) {
  return <span className={`pill ${tone} ${plain ? "pill-plain" : ""}`}>{children}</span>;
}

export function PageHead({ title, desc }: { title: string; desc: string }) {
  return (
    <header className="mb-6 animate-fade-up">
      <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
      <p className="mt-1 max-w-[70ch] text-[13px] text-fg-muted">{desc}</p>
    </header>
  );
}

export function Panel({
  title, hint, actions, flush, children,
}: { title?: string; hint?: string; actions?: ReactNode; flush?: boolean; children: ReactNode }) {
  return (
    <section className="panel mb-4 animate-fade-up">
      {(title || actions) && (
        <div className={`flex items-baseline justify-between gap-3 ${flush ? "px-5 pt-4" : "px-5 pt-4"}`}>
          <h2 className="text-[13px] font-semibold tracking-tight">{title}</h2>
          <div className="flex items-center gap-2">
            {hint && <span className="text-[11px] text-fg-faint">{hint}</span>}
            {actions}
          </div>
        </div>
      )}
      <div className={flush ? "mt-3" : "panel-pad pt-3"}>{children}</div>
    </section>
  );
}

export interface Kpi { label: string; value: ReactNode; sub?: string; tone?: "brand" | "crit" | "ok" | "" }
export function Kpis({ items }: { items: Kpi[] }) {
  const toneClass: Record<string, string> = {
    brand: "text-brand", crit: "text-crit", ok: "text-ok", "": "",
  };
  return (
    <div className="mb-5 grid gap-3 [grid-template-columns:repeat(auto-fit,minmax(150px,1fr))]">
      {items.map((k, i) => (
        <div key={i} className="panel px-4 py-3.5 animate-fade-up" style={{ animationDelay: `${i * 30}ms` }}>
          <div className="kpi-label mb-2">{k.label}</div>
          <div className={`stat ${toneClass[k.tone ?? ""]}`}>{k.value}</div>
          {k.sub && <div className="mt-1.5 text-[11.5px] text-fg-faint">{k.sub}</div>}
        </div>
      ))}
    </div>
  );
}

export interface Col { label: string; className?: string }
export function DataTable({ cols, rows }: { cols: Col[]; rows: ReactNode[][] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[12.5px]">
        <thead>
          <tr>{cols.map((c, i) => <th key={i} className={`th ${c.className ?? ""}`}>{c.label}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r, ri) => (
            <tr key={ri} className="transition hover:bg-white/[0.025]">
              {r.map((cell, ci) => (
                <td key={ci} className={`td ${cols[ci]?.className ?? ""}`}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Loading<T>({ s, skeleton, children }: {
  s: AsyncState<T>; skeleton?: ReactNode; children: (data: T) => ReactNode;
}) {
  if (s.loading)
    return skeleton ? <>{skeleton}</> : (
      <div className="h-1 w-full overflow-hidden rounded bg-ink-700">
        <div className="h-full w-1/3 animate-[shimmer_1.1s_infinite] rounded bg-brand" />
      </div>
    );
  if (s.error)
    return <div className="rounded-xl border border-crit/30 bg-crit/10 px-4 py-3 text-[12.5px] text-crit">
      Could not load: {s.error}
    </div>;
  return <>{children(s.data as T)}</>;
}

export function Slider({
  label, value, min, max, step, onChange, fmt,
}: {
  label: string; value: number; min: number; max: number; step: number;
  onChange: (v: number) => void; fmt?: (v: number) => string;
}) {
  return (
    <label className="flex min-w-[190px] flex-col gap-1.5">
      <span className="kpi-label">{label}</span>
      <span className="flex items-center gap-3">
        <input className="range" type="range" min={min} max={max} step={step} value={value}
          onChange={(e) => onChange(Number(e.target.value))} />
        <span className="min-w-[54px] text-right font-mono text-[12px]">{fmt ? fmt(value) : value}</span>
      </span>
    </label>
  );
}

export function MetricGrid({ items }: { items: [string, ReactNode][] }) {
  return (
    <div className="my-3.5 grid gap-2.5 [grid-template-columns:repeat(auto-fit,minmax(112px,1fr))]">
      {items.map(([k, v], i) => (
        <div key={i} className="rounded-lg border border-white/[0.06] bg-ink-800/70 px-3 py-2">
          <div className="text-[10px] uppercase tracking-[0.08em] text-fg-faint">{k}</div>
          <div className="mt-1 font-mono text-[15px]">{v}</div>
        </div>
      ))}
    </div>
  );
}

export function Diagram({ text }: { text?: string }) {
  if (!text) return null;
  return (
    <pre className="my-2 overflow-x-auto rounded-lg border border-white/[0.06] bg-ink-950 p-3
      font-mono text-[11px] leading-[1.35] text-fg-muted">{text}</pre>
  );
}

export function num(x: unknown, d = 2): string {
  return typeof x === "number" ? x.toFixed(d) : x == null ? "–" : String(x);
}
