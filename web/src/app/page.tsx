import Link from "next/link";
import { api } from "@/lib/api";
import { clientFrom, withClient, type SearchParams } from "@/lib/client";
import { formatEur, formatSignedPct } from "@/lib/format";
import DecisionBrief from "@/components/DecisionBrief";
import MetricDisplay from "@/components/MetricDisplay";
import DeltaTag from "@/components/DeltaTag";
import BacktestBars from "@/components/BacktestBars";
import styles from "./page.module.css";

export const dynamic = "force-dynamic";

export default async function OutlookPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const client = clientFrom(await searchParams);
  const [outlook, brief] = await Promise.all([api.outlook(client), api.decisionBrief(client)]);
  const { forecast, backtest, statement } = outlook;

  const revDelta = backtest?.driver_based.revenue_error_pct ?? 0;
  const opDelta = backtest?.driver_based.operating_profit_error_pct ?? 0;
  const fcfDelta = backtest?.driver_based.free_cash_flow_error_pct ?? 0;

  return (
    <div className={styles.page}>
      {/* Management state first, then the outlook that produced it. An
          executive arrives asking what needs attention, not what the model
          scored — the evidence for the answer comes further down. */}
      <section className={styles.briefSection}>
        <DecisionBrief brief={brief} />
      </section>

      <section className={styles.statementSection}>
        <div className={`label ${styles.eyebrow}`}>Outlook · {brief.client.fiscal_year}</div>
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
            {backtest && <DeltaTag text={`${formatSignedPct(revDelta)} vs. actual`} direction="neutral" />}
          </div>
          <div className={styles.metricCol}>
            <MetricDisplay label="Operating profit forecast" value={formatEur(forecast.operating_profit)} />
            {backtest && <DeltaTag text={`${formatSignedPct(opDelta)} vs. actual`} direction="neutral" />}
          </div>
          <div className={styles.metricCol}>
            <MetricDisplay label="Free cash flow forecast" value={formatEur(forecast.free_cash_flow)} />
            {backtest && <DeltaTag text={`${formatSignedPct(fcfDelta)} vs. actual`} direction="neutral" />}
          </div>
        </div>
        <p className={styles.metricsNote}>
          {backtest ? (
            <>
              Built as of {brief.client.fiscal_year === "FY2025" ? "FY2024" : "the baseline year"} using
              only that year&rsquo;s data and {brief.client.short_label}&rsquo;s own stated guidance —
              deltas shown are the forecast error against what actually happened, not a live
              re-forecast.
            </>
          ) : (
            <>
              Synthetic client: there is no actual outturn to measure this forecast against, so no
              error is shown. A backtest on invented data would look like evidence and be none.
            </>
          )}
        </p>
      </section>

      <section className={styles.splitSection}>
        <div>
          <h2 className={styles.sectionHeading}>Ranked exposures</h2>
          <ol className={styles.rankList}>
            {brief.ranked.slice(0, 4).map((row) => (
              <li key={row.driver_id} className={styles.rankItem}>
                <span className={styles.rankName}>{row.label}</span>
                <span className={styles.rankBand}>{row.priority}</span>
                <span className={`mono ${styles.rankValue}`}>
                  {formatEur(row.exposure_magnitude)}
                </span>
              </li>
            ))}
          </ol>
          <Link href={withClient("/priorities", client)} className={styles.moreLink}>
            All priorities and how they are ranked →
          </Link>
        </div>
        <div>
          <h2 className={styles.sectionHeading}>
            {backtest ? "Backtested against actuals" : "Forecast confidence"}
          </h2>
          {backtest ? (
            <BacktestBars backtest={backtest} />
          ) : (
            <p className={styles.noBacktest}>
              No backtest is available for a synthetic client. The simulation still shows the
              range the plan could land in.
            </p>
          )}
          <Link href={withClient("/forecast-risk", client)} className={styles.moreLink}>
            {backtest ? "Full backtest and Monte Carlo range →" : "Monte Carlo range →"}
          </Link>
        </div>
      </section>
    </div>
  );
}
