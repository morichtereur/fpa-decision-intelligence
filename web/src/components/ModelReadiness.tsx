import type { Readiness } from "@/lib/types";
import styles from "./ModelReadiness.module.css";

/**
 * What this planning model cannot answer about itself.
 *
 * The only output here that is useful before the numbers are trusted. On day
 * one of an engagement the drivers are half-agreed and nobody has settled a
 * plausible range — and the gaps are the finding, not an obstacle to one.
 */
export default function ModelReadiness({ readiness }: { readiness: Readiness }) {
  return (
    <>
      <p className={styles.summary}>{readiness.summary}</p>
      <ul className={styles.list}>
        {readiness.checks.map((check) => (
          <li
            key={check.id}
            className={`${styles.row} ${check.complete ? styles.answered : styles.open}`}
          >
            <span className={styles.question}>{check.question}</span>
            <span className={styles.detail}>{check.detail}</span>
            {!check.complete && <span className={styles.why}>{check.why}</span>}
          </li>
        ))}
      </ul>
      <p className={styles.note}>{readiness.note}</p>
    </>
  );
}
