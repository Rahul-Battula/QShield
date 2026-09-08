import { get, type Benchmark as B } from "../lib/api";
import { useAsync } from "../lib/hooks";
import { DataTable, Kpis, Loading, PageHead, Panel, Pill } from "../components/ui";

export function Benchmark() {
  const [s] = useAsync(() => get<B>("/api/benchmark?iterations=15"), []);
  return (
    <>
      <PageHead title="Benchmark"
        desc="Timings and sizes for every suite. Reference-only rows show published sizes, never invented timings." />
      <Loading s={s} skeleton={<p className="text-[12.5px] text-fg-muted">Timing every suite — a moment.</p>}>
        {(d) => {
          const ms = (row: B["suites"][number], k: string) =>
            row.live && row.timings[k] ? row.timings[k].median_ms.toFixed(2) : "–";
          return (
            <>
              <Kpis items={[
                { label: "Iterations / op", value: d.iterations },
                { label: "Runtime", value: d.machine.implementation,
                  sub: `${d.machine.python} · ${d.machine.platform}` },
                { label: "Suites", value: d.suites.length },
              ]} />
              <Panel flush title="Per-suite cost" hint="median ms · bytes">
                <DataTable
                  cols={[
                    { label: "Suite", className: "font-mono" }, { label: "Live" },
                    { label: "KEM keygen", className: "text-right font-mono" },
                    { label: "Encaps", className: "text-right font-mono" },
                    { label: "Decaps", className: "text-right font-mono" },
                    { label: "Sign", className: "text-right font-mono" },
                    { label: "Verify", className: "text-right font-mono" },
                    { label: "Handshake", className: "text-right font-mono" },
                    { label: "vs classical", className: "text-right font-mono" },
                    { label: "KEM pub", className: "text-right font-mono" },
                    { label: "Ciphertext", className: "text-right font-mono" },
                    { label: "Signature", className: "text-right font-mono" },
                  ]}
                  rows={d.suites.map((s) => [
                    s.suite,
                    <Pill tone={s.live ? "text-ok bg-ok/10" : "text-fg-muted bg-white/5"} plain>
                      {s.live ? "live" : "ref"}
                    </Pill>,
                    ms(s, "kem_keygen"), ms(s, "encapsulate"), ms(s, "decapsulate"),
                    ms(s, "sign"), ms(s, "verify"),
                    s.handshake_ms == null ? "–" : s.handshake_ms.toFixed(2),
                    s.handshake_vs_classical == null ? "–" : `${s.handshake_vs_classical}×`,
                    s.sizes.kem_public ?? "–", s.sizes.ciphertext ?? "–", s.sizes.signature ?? "–",
                  ])}
                />
              </Panel>
            </>
          );
        }}
      </Loading>
    </>
  );
}
