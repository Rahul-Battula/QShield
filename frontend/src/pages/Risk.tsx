import { useState } from "react";
import { get, type MlRank, type RiskReport } from "../lib/api";
import { useAsync } from "../lib/hooks";
import {
  BAND, DataTable, Kpis, Loading, num, PageHead, Panel, Pill,
} from "../components/ui";
import { DistBar, HBars } from "../components/charts";

export function Risk() {
  const [s] = useAsync(() => get<RiskReport>("/api/risk?assessment_year=2026"), []);
  return (
    <>
      <PageHead title="Risk"
        desc="Mosca's inequality with exposure and blast radius, plus a scikit-learn model that scores and explains each finding." />
      <Loading s={s}>{(d) => {
        const b = d.summary.bands;
        return (
          <>
            <Kpis items={[
              { label: "P1 — do now", value: b.P1, tone: "crit" },
              { label: "P2 — this cycle", value: b.P2 },
              { label: "Past Mosca start date", value: d.summary.too_late, tone: "crit" },
              { label: "CRQC horizon", value: d.summary.crqc_year, tone: "brand",
                sub: `assessed ${d.summary.assessment_year}` },
            ]} />

            <Panel title="Priority mix (Mosca score)">
              <DistBar segments={[
                { label: "P1", value: b.P1, color: "#ff6b6b" },
                { label: "P2", value: b.P2, color: "#ffb454" },
                { label: "P3", value: b.P3, color: "#e9d16b" },
                { label: "P4", value: b.P4, color: "#5fd08a" },
              ]} />
            </Panel>

            <Panel flush title="Ranked findings" hint="top 40">
              <DataTable
                cols={[
                  { label: "#", className: "text-right font-mono" },
                  { label: "Score", className: "text-right font-mono" },
                  { label: "Band" }, { label: "Algorithm", className: "font-mono" },
                  { label: "System" }, { label: "Location", className: "font-mono text-fg-muted" },
                ]}
                rows={d.scores.slice(0, 40).map((x, i) => [
                  i + 1, num(x.score, 1),
                  <Pill tone={BAND[x.band]} plain>{x.band}</Pill>,
                  x.asset.detail, x.system,
                  <span title={x.asset.location}>{x.asset.location}</span>,
                ])}
              />
            </Panel>

            <Panel title="Work packages">
              {d.work_packages.map((w) => (
                <div key={w.id}
                  className="flex items-center gap-3 border-b border-white/[0.05] py-2.5 last:border-0">
                  <span className="min-w-[46px] font-mono text-fg-faint">{w.id}</span>
                  <Pill tone={BAND[w.top_band]} plain>{w.top_band}</Pill>
                  <span className="font-medium">{w.title}</span>
                  <span className="ml-auto text-[12px] text-fg-faint">
                    {w.size} findings · {num(w.total_migration_years, 1)} yr-equiv
                  </span>
                </div>
              ))}
            </Panel>

            <MlSection />
          </>
        );
      }}</Loading>
    </>
  );
}

function MlSection() {
  const [s] = useAsync(() => get<MlRank>("/api/risk/rank?limit=15"), []);
  const [sel, setSel] = useState<string | null>(null);
  return (
    <Loading s={s} skeleton={<p className="text-[12.5px] text-fg-muted">Training the risk model…</p>}>
      {(d) => {
        const imp = Object.entries(d.model.regressor)
          .map(([name, value]) => ({ name: name.replace(/_/g, " "), value }))
          .sort((a, b) => b.value - a.value);
        return (
          <>
            <Panel flush title="ML migration queue"
              hint={`GradientBoosting R² ${d.model.metrics.regressor_r2} · RandomForest acc ${d.model.metrics.classifier_accuracy}`}>
              <DataTable
                cols={[
                  { label: "#", className: "text-right font-mono" },
                  { label: "Score", className: "text-right font-mono" },
                  { label: "Band" }, { label: "Algorithm", className: "font-mono" },
                  { label: "Why", className: "text-fg-muted" },
                ]}
                rows={d.queue.map((r) => [
                  r.rank, num(r.priority_score, 1),
                  <button onClick={() => setSel(r.asset_id)}>
                    <Pill tone={BAND[r.priority_band]} plain>{r.priority_band}</Pill>
                  </button>,
                  r.detail,
                  <button className="text-left" onClick={() => setSel(r.asset_id)}>{r.explanation}</button>,
                ])}
              />
            </Panel>
            <Panel title="Feature importance — priority regressor">
              <HBars data={imp} />
            </Panel>
            {sel && <MlExplain id={sel} onClose={() => setSel(null)} />}
          </>
        );
      }}
    </Loading>
  );
}

function MlExplain({ id, onClose }: { id: string; onClose: () => void }) {
  const [s] = useAsync(() => get<any>(`/api/risk/explain/${id}`), [id]);
  return (
    <Panel title="Why this asset ranked here"
      actions={<button className="btn" onClick={onClose}>Close</button>}>
      <Loading s={s}>{(d) => (
        <>
          <p className="mb-3 text-[12.5px] text-fg-muted">
            <b className="text-fg">{d.detail}</b> @ <code className="font-mono">{d.location}</code> — {d.summary}
          </p>
          <DataTable
            cols={[
              { label: "Feature" }, { label: "Value", className: "text-right font-mono" },
              { label: "Importance", className: "text-right font-mono" },
              { label: "Contribution", className: "text-right font-mono" },
            ]}
            rows={d.contributions.map((c: any) => [
              c.feature.replace(/_/g, " "), c.value, c.importance,
              <b className={c.contribution > 0 ? "text-crit" : "text-ok"}>
                {c.contribution > 0 ? "+" : ""}{c.contribution}
              </b>,
            ])}
          />
        </>
      )}</Loading>
    </Panel>
  );
}
