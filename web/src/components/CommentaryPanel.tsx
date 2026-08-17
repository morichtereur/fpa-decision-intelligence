"use client";

import type { CommentaryResponse } from "@/lib/types";
import styles from "./CommentaryPanel.module.css";

export default function CommentaryPanel({
  commentary,
  loading,
  error,
  onGenerate,
  canGenerate,
}: {
  commentary: CommentaryResponse | null;
  loading: boolean;
  error: string | null;
  onGenerate: () => void;
  canGenerate: boolean;
}) {
  const rate = commentary?.grounding.grounding_rate;

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <span className={`label ${styles.title}`}>Management Commentary</span>
        {commentary && (
          <span className={styles.status}>
            Draft · Numerically verified
            {rate !== null && rate !== undefined && (
              <span className={rate === 1 ? styles.rateGood : styles.rateWarn}>
                {" "}
                ({commentary.grounding.grounded}/{commentary.grounding.total_claims})
              </span>
            )}
          </span>
        )}
      </div>

      {commentary ? (
        <blockquote className={styles.text}>{commentary.text}</blockquote>
      ) : (
        <div className={styles.empty}>
          <p>
            Commentary is generated from this scenario&rsquo;s calculated outputs only — the model
            never sees raw source text, and every number it states is checked back against the
            output table.
          </p>
          <button type="button" className={styles.generate} onClick={onGenerate} disabled={!canGenerate || loading}>
            {loading ? "Generating…" : "Generate commentary for this scenario"}
          </button>
          {error && <p className={styles.error}>{error}</p>}
        </div>
      )}

      {commentary && commentary.grounding.ungrounded.length > 0 && (
        <details className={styles.details}>
          <summary>{commentary.grounding.ungrounded.length} claim(s) could not be verified</summary>
          <ul>
            {commentary.grounding.ungrounded.map((claim) => (
              <li key={claim} className="mono">
                {claim}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
