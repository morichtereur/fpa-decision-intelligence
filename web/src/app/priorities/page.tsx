import { api } from "@/lib/api";
import PriorityTable from "@/components/PriorityTable";
import styles from "./priorities.module.css";

export const dynamic = "force-dynamic";

export default async function PrioritiesPage() {
  const { ranked, methodology } = await api.priorities();

  return (
    <div className={styles.page}>
      <span className={`label ${styles.eyebrow}`}>Priorities · {methodology.objective}</span>
      <h1 className={styles.heading}>Where should management spend its next 30 minutes?</h1>
      <p className={styles.intro}>
        Every planning driver, ranked by what it would take to move it and what moving it is
        worth. The order is not by size: an exposure management cannot influence inside the
        year ranks below a smaller one it can, because attention is a budget and it should be
        spent where it converts into an outcome.
      </p>

      <PriorityTable rows={ranked} />

      <section className={styles.section}>
        <h2 className={styles.sectionHeading}>How this ranking is produced</h2>
        <div className={styles.method}>
          {methodology.axes.map((axis) => (
            <div key={axis.name}>
              <div className={styles.axisName}>
                {axis.name}
                <span
                  className={`${styles.basis} ${
                    axis.basis === "computed" ? styles.computed : styles.declared
                  }`}
                >
                  {axis.basis}
                </span>
              </div>
              <p className={styles.axisDetail}>{axis.detail}</p>
            </div>
          ))}
        </div>

        <p className={styles.thresholdNote}>{methodology.threshold_text}</p>

        <table className={styles.ruleTable}>
          <caption className="visually-hidden">
            The rule that converts the three axes into a priority band.
          </caption>
          <thead>
            <tr>
              <th scope="col">When</th>
              <th scope="col">Priority</th>
              <th scope="col">Why</th>
            </tr>
          </thead>
          <tbody>
            {methodology.rules.map((rule) => (
              <tr key={rule.when}>
                <td>{rule.when}</td>
                <td className={styles.then}>{rule.then}</td>
                <td>{rule.why}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionHeading}>What this ranking is not</h2>
        <ul className={styles.limits}>
          {methodology.limitations.map((limitation) => (
            <li key={limitation}>{limitation}</li>
          ))}
        </ul>
      </section>
    </div>
  );
}
