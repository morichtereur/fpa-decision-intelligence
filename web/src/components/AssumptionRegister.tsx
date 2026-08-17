"use client";

import type { AssumptionRow } from "@/lib/types";
import { formatPct } from "@/lib/format";
import styles from "./AssumptionRegister.module.css";

function formatValue(row: AssumptionRow) {
  return row.unit === "pct" ? formatPct(row.current_value) : `€${Math.round(row.current_value)}m`;
}

export default function AssumptionRegister({ rows }: { rows: AssumptionRow[] }) {
  return (
    <div className={styles.register}>
      {rows.map((row) => (
        <details key={row.driver_id} className={styles.row}>
          <summary className={styles.summary}>
            <span className={styles.name}>{row.label}</span>
            <span className={`mono ${styles.value}`}>{formatValue(row)}</span>
            <span className={styles.badges}>
              <span className={styles.badge}>{row.confidence} confidence</span>
              <span className={styles.badge}>{row.sensitivity} sensitivity</span>
            </span>
            <span className={styles.chevron} aria-hidden="true">
              ＋
            </span>
          </summary>
          <div className={styles.detail}>
            <dl>
              <dt>Source</dt>
              <dd>{row.source}</dd>
              <dt>Guidance context</dt>
              <dd>{row.guidance_text}</dd>
              <dt>Fiscal year</dt>
              <dd>{row.fiscal_year}</dd>
            </dl>
          </div>
        </details>
      ))}
    </div>
  );
}
