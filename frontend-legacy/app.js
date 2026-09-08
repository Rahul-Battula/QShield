/* QShield dashboard — React 18 (UMD), no build step, no JSX.
   `h` is React.createElement; each view is a thin, styled render over a /api/ endpoint. */
(function () {
  "use strict";
  var h = React.createElement;
  var useState = React.useState, useEffect = React.useEffect, useCallback = React.useCallback;
  var F = React.Fragment;

  /* ---- data ------------------------------------------------------ */
  function api(path, opts) {
    return fetch(path, Object.assign({ headers: { "Content-Type": "application/json" } }, opts))
      .then(function (r) {
        if (!r.ok) return r.text().then(function (t) { throw new Error(t || ("HTTP " + r.status)); });
        return r.json();
      });
  }
  function post(path, body) { return api(path, { method: "POST", body: JSON.stringify(body || {}) }); }

  function useAsync(fn, deps) {
    var st = useState({ loading: true, data: null, error: null });
    var state = st[0], set = st[1];
    var run = useCallback(function () {
      set({ loading: true, data: null, error: null });
      Promise.resolve().then(fn)
        .then(function (d) { set({ loading: false, data: d, error: null }); })
        .catch(function (e) { set({ loading: false, data: null, error: String(e.message || e) }); });
    }, deps || []);
    useEffect(run, [run]);
    return [state, run];
  }

  /* ---- primitives ---------------------------------------------- */
  var EXPO = {
    CLASSICALLY_BROKEN: ["s-crit", "BROKEN NOW"],
    QUANTUM_BROKEN: ["s-high", "QUANTUM-BROKEN"],
    QUANTUM_WEAKENED: ["s-med", "WEAKENED"],
    QUANTUM_SAFE: ["s-ok", "SAFE"],
    UNKNOWN: ["s-neutral", "UNKNOWN"],
  };
  var BAND = { P1: ["s-crit", "P1"], P2: ["s-high", "P2"], P3: ["s-med", "P3"], P4: ["s-ok", "P4"] };

  function fmt(x, d) {
    if (x == null) return "–";
    return typeof x === "number" ? x.toFixed(d == null ? 2 : d) : String(x);
  }

  function Shield() {
    return h("svg", { viewBox: "0 0 24 24", "aria-hidden": "true" },
      h("path", {
        d: "M12 2.4l7.2 2.7v5.6c0 4.6-3 7.8-7.2 9.3-4.2-1.5-7.2-4.7-7.2-9.3V5.1z",
        fill: "none", stroke: "#e9ebef", strokeWidth: "1.5", strokeLinejoin: "round",
      }),
      h("path", { d: "M12 9.1a2 2 0 00-1 3.75V15h2v-2.15A2 2 0 0012 9.1z", fill: "#4c9dff" }));
  }

  function Pill(p) {
    return h("span", {
      className: "pill " + (p.tone || "s-neutral") + (p.plain ? " plain" : ""),
    }, p.children);
  }
  function Loader() { return h("div", { className: "loader" }); }
  function ErrBox(p) { return h("div", { className: "err" }, "Could not load: " + p.msg); }

  function Async(p) {
    if (p.state.loading) return h(F, null, h(Loader), p.skeleton || null);
    if (p.state.error) return h(ErrBox, { msg: p.state.error });
    return p.children;
  }

  function ViewHead(p) {
    return h("div", { className: "view-head" }, h("h1", null, p.title), h("p", null, p.desc));
  }

  function Kpis(p) {
    return h("div", { className: "kpis" }, p.items.map(function (k, i) {
      return h("div", { className: "kpi", key: i },
        h("div", { className: "label" }, k.label),
        h("div", { className: "value " + (k.tone || "") }, k.value),
        k.sub ? h("div", { className: "sub" }, k.sub) : null);
    }));
  }

  function Panel(p) {
    var head = (p.title || p.actions)
      ? h("div", { className: "panel-head" },
          h("h2", null, p.title),
          p.hint ? h("span", { className: "hint" }, p.hint) : null,
          p.actions || null)
      : null;
    return h("div", { className: "panel" + (p.flush ? " flush" : "") }, head, p.children);
  }

  function DistBar(p) {
    var total = p.segments.reduce(function (a, s) { return a + s.value; }, 0) || 1;
    return h(F, null,
      h("div", { className: "distbar" }, p.segments.map(function (s, i) {
        return h("span", { key: i, className: s.cls, style: { width: (100 * s.value / total) + "%" } });
      })),
      h("div", { className: "distlegend" }, p.segments.map(function (s, i) {
        return h("span", { key: i },
          h("i", { style: { background: "var(" + s.varr + ")" } }), s.label, " ", h("b", null, s.value));
      })));
  }

  // cols: [{ label, cls }]   rows: [[cell, cell, ...]]
  function Table(p) {
    return h("div", { className: "scroll" },
      h("table", null,
        h("thead", null,
          h("tr", null, p.cols.map(function (c, i) {
            return h("th", { key: i, className: c.cls || "" }, c.label);
          }))),
        h("tbody", null, p.rows.map(function (row, ri) {
          return h("tr", { key: ri }, row.map(function (cell, ci) {
            var cls = p.cols[ci] && p.cols[ci].cls;
            var isObj = cell && typeof cell === "object" && "node" in cell;
            return h("td", {
              key: ci, className: cls || "",
              title: isObj ? cell.title : undefined,
              onClick: isObj ? cell.onClick : undefined,
            }, isObj ? cell.node : cell);
          }));
        }))));
  }
  // cell with an explicit class override / title
  function cell(node, opts) { return Object.assign({ node: node }, opts || {}); }

  function Slider(p) {
    return h("div", { className: "slider" },
      h("label", null, p.label),
      h("div", { className: "row" },
        h("input", { type: "range", min: p.min, max: p.max, step: p.step, value: p.value,
          onChange: function (e) { p.onChange(Number(e.target.value)); } }),
        h("span", { className: "val" }, p.fmt ? p.fmt(p.value) : p.value)));
  }
  function Metrics(p) {
    return h("div", { className: "metrics" }, p.items.map(function (m, i) {
      return h("div", { className: "metric", key: i },
        h("div", { className: "k" }, m[0]), h("div", { className: "v" }, m[1]));
    }));
  }
  function Histo(p) {
    var entries = Object.entries(p.data || {}).map(function (e) { return [Number(e[0]), e[1]]; })
      .sort(function (a, b) { return a[0] - b[0]; });
    var max = Math.max(1, ...entries.map(function (e) { return e[1]; }));
    return h("div", { className: "histo-wrap" },
      p.title ? h("div", { className: "k", style: { fontSize: 10, letterSpacing: ".09em",
        textTransform: "uppercase", color: "var(--fg-3)", marginBottom: 6 } }, p.title) : null,
      h("div", { className: "histo" }, entries.map(function (e, i) {
        return h("div", { key: i, className: "bar" + (e[0] === p.mark ? " mark" : ""),
          style: { height: (100 * e[1] / max) + "%" }, title: e[0] + " → " + e[1] },
          entries.length <= 20 ? h("span", { className: "lbl" }, e[0]) : null);
      })));
  }
  function Diagram(p) {
    if (!p.text) return null;
    return h("pre", { className: "diagram" }, p.text);
  }

  /* ---- Quantum Lab ----------------------------------------- */
  function QLab() {
    var health = useAsync(function () { return api("/api/health"); }, [])[0];
    return h(F, null,
      h(ViewHead, { title: "Quantum Lab",
        desc: "Shor and Grover as real Qiskit circuits on Aer — ideal vs noisy, with the resource projection that scales the mechanism up to RSA-2048." }),
      h(Async, { state: health }, health.data && (health.data.qiskit
        ? h(F, null, h(GroverLab), h(ShorLab), h(CompareLab), h(EstimateLab))
        : h("div", { className: "err" },
            "The Qiskit Lab needs the optional extra: run "
            + "pip install -r requirements-qiskit.txt, then restart. "
            + "(The Threat tab's demos still run on the bundled simulator.)"))));
  }

  function runState() {
    var s = useState({ busy: false, res: null, err: null });
    return [s[0], function (fn) {
      s[1]({ busy: true, res: null, err: null });
      fn().then(function (r) { s[1]({ busy: false, res: r, err: null }); })
        .catch(function (e) { s[1]({ busy: false, res: null, err: String(e.message || e) }); });
    }];
  }

  function NoiseControls(p) {
    if (p.backend !== "noisy") return null;
    return h(F, null,
      h(Slider, { label: "1-qubit error", min: 0, max: 0.05, step: 0.001, value: p.p1,
        onChange: p.set("p1"), fmt: function (v) { return v.toExponential(1); } }),
      h(Slider, { label: "2-qubit error", min: 0, max: 0.1, step: 0.002, value: p.p2,
        onChange: p.set("p2"), fmt: function (v) { return v.toExponential(1); } }),
      h(Slider, { label: "readout error", min: 0, max: 0.1, step: 0.002, value: p.readout,
        onChange: p.set("readout"), fmt: function (v) { return v.toExponential(1); } }));
  }

  function BackendPicker(p) {
    return h("div", { className: "slider" }, h("label", null, "backend"),
      h("div", { className: "chips" }, ["ideal", "noisy", "matrix"].map(function (n) {
        return h("button", { key: n, className: "chip" + (p.value === n ? " is-active" : ""),
          onClick: function () { p.onChange(n); } }, n);
      })));
  }

  function GroverLab() {
    var f = useState({ n_bits: 4, backend: "ideal", p1: 1e-3, p2: 1e-2, readout: 2e-2 });
    var st = runState();
    var set = function (k) { return function (v) { f[1](Object.assign({}, f[0], k ? mk(k, v) : v)); }; };
    function mk(k, v) { var o = {}; o[k] = v; return o; }
    function run() { st[1](function () { return post("/api/quantum/grover", f[0]); }); }
    var r = (st[0].res && st[0].res.measured != null) ? st[0].res : null;
    return h(Panel, { title: "Grover search — a marked key in an n-bit space",
      actions: h("button", { className: "btn primary", disabled: st[0].busy, onClick: run },
        st[0].busy ? "Running…" : "Run") },
      h("div", { className: "controls" },
        h(Slider, { label: "key bits (n)", min: 2, max: 7, step: 1, value: f[0].n_bits,
          onChange: set("n_bits") }),
        h(BackendPicker, { value: f[0].backend, onChange: set("backend") }),
        h(NoiseControls, { backend: f[0].backend, p1: f[0].p1, p2: f[0].p2, readout: f[0].readout, set: set })),
      st[0].err ? h("div", { className: "err" }, st[0].err) : null,
      r ? h(F, null,
        h(Metrics, { items: [
          ["measured", r.measured + " / " + r.target],
          ["P(success)", fmt(r.success_probability, 3)],
          ["iterations", r.iterations + " of " + r.optimal_iterations],
          ["qubits", r.n_qubits],
          ["depth", r.depth_pre_transpile + " → " + r.depth_post_transpile],
          ["backend", r.backend],
          ["wall", r.wall_ms + " ms"],
        ] }),
        h("div", { className: "k", style: { fontSize: 10, letterSpacing: ".09em",
          textTransform: "uppercase", color: "var(--fg-3)", margin: "4px 0 2px" } },
          "success probability vs iterations"),
        h("div", { className: "curve" }, (r.success_curve || []).map(function (p, i, arr) {
          return h("div", { key: i, className: "pt" + (i === arr.length - 1 ? " best" : ""),
            style: { height: (100 * p.success_probability) + "%" },
            title: "it " + p.iterations + " → " + p.success_probability },
            h("span", null, p.iterations));
        })),
        h(Histo, { data: r.histogram, mark: r.target, title: "measurement counts" }),
        h(Diagram, { text: r.diagram })) : null);
  }

  function ShorLab() {
    var f = useState({ N: 15, a: 2, backend: "ideal", p1: 1e-3, p2: 1e-2, readout: 2e-2 });
    var st = runState();
    function set(k) { return function (v) { var o = Object.assign({}, f[0]); o[k] = v; f[1](o); }; }
    function run() { st[1](function () { return post("/api/quantum/shor", f[0]); }); }
    var r = (st[0].res && st[0].res.N) ? st[0].res : null;
    return h(Panel, { title: "Shor — factor N by quantum order-finding",
      actions: h("button", { className: "btn primary", disabled: st[0].busy, onClick: run },
        st[0].busy ? "Running…" : "Run") },
      h("div", { className: "controls" },
        h("div", { className: "slider" }, h("label", null, "N"),
          h("div", { className: "chips" }, [15, 21, 35].map(function (n) {
            return h("button", { key: n, className: "chip" + (f[0].N === n ? " is-active" : ""),
              onClick: function () { set("N")(n); } }, n);
          }))),
        h(Slider, { label: "base a", min: 2, max: 13, step: 1, value: f[0].a, onChange: set("a") }),
        h(BackendPicker, { value: f[0].backend, onChange: set("backend") })),
      st[0].err ? h("div", { className: "err" }, st[0].err) : null,
      r ? h(F, null,
        h(Metrics, { items: [
          ["N", r.N + " = " + (r.factors.length ? r.factors.join(" × ") : "?")],
          ["order r", r.order == null ? "—" : r.order],
          ["verified", String(r.order_verified)],
          ["qubits", r.n_qubits + " (" + r.counting_qubits + "+" + r.work_qubits + ")"],
          ["mode", r.mode],
          ["depth", r.depth_pre_transpile + " → " + r.depth_post_transpile],
          ["wall", r.wall_ms + " ms"],
        ] }),
        h(Histo, { data: r.histogram, title: "counting-register measurements" }),
        h(Diagram, { text: r.diagram })) : null);
  }

  function CompareLab() {
    var f = useState({ N: 15, a: 7 });
    var st = runState();
    function run() { st[1](function () { return post("/api/quantum/compare", f[0]); }); }
    var r = (st[0].res && st[0].res.ideal) ? st[0].res : null;
    return h(Panel, { title: "Ideal vs noisy — the same Shor circuit, both backends",
      actions: h(F, null,
        h("div", { className: "chips", style: { display: "inline-flex", marginRight: 8 } },
          [15, 21, 35].map(function (n) {
            return h("button", { key: n, className: "chip" + (f[0].N === n ? " is-active" : ""),
              onClick: function () { f[1]({ N: n, a: f[0].a }); } }, n);
          })),
        h("button", { className: "btn primary", disabled: st[0].busy, onClick: run },
          st[0].busy ? "Running…" : "Compare")) },
      st[0].err ? h("div", { className: "err" }, st[0].err) : null,
      r ? h(F, null,
        r.note ? h("p", { className: "prose" }, r.note) : null,
        h("div", { className: "histo-pair" },
          h("div", null,
            h("div", { className: "kv" }, h("div", null, "ideal → ",
              h("b", null, r.ideal.factors.join(" × ") || "no factors"))),
            h(Histo, { data: r.ideal.histogram })),
          h("div", null,
            h("div", { className: "kv" }, h("div", null,
              (r.noise_applied ? "noisy" : "sampling spread") + " → ",
              h("b", null, r.noisy.factors.join(" × ") || "no factors"))),
            h(Histo, { data: r.noisy.histogram })))) : null);
  }

  function EstimateLab() {
    var f = useState({ algorithm: "RSA", key_bits: 2048, phys_error_rate: 1e-3, annual_growth: 1.5 });
    var st = runState();
    function set(k) { return function (v) { var o = Object.assign({}, f[0]); o[k] = v; f[1](o); }; }
    function run() { st[1](function () { return post("/api/quantum/estimate", f[0]); }); }
    useEffect(run, []); // eslint-disable-line
    var r = (st[0].res && st[0].res.attack) ? st[0].res : null;
    var TARGETS = [["RSA", 2048], ["RSA", 3072], ["ECC", 256], ["AES", 128], ["AES", 256]];
    return h(Panel, { title: "Resource projection — scaling the mechanism to real key sizes",
      hint: "a projection under the stated assumptions, not a prediction" },
      h("div", { className: "controls" },
        h("div", { className: "slider" }, h("label", null, "target"),
          h("div", { className: "chips" }, TARGETS.map(function (t) {
            var on = f[0].algorithm === t[0] && f[0].key_bits === t[1];
            return h("button", { key: t.join(), className: "chip" + (on ? " is-active" : ""),
              onClick: function () { var o = Object.assign({}, f[0]); o.algorithm = t[0]; o.key_bits = t[1]; f[1](o); } },
              t[0] + "-" + t[1]);
          }))),
        h(Slider, { label: "physical error rate", min: 0.0001, max: 0.005, step: 0.0001,
          value: f[0].phys_error_rate, onChange: set("phys_error_rate"),
          fmt: function (v) { return v.toExponential(1); } }),
        h(Slider, { label: "qubit growth / yr", min: 1.1, max: 3, step: 0.1,
          value: f[0].annual_growth, onChange: set("annual_growth"), fmt: function (v) { return v.toFixed(1) + "×"; } }),
        h("button", { className: "btn", disabled: st[0].busy, onClick: run }, "Recompute")),
      st[0].err ? h("div", { className: "err" }, st[0].err) : null,
      r ? h(F, null,
        h(Metrics, { items: [
          ["attack", r.attack.split(" ")[0]],
          ["logical qubits", Number(r.logical_qubits).toLocaleString()],
          ["code distance", r.code_distance],
          ["physical qubits", Number(r.physical_qubits).toExponential(2)],
          ["runtime", r.runtime_human],
          ["feasible year", r.feasible_year || "beyond curve"],
        ] }),
        h("div", { className: "k", style: { fontSize: 10, letterSpacing: ".09em",
          textTransform: "uppercase", color: "var(--fg-3)", margin: "6px 0 2px" } },
          "years until enough physical qubits exist (red = feasible)"),
        h("div", { className: "yearstrip" }, (r.growth_curve || []).map(function (s, i) {
          return h("i", { key: i, className: (s.feasible ? "feasible" : "") + (s.year === 2026 ? " now" : ""),
            title: s.year + ": " + Number(s.available_physical_qubits).toExponential(1) + " qubits" });
        })),
        h("p", { className: "prose" }, r.disclaimer)) : null);
  }

  /* ---- Overview ---------------------------------------------- */
  function Overview() {
    var r = useAsync(function () {
      return Promise.all([
        api("/api/policy"), api("/api/discovery"), api("/api/risk"), api("/api/threat"),
      ]).then(function (a) { return { policy: a[0], disc: a[1], risk: a[2], threat: a[3] }; });
    }, []);
    var st = r[0], reloadAll = r[1];
    var busy = useState(false);
    function swap(name) {
      busy[1](true);
      post("/api/policy/active", { suite: name }).then(reloadAll).finally(function () { busy[1](false); });
    }
    return h(F, null,
      h(ViewHead, {
        title: "Overview",
        desc: "The estate at a glance, and the one control that performs a migration.",
      }),
      h(Async, { state: st }, st.data && renderOverview(st.data, busy[0], swap)));
  }
  function renderOverview(d, busy, swap) {
    var sum = d.disc.summary;
    var suite = d.policy.suites[d.policy.active_suite];
    return h(F, null,
      h(Kpis, { items: [
        { label: "Assets inventoried", value: sum.total },
        { label: "P1 findings", value: d.risk.summary.bands.P1, tone: "crit" },
        { label: "Broken by Shor", value: d.threat.summary.shor_targets, tone: "crit" },
        { label: "CRQC horizon", value: d.policy.mosca.crqc_year, tone: "accent",
          sub: d.policy.mosca.active_preset + " preset" },
      ] }),
      h(Panel, {
        title: "Active cryptographic policy",
        hint: "changing this and reloading is the entire migration",
      },
        h("div", { className: "kv", style: { marginBottom: 14 } },
          h("div", null, "suite ", h("b", null, d.policy.active_suite)),
          h("div", null, "KEM ", h("b", null, suite.kem)),
          h("div", null, "signature ", h("b", null, suite.sig))),
        h("div", { className: "chips" }, Object.keys(d.policy.suites).map(function (n) {
          return h("button", {
            key: n, disabled: busy,
            className: "chip" + (n === d.policy.active_suite ? " is-active" : ""),
            onClick: function () { swap(n); },
          }, n);
        }))),
      h(Panel, { title: "Exposure of inventoried cryptography" },
        h(DistBar, { segments: [
          { label: "broken now", value: sum.CLASSICALLY_BROKEN, cls: "b-crit", varr: "--crit" },
          { label: "quantum-broken", value: sum.QUANTUM_BROKEN, cls: "b-high", varr: "--high" },
          { label: "weakened", value: sum.QUANTUM_WEAKENED, cls: "b-med", varr: "--med" },
          { label: "safe", value: sum.QUANTUM_SAFE, cls: "b-ok", varr: "--ok" },
        ] })));
  }

  /* ---- Discovery ------------------------------------------- */
  function Discovery() {
    var st = useAsync(function () { return api("/api/discovery"); }, [])[0];
    return h(F, null,
      h(ViewHead, {
        title: "Discovery",
        desc: "The CBOM — every place the estate uses cryptography, classified by exposure.",
      }),
      h(Async, { state: st }, st.data && (function () {
        var s = st.data.summary;
        return h(F, null,
          h(Kpis, { items: [
            { label: "Total assets", value: s.total },
            { label: "Broken now", value: s.CLASSICALLY_BROKEN, tone: "crit" },
            { label: "Quantum-broken", value: s.QUANTUM_BROKEN, tone: "crit" },
            { label: "Quantum-safe", value: s.QUANTUM_SAFE },
          ] }),
          h(Panel, { flush: true, title: "Cryptographic bill of materials",
            hint: st.data.assets.length + " assets",
            actions: h("a", { className: "btn", href: "/api/cbom/export?format=csv" }, "Export CSV") },
            h(Table, {
              cols: [
                { label: "Exposure" }, { label: "Algorithm", cls: "mono" }, { label: "Kind" },
                { label: "Data class" }, { label: "Retention", cls: "num" },
                { label: "Location", cls: "mono trunc" },
              ],
              rows: st.data.assets.map(function (a) {
                var e = EXPO[a.exposure] || EXPO.UNKNOWN;
                return [
                  h(Pill, { tone: e[0] }, e[1]),
                  a.detail,
                  a.kind.toLowerCase().replace("_", " "),
                  a.data_classification || "—",
                  (a.data_retention_years || "—") + "y",
                  cell(a.location, { title: a.location }),
                ];
              }),
            })));
      })()));
  }

  /* ---- Risk --------------------------------------------- */
  function Risk() {
    var st = useAsync(function () { return api("/api/risk?assessment_year=2026"); }, [])[0];
    return h(F, null,
      h(ViewHead, {
        title: "Risk",
        desc: "Mosca's inequality with exposure and blast radius, ranked and grouped into work packages.",
      }),
      h(Async, { state: st }, st.data && (function () {
        var d = st.data, b = d.summary.bands;
        var rows = d.scores.slice(0, 40).map(function (x, i) {
          var bd = BAND[x.band] || BAND.P4;
          return [
            i + 1, fmt(x.score, 1),
            h(Pill, { tone: bd[0], plain: true }, bd[1]),
            x.asset.detail, x.system,
            cell(x.asset.location, { title: x.asset.location }),
          ];
        });
        return h(F, null,
          h(Kpis, { items: [
            { label: "P1 — do now", value: b.P1, tone: "crit" },
            { label: "P2 — this cycle", value: b.P2 },
            { label: "Past Mosca start date", value: d.summary.too_late, tone: "crit" },
            { label: "CRQC horizon", value: d.summary.crqc_year, tone: "accent",
              sub: "assessed " + d.summary.assessment_year },
          ] }),
          h(Panel, { title: "Priority mix" },
            h(DistBar, { segments: [
              { label: "P1", value: b.P1, cls: "b-crit", varr: "--crit" },
              { label: "P2", value: b.P2, cls: "b-high", varr: "--high" },
              { label: "P3", value: b.P3, cls: "b-med", varr: "--med" },
              { label: "P4", value: b.P4, cls: "b-ok", varr: "--ok" },
            ] })),
          h(Panel, { flush: true, title: "Ranked findings", hint: "top 40" },
            h(Table, {
              cols: [
                { label: "#", cls: "num" }, { label: "Score", cls: "num" }, { label: "Band" },
                { label: "Algorithm", cls: "mono" }, { label: "System" },
                { label: "Location", cls: "mono trunc" },
              ],
              rows: rows,
            })),
          h(Panel, { title: "Work packages" }, d.work_packages.map(function (w) {
            var bd = BAND[w.top_band] || BAND.P4;
            return h("div", {
              key: w.id,
              style: { display: "flex", alignItems: "center", gap: 12, padding: "9px 0",
                borderBottom: "1px solid var(--border-soft)" },
            },
              h("span", { className: "mono", style: { color: "var(--fg-3)", minWidth: 46 } }, w.id),
              h(Pill, { tone: bd[0], plain: true }, bd[1]),
              h("span", { style: { fontWeight: 500 } }, w.title),
              h("span", { style: { marginLeft: "auto", color: "var(--fg-3)", fontSize: 12 } },
                w.size + " findings · " + fmt(w.total_migration_years, 1) + " yr-equiv"));
          })),
          h(MLRank));
      })()));
  }

  function MLRank() {
    var st = useAsync(function () { return api("/api/risk/rank?limit=15"); }, [])[0];
    var sel = useState(null);
    return h(Async, { state: st, skeleton: h("p", { className: "prose" }, "Training the risk model…") },
      st.data && (function () {
        var d = st.data, imp = d.model.regressor;
        var maxImp = Math.max(...Object.values(imp));
        return h(F, null,
          h(Panel, { title: "ML migration queue",
            hint: "GradientBoosting · R² " + d.model.metrics.regressor_r2
              + " · RandomForest acc " + d.model.metrics.classifier_accuracy },
            h(Table, {
              cols: [
                { label: "#", cls: "num" }, { label: "Score", cls: "num" }, { label: "Band" },
                { label: "Algorithm", cls: "mono" }, { label: "Why" },
              ],
              rows: d.queue.map(function (r) {
                var bd = { High: "s-crit", Medium: "s-high", Low: "s-ok" }[r.priority_band];
                return [
                  r.rank, fmt(r.priority_score, 1),
                  cell(h(Pill, { tone: bd, plain: true }, r.priority_band),
                    { onClick: function () { sel[1](r.asset_id); } }),
                  r.detail,
                  cell(h("span", { className: "muted", style: { cursor: "pointer" },
                    onClick: function () { sel[1](r.asset_id); } }, r.explanation)),
                ];
              }),
            })),
          h(Panel, { title: "Feature importance (priority regressor)" },
            Object.entries(imp).sort(function (a, b) { return b[1] - a[1]; }).map(function (e) {
              return h("div", { key: e[0], style: { display: "flex", alignItems: "center",
                gap: 10, margin: "5px 0", fontSize: 12 } },
                h("span", { style: { minWidth: 190, color: "var(--fg-2)" } }, e[0].replace(/_/g, " ")),
                h("span", { style: { flex: 1, height: 8, background: "var(--border-soft)", borderRadius: 4 } },
                  h("span", { style: { display: "block", height: "100%", borderRadius: 4,
                    width: (100 * e[1] / maxImp) + "%", background: "var(--accent)" } })),
                h("span", { className: "mono", style: { minWidth: 44, textAlign: "right" } }, e[1].toFixed(3)));
            })),
          sel[0] ? h(MLExplain, { id: sel[0], onClose: function () { sel[1](null); } }) : null);
      })());
  }

  function MLExplain(p) {
    var st = useAsync(function () { return api("/api/risk/explain/" + p.id); }, [p.id])[0];
    return h(Panel, { title: "Why this asset ranked here",
      actions: h("button", { className: "btn", onClick: p.onClose }, "Close") },
      h(Async, { state: st }, st.data && h(F, null,
        h("p", { className: "prose" }, h("b", null, st.data.detail), " @ ",
          h("code", null, st.data.location), " — ", st.data.summary),
        h(Table, {
          cols: [{ label: "Feature" }, { label: "Value", cls: "num" },
            { label: "Importance", cls: "num" }, { label: "Contribution", cls: "num" }],
          rows: st.data.contributions.map(function (c) {
            return [c.feature.replace(/_/g, " "), c.value, c.importance,
              cell(h("b", { style: { color: c.contribution > 0 ? "var(--crit)" : "var(--ok)" } },
                (c.contribution > 0 ? "+" : "") + c.contribution))];
          }),
        }))));
  }

  /* ---- Threat ----------------------------------------- */
  function Threat() {
    var st = useAsync(function () { return api("/api/threat"); }, [])[0];
    var hz = useAsync(function () { return api("/api/health"); }, [])[0];
    var g = useState(null);
    var eng = useState("python");
    var running = useState(false);
    function runGrover() {
      running[1](true);
      post("/api/threat/demo/grover", { qubits: 4, target: 11, seed: 0, engine: eng[0] })
        .then(g[1]).finally(function () { running[1](false); });
    }
    var haveQiskit = hz.data && hz.data.qiskit;
    return h(F, null,
      h(ViewHead, {
        title: "Threat",
        desc: "Which quantum attack applies to each finding, its published cost, and a demonstration that runs.",
      }),
      h(Async, { state: st }, st.data && (function () {
        var s = st.data.summary;
        var rows = st.data.threats.filter(function (t) { return t.attack !== "none"; }).map(function (t) {
          return [
            h(Pill, { tone: t.attack === "Grover" ? "s-med" : "s-crit", plain: true }, t.attack),
            t.primitive,
            cell(t.location, { title: t.location }),
            t.summary,
          ];
        });
        return h(F, null,
          h(Kpis, { items: [
            { label: "Broken by Shor", value: s.shor_targets, tone: "crit" },
            { label: "Weakened by Grover", value: s.grover_targets },
            { label: "Already classical", value: s.classically_broken, tone: "crit" },
            { label: "Unaffected", value: s.unaffected },
          ] }),
          h(Panel, {
            title: "Live demonstration — Grover search",
            actions: h("div", { style: { display: "flex", gap: 8, alignItems: "center" } },
              haveQiskit ? h("div", { className: "chips" },
                ["python", "qiskit"].map(function (n) {
                  return h("button", {
                    key: n, className: "chip" + (eng[0] === n ? " is-active" : ""),
                    onClick: function () { eng[1](n); },
                  }, n);
                })) : null,
              h("button", {
                className: "btn primary", disabled: running[0], onClick: runGrover,
              }, running[0] ? "Running…" : "Run")),
          },
            g[0]
              ? h("p", { className: "prose" }, "Engine ", h("b", null, g[0].engine || eng[0]),
                  " — measured ", h("b", null, g[0].measured),
                  " (target ", g[0].target, ") after ", g[0].iterations, " iterations · P(success) ",
                  fmt(g[0].success_probability, 3), " · ", h("b", null, g[0].speedup + "×"),
                  " fewer queries than a classical search.")
              : h("p", { className: "prose" },
                  "Runs a real amplitude-amplification circuit — on QShield's bundled "
                  + "statevector simulator, or on Qiskit Aer when the ", h("code", null, "quantum"),
                  " extra is installed.")),
          h(Panel, { flush: true, title: "Findings" },
            h(Table, {
              cols: [
                { label: "Attack" }, { label: "Primitive", cls: "mono" },
                { label: "Location", cls: "mono trunc" }, { label: "Consequence", cls: "wrap" },
              ],
              rows: rows,
            })),
          st.data.horizon ? h("p", { className: "prose" }, st.data.horizon) : null);
      })()));
  }

  /* ---- Benchmark ---------------------------------- */
  function Benchmark() {
    var st = useAsync(function () { return api("/api/benchmark?iterations=15"); }, [])[0];
    return h(F, null,
      h(ViewHead, {
        title: "Benchmark",
        desc: "Timings and sizes for every suite. Reference-only rows show published sizes, never invented timings.",
      }),
      h(Async, {
        state: st,
        skeleton: h("p", { className: "prose" }, "Timing every suite — this takes a moment."),
      }, st.data && (function () {
        var d = st.data;
        var rows = d.suites.map(function (s) {
          var t = s.timings;
          var ms = function (k) { return s.live && t[k] ? t[k].median_ms.toFixed(2) : "–"; };
          return [
            s.suite,
            h(Pill, { tone: s.live ? "s-ok" : "s-neutral", plain: true }, s.live ? "live" : "ref"),
            ms("kem_keygen"), ms("encapsulate"), ms("decapsulate"), ms("sign"), ms("verify"),
            s.handshake_ms == null ? "–" : s.handshake_ms.toFixed(2),
            s.handshake_vs_classical == null ? "–" : s.handshake_vs_classical + "×",
            s.sizes.kem_public || "–", s.sizes.ciphertext || "–", s.sizes.signature || "–",
          ];
        });
        return h(F, null,
          h(Kpis, { items: [
            { label: "Iterations / op", value: d.iterations },
            { label: "Runtime", value: d.machine.implementation,
              sub: d.machine.python + " · " + d.machine.platform },
            { label: "Suites", value: d.suites.length },
          ] }),
          h(Panel, { flush: true, title: "Per-suite cost", hint: "median ms · bytes" },
            h(Table, {
              cols: [
                { label: "Suite", cls: "mono" }, { label: "Live" },
                { label: "KEM keygen", cls: "num" }, { label: "Encaps", cls: "num" },
                { label: "Decaps", cls: "num" }, { label: "Sign", cls: "num" },
                { label: "Verify", cls: "num" }, { label: "Handshake", cls: "num" },
                { label: "vs classical", cls: "num" }, { label: "KEM pub", cls: "num" },
                { label: "Ciphertext", cls: "num" }, { label: "Signature", cls: "num" },
              ],
              rows: rows,
            })));
      })()));
  }

  /* ---- Migrate ---------------------------------- */
  function Migrate() {
    var pol = useAsync(function () { return api("/api/policy"); }, [])[0];
    var s = useState({ to: "pqc", records: 10, running: false, result: null, error: null });
    var f = s[0], set = s[1];
    function patch(o) { set(Object.assign({}, f, o)); }
    function run() {
      patch({ running: true, result: null, error: null });
      post("/api/migration/run", { to_suite: f.to, records: Number(f.records) })
        .then(function (res) { patch({ running: false, result: res }); })
        .catch(function (e) { patch({ running: false, error: String(e.message || e) }); });
    }
    return h(F, null,
      h(ViewHead, {
        title: "Migrate",
        desc: "Run a real migration of the demo land registry and check the crypto-agility claim held.",
      }),
      h(Async, { state: pol }, pol.data && h(F, null,
        h(Panel, { title: "Operation" },
          h("div", { style: { display: "flex", gap: 16, alignItems: "flex-end", flexWrap: "wrap" } },
            h("label", { className: "field" }, "target suite",
              h("select", { value: f.to, onChange: function (e) { patch({ to: e.target.value }); } },
                Object.keys(pol.data.suites).map(function (n) {
                  return h("option", { key: n, value: n }, n);
                }))),
            h("label", { className: "field" }, "records",
              h("input", {
                type: "number", min: 1, max: 200, value: f.records, style: { width: 84 },
                onChange: function (e) { patch({ records: e.target.value }); },
              })),
            h("button", { className: "btn primary", disabled: f.running, onClick: run },
              f.running ? "Running…" : "Run migration")),
          f.error ? h("div", { className: "err", style: { marginTop: 14 } }, f.error) : null),
        f.result ? renderResult(f.result) : null)));
  }
  function renderResult(R) {
    var su = R.summary;
    var before = su.algorithms_before.map(function (p) { return p.join(" / "); });
    var after = su.algorithms_after.map(function (p) { return p.join(" / "); });
    var recRows = R.records.map(function (rec) {
      return [
        rec.record_id,
        h(F, null, rec.before.kem, " → ", h("b", null, rec.after.kem)),
        h(F, null, rec.before.sig, " → ", h("b", null, rec.after.sig)),
        rec.reseal_ms,
      ];
    });
    return h(F, null,
      h(Panel, {
        title: su.from_suite + "  →  " + su.to_suite,
        actions: h("span", { className: "verdict " + (R.thesis_ok ? "pass" : "fail") },
          R.thesis_ok ? "THESIS UPHELD" : "THESIS VIOLATED"),
      },
        R.thesis_error ? h("p", { className: "err" }, R.thesis_error) : null,
        h("div", { className: "diff", style: { margin: "6px 0 16px" } },
          h("div", { className: "card" },
            h("div", { className: "label" }, "before"),
            h("div", { className: "algo" }, before.map(function (x, i) { return h("div", { key: i }, x); }))),
          h("div", { className: "sep" }, "→"),
          h("div", { className: "card" },
            h("div", { className: "label" }, "after"),
            h("div", { className: "algo" }, after.map(function (x, i) { return h("div", { key: i }, x); })))),
        h("div", { className: "kv" },
          h("div", null, "records ", h("b", null, su.records_changed + " / " + su.records + " changed")),
          h("div", null, "verified before / after ",
            h("b", null, String(su.before_all_valid) + " / " + String(su.after_all_valid))),
          h("div", null, "application code ",
            h("b", null, su.app_code_touched ? "MODIFIED" : "UNCHANGED")),
          h("div", null, "re-seal ", h("b", null, (su.reseal_seconds * 1000).toFixed(0) + " ms")))),
      h(Panel, { flush: true, title: "Per-record" },
        h(Table, {
          cols: [
            { label: "Record", cls: "mono" }, { label: "KEM  before → after", cls: "mono" },
            { label: "Signature  before → after", cls: "mono" }, { label: "Re-seal", cls: "num" },
          ],
          rows: recRows,
        })));
  }

  /* ---- shell ---------------------------------- */
  var TABS = [
    ["overview", "Overview", Overview],
    ["discovery", "Discovery", Discovery],
    ["risk", "Risk", Risk],
    ["threat", "Threat", Threat],
    ["qlab", "Quantum Lab", QLab],
    ["benchmark", "Benchmark", Benchmark],
    ["migrate", "Migrate", Migrate],
  ];
  function App() {
    var t = useState("overview"), tab = t[0], setTab = t[1];
    var View = (TABS.find(function (x) { return x[0] === tab; }) || TABS[0])[2];
    return h("div", { className: "app" },
      h("aside", { className: "sidebar" },
        h("div", { className: "brand" },
          h(Shield),
          h("div", null,
            h("div", { className: "name" }, "QShield"),
            h("div", { className: "tag" }, "Command Centre"))),
        h("nav", { className: "nav" }, TABS.map(function (x) {
          return h("button", {
            key: x[0], className: tab === x[0] ? "active" : "",
            onClick: function () { setTab(x[0]); },
          }, h("span", { className: "dot" }), x[1]);
        })),
        h("div", { className: "foot" }, "Post-quantum cryptography", h("br"), "migration, six phases.")),
      h("main", { className: "view" }, h(View, { key: tab })));
  }
  ReactDOM.createRoot(document.getElementById("root")).render(h(App, null));
})();
