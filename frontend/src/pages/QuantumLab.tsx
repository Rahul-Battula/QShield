import { useEffect, useState } from "react";
import {
  get, post, type CompareRun, type Estimate, type GroverRun, type ShorRun,
} from "../lib/api";
import { useAsync } from "../lib/hooks";
import {
  Diagram, Loading, MetricGrid, PageHead, Panel, Slider,
} from "../components/ui";
import { Curve, Histogram, YearStrip } from "../components/charts";

export function QuantumLab() {
  const [health] = useAsync(() => get<{ qiskit: boolean }>("/api/health"), []);
  return (
    <>
      <PageHead title="Quantum Lab"
        desc="Shor and Grover as real Qiskit circuits on Aer — ideal vs noisy — with the resource projection that scales the mechanism up to RSA-2048." />
      <Loading s={health}>{(h) =>
        h.qiskit ? (
          <>
            <GroverLab /><ShorLab /><CompareLab /><EstimateLab />
          </>
        ) : (
          <div className="rounded-xl border border-crit/30 bg-crit/10 px-4 py-3 text-[12.5px] text-crit">
            The Quantum Lab needs the optional extra: <code className="font-mono">
            pip install -r requirements-qiskit.txt</code>, then restart. The Threat tab's
            demos still run on the bundled simulator.
          </div>
        )
      }</Loading>
    </>
  );
}

function useRun<T>() {
  const [st, setSt] = useState<{ busy: boolean; res: T | null; err: string | null }>({
    busy: false, res: null, err: null,
  });
  const go = (fn: () => Promise<T>) => {
    setSt({ busy: true, res: null, err: null });
    fn().then((res) => setSt({ busy: false, res, err: null }))
      .catch((e) => setSt({ busy: false, res: null, err: String(e?.message ?? e) }));
  };
  return [st, go] as const;
}

function BackendChips({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <label className="flex min-w-[190px] flex-col gap-1.5">
      <span className="kpi-label">backend</span>
      <span className="flex gap-1.5">
        {["ideal", "noisy", "matrix"].map((n) => (
          <button key={n} className={`chip ${value === n ? "chip-on" : ""}`}
            onClick={() => onChange(n)}>{n}</button>
        ))}
      </span>
    </label>
  );
}

function Noise({ f, set }: { f: any; set: (k: string) => (v: number) => void }) {
  if (f.backend !== "noisy") return null;
  const e = (v: number) => v.toExponential(1);
  return (
    <>
      <Slider label="1-qubit error" min={0} max={0.05} step={0.001} value={f.p1} onChange={set("p1")} fmt={e} />
      <Slider label="2-qubit error" min={0} max={0.1} step={0.002} value={f.p2} onChange={set("p2")} fmt={e} />
      <Slider label="readout error" min={0} max={0.1} step={0.002} value={f.readout} onChange={set("readout")} fmt={e} />
    </>
  );
}

function GroverLab() {
  const [f, setF] = useState({ n_bits: 4, backend: "ideal", p1: 1e-3, p2: 1e-2, readout: 2e-2 });
  const set = (k: string) => (v: number | string) => setF({ ...f, [k]: v });
  const [st, go] = useRun<GroverRun>();
  const r = st.res;
  return (
    <Panel title="Grover search — a marked key in an n-bit space"
      actions={<button className="btn btn-primary" disabled={st.busy}
        onClick={() => go(() => post("/api/quantum/grover", f))}>{st.busy ? "Running…" : "Run"}</button>}>
      <div className="flex flex-wrap items-end gap-x-6 gap-y-4">
        <Slider label="key bits (n)" min={2} max={7} step={1} value={f.n_bits} onChange={set("n_bits")} />
        <BackendChips value={f.backend} onChange={(v) => set("backend")(v)} />
        <Noise f={f} set={set as any} />
      </div>
      {st.err && <div className="mt-3 rounded-lg bg-crit/10 px-3 py-2 text-[12px] text-crit">{st.err}</div>}
      {r && (
        <>
          <MetricGrid items={[
            ["measured", `${r.measured} / ${r.target}`],
            ["P(success)", r.success_probability.toFixed(3)],
            ["iterations", `${r.iterations} of ${r.optimal_iterations}`],
            ["qubits", r.n_qubits],
            ["depth", `${r.depth_pre_transpile} → ${r.depth_post_transpile}`],
            ["backend", r.backend], ["wall", `${r.wall_ms} ms`],
          ]} />
          <div className="kpi-label mb-1 mt-1">success probability vs iterations</div>
          <Curve data={r.success_curve} xKey="iterations" yKey="success_probability" ydomain={[0, 1]} />
          <div className="kpi-label mb-1 mt-3">measurement counts</div>
          <Histogram data={r.histogram} mark={r.target} />
          <Diagram text={r.diagram} />
        </>
      )}
    </Panel>
  );
}

function ShorLab() {
  const [f, setF] = useState({ N: 15, a: 2, backend: "ideal", p1: 1e-3, p2: 1e-2, readout: 2e-2 });
  const set = (k: string) => (v: number | string) => setF({ ...f, [k]: v });
  const [st, go] = useRun<ShorRun>();
  const r = st.res;
  return (
    <Panel title="Shor — factor N by quantum order-finding"
      actions={<button className="btn btn-primary" disabled={st.busy}
        onClick={() => go(() => post("/api/quantum/shor", f))}>{st.busy ? "Running…" : "Run"}</button>}>
      <div className="flex flex-wrap items-end gap-x-6 gap-y-4">
        <label className="flex flex-col gap-1.5">
          <span className="kpi-label">N</span>
          <span className="flex gap-1.5">
            {[15, 21, 35].map((n) => (
              <button key={n} className={`chip ${f.N === n ? "chip-on" : ""}`}
                onClick={() => set("N")(n)}>{n}</button>
            ))}
          </span>
        </label>
        <Slider label="base a" min={2} max={13} step={1} value={f.a} onChange={set("a")} />
        <BackendChips value={f.backend} onChange={(v) => set("backend")(v)} />
      </div>
      {st.err && <div className="mt-3 rounded-lg bg-crit/10 px-3 py-2 text-[12px] text-crit">{st.err}</div>}
      {r && (
        <>
          <MetricGrid items={[
            ["N", `${r.N} = ${r.factors.length ? r.factors.join(" × ") : "?"}`],
            ["order r", r.order ?? "—"],
            ["verified", String(r.order_verified)],
            ["qubits", `${r.n_qubits} (${r.counting_qubits}+${r.work_qubits})`],
            ["mode", r.mode],
            ["depth", `${r.depth_pre_transpile} → ${r.depth_post_transpile}`],
            ["wall", `${r.wall_ms} ms`],
          ]} />
          <div className="kpi-label mb-1">counting-register measurements</div>
          <Histogram data={r.histogram} />
          <Diagram text={r.diagram} />
        </>
      )}
    </Panel>
  );
}

function CompareLab() {
  const [f, setF] = useState({ N: 15, a: 7 });
  const [st, go] = useRun<CompareRun>();
  const r = st.res;
  return (
    <Panel title="Ideal vs noisy — the same Shor circuit, both backends"
      actions={
        <div className="flex items-center gap-2">
          <div className="flex gap-1.5">
            {[15, 21, 35].map((n) => (
              <button key={n} className={`chip ${f.N === n ? "chip-on" : ""}`}
                onClick={() => setF({ N: n, a: f.a })}>{n}</button>
            ))}
          </div>
          <button className="btn btn-primary" disabled={st.busy}
            onClick={() => go(() => post("/api/quantum/compare", f))}>
            {st.busy ? "Running…" : "Compare"}
          </button>
        </div>
      }>
      {st.err && <div className="rounded-lg bg-crit/10 px-3 py-2 text-[12px] text-crit">{st.err}</div>}
      {r && (
        <>
          {r.note && <p className="mb-3 text-[12px] text-fg-muted">{r.note}</p>}
          <div className="grid gap-6 md:grid-cols-2">
            <div>
              <div className="mb-1 text-[12.5px]">ideal → <b>{r.ideal.factors.join(" × ") || "no factors"}</b></div>
              <Histogram data={r.ideal.histogram} />
            </div>
            <div>
              <div className="mb-1 text-[12.5px]">
                {r.noise_applied ? "noisy" : "sampling spread"} → <b>{r.noisy.factors.join(" × ") || "no factors"}</b>
              </div>
              <Histogram data={r.noisy.histogram} />
            </div>
          </div>
        </>
      )}
    </Panel>
  );
}

const TARGETS: [string, number][] = [
  ["RSA", 2048], ["RSA", 3072], ["ECC", 256], ["AES", 128], ["AES", 256],
];

function EstimateLab() {
  const [f, setF] = useState({ algorithm: "RSA", key_bits: 2048, phys_error_rate: 1e-3, annual_growth: 1.5 });
  const set = (k: string) => (v: number) => setF({ ...f, [k]: v });
  const [st, go] = useRun<Estimate>();
  useEffect(() => { go(() => post("/api/quantum/estimate", f)); }, [f]); // eslint-disable-line
  const r = st.res;
  return (
    <Panel title="Resource projection — scaling the mechanism to real key sizes"
      hint="a projection under the stated assumptions, not a prediction">
      <div className="flex flex-wrap items-end gap-x-6 gap-y-4">
        <label className="flex flex-col gap-1.5">
          <span className="kpi-label">target</span>
          <span className="flex flex-wrap gap-1.5">
            {TARGETS.map(([alg, bits]) => (
              <button key={`${alg}${bits}`}
                className={`chip ${f.algorithm === alg && f.key_bits === bits ? "chip-on" : ""}`}
                onClick={() => setF({ ...f, algorithm: alg, key_bits: bits })}>
                {alg}-{bits}
              </button>
            ))}
          </span>
        </label>
        <Slider label="physical error rate" min={0.0001} max={0.005} step={0.0001}
          value={f.phys_error_rate} onChange={set("phys_error_rate")} fmt={(v) => v.toExponential(1)} />
        <Slider label="qubit growth / yr" min={1.1} max={3} step={0.1}
          value={f.annual_growth} onChange={set("annual_growth")} fmt={(v) => `${v.toFixed(1)}×`} />
      </div>
      {r && (
        <>
          <MetricGrid items={[
            ["attack", r.attack.split(" ")[0]],
            ["logical qubits", r.logical_qubits.toLocaleString()],
            ["code distance", r.code_distance],
            ["physical qubits", Number(r.physical_qubits).toExponential(2)],
            ["runtime", r.runtime_human],
            ["feasible year", r.feasible_year ?? "beyond curve"],
          ]} />
          <div className="kpi-label mb-1">years until enough physical qubits exist (red = feasible)</div>
          <YearStrip series={r.growth_curve} />
          <p className="text-[12px] text-fg-faint">{r.disclaimer}</p>
        </>
      )}
    </Panel>
  );
}
