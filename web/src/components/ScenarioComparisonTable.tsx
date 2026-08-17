import type { ForecastResult } from "@/lib/types";
import { deltaDirection, formatEur, formatEurSigned } from "@/lib/format";
import styles from "./ScenarioComparisonTable.module.css";

const ROWS: { key: "revenue" | "operating_profit" | "free_cash_flow" | "operating_working_capital"; label: string }[] = [
  { key: "revenue", label: "Revenue" },
  { key: "operating_profit", label: "Operating profit" },
  { key: "free_cash_flow", label: "Free cash flow" },
  { key: "operating_working_capital", label: "Working capital" },
];

export default function ScenarioComparisonTable({
  base,
  scenario,
}: {
  base: ForecastResult;
  scenario: ForecastResult;
}) {
  return (
    <table className={styles.table}>
      <thead>
        <tr>
          <th className={styles.headCell} />
          <th className={`${styles.headCell} ${styles.numCell}`}>Base</th>
          <th className={`${styles.headCell} ${styles.numCell}`}>Scenario</th>
          <th className={`${styles.headCell} ${styles.numCell}`}>Change vs. Base</th>
        </tr>
      </thead>
      <tbody>
        {ROWS.map((row) => {
          const baseValue = base[row.key];
          const scenarioValue = scenario[row.key];
          const delta = scenarioValue - baseValue;
          const invert = row.key === "operating_working_capital"; // more WC tied up is a cash use, not a gain
          return (
            <tr key={row.key} className={styles.bodyRow}>
              <td className={styles.rowLabel}>{row.label}</td>
              <td className={`mono ${styles.numCell}`}>{formatEur(baseValue)}</td>
              <td className={`mono ${styles.numCell}`}>{formatEur(scenarioValue)}</td>
              <td className={`mono ${styles.numCell} ${styles[deltaDirection(delta, invert)]}`}>
                {Math.abs(delta) < 0.5 ? "—" : formatEurSigned(delta)}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
