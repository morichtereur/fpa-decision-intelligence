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
  maps_to: string;
  role: string;
  category: string;
  label: string;
  unit: "pct" | "eur_m" | "days" | "ppt";
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
  unit: "pct" | "eur_m" | "days" | "ppt";
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
  /** Two independent checks. Grounding: is this number in the table?
   *  Coherence: is it being used to say something the table supports? A
   *  paragraph can pass the first completely and fail the second. */
  coherence?: {
    finding_count: number;
    clean: boolean;
    findings: { kind: string; detail: string; sentence: string }[];
  };
  provenance?: {
    provider: string;
    model: string;
    usage?: { input_tokens: number; output_tokens: number };
  };
  generated_at?: string;
}

// --- Decision materiality -------------------------------------------------

export type Priority = "Critical" | "Act" | "Review" | "Monitor";
export type Band = "High" | "Medium" | "Low";

export interface PriorityRow {
  driver_id: string;
  label: string;
  category: string;
  owner: string;
  metric: string;
  unit: string;
  range_low: number;
  range_high: number;
  range_basis: string;
  value_at_low: number;
  value_at_high: number;
  value_at_base: number;
  /** Signed: the direction of the swing carries meaning. */
  exposure: number;
  exposure_magnitude: number;
  downside: number;
  per_unit: number;
  confidence: Band;
  materiality: Band;
  uncertainty: Band;
  controllability: Band;
  priority: Priority;
  /** Which axes were computed and which are declared judgements. The UI is
   *  required to show this — a judgement must never read as a measurement. */
  basis: { materiality: string; uncertainty: string; controllability: string };
  rationale: string;
}

export interface MethodologyAxis {
  name: string;
  basis: string;
  detail: string;
}

export interface Methodology {
  objective: string;
  objective_metric: string;
  thresholds: { high: number; medium: number };
  threshold_text: string;
  axes: MethodologyAxis[];
  rules: { when: string; then: Priority; why: string }[];
  limitations: string[];
}

export interface PrioritiesResponse {
  ranked: PriorityRow[];
  methodology: Methodology;
}

export interface RuleResult {
  id: string | null;
  label: string;
  metric: string;
  metric_kind: "driver" | "output";
  condition: string;
  threshold: number;
  observed: number;
  breached: boolean;
  severity: "critical" | "high" | "medium" | "low";
  management_question: string;
  suggested_owner: string;
  next_action: string;
  trigger: string;
}

export interface ClientSummary {
  id: string;
  name: string;
  short_label: string;
  data_basis: string;
  industry: string;
  currency: string;
  currency_symbol: string;
  unit: string;
  fiscal_year: string;
  objective: string;
  is_synthetic: boolean;
  has_backtest: boolean;
  disclaimer: string;
  audiences: string[];
}

export interface DecisionBriefResponse {
  client: ClientSummary;
  objective: string;
  objective_metric: string;
  objective_value: number;
  objective_variance: number;
  is_base_case: boolean;
  lead: PriorityRow & {
    threshold: RuleResult | null;
    management_question: string;
    suggested_owner: string;
    next_action: string;
    trigger: string;
    /** Set when the lead exposure is covered by a rule that has NOT fired —
     *  the brief still names who watches it and when. */
    watching_rule: string | null;
  };
  ranked: PriorityRow[];
  rules: RuleResult[];
  breached_count: number;
  attention: {
    state: "critical" | "attention" | "steady";
    headline: string;
    breached: RuleResult[];
    critical_count: number;
    act_count: number;
  };
  methodology: Methodology;
}

export interface VarianceStep {
  driver_id: string;
  label: string;
  unit: string;
  forecast_value: number;
  actual_value: number;
  impact: number;
  share_of_variance_pct: number | null;
  source: string;
}

export interface VarianceBridgeResponse {
  client: string;
  metric: string;
  forecast: number;
  actual: number;
  total_variance: number;
  explained_by_drivers: number;
  residual: number;
  gross_driver_movement: number;
  /** Set when a small net variance is built from large opposing driver
   *  errors — a materially different finding from an accurate forecast. */
  offsetting_note: string | null;
  residual_note: string;
  order_note: string;
  waterfall: BridgeStep[];
  steps: VarianceStep[];
}
