import type { DecisionBriefResponse } from "@/lib/types";
import { formatEur } from "@/lib/format";
import styles from "./DecisionBrief.module.css";

/** One point of a percentage driver, or one day of a days-based one. Only
 *  these two units have a per-unit reading a CFO would use — "per €1m of
 *  capex" is a tautology, so it is not shown. */
function perUnitLabel(unit: string): string | null {
  if (unit === "pct" || unit === "ppt") return "point";
  if (unit === "days") return "day";
  return null;
}

function rangeText(low: number, high: number, unit: string): string {
  if (unit === "eur_m") return `${formatEur(low)}–${formatEur(high)}`;
  const suffix = unit === "days" ? " days" : "%";
  return `${low.toLocaleString("en-US")}–${high.toLocaleString("en-US")}${suffix}`;
}

const STATE_CLASS = {
  critical: styles.stateCritical,
  attention: styles.stateAttention,
  steady: styles.stateSteady,
} as const;

/**
 * The executive brief: what matters, how much is at risk, why, whether it is
 * outside tolerance, whether management can move it, what to ask, who owns
 * it, and what happens next — in one editorial composition rather than eight
 * tiles. The labels sit in the margin, as they would in a board paper.
 */
export default function DecisionBrief({ brief }: { brief: DecisionBriefResponse }) {
  const { lead, attention, client } = brief;
  const unitLabel = perUnitLabel(lead.unit);
  const objectiveName = brief.objective.toLowerCase();

  const standfirst =
    lead.priority === "Monitor"
      ? `Nothing in the plan is both material and within management's control.`
      : `${lead.label} is the largest exposure management can act on.`;

  return (
    <section className={styles.brief} aria-labelledby="decision-brief-heading">
      <div className={styles.header}>
        <h2 className="label" id="decision-brief-heading">
          Decision brief · {client.fiscal_year}
        </h2>
        <span className={`${styles.state} ${STATE_CLASS[attention.state]}`}>
          {attention.headline}
        </span>
      </div>

      <p className={styles.standfirst}>{standfirst}</p>

      <dl className={styles.rows}>
        <dt className={styles.term}>What matters</dt>
        <dd className={styles.definition}>
          <span className={styles.axisValue}>{lead.label}</span>{" "}
          <span className={styles.suggested}>· {lead.category}</span>
          <span className={styles.qualifier}>{lead.rationale}</span>
        </dd>

        <dt className={styles.term}>At risk</dt>
        <dd className={styles.definition}>
          <span className={`mono ${styles.figure}`}>{formatEur(lead.exposure_magnitude)}</span>
          <span className={styles.qualifier}>
            swing in {objectiveName} across {rangeText(lead.range_low, lead.range_high, lead.unit)}
            {" — "}
            {lead.range_basis}
          </span>
          {unitLabel && (
            <span className={styles.perUnit}>
              One {unitLabel} of {lead.label.toLowerCase()}{" "}
              {lead.per_unit < 0 ? "costs" : "adds"}{" "}
              <span className="mono">{formatEur(Math.abs(lead.per_unit))}</span> of {objectiveName}.
            </span>
          )}
        </dd>

        <dt className={styles.term}>Tolerance</dt>
        <dd className={styles.definition}>
          {lead.threshold ? (
            <>
              <span className={styles.breached}>Outside tolerance</span>
              <span className={styles.qualifier}>{lead.threshold.label}</span>
            </>
          ) : (
            <>
              <span className={styles.within}>Within tolerance</span>
              <span className={styles.qualifier}>
                {brief.breached_count === 0
                  ? "No configured threshold is breached at these assumptions."
                  : `${brief.breached_count} threshold(s) breached elsewhere in the plan.`}
              </span>
            </>
          )}
        </dd>

        <dt className={styles.term}>Control</dt>
        <dd className={styles.definition}>
          <div className={styles.axis}>
            <span className={styles.axisValue}>{lead.controllability}</span>
            <span className={styles.suggested}>
              uncertainty {lead.uncertainty.toLowerCase()} · materiality {lead.materiality.toLowerCase()}
            </span>
          </div>
          <span className={styles.qualifier}>
            Controllability and uncertainty are stated judgements recorded in the client model,
            not measurements. Exposure is computed.
          </span>
        </dd>

        <dt className={styles.term}>Question</dt>
        <dd className={styles.definition}>
          <p className={styles.question}>{lead.management_question}</p>
        </dd>

        <dt className={styles.term}>Owner</dt>
        <dd className={styles.definition}>
          <span className={styles.axisValue}>{lead.suggested_owner}</span>{" "}
          <span className={styles.suggested}>· suggested</span>
        </dd>

        <dt className={styles.term}>Next</dt>
        <dd className={styles.definition}>
          {lead.trigger || "No review trigger is configured for this exposure."}
          {lead.next_action ? (
            <span className={styles.qualifier}>{lead.next_action}</span>
          ) : (
            lead.watching_rule && (
              <span className={styles.qualifier}>
                Watched by “{lead.watching_rule}”, which has not been triggered at these
                assumptions.
              </span>
            )
          )}
        </dd>
      </dl>
    </section>
  );
}
