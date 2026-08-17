import Link from "next/link";
import { api } from "@/lib/api";
import { formatEur, formatEurSigned, formatSignedPct } from "@/lib/format";
import MetricDisplay from "@/components/MetricDisplay";
import DeltaTag from "@/components/DeltaTag";
import BacktestBars from "@/components/BacktestBars";
import DriverPriorityList from "@/components/DriverPriorityList";
import styles from "./page.module.css";

export const dynamic = "force-dynamic";

export default async function OutlookPage() {
  const [outlook, drivers] = await Promise.all([api.outlook(), api.drivers()]);
  const { forecast, backtest, statement, driver_priority } = outlook;

  // What would it have cost, in FCF, if the base forecast had used FY2025's
  // *actual* working-capital ratio instead of the guidance-based
  // assumption? A real computed number, not an invented one — one extra
  // scenario call rather than a hardcoded figure.
  const actualWcScenario = await api.scenario({
    revenue_growth: drivers.revenue_growth.default,
    ebitda_margin: drivers.ebitda_margin.default,
    working_capital_pct: 23.0,
    capex_eur_m: drivers.capex_eur_m.default,
    tax_rate_pct: drivers.tax_rate_pct.default,
  });

  const revDelta = backtest.driver_based.revenue_error_pct ?? 0;
  const opDelta = backtest.driver_based.operating_profit_error_pct ?? 0;
  const fcfDelta = backtest.driver_based.free_cash_flow_error_pct ?? 0;

  return (
    <div className={styles.page}>
      <section className={styles.statementSection}>
        <div className={`label ${styles.eyebrow}`}>01 — Outlook · FY2025</div>
        <h1 className={styles.headline}>{statement.headline}</h1>
        <ul className={styles.evidence}>
          {statement.evidence.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      </section>

      <section className={styles.metricsSection}>
        <div className={styles.metricsRow}>
          <div className={styles.metricCol}>
            <MetricDisplay label="Revenue forecast" value={formatEur(forecast.revenue)} />
            <DeltaTag text={`${formatSignedPct(revDelta)} vs. actual`} direction="neutral" />
          </div>
          <div className={styles.metricCol}>
            <MetricDisplay label="Operating profit forecast" value={formatEur(forecast.operating_profit)} />
            <DeltaTag text={`${formatSignedPct(opDelta)} vs. actual`} direction="neutral" />
          </div>
          <div className={styles.metricCol}>
            <MetricDisplay label="Free cash flow forecast" value={formatEur(forecast.free_cash_flow)} />
            <DeltaTag text={`${formatSignedPct(fcfDelta)} vs. actual`} direction="neutral" />
          </div>
        </div>
        <p className={styles.metricsNote}>
          Built as of FY2024 using only that year&rsquo;s data and adidas&rsquo;s own stated FY2025
          guidance — deltas shown are the forecast error against what actually happened, not a live
          re-forecast.
        </p>
      </section>

      <section className={styles.splitSection}>
        <div>
          <h2 className={styles.sectionHeading}>Backtested against FY2025 actuals</h2>
          <BacktestBars backtest={backtest} />
          <Link href="/forecast-risk" className={styles.moreLink}>
            Full backtest and Monte Carlo range →
          </Link>
        </div>
        <div>
          <h2 className={styles.sectionHeading}>Management attention</h2>
          <DriverPriorityList rows={driver_priority} />
          <Link href="/planner" className={styles.moreLink}>
            Open Scenario Planner →
          </Link>
        </div>
      </section>

      <section className={styles.exposureSection}>
        <h2 className={styles.sectionHeading}>Largest financial exposure</h2>
        <p className={styles.exposureText}>
          The base forecast assumes working capital at{" "}
          <strong className="mono">{forecast.assumptions.operating_working_capital_pct.toFixed(1)}%</strong> of
          net sales. Actual FY2025 came in at <strong className="mono">23.0%</strong> — modelling that
          single change against an otherwise unchanged base forecast moves free cash flow by{" "}
          <strong className="mono">{formatEurSigned(actualWcScenario.deltas.free_cash_flow)}</strong>, more
          than any other single driver at this magnitude of move.
        </p>
      </section>
    </div>
  );
}
