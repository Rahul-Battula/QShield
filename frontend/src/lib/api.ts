/* Typed fetch helpers for the QShield API. */

export async function get<T = any>(path: string): Promise<T> {
  const r = await fetch(path);
  if (!r.ok) throw new Error((await r.text()) || `HTTP ${r.status}`);
  return r.json();
}

export async function post<T = any>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
  if (!r.ok) throw new Error((await r.text()) || `HTTP ${r.status}`);
  return r.json();
}

/* ---- response shapes (only the fields the UI reads) ---- */

export type Exposure =
  | "CLASSICALLY_BROKEN" | "QUANTUM_BROKEN" | "QUANTUM_WEAKENED"
  | "QUANTUM_SAFE" | "UNKNOWN";

export interface Health { status: string; version: string; qiskit: boolean; }

export interface Policy {
  active_suite: string;
  suites: Record<string, { kem: string; sig: string }>;
  mosca: { active_preset: string; presets: Record<string, number>; crqc_year: number };
}

export interface CbomAsset {
  asset_id: string; exposure: Exposure; detail: string; kind: string;
  location: string; recommendation: string;
  data_classification: string; data_retention_years: number;
  network_exposure: string; confidence: number;
}
export interface Cbom {
  summary: Record<string, number>;
  assets: CbomAsset[];
  generated_at: string;
}

export interface RiskReport {
  summary: {
    bands: Record<"P1" | "P2" | "P3" | "P4", number>;
    too_late: number; crqc_year: number; assessment_year: number;
  };
  scores: { score: number; band: string; system: string;
            asset: { detail: string; location: string } }[];
  work_packages: { id: string; title: string; top_band: string; size: number;
                   total_migration_years: number; max_score: number }[];
}

export interface MlRank {
  model: {
    regressor: Record<string, number>;
    metrics: { regressor_r2: number; classifier_accuracy: number };
  };
  count: number;
  queue: {
    rank: number; asset_id: string; detail: string;
    priority_score: number; priority_band: "High" | "Medium" | "Low";
    explanation: string;
  }[];
}

export interface QuantumRun {
  backend: string; n_qubits: number;
  depth_pre_transpile: number; depth_post_transpile: number;
  ops: Record<string, number>; wall_ms: number; diagram: string;
  histogram: Record<string, number>;
}
export interface GroverRun extends QuantumRun {
  measured: number; target: number; iterations: number;
  optimal_iterations: number; success_probability: number;
  success_curve: { iterations: number; success_probability: number }[];
}
export interface ShorRun extends QuantumRun {
  N: number; a: number; mode: string; order: number | null;
  order_verified: boolean; factors: number[];
  counting_qubits: number; work_qubits: number;
}
export interface CompareRun {
  N: number; a: number; noise_applied: boolean; note: string;
  ideal: ShorRun; noisy: ShorRun;
}
export interface Estimate {
  target: string; attack: string; logical_qubits: number;
  code_distance: number; physical_qubits: number;
  runtime_human: string; feasible_year: number | null; disclaimer: string;
  growth_curve: { year: number; available_physical_qubits: number; feasible: boolean }[];
}

export interface WavePlan {
  deadline: string; total_effort_years: number; total_findings: number;
  waves: {
    id: string; name: string; band: string; start_date: string; target_date: string;
    effort_years: number; risk_reduction_pct: number; target_suite: string;
    size: number;
    items: { detail: string; location: string; kind: string; score: number;
             past_start_date: boolean }[];
  }[];
}

export interface Benchmark {
  iterations: number;
  machine: { implementation: string; python: string; platform: string };
  suites: {
    suite: string; live: boolean; handshake_ms: number | null;
    handshake_vs_classical: number | null;
    timings: Record<string, { median_ms: number }>;
    sizes: { kem_public: number | null; ciphertext: number | null; signature: number | null };
  }[];
}

export interface MigrationResult {
  thesis_ok: boolean; thesis_error: string | null;
  summary: {
    from_suite: string; to_suite: string; records: number; records_changed: number;
    algorithms_before: string[][]; algorithms_after: string[][];
    before_all_valid: boolean; after_all_valid: boolean;
    app_code_touched: boolean; reseal_seconds: number;
  };
  records: {
    record_id: string;
    before: { kem: string; sig: string }; after: { kem: string; sig: string };
    reseal_ms: number;
  }[];
}
