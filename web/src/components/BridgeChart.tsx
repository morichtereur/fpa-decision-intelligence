import type { BridgeStep } from "@/lib/types";
import { formatEur, formatEurSigned } from "@/lib/format";
import styles from "./BridgeChart.module.css";

export default function BridgeChart({ steps }: { steps: BridgeStep[] }) {
  if (steps.length <= 1) {
    return <p className={styles.empty}>No assumptions changed — scenario matches Base.</p>;
  }

  const values = steps.map((s) => s.value);
  const domainMax = Math.max(...values, 0);
  const domainMin = Math.min(...values, 0);
  const span = domainMax - domainMin || 1;
  const pct = (v: number) => ((v - domainMin) / span) * 100;

  return (
    <div className={styles.chart}>
      {steps.map((step, i) => {
        const isEndpoint = step.label === "Base" || step.label === "Scenario";
        const prevValue = i > 0 ? steps[i - 1].value : 0;
        const segStart = isEndpoint ? 0 : Math.min(prevValue, step.value);
        const segEnd = isEndpoint ? step.value : Math.max(prevValue, step.value);
        const positive = step.delta === null || step.delta >= 0;

        return (
          <div key={`${step.label}-${i}`} className={styles.row}>
            <div className={styles.rowLabel}>{step.label}</div>
            <div className={styles.track}>
              <div
                className={
                  isEndpoint
                    ? `${styles.bar} ${styles.barEndpoint}`
                    : `${styles.bar} ${positive ? styles.barPositive : styles.barNegative}`
                }
                style={{ left: `${pct(segStart)}%`, width: `${pct(segEnd) - pct(segStart)}%` }}
              />
              <div className={styles.zeroLine} style={{ left: `${pct(0)}%` }} />
            </div>
            <div className={`mono ${styles.rowValue}`}>
              {step.delta === null ? formatEur(step.value) : formatEurSigned(step.delta)}
            </div>
          </div>
        );
      })}
    </div>
  );
}
