import type { ClientSummary, DriverConfig } from "@/lib/types";
import styles from "./DriverTree.module.css";

/** The calculation chain is fixed by the model. What varies per client is
 *  which of its drivers feed each step — so the chain is the spine and the
 *  client's own drivers hang off it, rather than the whole diagram being
 *  hardcoded for one company. */
const CHAIN = [
  {
    title: "Revenue",
    assumption: "division_growth",
    detail: "Baseline revenue by segment × (1 + growth assumption)",
  },
  {
    title: "EBITDA",
    assumption: "ebitda_margin_pct",
    detail: "Revenue × EBITDA margin assumption",
  },
  {
    title: "Operating profit",
    assumption: null,
    detail: "EBITDA − D&A (held at baseline run-rate, scaled with revenue)",
  },
  {
    title: "NOPAT",
    assumption: "effective_tax_rate_pct",
    detail: "Operating profit × (1 − effective tax rate)",
  },
  {
    title: "Free cash flow",
    assumption: "operating_working_capital_pct|capex_eur_m",
    detail: "NOPAT + D&A − change in working capital − capex",
  },
] as const;

export default function DriverTree({
  summary,
  drivers,
}: {
  summary: ClientSummary;
  drivers: DriverConfig;
}) {
  const feeding = (assumption: string | null) => {
    if (!assumption) return [];
    const keys = assumption.split("|");
    return Object.entries(drivers)
      .filter(([, spec]) => keys.includes(spec.maps_to))
      .map(([id, spec]) => ({ id, label: spec.label, role: spec.role }));
  };

  return (
    <div className={styles.tree}>
      {CHAIN.map((step, i) => {
        const inputs = feeding(step.assumption);
        return (
          <div key={step.title} className={styles.step}>
            <div className={styles.row}>
              <div className={styles.node}>
                <span className={styles.title}>{step.title}</span>
                <span className={styles.detail}>{step.detail}</span>
              </div>
              {inputs.length > 0 && (
                <div className={styles.inputs}>
                  <span className={styles.inputsLabel}>
                    {summary.short_label} drivers
                  </span>
                  <ul className={styles.inputList}>
                    {inputs.map((input) => (
                      <li key={input.id}>
                        {input.label}
                        {input.role !== "base" && (
                          <span className={styles.role}> · {input.role}</span>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
            {i < CHAIN.length - 1 && (
              <div className={styles.connector} aria-hidden="true">
                ↓
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
