import type { DriverPriorityRow } from "@/lib/types";
import styles from "./DriverPriorityList.module.css";

// "High" means opposite things for the two axes: high SENSITIVITY is a
// risk flag (worth attention), high CONFIDENCE is reassuring. Using one
// color scale for both would send a confusing mixed signal, so they're
// mapped separately rather than sharing a generic "levelClass".
function sensitivityClass(level: string) {
  if (level === "High") return styles.attention;
  if (level === "Medium") return styles.neutral;
  return styles.muted;
}

function confidenceClass(level: string) {
  if (level === "High") return styles.reassuring;
  if (level === "Medium") return styles.neutral;
  return styles.attention;
}

export default function DriverPriorityList({ rows }: { rows: DriverPriorityRow[] }) {
  return (
    <ol className={styles.list}>
      {rows.map((row, i) => (
        <li key={row.driver_id} className={styles.item}>
          <span className={`mono ${styles.rank}`}>{i + 1}</span>
          <div className={styles.body}>
            <div className={styles.name}>{row.label}</div>
            <div className={styles.meta}>
              <span className={sensitivityClass(row.sensitivity)}>{row.sensitivity} sensitivity</span>
              <span className={styles.dot}>·</span>
              <span className={confidenceClass(row.confidence)}>{row.confidence} confidence</span>
            </div>
          </div>
        </li>
      ))}
    </ol>
  );
}
