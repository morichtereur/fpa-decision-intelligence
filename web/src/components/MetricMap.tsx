import type { MetricMapping } from "@/lib/types";
import styles from "./MetricMap.module.css";

const CONTRACT = [
  "date", "entity", "business_unit", "region",
  "account", "metric", "actual", "budget", "forecast",
];

/**
 * How a client's source data resolves to the model's metrics.
 *
 * A ledger-backed client maps account numbers; a client built from published
 * filings maps fact paths in the extracted document. Both shapes render here,
 * because both are answers to the same question — and the column that matters
 * either way is whether the metric is reported or constructed.
 */
export default function MetricMap({ mappings }: { mappings: Record<string, MetricMapping> }) {
  const entries = Object.entries(mappings);
  if (entries.length === 0) {
    return <p className={styles.source}>No mapping is declared for this planning model.</p>;
  }

  return (
    <>
      <p className={styles.contract}>{CONTRACT.join("  ·  ")}</p>
      <div className={styles.wrap}>
        <table className={styles.table}>
          <caption className="visually-hidden">
            Source data mapped to the model&rsquo;s metrics, with the basis of each.
          </caption>
          <thead>
            <tr>
              <th scope="col">Metric</th>
              <th scope="col">Source</th>
              <th scope="col">Statement</th>
              <th scope="col">Basis</th>
            </tr>
          </thead>
          <tbody>
            {entries.map(([metric, spec]) => {
              const accounts = spec.source_accounts ?? [];
              const source =
                accounts.length > 0
                  ? accounts.join(", ")
                  : spec.fact_path ?? "—";
              return (
                <tr key={metric}>
                  <td className={styles.metric}>{metric.replace(/_/g, " ")}</td>
                  <td className={`mono ${styles.source}`}>{source}</td>
                  <td className={styles.source}>{spec.statement}</td>
                  <td>
                    <span
                      className={`${styles.basis} ${
                        spec.basis === "reported" ? styles.reported : styles.derived
                      }`}
                    >
                      {spec.basis}
                    </span>
                    {spec.note && <span className={styles.note}>{spec.note}</span>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}
