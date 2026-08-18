import { Fragment } from "react";
import type { Band, Priority, PriorityRow } from "@/lib/types";
import { formatEur } from "@/lib/format";
import styles from "./PriorityTable.module.css";

const BANDS: Priority[] = ["Critical", "Act", "Review", "Monitor"];

const BAND_BAR = {
  Critical: styles.barCritical,
  Act: styles.barAct,
  Review: styles.barReview,
  Monitor: styles.barMonitor,
} as const;

/** What each band means for the reader's next half hour. Stated on the page
 *  rather than left for the reader to infer from a colour. */
const BAND_MEANING: Record<Priority, string> = {
  Critical: "Material, unresolved, and movable",
  Act: "Material and within management's control",
  Review: "Moderate exposure, controllable",
  Monitor: "Watch — too small, or not management's to move",
};

/** The three axis columns already say why an Act row is an Act row. A
 *  rationale line earns its space only where the band is NOT what the
 *  exposure alone would suggest — a large exposure held down to Monitor, or a
 *  Critical escalation — which is exactly where a reader pauses to ask why. */
function explains(row: PriorityRow): boolean {
  if (row.priority === "Critical") return true;
  return row.priority === "Monitor" && row.materiality !== "Low";
}

function axisClass(level: Band) {
  return level === "High" ? styles.axisHigh : styles.axis;
}

export default function PriorityTable({ rows }: { rows: PriorityRow[] }) {
  const largest = Math.max(...rows.map((r) => r.exposure_magnitude), 1);
  const present = BANDS.filter((band) => rows.some((r) => r.priority === band));

  return (
    <div className={styles.wrap}>
      <table className={styles.table}>
        <caption className="visually-hidden">
          Planning drivers ranked by management priority, showing financial exposure,
          materiality, uncertainty and controllability.
        </caption>
        <thead className={styles.head}>
          <tr>
            <th scope="col">Driver</th>
            <th scope="col">Materiality</th>
            <th scope="col">Uncertainty</th>
            <th scope="col">Control</th>
            <th scope="col">Exposure</th>
          </tr>
        </thead>
        {present.map((band) => {
          const bandRows = rows.filter((r) => r.priority === band);
          const total = bandRows.reduce((sum, r) => sum + r.exposure_magnitude, 0);
          return (
            <tbody
              key={band}
              className={`${styles.band} ${band === "Critical" ? styles.bandCritical : ""}`}
            >
              <tr className={styles.bandRow}>
                <th colSpan={5} scope="colgroup">
                  <span className={styles.bandHead}>
                    <span className={styles.bandName}>{band}</span>
                    <span className={styles.bandMeta}>
                      {BAND_MEANING[band]} · {bandRows.length} driver
                      {bandRows.length === 1 ? "" : "s"} · {formatEur(total)}
                    </span>
                  </span>
                </th>
              </tr>
              {bandRows.map((row) => (
                <Fragment key={row.driver_id}>
                  <tr className={styles.row}>
                    <td>
                      <span className={styles.driver}>{row.label}</span>
                      <span className={styles.owner}>
                        {row.category} · {row.owner}
                      </span>
                    </td>
                    <td className={axisClass(row.materiality)}>{row.materiality}</td>
                    <td className={axisClass(row.uncertainty)}>{row.uncertainty}</td>
                    <td className={axisClass(row.controllability)}>{row.controllability}</td>
                    <td>
                      <span className={`mono ${styles.exposure}`}>
                        {formatEur(row.exposure_magnitude)}
                      </span>
                      <span
                        className={`${styles.bar} ${BAND_BAR[row.priority]}`}
                        style={{ width: `${(row.exposure_magnitude / largest) * 100}%` }}
                        aria-hidden="true"
                      />
                    </td>
                  </tr>
                  {explains(row) && (
                    <tr className={styles.rationaleRow}>
                      <td colSpan={5}>
                        <span className={styles.rationale}>{row.rationale}</span>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          );
        })}
      </table>
    </div>
  );
}
