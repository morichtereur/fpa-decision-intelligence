import { api } from "@/lib/api";
import { clientFrom, type SearchParams } from "@/lib/client";
import DriverTree from "@/components/DriverTree";
import AssumptionRegister from "@/components/AssumptionRegister";
import styles from "./model.module.css";

export const dynamic = "force-dynamic";

export default async function ModelPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const client = clientFrom(await searchParams);
  const [assumptions, summary, drivers] = await Promise.all([
    api.assumptions(client),
    api.client(client),
    api.drivers(client),
  ]);

  return (
    <div className={styles.page}>
      <div className={`label ${styles.eyebrow}`}>Model · {summary.short_label} · {summary.industry}</div>
      <h1 className={styles.heading}>How the forecast is actually built</h1>
      <p className={styles.intro}>
        No step here requires reading Python to understand. The calculation chain is fixed by
        the model; the drivers hanging off it come from {summary.name}&rsquo;s own configuration,
        which is where a client&rsquo;s economics live. The model is authoritative — this page is
        a window into it, not a separate description of it.
      </p>

      <section className={styles.section}>
        <h2 className={styles.sectionHeading}>Calculation chain</h2>
        <p className={styles.sectionIntro}>
          The chain is fixed by the model. The drivers to its right are
          {" "}{summary.short_label}&rsquo;s own, and change with the planning model.
        </p>
        <DriverTree drivers={drivers} />
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionHeading}>Assumption register</h2>
        <p className={styles.sectionIntro}>Click a row for its source and guidance context.</p>
        <AssumptionRegister rows={assumptions} />
      </section>

      {summary.has_backtest && (
      <section className={styles.section}>
        <h2 className={styles.sectionHeading}>Data lineage — an example</h2>
        <div className={styles.lineage}>
          <div className={styles.lineageStep}>
            <span className={styles.lineageLabel}>Source disclosure</span>
            <span className={styles.lineageValue}>
              adidas_Report_2024.pdf, Targets – Results – Outlook, &ldquo;2025 Outlook&rdquo; column
            </span>
          </div>
          <div className={styles.lineageArrow}>↓</div>
          <div className={styles.lineageStep}>
            <span className={styles.lineageLabel}>Extracted fact</span>
            <span className={styles.lineageValue}>Operating profit guidance: €1.7bn – €1.8bn</span>
          </div>
          <div className={styles.lineageArrow}>↓</div>
          <div className={styles.lineageStep}>
            <span className={styles.lineageLabel}>Model assumption</span>
            <span className={styles.lineageValue}>
              EBITDA margin back-solved to hit the €1.75bn midpoint at 8% revenue growth (11.6%)
            </span>
          </div>
          <div className={styles.lineageArrow}>↓</div>
          <div className={styles.lineageStep}>
            <span className={styles.lineageLabel}>Forecast output</span>
            <span className={styles.lineageValue}>Base-case operating profit: €1.75bn</span>
          </div>
        </div>
      </section>
      )}

      <section className={styles.section}>
        <h2 className={styles.sectionHeading}>What this is not</h2>
        <ul className={styles.notList}>
          {summary.is_synthetic && (
            <li>
              <strong>A real company.</strong> {summary.disclaimer}
            </li>
          )}
          <li>
            <strong>A multi-company benchmark.</strong> One company, two driver dimensions
            (product division, channel), three fiscal years.
          </li>
          <li>
            <strong>A price/volume analysis.</strong> adidas doesn&rsquo;t disclose that split —
            product division and channel growth are the real drivers used here.
          </li>
          <li>
            <strong>A track record.</strong> One backtest point. A single win over a naive baseline
            is not evidence the driver-based approach generalizes.
          </li>
          <li>
            <strong>A trading or investment signal.</strong> This is a methodology exercise on
            public financial disclosures.
          </li>
        </ul>
      </section>
    </div>
  );
}
