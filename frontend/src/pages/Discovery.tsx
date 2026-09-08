import { get, type Cbom } from "../lib/api";
import { useAsync } from "../lib/hooks";
import { DataTable, EXPO, Kpis, Loading, PageHead, Panel, Pill } from "../components/ui";

export function Discovery() {
  const [s] = useAsync(() => get<Cbom>("/api/discovery"), []);
  return (
    <>
      <PageHead title="Discovery"
        desc="The CBOM — every place the estate uses cryptography, classified by exposure. Python is parsed with the ast module; the rest by pattern." />
      <Loading s={s}>{(d) => {
        const sum = d.summary;
        return (
          <>
            <Kpis items={[
              { label: "Total assets", value: sum.total },
              { label: "Broken now", value: sum.CLASSICALLY_BROKEN, tone: "crit" },
              { label: "Quantum-broken", value: sum.QUANTUM_BROKEN, tone: "crit" },
              { label: "Quantum-safe", value: sum.QUANTUM_SAFE, tone: "ok" },
            ]} />
            <Panel flush title="Cryptographic bill of materials" hint={`${d.assets.length} assets`}
              actions={<a className="btn" href="/api/cbom/export?format=csv">Export CSV</a>}>
              <DataTable
                cols={[
                  { label: "Exposure" }, { label: "Algorithm", className: "font-mono" },
                  { label: "Kind" }, { label: "Data class" },
                  { label: "Retention", className: "text-right font-mono" },
                  { label: "Location", className: "font-mono text-fg-muted" },
                ]}
                rows={d.assets.map((a) => {
                  const [tone, lbl] = EXPO[a.exposure] ?? EXPO.UNKNOWN;
                  return [
                    <Pill tone={tone}>{lbl}</Pill>,
                    a.detail,
                    a.kind.toLowerCase().replace(/_/g, " "),
                    a.data_classification,
                    `${a.data_retention_years}y`,
                    <span title={a.location}>{a.location}</span>,
                  ];
                })}
              />
            </Panel>
          </>
        );
      }}</Loading>
    </>
  );
}
