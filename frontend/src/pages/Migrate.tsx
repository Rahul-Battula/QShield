import { useState } from "react";
import { get, post, type MigrationResult, type Policy, type WavePlan } from "../lib/api";
import { useAsync } from "../lib/hooks";
import { DataTable, Loading, PageHead, Panel, Pill, BAND } from "../components/ui";

export function Migrate() {
  const [pol] = useAsync(() => get<Policy>("/api/policy"), []);
  const [to, setTo] = useState("pqc");
  const [records, setRecords] = useState(10);
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState<MigrationResult | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const run = () => {
    setBusy(true); setRes(null); setErr(null);
    post<MigrationResult>("/api/migration/run", { to_suite: to, records })
      .then(setRes).catch((e) => setErr(String(e?.message ?? e))).finally(() => setBusy(false));
  };

  return (
    <>
      <PageHead title="Migrate"
        desc="Run a real migration of the demo land registry, and see the phased plan for the whole estate." />
      <Loading s={pol}>{(p) => (
        <>
          <Panel title="Operation">
            <div className="flex flex-wrap items-end gap-4">
              <label className="flex flex-col gap-1.5">
                <span className="kpi-label">target suite</span>
                <select className="rounded-lg border border-white/10 bg-ink-950 px-2.5 py-2 text-[12.5px]"
                  value={to} onChange={(e) => setTo(e.target.value)}>
                  {Object.keys(p.suites).map((n) => <option key={n} value={n}>{n}</option>)}
                </select>
              </label>
              <label className="flex flex-col gap-1.5">
                <span className="kpi-label">records</span>
                <input type="number" min={1} max={200} value={records}
                  onChange={(e) => setRecords(Number(e.target.value))}
                  className="w-20 rounded-lg border border-white/10 bg-ink-950 px-2.5 py-2 text-[12.5px]" />
              </label>
              <button className="btn btn-primary" disabled={busy} onClick={run}>
                {busy ? "Running…" : "Run migration"}
              </button>
            </div>
            {err && <div className="mt-3 rounded-lg bg-crit/10 px-3 py-2 text-[12px] text-crit">{err}</div>}
          </Panel>

          {res && <Result r={res} />}
          <WaveSection />
        </>
      )}</Loading>
    </>
  );
}

function Result({ r }: { r: MigrationResult }) {
  const su = r.summary;
  const before = su.algorithms_before.map((p) => p.join(" / "));
  const after = su.algorithms_after.map((p) => p.join(" / "));
  return (
    <>
      <Panel title={`${su.from_suite}  →  ${su.to_suite}`}
        actions={
          <span className={`inline-flex items-center rounded-lg px-3 py-1.5 text-[12px] font-bold ${
            r.thesis_ok ? "bg-ok/10 text-ok" : "bg-crit/10 text-crit"}`}>
            {r.thesis_ok ? "THESIS UPHELD" : "THESIS VIOLATED"}
          </span>
        }>
        {r.thesis_error && <p className="mb-2 text-[12px] text-crit">{r.thesis_error}</p>}
        <div className="my-2 grid items-stretch gap-3.5 md:grid-cols-[1fr_auto_1fr]">
          <div className="rounded-xl border border-white/[0.06] bg-ink-800/70 p-4">
            <div className="kpi-label mb-2">before</div>
            <div className="font-mono text-[13px] leading-8">{before.map((x, i) => <div key={i}>{x}</div>)}</div>
          </div>
          <div className="flex items-center text-xl text-fg-faint">→</div>
          <div className="rounded-xl border border-white/[0.06] bg-ink-800/70 p-4">
            <div className="kpi-label mb-2">after</div>
            <div className="font-mono text-[13px] leading-8">{after.map((x, i) => <div key={i}>{x}</div>)}</div>
          </div>
        </div>
        <div className="flex flex-wrap gap-x-7 gap-y-1.5 text-[12.5px] text-fg-faint">
          <span>records <b className="text-fg">{su.records_changed} / {su.records} changed</b></span>
          <span>verified before / after <b className="text-fg">{String(su.before_all_valid)} / {String(su.after_all_valid)}</b></span>
          <span>application code <b className="text-fg">{su.app_code_touched ? "MODIFIED" : "UNCHANGED"}</b></span>
          <span>re-seal <b className="text-fg">{(su.reseal_seconds * 1000).toFixed(0)} ms</b></span>
        </div>
      </Panel>
      <Panel flush title="Per-record">
        <DataTable
          cols={[
            { label: "Record", className: "font-mono" },
            { label: "KEM  before → after", className: "font-mono" },
            { label: "Signature  before → after", className: "font-mono" },
            { label: "Re-seal", className: "text-right font-mono" },
          ]}
          rows={r.records.map((rec) => [
            rec.record_id,
            <>{rec.before.kem} → <b>{rec.after.kem}</b></>,
            <>{rec.before.sig} → <b>{rec.after.sig}</b></>,
            rec.reseal_ms,
          ])}
        />
      </Panel>
    </>
  );
}

function WaveSection() {
  const [s] = useAsync(() => get<WavePlan>("/api/migration/plan?assessment_year=2026"), []);
  return (
    <Loading s={s}>{(p) => (
      <Panel title="Phased migration plan"
        hint={`deadline ${p.deadline} · ${p.total_effort_years} yr-equiv total`}>
        {p.waves.map((w) => (
          <div key={w.id} className="mb-3 rounded-xl border border-white/[0.06] bg-ink-800/50 p-3.5 last:mb-0">
            <div className="flex flex-wrap items-center gap-2.5">
              <Pill tone={BAND[w.band]} plain>{w.band}</Pill>
              <b className="text-[13px]">{w.name}</b>
              <span className="text-[12px] text-fg-faint">{w.start_date} → {w.target_date}</span>
              <span className="ml-auto text-[12px] text-fg-faint">
                {w.size} findings · {w.effort_years} yr-equiv · removes{" "}
                <b className="text-fg">{w.risk_reduction_pct}%</b> of risk
              </span>
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {w.items.slice(0, 8).map((it, i) => (
                <span key={i}
                  className={`chip !text-[10.5px] ${it.past_start_date ? "border-crit/30 text-crit" : ""}`}>
                  {it.detail}
                </span>
              ))}
              {w.size > 8 && <span className="chip !text-[10.5px]">+{w.size - 8} more</span>}
            </div>
          </div>
        ))}
      </Panel>
    )}</Loading>
  );
}
