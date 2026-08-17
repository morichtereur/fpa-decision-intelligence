import type { BacktestResult } from "@/lib/types";
import styles from "./BacktestBars.module.css";

const METRICS: { key: "revenue_error_pct" | "operating_profit_error_pct" | "free_cash_flow_error_pct"; label: string }[] = [
  { key: "revenue_error_pct", label: "Revenue" },
  { key: "operating_profit_error_pct", label: "Operating profit" },
  { key: "free_cash_flow_error_pct", label: "Free cash flow" },
];

export default function BacktestBars({ backtest }: { backtest: BacktestResult }) {
  const maxError = Math.max(
    ...METRICS.map((m) => Math.abs(backtest.naive[m.key] ?? 0)),
    ...METRICS.map((m) => Math.abs(backtest.driver_based[m.key] ?? 0)),
  );

  return (
    <div className={styles.chart}>
      <div className={styles.legend}>
        <span className={styles.legendItem}>
          <span className={`${styles.swatch} ${styles.swatchNaive}`} /> Naive extrapolation
        </span>
        <span className={styles.legendItem}>
          <span className={`${styles.swatch} ${styles.swatchDriven}`} /> Driver-based
        </span>
      </div>
      {METRICS.map((m) => {
        const naive = Math.abs(backtest.naive[m.key] ?? 0);
        const driven = Math.abs(backtest.driver_based[m.key] ?? 0);
        return (
          <div key={m.key} className={styles.row}>
            <div className={styles.rowLabel}>{m.label}</div>
            <div className={styles.bars}>
              <div className={styles.barTrack}>
                <div
                  className={`${styles.bar} ${styles.barDriven}`}
                  style={{ width: `${(driven / maxError) * 100}%` }}
                />
                <span className={`mono ${styles.barValue}`}>{driven.toFixed(1)}%</span>
              </div>
              <div className={styles.barTrack}>
                <div
                  className={`${styles.bar} ${styles.barNaive}`}
                  style={{ width: `${(naive / maxError) * 100}%` }}
                />
                <span className={`mono ${styles.barValue}`}>{naive.toFixed(1)}%</span>
              </div>
            </div>
          </div>
        );
      })}
      <div className={styles.footnote}>Absolute forecast error vs. FY2025 actuals</div>
    </div>
  );
}
