import { useState } from "react";
import { get, post } from "../lib/api";
import { useAsync } from "../lib/hooks";
import { DataTable, Kpis, Loading, num, PageHead, Panel, Pill } from "../components/ui";

interface ThreatData {
  summary: { shor_targets: number; grover_targets: number;
             classically_broken: number; unaffected: number };
  threats: { attack: string; primitive: string; location: string; summary: string }[];
  horizon: string | null;
}

export function Threat() {
  const [s] = useAsync(() => get<ThreatData>("/api/threat"), []);
  const [health] = useAsync(() => get<{ qiskit: boolean }>("/api/health"), []);
  const [eng, setEng] = useState<"python" | "qiskit">("python");
  const [grover, setGrover] = useState<any>(null);
  const [running, setRunning] = useState(false);

  const runGrover = () => {
    setRunning(true);
    post("/api/threat/demo/grover", { qubits: 4, target: 11, seed: 0, engine: eng })
      .then(setGrover).finally(() => setRunning(false));
  };
  const haveQiskit = health.data?.qiskit;

  return (
    <>
      <PageHead title="Threat"
        desc="Which quantum attack applies to each finding, its published cost, and a demonstration that runs on the simulator." />
      <Loading s={s}>{(d) => (
        <>
          <Kpis items={[
            { label: "Broken by Shor", value: d.summary.shor_targets, tone: "crit" },
            { label: "Weakened by Grover", value: d.summary.grover_targets },
            { label: "Already classical", value: d.summary.classically_broken, tone: "crit" },
            { label: "Unaffected", value: d.summary.unaffected, tone: "ok" },
          ]} />

          <Panel title="Live demonstration — Grover search"
            actions={
              <div className="flex items-center gap-2">
                {haveQiskit && (
                  <div className="flex gap-1.5">
                    {(["python", "qiskit"] as const).map((n) => (
                      <button key={n} className={`chip ${eng === n ? "chip-on" : ""}`}
                        onClick={() => setEng(n)}>{n}</button>
                    ))}
                  </div>
                )}
                <button className="btn btn-primary" disabled={running} onClick={runGrover}>
                  {running ? "Running…" : "Run"}
                </button>
              </div>
            }>
            {grover ? (
              <p className="max-w-[74ch] text-[12.5px] leading-relaxed text-fg-muted">
                Engine <b className="text-fg">{grover.engine ?? eng}</b> — measured{" "}
                <b className="text-fg">{grover.measured}</b> (target {grover.target}) after{" "}
                {grover.iterations} iterations · P(success) {num(grover.success_probability, 3)} ·{" "}
                <b className="text-fg">{grover.speedup}×</b> fewer queries than a classical search.
              </p>
            ) : (
              <p className="max-w-[74ch] text-[12.5px] leading-relaxed text-fg-muted">
                Runs a real amplitude-amplification circuit — on the bundled statevector simulator,
                or on Qiskit Aer when the <code className="font-mono">quantum</code> extra is installed.
              </p>
            )}
          </Panel>

          <Panel flush title="Findings">
            <DataTable
              cols={[
                { label: "Attack" }, { label: "Primitive", className: "font-mono" },
                { label: "Location", className: "font-mono text-fg-muted" },
                { label: "Consequence", className: "text-fg-muted" },
              ]}
              rows={d.threats.filter((t) => t.attack !== "none").map((t) => [
                <Pill tone={t.attack === "Grover" ? "text-med bg-med/10" : "text-crit bg-crit/10"} plain>
                  {t.attack}
                </Pill>,
                t.primitive,
                <span title={t.location}>{t.location}</span>,
                <span className="whitespace-normal">{t.summary}</span>,
              ])}
            />
          </Panel>

          {d.horizon && (
            <p className="max-w-[74ch] text-[12px] leading-relaxed text-fg-faint">{d.horizon}</p>
          )}
        </>
      )}</Loading>
    </>
  );
}
