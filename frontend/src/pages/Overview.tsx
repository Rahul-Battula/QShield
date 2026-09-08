import { get, post, type Cbom, type Policy, type RiskReport } from "../lib/api";
import { useAsync } from "../lib/hooks";
import { Kpis, Loading, PageHead, Panel } from "../components/ui";
import { DistBar } from "../components/charts";
import { useState } from "react";

interface Threat { summary: { shor_targets: number } }

export function Overview() {
  const [s, reload] = useAsync(
    () => Promise.all([
      get<Policy>("/api/policy"), get<Cbom>("/api/discovery"),
      get<RiskReport>("/api/risk"), get<Threat>("/api/threat"),
    ]).then(([policy, disc, risk, threat]) => ({ policy, disc, risk, threat })),
    [],
  );
  const [busy, setBusy] = useState(false);
  const swap = (name: string) => {
    setBusy(true);
    post("/api/policy/active", { suite: name }).then(reload).finally(() => setBusy(false));
  };

  return (
    <>
      <PageHead title="Overview"
        desc="The estate at a glance, and the one control that performs a migration." />
      <Loading s={s}>{(d) => {
        const sum = d.disc.summary;
        const suite = d.policy.suites[d.policy.active_suite];
        return (
          <>
            <Kpis items={[
              { label: "Assets inventoried", value: sum.total },
              { label: "P1 findings", value: d.risk.summary.bands.P1, tone: "crit" },
              { label: "Broken by Shor", value: d.threat.summary.shor_targets, tone: "crit" },
              { label: "CRQC horizon", value: d.policy.mosca.crqc_year, tone: "brand",
                sub: `${d.policy.mosca.active_preset} preset` },
            ]} />

            <Panel title="Active cryptographic policy"
              hint="changing this and reloading is the entire migration">
              <div className="mb-4 flex flex-wrap gap-x-7 gap-y-1.5 text-[12.5px] text-fg-faint">
                <span>suite <b className="font-mono text-fg">{d.policy.active_suite}</b></span>
                <span>KEM <b className="font-mono text-fg">{suite.kem}</b></span>
                <span>signature <b className="font-mono text-fg">{suite.sig}</b></span>
              </div>
              <div className="flex flex-wrap gap-2">
                {Object.keys(d.policy.suites).map((n) => (
                  <button key={n} disabled={busy} onClick={() => swap(n)}
                    className={`chip font-mono ${n === d.policy.active_suite ? "chip-on" : ""}`}>
                    {n}
                  </button>
                ))}
              </div>
            </Panel>

            <Panel title="Exposure of inventoried cryptography">
              <DistBar segments={[
                { label: "broken now", value: sum.CLASSICALLY_BROKEN, color: "#ff6b6b" },
                { label: "quantum-broken", value: sum.QUANTUM_BROKEN, color: "#ffb454" },
                { label: "weakened", value: sum.QUANTUM_WEAKENED, color: "#e9d16b" },
                { label: "safe", value: sum.QUANTUM_SAFE, color: "#5fd08a" },
              ]} />
            </Panel>
          </>
        );
      }}</Loading>
    </>
  );
}
