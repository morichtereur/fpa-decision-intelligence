"use client";

import type { CommentaryResponse } from "@/lib/types";
import styles from "./CommentaryPanel.module.css";

/**
 * The written note that accompanies the numbers.
 *
 * Deliberately the quietest thing on the page. The deterministic engine
 * calculates; this only describes what it calculated, and the product is
 * fully usable with it switched off. What is NOT quiet is the verification
 * footnote: every figure in the paragraph is checked back against the output
 * table, and a reader deciding whether to trust the prose should see that
 * before they see who wrote it.
 */
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
  const grounding = commentary?.grounding;
  const rate = grounding?.grounding_rate;
  const coherence = commentary?.coherence;
  const provenance = commentary?.provenance;
  const allGrounded = rate === 1;

  return (
    <section className={styles.panel} aria-labelledby="note-heading">
      <div className={styles.header}>
        <h2 className={`label ${styles.title}`} id="note-heading">
          Management note
        </h2>
      </div>

      {commentary ? (
        <>
          <p className={styles.text}>{commentary.text}</p>
          <p className={styles.footnote}>
            <span className={allGrounded ? styles.checkGood : styles.checkWarn}>
              {grounding?.grounded ?? 0}/{grounding?.total_claims ?? 0} figures traced to the
              output table
            </span>
            {coherence && (
              <span className={coherence.clean ? styles.checkGood : styles.checkWarn}>
                {coherence.clean
                  ? "no unsupported comparisons"
                  : `${coherence.finding_count} unsupported comparison(s)`}
              </span>
            )}
            <span>
              Drafted from the calculated outputs only
              {provenance?.model ? ` by ${provenance.model}` : ""}. It computes nothing.
            </span>
          </p>
        </>
      ) : (
        <div className={styles.empty}>
          <p>
            A short written reading of this scenario, drafted from its calculated outputs. Every
            figure it states is checked back against the output table, and every comparison
            against what that table actually supports. Nothing here is required to use the model.
          </p>
          <button
            type="button"
            className={styles.generate}
            onClick={onGenerate}
            disabled={!canGenerate || loading}
          >
            {loading ? "Drafting…" : "Draft a note on this scenario"}
          </button>
          {error && <p className={styles.error}>{error}</p>}
        </div>
      )}

      {grounding && grounding.ungrounded.length > 0 && (
        <details className={styles.details}>
          <summary>{grounding.ungrounded.length} figure(s) could not be traced</summary>
          <ul>
            {grounding.ungrounded.map((claim) => (
              <li key={claim} className="mono">
                {claim}
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}
