import type { ClientSummary, DriverConfig, PriorityRow } from "@/lib/types";

/** Minimal fixtures shaped like the API's real payloads. Deliberately hand-
 *  written rather than snapshotted: a snapshot of a broken render is a test
 *  that locks the bug in. */

export function priorityRow(over: Partial<PriorityRow> = {}): PriorityRow {
  return {
    driver_id: "working_capital_pct",
    label: "Working capital",
    category: "Working Capital",
    owner: "Head of Treasury",
    metric: "free_cash_flow",
    unit: "pct",
    range_low: 21,
    range_high: 23.5,
    range_basis: "stated plausible range",
    value_at_low: 1200,
    value_at_high: 560,
    value_at_base: 1069,
    exposure: -639.6,
    exposure_magnitude: 639.6,
    downside: -509,
    per_unit: -255.8,
    confidence: "High",
    materiality: "High",
    uncertainty: "Low",
    controllability: "High",
    priority: "Act",
    basis: { materiality: "computed", uncertainty: "declared", controllability: "declared" },
    rationale: "Large exposure on a firm assumption.",
    ...over,
  };
}

export function summary(over: Partial<ClientSummary> = {}): ClientSummary {
  return {
    id: "adidas",
    name: "adidas AG",
    short_label: "adidas",
    data_basis: "Public Data",
    industry: "Sporting goods",
    currency: "EUR",
    currency_symbol: "€",
    unit: "millions",
    fiscal_year: "FY2025",
    objective: "Free Cash Flow",
    is_synthetic: false,
    has_backtest: true,
    disclaimer: "Built from published annual reports.",
    audiences: ["CFO"],
    ...over,
  };
}

export const driverConfig: DriverConfig = {
  volume_growth: {
    maps_to: "division_growth", role: "base", category: "Commercial",
    label: "Volume growth", unit: "pct", min: -8, max: 12, step: 0.5, default: 3,
    guidance_low: null, guidance_high: null, guidance_text: "", confidence: "Medium",
    source: "Synthetic",
  } as DriverConfig[string],
  price_growth: {
    maps_to: "division_growth", role: "add", category: "Commercial",
    label: "Price / mix", unit: "pct", min: -3, max: 8, step: 0.25, default: 2,
    guidance_low: null, guidance_high: null, guidance_text: "", confidence: "Medium",
    source: "Synthetic",
  } as DriverConfig[string],
  capex_eur_m: {
    maps_to: "capex_eur_m", role: "base", category: "Investment",
    label: "Capex", unit: "eur_m", min: 70, max: 170, step: 5, default: 115,
    guidance_low: null, guidance_high: null, guidance_text: "", confidence: "Medium",
    source: "Synthetic",
  } as DriverConfig[string],
};
