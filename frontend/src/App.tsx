import { useState } from "react";
import { Layout, type Tab } from "./components/Layout";
import { Overview } from "./pages/Overview";
import { Discovery } from "./pages/Discovery";
import { Risk } from "./pages/Risk";
import { Threat } from "./pages/Threat";
import { QuantumLab } from "./pages/QuantumLab";
import { Benchmark } from "./pages/Benchmark";
import { Migrate } from "./pages/Migrate";

const TABS: [Tab, () => JSX.Element][] = [
  [{ id: "overview", label: "Overview" }, Overview],
  [{ id: "discovery", label: "Discovery" }, Discovery],
  [{ id: "risk", label: "Risk" }, Risk],
  [{ id: "threat", label: "Threat" }, Threat],
  [{ id: "qlab", label: "Quantum Lab" }, QuantumLab],
  [{ id: "benchmark", label: "Benchmark" }, Benchmark],
  [{ id: "migrate", label: "Migrate" }, Migrate],
];

export default function App() {
  const [tab, setTab] = useState("overview");
  const View = (TABS.find(([t]) => t.id === tab) ?? TABS[0])[1];
  return (
    <Layout tabs={TABS.map(([t]) => t)} active={tab} onTab={setTab}>
      <div key={tab}>
        <View />
      </div>
    </Layout>
  );
}
