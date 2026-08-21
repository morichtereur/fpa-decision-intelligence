import type { DecisionBriefResponse } from "@/lib/types";
import { formatEur, formatEurSigned } from "@/lib/format";
import styles from "./DecisionConsequence.module.css";

/** A variance rule's numbers are signed movements, so they take the signed
 *  formatter — otherwise a EUR 64m shortfall reads as "€-64m", with the minus
 *  stranded inside the currency rather than in front of the amount. Level
 *  rules (days, percentages) are plain readings and stay unsigned. */
function reading(rule: DecisionBriefResponse["rules"][number]): string {
  const isVariance = rule.condition.startsWith("variance");
  const asMoney = rule.metric_kind === "output";
  const show = (value: number) =>
    asMoney ? (isVariance ? formatEurSigned(value) : formatEur(value)) : value.toFixed(1);
  const direction = rule.condition.includes("above") ? "above" : "below";
  return `Modelled at ${show(rule.observed)}, ${direction} the ${show(rule.threshold)} threshold.`;
}

/**
 * The planner's answer to "so what?".
 *
 * A scenario tool that stops at the new number leaves the reader to work out
 * whether it matters. This says what the change did to the objective, which
 * thresholds it crossed, and what that puts on someone's agenda — in the same
 * marginal-label idiom as the Decision Brief, so the two read as one document
 * type at two scales.
 */
export default function DecisionConsequence({
  brief,
  hasChanges,
}: {
  brief: DecisionBriefResponse;
  hasChanges: boolean;
}) {
  const breached = brief.rules.filter((rule) => rule.breached);
  const { lead } = brief;
  const variance = brief.objective_variance;
  const objectiveName = brief.objective.toLowerCase();

  const lede = !hasChanges
    ? "This is the plan as configured. Move an assumption to see what decision it creates."
    : breached.length > 0
      ? `This scenario moves ${objectiveName} by ${formatEurSigned(variance)} and crosses ${
          breached.length === 1 ? "a threshold" : `${breached.length} thresholds`
        }.`
      : `This scenario moves ${objectiveName} by ${formatEurSigned(variance)} without crossing a threshold.`;

  return (
    <section className={styles.panel} aria-labelledby="consequence-heading">
      <div className={styles.header}>
        <h2 className="label" id="consequence-heading">
          What this scenario creates
        </h2>
        {hasChanges && (
          <span
            className={`${styles.verdict} ${
              breached.length > 0 ? styles.verdictBreached : styles.verdictClear
            }`}
          >
            {breached.length > 0 ? "Outside tolerance" : "Within tolerance"}
          </span>
        )}
      </div>

      {/* The one live region on the page. Moving a slider rewrites the whole
          results column — the comparison table, the bridge, the thresholds —
          and a screen reader announced none of it. Marking the summary
          sentence polite announces exactly what changed and why it matters,
          once per update. Marking the results column itself live would read
          out every figure in it on every keystroke, which is worse than
          silence. */}
      <p className={styles.lede} aria-live="polite">
        {lede}
      </p>

      {breached.length > 0 && (
        <ul className={styles.breaches}>
          {breached.map((rule) => (
            <li key={rule.id ?? rule.label} className={styles.breach}>
              <span className={styles.breachLabel}>{rule.label}</span>
              <span className={styles.breachSeverity}>{rule.severity}</span>
              <span className={styles.breachReading}>{reading(rule)}</span>
            </li>
          ))}
        </ul>
      )}

      <dl className={styles.rows}>
        <dt className={styles.term}>Priority</dt>
        <dd className={styles.definition}>
          <span className={styles.strong}>{lead.priority}</span>{" "}
          <span className={styles.muted}>
            · {lead.label} · {formatEur(lead.exposure_magnitude)} exposure
          </span>
        </dd>

        <dt className={styles.term}>Question</dt>
        <dd className={styles.definition}>
          {breached.length > 0 ? breached[0].management_question : lead.management_question}
        </dd>

        <dt className={styles.term}>Owner</dt>
        <dd className={styles.definition}>
          <span className={styles.strong}>
            {breached.length > 0 ? breached[0].suggested_owner : lead.suggested_owner}
          </span>{" "}
          <span className={styles.muted}>· suggested</span>
        </dd>

        <dt className={styles.term}>Next</dt>
        <dd className={styles.definition}>
          {(breached.length > 0 ? breached[0].trigger : lead.trigger) ||
            "No review trigger is configured for this exposure."}
        </dd>
      </dl>
    </section>
  );
}
