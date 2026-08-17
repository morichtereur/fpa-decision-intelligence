import { api } from "@/lib/api";
import { formatEur } from "@/lib/format";
import BacktestBars from "@/components/BacktestBars";
import MonteCarloChart from "@/components/MonteCarloChart";
import DriverPriorityList from "@/components/DriverPriorityList";
import styles from "./forecast-risk.module.css";

export const dynamic = "force-dynamic";

export default async function ForecastRiskPage() {
  const [backtest, monteCarlo, driverPriority] = await Promise.all([
    api.backtest(),
    api.monteCarlo(),
    api.driverPriority(),
  ]);

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
        <h2 className={styles.sectionHeading}>Where should FP&amp;A spend the next hour of diligence?</h2>
        <p className={styles.sectionIntro}>
          Ranked by simulated sensitivity to free cash flow, combined with how confident the
          underlying assumption is.
        </p>
        <DriverPriorityList rows={driverPriority} />
      </section>
    </div>
  );
}
