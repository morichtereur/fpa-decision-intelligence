export interface ForecastResult {
  revenue_by_division: Record<string, number>;
  revenue: number;
  ebitda: number;
  da: number;
  operating_profit: number;
  tax: number;
  nopat: number;
  operating_working_capital: number;
  change_in_working_capital: number;
  capex: number;
  free_cash_flow: number;
  assumptions: {
    division_growth: Record<string, number>;
    ebitda_margin_pct: number;
    effective_tax_rate_pct: number;
    operating_working_capital_pct: number;
    capex_eur_m: number;
  };
  baseline_year_used: string;
}

export interface BacktestMethodResult {
  revenue: number;
  operating_profit: number;
  free_cash_flow: number;
  revenue_error_pct?: number;
  operating_profit_error_pct?: number;
  free_cash_flow_error_pct?: number;
}

export interface BacktestResult {
  actual: BacktestMethodResult;
  naive: BacktestMethodResult;
  driver_based: BacktestMethodResult;
}

export interface DriverSpec {
  label: string;
  unit: "pct" | "eur_m";
  min: number;
  max: number;
  step: number;
  default: number;
  guidance_low: number | null;
  guidance_high: number | null;
  guidance_text: string;
  confidence: "High" | "Medium" | "Low";
  source: string;
}

export type DriverConfig = Record<string, DriverSpec>;
export type DriverValues = Record<string, number>;

export interface DriverPriorityRow {
  driver_id: string;
  label: string;
  confidence: "High" | "Medium" | "Low";
  sensitivity: "High" | "Medium" | "Low" | "Not simulated";
  correlation: number | null;
}

export interface ExecutiveStatement {
  headline: string;
  evidence: string[];
}

export interface OutlookResponse {
  forecast: ForecastResult;
  backtest: BacktestResult;
  statement: ExecutiveStatement;
  driver_priority: DriverPriorityRow[];
}

export interface PresetInfo {
  label: string;
  values: DriverValues;
  changed_drivers: string[];
}

export type PresetsResponse = Record<string, PresetInfo>;

export interface BridgeStep {
  label: string;
  value: number;
  delta: number | null;
}

export interface ScenarioResponse {
  base: ForecastResult;
  scenario: ForecastResult;
  deltas: {
    revenue: number;
    operating_profit: number;
    free_cash_flow: number;
    operating_working_capital: number;
  };
  changed_drivers: Record<string, { base: number; value: number }>;
  out_of_guidance: Record<string, boolean>;
  bridge: BridgeStep[];
}

export interface MonteCarloResponse {
  n: number;
  fcf_p10: number;
  fcf_p50: number;
  fcf_p90: number;
  fcf_mean: number;
  fcf_std: number;
  sensitivity_to_fcf: Record<string, number>;
  caveat: string;
  histogram: { counts: number[]; bin_edges: number[] };
}

export interface AssumptionRow {
  driver_id: string;
  label: string;
  current_value: number;
  unit: "pct" | "eur_m";
  source: string;
  guidance_text: string;
  confidence: "High" | "Medium" | "Low";
  sensitivity: string;
  fiscal_year: string;
}

export interface CommentaryResponse {
  text: string;
  grounding: {
    total_claims: number;
    grounded: number;
    ungrounded: string[];
    grounding_rate: number | null;
  };
  generated_at?: string;
}
