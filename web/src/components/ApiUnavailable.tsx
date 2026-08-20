import { API_BASE } from "@/lib/api";
import styles from "./ApiUnavailable.module.css";

/**
 * The API could not be reached.
 *
 * Every page here is server-rendered from the model, so an unreachable API
 * used to mean an unhandled throw and a platform crash page — the reader got
 * `FUNCTION_INVOCATION_FAILED` and no idea whose fault it was. On a free tier
 * that sleeps after inactivity, that is a normal Monday morning, not an edge
 * case.
 *
 * It names the address it tried, because the two failures that look identical
 * from outside — the service asleep, and the frontend built pointing at the
 * wrong host — need opposite responses.
 */
export default function ApiUnavailable({ detail }: { detail?: string }) {
  return (
    <div className={styles.panel}>
      <span className={`label ${styles.eyebrow}`}>Model unavailable</span>
      <h1 className={styles.heading}>The decision engine did not answer.</h1>
      <p className={styles.body}>
        Every figure on this site is computed by the model on request — nothing is
        pre-rendered — so with the engine unreachable there is nothing honest to show. No
        cached or placeholder numbers are displayed in its place.
      </p>
      <dl className={styles.rows}>
        <dt className={styles.term}>Tried</dt>
        <dd className={`mono ${styles.definition}`}>{API_BASE}</dd>

        <dt className={styles.term}>Likely</dt>
        <dd className={styles.definition}>
          The API sleeps after inactivity on its free tier and takes about a minute to wake.
          Reloading once or twice usually resolves it.
        </dd>

        {detail && (
          <>
            <dt className={styles.term}>Detail</dt>
            <dd className={`mono ${styles.definition}`}>{detail}</dd>
          </>
        )}
      </dl>
    </div>
  );
}
