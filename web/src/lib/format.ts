/**
 * Every number the product shows goes through here. The model's internal
 * unit is always € millions (matching src/model.py) — these functions are
 * the only place that decides how a human reads that number.
 */

export function formatEur(valueEurM: number): string {
  const abs = Math.abs(valueEurM);
  if (abs >= 1000) {
    return `€${(valueEurM / 1000).toFixed(2)}bn`;
  }
  return `€${Math.round(valueEurM).toLocaleString("en-US")}m`;
}

export function formatEurSigned(valueEurM: number): string {
  const sign = valueEurM > 0 ? "+" : valueEurM < 0 ? "−" : "";
  return `${sign}${formatEur(Math.abs(valueEurM))}`;
}

/** A share of sales, a margin, a growth rate — always one decimal. */
export function formatPct(value: number): string {
  return `${value.toFixed(1)}%`;
}

/**
 * The change between two already-percentage figures (e.g. working capital
 * 21.5% -> 23.0%) is a move in PERCENTAGE POINTS, not a percentage change
 * of the percentage — a distinction FP&A readers care about and that a
 * naive formatter would blur.
 */
export function formatPp(deltaPoints: number): string {
  const sign = deltaPoints > 0 ? "+" : deltaPoints < 0 ? "−" : "";
  return `${sign}${Math.abs(deltaPoints).toFixed(1)}pp`;
}

export function formatSignedPct(value: number): string {
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  return `${sign}${Math.abs(value).toFixed(1)}%`;
}

export type DeltaDirection = "positive" | "negative" | "neutral";

/** Whether a delta reads as an improvement. For FCF/revenue/operating
 * profit, bigger is better. Callers pass `invert: true` for metrics where
 * that's reversed (there are none in this model yet, but the hook exists
 * rather than hardcoding the assumption everywhere it's used). */
export function deltaDirection(value: number, invert = false): DeltaDirection {
  if (Math.abs(value) < 1e-9) return "neutral";
  const positive = invert ? value < 0 : value > 0;
  return positive ? "positive" : "negative";
}

/**
 * A driver's own value, in its own unit.
 *
 * Units are per client: a manufacturer plans working capital in days and input
 * costs in points against plan, where a branded business plans the same cash
 * as a single percentage of sales. `ppt` always carries a sign because it is
 * a movement, never a level.
 */
export function formatDriverValue(value: number, unit: string): string {
  switch (unit) {
    case "days":
      return `${value.toFixed(0)} days`;
    case "ppt":
      return `${value > 0 ? "+" : value < 0 ? "\u2212" : ""}${Math.abs(value).toFixed(2)}pp`;
    case "eur_m":
      return formatEur(value);
    default:
      return formatPct(value);
  }
}
