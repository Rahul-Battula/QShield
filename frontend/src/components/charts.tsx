import {
  Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";

const AXIS = { stroke: "#626b7c", fontSize: 10, fontFamily: "JetBrains Mono, monospace" };
const GRID = "#1e2532";
const tip = {
  contentStyle: {
    background: "#10141d", border: "1px solid #2b3342", borderRadius: 10,
    fontSize: 11, fontFamily: "JetBrains Mono, monospace",
  },
  labelStyle: { color: "#9aa3b2" },
};

/** Stacked distribution bar (one row). segments: [{label,value,color}] */
export function DistBar({ segments }: { segments: { label: string; value: number; color: string }[] }) {
  const total = segments.reduce((a, s) => a + s.value, 0) || 1;
  return (
    <div>
      <div className="flex h-2 overflow-hidden rounded-full bg-ink-700">
        {segments.map((s, i) => (
          <div key={i} style={{ width: `${(100 * s.value) / total}%`, background: s.color }} />
        ))}
      </div>
      <div className="mt-2.5 flex flex-wrap gap-x-4 gap-y-1 text-[11.5px] text-fg-muted">
        {segments.map((s, i) => (
          <span key={i} className="inline-flex items-center gap-1.5">
            <i className="inline-block h-2 w-2 rounded-[2px]" style={{ background: s.color }} />
            {s.label} <b className="text-fg">{s.value}</b>
          </span>
        ))}
      </div>
    </div>
  );
}

export function Histogram({
  data, mark, height = 150,
}: { data: Record<string, number>; mark?: number; height?: number }) {
  const rows = Object.entries(data)
    .map(([k, v]) => ({ x: Number(k), v }))
    .sort((a, b) => a.x - b.x);
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={rows} margin={{ top: 6, right: 6, bottom: 0, left: -18 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="x" tick={AXIS} tickLine={false} axisLine={{ stroke: GRID }}
          interval="preserveStartEnd" />
        <YAxis tick={AXIS} tickLine={false} axisLine={false} width={44} />
        <Tooltip {...tip} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
        <Bar dataKey="v" radius={[2, 2, 0, 0]}>
          {rows.map((r, i) => (
            <Cell key={i} fill={r.x === mark ? "#5fd08a" : "#5bb0ff"} fillOpacity={r.x === mark ? 1 : 0.8} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export function Curve({
  data, xKey, yKey, height = 120, ydomain,
}: { data: any[]; xKey: string; yKey: string; height?: number; ydomain?: [number, number] }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 6, right: 10, bottom: 0, left: -18 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey={xKey} tick={AXIS} tickLine={false} axisLine={{ stroke: GRID }} />
        <YAxis tick={AXIS} tickLine={false} axisLine={false} width={44} domain={ydomain} />
        <Tooltip {...tip} />
        <Line type="monotone" dataKey={yKey} stroke="#5bb0ff" strokeWidth={2}
          dot={{ r: 2.5, fill: "#5bb0ff" }} activeDot={{ r: 4 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function HBars({
  data, height = 190,
}: { data: { name: string; value: number }[]; height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout="vertical" margin={{ top: 2, right: 24, bottom: 2, left: 8 }}>
        <XAxis type="number" hide />
        <YAxis type="category" dataKey="name" tick={{ ...AXIS, fontSize: 11 }} width={168}
          tickLine={false} axisLine={false} />
        <Tooltip {...tip} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
        <Bar dataKey="value" fill="#5bb0ff" radius={[0, 3, 3, 0]} barSize={12} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function YearStrip({
  series, nowYear = 2026,
}: { series: { year: number; feasible: boolean }[]; nowYear?: number }) {
  return (
    <div className="my-2.5 flex gap-[2px]">
      {series.map((s, i) => (
        <i key={i} title={`${s.year}`}
          className={`h-5 flex-1 rounded-[2px] ${s.feasible ? "bg-crit" : "bg-ink-700"} ${
            s.year === nowYear ? "outline outline-2 -outline-offset-2 outline-brand" : ""}`} />
      ))}
    </div>
  );
}
