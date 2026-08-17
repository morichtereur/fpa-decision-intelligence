import styles from "./DriverTree.module.css";

const STEPS = [
  { title: "Revenue", detail: "Baseline product-division revenue × (1 + growth assumption)" },
  { title: "EBITDA", detail: "Revenue × EBITDA margin assumption" },
  { title: "Operating profit", detail: "EBITDA − D&A (held at baseline run-rate, scaled with revenue)" },
  { title: "NOPAT", detail: "Operating profit × (1 − effective tax rate)" },
  { title: "Free cash flow", detail: "NOPAT + D&A − change in working capital − capex" },
];

export default function DriverTree() {
  return (
    <div className={styles.tree}>
      {STEPS.map((step, i) => (
        <div key={step.title} className={styles.step}>
          <div className={styles.node}>
            <span className={styles.title}>{step.title}</span>
            <span className={styles.detail}>{step.detail}</span>
          </div>
          {i < STEPS.length - 1 && (
            <div className={styles.connector} aria-hidden="true">
              ↓
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
