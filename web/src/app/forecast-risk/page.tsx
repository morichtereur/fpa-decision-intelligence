import Link from "next/link";
import { api } from "@/lib/api";
import { formatEur } from "@/lib/format";
import BacktestBars from "@/components/BacktestBars";
import MonteCarloChart from "@/components/MonteCarloChart";
import styles from "./forecast-risk.module.css";

/** The simulation samples model assumptions, not business drivers, so its
 *  variable names are the model's. Translated here rather than shown raw. */
const SENSITIVITY_LABELS: Record<string, string> = {
  working_capital_pct: "Working capital, % of sales",
  operating_profit_target: "Operating profit within guidance",
  capex: "Capital expenditure",
  growth: "Revenue growth",
  ebitda_margin_pct: "EBITDA margin",
};

export const dynamic = "force-dynamic";

export default async function ForecastRiskPage() {
  const [backtest, monteCarlo] = await Promise.all([api.backtest(), api.monteCarlo()]);

  return (
    <div className={styles.page}>
      <div className={`label ${styles.eyebrow}`}>03 — Forecast &amp; Risk</div>
      <h1 className={styles.heading}>How confident should we be in the forecast?</h1>

      <section className={styles.section}>
        <h2 className={styles.sectionHeading}>Backtest: better model, not accurate model</h2>
        <p className={styles.sectionIntro}>
          The driver-based forecast produced a smaller error than a naive extrapolation on every
          metric — but both undershot what adidas actually delivered. Beating a naive baseline once
          is not the same claim as being reliable.
        </p>
        <div className={styles.backtestLayout}>
          <BacktestBars backtest={backtest} />
          <table className={styles.actualsTable}>
            <thead>
              <tr>
                <th></th>
                <th className={styles.num}>Naive</th>
                <th className={styles.num}>Driver-based</th>
                <th className={styles.num}>Actual</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Revenue</td>
                <td className={`mono ${styles.num}`}>{formatEur(backtest.naive.revenue)}</td>
                <td className={`mono ${styles.num}`}>{formatEur(backtest.driver_based.revenue)}</td>
                <td className={`mono ${styles.num}`}>{formatEur(backtest.actual.revenue)}</td>
              </tr>
              <tr>
                <td>Operating profit</td>
                <td className={`mono ${styles.num}`}>{formatEur(backtest.naive.operating_profit)}</td>
                <td className={`mono ${styles.num}`}>{formatEur(backtest.driver_based.operating_profit)}</td>
                <td className={`mono ${styles.num}`}>{formatEur(backtest.actual.operating_profit)}</td>
              </tr>
              <tr>
                <td>Free cash flow</td>
                <td className={`mono ${styles.num}`}>{formatEur(backtest.naive.free_cash_flow)}</td>
                <td className={`mono ${styles.num}`}>{formatEur(backtest.driver_based.free_cash_flow)}</td>
                <td className={`mono ${styles.num}`}>{formatEur(backtest.actual.free_cash_flow)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionHeading}>Forecast vintage</h2>
        <div className={styles.vintageEmpty}>
          <p>
            <strong>One backtest point, not a rolling history.</strong> A vintage timeline (plan →
            quarterly updates → actual) needs forecast snapshots taken through the year — this
            project has only the FY2024 report&rsquo;s initial FY2025 guidance and the FY2025
            actuals, an annual cross-section rather than a rolling forecast. Showing a fabricated
            multi-point timeline here would overstate what this data supports.
          </p>
          <div className={styles.vintageTimeline}>
            <div className={styles.vintagePoint}>
              <span className={styles.vintageDot} />
              <span className={styles.vintageLabel}>FY2024 report</span>
              <span className={styles.vintageSub}>Guidance set</span>
            </div>
            <div className={styles.vintageLine} />
            <div className={styles.vintagePoint}>
              <span className={styles.vintageDot} />
              <span className={styles.vintageLabel}>FY2025 actual</span>
              <span className={styles.vintageSub}>Checked against</span>
            </div>
          </div>
        </div>
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionHeading}>Monte Carlo range</h2>
        <p className={styles.sectionIntro}>{monteCarlo.caveat}</p>
        <MonteCarloChart monteCarlo={monteCarlo} actualFcf={backtest.actual.free_cash_flow} />
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionHeading}>Which assumption explains the most variance?</h2>
        <p className={styles.sectionIntro}>
          The simulation ranks assumptions by how much of the free-cash-flow spread each one
          explains. That is a statistical reading, and it is not the same question as where
          management should spend its attention — an assumption can dominate the variance and
          still be one nobody can move. Priorities answers that second question.
        </p>
        <ul className={styles.varianceList}>
          {Object.entries(monteCarlo.sensitivity_to_fcf).map(([name, correlation]) => (
            <li key={name}>
              <span>{SENSITIVITY_LABELS[name] ?? name}</span>
              <span className="mono">{correlation.toFixed(2)}</span>
            </li>
          ))}
        </ul>
        <Link href="/priorities" className={styles.moreLink}>
          Ranked management priorities →
        </Link>
      </section>
    </div>
  );
}
