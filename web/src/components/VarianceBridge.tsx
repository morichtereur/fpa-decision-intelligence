import type { VarianceBridgeResponse } from "@/lib/types";
import { formatDriverValue, formatEurSigned } from "@/lib/format";
import BridgeChart from "./BridgeChart";
import styles from "./VarianceBridge.module.css";

/**
 * The forecast-to-actual bridge. Reuses BridgeChart rather than drawing a
 * second waterfall: the API emits the same {label, value, delta} shape the
 * Scenario Planner's bridge uses, so both are one chart fed by one contract.
 *
 * The residual is a row on the chart, not a footnote. It is the part of the
 * variance no driver explains, and a bridge that renders only the drivers
 * invites the reader to believe they add up.
 */
export default function VarianceBridge({ bridge }: { bridge: VarianceBridgeResponse }) {
  const largest = bridge.steps.reduce((a, b) => (Math.abs(b.impact) > Math.abs(a.impact) ? b : a));

  return (
    <div className={styles.wrap}>
      <BridgeChart steps={bridge.waterfall} />

      <table className={styles.table}>
        <thead>
          <tr>
            <th>Driver</th>
            <th className={styles.num}>Assumed</th>
            <th className={styles.num}>Actual</th>
            <th className={styles.num}>Impact</th>
          </tr>
        </thead>
        <tbody>
          {bridge.steps.map((step) => (
            <tr
              key={step.driver_id}
              className={step.driver_id === largest.driver_id ? styles.largest : undefined}
            >
              <td>
                {step.label}
                <div className={styles.source}>{step.source}</div>
              </td>
              <td className={`mono ${styles.num}`}>
                {formatDriverValue(step.forecast_value, step.unit)}
              </td>
              <td className={`mono ${styles.num}`}>
                {formatDriverValue(step.actual_value, step.unit)}
              </td>
              <td
                className={`mono ${styles.num} ${step.impact >= 0 ? styles.positive : styles.negative}`}
              >
                {formatEurSigned(step.impact)}
              </td>
            </tr>
          ))}
          <tr>
            <td>
              Residual
              <div className={styles.source}>not attributable to any driver</div>
            </td>
            <td className={styles.num}>—</td>
            <td className={styles.num}>—</td>
            <td className={`mono ${styles.num}`}>{formatEurSigned(bridge.residual)}</td>
          </tr>
        </tbody>
      </table>

      {bridge.offsetting_note && (
        <p className={`${styles.note} ${styles.callout}`}>{bridge.offsetting_note}</p>
      )}
      <p className={styles.note}>{bridge.residual_note}</p>
      <p className={styles.note}>{bridge.order_note}</p>
    </div>
  );
}
